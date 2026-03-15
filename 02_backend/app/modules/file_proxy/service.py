# FileProxyService: download_for_worker(), upload_from_worker()

import logging
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Job, File
from app.infrastructure.database.repositories import JobRepository
from app.infrastructure.storage import MinIOStorageService, generate_result_key
from app.config import settings
from .access_control import verify_access_key, check_job_file_acl

logger = logging.getLogger(__name__)


class FileProxyService:
    def __init__(self, db: Session, storage: MinIOStorageService):
        self.db = db
        self.storage = storage
        self.job_repo = JobRepository(db)

    async def download_for_worker(
        self,
        access_key: str,
        job_id: str,
        file_id: str,
    ) -> tuple[bytes, str, str]:
        """Download file for worker processing.

        Returns: (content, content_type, filename)
        """
        # Verify access key (returns ServiceType)
        service_type = verify_access_key(self.db, access_key)

        # Verify job-file relationship and access
        job, file = check_job_file_acl(self.db, job_id, file_id, service_type)

        # Download from MinIO
        content = await self.storage.download(
            bucket=settings.minio_bucket_uploads,
            object_key=file.object_key,
        )

        logger.debug(
            "Downloaded file %s for job %s", file_id, job_id,
            extra={"job_id": job_id},
        )
        return content, file.mime_type, file.original_name

    async def upload_from_worker(
        self,
        access_key: str,
        job_id: str,
        file_id: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Upload result from worker.

        Returns: result object key
        """
        # Verify access key (returns ServiceType)
        service_type = verify_access_key(self.db, access_key)

        # Verify job-file relationship and access
        job, file = check_job_file_acl(self.db, job_id, file_id, service_type)

        # Generate result key
        # Get request for user_id, output_format, and context for path
        request = job.request
        result_key = generate_result_key(
            user_id=request.user_id,
            request_id=request.id,
            file_id=file_id,
            output_format=request.output_format,
            original_name=file.original_name,
            method=request.method,
            created_at=request.created_at,
        )

        # Store in MinIO results bucket
        await self.storage.upload(
            bucket=settings.minio_bucket_results,
            object_key=result_key,
            data=content,
            content_type=content_type,
        )

        # Update job with result path
        self.job_repo.set_result_path(job, result_key)

        logger.info(
            "Uploaded result for job %s: %s", job_id, result_key,
            extra={"job_id": job_id},
        )
        return result_key
