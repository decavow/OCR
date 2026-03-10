# POST /internal/register - Worker registration endpoint

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_request_id
from app.api.v1.schemas.register import (
    ServiceRegistrationRequest,
    ServiceRegistrationResponse,
    ServiceDeregisterRequest,
)
from app.infrastructure.database.repositories import (
    ServiceTypeRepository,
    ServiceInstanceRepository,
)
from app.infrastructure.database.models import ServiceTypeStatus, ServiceInstanceStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=ServiceRegistrationResponse)
async def register_service(
    data: ServiceRegistrationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Register a service instance.

    Flow:
    - If service_type doesn't exist: Create it with PENDING status, create instance with WAITING
    - If service_type exists and APPROVED: Create instance with ACTIVE, return access_key
    - If service_type exists and PENDING/DISABLED: Create instance with WAITING
    - If service_type exists and REJECTED: Return 403 error

    Workers call this on startup to register themselves.
    """
    rid = get_request_id(request)
    service_type_repo = ServiceTypeRepository(db)
    service_instance_repo = ServiceInstanceRepository(db)

    # Check if service type exists
    service_type = service_type_repo.get(data.service_type)

    if not service_type:
        # Create new service type in PENDING state
        logger.warning(
            "New service type registration: %s, allowed_methods=%s",
            data.service_type, data.allowed_methods,
            extra={"request_id": rid, "service_type": data.service_type},
        )
        service_type = service_type_repo.register(
            type_id=data.service_type,
            display_name=data.display_name or data.service_type,
            description=data.description,
            allowed_methods=data.allowed_methods,
            allowed_tiers=data.allowed_tiers,
            engine_info=data.engine_info,
            dev_contact=data.dev_contact,
            supported_output_formats=data.supported_output_formats,
        )
    else:
        logger.info(
            "Existing service type re-registration: %s (status=%s), allowed_methods=%s",
            data.service_type, service_type.status, data.allowed_methods,
            extra={"request_id": rid, "service_type": data.service_type},
        )
        # Update mutable fields via register()
        service_type = service_type_repo.register(
            type_id=data.service_type,
            display_name=data.display_name or data.service_type,
            description=data.description,
            allowed_methods=data.allowed_methods,
            allowed_tiers=data.allowed_tiers,
            engine_info=data.engine_info,
            dev_contact=data.dev_contact,
            supported_output_formats=data.supported_output_formats,
        )

    # Check if type is rejected
    if service_type.status == ServiceTypeStatus.REJECTED:
        logger.warning(
            "Registration rejected for type %s: %s",
            data.service_type, service_type.rejection_reason,
            extra={"request_id": rid, "service_type": data.service_type},
        )
        raise HTTPException(
            status_code=403,
            detail=f"Service type '{data.service_type}' has been rejected: {service_type.rejection_reason or 'No reason provided'}"
        )

    # Register the instance
    instance = service_instance_repo.register(
        instance_id=data.instance_id,
        service_type=service_type,
        metadata=data.metadata,
    )

    logger.info(
        "Instance registered: %s (type=%s, instance_status=%s, type_status=%s)",
        data.instance_id, data.service_type, instance.status, service_type.status,
        extra={"request_id": rid, "instance_id": data.instance_id, "service_type": data.service_type},
    )

    # Build response
    response = ServiceRegistrationResponse(
        instance_id=instance.id,
        instance_status=instance.status,
        type_status=service_type.status,
    )

    # Include access_key if type is already approved
    if service_type.status == ServiceTypeStatus.APPROVED:
        response.access_key = service_type.access_key

    return response


@router.post("/deregister")
async def deregister_service(
    data: ServiceDeregisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Deregister a service instance.

    Workers call this on graceful shutdown to mark themselves as DEAD.
    """
    rid = get_request_id(request)
    service_instance_repo = ServiceInstanceRepository(db)

    success = service_instance_repo.deregister(data.instance_id)

    logger.info(
        "Instance deregistered: %s (success=%s)",
        data.instance_id, success,
        extra={"request_id": rid, "instance_id": data.instance_id},
    )

    return {
        "success": success,
        "instance_id": data.instance_id,
    }
