# RetryOrchestrator: handle_failure(), decide_retry_or_dlq()

from sqlalchemy.orm import Session

from app.infrastructure.database.models import Job
from app.infrastructure.queue.interface import IQueueService


class RetryOrchestrator:
    def __init__(self, db: Session, queue: IQueueService):
        self.db = db
        self.queue = queue

    async def handle_failure(self, job: Job, error: str, retriable: bool) -> None:
        """Handle job failure - decide retry or DLQ."""
        # TODO: Check retry count
        # TODO: If retriable and under limit, requeue
        # TODO: Otherwise, move to DLQ
        pass

    async def decide_retry_or_dlq(self, job: Job) -> str:
        """Decide whether to retry or send to DLQ."""
        if not job.error_history:
            return "retry"

        # TODO: Check if last error was retriable
        # TODO: Check retry count vs max_retries
        pass

    async def requeue_job(self, job: Job) -> None:
        """Requeue job for retry."""
        # TODO: Increment retry count
        # TODO: Publish to queue
        pass

    async def move_to_dlq(self, job: Job) -> None:
        """Move job to Dead Letter Queue."""
        # TODO: Update status to DEAD_LETTER
        # TODO: Publish to DLQ stream
        pass
