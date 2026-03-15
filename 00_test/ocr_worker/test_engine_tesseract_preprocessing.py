"""Unit tests for tesseract preprocessing — TP-001 to TP-010.

Tests image loading and preparation without needing Tesseract installed.
pdf2image is mocked for PDF tests.
"""

import io
import sys
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Mock heavy dependencies before any engine import triggers __init__.py
# ---------------------------------------------------------------------------
sys.modules.setdefault("pytesseract", MagicMock())
sys.modules.setdefault("pdf2image", MagicMock())

import pytest
from PIL import Image

from app.engines.tesseract.preprocessing import (
    is_pdf,
    load_images,
    prepare_image,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_image_bytes(width: int = 10, height: int = 10,
                     mode: str = "RGB", fmt: str = "PNG") -> bytes:
    """Create real image bytes with the given mode and format."""
    color: int | tuple
    if mode == "L":
        color = 128
    elif mode == "RGBA":
        color = (255, 0, 0, 200)
    else:
        color = (255, 0, 0)
    img = Image.new(mode, (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


FAKE_PDF = b"%PDF-1.4 fake content"


# ---------------------------------------------------------------------------
# Tests — is_pdf
# ---------------------------------------------------------------------------

class TestIsPdf:
    """TP-001 to TP-003."""

    def test_tp001_pdf_bytes_returns_true(self):
        """TP-001: Bytes starting with %PDF are detected as PDF."""
        assert is_pdf(FAKE_PDF) is True

    def test_tp002_png_bytes_returns_false(self):
        """TP-002: PNG bytes are not PDF."""
        data = make_image_bytes(fmt="PNG")
        assert is_pdf(data) is False

    def test_tp003_empty_bytes_returns_false(self):
        """TP-003: Empty bytes are not PDF."""
        assert is_pdf(b"") is False


# ---------------------------------------------------------------------------
# Tests — load_images
# ---------------------------------------------------------------------------

class TestLoadImages:
    """TP-004 to TP-006, TP-010."""

    def test_tp004_png_returns_single_image(self):
        """TP-004: PNG bytes yield a list with 1 PIL Image."""
        data = make_image_bytes(20, 15, "RGB", "PNG")
        images = load_images(data)

        assert len(images) == 1
        assert isinstance(images[0], Image.Image)
        assert images[0].size == (20, 15)

    def test_tp005_jpeg_returns_single_image(self):
        """TP-005: JPEG bytes yield a list with 1 PIL Image."""
        data = make_image_bytes(20, 15, "RGB", "JPEG")
        images = load_images(data)

        assert len(images) == 1
        assert isinstance(images[0], Image.Image)

    def test_tp006_invalid_bytes_raises(self):
        """TP-006: Invalid bytes raise an exception."""
        with pytest.raises(Exception):
            load_images(b"not an image and not a pdf either")

    @patch("app.engines.tesseract.preprocessing.convert_from_bytes")
    def test_tp010_pdf_calls_pdf2image(self, mock_convert):
        """TP-010: PDF bytes route through pdf2image.convert_from_bytes."""
        fake_img = Image.new("RGB", (100, 100), color="white")
        mock_convert.return_value = [fake_img, fake_img]

        images = load_images(FAKE_PDF)

        mock_convert.assert_called_once_with(FAKE_PDF, dpi=200)
        assert len(images) == 2


# ---------------------------------------------------------------------------
# Tests — prepare_image
# ---------------------------------------------------------------------------

class TestPrepareImage:
    """TP-007 to TP-009."""

    def test_tp007_rgba_converted_to_rgb(self):
        """TP-007: RGBA image is converted to RGB."""
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 200))
        result = prepare_image(img)

        assert result.mode == "RGB"

    def test_tp008_grayscale_stays_l(self):
        """TP-008: Grayscale (L) image stays in L mode (allowed by Tesseract)."""
        img = Image.new("L", (10, 10), color=128)
        result = prepare_image(img)

        assert result.mode == "L"

    def test_tp009_rgb_stays_rgb(self):
        """TP-009: RGB image stays RGB (no conversion needed)."""
        img = Image.new("RGB", (10, 10), color=(0, 255, 0))
        result = prepare_image(img)

        assert result.mode == "RGB"
        # Should be the same object (no conversion)
        assert result is img
