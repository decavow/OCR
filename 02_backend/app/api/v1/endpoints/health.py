# GET /health (DB + NATS + MinIO readiness)

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    """Check system health: DB, NATS, MinIO."""
    # TODO: Check all connections
    return {
        "status": "healthy",
        "database": "ok",
        "nats": "ok",
        "minio": "ok",
    }
