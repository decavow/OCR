# JobRepository

import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import Job


class JobRepository(BaseRepository[Job]):
    """Repository for Job operations."""

    def __init__(self, db: Session):
        super().__init__(db, Job)

    def get_active(self, job_id: str) -> Optional[Job]:
        """Get active job by ID (not deleted)."""
        return self.db.query(Job).filter(
            Job.id == job_id,
            Job.deleted_at.is_(None)
        ).first()

    def get_by_request(self, request_id: str) -> List[Job]:
        """Get all jobs for a request."""
        return self.db.query(Job).filter(
            Job.request_id == request_id,
            Job.deleted_at.is_(None)
        ).all()

    def get_by_file(self, file_id: str) -> Optional[Job]:
        """Get job by file ID."""
        return self.db.query(Job).filter(
            Job.file_id == file_id,
            Job.deleted_at.is_(None)
        ).first()

    def get_by_status(self, status: str, limit: int = 100) -> List[Job]:
        """Get jobs by status."""
        return self.db.query(Job).filter(
            Job.status == status,
            Job.deleted_at.is_(None)
        ).limit(limit).all()

    def get_queued_by_request(self, request_id: str) -> List[Job]:
        """Get queued jobs for a request (for cancellation)."""
        return self.db.query(Job).filter(
            Job.request_id == request_id,
            Job.status == "QUEUED",
            Job.deleted_at.is_(None)
        ).all()

    def get_processing_by_worker(self, worker_id: str) -> List[Job]:
        """Get processing jobs for a worker."""
        return self.db.query(Job).filter(
            Job.worker_id == worker_id,
            Job.status == "PROCESSING",
            Job.deleted_at.is_(None)
        ).all()

    def create_job(
        self,
        request_id: str,
        file_id: str,
        method: str,
        tier: int,
        job_id: str = None,
    ) -> Job:
        """Create new job."""
        job = Job(
            request_id=request_id,
            file_id=file_id,
            method=method,
            tier=tier,
            status="SUBMITTED",
        )
        if job_id:
            job.id = job_id
        return self.create(job)

    def update_status(
        self,
        job: Job,
        status: str,
        worker_id: str = None,
        error: str = None,
        retriable: bool = True,
    ) -> Job:
        """Update job status."""
        job.status = status

        if worker_id:
            job.worker_id = worker_id

        if status == "PROCESSING":
            job.started_at = datetime.now(timezone.utc)

        if status in ("COMPLETED", "PARTIAL_SUCCESS", "FAILED", "DEAD_LETTER"):
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                # Handle timezone-naive datetime from DB
                started = job.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                delta = job.completed_at - started
                job.processing_time_ms = int(delta.total_seconds() * 1000)

        if error:
            self._add_error(job, error, retriable)

        return self.update(job)

    def _add_error(self, job: Job, error: str, retriable: bool) -> None:
        """Add error to job's error history."""
        history = json.loads(job.error_history or "[]")
        history.append({
            "error": error,
            "retriable": retriable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        job.error_history = json.dumps(history)

    def increment_retry(self, job: Job) -> Job:
        """Increment retry count."""
        job.retry_count += 1
        return self.update(job)

    def set_result_path(self, job: Job, result_path: str) -> Job:
        """Set result path for completed job."""
        job.result_path = result_path
        return self.update(job)

    def count_all_active(self) -> int:
        """Count all active jobs."""
        return self.db.query(Job).filter(
            Job.deleted_at.is_(None)
        ).count()

    def count_all_by_status(self, status: str) -> int:
        """Count all jobs with given status."""
        return self.db.query(Job).filter(
            Job.status == status,
            Job.deleted_at.is_(None)
        ).count()

    def avg_processing_time(self) -> float | None:
        """Average processing time in ms for completed jobs."""
        from sqlalchemy import func
        result = self.db.query(func.avg(Job.processing_time_ms)).filter(
            Job.status == "COMPLETED",
            Job.processing_time_ms.isnot(None),
            Job.deleted_at.is_(None)
        ).scalar()
        return float(result) if result else None

    def get_hourly_volume(self, hours: int = 24) -> list[dict]:
        """Get job volume grouped by hour for the last N hours."""
        from sqlalchemy import func
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        rows = self.db.query(
            func.strftime('%H', Job.created_at).label('hour'),
            func.count(Job.id).label('volume'),
            func.avg(Job.processing_time_ms).label('avg_latency'),
        ).filter(
            Job.created_at >= cutoff,
            Job.deleted_at.is_(None)
        ).group_by(
            func.strftime('%H', Job.created_at)
        ).order_by('hour').all()

        return [
            {
                "hour": f"{row.hour}:00",
                "volume": row.volume,
                "avg_latency_ms": round(float(row.avg_latency or 0), 1),
            }
            for row in rows
        ]

    def cancel_jobs(self, jobs: List[Job]) -> int:
        """Cancel multiple jobs. Returns cancelled count."""
        count = 0
        for job in jobs:
            if job.status == "QUEUED":
                job.status = "CANCELLED"
                count += 1
        self.db.commit()
        return count
