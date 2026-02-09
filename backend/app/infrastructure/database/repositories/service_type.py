# ServiceTypeRepository

import json
import secrets
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import (
    ServiceType,
    ServiceTypeStatus,
    ServiceInstance,
    ServiceInstanceStatus,
)


def generate_access_key() -> str:
    """Generate a secure access key for service type."""
    return f"sk_{secrets.token_urlsafe(32)}"


class ServiceTypeRepository(BaseRepository[ServiceType]):
    """Repository for ServiceType (admin-managed) operations."""

    def __init__(self, db: Session):
        super().__init__(db, ServiceType)

    def get_by_access_key(self, access_key: str) -> Optional[ServiceType]:
        """Get service type by access key."""
        return self.db.query(ServiceType).filter(
            ServiceType.access_key == access_key
        ).first()

    def get_by_status(self, status: str) -> List[ServiceType]:
        """Get all service types with given status."""
        return self.db.query(ServiceType).filter(
            ServiceType.status == status
        ).all()

    def get_approved(self) -> List[ServiceType]:
        """Get all approved service types."""
        return self.get_by_status(ServiceTypeStatus.APPROVED)

    def get_pending(self) -> List[ServiceType]:
        """Get all pending service types."""
        return self.get_by_status(ServiceTypeStatus.PENDING)

    def create_or_update(
        self,
        type_id: str,
        display_name: str,
        description: Optional[str] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_tiers: Optional[List[int]] = None,
        engine_info: Optional[dict] = None,
        dev_contact: Optional[str] = None,
        status: str = ServiceTypeStatus.PENDING,
        access_key: Optional[str] = None,
    ) -> ServiceType:
        """
        Create new service type or update existing one.
        Used for both registration and seeding.
        """
        existing = self.get(type_id)

        if existing:
            # Update existing (but don't overwrite status/access_key unless specified)
            existing.display_name = display_name
            if description is not None:
                existing.description = description
            if allowed_methods is not None:
                existing.allowed_methods = json.dumps(allowed_methods)
            if allowed_tiers is not None:
                existing.allowed_tiers = json.dumps(allowed_tiers)
            if engine_info is not None:
                existing.engine_info = json.dumps(engine_info)
            if dev_contact is not None:
                existing.dev_contact = dev_contact
            # Only update status/access_key if explicitly provided (for seeding)
            if access_key is not None:
                existing.access_key = access_key
                existing.status = status
                if status == ServiceTypeStatus.APPROVED and not existing.approved_at:
                    existing.approved_at = datetime.now(timezone.utc)
            return self.update(existing)

        # Create new
        service_type = ServiceType(
            id=type_id,
            display_name=display_name,
            description=description,
            status=status,
            access_key=access_key,
            allowed_methods=json.dumps(allowed_methods or ["text_raw"]),
            allowed_tiers=json.dumps(allowed_tiers or [0]),
            engine_info=json.dumps(engine_info) if engine_info else None,
            dev_contact=dev_contact,
        )

        if status == ServiceTypeStatus.APPROVED:
            service_type.approved_at = datetime.now(timezone.utc)

        return self.create(service_type)

    def register(
        self,
        type_id: str,
        display_name: str,
        description: Optional[str] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_tiers: Optional[List[int]] = None,
        engine_info: Optional[dict] = None,
        dev_contact: Optional[str] = None,
    ) -> ServiceType:
        """
        Register a new service type (from worker registration).
        Creates with PENDING status, no access_key.
        """
        existing = self.get(type_id)
        if existing:
            return existing  # Don't modify existing type

        return self.create_or_update(
            type_id=type_id,
            display_name=display_name,
            description=description,
            allowed_methods=allowed_methods,
            allowed_tiers=allowed_tiers,
            engine_info=engine_info,
            dev_contact=dev_contact,
            status=ServiceTypeStatus.PENDING,
            access_key=None,
        )

    def approve(self, service_type: ServiceType, approved_by: Optional[str] = None) -> ServiceType:
        """
        Approve a service type.
        Generates access_key and sets status to APPROVED.
        """
        if service_type.status == ServiceTypeStatus.REJECTED:
            raise ValueError("Cannot approve a rejected service type")

        service_type.status = ServiceTypeStatus.APPROVED
        service_type.access_key = generate_access_key()
        service_type.approved_at = datetime.now(timezone.utc)
        service_type.approved_by = approved_by

        # Also activate all WAITING instances
        for instance in service_type.instances:
            if instance.status == ServiceInstanceStatus.WAITING:
                instance.status = ServiceInstanceStatus.ACTIVE

        return self.update(service_type)

    def reject(self, service_type: ServiceType, reason: str) -> ServiceType:
        """
        Reject a service type (terminal state).
        All instances will receive shutdown signal via heartbeat.
        """
        service_type.status = ServiceTypeStatus.REJECTED
        service_type.rejected_at = datetime.now(timezone.utc)
        service_type.rejection_reason = reason

        # Mark all instances as DEAD
        for instance in service_type.instances:
            instance.status = ServiceInstanceStatus.DEAD

        return self.update(service_type)

    def disable(self, service_type: ServiceType) -> ServiceType:
        """
        Temporarily disable a service type.
        All instances will receive drain signal via heartbeat.
        """
        if service_type.status != ServiceTypeStatus.APPROVED:
            raise ValueError("Can only disable APPROVED service types")

        service_type.status = ServiceTypeStatus.DISABLED

        # Set all active instances to DRAINING
        for instance in service_type.instances:
            if instance.status in (ServiceInstanceStatus.ACTIVE, ServiceInstanceStatus.PROCESSING):
                instance.status = ServiceInstanceStatus.DRAINING

        return self.update(service_type)

    def enable(self, service_type: ServiceType) -> ServiceType:
        """
        Re-enable a disabled service type.
        All WAITING/DRAINING instances become ACTIVE.
        """
        if service_type.status != ServiceTypeStatus.DISABLED:
            raise ValueError("Can only enable DISABLED service types")

        service_type.status = ServiceTypeStatus.APPROVED

        # Activate all WAITING or DRAINING instances
        for instance in service_type.instances:
            if instance.status in (ServiceInstanceStatus.WAITING, ServiceInstanceStatus.DRAINING):
                instance.status = ServiceInstanceStatus.ACTIVE

        return self.update(service_type)

    def can_handle(self, service_type: ServiceType, method: str, tier: int) -> bool:
        """Check if service type can handle this method and tier."""
        allowed_methods = json.loads(service_type.allowed_methods)
        allowed_tiers = json.loads(service_type.allowed_tiers)
        return method in allowed_methods and tier in allowed_tiers

    def get_instance_count(self, service_type: ServiceType) -> dict:
        """Get count of instances by status."""
        result = {}
        for instance in service_type.instances:
            result[instance.status] = result.get(instance.status, 0) + 1
        return result

    def delete_with_instances(self, service_type: ServiceType) -> None:
        """Delete service type and all its instances."""
        # Cascade delete will handle instances
        self.delete(service_type)
