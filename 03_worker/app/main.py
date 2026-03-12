# Worker entry point, signal handlers, main loop

import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
import signal
import socket
import sys

from app.config import settings
from app.core.worker import OCRWorker
from app.core.shutdown import GracefulShutdown


def setup_logging():
    """Configure logging with stdout + file output."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(__file__).resolve().parents[2] / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout handler (giữ nguyên)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    # File handler — rotation theo ngày, giữ 30 ngày, tách file per instance
    instance_id = os.getenv("WORKER_SERVICE_ID", "") or f"{os.getenv('WORKER_SERVICE_TYPE', 'ocr-text-tier0')}-{socket.gethostname()[:12]}"
    file_handler = TimedRotatingFileHandler(
        filename=str(log_dir / f"worker-{instance_id}.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=[stdout_handler, file_handler],
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
