# UploadConfig (output_format, retention_hours)

from pydantic import BaseModel, field_validator

VALID_RETENTION_HOURS = [1, 6, 12, 24, 168, 720]


class UploadConfig(BaseModel):
    output_format: str = "txt"  # Validated dynamically via services
    retention_hours: int = 24  # 24h default

    @field_validator("retention_hours")
    @classmethod
    def validate_retention(cls, v: int) -> int:
        if v not in VALID_RETENTION_HOURS:
            raise ValueError(f"retention_hours must be one of {VALID_RETENTION_HOURS}")
        return v
