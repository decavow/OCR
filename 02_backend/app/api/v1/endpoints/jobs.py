# GET /jobs/:id, /jobs/:id/result (text content)

import json
import logging
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.schemas.job import JobResponse, JobResultResponse, JobResultMetadata
from app.api.deps import get_current_user, get_db, get_storage, get_job_service
from app.infrastructure.database.repositories import JobRepository, RequestRepository, FileRepository, ServiceTypeRepository
from app.infrastructure.storage.exceptions import ObjectNotFoundError
from app.modules.job.service import JobService
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    current_user=Depends(get_current_user),
):
    """Get job status."""
    job = await job_service.get_job(job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Parse error history
    error_history = []
    if job.error_history:
        try:
            error_history = json.loads(job.error_history)
        except Exception as e:
            logger.debug("Failed to parse error_history for job %s: %s", job_id, e)

    return JobResponse(
        id=job.id,
        request_id=job.request_id,
        file_id=job.file_id,
        status=job.status,
        method=job.method,
        tier=job.tier,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        error_history=error_history,
        started_at=job.started_at,
        completed_at=job.completed_at,
        processing_time_ms=job.processing_time_ms,
        result_path=job.result_path,
        worker_id=job.worker_id,
        created_at=job.created_at,
    )


@router.get("/{job_id}/result")
async def get_job_result(
    job_id: str,
    format: str = "text",  # text, json, raw
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Get job result (text content)."""
    job_repo = JobRepository(db)
    request_repo = RequestRepository(db)

    # Get job
    job = job_repo.get_active(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership via request
    request = request_repo.get_active(job.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if job is completed
    if job.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    # Check if result exists
    if not job.result_path:
        raise HTTPException(status_code=404, detail="Result not found")

    # Download result from MinIO
    try:
        content = await storage.download(settings.minio_bucket_results, job.result_path)
    except ObjectNotFoundError:
        logger.warning("Result file not found in storage: job_id=%s path=%s", job_id, job.result_path)
        raise HTTPException(status_code=404, detail="Result file not found in storage")

    text = content.decode("utf-8")

    # Return based on format
    if format == "raw":
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="result_{job_id}.txt"'}
        )

    if format == "json" or request.output_format == "json":
        # Try to parse as JSON if output_format was json
        try:
            data = json.loads(text)
            return data
        except json.JSONDecodeError as e:
            logger.debug("Result is not valid JSON for job %s: %s", job_id, e)

    # Resolve engine name from service type
    engine_name = None
    if job.worker_id:
        service_type_repo = ServiceTypeRepository(db)
        svc_type = service_type_repo.get(job.worker_id)
        if svc_type and svc_type.engine_info:
            try:
                info = json.loads(svc_type.engine_info)
                engine_name = info.get("name")
            except (json.JSONDecodeError, TypeError):
                pass

    # Return structured response
    lines = text.strip().split("\n") if text.strip() else []
    return JobResultResponse(
        text=text,
        lines=len(lines),
        metadata=JobResultMetadata(
            method=job.method,
            tier=str(job.tier),
            processing_time_ms=job.processing_time_ms or 0,
            service_version=job.engine_version or "unknown",
            engine_name=engine_name,
        )
    )


@router.get("/{job_id}/download")
async def download_job_result(
    job_id: str,
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Download job result as file."""
    job_repo = JobRepository(db)
    request_repo = RequestRepository(db)
    file_repo = FileRepository(db)

    # Get job
    job = job_repo.get_active(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership via request
    request = request_repo.get_active(job.request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if job is completed
    if job.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    if not job.result_path:
        raise HTTPException(status_code=404, detail="Result not found")

    # Get original filename
    file = file_repo.get(job.file_id)
    original_name = file.original_name if file else "result"
    base_name = original_name.rsplit(".", 1)[0]

    # Determine extension
    ext = "json" if request.output_format == "json" else "txt"
    filename = f"{base_name}_result.{ext}"

    # Download from MinIO
    try:
        content = await storage.download(settings.minio_bucket_results, job.result_path)
    except ObjectNotFoundError:
        logger.warning("Result file not found for download: job_id=%s path=%s", job_id, job.result_path)
        raise HTTPException(status_code=404, detail="Result file not found")

    content_type = "application/json" if ext == "json" else "text/plain"

    # RFC 6266: use filename* for non-ASCII, fallback filename for ASCII
    ascii_filename = f"result_{job_id[:8]}.{ext}"
    encoded_filename = quote(filename)
    content_disposition = (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": content_disposition}
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    current_user=Depends(get_current_user),
):
    """Cancel a single job (only if QUEUED)."""
    result = await job_service.cancel_job(job_id, current_user.id)
    if not result["success"]:
        if result["message"] == "Job not found":
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=400, detail=result["message"])
    return result
