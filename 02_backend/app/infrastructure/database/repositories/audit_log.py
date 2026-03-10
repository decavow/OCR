# AuditLogRepository

import json
from typing import Optional, List
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import AuditLog


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for audit log entries."""

    def __init__(self, db: Session):
        super().__init__(db, AuditLog)

    def record(
        self,
        actor_email: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: Optional[dict] = None,
        request_id: Optional[str] = None,
    ) -> AuditLog:
        """Record an audit log entry."""
        entry = AuditLog(
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details else None,
            request_id=request_id,
        )
        return self.create(entry)

    def query_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Query audit logs by entity."""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def query_recent(self, limit: int = 50) -> List[AuditLog]:
        """Query most recent audit log entries."""
        return (
            self.db.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )
