"""Unit tests for paddle_vl preprocessing — VP-001 to VP-008.

Tests file type detection, image loading, and image preparation
without needing PaddleOCR/PPStructure installed.
"""

import io
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock heavy dependencies before any engine import triggers __init__.py
# ---------------------------------------------------------------------------
sys.modules.setdefault("paddleocr", MagicMock())

import numpy as np
import pytest
from PIL import Image

from app.engines.paddle_vl.preprocessing import (
    detect_file_type,
    load_images,
    prepare_image,
    MIN_SHORT_SIDE,
    MAX_LONG_SIDE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_png_bytes(width: int = 10, height: int = 10, mode: str = "RGB") -> bytes:
    """Create real PNG bytes."""
    color: int | tuple
    if mode == "L":
        color = 128
    elif mode == "RGBA":
        color = (255, 0, 0, 200)
    else:
        color = (255, 0, 0)
    img = Image.new(mode, (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


FAKE_PDF = b"%PDF-1.4 fake content"


# ---------------------------------------------------------------------------
# Tests — detect_file_type
# ---------------------------------------------------------------------------

class TestDetectFileType:
    """VP-001 to VP-003."""

    def test_vp001_pdf_bytes(self):
        """VP-001: PDF magic bytes return 'pdf'."""
        assert detect_file_type(FAKE_PDF) == "pdf"

    def test_vp002_png_bytes(self):
        """VP-002: PNG bytes return 'image'."""
        data = make_png_bytes()
        assert detect_file_type(data) == "image"

    def test_vp003_empty_bytes(self):
        """VP-003: Empty bytes return 'image' (default)."""
        assert detect_file_type(b"") == "image"


# ---------------------------------------------------------------------------
# Tests — load_images
# ---------------------------------------------------------------------------

class TestLoadImages:
    """VP-004 to VP-005."""

    def test_vp004_png_returns_ndarray_list(self):
        """VP-004: PNG bytes return a list with one np.ndarray."""
        data = make_png_bytes(20, 15, "RGB")
        images = load_images(data)

        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        # shape: (height, width, channels)
        assert images[0].shape == (15, 20, 3)

    def test_vp005_rgba_converted_to_rgb(self):
        """VP-005: RGBA image is converted to 3-channel RGB."""
        data = make_png_bytes(10, 10, "RGBA")
        images = load_images(data)

        assert len(images) == 1
        assert images[0].shape[2] == 3  # RGB, not RGBA


# ---------------------------------------------------------------------------
# Tests — prepare_image
# ---------------------------------------------------------------------------

class TestPrepareImage:
    """VP-006 to VP-008."""

    def test_vp006_small_image_upscaled(self):
        """VP-006: Image with short side < MIN_SHORT_SIDE is upscaled."""
        # Create a 200x300 image (short side = 200 < MIN_SHORT_SIDE=1500)
        img = np.zeros((300, 200, 3), dtype=np.uint8)
        result = prepare_image(img)

        h, w = result.shape[:2]
        short_side = min(h, w)
        # After upscaling, the short side should be >= MIN_SHORT_SIDE
        # (unless capped by MAX_LONG_SIDE)
        assert short_side >= MIN_SHORT_SIDE or max(h, w) >= MAX_LONG_SIDE

    def test_vp007_large_enough_no_change(self):
        """VP-007: Image already meeting MIN_SHORT_SIDE is not modified."""
        # Create image with short side = 1600 > MIN_SHORT_SIDE=1500
        img = np.zeros((1600, 2000, 3), dtype=np.uint8)
        result = prepare_image(img)

        assert result.shape == img.shape

    def test_vp008_very_large_upscale_capped(self):
        """VP-008: Upscaling is capped so long side does not exceed MAX_LONG_SIDE."""
        # Create a 100x3500 image.  short_side=100, long_side=3500.
        # scale for short = MIN_SHORT_SIDE / 100 = 15.0
        # long_side * 15.0 = 52500 >> MAX_LONG_SIDE => clamp scale
        # clamped_scale = MAX_LONG_SIDE / 3500 = ~1.14
        img = np.zeros((3500, 100, 3), dtype=np.uint8)
        result = prepare_image(img)

        h, w = result.shape[:2]
        long_side = max(h, w)
        assert long_side <= MAX_LONG_SIDE + 1  # +1 for int rounding
