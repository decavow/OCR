# HeartbeatMonitor: detect dead workers, recover stalled jobs

from sqlalchemy.orm import Session

from app.infrastructure.database.models import Job
from app.infrastructure.database.repositories import (
    ServiceInstanceRepository, HeartbeatRepository, JobRepository,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

HEARTBEAT_TIMEOUT_SECONDS = 90     # 3 missed heartbeats (30s interval)
STALLED_JOB_TIMEOUT_SECONDS = 600  # 10 minutes


class HeartbeatMonitor:
    def __init__(self, db: Session, retry_orchestrator=None):
        self.db = db
        self.instance_repo = ServiceInstanceRepository(db)
        self.heartbeat_repo = HeartbeatRepository(db)
        self.job_repo = JobRepository(db)
        self.retry_orchestrator = retry_orchestrator

    async def check_workers(self) -> list[str]:
        """Find dead workers (no heartbeat in timeout period)."""
        stale = self.instance_repo.get_stale_instances(HEARTBEAT_TIMEOUT_SECONDS)
        dead_ids = []
        for instance in stale:
            self.instance_repo.mark_dead(instance)
            dead_ids.append(instance.id)
            logger.info(f"Marked worker {instance.id} as DEAD (heartbeat timeout)")
        return dead_ids

    async def detect_stalled(self) -> list[Job]:
        """Find PROCESSING jobs on dead workers."""
        dead_workers = await self.check_workers()
        stalled_jobs = []
        for worker_id in dead_workers:
            jobs = self.job_repo.get_processing_by_worker(worker_id)
            stalled_jobs.extend(jobs)
        return stalled_jobs

    async def recover_stalled_jobs(self, jobs: list[Job]) -> None:
        """Requeue stalled jobs via RetryOrchestrator."""
        if not self.retry_orchestrator:
            logger.warning("RetryOrchestrator not available, cannot recover stalled jobs")
            return

        for job in jobs:
            try:
                await self.retry_orchestrator.handle_failure(
                    job, error="Worker died (heartbeat timeout)", retriable=True
                )
                logger.info(f"Recovered stalled job {job.id}")
            except Exception as e:
                logger.error(f"Failed to recover job {job.id}: {e}")

    async def run_check(self) -> dict:
        """Full check cycle — called by scheduler."""
        stalled = await self.detect_stalled()
        if stalled:
            await self.recover_stalled_jobs(stalled)
            logger.info(f"Recovered {len(stalled)} stalled jobs")

        # Cleanup old heartbeat records
        cleaned = self.heartbeat_repo.cleanup_old(keep_hours=24)
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old heartbeat records")

        return {"stalled_recovered": len(stalled), "heartbeats_cleaned": cleaned}
