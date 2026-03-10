# RetryOrchestrator: handle_failure(), requeue, DLQ

import json
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Job
from app.infrastructure.database.repositories import JobRepository, FileRepository
from app.infrastructure.queue.messages import JobMessage
from app.infrastructure.queue.subjects import get_subject, get_dlq_subject
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetryOrchestrator:
    MAX_RETRIES = 3

    def __init__(self, db: Session, queue=None):
        self.db = db
        self.queue = queue
        self.job_repo = JobRepository(db)
        self.file_repo = FileRepository(db)

    async def handle_failure(self, job: Job, error: str, retriable: bool) -> None:
        """Handle job failure. Called by JobService.update_job_status()."""
        action = self.decide_retry_or_dlq(job, retriable)
        logger.info(
            "Handling failure for job %s: action=%s retry_count=%d retriable=%s",
            job.id, action, job.retry_count, retriable,
            extra={"job_id": job.id},
        )
        if action == "retry":
            await self.requeue_job(job)
        else:
            await self.move_to_dlq(job)

    def decide_retry_or_dlq(self, job: Job, retriable: bool = True) -> str:
        """Decide action based on error history and retry count."""
        max_retries = getattr(settings, "max_job_retries", self.MAX_RETRIES)

        if job.retry_count >= max_retries:
            return "dlq"

        if not retriable:
            return "dlq"

        # Check last error in history
        try:
            history = json.loads(job.error_history or "[]")
            if history and not history[-1].get("retriable", True):
                return "dlq"
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("Failed to parse error_history for job %s: %s", job.id, e)

        return "retry"

    async def requeue_job(self, job: Job) -> None:
        """Requeue job for retry."""
        # 1. Increment retry count
        self.job_repo.increment_retry(job)

        # 2. Reset status to QUEUED
        self.job_repo.update_status(job, status="QUEUED")

        # 3. Publish to NATS
        if self.queue:
            message = self._build_message(job)
            subject = get_subject(job.method, job.tier)
            await self.queue.publish(subject, message)
            logger.info(
                "Requeued job %s (retry %d)", job.id, job.retry_count,
                extra={"job_id": job.id},
            )
        else:
            logger.warning(
                "Queue not available, job %s set to QUEUED but not published", job.id,
                extra={"job_id": job.id},
            )

    async def move_to_dlq(self, job: Job) -> None:
        """Move job to Dead Letter Queue."""
        # 1. Update status to DEAD_LETTER
        self.job_repo.update_status(job, status="DEAD_LETTER")

        # 2. Publish to DLQ stream
        if self.queue:
            message = self._build_message(job)
            dlq_subject = get_dlq_subject(job.method, job.tier)
            await self.queue.publish(dlq_subject, message)
            logger.warning(
                "Exhausted retries, moved job %s to DLQ (retries: %d)",
                job.id, job.retry_count,
                extra={"job_id": job.id},
            )
        else:
            logger.warning(
                "Queue not available, job %s marked DEAD_LETTER but not published to DLQ",
                job.id,
                extra={"job_id": job.id},
            )

    def _build_message(self, job: Job) -> JobMessage:
        """Build JobMessage from Job model."""
        file = self.file_repo.get_active(job.file_id) if job.file_id else None
        object_key = file.object_key if file else ""

        # Get output_format from request relationship if available
        output_format = "txt"
        if hasattr(job, "request") and job.request:
            output_format = job.request.output_format or "txt"

        return JobMessage(
            job_id=job.id,
            file_id=job.file_id or "",
            request_id=job.request_id,
            method=job.method,
            tier=job.tier,
            output_format=output_format,
            object_key=object_key,
            retry_count=job.retry_count,
        )
