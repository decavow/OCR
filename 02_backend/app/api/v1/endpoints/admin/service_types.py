# Admin endpoints for Service Types

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_admin_user, get_request_id
from app.infrastructure.database.models import User, ServiceTypeStatus
from app.infrastructure.database.repositories import ServiceTypeRepository, AuditLogRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class ServiceTypeResponse(BaseModel):
    """Service type response."""
    id: str
    display_name: str
    description: Optional[str]
    status: str
    access_key: Optional[str]
    allowed_methods: List[str]
    allowed_tiers: List[int]
    engine_info: Optional[dict]
    dev_contact: Optional[str]
    max_instances: int
    registered_at: str
    approved_at: Optional[str]
    approved_by: Optional[str]
    rejected_at: Optional[str]
    rejection_reason: Optional[str]
    instance_count: dict  # {status: count}

    class Config:
        from_attributes = True


class ServiceTypeListResponse(BaseModel):
    """List of service types."""
    items: List[ServiceTypeResponse]
    total: int


class RejectRequest(BaseModel):
    """Request body for rejecting a service type."""
    reason: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=ServiceTypeListResponse)
async def list_service_types(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    List all service types.

    Optionally filter by status (PENDING, APPROVED, DISABLED, REJECTED).
    """
    service_type_repo = ServiceTypeRepository(db)

    if status:
        types = service_type_repo.get_by_status(status)
    else:
        types = service_type_repo.get_all()

    items = []
    for t in types:
        items.append(_build_response(t, service_type_repo))

    return ServiceTypeListResponse(items=items, total=len(items))


@router.get("/{type_id}", response_model=ServiceTypeResponse)
async def get_service_type(
    type_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get service type details."""
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    return _build_response(service_type, service_type_repo)


@router.post("/{type_id}/approve", response_model=ServiceTypeResponse)
async def approve_service_type(
    type_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Approve a service type.

    - Generates access_key for the type
    - All WAITING instances become ACTIVE
    - Instances receive access_key via next heartbeat
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    if service_type.status == ServiceTypeStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Service type already approved")

    if service_type.status == ServiceTypeStatus.REJECTED:
        raise HTTPException(
            status_code=400,
            detail="Cannot approve rejected service type. Delete and re-register instead."
        )

    try:
        service_type = service_type_repo.approve(service_type, approved_by=admin.email)
    except ValueError as e:
        logger.warning("Approve failed for service type %s: %s", type_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.warning(
        "APPROVE service type: %s by %s, allowed_methods=%s",
        type_id, admin.email, service_type.allowed_methods,
        extra={"request_id": rid, "action": "APPROVE", "actor_email": admin.email, "entity_type": "service_type", "entity_id": type_id},
    )
    AuditLogRepository(db).record(
        actor_email=admin.email, action="APPROVE", entity_type="service_type",
        entity_id=type_id, details={"allowed_methods": json.loads(service_type.allowed_methods)}, request_id=rid,
    )

    return _build_response(service_type, service_type_repo)


@router.post("/{type_id}/reject", response_model=ServiceTypeResponse)
async def reject_service_type(
    type_id: str,
    data: RejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Reject a service type (terminal state).

    - All instances receive shutdown signal via next heartbeat
    - Cannot be undone - must delete and re-register
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    if service_type.status == ServiceTypeStatus.REJECTED:
        raise HTTPException(status_code=400, detail="Service type already rejected")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    try:
        service_type = service_type_repo.reject(service_type, data.reason)
    except ValueError as e:
        logger.warning("Reject failed for service type %s: %s", type_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.warning(
        "REJECT service type: %s by %s, reason=%s",
        type_id, admin.email, data.reason,
        extra={"request_id": rid, "action": "REJECT", "actor_email": admin.email, "entity_type": "service_type", "entity_id": type_id},
    )
    AuditLogRepository(db).record(
        actor_email=admin.email, action="REJECT", entity_type="service_type",
        entity_id=type_id, details={"reason": data.reason}, request_id=rid,
    )

    return _build_response(service_type, service_type_repo)


@router.post("/{type_id}/disable", response_model=ServiceTypeResponse)
async def disable_service_type(
    type_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Temporarily disable a service type.

    - All instances receive drain signal via next heartbeat
    - Instances finish current job then stop accepting new jobs
    - Can be re-enabled with /enable
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    if service_type.status != ServiceTypeStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only disable APPROVED types (current: {service_type.status})"
        )

    try:
        service_type = service_type_repo.disable(service_type)
    except ValueError as e:
        logger.warning("Disable failed for service type %s: %s", type_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.warning(
        "DISABLE service type: %s by %s",
        type_id, admin.email,
        extra={"request_id": rid, "action": "DISABLE", "actor_email": admin.email, "entity_type": "service_type", "entity_id": type_id},
    )
    AuditLogRepository(db).record(
        actor_email=admin.email, action="DISABLE", entity_type="service_type",
        entity_id=type_id, request_id=rid,
    )

    return _build_response(service_type, service_type_repo)


@router.post("/{type_id}/enable", response_model=ServiceTypeResponse)
async def enable_service_type(
    type_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Re-enable a disabled service type.

    - All WAITING/DRAINING instances become ACTIVE
    - Instances resume accepting jobs
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    if service_type.status != ServiceTypeStatus.DISABLED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only enable DISABLED types (current: {service_type.status})"
        )

    try:
        service_type = service_type_repo.enable(service_type)
    except ValueError as e:
        logger.warning("Enable failed for service type %s: %s", type_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "ENABLE service type: %s by %s",
        type_id, admin.email,
        extra={"request_id": rid, "action": "ENABLE", "actor_email": admin.email, "entity_type": "service_type", "entity_id": type_id},
    )
    AuditLogRepository(db).record(
        actor_email=admin.email, action="ENABLE", entity_type="service_type",
        entity_id=type_id, request_id=rid,
    )

    return _build_response(service_type, service_type_repo)


@router.delete("/{type_id}")
async def delete_service_type(
    type_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Delete a service type and all its instances.

    Use this to clean up rejected types before re-registering with same name.
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get(type_id)

    if not service_type:
        raise HTTPException(status_code=404, detail="Service type not found")

    logger.warning(
        "DELETE service type: %s by %s (was %s)",
        type_id, admin.email, service_type.status,
        extra={"request_id": rid, "action": "DELETE", "actor_email": admin.email, "entity_type": "service_type", "entity_id": type_id},
    )
    AuditLogRepository(db).record(
        actor_email=admin.email, action="DELETE", entity_type="service_type",
        entity_id=type_id, details={"previous_status": service_type.status}, request_id=rid,
    )

    service_type_repo.delete_with_instances(service_type)

    return {"success": True, "deleted": type_id}


# =============================================================================
# Helpers
# =============================================================================

def _build_response(service_type, repo: ServiceTypeRepository) -> ServiceTypeResponse:
    """Build response from service type model."""
    return ServiceTypeResponse(
        id=service_type.id,
        display_name=service_type.display_name,
        description=service_type.description,
        status=service_type.status,
        access_key=service_type.access_key,
        allowed_methods=json.loads(service_type.allowed_methods),
        allowed_tiers=json.loads(service_type.allowed_tiers),
        engine_info=json.loads(service_type.engine_info) if service_type.engine_info else None,
        dev_contact=service_type.dev_contact,
        max_instances=service_type.max_instances,
        registered_at=service_type.registered_at.isoformat(),
        approved_at=service_type.approved_at.isoformat() if service_type.approved_at else None,
        approved_by=service_type.approved_by,
        rejected_at=service_type.rejected_at.isoformat() if service_type.rejected_at else None,
        rejection_reason=service_type.rejection_reason,
        instance_count=repo.get_instance_count(service_type),
    )
