# UploadConfig (output_format, retention_hours)

from pydantic import BaseModel


class UploadConfig(BaseModel):
    output_format: str = "txt"  # Validated dynamically via services
    retention_hours: int = 168  # 1 week default
