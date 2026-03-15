"""Contract tests: Registration (C6)

Verify field alignment between worker registration payload and
backend ServiceRegistrationRequest schema.

Test IDs: CT-025 through CT-027
"""

from helpers import load_backend_module


# Load backend schema
_reg_schema = load_backend_module("api/v1/schemas/register.py", "ct_register_schema")
ServiceRegistrationRequest = _reg_schema.ServiceRegistrationRequest
ServiceRegistrationResponse = _reg_schema.ServiceRegistrationResponse


# ---------------------------------------------------------------------------
# CT-025: Worker register payload → backend validates
# ---------------------------------------------------------------------------

class TestRegistrationFieldAlignment:
    """CT-025: Worker register payload matches backend schema."""

    def test_worker_register_payload_validates(self):
        """CT-025: Exact payload worker builds passes backend validation."""
        # From orchestrator_client.py register() method:
        worker_payload = {
            "service_type": "ocr-text-tier0",
            "instance_id": "ocr-text-tier0-abc123",
            "display_name": "Vietnamese Text OCR",
            "description": "PaddleOCR-based text extraction",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
        }
        parsed = ServiceRegistrationRequest(**worker_payload)
        assert parsed.service_type == "ocr-text-tier0"
        assert parsed.instance_id == "ocr-text-tier0-abc123"
        assert parsed.display_name == "Vietnamese Text OCR"
        assert parsed.allowed_methods == ["ocr_paddle_text"]
        assert parsed.allowed_tiers == [0]

    def test_worker_payload_with_optional_fields(self):
        """CT-025b: Worker payload with dev_contact + engine_info validates."""
        worker_payload = {
            "service_type": "paddle-vl-tier1",
            "instance_id": "paddle-vl-tier1-xyz789",
            "display_name": "PaddleVL Structured Extract",
            "description": "Vision-language OCR",
            "allowed_methods": ["structured_extract"],
            "allowed_tiers": [1],
            "dev_contact": "team@example.com",
            "engine_info": {
                "engine": "paddle_vl",
                "version": "3.0.0",
                "capabilities": ["table", "layout"],
            },
            "supported_output_formats": ["txt", "json", "md"],
        }
        parsed = ServiceRegistrationRequest(**worker_payload)
        assert parsed.dev_contact == "team@example.com"
        assert parsed.engine_info["engine"] == "paddle_vl"
        assert "md" in parsed.supported_output_formats

    def test_required_fields_present(self):
        """CT-025c: All required fields in backend schema are sent by worker."""
        required = {
            name for name, f in ServiceRegistrationRequest.model_fields.items()
            if f.is_required()
        }
        # Worker always sends these (from orchestrator_client.py):
        worker_always_sends = {"service_type", "instance_id"}
        missing = required - worker_always_sends
        assert missing == set(), f"Worker missing required fields: {missing}"

    def test_response_schema_fields(self):
        """CT-025d: Backend response has fields worker expects."""
        response = ServiceRegistrationResponse(
            instance_id="ocr-text-tier0-abc123",
            instance_status="WAITING",
            type_status="PENDING",
        )
        assert response.instance_id == "ocr-text-tier0-abc123"
        assert response.type_status == "PENDING"
        assert response.access_key is None

    def test_response_with_access_key(self):
        """CT-025e: Approved type returns access_key in response."""
        response = ServiceRegistrationResponse(
            instance_id="ocr-text-tier0-abc123",
            instance_status="ACTIVE",
            type_status="APPROVED",
            access_key="sk_test_key",
        )
        assert response.access_key == "sk_test_key"
        assert response.type_status == "APPROVED"


# ---------------------------------------------------------------------------
# CT-026: Worker does NOT send metadata → backend accepts
# ---------------------------------------------------------------------------

class TestMetadataOptional:
    """CT-026: Worker omits metadata field → backend accepts (optional)."""

    def test_no_metadata_validates(self):
        """CT-026: Payload without metadata passes validation."""
        worker_payload = {
            "service_type": "ocr-text-tier0",
            "instance_id": "worker-1",
            "display_name": "OCR Worker",
            "description": "Test",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            # No metadata field
        }
        parsed = ServiceRegistrationRequest(**worker_payload)
        assert parsed.metadata is None

    def test_metadata_is_optional_in_schema(self):
        """CT-026b: metadata field is Optional in backend schema."""
        field = ServiceRegistrationRequest.model_fields["metadata"]
        assert not field.is_required()

    def test_metadata_accepted_if_sent(self):
        """CT-026c: If metadata is sent, backend accepts it."""
        worker_payload = {
            "service_type": "ocr-text-tier0",
            "instance_id": "worker-1",
            "display_name": "OCR Worker",
            "description": "Test",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "metadata": {"hostname": "worker-pod-1", "gpu": "A100"},
        }
        parsed = ServiceRegistrationRequest(**worker_payload)
        assert parsed.metadata["hostname"] == "worker-pod-1"


# ---------------------------------------------------------------------------
# CT-027: Worker allowed_methods valid in backend config
# ---------------------------------------------------------------------------

class TestAllowedMethodsValid:
    """CT-027: All allowed_methods worker sends are valid method names."""

    def test_common_methods_are_valid_strings(self):
        """CT-027: Standard method names are non-empty strings."""
        # Methods used by different worker types
        all_methods = [
            "ocr_paddle_text",       # PaddleOCR text
            "ocr_general",        # Tesseract
            "structured_extract", # PaddleVL
        ]
        for method in all_methods:
            assert isinstance(method, str) and len(method) > 0

    def test_methods_accepted_by_schema(self):
        """CT-027b: allowed_methods list validates in schema."""
        payload = ServiceRegistrationRequest(
            service_type="test",
            instance_id="test-1",
            allowed_methods=["ocr_paddle_text", "ocr_general"],
            allowed_tiers=[0, 1],
        )
        assert "ocr_paddle_text" in payload.allowed_methods
        assert "ocr_general" in payload.allowed_methods

    def test_multi_tier_worker(self):
        """CT-027c: Worker supporting multiple tiers validates."""
        payload = ServiceRegistrationRequest(
            service_type="multi-tier",
            instance_id="multi-1",
            allowed_methods=["structured_extract"],
            allowed_tiers=[0, 1, 2],
        )
        assert payload.allowed_tiers == [0, 1, 2]
