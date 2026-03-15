"""Repository integration tests — real SQLite in-memory.

Tests all repository CRUD operations, relationships, and constraints
using a real SQLite database (in-memory) instead of mocks.

Test IDs: RP-001 to RP-030
"""

import json
from datetime import datetime, timezone, timedelta

import pytest

from app.infrastructure.database.models import (
    User,
    Request,
    File,
    Job,
    ServiceType,
    ServiceInstance,
    ServiceTypeStatus,
    ServiceInstanceStatus,
)
from app.infrastructure.database.repositories import (
    UserRepository,
    SessionRepository,
    RequestRepository,
    FileRepository,
    JobRepository,
    ServiceTypeRepository,
    ServiceInstanceRepository,
    HeartbeatRepository,
    AuditLogRepository,
)


# ============================================================================
# User Repository
# ============================================================================


class TestUserRepository:
    """RP-001 to RP-005: User CRUD operations."""

    def test_rp001_create_and_get_by_email(self, db):
        """RP-001: Create user and retrieve by email."""
        repo = UserRepository(db)
        user = repo.create_user("alice@test.com", "hashed_pw")

        found = repo.get_by_email("alice@test.com")
        assert found is not None
        assert found.id == user.id
        assert found.email == "alice@test.com"

    def test_rp002_email_exists(self, db):
        """RP-002: email_exists returns True for existing, False for new."""
        repo = UserRepository(db)
        repo.create_user("bob@test.com", "hash")

        assert repo.email_exists("bob@test.com") is True
        assert repo.email_exists("nobody@test.com") is False

    def test_rp003_soft_delete_hides_user(self, db):
        """RP-003: Soft-deleted users are hidden from active queries."""
        repo = UserRepository(db)
        user = repo.create_user("charlie@test.com", "hash")
        repo.soft_delete(user)

        assert repo.get_by_email("charlie@test.com") is None
        assert repo.email_exists("charlie@test.com") is False
        assert repo.get_active(user.id) is None

    def test_rp004_count_active(self, db):
        """RP-004: Count active users with admin exclusion."""
        repo = UserRepository(db)
        u1 = repo.create_user("u1@test.com", "h")
        u2 = repo.create_user("u2@test.com", "h")
        admin = repo.create_user("admin@test.com", "h")
        admin.is_admin = True
        db.commit()

        assert repo.count_active() == 3
        assert repo.count_active(exclude_admins=True) == 2

    def test_rp005_get_all_active_paginated(self, db):
        """RP-005: Pagination returns correct subset."""
        repo = UserRepository(db)
        for i in range(5):
            repo.create_user(f"user{i}@test.com", "h")

        page1 = repo.get_all_active(skip=0, limit=3)
        page2 = repo.get_all_active(skip=3, limit=3)

        assert len(page1) == 3
        assert len(page2) == 2


# ============================================================================
# Session Repository
# ============================================================================


class TestSessionRepository:
    """RP-006 to RP-008: Session CRUD and expiry."""

    def test_rp006_create_and_get_valid(self, db):
        """RP-006: Create session and retrieve while valid."""
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)

        user = user_repo.create_user("sess@test.com", "h")
        session = session_repo.create_session(
            user_id=user.id,
            token="valid_token_123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        found = session_repo.get_valid("valid_token_123")
        assert found is not None
        assert found.user_id == user.id

    def test_rp007_expired_session_not_returned(self, db):
        """RP-007: Expired sessions are not returned by get_valid."""
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)

        user = user_repo.create_user("expired@test.com", "h")
        session_repo.create_session(
            user_id=user.id,
            token="expired_token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert session_repo.get_valid("expired_token") is None

    def test_rp008_delete_by_user(self, db):
        """RP-008: Delete all sessions for a user."""
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)

        user = user_repo.create_user("multi@test.com", "h")
        for i in range(3):
            session_repo.create_session(
                user_id=user.id,
                token=f"token_{i}",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

        deleted = session_repo.delete_by_user(user.id)
        assert deleted == 3
        assert len(session_repo.get_by_user(user.id)) == 0


# ============================================================================
# Request Repository
# ============================================================================


class TestRequestRepository:
    """RP-009 to RP-014: Request CRUD, filters, status updates."""

    def _create_user(self, db, email="req_user@test.com"):
        return UserRepository(db).create_user(email, "h")

    def test_rp009_create_and_get_active(self, db):
        """RP-009: Create request and retrieve by ID."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        request = repo.create_request(
            user_id=user.id,
            file_count=3,
            method="ocr_paddle_text",
            tier=0,
            output_format="txt",
        )

        found = repo.get_active(request.id)
        assert found is not None
        assert found.user_id == user.id
        assert found.total_files == 3
        assert found.status == "PROCESSING"

    def test_rp010_get_by_user_with_filters(self, db):
        """RP-010: Filter requests by status and method."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        r1 = repo.create_request(user_id=user.id, file_count=1, method="ocr_paddle_text")
        r2 = repo.create_request(user_id=user.id, file_count=1, method="structured_extract")
        repo.update_status(r1, "COMPLETED")

        # Filter by status
        completed = repo.get_by_user(user.id, status="COMPLETED")
        assert len(completed) == 1
        assert completed[0].id == r1.id

        # Filter by method
        struct = repo.get_by_user(user.id, method="structured_extract")
        assert len(struct) == 1

    def test_rp011_pagination(self, db):
        """RP-011: Paginated request listing."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        for _ in range(5):
            repo.create_request(user_id=user.id, file_count=1)

        assert repo.count_by_user(user.id) == 5
        page = repo.get_by_user(user.id, skip=2, limit=2)
        assert len(page) == 2

    def test_rp012_update_status_sets_completed_at(self, db):
        """RP-012: Updating to terminal status sets completed_at."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        request = repo.create_request(user_id=user.id, file_count=1)
        assert request.completed_at is None

        repo.update_status(request, "COMPLETED")
        assert request.completed_at is not None
        assert request.status == "COMPLETED"

    def test_rp013_soft_delete(self, db):
        """RP-013: Soft-deleted request hidden from active queries."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        request = repo.create_request(user_id=user.id, file_count=1)
        repo.soft_delete(request)

        assert repo.get_active(request.id) is None
        # Still accessible by raw query
        raw = db.query(Request).filter(Request.id == request.id).first()
        assert raw is not None
        assert raw.deleted_at is not None

    def test_rp014_increment_counters(self, db):
        """RP-014: Increment completed/failed counters."""
        user = self._create_user(db)
        repo = RequestRepository(db)

        request = repo.create_request(user_id=user.id, file_count=3)
        repo.increment_completed(request)
        repo.increment_completed(request)
        repo.increment_failed(request)

        assert request.completed_files == 2
        assert request.failed_files == 1


# ============================================================================
# Job Repository
# ============================================================================


class TestJobRepository:
    """RP-015 to RP-022: Job CRUD, status updates, error history, cancellation."""

    def _setup(self, db):
        user = UserRepository(db).create_user("job_user@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=1)
        f = FileRepository(db).create_file(
            request_id=req.id,
            original_name="test.png",
            mime_type="image/png",
            size_bytes=1024,
            object_key="users/u/r/f/test.png",
        )
        return user, req, f

    def test_rp015_create_job_default_status(self, db):
        """RP-015: New job starts with SUBMITTED status."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        assert job.status == "SUBMITTED"
        assert job.retry_count == 0
        assert job.max_retries == 3

    def test_rp016_update_to_processing_sets_started_at(self, db):
        """RP-016: PROCESSING status sets started_at timestamp."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        repo.update_status(job, status="QUEUED")
        assert job.started_at is None

        repo.update_status(job, status="PROCESSING", worker_id="worker-1")
        assert job.started_at is not None
        assert job.worker_id == "worker-1"

    def test_rp017_update_to_completed_sets_processing_time(self, db):
        """RP-017: COMPLETED status calculates processing_time_ms."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        repo.update_status(job, status="QUEUED")
        repo.update_status(job, status="PROCESSING")
        repo.update_status(job, status="COMPLETED", engine_version="paddle 2.7")

        assert job.completed_at is not None
        assert job.processing_time_ms is not None
        assert job.processing_time_ms >= 0
        assert job.engine_version == "paddle 2.7"

    def test_rp018_error_history_appended(self, db):
        """RP-018: Error adds entry to error_history JSON array."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        repo.update_status(job, status="QUEUED")
        repo.update_status(job, status="PROCESSING")
        repo.update_status(
            job, status="FAILED", error="Timeout after 30s", retriable=True
        )

        history = json.loads(job.error_history)
        assert len(history) == 1
        assert history[0]["error"] == "Timeout after 30s"
        assert history[0]["retriable"] is True

    def test_rp019_get_by_request(self, db):
        """RP-019: Get all jobs for a request."""
        user = UserRepository(db).create_user("multi@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=3)
        file_repo = FileRepository(db)
        job_repo = JobRepository(db)

        for i in range(3):
            f = file_repo.create_file(
                request_id=req.id,
                original_name=f"f{i}.png",
                mime_type="image/png",
                size_bytes=100,
                object_key=f"k{i}",
            )
            job_repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)

        jobs = job_repo.get_by_request(req.id)
        assert len(jobs) == 3

    def test_rp020_cancel_queued_jobs(self, db):
        """RP-020: Cancel only QUEUED jobs, skip others."""
        user = UserRepository(db).create_user("cancel@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=3)
        file_repo = FileRepository(db)
        job_repo = JobRepository(db)

        jobs = []
        for i in range(3):
            f = file_repo.create_file(
                request_id=req.id,
                original_name=f"f{i}.png",
                mime_type="image/png",
                size_bytes=100,
                object_key=f"k{i}",
            )
            j = job_repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
            jobs.append(j)

        # Move first two to QUEUED, third to PROCESSING
        job_repo.update_status(jobs[0], status="QUEUED")
        job_repo.update_status(jobs[1], status="QUEUED")
        job_repo.update_status(jobs[2], status="QUEUED")
        job_repo.update_status(jobs[2], status="PROCESSING")

        queued = job_repo.get_queued_by_request(req.id)
        cancelled = job_repo.cancel_jobs(queued)
        assert cancelled == 2

        db.refresh(jobs[2])
        assert jobs[2].status == "PROCESSING"  # not cancelled

    def test_rp021_get_processing_by_worker(self, db):
        """RP-021: Find jobs currently processed by a specific worker."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        repo.update_status(job, status="QUEUED")
        repo.update_status(job, status="PROCESSING", worker_id="worker-abc")

        found = repo.get_processing_by_worker("worker-abc")
        assert len(found) == 1
        assert found[0].id == job.id

    def test_rp022_increment_retry(self, db):
        """RP-022: Increment retry count."""
        _, req, f = self._setup(db)
        repo = JobRepository(db)

        job = repo.create_job(request_id=req.id, file_id=f.id, method="ocr_paddle_text", tier=0)
        assert job.retry_count == 0

        repo.increment_retry(job)
        assert job.retry_count == 1

        repo.increment_retry(job)
        assert job.retry_count == 2


# ============================================================================
# File Repository
# ============================================================================


class TestFileRepository:
    """RP-023 to RP-025: File CRUD operations."""

    def test_rp023_create_and_get_by_request(self, db):
        """RP-023: Create files and retrieve by request."""
        user = UserRepository(db).create_user("file@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=2)
        repo = FileRepository(db)

        f1 = repo.create_file(req.id, "a.png", "image/png", 100, "k1")
        f2 = repo.create_file(req.id, "b.pdf", "application/pdf", 200, "k2")

        files = repo.get_by_request(req.id)
        assert len(files) == 2

    def test_rp024_soft_delete_file(self, db):
        """RP-024: Soft-deleted file hidden from active queries."""
        user = UserRepository(db).create_user("fdel@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=1)
        repo = FileRepository(db)

        f = repo.create_file(req.id, "del.png", "image/png", 100, "k")
        repo.soft_delete(f)

        assert repo.get_active(f.id) is None
        # Include deleted
        all_files = repo.get_by_request_include_deleted(req.id)
        assert len(all_files) == 1

    def test_rp025_total_size_by_request(self, db):
        """RP-025: Sum file sizes for a request."""
        user = UserRepository(db).create_user("size@test.com", "h")
        req = RequestRepository(db).create_request(user_id=user.id, file_count=2)
        repo = FileRepository(db)

        repo.create_file(req.id, "a.png", "image/png", 1000, "k1")
        repo.create_file(req.id, "b.png", "image/png", 2000, "k2")

        assert repo.get_total_size_by_request(req.id) == 3000


# ============================================================================
# Service Type & Instance Repository
# ============================================================================


class TestServiceTypeRepository:
    """RP-026 to RP-030: Service type lifecycle."""

    def test_rp026_register_pending(self, db):
        """RP-026: Register new service type starts as PENDING."""
        repo = ServiceTypeRepository(db)

        st = repo.register(
            type_id="ocr-new",
            display_name="New OCR",
            allowed_methods=["ocr_paddle_text"],
            allowed_tiers=[0],
        )

        assert st.status == ServiceTypeStatus.PENDING
        assert st.access_key is None

    def test_rp027_approve_generates_key(self, db):
        """RP-027: Approving generates access_key and activates instances."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.register(type_id="ocr-approve", display_name="Approve Test")
        inst = inst_repo.register(instance_id="inst-1", service_type=st)
        assert inst.status == ServiceInstanceStatus.WAITING

        type_repo.approve(st, approved_by="admin@test.com")

        assert st.status == ServiceTypeStatus.APPROVED
        assert st.access_key is not None
        assert st.access_key.startswith("sk_")
        assert st.approved_by == "admin@test.com"

        db.refresh(inst)
        assert inst.status == ServiceInstanceStatus.ACTIVE

    def test_rp028_reject_terminal(self, db):
        """RP-028: Reject marks type as REJECTED and instances as DEAD."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.register(type_id="ocr-reject", display_name="Reject Test")
        inst = inst_repo.register(instance_id="inst-r1", service_type=st)

        type_repo.reject(st, reason="Security concern")

        assert st.status == ServiceTypeStatus.REJECTED
        assert st.rejection_reason == "Security concern"

        db.refresh(inst)
        assert inst.status == ServiceInstanceStatus.DEAD

    def test_rp029_disable_enable_cycle(self, db):
        """RP-029: Disable sets DRAINING, enable re-activates."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.create_or_update(
            type_id="ocr-cycle", display_name="Cycle Test",
            status=ServiceTypeStatus.APPROVED, access_key="sk_cycle",
        )
        inst = inst_repo.register(instance_id="inst-c1", service_type=st)
        assert inst.status == ServiceInstanceStatus.ACTIVE

        # Disable
        type_repo.disable(st)
        assert st.status == ServiceTypeStatus.DISABLED
        db.refresh(inst)
        assert inst.status == ServiceInstanceStatus.DRAINING

        # Enable
        type_repo.enable(st)
        assert st.status == ServiceTypeStatus.APPROVED
        db.refresh(inst)
        assert inst.status == ServiceInstanceStatus.ACTIVE

    def test_rp030_can_handle_method_tier(self, db):
        """RP-030: can_handle checks method and tier support."""
        repo = ServiceTypeRepository(db)

        st = repo.create_or_update(
            type_id="ocr-handle",
            display_name="Handle Test",
            allowed_methods=["ocr_paddle_text", "structured_extract"],
            allowed_tiers=[0, 1],
        )

        assert repo.can_handle(st, "ocr_paddle_text", 0) is True
        assert repo.can_handle(st, "structured_extract", 1) is True
        assert repo.can_handle(st, "ocr_table", 0) is False
        assert repo.can_handle(st, "ocr_paddle_text", 2) is False


class TestServiceInstanceRepository:
    """RP-031 to RP-033: Service instance operations."""

    def test_rp031_register_for_approved_type(self, db):
        """RP-031: Instance for APPROVED type starts ACTIVE."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.create_or_update(
            type_id="ocr-active", display_name="Active",
            status=ServiceTypeStatus.APPROVED, access_key="sk_active",
        )

        inst = inst_repo.register(instance_id="inst-a1", service_type=st)
        assert inst.status == ServiceInstanceStatus.ACTIVE

    def test_rp032_register_for_pending_type(self, db):
        """RP-032: Instance for PENDING type starts WAITING."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.register(type_id="ocr-pending", display_name="Pending")

        inst = inst_repo.register(instance_id="inst-p1", service_type=st)
        assert inst.status == ServiceInstanceStatus.WAITING

    def test_rp033_stale_instance_detection(self, db):
        """RP-033: Detect instances with old heartbeats."""
        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.create_or_update(
            type_id="ocr-stale", display_name="Stale",
            status=ServiceTypeStatus.APPROVED, access_key="sk_stale",
        )

        inst = inst_repo.register(instance_id="inst-s1", service_type=st)
        # Simulate old heartbeat
        inst.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        db.commit()

        stale = inst_repo.get_stale_instances(timeout_seconds=90)
        assert len(stale) == 1
        assert stale[0].id == "inst-s1"


# ============================================================================
# Cascade Delete
# ============================================================================


class TestCascadeDelete:
    """RP-034: Cascade delete from request to files and jobs."""

    def test_rp034_hard_delete_request_cascades(self, db):
        """RP-034: Hard delete request removes files and jobs."""
        user = UserRepository(db).create_user("cascade@test.com", "h")
        req_repo = RequestRepository(db)
        file_repo = FileRepository(db)
        job_repo = JobRepository(db)

        req = req_repo.create_request(user_id=user.id, file_count=2)
        f1 = file_repo.create_file(req.id, "a.png", "image/png", 100, "k1")
        f2 = file_repo.create_file(req.id, "b.png", "image/png", 200, "k2")
        j1 = job_repo.create_job(req.id, f1.id, "ocr_paddle_text", 0)
        j2 = job_repo.create_job(req.id, f2.id, "ocr_paddle_text", 0)

        # Hard delete request
        req_repo.hard_delete(req)

        # Files and jobs should be gone
        assert file_repo.get_active(f1.id) is None
        assert file_repo.get_active(f2.id) is None
        assert job_repo.get_active(j1.id) is None
        assert job_repo.get_active(j2.id) is None


# ============================================================================
# Audit Log
# ============================================================================


class TestAuditLogRepository:
    """RP-035: Audit log recording and querying."""

    def test_rp035_record_and_query(self, db):
        """RP-035: Record audit entries and query by entity."""
        repo = AuditLogRepository(db)

        repo.record(
            actor_email="admin@test.com",
            action="APPROVE",
            entity_type="service_type",
            entity_id="ocr-text",
            details=json.dumps({"reason": "approved"}),
        )
        repo.record(
            actor_email="admin@test.com",
            action="REJECT",
            entity_type="service_type",
            entity_id="ocr-bad",
        )

        logs = repo.query_by_entity("service_type", "ocr-text")
        assert len(logs) == 1
        assert logs[0].action == "APPROVE"

        recent = repo.query_recent(limit=10)
        assert len(recent) == 2
