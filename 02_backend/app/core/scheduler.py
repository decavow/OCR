# APScheduler setup — Background task infrastructure
# Managed by FastAPI lifespan (startup/shutdown)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.logging import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def init_scheduler():
    """Start the scheduler. Called during app startup."""
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    """Graceful shutdown. Called during app shutdown."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
