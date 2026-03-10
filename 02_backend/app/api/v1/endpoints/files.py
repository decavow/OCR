# GET /files/:id/original-url, /files/:id/result-url, /files/:id/download

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.schemas.file import FileResponse, PresignedUrlResponse
from app.api.deps import get_current_user, get_db, get_storage
from app.infrastructure.database.repositories import FileRepository, RequestRepository, JobRepository
from app.infrastructure.storage.exceptions import ObjectNotFoundError
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get file metadata."""
    file_repo = FileRepository(db)
    request_repo = RequestRepository(db)

    # Get file
    file = file_repo.get_active(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check ownership via request
    request = request_repo.get_active(file.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse.model_validate(file)


@router.get("/{file_id}/original-url", response_model=PresignedUrlResponse)
async def get_original_url(
    file_id: str,
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Get presigned URL for original file."""
    file_repo = FileRepository(db)
    request_repo = RequestRepository(db)

    # Get file
    file = file_repo.get_active(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check ownership via request
    request = request_repo.get_active(file.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Generate presigned URL
    expires = timedelta(hours=1)
    url = await storage.get_presigned_url(
        settings.minio_bucket_uploads,
        file.object_key,
        expires=expires,
    )

    return PresignedUrlResponse(
        url=url,
        expires_at=datetime.now(timezone.utc) + expires,
    )


@router.get("/{file_id}/result-url", response_model=PresignedUrlResponse)
async def get_result_url(
    file_id: str,
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Get presigned URL for result file."""
    file_repo = FileRepository(db)
    request_repo = RequestRepository(db)
    job_repo = JobRepository(db)

    # Get file
    file = file_repo.get_active(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check ownership via request
    request = request_repo.get_active(file.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get job for this file to find result_path
    job = job_repo.get_by_file(file_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found for file")

    if job.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    if not job.result_path:
        raise HTTPException(status_code=404, detail="Result not found")

    # Generate presigned URL
    expires = timedelta(hours=1)
    url = await storage.get_presigned_url(
        settings.minio_bucket_results,
        job.result_path,
        expires=expires,
    )

    return PresignedUrlResponse(
        url=url,
        expires_at=datetime.now(timezone.utc) + expires,
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    type: str = "original",  # original or result
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Download file (original or result)."""
    file_repo = FileRepository(db)
    request_repo = RequestRepository(db)
    job_repo = JobRepository(db)

    # Get file
    file = file_repo.get_active(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check ownership via request
    request = request_repo.get_active(file.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if type == "original":
        # Download original file
        try:
            content = await storage.download(settings.minio_bucket_uploads, file.object_key)
        except ObjectNotFoundError:
            logger.warning("Original file not found in storage: file_id=%s key=%s", file_id, file.object_key)
            raise HTTPException(status_code=404, detail="Original file not found")

        return Response(
            content=content,
            media_type=file.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file.original_name}"'}
        )

    elif type == "result":
        # Get job for this file
        job = job_repo.get_by_file(file_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found for file")

        if job.status != "COMPLETED":
            raise HTTPException(
                status_code=400,
                detail=f"Job is not completed. Current status: {job.status}"
            )

        if not job.result_path:
            raise HTTPException(status_code=404, detail="Result not found")

        # Download result
        try:
            content = await storage.download(settings.minio_bucket_results, job.result_path)
        except ObjectNotFoundError:
            logger.warning("Result file not found in storage: file_id=%s path=%s", file_id, job.result_path)
            raise HTTPException(status_code=404, detail="Result file not found")

        # Determine filename and content type
        base_name = file.original_name.rsplit(".", 1)[0]
        ext = "json" if request.output_format == "json" else "txt"
        filename = f"{base_name}_result.{ext}"
        content_type = "application/json" if ext == "json" else "text/plain"

        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid type. Use 'original' or 'result'")
