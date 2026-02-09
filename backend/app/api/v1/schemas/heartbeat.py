# Heartbeat Schemas

from pydantic import BaseModel
from typing import Optional


class HeartbeatPayload(BaseModel):
    """Heartbeat request from worker."""
    instance_id: str            # Instance ID (unique per container)
    status: str                 # idle, processing, error
    current_job_id: Optional[str] = None
    files_completed: int = 0
    files_total: int = 0
    error_count: int = 0


class HeartbeatResponse(BaseModel):
    """Heartbeat response with action."""
    success: bool
    received_at: str
    action: str                 # continue, approved, drain, shutdown
    access_key: Optional[str] = None        # Only when action=approved
    rejection_reason: Optional[str] = None  # Only when action=shutdown
