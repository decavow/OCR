"""Contract tests: Heartbeat (C5)

Verify field alignment between worker heartbeat payload and
backend HeartbeatPayload/HeartbeatResponse schemas.

Test IDs: CT-022 through CT-024
"""

from helpers import load_backend_module


# Load backend schemas
_hb_schema = load_backend_module("api/v1/schemas/heartbeat.py", "ct_heartbeat_schema")
HeartbeatPayload = _hb_schema.HeartbeatPayload
HeartbeatResponse = _hb_schema.HeartbeatResponse


# ---------------------------------------------------------------------------
# CT-022: Worker payload fields match backend schema
# ---------------------------------------------------------------------------

class TestHeartbeatFieldAlignment:
    """CT-022: Worker HeartbeatPayload fields match backend schema."""

    def test_worker_payload_validates(self):
        """CT-022: Worker heartbeat payload passes backend validation."""
        # Worker heartbeat_client.py builds this exact payload:
        worker_payload = {
            "instance_id": "ocr-text-tier0-abc123",
            "status": "processing",
            "current_job_id": "job-1",
            "files_completed": 5,
            "files_total": 10,
            "error_count": 0,
        }
        parsed = HeartbeatPayload(**worker_payload)
        assert parsed.instance_id == "ocr-text-tier0-abc123"
        assert parsed.status == "processing"
        assert parsed.current_job_id == "job-1"
        assert parsed.files_completed == 5
        assert parsed.files_total == 10
        assert parsed.error_count == 0

    def test_required_fields_present(self):
        """CT-022b: All required fields in backend schema are sent by worker."""
        required = {
            name for name, f in HeartbeatPayload.model_fields.items()
            if f.is_required()
        }
        # Worker always sends: instance_id, status
        worker_required = {"instance_id", "status"}
        # Backend may require instance_id and status
        missing = required - worker_required - {
            "current_job_id", "files_completed", "files_total", "error_count"
        }
        assert missing == set(), f"Worker missing required fields: {missing}"

    def test_idle_payload_validates(self):
        """CT-022c: Idle worker payload validates."""
        worker_payload = {
            "instance_id": "ocr-text-tier0-abc123",
            "status": "idle",
            "current_job_id": None,
            "files_completed": 0,
            "files_total": 0,
            "error_count": 0,
        }
        parsed = HeartbeatPayload(**worker_payload)
        assert parsed.status == "idle"
        assert parsed.current_job_id is None

    def test_error_status_payload_validates(self):
        """CT-022d: Error status payload validates."""
        worker_payload = {
            "instance_id": "ocr-text-tier0-abc123",
            "status": "error",
            "current_job_id": None,
            "files_completed": 3,
            "files_total": 5,
            "error_count": 2,
        }
        parsed = HeartbeatPayload(**worker_payload)
        assert parsed.status == "error"
        assert parsed.error_count == 2


# ---------------------------------------------------------------------------
# CT-023: Backend response action → worker callback
# ---------------------------------------------------------------------------

class TestHeartbeatResponseAction:
    """CT-023: Backend HeartbeatResponse.action → worker callback dispatch."""

    def test_continue_action(self):
        """CT-023: Backend sends action=continue → worker continues normally."""
        response = HeartbeatResponse(
            success=True, received_at="2026-03-15T10:00:00Z",
            action="continue",
        )
        assert response.action == "continue"
        assert response.access_key is None

    def test_approved_action_with_key(self):
        """CT-023b: Backend sends action=approved + access_key → worker stores key."""
        response = HeartbeatResponse(
            success=True, received_at="2026-03-15T10:00:00Z",
            action="approved", access_key="sk_test_key_123",
        )
        assert response.action == "approved"
        assert response.access_key == "sk_test_key_123"

    def test_drain_action(self):
        """CT-023c: Backend sends action=drain → worker stops accepting jobs."""
        response = HeartbeatResponse(
            success=True, received_at="2026-03-15T10:00:00Z",
            action="drain",
        )
        assert response.action == "drain"

    def test_shutdown_action_with_reason(self):
        """CT-023d: Backend sends action=shutdown + reason → worker exits."""
        response = HeartbeatResponse(
            success=True, received_at="2026-03-15T10:00:00Z",
            action="shutdown",
            rejection_reason="Service type REJECTED by admin",
        )
        assert response.action == "shutdown"
        assert response.rejection_reason == "Service type REJECTED by admin"

    def test_all_valid_actions(self):
        """CT-023e: All actions worker handles are producible by backend."""
        # Worker handles: continue, approved, drain, shutdown
        valid_actions = ["continue", "approved", "drain", "shutdown"]
        for action in valid_actions:
            resp = HeartbeatResponse(
                success=True, received_at="2026-03-15T10:00:00Z",
                action=action,
            )
            assert resp.action == action


# ---------------------------------------------------------------------------
# CT-024: Idle worker heartbeat (current_job_id=None)
# ---------------------------------------------------------------------------

class TestIdleWorkerHeartbeat:
    """CT-024: Heartbeat with current_job_id=None (idle worker)."""

    def test_null_job_id_validates(self):
        """CT-024: current_job_id=None is valid in backend schema."""
        payload = HeartbeatPayload(
            instance_id="worker-1",
            status="idle",
            current_job_id=None,
            files_completed=0,
            files_total=0,
            error_count=0,
        )
        assert payload.current_job_id is None

    def test_default_current_job_id_is_none(self):
        """CT-024b: Default current_job_id is None."""
        payload = HeartbeatPayload(
            instance_id="worker-1",
            status="idle",
        )
        assert payload.current_job_id is None

    def test_default_counters_zero(self):
        """CT-024c: Default counter values are 0."""
        payload = HeartbeatPayload(
            instance_id="worker-1",
            status="idle",
        )
        assert payload.files_completed == 0
        assert payload.files_total == 0
        assert payload.error_count == 0
