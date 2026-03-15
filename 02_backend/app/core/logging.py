# Structured JSON logger setup

import logging
import json
import sys
import contextvars
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Context variables for global tracing
request_id_ctx = contextvars.ContextVar("request_id", default=None)
job_id_ctx = contextvars.ContextVar("job_id", default=None)

# Whitelisted extra fields that will be included in JSON output
EXTRA_FIELDS = (
    "request_id", "user_id", "job_id", "instance_id",
    "service_type", "action", "actor_email", "entity_type",
    "entity_id", "method", "status_code",
)


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Retrieve global contextvars first
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id
            
        jb_id = job_id_ctx.get()
        if jb_id:
            log_data["job_id"] = jb_id

        # Add whitelisted extra fields set on the LogRecord (can override contextvars)
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_data[field] = value

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """Setup structured logging with stdout + file output."""
    log_dir = Path(__file__).resolve().parents[3] / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = JSONFormatter()

    # Stdout handler (giữ nguyên)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    # File handler — rotation theo ngày, giữ 30 ngày
    file_handler = TimedRotatingFileHandler(
        filename=str(log_dir / "backend.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get logger by name."""
    return logging.getLogger(name)
