# Worker entry point, signal handlers, main loop

import asyncio
import logging
import os
import signal
import sys

from app.config import settings
from app.core.worker import OCRWorker
from app.core.shutdown import GracefulShutdown


def setup_logging():
    """Configure logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("nats").setLevel(logging.WARNING)
    logging.getLogger("paddleocr").setLevel(logging.WARNING)
    logging.getLogger("ppocr").setLevel(logging.WARNING)


async def main():
    """Main entry point."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info(f"OCR Worker Starting")
    logger.info(f"Instance ID: {settings.worker_instance_id}")
    logger.info(f"Service Type: {settings.worker_service_type}")
    logger.info(f"Subject Filter: {settings.worker_filter_subject}")
    logger.info("=" * 60)

    # Setup graceful shutdown
    shutdown_handler = GracefulShutdown()

    # Setup signal handlers (Unix only)
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(shutdown_handler.handle_signal(s))
            )

    # Create and start worker
    worker = OCRWorker(shutdown_handler)

    try:
        await worker.start()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await worker.stop()

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
