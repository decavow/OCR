# FileRepository

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import File


class FileRepository(BaseRepository[File]):
    """Repository for File operations."""

    def __init__(self, db: Session):
        super().__init__(db, File)

    def get_active(self, file_id: str) -> Optional[File]:
        """Get active file by ID (not deleted)."""
        return self.db.query(File).filter(
            File.id == file_id,
            File.deleted_at.is_(None)
        ).first()

    def get_by_request(self, request_id: str) -> List[File]:
        """Get all files for a request."""
        return self.db.query(File).filter(
            File.request_id == request_id,
            File.deleted_at.is_(None)
        ).order_by(File.created_at).all()

    def count_by_request(self, request_id: str) -> int:
        """Count files for a request."""
        return self.db.query(File).filter(
            File.request_id == request_id,
            File.deleted_at.is_(None)
        ).count()

    def create_file(
        self,
        request_id: str,
        original_name: str,
        mime_type: str,
        size_bytes: int,
        object_key: str,
        file_id: str = None,
        page_count: int = 1,
    ) -> File:
        """Create new file record."""
        file = File(
            request_id=request_id,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            object_key=object_key,
            page_count=page_count,
        )
        if file_id:
            file.id = file_id
        return self.create(file)

    def soft_delete(self, file: File) -> File:
        """Soft delete file."""
        file.deleted_at = datetime.now(timezone.utc)
        return self.update(file)

    def get_by_request_include_deleted(self, request_id: str) -> List[File]:
        """Get all files for a request, including soft-deleted ones."""
        return self.db.query(File).filter(
            File.request_id == request_id
        ).all()

    def get_total_size_by_request(self, request_id: str) -> int:
        """Get total size of all files in a request."""
        from sqlalchemy import func
        result = self.db.query(func.sum(File.size_bytes)).filter(
            File.request_id == request_id,
            File.deleted_at.is_(None)
        ).scalar()
        return result or 0
