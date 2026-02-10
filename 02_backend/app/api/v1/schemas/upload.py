# UploadConfig (output_format, retention_hours)

from pydantic import BaseModel
from typing import Literal


class UploadConfig(BaseModel):
    output_format: Literal["txt", "json"] = "txt"
    retention_hours: int = 168  # 1 week default
