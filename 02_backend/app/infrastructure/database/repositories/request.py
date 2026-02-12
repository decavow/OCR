# RequestRepository

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import Request


class RequestRepository(BaseRepository[Request]):
    """Repository for Request (Batch) operations."""

    def __init__(self, db: Session):
        super().__init__(db, Request)

    def get_active(self, request_id: str) -> Optional[Request]:
        """Get active request by ID (not deleted)."""
        return self.db.query(Request).filter(
            Request.id == request_id,
            Request.deleted_at.is_(None)
        ).first()

    def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Request]:
        """Get requests for user with pagination."""
        return self.db.query(Request).filter(
            Request.user_id == user_id,
            Request.deleted_at.is_(None)
        ).order_by(Request.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_user(self, user_id: str) -> int:
        """Count requests for user."""
        return self.db.query(Request).filter(
            Request.user_id == user_id,
            Request.deleted_at.is_(None)
        ).count()

    def get_by_status(self, status: str, limit: int = 100) -> List[Request]:
        """Get requests by status."""
        return self.db.query(Request).filter(
            Request.status == status,
            Request.deleted_at.is_(None)
        ).limit(limit).all()

    def create_request(
        self,
        user_id: str,
        file_count: int,
        method: str = "text_raw",
        tier: int = 0,
        output_format: str = "txt",
        retention_hours: int = 168,
        expires_at: datetime = None,
    ) -> Request:
        """Create new request."""
        request = Request(
            user_id=user_id,
            method=method,
            tier=tier,
            output_format=output_format,
            retention_hours=retention_hours,
            status="PROCESSING",
            total_files=file_count,
            expires_at=expires_at,
        )
        return self.create(request)

    def update_status(self, request: Request, status: str) -> Request:
        """Update request status."""
        request.status = status
        if status in ("COMPLETED", "PARTIAL_SUCCESS", "FAILED", "CANCELLED"):
            request.completed_at = datetime.now(timezone.utc)
        return self.update(request)

    def increment_completed(self, request: Request) -> Request:
        """Increment completed files count."""
        request.completed_files += 1
        return self.update(request)

    def increment_failed(self, request: Request) -> Request:
        """Increment failed files count."""
        request.failed_files += 1
        return self.update(request)

    def soft_delete(self, request: Request) -> Request:
        """Soft delete request."""
        request.deleted_at = datetime.now(timezone.utc)
        return self.update(request)

    def count_all_active(self) -> int:
        """Count all active requests (all users)."""
        return self.db.query(Request).filter(
            Request.deleted_at.is_(None)
        ).count()

    def get_all_recent(self, skip: int = 0, limit: int = 20) -> List[Request]:
        """Get recent requests from all users."""
        return self.db.query(Request).filter(
            Request.deleted_at.is_(None)
        ).order_by(Request.created_at.desc()).offset(skip).limit(limit).all()
