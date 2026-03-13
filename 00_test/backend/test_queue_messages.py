"""
Test cases for Queue Messages & Subjects (QM-001 to QM-004)

Covers:
- JobMessage dataclass serialization
- Default retry_count
- Subject format: ocr.{method}.tier{tier}
- DLQ subject format: dlq.{method}.tier{tier}
- parse_subject()
"""

import importlib.util
from pathlib import Path

# Load messages module
msg_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "infrastructure" / "queue" / "messages.py"
spec_msg = importlib.util.spec_from_file_location("messages", msg_path)
msg_mod = importlib.util.module_from_spec(spec_msg)
spec_msg.loader.exec_module(msg_mod)
JobMessage = msg_mod.JobMessage

# Load subjects module
subj_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "infrastructure" / "queue" / "subjects.py"
spec_subj = importlib.util.spec_from_file_location("subjects", subj_path)
subj_mod = importlib.util.module_from_spec(spec_subj)
spec_subj.loader.exec_module(subj_mod)
get_subject = subj_mod.get_subject
get_dlq_subject = subj_mod.get_dlq_subject
parse_subject = subj_mod.parse_subject


class TestJobMessageSerialization:
    """QM-001: to_dict() serialization."""

    def test_to_dict_all_fields_present(self):
        msg = JobMessage(
            job_id="j-1",
            file_id="f-1",
            request_id="r-1",
            method="ocr_text_raw",
            tier=0,
            output_format="txt",
            object_key="user1/req1/file1/test.png",
            retry_count=2,
        )
        d = msg.to_dict()
        assert d["job_id"] == "j-1"
        assert d["file_id"] == "f-1"
        assert d["request_id"] == "r-1"
        assert d["method"] == "ocr_text_raw"
        assert d["tier"] == 0
        assert d["output_format"] == "txt"
        assert d["object_key"] == "user1/req1/file1/test.png"
        assert d["retry_count"] == 2

    def test_from_dict_roundtrip(self):
        original = JobMessage(
            job_id="j-1", file_id="f-1", request_id="r-1",
            method="ocr_text_raw", tier=0, output_format="json",
            object_key="key/path", retry_count=1,
        )
        restored = JobMessage.from_dict(original.to_dict())
        assert restored.job_id == original.job_id
        assert restored.method == original.method
        assert restored.retry_count == original.retry_count


class TestJobMessageDefaults:
    """QM-002: Default retry_count = 0."""

    def test_default_retry_count(self):
        msg = JobMessage(
            job_id="j-1", file_id="f-1", request_id="r-1",
            method="ocr_text_raw", tier=0, output_format="txt",
            object_key="key/path",
        )
        assert msg.retry_count == 0


class TestSubjectFormat:
    """QM-003: Subject format ocr.{method}.tier{tier}."""

    def test_standard_subject(self):
        assert get_subject("ocr_text_raw", 0) == "ocr.ocr_text_raw.tier0"

    def test_different_method_and_tier(self):
        assert get_subject("structured_extract", 1) == "ocr.structured_extract.tier1"

    def test_parse_subject_roundtrip(self):
        subject = get_subject("ocr_text_raw", 2)
        parsed = parse_subject(subject)
        assert parsed["method"] == "ocr_text_raw"
        assert parsed["tier"] == 2


class TestDlqSubjectFormat:
    """QM-004: DLQ subject format dlq.{method}.tier{tier}."""

    def test_standard_dlq_subject(self):
        assert get_dlq_subject("ocr_text_raw", 0) == "dlq.ocr_text_raw.tier0"

    def test_different_method_and_tier(self):
        assert get_dlq_subject("structured_extract", 1) == "dlq.structured_extract.tier1"


class TestParseSubject:
    """Additional: parse_subject edge cases."""

    def test_parse_invalid_subject_returns_empty(self):
        assert parse_subject("invalid") == {}

    def test_parse_non_ocr_prefix_returns_empty(self):
        assert parse_subject("dlq.method.tier0") == {}
