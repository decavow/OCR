# UploadService: process_upload(), validate_and_store()

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from dataclasses import dataclass
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Request, File, Job, ServiceInstanceStatus
from app.infrastructure.database.repositories import (
    RequestRepository,
    FileRepository,
    JobRepository,
    ServiceTypeRepository,
)
from app.infrastructure.storage import MinIOStorageService, generate_object_key
from app.infrastructure.queue import NATSQueueService, JobMessage, get_subject
from app.config import settings
from .validators import validate_file, validate_batch, validate_total_batch_size
from .exceptions import ServiceNotAvailable

logger = logging.getLogger(__name__)


@dataclass
class ValidatedFile:
    """Holds validated file data before storing."""
    filename: str
    content: bytes
    mime_type: str
    file_id: str
    job_id: str


class UploadService:
    def __init__(
        self,
        db: Session,
        storage: MinIOStorageService,
        queue: NATSQueueService,
    ):
        self.db = db
        self.storage = storage
        self.queue = queue
        self.request_repo = RequestRepository(db)
        self.file_repo = FileRepository(db)
        self.job_repo = JobRepository(db)
        self.service_type_repo = ServiceTypeRepository(db)

    async def process_upload(
        self,
        user_id: str,
        files: List[UploadFile],
        output_format: str = "txt",
        retention_hours: int = 168,
        method: str = "ocr_text_raw",
        tier: int = 0,
    ) -> Request:
        """Process file upload: validate, store, create request and jobs."""
        # Step 0: Validate method/tier against approved services
        self._validate_service_available(method, tier)

        # Step 1: Validate batch size
        validate_batch(files)

        # Step 2: Read and validate ALL files BEFORE creating any records
        validated_files: List[ValidatedFile] = []
        for upload_file in files:
            validated = await self._validate_single_file(upload_file)
            validated_files.append(validated)

        # Step 2.5: Validate total batch size (200MB limit)
        total_size = sum(len(v.content) for v in validated_files)
        validate_total_batch_size(total_size)

        # Step 3: All files valid - now create Request record
        expires_at = datetime.now(timezone.utc) + timedelta(hours=retention_hours)
        request = self.request_repo.create_request(
            user_id=user_id,
            file_count=len(validated_files),
            output_format=output_format,
            method=method,
            tier=tier,
            expires_at=expires_at,
        )
        logger.info(f"Created request {request.id} for user {user_id}")

        # Step 4: Store files and create File/Job records
        for validated in validated_files:
            await self._store_and_publish(
                validated=validated,
                request=request,
                user_id=user_id,
                output_format=output_format,
                method=method,
                tier=tier,
            )

        return request

    def _validate_service_available(self, method: str, tier: int) -> None:
        """Ensure at least one approved service with active instances can handle this method/tier."""
        approved_types = self.service_type_repo.get_approved()
        for st in approved_types:
            if not self.service_type_repo.can_handle(st, method, tier):
                continue
            active_count = sum(
                1 for inst in st.instances
                if inst.status in (ServiceInstanceStatus.ACTIVE, ServiceInstanceStatus.PROCESSING)
            )
            if active_count > 0:
                return
        raise ServiceNotAvailable(method, tier)

    async def _validate_single_file(self, upload_file: UploadFile) -> ValidatedFile:
        """Read and validate a single file. Raises exception if invalid."""
        content = await upload_file.read()
        filename = upload_file.filename or "unknown"
        declared_mime = upload_file.content_type or "application/octet-stream"

        # Validate - raises exception if invalid
        mime_type = validate_file(content, declared_mime, filename)

        return ValidatedFile(
            filename=filename,
            content=content,
            mime_type=mime_type,
            file_id=str(uuid.uuid4()),
            job_id=str(uuid.uuid4()),
        )

    async def _store_and_publish(
        self,
        validated: ValidatedFile,
        request: Request,
        user_id: str,
        output_format: str,
        method: str,
        tier: int,
    ) -> Tuple[File, Job]:
        """Store validated file in MinIO and create DB records."""
        object_key = generate_object_key(
            user_id, request.id, validated.file_id, validated.filename
        )

        # Store in MinIO
        await self.storage.upload(
            bucket=settings.minio_bucket_uploads,
            object_key=object_key,
            data=validated.content,
            content_type=validated.mime_type,
        )
        logger.debug(f"Stored file {validated.file_id} in MinIO: {object_key}")

        # Create File record
        file_record = self.file_repo.create_file(
            file_id=validated.file_id,
            request_id=request.id,
            original_name=validated.filename,
            mime_type=validated.mime_type,
            size_bytes=len(validated.content),
            object_key=object_key,
        )
        logger.debug(f"Created file record: {validated.file_id}")

        # Create Job record
        job = self.job_repo.create_job(
            job_id=validated.job_id,
            request_id=request.id,
            file_id=validated.file_id,
            method=method,
            tier=tier,
        )
        logger.debug(f"Created job record: {validated.job_id}")

        # Publish to NATS
        subject = get_subject(method, tier)
        message = JobMessage(
            job_id=validated.job_id,
            file_id=validated.file_id,
            request_id=request.id,
            method=method,
            tier=tier,
            output_format=output_format,
            object_key=object_key,
        )
        await self.queue.publish(subject, message)
        logger.info(f"Published job {validated.job_id} to {subject}")

        return file_record, job
