"""Unit tests for queue messages and subjects.

Sources:
  02_backend/app/infrastructure/queue/messages.py
  02_backend/app/infrastructure/queue/subjects.py

Pure logic tests — no external dependencies.

Test IDs: QM-001 to QM-004
"""

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_clean(relative_path, module_name):
    mod_path = BACKEND_ROOT / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


messages = _load_clean("infrastructure/queue/messages.py", "messages")
subjects = _load_clean("infrastructure/queue/subjects.py", "subjects")

JobMessage = messages.JobMessage
get_subject = subjects.get_subject
get_dlq_subject = subjects.get_dlq_subject


# ===================================================================
# JobMessage  (QM-001 to QM-002)
# ===================================================================


class TestJobMessage:
    """QM-001 to QM-002: Serialization and defaults."""

    def test_qm001_to_dict_serialization(self):
        """QM-001: to_dict() produces correct dictionary with all fields."""
        msg = JobMessage(
            job_id="j1",
            file_id="f1",
            request_id="r1",
            method="ocr_paddle_text",
            tier=0,
            output_format="txt",
            object_key="u1/r1/f1/doc.png",
            retry_count=2,
        )
        d = msg.to_dict()
        assert d == {
            "job_id": "j1",
            "file_id": "f1",
            "request_id": "r1",
            "method": "ocr_paddle_text",
            "tier": 0,
            "output_format": "txt",
            "object_key": "u1/r1/f1/doc.png",
            "retry_count": 2,
        }

        # Round-trip: from_dict should reconstruct the same message
        msg2 = JobMessage.from_dict(d)
        assert msg2.to_dict() == d

    def test_qm002_default_retry_count(self):
        """QM-002: Default retry_count is 0."""
        msg = JobMessage(
            job_id="j1",
            file_id="f1",
            request_id="r1",
            method="ocr_paddle_text",
            tier=0,
            output_format="txt",
            object_key="u1/r1/f1/doc.png",
        )
        assert msg.retry_count == 0


# ===================================================================
# Subjects  (QM-003 to QM-004)
# ===================================================================


class TestSubjects:
    """QM-003 to QM-004: Subject string formatting."""

    def test_qm003_subject_format(self):
        """QM-003: get_subject produces 'ocr.{method}.tier{tier}'."""
        assert get_subject("ocr_paddle_text", 0) == "ocr.ocr_paddle_text.tier0"
        assert get_subject("ocr_pdf", 1) == "ocr.ocr_pdf.tier1"

    def test_qm004_dlq_subject_format(self):
        """QM-004: get_dlq_subject produces 'dlq.{method}.tier{tier}'."""
        assert get_dlq_subject("ocr_paddle_text", 0) == "dlq.ocr_paddle_text.tier0"
        assert get_dlq_subject("ocr_pdf", 2) == "dlq.ocr_pdf.tier2"
