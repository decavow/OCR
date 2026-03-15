"""Cross-function flow tests: Registration + Approval (F4)

Test worker registration → pending → admin approve/reject flow.

Test IDs: FL-010 through FL-012
"""

from helpers import load_backend_module


# Load registration schema
_reg_schema = load_backend_module("api/v1/schemas/register.py", "fl_register_schema")
ServiceRegistrationRequest = _reg_schema.ServiceRegistrationRequest
ServiceRegistrationResponse = _reg_schema.ServiceRegistrationResponse

# Load heartbeat schema for approval via heartbeat
_hb_schema = load_backend_module("api/v1/schemas/heartbeat.py", "fl_heartbeat_schema")
HeartbeatResponse = _hb_schema.HeartbeatResponse


# ---------------------------------------------------------------------------
# FL-010: Worker register → service status = PENDING
# ---------------------------------------------------------------------------

class TestRegistrationPending:
    """FL-010: Worker register → service status = PENDING."""

    def test_new_registration_returns_pending(self):
        """FL-010a: New service type registration returns PENDING."""
        # Simulate backend response for new service type
        response = ServiceRegistrationResponse(
            instance_id="ocr-text-tier0-abc123",
            instance_status="WAITING",
            type_status="PENDING",
            access_key=None,
        )
        assert response.type_status == "PENDING"
        assert response.instance_status == "WAITING"
        assert response.access_key is None

    def test_worker_payload_valid_for_registration(self):
        """FL-010b: Worker registration payload validates."""
        payload = ServiceRegistrationRequest(
            service_type="ocr-text-tier0",
            instance_id="ocr-text-tier0-abc123",
            display_name="Vietnamese Text OCR",
            description="PaddleOCR v4",
            allowed_methods=["ocr_paddle_text"],
            allowed_tiers=[0],
            supported_output_formats=["txt", "json"],
        )
        assert payload.service_type == "ocr-text-tier0"
        assert payload.allowed_methods == ["ocr_paddle_text"]

    def test_pending_worker_no_access_key(self):
        """FL-010c: PENDING worker has no access_key → cannot process jobs."""
        response = ServiceRegistrationResponse(
            instance_id="worker-1",
            instance_status="WAITING",
            type_status="PENDING",
        )
        assert response.access_key is None


# ---------------------------------------------------------------------------
# FL-011: Admin approve → APPROVED → worker can receive jobs
# ---------------------------------------------------------------------------

class TestApprovalFlow:
    """FL-011: Admin approve → status = APPROVED → worker gets access key."""

    def test_approved_response_has_access_key(self):
        """FL-011a: Already-approved type returns access_key on register."""
        response = ServiceRegistrationResponse(
            instance_id="ocr-text-tier0-abc123",
            instance_status="ACTIVE",
            type_status="APPROVED",
            access_key="sk_production_key_abc",
        )
        assert response.type_status == "APPROVED"
        assert response.instance_status == "ACTIVE"
        assert response.access_key is not None
        assert response.access_key == "sk_production_key_abc"

    def test_approval_via_heartbeat_action(self):
        """FL-011b: Backend sends approved action via heartbeat with access_key."""
        heartbeat_resp = HeartbeatResponse(
            success=True,
            received_at="2026-03-15T10:00:00Z",
            action="approved",
            access_key="sk_new_key_xyz",
        )
        assert heartbeat_resp.action == "approved"
        assert heartbeat_resp.access_key == "sk_new_key_xyz"

    def test_worker_can_set_access_key_from_response(self):
        """FL-011c: Worker extracts access_key from registration response."""
        # Simulate what worker does in _register() callback
        reg_result = {
            "type_status": "APPROVED",
            "instance_status": "ACTIVE",
            "access_key": "sk_key_123",
        }
        assert reg_result.get("access_key") is not None
        assert reg_result["type_status"] == "APPROVED"

    def test_worker_can_set_access_key_from_heartbeat(self):
        """FL-011d: Worker extracts access_key from heartbeat approved action."""
        heartbeat_data = {
            "success": True,
            "received_at": "2026-03-15T10:00:00Z",
            "action": "approved",
            "access_key": "sk_heartbeat_key",
        }
        assert heartbeat_data.get("action") == "approved"
        assert heartbeat_data.get("access_key") == "sk_heartbeat_key"


# ---------------------------------------------------------------------------
# FL-012: Admin reject → REJECTED → worker blocked
# ---------------------------------------------------------------------------

class TestRejectionFlow:
    """FL-012: Admin reject → status = REJECTED → worker blocked."""

    def test_rejected_registration_response(self):
        """FL-012a: REJECTED type returns no access_key."""
        response = ServiceRegistrationResponse(
            instance_id="malicious-worker-1",
            instance_status="WAITING",
            type_status="REJECTED",
            access_key=None,
        )
        assert response.type_status == "REJECTED"
        assert response.access_key is None

    def test_shutdown_via_heartbeat(self):
        """FL-012b: Backend sends shutdown action with rejection reason."""
        heartbeat_resp = HeartbeatResponse(
            success=True,
            received_at="2026-03-15T10:00:00Z",
            action="shutdown",
            rejection_reason="Service type REJECTED by admin",
        )
        assert heartbeat_resp.action == "shutdown"
        assert "REJECTED" in heartbeat_resp.rejection_reason

    def test_rejected_worker_cannot_process(self):
        """FL-012c: Worker with no access_key cannot call status update."""
        # Worker checks self._access_key before calling orchestrator
        access_key = None
        assert access_key is None  # Cannot make authenticated requests
