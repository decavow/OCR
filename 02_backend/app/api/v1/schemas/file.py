# FileResponse, PresignedUrlResponse

from pydantic import BaseModel
from datetime import datetime


class FileResponse(BaseModel):
    id: str
    request_id: str
    original_name: str
    mime_type: str
    size_bytes: int
    page_count: int
    object_key: str
    created_at: datetime

    class Config:
        from_attributes = True


class PresignedUrlResponse(BaseModel):
    url: str
    expires_at: datetime
