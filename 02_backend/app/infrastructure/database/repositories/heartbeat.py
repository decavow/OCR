# HeartbeatRepository

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from .base import BaseRepository
from app.infrastructure.database.models import Heartbeat


class HeartbeatRepository(BaseRepository[Heartbeat]):
    """Repository for Heartbeat operations."""

    def __init__(self, db: Session):
        super().__init__(db, Heartbeat)

    def get_latest_by_instance(self, instance_id: str) -> Optional[Heartbeat]:
        """Get latest heartbeat for instance."""
        return self.db.query(Heartbeat).filter(
            Heartbeat.instance_id == instance_id
        ).order_by(Heartbeat.received_at.desc()).first()

    def upsert(
        self,
        instance_id: str,
        status: str,
        current_job_id: str = None,
        files_completed: int = 0,
        files_total: int = 0,
        error_count: int = 0,
    ) -> Heartbeat:
        """Create heartbeat record for instance."""
        heartbeat = Heartbeat(
            instance_id=instance_id,
            status=status,
            current_job_id=current_job_id,
            files_completed=files_completed,
            files_total=files_total,
            error_count=error_count,
            received_at=datetime.now(timezone.utc),
        )
        self.db.add(heartbeat)
        self.db.commit()
        self.db.refresh(heartbeat)
        return heartbeat

    def get_stale_instances(self, timeout_seconds: int = 90, limit: int = 500) -> List[str]:
        """Get instance IDs with stale heartbeats (no heartbeat in timeout period).

        Results are limited to prevent unbounded memory usage with many workers.
        """
        threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)

        # Subquery to get latest heartbeat per instance
        subq = self.db.query(
            Heartbeat.instance_id,
            func.max(Heartbeat.received_at).label("latest")
        ).group_by(Heartbeat.instance_id).subquery()

        # Find instances with latest heartbeat older than threshold
        stale = self.db.query(subq.c.instance_id).filter(
            subq.c.latest < threshold
        ).limit(limit).all()

        return [s[0] for s in stale]

    def get_active_instances(self, timeout_seconds: int = 90) -> List[Heartbeat]:
        """Get latest heartbeats for active instances."""
        threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)

        # Subquery to get latest heartbeat per instance
        subq = self.db.query(
            Heartbeat.instance_id,
            func.max(Heartbeat.id).label("latest_id")
        ).group_by(Heartbeat.instance_id).subquery()

        # Get full heartbeat records that are recent
        return self.db.query(Heartbeat).join(
            subq, Heartbeat.id == subq.c.latest_id
        ).filter(
            Heartbeat.received_at >= threshold
        ).all()

    def cleanup_old(self, keep_hours: int = 24) -> int:
        """Delete old heartbeat records. Returns deleted count."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
        count = self.db.query(Heartbeat).filter(
            Heartbeat.received_at < threshold
        ).delete()
        self.db.commit()
        return count
