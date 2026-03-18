# Settings from env vars (Pydantic BaseSettings)

import logging
import warnings

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_INSECURE_SECRET_KEYS = {
    "your-secret-key-change-in-production",
    "dev-secret-key-change-in-production",
    "changeme",
    "secret",
    "",
}


class Settings(BaseSettings):
    # Database (relative to project root, not backend/)
    database_url: str = "sqlite:///../data/ocr_platform.db"

    # MinIO (Edge layer storage)
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_uploads: str = "uploads"
    minio_bucket_results: str = "results"
    minio_bucket_deleted: str = "deleted"
    minio_secure: bool = False

    # NATS (Orchestration layer queue)
    nats_url: str = "nats://nats:4222"
    nats_stream_name: str = "OCR_JOBS"
    nats_dlq_stream_name: str = "OCR_DLQ"

    # Service registry
    seed_services: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173"  # comma-separated origins

    # Auth
    secret_key: str = "your-secret-key-change-in-production"
    session_expire_hours: int = 24

    # Job retry
    max_job_retries: int = 3

    # Rate limiting
    rate_limit_enabled: bool = True

    class Config:
        env_file = ".env"

    def validate_secret_key(self) -> None:
        """Validate secret_key strength at startup. Call during lifespan."""
        if self.secret_key in _INSECURE_SECRET_KEYS:
            warnings.warn(
                "SECRET_KEY is using an insecure default value! "
                "Set a strong SECRET_KEY (>= 32 chars) in your .env file.",
                stacklevel=2,
            )
            logger.critical(
                "SECURITY: SECRET_KEY is insecure. "
                "Set SECRET_KEY to a random string >= 32 characters."
            )
        elif len(self.secret_key) < 32:
            warnings.warn(
                f"SECRET_KEY is too short ({len(self.secret_key)} chars). "
                "Use at least 32 characters for production.",
                stacklevel=2,
            )
            logger.warning(
                "SECRET_KEY is shorter than recommended (< 32 chars)."
            )


settings = Settings()
