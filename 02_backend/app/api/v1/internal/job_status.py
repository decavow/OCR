# PATCH /internal/jobs/:id/status

import logging
from fastapi import APIRouter, Header, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_job_service, get_request_id
from app.infrastructure.database.repositories import ServiceTypeRepository
from app.infrastructure.database.models import ServiceTypeStatus
from app.api.v1.schemas.job import JobStatus
from app.modules.job.service import JobService

logger = logging.getLogger(__name__)

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
    request: Request,
    x_access_key: str = Header(..., alias="X-Access-Key"),
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
):
    """Update job status from worker.

    Workers call this endpoint to report job completion or failure.
    Access is verified via the X-Access-Key header.
    """
    rid = get_request_id(request)

    # Verify access key
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get_by_access_key(x_access_key)
    if not service_type:
        logger.warning(
            "Invalid access key for job status update: job_id=%s", job_id,
            extra={"request_id": rid, "job_id": job_id},
        )
        raise HTTPException(status_code=403, detail="Invalid access key")
    if service_type.status != ServiceTypeStatus.APPROVED:
        logger.warning(
            "Non-approved service type attempted status update: type=%s status=%s job_id=%s",
            service_type.id, service_type.status, job_id,
            extra={"request_id": rid, "job_id": job_id, "service_type": service_type.id},
        )
        raise HTTPException(status_code=403, detail=f"Service type is {service_type.status}, not APPROVED")

    # Validate status value
    valid_statuses = {s.value for s in JobStatus}
    if data.status not in valid_statuses:
        logger.warning(
            "Invalid job status value: %s for job_id=%s", data.status, job_id,
            extra={"request_id": rid, "job_id": job_id},
        )
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    # Update job via JobService (handles status recalculation + retry)
    job = await job_service.update_job_status(
        job_id=job_id,
        status=data.status,
        worker_id=service_type.id,
        error=data.error,
        retriable=data.retriable,
        engine_version=data.engine_version,
    )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or invalid status transition")

    logger.info(
        "Job status updated: job_id=%s new_status=%s worker=%s",
        job_id, job.status, service_type.id,
        extra={"request_id": rid, "job_id": job_id, "service_type": service_type.id},
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": job.status,
    }
