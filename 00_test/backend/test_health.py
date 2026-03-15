"""Unit tests for HealthService edge cases (02_backend/app/modules/health/service.py).

Complementary to test_health_service.py — tests specific infrastructure
failure combinations and edge-case scenarios.

Test IDs: HE-001 to HE-003
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
    spec = importlib.util.spec_from_file_location("health_service_he", mod_path)
    mod = importlib.util.module_from_spec(spec)

    sa_mock = MagicMock()
    sa_mock.text = lambda s: s

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


# ===================================================================
# check_all edge cases  (HE-001 to HE-003)
# ===================================================================

class TestHealthEdgeCases:
    """HE-001 to HE-003: HealthService edge-case scenarios."""

    @pytest.mark.asyncio
    async def test_he001_db_only_healthy_others_none(self):
        """HE-001: DB healthy, storage=None, queue=None -> degraded."""
        db = MagicMock()
        svc = HealthService(db, storage=None, queue=None)

        result = await svc.check_all()

        assert result["status"] == "degraded"
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["nats"]["status"] == "unhealthy"
        assert result["checks"]["minio"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_he002_nats_connected_but_minio_exception(self):
        """HE-002: DB healthy, NATS connected, MinIO throws -> degraded."""
        db = MagicMock()
        storage = MagicMock()
        storage.client.list_buckets.side_effect = ConnectionError("MinIO timeout")
        queue = MagicMock()
        queue.is_connected = True

        svc = HealthService(db, storage=storage, queue=queue)
        result = await svc.check_all()

        assert result["status"] == "degraded"
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["nats"]["status"] == "healthy"
        assert result["checks"]["minio"]["status"] == "unhealthy"
        assert "MinIO timeout" in result["checks"]["minio"]["error"]

    @pytest.mark.asyncio
    async def test_he003_db_exception_nats_disconnected_minio_ok(self):
        """HE-003: DB throws, NATS disconnected, MinIO ok -> degraded (not unhealthy,
        because MinIO is still healthy)."""
        db = MagicMock()
        db.execute.side_effect = Exception("DB locked")
        storage = MagicMock()
        storage.client.list_buckets.return_value = ["uploads"]
        queue = MagicMock()
        queue.is_connected = False

        svc = HealthService(db, storage=storage, queue=queue)
        result = await svc.check_all()

        assert result["status"] == "degraded"
        assert result["checks"]["database"]["status"] == "unhealthy"
        assert result["checks"]["nats"]["status"] == "unhealthy"
        assert result["checks"]["minio"]["status"] == "healthy"
