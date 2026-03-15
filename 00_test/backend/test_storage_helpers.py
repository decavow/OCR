"""Unit tests for storage helpers (02_backend/app/infrastructure/storage/utils.py).

Pure logic tests — no external dependencies.

Test IDs: SH-001 to SH-003
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load():
    mod_path = BACKEND_ROOT / "app" / "infrastructure" / "storage" / "utils.py"
    spec = importlib.util.spec_from_file_location("storage_utils", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


utils = _load()
generate_object_key = utils.generate_object_key
generate_result_key = utils.generate_result_key
parse_object_key = utils.parse_object_key


# ===================================================================
# Storage helpers  (SH-001 to SH-003)
# ===================================================================


class TestStorageHelpers:
    """SH-001 to SH-003: Object key generation and parsing."""

    def test_sh001_generate_object_key(self):
        """SH-001: generate_object_key produces '{date}/{HHmmss}_{method}_{user8}/{name}'."""
        ts = datetime(2026, 3, 15, 15, 30, 42, tzinfo=timezone.utc)
        key = generate_object_key(
            user_id="user-1-abcdef",
            request_id="req-1",
            file_id="file-1",
            original_name="photo.png",
            method="ocr_paddle_text",
            created_at=ts,
        )
        assert key == "2026-03-15/223042_ocr_paddle_text_user-1-a/photo.png"

    def test_sh001b_generate_object_key_sanitizes_filename(self):
        """SH-001b: Dangerous path separators are stripped from filename."""
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        key = generate_object_key(
            user_id="u1234567",
            request_id="req-1",
            file_id="file-1",
            original_name="../../etc/passwd",
            created_at=ts,
        )
        assert ".." not in key
        assert "etc" not in key.split("/")[0]
        assert key.endswith("passwd")

    def test_sh002_generate_result_key(self):
        """SH-002: generate_result_key produces '{date}/{time}_{method}_{user8}/{base}_result.{fmt}'."""
        ts = datetime(2026, 3, 15, 15, 30, 42, tzinfo=timezone.utc)
        key = generate_result_key(
            user_id="user-1-abcdef",
            request_id="req-1",
            file_id="file-1",
            output_format="txt",
            original_name="invoice.png",
            method="ocr_paddle_text",
            created_at=ts,
        )
        assert key == "2026-03-15/223042_ocr_paddle_text_user-1-a/invoice_result.txt"

    def test_sh002b_generate_result_key_fallback_file_id(self):
        """SH-002b: Falls back to file_id prefix when no original_name."""
        ts = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        key = generate_result_key(
            user_id="abcdefgh",
            request_id="req-1",
            file_id="f1234567-rest",
            output_format="json",
            created_at=ts,
        )
        assert "f1234567_result.json" in key

    def test_sh003_parse_object_key(self):
        """SH-003: parse_object_key extracts date, folder, filename."""
        result = parse_object_key("2026-03-15/153042_ocr_paddle_text_user1234/photo.png")
        assert result == {
            "date": "2026-03-15",
            "folder": "153042_ocr_paddle_text_user1234",
            "filename": "photo.png",
        }
