"""Internal API integration tests — worker registration, heartbeat, job status.

Tests the internal endpoints used by OCR workers through FastAPI TestClient
with real SQLite database. Uses API calls for setup to avoid session isolation issues.

Test IDs: II-001 to II-015
"""

import pytest

from helpers import (
    register_and_get_token,
    auth_header,
)


# ============================================================================
# Worker Registration
# ============================================================================


class TestWorkerRegistration:
    """II-001 to II-004: POST /internal/register"""

    def test_ii001_register_new_type_pending(self, client):
        """II-001: Registering with unknown type creates PENDING type + WAITING instance."""
        resp = client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-brand-new",
                "instance_id": "inst-new-001",
                "display_name": "Brand New OCR",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["instance_id"] == "inst-new-001"
        assert data["type_status"] == "PENDING"
        assert data["instance_status"] == "WAITING"
        assert data["access_key"] is None

    def test_ii002_register_approved_type_active(self, client, db):
        """II-002: Registering with APPROVED type returns ACTIVE + access_key."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        # Create approved type directly in DB via the db fixture
        repo = ServiceTypeRepository(db)
        repo.create_or_update(
            type_id="ocr-approved",
            display_name="Approved OCR",
            allowed_methods=["ocr_paddle_text"],
            allowed_tiers=[0],
            status="APPROVED",
            access_key="sk_approved_test_key",
        )

        resp = client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-approved",
                "instance_id": "inst-approved-001",
                "display_name": "Approved Worker",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        assert resp.status_code == 200
        result = resp.json()
        assert result["type_status"] == "APPROVED"
        assert result["instance_status"] == "ACTIVE"
        assert result["access_key"] == "sk_approved_test_key"

    def test_ii003_register_rejected_type_403(self, client, db):
        """II-003: Registering with REJECTED type returns 403."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        repo = ServiceTypeRepository(db)
        st = repo.register(type_id="ocr-rejected", display_name="Rejected")
        repo.reject(st, reason="Security risk")

        resp = client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-rejected",
                "instance_id": "inst-rejected-001",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        assert resp.status_code == 403

    def test_ii004_re_register_existing_instance(self, client, db):
        """II-004: Re-registering existing instance updates it."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        repo = ServiceTypeRepository(db)
        repo.create_or_update(
            type_id="ocr-reregister",
            display_name="Re-register",
            allowed_methods=["ocr_paddle_text"],
            allowed_tiers=[0],
            status="APPROVED",
            access_key="sk_reregister",
        )

        # First registration
        resp1 = client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-reregister",
                "instance_id": "inst-reregister",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )
        assert resp1.status_code == 200

        # Re-register same instance
        resp2 = client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-reregister",
                "instance_id": "inst-reregister",
                "allowed_methods": ["ocr_paddle_text", "structured_extract"],
                "allowed_tiers": [0, 1],
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["instance_status"] == "ACTIVE"


# ============================================================================
# Heartbeat
# ============================================================================


class TestHeartbeat:
    """II-005 to II-009: POST /internal/heartbeat"""

    def test_ii005_heartbeat_approved_continue(self, client, db):
        """II-005: Heartbeat from active instance returns continue."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        repo = ServiceTypeRepository(db)
        repo.create_or_update(
            type_id="ocr-hb-ok", display_name="HB OK",
            status="APPROVED", access_key="sk_hb_ok",
        )

        # Register instance via API
        client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-hb-ok",
                "instance_id": "inst-hb-ok",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        resp = client.post(
            "/api/v1/internal/heartbeat",
            json={
                "instance_id": "inst-hb-ok",
                "status": "idle",
                "files_completed": 5,
                "files_total": 10,
                "error_count": 0,
            },
            headers={"X-Access-Key": "sk_hb_ok"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "continue"

    def test_ii006_heartbeat_waiting_gets_approved(self, client, db):
        """II-006: Heartbeat from WAITING instance after type approved returns key.

        approve() auto-activates WAITING instances, so we manually set the
        instance back to WAITING to simulate the race: admin approved but
        worker hasn't received the key yet.
        """
        from app.infrastructure.database.repositories import (
            ServiceTypeRepository,
            ServiceInstanceRepository,
        )
        from app.infrastructure.database.models import ServiceInstanceStatus

        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.register(type_id="ocr-hb-wait", display_name="Wait Test")
        inst = inst_repo.register(instance_id="inst-hb-wait", service_type=st)

        # Approve the type (auto-activates instances)
        type_repo.approve(st)
        access_key = st.access_key

        # Simulate: worker hasn't received key yet, instance still "WAITING"
        inst.status = ServiceInstanceStatus.WAITING
        db.commit()

        # Heartbeat should return approved + key
        resp = client.post(
            "/api/v1/internal/heartbeat",
            json={
                "instance_id": "inst-hb-wait",
                "status": "idle",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "approved"
        assert data["access_key"] == access_key

    def test_ii007_heartbeat_disabled_drain(self, client, db):
        """II-007: Heartbeat from DISABLED type returns drain."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        repo = ServiceTypeRepository(db)
        st = repo.create_or_update(
            type_id="ocr-hb-dis", display_name="Disabled",
            status="APPROVED", access_key="sk_hb_dis",
        )

        # Register instance
        client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-hb-dis",
                "instance_id": "inst-hb-dis",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        # Disable the type
        repo.disable(st)

        resp = client.post(
            "/api/v1/internal/heartbeat",
            json={
                "instance_id": "inst-hb-dis",
                "status": "idle",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["action"] == "drain"

    def test_ii008_heartbeat_rejected_shutdown(self, client, db):
        """II-008: Heartbeat from REJECTED type returns shutdown."""
        from app.infrastructure.database.repositories import (
            ServiceTypeRepository,
            ServiceInstanceRepository,
        )

        type_repo = ServiceTypeRepository(db)
        inst_repo = ServiceInstanceRepository(db)

        st = type_repo.register(type_id="ocr-hb-rej", display_name="Reject")
        inst = inst_repo.register(instance_id="inst-hb-rej", service_type=st)
        type_repo.reject(st, reason="Bad worker")

        resp = client.post(
            "/api/v1/internal/heartbeat",
            json={
                "instance_id": "inst-hb-rej",
                "status": "idle",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "shutdown"
        assert data["rejection_reason"] is not None

    def test_ii009_heartbeat_unknown_instance(self, client):
        """II-009: Heartbeat from unregistered instance returns 404."""
        resp = client.post(
            "/api/v1/internal/heartbeat",
            json={
                "instance_id": "ghost-instance-999",
                "status": "idle",
            },
        )

        assert resp.status_code == 404


# ============================================================================
# Job Status Update
# ============================================================================


class TestJobStatusUpdate:
    """II-010 to II-014: PATCH /internal/jobs/{id}/status"""

    def _setup_job(self, db):
        """Create user + approved service type + request + QUEUED job."""
        from helpers import create_user, create_request_with_jobs, create_approved_service_type

        access_key = "sk_job_status_test"
        user = create_user(db, email="job_status@example.com")
        create_approved_service_type(db, type_id="ocr-job-test", access_key=access_key)
        req, jobs = create_request_with_jobs(db, user.id, num_jobs=1)
        return jobs[0].id, access_key

    def test_ii010_status_to_processing(self, client, db):
        """II-010: Update QUEUED job to PROCESSING with valid access key."""
        job_id, access_key = self._setup_job(db)

        resp = client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "PROCESSING"},
            headers={"X-Access-Key": access_key},
        )

        assert resp.status_code == 200
        result = resp.json()
        assert result["success"] is True
        assert result["status"] == "PROCESSING"

    def test_ii011_status_to_completed(self, client, db):
        """II-011: Update PROCESSING job to COMPLETED."""
        job_id, access_key = self._setup_job(db)

        # QUEUED → PROCESSING
        client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "PROCESSING"},
            headers={"X-Access-Key": access_key},
        )

        # PROCESSING → COMPLETED
        resp = client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "COMPLETED", "engine_version": "paddle 2.7.3"},
            headers={"X-Access-Key": access_key},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    def test_ii012_status_to_failed(self, client, db):
        """II-012: Update PROCESSING job to FAILED with error."""
        job_id, access_key = self._setup_job(db)

        client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "PROCESSING"},
            headers={"X-Access-Key": access_key},
        )

        resp = client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={
                "status": "FAILED",
                "error": "OCR timeout after 30s",
                "retriable": True,
            },
            headers={"X-Access-Key": access_key},
        )

        assert resp.status_code == 200
        # Status may be QUEUED (if retry kicked in) or FAILED
        status = resp.json()["status"]
        assert status in ("FAILED", "QUEUED")

    def test_ii013_invalid_access_key(self, client, db):
        """II-013: Job status update with invalid key returns 403."""
        job_id, _ = self._setup_job(db)

        resp = client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "PROCESSING"},
            headers={"X-Access-Key": "sk_totally_invalid_key"},
        )

        assert resp.status_code == 403

    def test_ii014_invalid_status_transition(self, client, db):
        """II-014: Invalid state transition returns 404 (job not updated)."""
        job_id, access_key = self._setup_job(db)

        # Try to go directly from QUEUED to COMPLETED (invalid)
        resp = client.patch(
            f"/api/v1/internal/jobs/{job_id}/status",
            json={"status": "COMPLETED"},
            headers={"X-Access-Key": access_key},
        )

        assert resp.status_code == 404


# ============================================================================
# Deregistration
# ============================================================================


class TestDeregistration:
    """II-015: POST /internal/deregister"""

    def test_ii015_deregister_instance(self, client, db):
        """II-015: Deregister marks instance as DEAD."""
        from app.infrastructure.database.repositories import ServiceTypeRepository

        repo = ServiceTypeRepository(db)
        repo.create_or_update(
            type_id="ocr-dereg", display_name="Dereg",
            status="APPROVED", access_key="sk_dereg",
        )

        # Register instance via API
        client.post(
            "/api/v1/internal/register",
            json={
                "service_type": "ocr-dereg",
                "instance_id": "inst-dereg-001",
                "allowed_methods": ["ocr_paddle_text"],
                "allowed_tiers": [0],
            },
        )

        # Deregister
        resp = client.post(
            "/api/v1/internal/deregister",
            json={"instance_id": "inst-dereg-001"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify instance is DEAD
        from app.infrastructure.database.repositories import ServiceInstanceRepository

        inst_repo = ServiceInstanceRepository(db)
        inst = inst_repo.get("inst-dereg-001")
        assert inst.status == "DEAD"
