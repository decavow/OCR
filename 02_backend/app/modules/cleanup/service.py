# RetentionCleanupService: cleanup expired files and purge deleted

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.infrastructure.database.repositories import RequestRepository, FileRepository, JobRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetentionCleanupService:
    def __init__(self, db: Session, storage=None):
        self.db = db
        self.storage = storage
        self.request_repo = RequestRepository(db)
        self.file_repo = FileRepository(db)
        self.job_repo = JobRepository(db)

    async def cleanup_expired(self) -> dict:
        """Find and soft-delete expired requests + move files to deleted bucket."""
        expired = self.request_repo.get_expired(limit=100)
        if not expired:
            return {"expired_requests": 0, "files_moved": 0}

        files_moved = 0
        for request in expired:
            files = self.file_repo.get_by_request(request.id)
            jobs = self.job_repo.get_by_request(request.id)

            # Move files to deleted bucket
            for file in files:
                if self.storage:
                    try:
                        await self._move_to_deleted(file.object_key, "uploads")
                    except Exception as e:
                        logger.error(f"Failed to move file {file.object_key}: {e}")
                        continue
                self.file_repo.soft_delete(file)
                files_moved += 1

            # Move result files
            for job in jobs:
                if job.result_path and self.storage:
                    try:
                        await self._move_to_deleted(job.result_path, "results")
                    except Exception as e:
                        logger.error(f"Failed to move result {job.result_path}: {e}")

            # Soft-delete request
            self.request_repo.soft_delete(request)

        logger.info(f"Cleanup: {len(expired)} expired requests, {files_moved} files moved")
        return {"expired_requests": len(expired), "files_moved": files_moved}

    async def purge_deleted(self, older_than_hours: int = 168) -> dict:
        """Permanently delete files from deleted bucket older than threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        purged = self.request_repo.get_soft_deleted_before(cutoff, limit=100)

        if not purged:
            return {"purged_requests": 0, "files_removed": 0}

        files_removed = 0
        for request in purged:
            files = self.file_repo.get_by_request_include_deleted(request.id)

            for file in files:
                if self.storage:
                    try:
                        deleted_key = f"deleted/{file.object_key}"
                        self.storage.client.remove_object(
                            self.storage.deleted_bucket, file.object_key
                        )
                        files_removed += 1
                    except Exception as e:
                        logger.warning(f"Failed to purge {file.object_key}: {e}")

            # Hard delete from DB
            self.request_repo.hard_delete(request)

        logger.info(f"Purge: {len(purged)} requests, {files_removed} files removed")
        return {"purged_requests": len(purged), "files_removed": files_removed}

    async def _move_to_deleted(self, object_key: str, source_bucket: str) -> None:
        """Move object from source bucket to deleted bucket."""
        from minio.commonconfig import CopySource
        src_bucket = getattr(self.storage, f"{source_bucket}_bucket", source_bucket)
        dst_bucket = self.storage.deleted_bucket

        self.storage.client.copy_object(
            dst_bucket,
            object_key,
            CopySource(src_bucket, object_key),
        )
        self.storage.client.remove_object(src_bucket, object_key)
