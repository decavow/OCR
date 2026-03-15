"""Unit tests for paddle_text preprocessing — PP-001 to PP-005.

Tests image loading and conversion without needing PaddleOCR installed.
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

from app.engines.paddle_text.preprocessing import load_image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_png_bytes(width: int = 10, height: int = 10, mode: str = "RGB") -> bytes:
    """Create real PNG bytes with the given mode."""
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadImage:
    """PP-001 to PP-005: load_image tests."""

    def test_pp001_valid_png_returns_array_and_size(self):
        """PP-001: Valid RGB PNG returns (np.ndarray, (width, height))."""
        data = make_png_bytes(20, 15, "RGB")
        arr, size = load_image(data)

        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.uint8
        # PIL size is (width, height); numpy shape is (height, width, channels)
        assert size == (20, 15)
        assert arr.shape == (15, 20, 3)

    def test_pp002_rgba_converted_to_rgb(self):
        """PP-002: RGBA PNG is converted to RGB (3 channels)."""
        data = make_png_bytes(10, 10, "RGBA")
        arr, size = load_image(data)

        assert arr.shape[2] == 3  # RGB, not RGBA
        assert size == (10, 10)

    def test_pp003_grayscale_converted_to_rgb(self):
        """PP-003: Grayscale (L) PNG is converted to RGB."""
        data = make_png_bytes(8, 8, "L")
        arr, size = load_image(data)

        assert arr.ndim == 3
        assert arr.shape[2] == 3
        assert size == (8, 8)

    def test_pp004_invalid_bytes_raises(self):
        """PP-004: Random non-image bytes raise an exception."""
        with pytest.raises(Exception):
            load_image(b"this is not an image at all")

    def test_pp005_empty_bytes_raises(self):
        """PP-005: Empty bytes raise an exception."""
        with pytest.raises(Exception):
            load_image(b"")
