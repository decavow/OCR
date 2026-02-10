# JobMessage dataclass

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class JobMessage:
    """Job message for queue."""
    job_id: str
    file_id: str
    request_id: str
    method: str
    tier: int
    output_format: str
    object_key: str
    retry_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "JobMessage":
        """Create from dictionary."""
        return cls(**data)
