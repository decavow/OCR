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

    def _build_user_query(
        self,
        user_id: str,
        status: Optional[str] = None,
        method: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        """Build filtered query for user requests."""
        query = self.db.query(Request).filter(
            Request.user_id == user_id,
            Request.deleted_at.is_(None)
        )
        if status:
            query = query.filter(Request.status == status)
        if method:
            query = query.filter(Request.method == method)
        if date_from:
            query = query.filter(Request.created_at >= date_from)
        if date_to:
            query = query.filter(Request.created_at <= date_to)
        return query

    def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        method: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Request]:
        """Get requests for user with pagination and filters."""
        return self._build_user_query(
            user_id, status=status, method=method, date_from=date_from, date_to=date_to
        ).order_by(Request.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_user(
        self,
        user_id: str,
        status: Optional[str] = None,
        method: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> int:
        """Count requests for user with filters."""
        return self._build_user_query(
            user_id, status=status, method=method, date_from=date_from, date_to=date_to
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
        method: str = "ocr_text_raw",
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

    def get_expired(self, limit: int = 100) -> List[Request]:
        """Get expired requests (expires_at < now, not deleted)."""
        return self.db.query(Request).filter(
            Request.expires_at < datetime.now(timezone.utc),
            Request.deleted_at.is_(None)
        ).limit(limit).all()

    def get_soft_deleted_before(self, cutoff: datetime, limit: int = 100) -> List[Request]:
        """Get soft-deleted requests older than cutoff (for purge)."""
        return self.db.query(Request).filter(
            Request.deleted_at.isnot(None),
            Request.deleted_at < cutoff,
        ).limit(limit).all()

    def hard_delete(self, request: Request) -> None:
        """Permanently delete request from DB (cascade deletes files/jobs)."""
        self.db.delete(request)
        self.db.commit()
