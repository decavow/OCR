"""Unit tests for upload validators (02_backend/app/modules/upload/validators.py).

Tests the pure-logic validation functions: validate_file, validate_batch,
validate_total_batch_size, detect_mime_from_magic, and constants.

Test IDs: UP-001 to UP-011
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_upload_exceptions():
    """Load upload exception classes."""
    # Load core exceptions first (pure Python)
    exc_path = BACKEND_ROOT / "app" / "core" / "exceptions.py"
    spec = importlib.util.spec_from_file_location("core_exceptions_up", exc_path)
    exc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exc_mod)

    # Load upload exceptions
    up_exc_path = BACKEND_ROOT / "app" / "modules" / "upload" / "exceptions.py"
    spec2 = importlib.util.spec_from_file_location("upload_exceptions_up", up_exc_path)
    mod2 = importlib.util.module_from_spec(spec2)

    mocked = {
        "app.core.exceptions": exc_mod,
    }
    with patch.dict("sys.modules", mocked):
        spec2.loader.exec_module(mod2)
    return exc_mod, mod2


def _load_validators(upload_exc_mod):
    """Load validators module with real upload exceptions."""
    mod_path = BACKEND_ROOT / "app" / "modules" / "upload" / "validators.py"
    spec = importlib.util.spec_from_file_location("upload_validators_up", mod_path)
    mod = importlib.util.module_from_spec(spec)

    # Build the exceptions namespace that the relative import resolves to
    exc_ns = MagicMock()
    exc_ns.InvalidFileType = upload_exc_mod.InvalidFileType
    exc_ns.FileTooLarge = upload_exc_mod.FileTooLarge
    exc_ns.BatchTooLarge = upload_exc_mod.BatchTooLarge
    exc_ns.BatchTotalSizeTooLarge = upload_exc_mod.BatchTotalSizeTooLarge

    # The validators module does:
    #   from .exceptions import InvalidFileType, FileTooLarge, BatchTooLarge, BatchTotalSizeTooLarge
    #   from fastapi import UploadFile
    # We mock the parent package so the relative import resolves.
    parent_pkg = MagicMock()
    parent_pkg.exceptions = exc_ns

    mocked = {
        # Resolve relative import ".exceptions"
        "app": MagicMock(),
        "app.modules": MagicMock(),
        "app.modules.upload": parent_pkg,
        "app.modules.upload.exceptions": exc_ns,
        # FastAPI UploadFile
        "fastapi": MagicMock(),
    }

    # Set __package__ so relative imports work
    mod.__package__ = "app.modules.upload"

    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


# Load modules
core_exc_mod, upload_exc_mod = _load_upload_exceptions()
validators = _load_validators(upload_exc_mod)

# Import classes and functions
validate_file = validators.validate_file
validate_batch = validators.validate_batch
validate_total_batch_size = validators.validate_total_batch_size
detect_mime_from_magic = validators.detect_mime_from_magic
ALLOWED_MIME_TYPES = validators.ALLOWED_MIME_TYPES
MAGIC_BYTES = validators.MAGIC_BYTES
MAX_FILE_SIZE = validators.MAX_FILE_SIZE
MAX_BATCH_SIZE = validators.MAX_BATCH_SIZE
MAX_TOTAL_BATCH_SIZE = validators.MAX_TOTAL_BATCH_SIZE

InvalidFileType = upload_exc_mod.InvalidFileType
FileTooLarge = upload_exc_mod.FileTooLarge
BatchTooLarge = upload_exc_mod.BatchTooLarge
BatchTotalSizeTooLarge = upload_exc_mod.BatchTotalSizeTooLarge


# ---------------------------------------------------------------------------
# Sample file bytes
# ---------------------------------------------------------------------------

# Minimal PNG header (magic bytes)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SAMPLE_PNG = (
    PNG_MAGIC
    + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    + b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    + b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal PDF header
PDF_MAGIC = b"%PDF"
SAMPLE_PDF = (
    b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
)

# JPEG magic bytes
JPEG_MAGIC = b"\xff\xd8\xff"
SAMPLE_JPEG = JPEG_MAGIC + b"\xe0" + b"\x00" * 100


# ===================================================================
# validate_file  (UP-001 to UP-004)
# ===================================================================

class TestValidateFile:
    """UP-001 to UP-004: File validation logic."""

    def test_up001_valid_png(self):
        """UP-001: validate_file with valid PNG content returns 'image/png'."""
        result = validate_file(SAMPLE_PNG, "image/png", "test.png")
        assert result == "image/png"

    def test_up002_valid_pdf(self):
        """UP-002: validate_file with valid PDF content returns 'application/pdf'."""
        result = validate_file(SAMPLE_PDF, "application/pdf", "doc.pdf")
        assert result == "application/pdf"

    def test_up003_invalid_type_raises(self):
        """UP-003: validate_file with unsupported type raises InvalidFileType."""
        # Content with unknown magic bytes and unsupported declared mime
        content = b"PK\x03\x04" + b"\x00" * 100  # ZIP-like magic
        with pytest.raises(InvalidFileType) as exc_info:
            validate_file(content, "application/zip", "archive.zip")
        assert exc_info.value.code == "INVALID_FILE_TYPE"

    def test_up004_empty_content_with_bad_mime_raises(self):
        """UP-004: validate_file with no recognizable content and bad mime raises."""
        content = b"\x00\x00\x00\x00"  # Unknown magic bytes
        with pytest.raises(InvalidFileType):
            validate_file(content, "application/octet-stream", "unknown.bin")

    def test_up004b_file_too_large_raises(self):
        """UP-004b: validate_file with oversized content raises FileTooLarge."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_FILE_SIZE + 1)
        with pytest.raises(FileTooLarge):
            validate_file(content, "image/png", "huge.png")


# ===================================================================
# validate_batch  (UP-005 to UP-006)
# ===================================================================

class TestValidateBatch:
    """UP-005 to UP-006: Batch size validation."""

    def test_up005_batch_within_limit(self):
        """UP-005: validate_batch with <= 20 files does not raise."""
        files = [MagicMock() for _ in range(5)]
        # Should not raise
        validate_batch(files)

    def test_up006_batch_over_limit_raises(self):
        """UP-006: validate_batch with > 20 files raises BatchTooLarge."""
        files = [MagicMock() for _ in range(21)]
        with pytest.raises(BatchTooLarge) as exc_info:
            validate_batch(files)
        assert exc_info.value.code == "BATCH_TOO_LARGE"

    def test_up006b_empty_batch_raises(self):
        """UP-006b: validate_batch with 0 files raises BatchTooLarge."""
        with pytest.raises(BatchTooLarge):
            validate_batch([])


# ===================================================================
# validate_total_batch_size  (UP-007 to UP-008)
# ===================================================================

class TestValidateTotalBatchSize:
    """UP-007 to UP-008: Total batch size validation."""

    def test_up007_within_limit(self):
        """UP-007: validate_total_batch_size within 200MB does not raise."""
        # 100MB should be fine
        validate_total_batch_size(100 * 1024 * 1024)

    def test_up008_over_limit_raises(self):
        """UP-008: validate_total_batch_size over 200MB raises."""
        over_limit = MAX_TOTAL_BATCH_SIZE + 1
        with pytest.raises(BatchTotalSizeTooLarge) as exc_info:
            validate_total_batch_size(over_limit)
        assert exc_info.value.code == "BATCH_TOTAL_SIZE_TOO_LARGE"


# ===================================================================
# Constants  (UP-009 to UP-010)
# ===================================================================

class TestConstants:
    """UP-009 to UP-010: Verify expected constants."""

    def test_up009_allowed_mime_types(self):
        """UP-009: ALLOWED_MIME_TYPES includes standard image and PDF types."""
        assert "image/jpeg" in ALLOWED_MIME_TYPES
        assert "image/png" in ALLOWED_MIME_TYPES
        assert "image/tiff" in ALLOWED_MIME_TYPES
        assert "application/pdf" in ALLOWED_MIME_TYPES
        assert "image/gif" in ALLOWED_MIME_TYPES
        assert "image/webp" in ALLOWED_MIME_TYPES
        assert "image/bmp" in ALLOWED_MIME_TYPES

    def test_up010_max_file_size_50mb(self):
        """UP-010: MAX_FILE_SIZE is 50MB."""
        assert MAX_FILE_SIZE == 50 * 1024 * 1024


# ===================================================================
# detect_mime_from_magic  (UP-011)
# ===================================================================

class TestDetectMimeFromMagic:
    """UP-011: Magic byte detection."""

    def test_up011_png_magic_bytes(self):
        """UP-011: detect_mime_from_magic identifies PNG from magic bytes."""
        result = detect_mime_from_magic(SAMPLE_PNG)
        assert result == "image/png"

    def test_up011b_jpeg_magic_bytes(self):
        """UP-011b: detect_mime_from_magic identifies JPEG from magic bytes."""
        result = detect_mime_from_magic(SAMPLE_JPEG)
        assert result == "image/jpeg"

    def test_up011c_pdf_magic_bytes(self):
        """UP-011c: detect_mime_from_magic identifies PDF from magic bytes."""
        result = detect_mime_from_magic(SAMPLE_PDF)
        assert result == "application/pdf"

    def test_up011d_unknown_magic_returns_none(self):
        """UP-011d: detect_mime_from_magic returns None for unknown magic."""
        result = detect_mime_from_magic(b"\x00\x00\x00\x00content")
        assert result is None
