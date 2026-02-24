# Settings from env vars (Pydantic BaseSettings)

from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"


settings = Settings()
