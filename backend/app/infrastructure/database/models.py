# SQLAlchemy models (all tables)

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def generate_uuid() -> str:
    """Generate UUID string."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    requests: Mapped[List["Request"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Session {self.id[:8]}...>"

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(50), default="text_raw")
    tier: Mapped[int] = mapped_column(Integer, default=0)
    output_format: Mapped[str] = mapped_column(String(10), default="txt")
    retention_hours: Mapped[int] = mapped_column(Integer, default=168)
    status: Mapped[str] = mapped_column(String(20), default="PROCESSING")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    completed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="requests")
    jobs: Mapped[List["Job"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    files: Mapped[List["File"]] = relationship(back_populates="request", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_requests_user_id", "user_id"),
        Index("ix_requests_status", "status"),
        Index("ix_requests_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Request {self.id[:8]}... status={self.status}>"


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("requests.id", ondelete="CASCADE"))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    object_key: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    request: Mapped["Request"] = relationship(back_populates="files")
    job: Mapped[Optional["Job"]] = relationship(back_populates="file", uselist=False)

    # Indexes
    __table_args__ = (
        Index("ix_files_request_id", "request_id"),
    )

    def __repr__(self) -> str:
        return f"<File {self.original_name}>"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("requests.id", ondelete="CASCADE"))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="SUBMITTED")
    method: Mapped[str] = mapped_column(String(50))
    tier: Mapped[int] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_history: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    request: Mapped["Request"] = relationship(back_populates="jobs")
    file: Mapped["File"] = relationship(back_populates="job")

    # Indexes
    __table_args__ = (
        Index("ix_jobs_request_id", "request_id"),
        Index("ix_jobs_file_id", "file_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_worker_id", "worker_id"),
    )

    def __repr__(self) -> str:
        return f"<Job {self.id[:8]}... status={self.status}>"


# =============================================================================
# Service Type Status Constants
# =============================================================================

class ServiceTypeStatus:
    """Status values for service types (admin-managed)."""
    PENDING = "PENDING"      # Waiting for admin approval
    APPROVED = "APPROVED"    # Active, instances can process jobs
    DISABLED = "DISABLED"    # Temporarily paused
    REJECTED = "REJECTED"    # Permanently rejected (terminal)


class ServiceInstanceStatus:
    """Status values for service instances (system-managed)."""
    WAITING = "WAITING"       # Type not yet approved
    ACTIVE = "ACTIVE"         # Idle, ready for jobs
    PROCESSING = "PROCESSING" # Currently processing a job
    DRAINING = "DRAINING"     # Finishing current job, won't take new
    DEAD = "DEAD"             # Shutdown/disconnected


# =============================================================================
# Service Type Model (Admin-managed)
# =============================================================================

class ServiceType(Base):
    """
    Service type definition (admin-managed).

    Each type represents a category of worker (e.g., text_raw, table, handwriting).
    Admin approves/rejects/disables at this level. access_key is generated per type.
    """
    __tablename__ = "service_types"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., "ocr-text-tier0"
    display_name: Mapped[str] = mapped_column(String(200), default="")  # e.g., "Vietnamese Text OCR"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Dev description
    status: Mapped[str] = mapped_column(String(20), default=ServiceTypeStatus.PENDING)
    access_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    allowed_methods: Mapped[str] = mapped_column(Text, default='["text_raw"]')  # JSON array
    allowed_tiers: Mapped[str] = mapped_column(Text, default='[0]')  # JSON array
    engine_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON {name, version, capabilities}
    dev_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Dev email/contact
    max_instances: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    instances: Mapped[List["ServiceInstance"]] = relationship(
        back_populates="service_type",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_service_types_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ServiceType {self.id} status={self.status}>"


# =============================================================================
# Service Instance Model (System-managed)
# =============================================================================

class ServiceInstance(Base):
    """
    Service instance (system-managed).

    Each instance represents a running worker container. Auto-managed based on
    the parent service type's status. No admin approval needed per instance.
    """
    __tablename__ = "service_instances"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)  # e.g., "ocr-text-tier0-abc123"
    service_type_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("service_types.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default=ServiceInstanceStatus.WAITING)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    instance_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON {hostname, engine_version, ...}

    # Relationships
    service_type: Mapped["ServiceType"] = relationship(back_populates="instances")
    heartbeats: Mapped[List["Heartbeat"]] = relationship(
        back_populates="instance",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_service_instances_service_type_id", "service_type_id"),
        Index("ix_service_instances_status", "status"),
        Index("ix_service_instances_last_heartbeat_at", "last_heartbeat_at"),
    )

    def __repr__(self) -> str:
        return f"<ServiceInstance {self.id} status={self.status}>"


# =============================================================================
# Heartbeat Model (Updated to reference ServiceInstance)
# =============================================================================

class Heartbeat(Base):
    """Heartbeat records from service instances."""
    __tablename__ = "heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[str] = mapped_column(
        String(150),
        ForeignKey("service_instances.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="idle")  # idle, processing, error
    current_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    files_completed: Mapped[int] = mapped_column(Integer, default=0)
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    instance: Mapped["ServiceInstance"] = relationship(back_populates="heartbeats")

    # Indexes
    __table_args__ = (
        Index("ix_heartbeats_instance_id", "instance_id"),
        Index("ix_heartbeats_received_at", "received_at"),
    )

    def __repr__(self) -> str:
        return f"<Heartbeat {self.instance_id} at {self.received_at}>"


# =============================================================================
# Legacy Service Model (kept for migration compatibility)
# =============================================================================

class Service(Base):
    """
    DEPRECATED: Legacy service model.
    Kept for migration compatibility. Use ServiceType and ServiceInstance instead.
    """
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    access_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    allowed_methods: Mapped[str] = mapped_column(Text, default='["text_raw"]')  # JSON array
    allowed_tiers: Mapped[str] = mapped_column(Text, default='[0]')  # JSON array
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<Service {self.id}> [DEPRECATED]"
