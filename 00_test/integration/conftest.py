"""Integration test configuration.

Real SQLite (in-memory) + FastAPI TestClient.
External services (MinIO, NATS) are mocked.

Provides:
- In-memory SQLite with real schema and repositories
- FastAPI TestClient with real routes, real auth, mocked storage/queue
- Helper functions to create test data
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = PROJECT_ROOT / "02_backend"
INTEGRATION_DIR = Path(__file__).resolve().parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Make helpers.py importable
if str(INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_DIR))

# ---------------------------------------------------------------------------
# Pre-mock external packages that may not be installed
# ---------------------------------------------------------------------------
for _pkg in (
    # MinIO client + all submodules
    "minio", "minio.error", "minio.commonconfig", "minio.deleteobjects",
    "minio.helpers", "minio.datatypes", "minio.credentials",
    # NATS client + all submodules
    "nats", "nats.js", "nats.js.api", "nats.aio", "nats.aio.client",
    "nats.aio.subscription", "nats.errors",
    # APScheduler
    "apscheduler", "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers", "apscheduler.triggers.interval",
):
    sys.modules.setdefault(_pkg, MagicMock())

# ---------------------------------------------------------------------------
# Environment (must be set before ANY app imports)
# ---------------------------------------------------------------------------
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "testkey"
os.environ["MINIO_SECRET_KEY"] = "testsecret"
os.environ["NATS_URL"] = "nats://localhost:4222"
os.environ["SEED_SERVICES"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["SECRET_KEY"] = "integration-test-secret"

# Prevent pydantic-settings from reading the project .env file
# by patching the Config before Settings() is instantiated.
# Since we set env vars above, all values come from environment.
import pydantic_settings

_orig_init = pydantic_settings.BaseSettings.__init_subclass__


# ---------------------------------------------------------------------------
# Force config to ignore extra env vars from .env
# ---------------------------------------------------------------------------
# Patch Settings to ignore extra fields and not read .env
_config_patched = False
if not _config_patched:
    # Import with env_file disabled
    import importlib.util

    _cfg_path = BACKEND_ROOT / "app" / "config.py"
    _cfg_spec = importlib.util.spec_from_file_location("app.config", _cfg_path)
    _cfg_mod = importlib.util.module_from_spec(_cfg_spec)

    # Temporarily override to prevent .env reading
    _orig_env_file = os.environ.get("ENV_FILE_OVERRIDE")
    _cfg_spec.loader.exec_module(_cfg_mod)

    # Re-create settings without .env file
    _SettingsClass = _cfg_mod.Settings

    # Create settings manually with only env vars (no .env file)
    try:
        _cfg_mod.settings = _SettingsClass(
            _env_file=None,  # pydantic-settings v2: skip .env
        )
    except TypeError:
        # Fallback: pydantic-settings v1
        _cfg_mod.settings = _SettingsClass()

    sys.modules["app.config"] = _cfg_mod
    _config_patched = True


# ---------------------------------------------------------------------------
# Database engine (in-memory SQLite)
# ---------------------------------------------------------------------------
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)

# Create all tables
from app.infrastructure.database.models import Base

Base.metadata.create_all(bind=test_engine)

# Patch connection module so app code uses the test engine
import app.infrastructure.database.connection as _conn_mod

_conn_mod.engine = test_engine
_conn_mod.SessionLocal = TestSessionLocal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables before each test for isolation."""
    session = TestSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()
    yield


@pytest.fixture
def db():
    """Database session for direct repository/service testing."""
    session = TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    """FastAPI TestClient with real routes, real DB, mocked storage/queue."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.router import api_router
    from app.api.deps import get_db, get_storage, get_queue
    from app.core.exceptions import AppException
    from app.core.middleware import app_exception_handler

    test_app = FastAPI()
    test_app.include_router(api_router, prefix="/api/v1")
    test_app.add_exception_handler(AppException, app_exception_handler)

    # DB dependency: new session per request (like production)
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    # Mock external services
    mock_storage = MagicMock()
    mock_storage.download = AsyncMock(return_value=b"mock result content")
    mock_storage.upload = AsyncMock()
    mock_storage.upload_stream = AsyncMock()
    mock_storage.ensure_buckets = AsyncMock()
    mock_storage.get_presigned_url = AsyncMock(
        return_value="https://test.local/presigned"
    )
    mock_storage.exists = AsyncMock(return_value=True)
    mock_storage.move = AsyncMock()
    mock_storage.delete = AsyncMock()
    mock_storage.delete_many = AsyncMock()

    mock_queue = MagicMock()
    mock_queue.publish = AsyncMock()
    mock_queue.connect = AsyncMock()
    mock_queue.ensure_streams = AsyncMock()

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_storage] = lambda: mock_storage
    test_app.dependency_overrides[get_queue] = lambda: mock_queue

    with TestClient(test_app) as c:
        c._mock_storage = mock_storage
        c._mock_queue = mock_queue
        yield c


# Helper functions are in helpers.py (importable by test modules)
