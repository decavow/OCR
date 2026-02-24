# PATCH /internal/jobs/:id/status

from fastapi import APIRouter, Header, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.infrastructure.database.repositories import JobRepository, ServiceTypeRepository
from app.infrastructure.database.models import ServiceTypeStatus
from app.api.v1.schemas.job import JobStatus

router = APIRouter()


class JobStatusUpdate(BaseModel):
    status: str
    error: Optional[str] = None
    retriable: bool = True
    engine_version: Optional[str] = None


@router.patch("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    data: JobStatusUpdate,
    x_access_key: str = Header(..., alias="X-Access-Key"),
    db: Session = Depends(get_db),
):
    """Update job status from worker.

    Workers call this endpoint to report job completion or failure.
    Access is verified via the X-Access-Key header.
    """
    # Verify access key
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get_by_access_key(x_access_key)
    if not service_type:
        raise HTTPException(status_code=403, detail="Invalid access key")
    if service_type.status != ServiceTypeStatus.APPROVED:
        raise HTTPException(status_code=403, detail=f"Service type is {service_type.status}, not APPROVED")

    # Get job
    job_repo = JobRepository(db)
    job = job_repo.get_active(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Validate status transition
    valid_statuses = {s.value for s in JobStatus}
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    # Update job status
    job = job_repo.update_status(
        job=job,
        status=data.status,
        worker_id=service_type.id,
        error=data.error,
        retriable=data.retriable,
        engine_version=data.engine_version,
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": job.status,
    }
