# Worker settings (NO MINIO_* vars)

import os
import socket
from typing import Optional, List


def get_worker_instance_id() -> str:
    """Generate unique worker instance ID.

    Uses SERVICE_TYPE + HOSTNAME (set by Docker) for uniqueness.
    Example: ocr-text-tier0-abc123def456
    """
    service_type = os.getenv("WORKER_SERVICE_TYPE", "ocr-text-tier0")
    # Check if explicit instance ID is set
    explicit_id = os.getenv("WORKER_SERVICE_ID", "")
    if explicit_id:
        return explicit_id
    # Auto-generate from service type + hostname
    hostname = socket.gethostname()[:12]  # Docker container ID (first 12 chars)
    return f"{service_type}-{hostname}"


class Settings:
    # Worker identity
    worker_instance_id: str = get_worker_instance_id()
    worker_service_type: str = os.getenv("WORKER_SERVICE_TYPE", "ocr-text-tier0")

    # Access key: empty = wait for approval, set = seed service
    _access_key_env: str = os.getenv("WORKER_ACCESS_KEY", "")
    worker_access_key: Optional[str] = _access_key_env if _access_key_env else None

    # Queue routing
    worker_filter_subject: str = os.getenv("WORKER_FILTER_SUBJECT", "ocr.ocr_paddle_text.tier0")

    # Registration info
    worker_display_name: str = os.getenv("WORKER_DISPLAY_NAME", "OCR Worker")
    worker_description: str = os.getenv("WORKER_DESCRIPTION", "")
    worker_dev_contact: Optional[str] = os.getenv("WORKER_DEV_CONTACT") or None

    # Capabilities
    @property
    def worker_allowed_methods(self) -> List[str]:
        methods_str = os.getenv("WORKER_ALLOWED_METHODS", "ocr_paddle_text")
        return [m.strip() for m in methods_str.split(",") if m.strip()]

    @property
    def worker_allowed_tiers(self) -> List[int]:
        tiers_str = os.getenv("WORKER_ALLOWED_TIERS", "0")
        return [int(t.strip()) for t in tiers_str.split(",") if t.strip()]

    @property
    def worker_supported_formats(self) -> List[str]:
        formats_str = os.getenv("WORKER_SUPPORTED_FORMATS", "txt,json")
        return [f.strip() for f in formats_str.split(",") if f.strip()]

    # Connections (NO MINIO_* variables!)
    nats_url: str = os.getenv("NATS_URL", "nats://nats:4222")
    file_proxy_url: str = os.getenv(
        "FILE_PROXY_URL", "http://backend:8000/api/v1/internal/file-proxy"
    )
    orchestrator_url: str = os.getenv(
        "ORCHESTRATOR_URL", "http://backend:8000/api/v1/internal"
    )

    # Config
    heartbeat_interval_ms: int = int(os.getenv("HEARTBEAT_INTERVAL_MS", "30000"))
    job_timeout_seconds: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))

    # Debug: save intermediate images, raw JSON, bounding box overlays
    debug_ocr: bool = os.getenv("DEBUG_OCR", "false").lower() == "true"

    # Local temp directory
    temp_dir: str = os.getenv("TEMP_DIR", "/tmp/ocr_worker")


settings = Settings()
