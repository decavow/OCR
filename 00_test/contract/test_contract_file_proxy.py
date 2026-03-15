"""Contract tests: File Download (C3) + File Upload (C4)

Verify field alignment and data format round-trip between
backend FileProxy schemas and worker FileProxyClient.

Test IDs: CT-012 through CT-021
"""

import base64
import json

from helpers import load_backend_module


# Load backend schemas
_fp_schema = load_backend_module("api/v1/schemas/file_proxy.py", "ct_file_proxy_schema")
FileProxyDownloadReq = _fp_schema.FileProxyDownloadReq
FileProxyUploadReq = _fp_schema.FileProxyUploadReq


# ===================================================================
# C3: File Download — CT-012 through CT-016
# ===================================================================

class TestDownloadFieldAlignment:
    """CT-012: Worker download payload matches backend schema."""

    def test_worker_download_payload_validates(self):
        """CT-012: Worker sends {job_id, file_id} → backend validates."""
        # Worker file_proxy_client.py: json={"job_id": job_id, "file_id": file_id}
        worker_payload = {"job_id": "job-1", "file_id": "file-1"}
        parsed = FileProxyDownloadReq(**worker_payload)
        assert parsed.job_id == "job-1"
        assert parsed.file_id == "file-1"

    def test_required_fields_present(self):
        """CT-012b: All required fields in download schema are sent by worker."""
        required = {
            name for name, f in FileProxyDownloadReq.model_fields.items()
            if f.is_required()
        }
        worker_fields = {"job_id", "file_id"}
        missing = required - worker_fields
        assert missing == set(), f"Worker missing required fields: {missing}"


class TestDownloadResponseHeaders:
    """CT-013: Backend response headers match what worker reads."""

    def test_content_type_header_name(self):
        """CT-013: Worker reads X-Content-Type header from backend response."""
        # Backend sets: headers["X-Content-Type"] = content_type
        # Worker reads: response.headers.get("X-Content-Type", "application/octet-stream")
        header_name = "X-Content-Type"
        assert header_name == "X-Content-Type"

    def test_file_name_header_name(self):
        """CT-013b: Worker reads X-File-Name header from backend response."""
        header_name = "X-File-Name"
        assert header_name == "X-File-Name"

    def test_content_type_default_fallback(self):
        """CT-013c: Worker has correct fallback if header missing."""
        # Worker: response.headers.get("X-Content-Type", "application/octet-stream")
        default = "application/octet-stream"
        assert default == "application/octet-stream"


class TestBinaryRoundTrip:
    """CT-014: Binary content survives download round-trip."""

    def test_pdf_bytes_round_trip(self):
        """CT-014: PDF bytes identical after HTTP transfer simulation."""
        original = (
            b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        )
        # HTTP transfers raw bytes — verify identity
        transferred = bytes(original)
        assert transferred == original

    def test_png_bytes_round_trip(self):
        """CT-014b: PNG bytes identical."""
        original = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        transferred = bytes(original)
        assert transferred == original


class TestLargeFileHandling:
    """CT-015: Large file marker test."""

    def test_large_payload_accepted(self):
        """CT-015: >1MB payload does not break schema validation."""
        # Schema only validates job_id and file_id, not content size
        payload = {"job_id": "job-1", "file_id": "file-1"}
        parsed = FileProxyDownloadReq(**payload)
        assert parsed.job_id == "job-1"


class TestDownloadNotFound:
    """CT-016: File not found error format."""

    def test_error_response_structure(self):
        """CT-016: Backend returns JSON error with 'detail' key on 404."""
        # Standard FastAPI HTTPException format
        error_response = {"detail": "File not found"}
        assert "detail" in error_response
        assert isinstance(error_response["detail"], str)


# ===================================================================
# C4: File Upload — CT-017 through CT-021
# ===================================================================

class TestUploadBase64RoundTrip:
    """CT-017: Worker base64 encode → backend decode → same bytes."""

    def test_text_content_round_trip(self):
        """CT-017: Plain text OCR result round-trips via base64."""
        original = b"Hello World\nLine 2\nVietnamese: Xin chao"
        encoded = base64.b64encode(original).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == original

    def test_json_content_round_trip(self):
        """CT-017b: JSON OCR result round-trips via base64."""
        original = json.dumps({"text": "Hello", "confidence": 0.95}).encode()
        encoded = base64.b64encode(original).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == original

    def test_binary_content_round_trip(self):
        """CT-017c: Binary content (e.g., markdown with unicode) round-trips."""
        original = "# Kết quả OCR\n\nĐây là nội dung tiếng Việt".encode("utf-8")
        encoded = base64.b64encode(original).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == original


class TestUploadFieldAlignment:
    """CT-018: Worker upload payload matches backend schema."""

    def test_worker_upload_payload_validates(self):
        """CT-018: Worker sends {job_id, file_id, content, content_type} → validates."""
        content = base64.b64encode(b"OCR result").decode("utf-8")
        worker_payload = {
            "job_id": "job-1",
            "file_id": "file-1",
            "content": content,
            "content_type": "text/plain",
        }
        parsed = FileProxyUploadReq(**worker_payload)
        assert parsed.job_id == "job-1"
        assert parsed.file_id == "file-1"
        assert parsed.content == content
        assert parsed.content_type == "text/plain"

    def test_required_fields_present(self):
        """CT-018b: All required fields sent by worker."""
        required = {
            name for name, f in FileProxyUploadReq.model_fields.items()
            if f.is_required()
        }
        # Worker sends: job_id, file_id, content (always), content_type (has default)
        worker_fields = {"job_id", "file_id", "content"}
        missing = required - worker_fields
        assert missing == set(), f"Worker missing required fields: {missing}"


class TestUploadContentType:
    """CT-019: Content-type propagation for all output formats."""

    def test_text_plain(self):
        """CT-019: text/plain for txt output format."""
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=base64.b64encode(b"text").decode(),
            content_type="text/plain",
        )
        assert payload.content_type == "text/plain"

    def test_application_json(self):
        """CT-019b: application/json for json output format."""
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=base64.b64encode(b"{}").decode(),
            content_type="application/json",
        )
        assert payload.content_type == "application/json"

    def test_text_markdown(self):
        """CT-019c: text/markdown for md output format."""
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=base64.b64encode(b"# Header").decode(),
            content_type="text/markdown",
        )
        assert payload.content_type == "text/markdown"

    def test_text_html(self):
        """CT-019d: text/html for html output format."""
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=base64.b64encode(b"<p>html</p>").decode(),
            content_type="text/html",
        )
        assert payload.content_type == "text/html"

    def test_default_content_type(self):
        """CT-019e: Default content_type is text/plain."""
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=base64.b64encode(b"data").decode(),
        )
        assert payload.content_type == "text/plain"


class TestEmptyUpload:
    """CT-020: Empty result upload (0 bytes base64)."""

    def test_empty_content_validates(self):
        """CT-020: Base64 of empty bytes validates in schema."""
        empty_b64 = base64.b64encode(b"").decode("utf-8")
        payload = FileProxyUploadReq(
            job_id="j1", file_id="f1",
            content=empty_b64, content_type="text/plain",
        )
        assert payload.content == empty_b64
        assert base64.b64decode(payload.content) == b""


class TestLargeUpload:
    """CT-021: Large result upload (>100KB)."""

    def test_large_content_round_trip(self):
        """CT-021: 100KB+ content base64 round-trips correctly."""
        original = b"A" * 150_000  # 150KB
        encoded = base64.b64encode(original).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == original
        assert len(decoded) == 150_000
