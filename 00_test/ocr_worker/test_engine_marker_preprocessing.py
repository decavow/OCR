"""Unit tests for Marker engine preprocessing module.

Tests MP-001 through MP-007: format detection, temp file creation,
edge cases for PDF, images, and unknown formats.
"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image
import io


# Ensure worker source is on sys.path
from pathlib import Path
WORKER_ROOT = Path(__file__).parent.parent.parent / "03_worker"
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from app.engines.marker.preprocessing import load_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width=10, height=10) -> bytes:
    """Create a valid PNG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width=10, height=10) -> bytes:
    """Create a valid JPEG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(0, 255, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_pdf_bytes() -> bytes:
    """Create minimal PDF bytes."""
    return (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadDocument:
    """MP-001 to MP-007: load_document format detection and temp file creation."""

    def _cleanup(self, temp_path):
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    # MP-001: PDF detected via magic bytes
    def test_pdf_detection(self):
        pdf_bytes = _make_pdf_bytes()
        temp_path, info = load_document(pdf_bytes)
        try:
            assert info["format"] == "pdf"
            assert temp_path.endswith(".pdf")
            assert info["size_bytes"] == len(pdf_bytes)
            assert os.path.exists(temp_path)
            with open(temp_path, "rb") as f:
                assert f.read() == pdf_bytes
        finally:
            self._cleanup(temp_path)

    # MP-002: PNG image detection via PIL
    def test_png_detection(self):
        png_bytes = _make_png_bytes(20, 30)
        temp_path, info = load_document(png_bytes)
        try:
            assert info["format"] == "png"
            assert temp_path.endswith(".png")
            assert info["dimensions"]["width"] == 20
            assert info["dimensions"]["height"] == 30
        finally:
            self._cleanup(temp_path)

    # MP-003: JPEG image detection via PIL
    def test_jpeg_detection(self):
        jpeg_bytes = _make_jpeg_bytes(40, 50)
        temp_path, info = load_document(jpeg_bytes)
        try:
            assert info["format"] == "jpeg"
            assert temp_path.endswith(".jpg")
            assert info["dimensions"]["width"] == 40
            assert info["dimensions"]["height"] == 50
        finally:
            self._cleanup(temp_path)

    # MP-004: Unknown format falls back to .bin
    def test_unknown_format(self):
        garbage = b"\x00\x01\x02\x03random garbage bytes"
        temp_path, info = load_document(garbage)
        try:
            assert info["format"] == "unknown"
            assert temp_path.endswith(".bin")
            assert info["size_bytes"] == len(garbage)
        finally:
            self._cleanup(temp_path)

    # MP-005: Empty content still creates a file
    def test_empty_content(self):
        temp_path, info = load_document(b"")
        try:
            assert info["size_bytes"] == 0
            assert os.path.exists(temp_path)
            # Empty non-PDF, non-image → unknown
            assert info["format"] == "unknown"
        finally:
            self._cleanup(temp_path)

    # MP-006: Size tracking is accurate
    def test_size_tracking(self):
        content = b"A" * 12345
        temp_path, info = load_document(content)
        try:
            assert info["size_bytes"] == 12345
        finally:
            self._cleanup(temp_path)

    # MP-007: temp_path is included in info dict
    def test_temp_path_in_info(self):
        png_bytes = _make_png_bytes()
        temp_path, info = load_document(png_bytes)
        try:
            assert "temp_path" in info
            assert info["temp_path"] == temp_path
        finally:
            self._cleanup(temp_path)
