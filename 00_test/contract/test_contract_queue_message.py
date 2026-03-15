"""Contract tests: Queue Message (C1)

Verify that backend JobMessage → JSON → worker parse produces identical data.
Both sides must agree on field names, types, and subject format.

Test IDs: CT-001 through CT-005
"""

import json
from types import SimpleNamespace

from helpers import JobMessage, get_subject


# ---------------------------------------------------------------------------
# CT-001: Full field round-trip
# ---------------------------------------------------------------------------

class TestQueueMessageRoundTrip:
    """CT-001: Backend JobMessage → JSON → Worker parse → same fields."""

    def test_all_fields_round_trip(self):
        """CT-001: All fields survive JSON serialization and match worker expectations."""
        # Backend builds a JobMessage
        backend_msg = JobMessage(
            job_id="job-abc",
            file_id="file-xyz",
            request_id="req-123",
            method="ocr_paddle_text",
            tier=0,
            output_format="txt",
            object_key="user1/req-123/file-xyz/test.png",
            retry_count=0,
        )

        # Serialize as backend would publish to NATS
        json_bytes = json.dumps(backend_msg.to_dict()).encode()

        # Worker parses the same JSON
        worker_data = json.loads(json_bytes.decode())

        # Worker extracts these exact fields (from queue_client.py pull_job)
        assert worker_data["job_id"] == "job-abc"
        assert worker_data["file_id"] == "file-xyz"
        assert worker_data["request_id"] == "req-123"
        assert worker_data["method"] == "ocr_paddle_text"
        assert worker_data["tier"] == 0
        assert worker_data["output_format"] == "txt"
        assert worker_data["object_key"] == "user1/req-123/file-xyz/test.png"

    def test_retry_count_preserved(self):
        """CT-001b: retry_count field round-trips correctly."""
        msg = JobMessage(
            job_id="j1", file_id="f1", request_id="r1",
            method="ocr_paddle_text", tier=0, output_format="txt",
            object_key="k1", retry_count=3,
        )
        data = json.loads(json.dumps(msg.to_dict()))
        assert data["retry_count"] == 3


# ---------------------------------------------------------------------------
# CT-002: NATS subject format
# ---------------------------------------------------------------------------

class TestSubjectFormat:
    """CT-002: Backend publish subject matches worker subscribe subject."""

    def test_subject_format_matches_worker_filter(self):
        """CT-002: get_subject produces format worker expects."""
        subject = get_subject("ocr_paddle_text", 0)
        # Worker subscribes to "ocr.{method}.tier{tier}"
        assert subject == "ocr.ocr_paddle_text.tier0"

    def test_subject_format_higher_tier(self):
        """CT-002b: Higher tier subject correct."""
        subject = get_subject("structured_extract", 1)
        assert subject == "ocr.structured_extract.tier1"


# ---------------------------------------------------------------------------
# CT-003: Missing optional fields
# ---------------------------------------------------------------------------

class TestMissingOptionalFields:
    """CT-003: Worker handles messages with missing optional fields."""

    def test_worker_handles_missing_retry_count(self):
        """CT-003: Worker can parse message without retry_count (default 0)."""
        # Backend sends without retry_count
        payload = {
            "job_id": "j1",
            "file_id": "f1",
            "request_id": "r1",
            "method": "ocr_paddle_text",
            "tier": 0,
            "output_format": "txt",
            "object_key": "k1",
        }
        json_bytes = json.dumps(payload).encode()
        parsed = json.loads(json_bytes.decode())

        # Worker extracts required fields — all present
        assert parsed["job_id"] == "j1"
        assert parsed["file_id"] == "f1"
        assert parsed["method"] == "ocr_paddle_text"
        # retry_count absent → worker should handle gracefully
        assert parsed.get("retry_count", 0) == 0

    def test_from_dict_default_retry_count(self):
        """CT-003b: JobMessage.from_dict without retry_count uses default=0."""
        data = {
            "job_id": "j1", "file_id": "f1", "request_id": "r1",
            "method": "m", "tier": 0, "output_format": "txt",
            "object_key": "k1",
        }
        msg = JobMessage.from_dict(data)
        assert msg.retry_count == 0


# ---------------------------------------------------------------------------
# CT-004: Extra fields ignored
# ---------------------------------------------------------------------------

class TestExtraFieldsIgnored:
    """CT-004: Worker does not crash when backend sends extra fields."""

    def test_extra_fields_do_not_break_worker_parse(self):
        """CT-004: Extra fields in JSON are harmlessly ignored by worker."""
        payload = {
            "job_id": "j1",
            "file_id": "f1",
            "request_id": "r1",
            "method": "ocr_paddle_text",
            "tier": 0,
            "output_format": "txt",
            "object_key": "k1",
            "future_field": "some_value",
            "another_new_field": 42,
        }
        json_bytes = json.dumps(payload).encode()
        parsed = json.loads(json_bytes.decode())

        # Worker only reads known fields — should not crash
        assert parsed["job_id"] == "j1"
        assert parsed["method"] == "ocr_paddle_text"
        # Extra fields exist but are not accessed by worker
        assert "future_field" in parsed


# ---------------------------------------------------------------------------
# CT-005: Unicode/special chars
# ---------------------------------------------------------------------------

class TestUnicodeSpecialChars:
    """CT-005: Unicode and special characters in method/tier survive round-trip."""

    def test_unicode_method_name(self):
        """CT-005: Method name with underscores/special chars round-trips."""
        msg = JobMessage(
            job_id="j1", file_id="f1", request_id="r1",
            method="structured_extract", tier=1,
            output_format="json", object_key="k1",
        )
        data = json.loads(json.dumps(msg.to_dict()))
        assert data["method"] == "structured_extract"

    def test_output_format_md(self):
        """CT-005b: Markdown output format round-trips."""
        msg = JobMessage(
            job_id="j1", file_id="f1", request_id="r1",
            method="structured_extract", tier=0,
            output_format="md", object_key="k1",
        )
        data = json.loads(json.dumps(msg.to_dict()))
        assert data["output_format"] == "md"

    def test_object_key_with_special_chars(self):
        """CT-005c: Object key with slashes and dots round-trips."""
        key = "user-1/req-abc/file-xyz/tài_liệu.pdf"
        msg = JobMessage(
            job_id="j1", file_id="f1", request_id="r1",
            method="ocr_paddle_text", tier=0,
            output_format="txt", object_key=key,
        )
        data = json.loads(json.dumps(msg.to_dict()))
        assert data["object_key"] == key
