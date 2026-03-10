# ServiceInstanceRepository

import json
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import (
    ServiceInstance,
    ServiceInstanceStatus,
    ServiceType,
    ServiceTypeStatus,
)


class ServiceInstanceRepository(BaseRepository[ServiceInstance]):
    """Repository for ServiceInstance (system-managed) operations."""

    def __init__(self, db: Session):
        super().__init__(db, ServiceInstance)

    def get_by_type(self, type_id: str) -> List[ServiceInstance]:
        """Get all instances for a service type."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.service_type_id == type_id
        ).all()

    def get_by_status(self, status: str) -> List[ServiceInstance]:
        """Get all instances with given status."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.status == status
        ).all()

    def get_active(self) -> List[ServiceInstance]:
        """Get all active instances."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.status.in_([
                ServiceInstanceStatus.ACTIVE,
                ServiceInstanceStatus.PROCESSING,
            ])
        ).all()

    def get_by_type_and_status(self, type_id: str, status: str) -> List[ServiceInstance]:
        """Get instances for a type with given status."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.service_type_id == type_id,
            ServiceInstance.status == status,
        ).all()

    def register(
        self,
        instance_id: str,
        service_type: ServiceType,
        metadata: Optional[dict] = None,
    ) -> ServiceInstance:
        """
        Register a new service instance.
        Status depends on the parent service type's status.
        """
        existing = self.get(instance_id)
        if existing:
            existing.last_heartbeat_at = datetime.now(timezone.utc)
            if metadata:
                existing.instance_metadata = json.dumps(metadata)
            # Re-activation: if type is APPROVED, a re-registering instance should become ACTIVE
            # (handles case where instance was marked DEAD by heartbeat monitor)
            if service_type.status == ServiceTypeStatus.APPROVED:
                if existing.status in (ServiceInstanceStatus.DEAD, ServiceInstanceStatus.WAITING):
                    existing.status = ServiceInstanceStatus.ACTIVE
            return self.update(existing)

        # Determine initial status based on type status
        if service_type.status == ServiceTypeStatus.APPROVED:
            initial_status = ServiceInstanceStatus.ACTIVE
        elif service_type.status == ServiceTypeStatus.REJECTED:
            raise ValueError("Cannot register instance for rejected service type")
        else:
            initial_status = ServiceInstanceStatus.WAITING

        instance = ServiceInstance(
            id=instance_id,
            service_type_id=service_type.id,
            status=initial_status,
            instance_metadata=json.dumps(metadata) if metadata else None,
        )

        return self.create(instance)

    def update_heartbeat(
        self,
        instance: ServiceInstance,
        status: Optional[str] = None,
        current_job_id: Optional[str] = None,
    ) -> ServiceInstance:
        """Update instance heartbeat data."""
        instance.last_heartbeat_at = datetime.now(timezone.utc)

        if status:
            # Map worker status to instance status
            if status == "processing":
                instance.status = ServiceInstanceStatus.PROCESSING
            elif status == "idle" and instance.status == ServiceInstanceStatus.PROCESSING:
                instance.status = ServiceInstanceStatus.ACTIVE

        instance.current_job_id = current_job_id

        return self.update(instance)

    def mark_processing(self, instance: ServiceInstance, job_id: str) -> ServiceInstance:
        """Mark instance as processing a job."""
        instance.status = ServiceInstanceStatus.PROCESSING
        instance.current_job_id = job_id
        instance.last_heartbeat_at = datetime.now(timezone.utc)
        return self.update(instance)

    def mark_idle(self, instance: ServiceInstance) -> ServiceInstance:
        """Mark instance as idle (finished processing)."""
        if instance.status == ServiceInstanceStatus.DRAINING:
            # If draining, go to WAITING after finishing job
            instance.status = ServiceInstanceStatus.WAITING
        else:
            instance.status = ServiceInstanceStatus.ACTIVE
        instance.current_job_id = None
        instance.last_heartbeat_at = datetime.now(timezone.utc)
        return self.update(instance)

    def mark_draining(self, instance: ServiceInstance) -> ServiceInstance:
        """Mark instance as draining (will finish current job then stop)."""
        instance.status = ServiceInstanceStatus.DRAINING
        return self.update(instance)

    def mark_dead(self, instance: ServiceInstance) -> ServiceInstance:
        """Mark instance as dead (disconnected/shutdown)."""
        instance.status = ServiceInstanceStatus.DEAD
        instance.current_job_id = None
        return self.update(instance)

    def activate(self, instance: ServiceInstance) -> ServiceInstance:
        """Activate a waiting instance."""
        if instance.status in (ServiceInstanceStatus.WAITING, ServiceInstanceStatus.DRAINING):
            instance.status = ServiceInstanceStatus.ACTIVE
            instance.last_heartbeat_at = datetime.now(timezone.utc)
            return self.update(instance)
        return instance

    def delete_by_type(self, type_id: str) -> int:
        """Delete all instances for a service type. Returns count deleted."""
        count = self.db.query(ServiceInstance).filter(
            ServiceInstance.service_type_id == type_id
        ).delete()
        self.db.commit()
        return count

    def count_by_type(self, type_id: str) -> int:
        """Count instances for a service type."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.service_type_id == type_id
        ).count()

    def count_active_by_type(self, type_id: str) -> int:
        """Count active instances for a service type."""
        return self.db.query(ServiceInstance).filter(
            ServiceInstance.service_type_id == type_id,
            ServiceInstance.status.in_([
                ServiceInstanceStatus.ACTIVE,
                ServiceInstanceStatus.PROCESSING,
            ])
        ).count()

    def get_stale_instances(self, timeout_seconds: int = 90) -> List[ServiceInstance]:
        """Get instances that haven't sent heartbeat within timeout."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)

        return self.db.query(ServiceInstance).filter(
            ServiceInstance.last_heartbeat_at < cutoff,
            ServiceInstance.status.in_([
                ServiceInstanceStatus.ACTIVE,
                ServiceInstanceStatus.PROCESSING,
                ServiceInstanceStatus.DRAINING,
            ])
        ).all()

    def deregister(self, instance_id: str) -> bool:
        """Deregister an instance (mark as DEAD and optionally delete)."""
        instance = self.get(instance_id)
        if not instance:
            return False

        instance.status = ServiceInstanceStatus.DEAD
        instance.current_job_id = None
        self.update(instance)
        return True
