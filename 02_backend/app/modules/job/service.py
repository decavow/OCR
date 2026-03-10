# JobService: centralized job logic — endpoints call this, not repos directly

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Request, Job
from app.infrastructure.database.repositories import (
    JobRepository, RequestRepository, FileRepository,
)
from app.modules.job.state_machine import JobStateMachine
from app.core.logging import get_logger

logger = get_logger(__name__)


class JobService:
    def __init__(self, db: Session, queue=None):
        self.db = db
        self.queue = queue
        self.job_repo = JobRepository(db)
        self.request_repo = RequestRepository(db)
        self.file_repo = FileRepository(db)
        self.state_machine = JobStateMachine()

    async def get_request(self, request_id: str, user_id: str) -> Request | None:
        """Get request, verify ownership."""
        request = self.request_repo.get_active(request_id)
        if request and request.user_id != user_id:
            return None
        return request

    async def get_request_with_jobs(self, request_id: str, user_id: str) -> tuple[Request, list[Job]] | None:
        """Get request with its jobs. Returns None if not found or not owned."""
        request = await self.get_request(request_id, user_id)
        if not request:
            return None
        jobs = self.job_repo.get_by_request(request_id)
        return request, jobs

    async def get_job(self, job_id: str, user_id: str) -> Job | None:
        """Get job, verify ownership via request."""
        job = self.job_repo.get_active(job_id)
        if not job:
            return None
        request = self.request_repo.get_active(job.request_id)
        if not request or request.user_id != user_id:
            return None
        return job

    async def get_job_result(self, job_id: str, user_id: str, storage) -> tuple[Job, bytes] | None:
        """Get job result content. Returns (job, content) or None."""
        job = await self.get_job(job_id, user_id)
        if not job:
            return None
        if job.status != "COMPLETED" or not job.result_path:
            return None
        from app.config import settings
        content = await storage.download(settings.minio_bucket_results, job.result_path)
        return job, content

    async def cancel_request(self, request_id: str, user_id: str) -> dict:
        """Cancel all QUEUED jobs in request."""
        request = await self.get_request(request_id, user_id)
        if not request:
            return {"success": False, "cancelled_jobs": 0, "message": "Request not found"}

        queued_jobs = self.job_repo.get_queued_by_request(request_id)
        cancelled_count = self.job_repo.cancel_jobs(queued_jobs)

        # Recalculate request status after cancellation
        self._recalculate_request_status(request)

        logger.info(
            "Request cancelled: request_id=%s cancelled_jobs=%d",
            request_id, cancelled_count,
        )

        return {
            "success": True,
            "cancelled_jobs": cancelled_count,
            "message": f"Cancelled {cancelled_count} queued jobs",
        }

    async def cancel_job(self, job_id: str, user_id: str) -> dict:
        """Cancel single QUEUED job."""
        job = await self.get_job(job_id, user_id)
        if not job:
            return {"success": False, "job_id": job_id, "cancelled": False, "message": "Job not found"}

        if job.status != "QUEUED":
            return {
                "success": False,
                "job_id": job_id,
                "cancelled": False,
                "message": f"Cannot cancel job with status {job.status}. Only QUEUED jobs can be cancelled.",
            }

        cancelled_count = self.job_repo.cancel_jobs([job])

        # Recalculate request status
        request = self.request_repo.get_active(job.request_id)
        if request:
            self._recalculate_request_status(request)

        return {
            "success": True,
            "job_id": job_id,
            "cancelled": cancelled_count > 0,
            "message": "Job cancelled" if cancelled_count > 0 else "Job was not in QUEUED state",
        }

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        worker_id: str,
        error: str = None,
        retriable: bool = True,
        engine_version: str = None,
    ) -> Job | None:
        """Update job status + trigger request status recalculation.

        Called by internal endpoint (worker callback).
        """
        job = self.job_repo.get_active(job_id)
        if not job:
            return None

        # 1. Validate transition
        if not self.state_machine.validate_transition(job.status, status):
            logger.warning(
                "Invalid transition for job %s: %s -> %s",
                job_id, job.status, status,
                extra={"job_id": job_id},
            )
            return None

        # 2. Update job status via repo
        job = self.job_repo.update_status(
            job=job,
            status=status,
            worker_id=worker_id,
            error=error,
            retriable=retriable,
            engine_version=engine_version,
        )

        # 3. Update request counters
        request = self.request_repo.get_active(job.request_id)
        if request:
            if status == "COMPLETED":
                self.request_repo.increment_completed(request)
            elif status in ("FAILED", "DEAD_LETTER"):
                self.request_repo.increment_failed(request)

            # 4. Recalculate request status
            self._recalculate_request_status(request)

            # 5. If FAILED + retriable → delegate to RetryOrchestrator (M3)
            if status == "FAILED" and retriable:
                await self._handle_retry(job, error, retriable)

        return job

    async def _handle_retry(self, job: Job, error: str, retriable: bool) -> None:
        """Delegate to RetryOrchestrator if available (M3 integration point)."""
        try:
            from app.modules.job.orchestrator import RetryOrchestrator
            orchestrator = RetryOrchestrator(self.db, self.queue)
            await orchestrator.handle_failure(job, error or "", retriable)
        except Exception as e:
            logger.warning(f"RetryOrchestrator not available or failed: {e}")

    def _recalculate_request_status(self, request: Request) -> None:
        """Fetch all jobs for request, compute aggregate status, update request."""
        jobs = self.job_repo.get_by_request(request.id)
        new_status = self.state_machine.get_request_status(jobs)
        if new_status != request.status:
            logger.debug(
                "Request status recalculated: request_id=%s %s -> %s",
                request.id, request.status, new_status,
            )
            self.request_repo.update_status(request, new_status)
