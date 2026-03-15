"""Backend unit test fixtures.

Provides shared fixtures for all backend unit tests:
- Module loading via importlib (avoids triggering full app import chain)
- Mock factories for common objects (jobs, requests, files)
- Async event loop
- Sample file bytes
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module loader — import backend modules without triggering app startup
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def load_module(relative_path: str, module_name: str):
    """Load a module from 02_backend/app/ without importing the full app."""
    mod_path = BACKEND_ROOT / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock()),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


def load_module_clean(relative_path: str, module_name: str):
    """Load a module that has no app-level dependencies."""
    mod_path = BACKEND_ROOT / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Async event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def make_job(
    job_id="job-1",
    status="PROCESSING",
    retry_count=0,
    error_history="[]",
    method="ocr_paddle_text",
    tier=0,
    request_id="req-1",
    file_id="file-1",
    result_path=None,
    worker_id=None,
    user_id="user-1",
):
    return SimpleNamespace(
        id=job_id,
        status=status,
        retry_count=retry_count,
        error_history=error_history,
        method=method,
        tier=tier,
        request_id=request_id,
        file_id=file_id,
        result_path=result_path,
        worker_id=worker_id,
        request=SimpleNamespace(
            id=request_id,
            user_id=user_id,
            output_format="txt",
        ),
    )


def make_request(
    request_id="req-1",
    user_id="user-1",
    status="PROCESSING",
    file_count=1,
    method="ocr_paddle_text",
    tier=0,
    output_format="txt",
    created_at=None,
):
    from datetime import datetime, timezone
    return SimpleNamespace(
        id=request_id,
        user_id=user_id,
        status=status,
        file_count=file_count,
        method=method,
        tier=tier,
        output_format=output_format,
        created_at=created_at or datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )


def make_file(
    file_id="file-1",
    request_id="req-1",
    original_name="test.png",
    mime_type="image/png",
    size_bytes=1024,
    object_key="user-1/req-1/file-1/test.png",
):
    return SimpleNamespace(
        id=file_id,
        request_id=request_id,
        original_name=original_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        object_key=object_key,
    )


# ---------------------------------------------------------------------------
# Sample file fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_png():
    """Minimal valid PNG (1x1 transparent pixel)."""
    return (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
def sample_pdf():
    """Minimal valid PDF bytes."""
    return (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    )
