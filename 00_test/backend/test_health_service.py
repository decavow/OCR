"""Unit tests for HealthService (02_backend/app/modules/health/service.py).

Service-layer tests with mocked database, storage, and queue.

Test IDs: HS-001 to HS-009
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_health_service():
    mod_path = BACKEND_ROOT / "app" / "modules" / "health" / "service.py"
    spec = importlib.util.spec_from_file_location("health_service", mod_path)
    mod = importlib.util.module_from_spec(spec)

    # HealthService imports sqlalchemy.text and sqlalchemy.orm.Session
    # We need a real-ish `text` function that returns what we give it,
    # so the db.execute(text("SELECT 1")) pattern works with our mock.
    sa_mock = MagicMock()
    sa_mock.text = lambda s: s  # pass-through

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "sqlalchemy": sa_mock,
        "sqlalchemy.orm": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


hs_mod = _load_health_service()
HealthService = hs_mod.HealthService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def healthy_svc():
    """HealthService with all dependencies healthy."""
    db = MagicMock()
    storage = MagicMock()
    storage.client.list_buckets.return_value = ["uploads", "results", "deleted"]
    queue = MagicMock()
    queue.is_connected = True
    return HealthService(db, storage=storage, queue=queue)


@pytest.fixture
def unhealthy_svc():
    """HealthService with failing dependencies."""
    db = MagicMock()
    db.execute.side_effect = Exception("DB connection refused")
    storage = MagicMock()
    storage.client.list_buckets.side_effect = Exception("MinIO unreachable")
    queue = MagicMock()
    queue.is_connected = False
    return HealthService(db, storage=storage, queue=queue)


# ===================================================================
# check_database  (HS-001 to HS-002)
# ===================================================================

class TestCheckDatabase:
    """HS-001 to HS-002: Database health check."""

    @pytest.mark.asyncio
    async def test_hs001_healthy_database(self, healthy_svc):
        """HS-001: Returns healthy status when DB responds to SELECT 1."""
        result = await healthy_svc.check_database()
        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert 0 <= result["latency_ms"] < 5000  # Should complete within 5s

    @pytest.mark.asyncio
    async def test_hs002_unhealthy_database(self, unhealthy_svc):
        """HS-002: Returns unhealthy status when DB throws exception."""
        result = await unhealthy_svc.check_database()
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert "latency_ms" in result


# ===================================================================
# check_nats  (HS-003 to HS-004)
# ===================================================================

class TestCheckNats:
    """HS-003 to HS-004: NATS health check."""

    @pytest.mark.asyncio
    async def test_hs003_healthy_nats(self, healthy_svc):
        """HS-003: Returns healthy when NATS is connected."""
        result = await healthy_svc.check_nats()
        assert result["status"] == "healthy"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_hs004_unhealthy_nats_disconnected(self, unhealthy_svc):
        """HS-004: Returns unhealthy when NATS is not connected."""
        result = await unhealthy_svc.check_nats()
        assert result["status"] == "unhealthy"
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_hs004b_unhealthy_nats_none(self):
        """HS-004b: Returns unhealthy when NATS service is None."""
        svc = HealthService(MagicMock(), storage=MagicMock(), queue=None)
        result = await svc.check_nats()
        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert "not initialized" in result["error"]


# ===================================================================
# check_minio  (HS-005 to HS-006)
# ===================================================================

class TestCheckMinio:
    """HS-005 to HS-006: MinIO health check."""

    @pytest.mark.asyncio
    async def test_hs005_healthy_minio(self, healthy_svc):
        """HS-005: Returns healthy when MinIO lists buckets."""
        result = await healthy_svc.check_minio()
        assert result["status"] == "healthy"
        assert result["buckets"] == 3

    @pytest.mark.asyncio
    async def test_hs006_unhealthy_minio(self, unhealthy_svc):
        """HS-006: Returns unhealthy when MinIO throws exception."""
        result = await unhealthy_svc.check_minio()
        assert result["status"] == "unhealthy"
        assert result["buckets"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_hs006b_unhealthy_minio_none(self):
        """HS-006b: Returns unhealthy when storage is None."""
        svc = HealthService(MagicMock(), storage=None, queue=MagicMock())
        result = await svc.check_minio()
        assert result["status"] == "unhealthy"
        assert result["buckets"] == 0
        assert "not initialized" in result["error"]


# ===================================================================
# check_all  (HS-007 to HS-009)
# ===================================================================

class TestCheckAll:
    """HS-007 to HS-009: Aggregate health check."""

    @pytest.mark.asyncio
    async def test_hs007_all_healthy(self, healthy_svc):
        """HS-007: Returns 'healthy' when all checks pass."""
        result = await healthy_svc.check_all()
        assert result["status"] == "healthy"
        assert "checks" in result
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["nats"]["status"] == "healthy"
        assert result["checks"]["minio"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_hs008_all_unhealthy(self, unhealthy_svc):
        """HS-008: Returns 'unhealthy' when all checks fail."""
        result = await unhealthy_svc.check_all()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_hs009_degraded_when_partial(self):
        """HS-009: Returns 'degraded' when some checks pass and some fail."""
        db = MagicMock()  # healthy
        storage = MagicMock()
        storage.client.list_buckets.side_effect = Exception("MinIO down")
        queue = MagicMock()
        queue.is_connected = True

        svc = HealthService(db, storage=storage, queue=queue)
        result = await svc.check_all()
        assert result["status"] == "degraded"
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["nats"]["status"] == "healthy"
        assert result["checks"]["minio"]["status"] == "unhealthy"
