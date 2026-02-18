# Registration Schemas

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ServiceRegistrationRequest(BaseModel):
    """Request payload for worker registration."""
    service_type: str           # e.g., "ocr-text-tier0"
    instance_id: str            # e.g., "ocr-text-tier0-abc123"
    display_name: str = ""      # e.g., "Vietnamese Text OCR"
    description: Optional[str] = None
    allowed_methods: List[str] = ["text_raw"]
    allowed_tiers: List[int] = [0]
    supported_output_formats: List[str] = ["txt", "json"]
    engine_info: Optional[Dict[str, Any]] = None  # {name, version, capabilities}
    dev_contact: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # {hostname, engine_version, ...}


class ServiceRegistrationResponse(BaseModel):
    """Response for worker registration."""
    instance_id: str
    instance_status: str        # WAITING, ACTIVE
    type_status: str            # PENDING, APPROVED, DISABLED
    access_key: Optional[str] = None  # Only if type already APPROVED


class ServiceDeregisterRequest(BaseModel):
    """Request payload for worker deregistration."""
    instance_id: str
