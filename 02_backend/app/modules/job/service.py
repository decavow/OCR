# JobService: create_request, get_status, cancel

from sqlalchemy.orm import Session

from app.infrastructure.database.models import Request, Job


class JobService:
    def __init__(self, db: Session):
        self.db = db

    async def create_request(
        self,
        user_id: str,
        method: str,
        tier: int,
        output_format: str,
        retention_hours: int,
        total_files: int,
    ) -> Request:
        """Create a new OCR request."""
        # TODO: Create Request record
        pass

    async def get_request(self, request_id: str, user_id: str) -> Request | None:
        """Get request by ID for user."""
        # TODO: Fetch request, verify ownership
        pass

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        # TODO: Fetch job
        pass

    async def cancel_request(self, request_id: str, user_id: str) -> Request:
        """Cancel request (only QUEUED jobs)."""
        # TODO: Find request, cancel QUEUED jobs
        pass

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error: str = None,
        retriable: bool = True,
    ) -> Job:
        """Update job status."""
        # TODO: Update job, trigger orchestrator if needed
        pass
