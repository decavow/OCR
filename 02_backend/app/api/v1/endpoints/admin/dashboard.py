# Admin dashboard endpoints: stats, recent requests, users, job volume

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_admin_user
from app.infrastructure.database.models import User
from app.infrastructure.database.repositories import (
    UserRepository,
    RequestRepository,
    JobRepository,
    ServiceTypeRepository,
    ServiceInstanceRepository,
)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class AdminStatsResponse(BaseModel):
    total_users: int
    total_requests: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    processing_jobs: int
    avg_processing_time_ms: Optional[float]
    success_rate: float


class AdminRequestItem(BaseModel):
    id: str
    user_id: str
    user_email: str
    method: str
    tier: int
    output_format: str
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    created_at: str
    completed_at: Optional[str]


class AdminRequestListResponse(BaseModel):
    items: List[AdminRequestItem]
    total: int
    page: int
    page_size: int


class AdminUserItem(BaseModel):
    id: str
    email: str
    is_admin: bool
    created_at: str
    total_requests: int


class AdminUserListResponse(BaseModel):
    items: List[AdminUserItem]
    total: int


class JobVolumePoint(BaseModel):
    hour: str
    volume: int
    avg_latency_ms: float


class JobVolumeResponse(BaseModel):
    data: List[JobVolumePoint]


class ServiceInstanceItem(BaseModel):
    id: str
    service_type_id: str
    status: str
    registered_at: str
    last_heartbeat_at: str
    current_job_id: Optional[str]


class ServiceInstanceListResponse(BaseModel):
    items: List[ServiceInstanceItem]
    total: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get system-wide KPI stats."""
    user_repo = UserRepository(db)
    request_repo = RequestRepository(db)
    job_repo = JobRepository(db)

    total_jobs = job_repo.count_all_active()
    completed = job_repo.count_all_by_status("COMPLETED")
    failed = job_repo.count_all_by_status("FAILED")
    processing = job_repo.count_all_by_status("PROCESSING")

    success_rate = (completed / total_jobs * 100) if total_jobs > 0 else 0.0

    return AdminStatsResponse(
        total_users=user_repo.count_active(exclude_admins=True),
        total_requests=request_repo.count_all_active(),
        total_jobs=total_jobs,
        completed_jobs=completed,
        failed_jobs=failed,
        processing_jobs=processing,
        avg_processing_time_ms=job_repo.avg_processing_time(),
        success_rate=round(success_rate, 1),
    )


@router.get("/recent-requests", response_model=AdminRequestListResponse)
async def get_admin_recent_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get recent requests from all users."""
    request_repo = RequestRepository(db)
    user_repo = UserRepository(db)

    skip = (page - 1) * page_size
    requests = request_repo.get_all_recent(skip=skip, limit=page_size)
    total = request_repo.count_all_active()

    items = []
    for r in requests:
        user = user_repo.get(r.user_id)
        items.append(AdminRequestItem(
            id=r.id,
            user_id=r.user_id,
            user_email=user.email if user else "unknown",
            method=r.method,
            tier=r.tier,
            output_format=r.output_format,
            status=r.status,
            total_files=r.total_files,
            completed_files=r.completed_files,
            failed_files=r.failed_files,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        ))

    return AdminRequestListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def get_admin_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get all users with request counts."""
    user_repo = UserRepository(db)
    request_repo = RequestRepository(db)

    skip = (page - 1) * page_size
    users = user_repo.get_all_active(skip=skip, limit=page_size, exclude_admins=True)
    total = user_repo.count_active(exclude_admins=True)

    items = []
    for u in users:
        items.append(AdminUserItem(
            id=u.id,
            email=u.email,
            is_admin=u.is_admin,
            created_at=u.created_at.isoformat(),
            total_requests=request_repo.count_by_user(u.id),
        ))

    return AdminUserListResponse(items=items, total=total)


@router.get("/job-volume", response_model=JobVolumeResponse)
async def get_job_volume(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get job volume grouped by hour."""
    job_repo = JobRepository(db)
    data = job_repo.get_hourly_volume(hours=hours)
    return JobVolumeResponse(data=data)


@router.get("/service-instances", response_model=ServiceInstanceListResponse)
async def get_admin_service_instances(
    type_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get all service instances for system health view."""
    instance_repo = ServiceInstanceRepository(db)

    if type_id and status:
        instances = instance_repo.get_by_type_and_status(type_id, status)
    elif type_id:
        instances = instance_repo.get_by_type(type_id)
    elif status:
        instances = instance_repo.get_by_status(status)
    else:
        instances = instance_repo.get_all()

    items = [
        ServiceInstanceItem(
            id=i.id,
            service_type_id=i.service_type_id,
            status=i.status,
            registered_at=i.registered_at.isoformat(),
            last_heartbeat_at=i.last_heartbeat_at.isoformat(),
            current_job_id=i.current_job_id,
        )
        for i in instances
    ]

    return ServiceInstanceListResponse(items=items, total=len(items))
