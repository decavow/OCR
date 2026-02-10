# ServiceRepository

import json
from typing import Optional, List
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import Service


class ServiceRepository(BaseRepository[Service]):
    """Repository for Service (Worker registration) operations."""

    def __init__(self, db: Session):
        super().__init__(db, Service)

    def get_by_access_key(self, access_key: str) -> Optional[Service]:
        """Get enabled service by access key."""
        return self.db.query(Service).filter(
            Service.access_key == access_key,
            Service.enabled == True
        ).first()

    def get_enabled(self) -> List[Service]:
        """Get all enabled services."""
        return self.db.query(Service).filter(
            Service.enabled == True
        ).all()

    def create_service(
        self,
        service_id: str,
        access_key: str,
        allowed_methods: List[str] = None,
        allowed_tiers: List[int] = None,
    ) -> Service:
        """Create or update service."""
        existing = self.get(service_id)
        if existing:
            existing.access_key = access_key
            existing.allowed_methods = json.dumps(allowed_methods or ["text_raw"])
            existing.allowed_tiers = json.dumps(allowed_tiers or [0])
            existing.enabled = True
            return self.update(existing)

        service = Service(
            id=service_id,
            access_key=access_key,
            allowed_methods=json.dumps(allowed_methods or ["text_raw"]),
            allowed_tiers=json.dumps(allowed_tiers or [0]),
        )
        return self.create(service)

    def disable(self, service: Service) -> Service:
        """Disable service."""
        service.enabled = False
        return self.update(service)

    def enable(self, service: Service) -> Service:
        """Enable service."""
        service.enabled = True
        return self.update(service)

    def can_handle(self, service: Service, method: str, tier: int) -> bool:
        """Check if service can handle this method and tier."""
        allowed_methods = json.loads(service.allowed_methods)
        allowed_tiers = json.loads(service.allowed_tiers)
        return method in allowed_methods and tier in allowed_tiers
