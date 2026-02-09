# Admin endpoints for Service Instances (read-only)

import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.infrastructure.database.repositories import ServiceInstanceRepository

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class ServiceInstanceResponse(BaseModel):
    """Service instance response."""
    id: str
    service_type_id: str
    status: str
    registered_at: str
    last_heartbeat_at: str
    current_job_id: Optional[str]
    metadata: Optional[dict]

    class Config:
        from_attributes = True


class ServiceInstanceListResponse(BaseModel):
    """List of service instances."""
    items: List[ServiceInstanceResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=ServiceInstanceListResponse)
async def list_service_instances(
    type: Optional[str] = Query(None, alias="type", description="Filter by service type ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """
    List all service instances.

    Optionally filter by type or status.
    """
    instance_repo = ServiceInstanceRepository(db)

    if type and status:
        instances = instance_repo.get_by_type_and_status(type, status)
    elif type:
        instances = instance_repo.get_by_type(type)
    elif status:
        instances = instance_repo.get_by_status(status)
    else:
        instances = instance_repo.get_all()

    items = [_build_response(i) for i in instances]

    return ServiceInstanceListResponse(items=items, total=len(items))


@router.get("/{instance_id}", response_model=ServiceInstanceResponse)
async def get_service_instance(
    instance_id: str,
    db: Session = Depends(get_db),
):
    """Get service instance details."""
    instance_repo = ServiceInstanceRepository(db)
    instance = instance_repo.get(instance_id)

    if not instance:
        raise HTTPException(status_code=404, detail="Service instance not found")

    return _build_response(instance)


# =============================================================================
# Helpers
# =============================================================================

def _build_response(instance) -> ServiceInstanceResponse:
    """Build response from service instance model."""
    return ServiceInstanceResponse(
        id=instance.id,
        service_type_id=instance.service_type_id,
        status=instance.status,
        registered_at=instance.registered_at.isoformat(),
        last_heartbeat_at=instance.last_heartbeat_at.isoformat(),
        current_job_id=instance.current_job_id,
        metadata=json.loads(instance.instance_metadata) if instance.instance_metadata else None,
    )
