"""
Test cases for M7: HealthService

Covers:
- Healthy response (all services up)
- Degraded (one service down)
- Unhealthy (all services down)
- Individual check methods
"""

import pytest
from unittest.mock import MagicMock, PropertyMock
from types import SimpleNamespace


# Inline import to avoid app import chain
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def health_service_class():
    """Load HealthService with mocked dependencies."""
    logger_mock = MagicMock()
    with patch.dict("sys.modules", {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
    }):
        svc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "health" / "service.py"
        spec = importlib.util.spec_from_file_location("health_service", svc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.HealthService


def make_db_mock(healthy=True):
    """Create mock DB session."""
    db = MagicMock()
    if not healthy:
        db.execute.side_effect = Exception("DB connection failed")
    return db


def make_storage_mock(healthy=True):
    """Create mock MinIO storage."""
    storage = MagicMock()
    if healthy:
        storage.client.list_buckets.return_value = [MagicMock(), MagicMock(), MagicMock()]
    else:
        storage.client.list_buckets.side_effect = Exception("MinIO connection failed")
    return storage


def make_queue_mock(healthy=True):
    """Create mock NATS queue."""
    queue = MagicMock()
    type(queue).is_connected = PropertyMock(return_value=healthy)
    return queue


class TestHealthCheckDatabase:
    @pytest.mark.asyncio
    async def test_db_healthy(self, health_service_class):
        svc = health_service_class(db=make_db_mock(True))
        result = await svc.check_database()
        assert result["status"] == "healthy"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_db_unhealthy(self, health_service_class):
        svc = health_service_class(db=make_db_mock(False))
        result = await svc.check_database()
        assert result["status"] == "unhealthy"
        assert "error" in result


class TestHealthCheckNATS:
    @pytest.mark.asyncio
    async def test_nats_healthy(self, health_service_class):
        svc = health_service_class(db=MagicMock(), queue=make_queue_mock(True))
        result = await svc.check_nats()
        assert result["status"] == "healthy"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_nats_unhealthy(self, health_service_class):
        svc = health_service_class(db=MagicMock(), queue=make_queue_mock(False))
        result = await svc.check_nats()
        assert result["status"] == "unhealthy"
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_nats_not_initialized(self, health_service_class):
        svc = health_service_class(db=MagicMock(), queue=None)
        result = await svc.check_nats()
        assert result["status"] == "unhealthy"


class TestHealthCheckMinIO:
    @pytest.mark.asyncio
    async def test_minio_healthy(self, health_service_class):
        svc = health_service_class(db=MagicMock(), storage=make_storage_mock(True))
        result = await svc.check_minio()
        assert result["status"] == "healthy"
        assert result["buckets"] == 3

    @pytest.mark.asyncio
    async def test_minio_unhealthy(self, health_service_class):
        svc = health_service_class(db=MagicMock(), storage=make_storage_mock(False))
        result = await svc.check_minio()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_minio_not_initialized(self, health_service_class):
        svc = health_service_class(db=MagicMock(), storage=None)
        result = await svc.check_minio()
        assert result["status"] == "unhealthy"


class TestHealthCheckAll:
    @pytest.mark.asyncio
    async def test_all_healthy(self, health_service_class):
        svc = health_service_class(
            db=make_db_mock(True),
            storage=make_storage_mock(True),
            queue=make_queue_mock(True),
        )
        result = await svc.check_all()
        assert result["status"] == "healthy"
        assert "checks" in result
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["nats"]["status"] == "healthy"
        assert result["checks"]["minio"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_db_down(self, health_service_class):
        svc = health_service_class(
            db=make_db_mock(False),
            storage=make_storage_mock(True),
            queue=make_queue_mock(True),
        )
        result = await svc.check_all()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_nats_down(self, health_service_class):
        svc = health_service_class(
            db=make_db_mock(True),
            storage=make_storage_mock(True),
            queue=make_queue_mock(False),
        )
        result = await svc.check_all()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_all_unhealthy(self, health_service_class):
        svc = health_service_class(
            db=make_db_mock(False),
            storage=make_storage_mock(False),
            queue=make_queue_mock(False),
        )
        result = await svc.check_all()
        assert result["status"] == "unhealthy"
