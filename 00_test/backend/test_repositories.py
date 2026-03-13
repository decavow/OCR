"""
Test cases for Repository Layer (RP-001 to RP-028)

Integration test with in-memory SQLite.
Covers CRUD operations for all repositories.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to path for direct imports
backend_path = Path(__file__).parent.parent.parent / "02_backend"
sys.path.insert(0, str(backend_path))

# Mock app.config and app.core.logging before importing any app modules
mock_settings = MagicMock()
mock_settings.database_url = "sqlite:///:memory:"
sys.modules["app.config"] = MagicMock(settings=mock_settings)
sys.modules["app.core.logging"] = MagicMock(get_logger=MagicMock(return_value=MagicMock()))

from app.infrastructure.database.models import (
    Base, User, Session as SessionModel, Request, File, Job,
    ServiceType, ServiceTypeStatus, ServiceInstance, ServiceInstanceStatus,
    Heartbeat, AuditLog,
)
from app.infrastructure.database.repositories.user import UserRepository
from app.infrastructure.database.repositories.session import SessionRepository
from app.infrastructure.database.repositories.request import RequestRepository
from app.infrastructure.database.repositories.file import FileRepository
from app.infrastructure.database.repositories.job import JobRepository
from app.infrastructure.database.repositories.heartbeat import HeartbeatRepository
from app.infrastructure.database.repositories.service_instance import ServiceInstanceRepository
from app.infrastructure.database.repositories.service_type import ServiceTypeRepository
from app.infrastructure.database.repositories.service import ServiceRepository
from app.infrastructure.database.repositories.audit_log import AuditLogRepository
from app.infrastructure.database.repositories.base import BaseRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite DB with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ===== Helper: create prerequisite records =====

def create_user(db_session, email="test@example.com") -> User:
    repo = UserRepository(db_session)
    return repo.create_user(email=email, password_hash="hashed_pw")


def create_request(db_session, user_id: str, **kwargs) -> Request:
    repo = RequestRepository(db_session)
    return repo.create_request(user_id=user_id, file_count=1, **kwargs)


def create_file(db_session, request_id: str, **kwargs) -> File:
    repo = FileRepository(db_session)
    return repo.create_file(
        request_id=request_id,
        original_name=kwargs.get("original_name", "test.png"),
        mime_type=kwargs.get("mime_type", "image/png"),
        size_bytes=kwargs.get("size_bytes", 1024),
        object_key=kwargs.get("object_key", f"u/r/{request_id}/test.png"),
        file_id=kwargs.get("file_id", None),
    )


def create_job(db_session, request_id: str, file_id: str, **kwargs) -> Job:
    repo = JobRepository(db_session)
    return repo.create_job(
        request_id=request_id,
        file_id=file_id,
        method=kwargs.get("method", "ocr_text_raw"),
        tier=kwargs.get("tier", 0),
        job_id=kwargs.get("job_id", None),
    )


def create_service_type(db_session, type_id="ocr-text-tier0", **kwargs) -> ServiceType:
    repo = ServiceTypeRepository(db_session)
    return repo.create_or_update(
        type_id=type_id,
        display_name=kwargs.get("display_name", "Test OCR"),
        status=kwargs.get("status", ServiceTypeStatus.APPROVED),
        access_key=kwargs.get("access_key", "sk_test_key"),
    )


# ===== RP-001 to RP-002: UserRepository =====

class TestUserRepository:
    def test_create_user_and_get_by_email(self, db_session):
        """RP-001: Create user, find by email."""
        repo = UserRepository(db_session)
        user = repo.create_user("alice@test.com", "hash123")
        found = repo.get_by_email("alice@test.com")
        assert found is not None
        assert found.email == "alice@test.com"
        assert found.id == user.id

    def test_get_by_email_nonexistent(self, db_session):
        """RP-002: Non-existent email returns None."""
        repo = UserRepository(db_session)
        assert repo.get_by_email("ghost@test.com") is None

    def test_email_exists(self, db_session):
        repo = UserRepository(db_session)
        repo.create_user("bob@test.com", "hash")
        assert repo.email_exists("bob@test.com") is True
        assert repo.email_exists("nobody@test.com") is False


# ===== RP-003 to RP-004: SessionRepository =====

class TestSessionRepository:
    def test_create_and_get_valid_session(self, db_session):
        """RP-003: Create session, find by valid token."""
        user = create_user(db_session, "sess_user@test.com")
        repo = SessionRepository(db_session)
        session = repo.create_session(
            user_id=user.id,
            token="valid-token-123",
            expires_hours=24,
        )
        found = repo.get_valid("valid-token-123")
        assert found is not None
        assert found.user_id == user.id

    def test_get_valid_expired_session(self, db_session):
        """RP-004: Expired session returns None."""
        user = create_user(db_session, "expired_user@test.com")
        repo = SessionRepository(db_session)
        # Create an already-expired session
        repo.create_session(
            user_id=user.id,
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert repo.get_valid("expired-token") is None


# ===== RP-005 to RP-010: RequestRepository =====

class TestRequestRepository:
    def test_create_and_get_active(self, db_session):
        """RP-005: Create request, find by get_active."""
        user = create_user(db_session, "req_user@test.com")
        req = create_request(db_session, user.id)
        repo = RequestRepository(db_session)
        found = repo.get_active(req.id)
        assert found is not None
        assert found.user_id == user.id
        assert found.status == "PROCESSING"

    def test_get_by_user_with_pagination(self, db_session):
        """RP-006: Pagination returns correct slice."""
        user = create_user(db_session, "pag_user@test.com")
        repo = RequestRepository(db_session)
        for _ in range(5):
            create_request(db_session, user.id)
        page = repo.get_by_user(user.id, skip=1, limit=2)
        assert len(page) == 2

    def test_get_expired_finds_only_expired(self, db_session):
        """RP-007: Only expired requests returned."""
        user = create_user(db_session, "exp_user@test.com")
        repo = RequestRepository(db_session)
        # Create expired request
        r1 = repo.create_request(
            user_id=user.id, file_count=1,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        # Create non-expired request
        r2 = repo.create_request(
            user_id=user.id, file_count=1,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        expired = repo.get_expired()
        expired_ids = [r.id for r in expired]
        assert r1.id in expired_ids
        assert r2.id not in expired_ids

    def test_soft_delete_and_get_soft_deleted_before(self, db_session):
        """RP-008: Soft-deleted found by cutoff."""
        user = create_user(db_session, "sd_user@test.com")
        repo = RequestRepository(db_session)
        req = create_request(db_session, user.id)
        repo.soft_delete(req)
        # cutoff in the future should find it
        cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
        found = repo.get_soft_deleted_before(cutoff)
        assert any(r.id == req.id for r in found)

    def test_hard_delete_removes_from_db(self, db_session):
        """RP-009: Hard delete removes from DB."""
        user = create_user(db_session, "hd_user@test.com")
        repo = RequestRepository(db_session)
        req = create_request(db_session, user.id)
        req_id = req.id
        repo.hard_delete(req)
        assert repo.get(req_id) is None

    def test_increment_completed_and_failed(self, db_session):
        """RP-010: Counters update correctly."""
        user = create_user(db_session, "cnt_user@test.com")
        repo = RequestRepository(db_session)
        req = create_request(db_session, user.id)
        assert req.completed_files == 0
        assert req.failed_files == 0
        repo.increment_completed(req)
        repo.increment_completed(req)
        repo.increment_failed(req)
        assert req.completed_files == 2
        assert req.failed_files == 1


# ===== RP-011 to RP-017: JobRepository =====

class TestJobRepository:
    def _setup(self, db_session):
        user = create_user(db_session, f"job_{id(db_session)}@test.com")
        req = create_request(db_session, user.id)
        f = create_file(db_session, req.id)
        return user, req, f

    def test_create_and_get_active(self, db_session):
        """RP-011: Job created and findable."""
        _, req, f = self._setup(db_session)
        repo = JobRepository(db_session)
        job = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        found = repo.get_active(job.id)
        assert found is not None
        assert found.request_id == req.id
        assert found.status == "SUBMITTED"

    def test_get_by_request_returns_all(self, db_session):
        """RP-012: get_by_request returns correct count."""
        _, req, f = self._setup(db_session)
        f2 = create_file(db_session, req.id, original_name="test2.png",
                         object_key=f"u/r/{req.id}/test2.png")
        repo = JobRepository(db_session)
        repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        repo.create_job(req.id, f2.id, "ocr_text_raw", 0)
        jobs = repo.get_by_request(req.id)
        assert len(jobs) == 2

    def test_get_by_status_filters(self, db_session):
        """RP-013: Only matching status returned."""
        _, req, f = self._setup(db_session)
        repo = JobRepository(db_session)
        job = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        repo.update_status(job, "PROCESSING")
        submitted = repo.get_by_status("SUBMITTED")
        processing = repo.get_by_status("PROCESSING")
        assert all(j.status == "PROCESSING" for j in processing)
        assert job.id not in [j.id for j in submitted]

    def test_get_queued_by_request(self, db_session):
        """RP-014: Only QUEUED jobs returned."""
        _, req, f = self._setup(db_session)
        f2 = create_file(db_session, req.id, original_name="q2.png",
                         object_key=f"u/r/{req.id}/q2.png")
        repo = JobRepository(db_session)
        j1 = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        j2 = repo.create_job(req.id, f2.id, "ocr_text_raw", 0)
        repo.update_status(j1, "QUEUED")
        # j2 stays as SUBMITTED
        queued = repo.get_queued_by_request(req.id)
        assert len(queued) == 1
        assert queued[0].id == j1.id

    def test_update_status(self, db_session):
        """RP-015: Status updated."""
        _, req, f = self._setup(db_session)
        repo = JobRepository(db_session)
        job = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        repo.update_status(job, "PROCESSING")
        assert job.status == "PROCESSING"

    def test_cancel_jobs(self, db_session):
        """RP-016: Cancel returns correct count."""
        _, req, f = self._setup(db_session)
        f2 = create_file(db_session, req.id, original_name="c2.png",
                         object_key=f"u/r/{req.id}/c2.png")
        repo = JobRepository(db_session)
        j1 = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        j2 = repo.create_job(req.id, f2.id, "ocr_text_raw", 0)
        repo.update_status(j1, "QUEUED")
        repo.update_status(j2, "QUEUED")
        count = repo.cancel_jobs([j1, j2])
        assert count == 2
        assert j1.status == "CANCELLED"
        assert j2.status == "CANCELLED"

    def test_increment_retry(self, db_session):
        """RP-017: retry_count incremented."""
        _, req, f = self._setup(db_session)
        repo = JobRepository(db_session)
        job = repo.create_job(req.id, f.id, "ocr_text_raw", 0)
        assert job.retry_count == 0
        repo.increment_retry(job)
        assert job.retry_count == 1
        repo.increment_retry(job)
        assert job.retry_count == 2


# ===== RP-018 to RP-020: FileRepository =====

class TestFileRepository:
    def test_create_and_get_active(self, db_session):
        """RP-018: File created and findable."""
        user = create_user(db_session, "file_user@test.com")
        req = create_request(db_session, user.id)
        repo = FileRepository(db_session)
        f = repo.create_file(req.id, "doc.png", "image/png", 2048, "key/doc.png")
        found = repo.get_active(f.id)
        assert found is not None
        assert found.original_name == "doc.png"

    def test_soft_delete_hides_from_get_active(self, db_session):
        """RP-019: Soft delete makes get_active return None."""
        user = create_user(db_session, "fsd_user@test.com")
        req = create_request(db_session, user.id)
        repo = FileRepository(db_session)
        f = repo.create_file(req.id, "del.png", "image/png", 1024, "key/del.png")
        repo.soft_delete(f)
        assert repo.get_active(f.id) is None

    def test_get_by_request_include_deleted(self, db_session):
        """RP-020: Returns even deleted files."""
        user = create_user(db_session, "fid_user@test.com")
        req = create_request(db_session, user.id)
        repo = FileRepository(db_session)
        f1 = repo.create_file(req.id, "a.png", "image/png", 100, "key/a.png")
        f2 = repo.create_file(req.id, "b.png", "image/png", 200, "key/b.png")
        repo.soft_delete(f1)
        # get_by_request_include_deleted should return both
        all_files = repo.get_by_request_include_deleted(req.id)
        assert len(all_files) == 2
        # get_by_request should return only active
        active_files = repo.get_by_request(req.id)
        assert len(active_files) == 1


# ===== RP-021 to RP-022: ServiceTypeRepository =====

class TestServiceTypeRepository:
    def test_get_approved_filters_by_status(self, db_session):
        """RP-021: Only APPROVED returned."""
        repo = ServiceTypeRepository(db_session)
        repo.create_or_update("type-a", "Type A", status=ServiceTypeStatus.APPROVED, access_key="sk_a")
        repo.create_or_update("type-b", "Type B", status=ServiceTypeStatus.PENDING)
        approved = repo.get_approved()
        assert len(approved) == 1
        assert approved[0].id == "type-a"

    def test_can_handle_checks_method_and_tier(self, db_session):
        """RP-022: True/False based on config."""
        repo = ServiceTypeRepository(db_session)
        st = repo.create_or_update(
            "type-c", "Type C",
            allowed_methods=["ocr_text_raw"],
            allowed_tiers=[0, 1],
            status=ServiceTypeStatus.APPROVED,
            access_key="sk_c",
        )
        assert repo.can_handle(st, "ocr_text_raw", 0) is True
        assert repo.can_handle(st, "ocr_text_raw", 1) is True
        assert repo.can_handle(st, "ocr_text_raw", 2) is False
        assert repo.can_handle(st, "handwriting", 0) is False


# ===== RP-023 to RP-024: ServiceInstanceRepository =====

class TestServiceInstanceRepository:
    def test_get_stale_instances(self, db_session):
        """RP-023: Returns stale instances."""
        st = create_service_type(db_session, "svc-stale")
        repo = ServiceInstanceRepository(db_session)
        instance = repo.register("inst-1", st)
        # Manually make it stale
        instance.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=200)
        db_session.commit()
        stale = repo.get_stale_instances(timeout_seconds=90)
        assert any(i.id == "inst-1" for i in stale)

    def test_mark_dead_changes_status(self, db_session):
        """RP-024: Status = DEAD."""
        st = create_service_type(db_session, "svc-dead")
        repo = ServiceInstanceRepository(db_session)
        instance = repo.register("inst-dead", st)
        repo.mark_dead(instance)
        assert instance.status == ServiceInstanceStatus.DEAD


# ===== RP-025 to RP-026: HeartbeatRepository =====

class TestHeartbeatRepository:
    def test_create_and_get_latest(self, db_session):
        """RP-025: Latest heartbeat returned."""
        st = create_service_type(db_session, "svc-hb")
        inst_repo = ServiceInstanceRepository(db_session)
        instance = inst_repo.register("hb-inst-1", st)

        repo = HeartbeatRepository(db_session)
        repo.upsert("hb-inst-1", "idle")
        repo.upsert("hb-inst-1", "processing", current_job_id="j-1")

        latest = repo.get_latest_by_instance("hb-inst-1")
        assert latest is not None
        assert latest.status == "processing"
        assert latest.current_job_id == "j-1"

    def test_cleanup_old_removes_old_records(self, db_session):
        """RP-026: Returns count deleted."""
        st = create_service_type(db_session, "svc-hb-clean")
        inst_repo = ServiceInstanceRepository(db_session)
        instance = inst_repo.register("hb-clean-inst", st)

        repo = HeartbeatRepository(db_session)
        hb = repo.upsert("hb-clean-inst", "idle")
        # Make it old
        hb.received_at = datetime.now(timezone.utc) - timedelta(hours=48)
        db_session.commit()

        deleted = repo.cleanup_old(keep_hours=24)
        assert deleted >= 1


# ===== RP-027: AuditLogRepository =====

class TestAuditLogRepository:
    def test_log_action_creates_entry(self, db_session):
        """RP-027: Entry created with all fields."""
        repo = AuditLogRepository(db_session)
        entry = repo.record(
            actor_email="admin@test.com",
            action="APPROVE",
            entity_type="service_type",
            entity_id="ocr-text",
            details={"key": "value"},
            request_id="req-123",
        )
        assert entry.id is not None
        assert entry.actor_email == "admin@test.com"
        assert entry.action == "APPROVE"
        assert entry.entity_type == "service_type"
        assert entry.entity_id == "ocr-text"
        assert entry.timestamp is not None
        parsed = json.loads(entry.details)
        assert parsed["key"] == "value"
        assert entry.request_id == "req-123"


# ===== RP-028: BaseRepository =====

class TestBaseRepository:
    def test_crud_operations(self, db_session):
        """RP-028: get, get_all, create, update, delete."""
        repo = UserRepository(db_session)
        # Create
        user = repo.create_user("crud@test.com", "hash")
        assert user.id is not None
        # Get
        found = repo.get(user.id)
        assert found.email == "crud@test.com"
        # Get All
        all_users = repo.get_all()
        assert len(all_users) >= 1
        # Update
        user.is_admin = True
        updated = repo.update(user)
        assert updated.is_admin is True
        # Delete
        repo.delete(user)
        assert repo.get(user.id) is None

    def test_count(self, db_session):
        repo = UserRepository(db_session)
        initial = repo.count()
        repo.create_user("count1@test.com", "h")
        repo.create_user("count2@test.com", "h")
        assert repo.count() == initial + 2
