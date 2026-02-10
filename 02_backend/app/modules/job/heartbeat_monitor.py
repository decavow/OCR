# HeartbeatMonitor: check_workers(), detect_stalled()

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Heartbeat, Job

HEARTBEAT_TIMEOUT_SECONDS = 90  # 3 missed heartbeats (30s interval)
STALLED_JOB_TIMEOUT_SECONDS = 600  # 10 minutes


class HeartbeatMonitor:
    def __init__(self, db: Session):
        self.db = db

    async def check_workers(self) -> list[str]:
        """Check for dead workers (no heartbeat in timeout period)."""
        # TODO: Find workers with old heartbeats
        pass

    async def detect_stalled(self) -> list[Job]:
        """Detect stalled jobs (PROCESSING but worker dead)."""
        # TODO: Find PROCESSING jobs with dead workers
        pass

    async def recover_stalled_jobs(self, jobs: list[Job]) -> None:
        """Requeue stalled jobs."""
        # TODO: Update status, requeue
        pass

    async def record_heartbeat(
        self,
        service_id: str,
        status: str,
        current_job_id: str = None,
        files_completed: int = 0,
        files_total: int = 0,
        error_count: int = 0,
    ) -> Heartbeat:
        """Record heartbeat from worker."""
        # TODO: Upsert heartbeat record
        pass
