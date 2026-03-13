"""
Test cases for Storage Helpers (SH-001 to SH-003)

Covers:
- generate_object_key() format
- generate_result_key() format
- parse_object_key() roundtrip
"""

import importlib.util
from pathlib import Path

# Load storage utils module
utils_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "infrastructure" / "storage" / "utils.py"
spec = importlib.util.spec_from_file_location("storage_utils", utils_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

generate_object_key = mod.generate_object_key
generate_result_key = mod.generate_result_key
parse_object_key = mod.parse_object_key


class TestGenerateObjectKey:
    """SH-001: Standard path format {user_id}/{request_id}/{file_id}/{filename}."""

    def test_standard_path(self):
        key = generate_object_key("user-1", "req-1", "file-1", "document.png")
        assert key == "user-1/req-1/file-1/document.png"

    def test_with_special_characters_in_filename(self):
        key = generate_object_key("u1", "r1", "f1", "my file (1).pdf")
        assert key == "u1/r1/f1/my file (1).pdf"

    def test_parse_roundtrip(self):
        key = generate_object_key("user-abc", "req-xyz", "file-123", "test.png")
        parsed = parse_object_key(key)
        assert parsed["user_id"] == "user-abc"
        assert parsed["request_id"] == "req-xyz"
        assert parsed["file_id"] == "file-123"
        assert parsed["filename"] == "test.png"


class TestGenerateResultKey:
    """SH-002: Result path format {user_id}/{request_id}/{file_id}/result.{format}."""

    def test_standard_result_path(self):
        key = generate_result_key("user-1", "req-1", "file-1", "txt")
        assert key == "user-1/req-1/file-1/result.txt"

    def test_json_format(self):
        key = generate_result_key("u1", "r1", "f1", "json")
        assert key == "u1/r1/f1/result.json"

    def test_result_key_is_parseable(self):
        key = generate_result_key("user-1", "req-1", "file-1", "txt")
        parsed = parse_object_key(key)
        assert parsed["user_id"] == "user-1"
        assert parsed["request_id"] == "req-1"
        assert parsed["file_id"] == "file-1"
        assert parsed["filename"] == "result.txt"


class TestParseObjectKey:
    """SH-003: parse_object_key returns correct components."""

    def test_valid_key(self):
        parsed = parse_object_key("user1/req1/file1/doc.png")
        assert parsed == {
            "user_id": "user1",
            "request_id": "req1",
            "file_id": "file1",
            "filename": "doc.png",
        }

    def test_invalid_key_too_short(self):
        assert parse_object_key("only/two") == {}

    def test_filename_with_slashes(self):
        parsed = parse_object_key("u/r/f/path/to/file.txt")
        assert parsed["filename"] == "path/to/file.txt"
