# GET /requests, /requests/:id, POST /requests/:id/cancel

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.api.v1.schemas.request import RequestResponse, RequestListResponse
from app.api.deps import get_current_user, get_db, get_job_service
from app.infrastructure.database.repositories import RequestRepository, JobRepository
from app.modules.job.service import JobService

router = APIRouter()


class JobSummary(BaseModel):
    id: str
    file_id: str
    status: str
    method: str
    tier: int
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_ms: int | None = None
    result_path: str | None = None

    class Config:
        from_attributes = True


class RequestDetailResponse(RequestResponse):
    jobs: List[JobSummary] = []


@router.get("", response_model=RequestListResponse)
async def get_requests(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = Query(None, description="Filter by status (PROCESSING, COMPLETED, FAILED, etc.)"),
    method: Optional[str] = Query(None, description="Filter by OCR method (ocr_paddle_text, ocr_tesseract_text, etc.)"),
    date_from: Optional[datetime] = Query(None, description="Filter by created_at >= date_from (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, description="Filter by created_at <= date_to (ISO 8601)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all requests (batches) for current user with optional filters."""
    request_repo = RequestRepository(db)

    # Calculate offset
    skip = (page - 1) * page_size

    filter_kwargs = dict(status=status, method=method, date_from=date_from, date_to=date_to)

    # Get requests and total count
    requests = request_repo.get_by_user(current_user.id, skip=skip, limit=page_size, **filter_kwargs)
    total = request_repo.count_by_user(current_user.id, **filter_kwargs)

    return RequestListResponse(
        items=[RequestResponse.model_validate(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{request_id}", response_model=RequestDetailResponse)
async def get_request(
    request_id: str,
    job_service: JobService = Depends(get_job_service),
    current_user=Depends(get_current_user),
):
    """Get a specific request with jobs."""
    result = await job_service.get_request_with_jobs(request_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")

    request, jobs = result
    return RequestDetailResponse(
        id=request.id,
        user_id=request.user_id,
        method=request.method,
        tier=request.tier,
        output_format=request.output_format,
        retention_hours=request.retention_hours,
        status=request.status,
        total_files=request.total_files,
        completed_files=request.completed_files,
        failed_files=request.failed_files,
        created_at=request.created_at,
        completed_at=request.completed_at,
        jobs=[JobSummary.model_validate(j) for j in jobs],
    )


@router.post("/{request_id}/cancel")
async def cancel_request(
    request_id: str,
    job_service: JobService = Depends(get_job_service),
    current_user=Depends(get_current_user),
):
    """Cancel a request (only cancels QUEUED jobs)."""
    result = await job_service.cancel_request(request_id, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result
