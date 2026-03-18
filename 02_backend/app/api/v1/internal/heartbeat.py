# POST /internal/heartbeat

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_request_id
from app.api.v1.schemas.heartbeat import HeartbeatPayload, HeartbeatResponse
from app.infrastructure.database.repositories import (
    ServiceTypeRepository,
    ServiceInstanceRepository,
    HeartbeatRepository,
)
from app.infrastructure.database.models import ServiceTypeStatus, ServiceInstanceStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def receive_heartbeat(
    data: HeartbeatPayload,
    request: Request,
    x_access_key: Optional[str] = Header(None, alias="X-Access-Key"),
    db: Session = Depends(get_db),
):
    """
    Receive heartbeat from worker instance.

    Workers call this endpoint periodically to report their status.

    Authentication:
    - If type is APPROVED and worker has key: X-Access-Key header required
    - If type is PENDING/DISABLED: No key required (worker is waiting)

    Response action:
    - "continue": Keep current state (waiting or processing)
    - "approved": Type was just approved, access_key included
    - "drain": Type was disabled, finish current job then stop
    - "shutdown": Type was rejected, shutdown immediately
    """
    rid = get_request_id(request)
    service_instance_repo = ServiceInstanceRepository(db)
    service_type_repo = ServiceTypeRepository(db)
    heartbeat_repo = HeartbeatRepository(db)

    # Get instance
    instance = service_instance_repo.get(data.instance_id)
    if not instance:
        logger.warning(
            "Heartbeat from unknown instance: %s", data.instance_id,
            extra={"request_id": rid, "instance_id": data.instance_id},
        )
        raise HTTPException(
            status_code=404,
            detail=f"Instance '{data.instance_id}' not found. Please register first."
        )

    # Get service type
    service_type = service_type_repo.get(instance.service_type_id)
    if not service_type:
        raise HTTPException(
            status_code=500,
            detail="Service type not found for instance"
        )

    # Validate access key for APPROVED types
    if service_type.status == ServiceTypeStatus.APPROVED:
        # Require key for active, processing, or dead instances (dead may re-activate)
        if instance.status in (ServiceInstanceStatus.ACTIVE, ServiceInstanceStatus.PROCESSING, ServiceInstanceStatus.DEAD):
            if not x_access_key:
                logger.warning(
                    "Missing access key for instance %s (type=%s)",
                    data.instance_id, instance.service_type_id,
                    extra={"request_id": rid, "instance_id": data.instance_id},
                )
                raise HTTPException(
                    status_code=401,
                    detail="X-Access-Key header required for approved service types"
                )
            if x_access_key != service_type.access_key:
                logger.warning(
                    "Invalid access key for instance %s (type=%s)",
                    data.instance_id, instance.service_type_id,
                    extra={"request_id": rid, "instance_id": data.instance_id},
                )
                raise HTTPException(
                    status_code=403,
                    detail="Invalid access key"
                )

    # Update instance heartbeat
    service_instance_repo.update_heartbeat(
        instance=instance,
        status=data.status,
        current_job_id=data.current_job_id,
    )

    # Record heartbeat in heartbeats table
    heartbeat_repo.upsert(
        instance_id=data.instance_id,
        status=data.status,
        current_job_id=data.current_job_id,
        files_completed=data.files_completed,
        files_total=data.files_total,
        error_count=data.error_count,
    )

    # Determine action based on type status
    action = "continue"
    access_key = None
    rejection_reason = None

    if service_type.status == ServiceTypeStatus.PENDING:
        action = "continue"  # Keep waiting

    elif service_type.status == ServiceTypeStatus.APPROVED:
        if instance.status == ServiceInstanceStatus.WAITING:
            # Instance was waiting, now approved - send key
            action = "approved"
            access_key = service_type.access_key
            # Activate the instance
            service_instance_repo.activate(instance)
            logger.info(
                "Instance %s approved, sending access key (type=%s)",
                data.instance_id, instance.service_type_id,
                extra={"request_id": rid, "instance_id": data.instance_id, "service_type": instance.service_type_id},
            )
        elif instance.status == ServiceInstanceStatus.DEAD:
            # Instance was marked dead (heartbeat timeout) but is back — re-activate
            action = "approved"
            access_key = service_type.access_key
            service_instance_repo.activate(instance)
            logger.info(
                "Instance %s re-activated from DEAD (type=%s)",
                data.instance_id, instance.service_type_id,
                extra={"request_id": rid, "instance_id": data.instance_id, "service_type": instance.service_type_id},
            )
        else:
            action = "continue"

    elif service_type.status == ServiceTypeStatus.DISABLED:
        action = "drain"
        # Mark instance as draining if not already
        if instance.status not in (ServiceInstanceStatus.DRAINING, ServiceInstanceStatus.WAITING):
            service_instance_repo.mark_draining(instance)
            logger.info(
                "Instance %s entering drain mode (type=%s)",
                data.instance_id, instance.service_type_id,
                extra={"request_id": rid, "instance_id": data.instance_id, "service_type": instance.service_type_id},
            )

    elif service_type.status == ServiceTypeStatus.REJECTED:
        action = "shutdown"
        rejection_reason = service_type.rejection_reason or "Service type rejected"
        # Mark instance as dead
        service_instance_repo.mark_dead(instance)
        logger.warning(
            "Instance %s shutdown signal sent (type=%s rejected: %s)",
            data.instance_id, instance.service_type_id, rejection_reason,
            extra={"request_id": rid, "instance_id": data.instance_id, "service_type": instance.service_type_id},
        )

    return HeartbeatResponse(
        success=True,
        received_at=datetime.now(timezone.utc).isoformat(),
        action=action,
        access_key=access_key,
        rejection_reason=rejection_reason,
    )
