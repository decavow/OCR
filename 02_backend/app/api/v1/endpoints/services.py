# GET /services/available - Public endpoint for available OCR services

import json
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.infrastructure.database.repositories import ServiceTypeRepository
from app.infrastructure.database.models import ServiceInstanceStatus

router = APIRouter()


class AvailableServiceResponse(BaseModel):
    """A single available OCR service."""
    id: str
    display_name: str
    description: str | None
    allowed_methods: List[str]
    allowed_tiers: List[int]
    supported_output_formats: List[str]
    active_instances: int


class AvailableServicesListResponse(BaseModel):
    """List of available services."""
    items: List[AvailableServiceResponse]
    total: int


@router.get("/available", response_model=AvailableServicesListResponse)
async def list_available_services(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List OCR services available for use.

    Only returns APPROVED service types that have at least one
    ACTIVE or PROCESSING instance (i.e. actually running workers).
    """
    service_type_repo = ServiceTypeRepository(db)
    approved_types = service_type_repo.get_approved()

    items = []
    for st in approved_types:
        active_count = sum(
            1 for inst in st.instances
            if inst.status in (ServiceInstanceStatus.ACTIVE, ServiceInstanceStatus.PROCESSING)
        )
        if active_count == 0:
            continue

        items.append(AvailableServiceResponse(
            id=st.id,
            display_name=st.display_name,
            description=st.description,
            allowed_methods=json.loads(st.allowed_methods),
            allowed_tiers=json.loads(st.allowed_tiers),
            supported_output_formats=json.loads(st.supported_output_formats),
            active_instances=active_count,
        ))

    return AvailableServicesListResponse(items=items, total=len(items))
