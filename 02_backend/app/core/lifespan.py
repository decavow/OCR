# Application startup/shutdown lifecycle

from app.core.logging import setup_logging, get_logger
from app.core.scheduler import init_scheduler, shutdown_scheduler
from app.infrastructure.database.connection import engine, SessionLocal, _run_migrations
from app.infrastructure.database.models import Base, ServiceTypeStatus
from app.infrastructure.database.repositories import ServiceTypeRepository
from app.infrastructure.storage.minio_client import MinIOStorageService
from app.infrastructure.queue.nats_client import NATSQueueService
from app.config import settings

logger = get_logger(__name__)

# Global instances
storage_service: MinIOStorageService = None
queue_service: NATSQueueService = None


async def startup() -> None:
    """Application startup.

    - Connect SQLite, enable WAL mode, create tables
    - Connect MinIO, ensure buckets exist
    - Connect NATS, ensure streams exist
    - Seed services from SEED_SERVICES env var
    """
    global storage_service, queue_service

    setup_logging()
    logger.info("Starting application...")

    # Validate security config early
    settings.validate_secret_key()

    # Database
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    _run_migrations()
    logger.info("Database initialized")

    # Storage
    logger.info("Connecting to MinIO...")
    storage_service = MinIOStorageService()
    await storage_service.ensure_buckets()
    logger.info("MinIO connected, buckets ready")

    # Queue
    logger.info("Connecting to NATS...")
    queue_service = NATSQueueService()
    await queue_service.connect()
    await queue_service.ensure_streams()
    logger.info("NATS connected, streams ready")

    # Seed services
    if settings.seed_services:
        seed_services(settings.seed_services)

    # Scheduler + periodic tasks
    init_scheduler()
    _register_periodic_tasks()

    logger.info("Application started successfully")


async def shutdown() -> None:
    """Application shutdown.

    - Close connections gracefully
    """
    global queue_service

    logger.info("Shutting down application...")

    shutdown_scheduler()

    if queue_service:
        await queue_service.disconnect()
        logger.info("NATS disconnected")

    logger.info("Application shutdown complete")


def _register_periodic_tasks() -> None:
    """Register all periodic background tasks in the scheduler."""
    from app.core.scheduler import scheduler

    # Track consecutive failures per task for alerting
    _failure_counts: dict[str, int] = {}
    _ALERT_THRESHOLD = 3

    def _run_with_tracking(task_name: str):
        """Decorator that tracks consecutive failures and logs critical after threshold."""
        def decorator(func):
            async def wrapper():
                db = SessionLocal()
                try:
                    await func(db)
                    _failure_counts[task_name] = 0
                except Exception as e:
                    _failure_counts[task_name] = _failure_counts.get(task_name, 0) + 1
                    count = _failure_counts[task_name]
                    if count >= _ALERT_THRESHOLD:
                        logger.critical(
                            "%s failed %d consecutive times: %s",
                            task_name, count, e,
                        )
                    else:
                        logger.error(f"{task_name} failed (attempt {count}): {e}")
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
            return wrapper
        return decorator

    @_run_with_tracking("heartbeat_check")
    async def heartbeat_check(db):
        from app.modules.job.orchestrator import RetryOrchestrator
        from app.modules.job.heartbeat_monitor import HeartbeatMonitor
        orchestrator = RetryOrchestrator(db, queue_service)
        monitor = HeartbeatMonitor(db, retry_orchestrator=orchestrator)
        await monitor.run_check()

    @_run_with_tracking("retention_cleanup")
    async def retention_cleanup(db):
        from app.modules.cleanup.service import RetentionCleanupService
        svc = RetentionCleanupService(db, storage_service)
        await svc.cleanup_expired()

    @_run_with_tracking("purge_deleted")
    async def purge_deleted(db):
        from app.modules.cleanup.service import RetentionCleanupService
        svc = RetentionCleanupService(db, storage_service)
        await svc.purge_deleted(older_than_hours=168)

    scheduler.add_job(heartbeat_check, 'interval', seconds=60, id='heartbeat_check')
    logger.info("Registered periodic task: heartbeat_check (60s)")
    scheduler.add_job(retention_cleanup, 'interval', hours=1, id='retention_cleanup')
    logger.info("Registered periodic task: retention_cleanup (1h)")
    scheduler.add_job(purge_deleted, 'interval', hours=24, id='purge_deleted')
    logger.info("Registered periodic task: purge_deleted (24h)")


def seed_services(seed_config: str) -> None:
    """Seed service types from config string.

    NOTE: Seed services are a DEV CONVENIENCE for local development.
    In production, workers register dynamically and admin approves.

    Format: type_id:access_key:methods:tiers[:formats[:display_name]];...
    Example: tesseract:sk_local:ocr_tesseract_text:0:txt,json:raw_text_extract(tesseract)
             marker:sk_local:ocr_marker:0:md,html,json:structure_text_extract(marker)

    Seeded types are pre-approved with access_key already set.
    """
    db = SessionLocal()
    try:
        service_type_repo = ServiceTypeRepository(db)

        for entry in seed_config.split(";"):
            entry = entry.strip()
            if not entry:
                continue

            parts = entry.split(":")
            if len(parts) < 4:
                logger.warning(f"Invalid seed entry (expected type_id:access_key:methods:tiers[:formats[:display_name]]): {entry}")
                continue

            type_id = parts[0]
            access_key = parts[1]
            methods = parts[2].split(",")
            tiers = [int(t) for t in parts[3].split(",")]
            formats = parts[4].split(",") if len(parts) > 4 else ["txt", "json"]
            display_name = parts[5] if len(parts) > 5 else type_id

            service_type_repo.create_or_update(
                type_id=type_id,
                display_name=display_name,
                description="Auto-seeded for local development",
                allowed_methods=methods,
                allowed_tiers=tiers,
                supported_output_formats=formats,
                status=ServiceTypeStatus.APPROVED,  # Pre-approved
                access_key=access_key,              # Pre-set key
            )
            logger.info(f"Seeded service type: {type_id} → {display_name} (APPROVED)")

    except Exception as e:
        logger.error(f"Error seeding service types: {e}")
    finally:
        db.close()
