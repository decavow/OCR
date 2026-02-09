# JobStatus enum, JobResponse, JobResultResponse

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum


class JobStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class ErrorEntry(BaseModel):
    error: str
    retriable: bool
    timestamp: datetime


class JobResponse(BaseModel):
    id: str
    request_id: str
    file_id: str
    status: JobStatus
    method: str
    tier: int
    retry_count: int
    max_retries: int
    error_history: List[ErrorEntry] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    result_path: Optional[str] = None
    worker_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobResultMetadata(BaseModel):
    method: str
    tier: str
    processing_time_ms: int
    version: str


class JobResultResponse(BaseModel):
    text: str
    lines: int
    metadata: JobResultMetadata
