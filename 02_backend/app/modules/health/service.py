# HealthService: check DB, NATS, MinIO connections

import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.logging import get_logger

logger = get_logger(__name__)


class HealthService:
    """Aggregate health check for all infrastructure services."""

    def __init__(self, db: Session, storage=None, queue=None):
        self.db = db
        self.storage = storage
        self.queue = queue

    async def check_database(self) -> dict:
        """Execute SELECT 1 on SQLite."""
        start = time.monotonic()
        try:
            self.db.execute(text("SELECT 1"))
            latency = (time.monotonic() - start) * 1000
            return {"status": "healthy", "latency_ms": round(latency, 2)}
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "latency_ms": round(latency, 2), "error": str(e)}

    async def check_nats(self) -> dict:
        """Check NATS connection status."""
        start = time.monotonic()
        try:
            if self.queue is None:
                return {"status": "unhealthy", "connected": False, "error": "NATS service not initialized"}
            connected = self.queue.is_connected
            latency = (time.monotonic() - start) * 1000
            return {
                "status": "healthy" if connected else "unhealthy",
                "connected": connected,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"NATS health check failed: {e}")
            return {"status": "unhealthy", "connected": False, "latency_ms": round(latency, 2), "error": str(e)}

    async def check_minio(self) -> dict:
        """List buckets to verify MinIO."""
        start = time.monotonic()
        try:
            if self.storage is None:
                return {"status": "unhealthy", "buckets": 0, "error": "MinIO service not initialized"}
            buckets = self.storage.client.list_buckets()
            latency = (time.monotonic() - start) * 1000
            return {
                "status": "healthy",
                "buckets": len(buckets),
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"MinIO health check failed: {e}")
            return {"status": "unhealthy", "buckets": 0, "latency_ms": round(latency, 2), "error": str(e)}

    async def check_all(self) -> dict:
        """Run all checks, return aggregate status."""
        db_check = await self.check_database()
        nats_check = await self.check_nats()
        minio_check = await self.check_minio()

        checks = {
            "database": db_check,
            "nats": nats_check,
            "minio": minio_check,
        }

        statuses = [c["status"] for c in checks.values()]

        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif all(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        return {"status": overall, "checks": checks}
