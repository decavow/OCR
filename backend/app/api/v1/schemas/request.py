# RequestResponse (total, completed, failed counts)

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RequestResponse(BaseModel):
    id: str
    user_id: str
    method: str
    tier: int
    output_format: str
    retention_hours: int
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RequestListResponse(BaseModel):
    items: list[RequestResponse]
    total: int
    page: int
    page_size: int
