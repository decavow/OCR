# Application startup/shutdown lifecycle

from app.core.logging import setup_logging, get_logger
from app.infrastructure.database.connection import engine, SessionLocal
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

    # Database
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
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

    logger.info("Application started successfully")


async def shutdown() -> None:
    """Application shutdown.

    - Close connections gracefully
    """
    global queue_service

    logger.info("Shutting down application...")

    if queue_service:
        await queue_service.disconnect()
        logger.info("NATS disconnected")

    logger.info("Application shutdown complete")


def seed_services(seed_config: str) -> None:
    """Seed service types from config string.

    NOTE: Seed services are a DEV CONVENIENCE for local development.
    In production, workers register dynamically and admin approves.

    Format: type_id:access_key:methods:tiers;...
    Example: ocr-text-tier0:sk_local_text_tier0:text_raw:0;ocr-table-tier0:sk_table:table:0

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
                logger.warning(f"Invalid seed entry (expected type_id:access_key:methods:tiers): {entry}")
                continue

            type_id = parts[0]
            access_key = parts[1]
            methods = parts[2].split(",")
            tiers = [int(t) for t in parts[3].split(",")]

            service_type_repo.create_or_update(
                type_id=type_id,
                display_name=f"Seeded: {type_id}",
                description="Auto-seeded for local development",
                allowed_methods=methods,
                allowed_tiers=tiers,
                status=ServiceTypeStatus.APPROVED,  # Pre-approved
                access_key=access_key,              # Pre-set key
            )
            logger.info(f"Seeded service type: {type_id} (APPROVED)")

    except Exception as e:
        logger.error(f"Error seeding service types: {e}")
    finally:
        db.close()
