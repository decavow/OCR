# WorkerState: tracking current job, progress

from datetime import datetime
from typing import Optional


class WorkerState:
    def __init__(self):
        self.current_job_id: Optional[str] = None
        self.job_started_at: Optional[datetime] = None
        self.files_completed: int = 0
        self.files_total: int = 0
        self.error_count: int = 0
        self.status: str = "idle"

    def start_job(self, job_id: str) -> None:
        """Mark job as started."""
        self.current_job_id = job_id
        self.job_started_at = datetime.utcnow()
        self.status = "processing"

    def end_job(self) -> None:
        """Mark job as ended."""
        self.current_job_id = None
        self.job_started_at = None
        self.files_completed += 1
        self.status = "idle"

    def record_error(self) -> None:
        """Record an error."""
        self.error_count += 1
        self.status = "error"

    def to_heartbeat(self) -> dict:
        """Convert state to heartbeat payload."""
        return {
            "status": self.status,
            "current_job_id": self.current_job_id,
            "files_completed": self.files_completed,
            "files_total": self.files_total,
            "error_count": self.error_count,
        }
