"""Unit tests for tesseract postprocessing — TO-001 to TO-009.

Tests extract_plain, extract_detailed, format_output, and _flush_line.
pytesseract is mocked at import time.
"""

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Mock heavy dependencies before any engine import triggers __init__.py.
# Use setdefault so the first mock registered wins (preprocessing test may
# have already set it).
# ---------------------------------------------------------------------------
_pytesseract_mock = MagicMock()
_pytesseract_mock.Output = SimpleNamespace(DICT="dict")
sys.modules.setdefault("pytesseract", _pytesseract_mock)
sys.modules.setdefault("pdf2image", MagicMock())

from app.engines.tesseract import postprocessing as _post_mod
from app.engines.tesseract.postprocessing import (
    extract_detailed,
    extract_plain,
    format_output,
    _flush_line,
)

# Get a reference to the actual pytesseract object that the postprocessing
# module imported, regardless of which mock it is.
_real_pyt = _post_mod.pytesseract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pil_image(width: int = 100, height: int = 100) -> Image.Image:
    return Image.new("RGB", (width, height), color="white")


def make_tesseract_data(entries: list[dict]) -> dict:
    """Build pytesseract.image_to_data DICT-style output.

    Each entry: {"text": str, "line_num": int, "conf": int,
                 "left": int, "top": int, "width": int, "height": int}
    """
    return {
        "text": [e["text"] for e in entries],
        "line_num": [e.get("line_num", 1) for e in entries],
        "conf": [e.get("conf", 90) for e in entries],
        "left": [e.get("left", 0) for e in entries],
        "top": [e.get("top", 0) for e in entries],
        "width": [e.get("width", 50) for e in entries],
        "height": [e.get("height", 20) for e in entries],
    }


# ---------------------------------------------------------------------------
# Tests — extract_plain
# ---------------------------------------------------------------------------

class TestExtractPlain:
    """TO-001 to TO-002."""

    def setup_method(self):
        _real_pyt.image_to_string.reset_mock()
        _real_pyt.image_to_data.reset_mock()

    def test_to001_extract_plain_returns_lines(self):
        """TO-001: extract_plain returns non-empty lines from pytesseract."""
        _real_pyt.image_to_string.return_value = "Hello\nWorld\n\n"
        img = make_pil_image()

        lines = extract_plain(img, "eng")

        assert lines == ["Hello", "World"]
        _real_pyt.image_to_string.assert_called_once_with(img, lang="eng")

    def test_to002_extract_plain_empty(self):
        """TO-002: extract_plain with empty output returns empty list."""
        _real_pyt.image_to_string.return_value = "  \n  \n  "
        img = make_pil_image()

        lines = extract_plain(img, "eng")

        assert lines == []


# ---------------------------------------------------------------------------
# Tests — extract_detailed
# ---------------------------------------------------------------------------

class TestExtractDetailed:
    """TO-003 to TO-005."""

    def setup_method(self):
        _real_pyt.image_to_string.reset_mock()
        _real_pyt.image_to_data.reset_mock()

    def test_to003_single_line_extraction(self):
        """TO-003: Single line with two words is extracted correctly."""
        data = make_tesseract_data([
            {"text": "Hello", "line_num": 1, "conf": 90,
             "left": 10, "top": 5, "width": 40, "height": 15},
            {"text": "World", "line_num": 1, "conf": 80,
             "left": 60, "top": 5, "width": 45, "height": 15},
        ])
        _real_pyt.image_to_data.return_value = data

        text_lines, boxes_data = extract_detailed(make_pil_image(), "eng")

        assert len(text_lines) == 1
        assert text_lines[0] == "Hello World"
        assert len(boxes_data) == 1
        # Average confidence: (90+80)/2 = 85 => 85/100 = 0.85
        assert boxes_data[0]["confidence"] == 0.85
        assert boxes_data[0]["text"] == "Hello World"

    def test_to004_multiple_lines(self):
        """TO-004: Words on different line_num produce separate lines."""
        data = make_tesseract_data([
            {"text": "First", "line_num": 1, "conf": 95,
             "left": 0, "top": 0, "width": 50, "height": 20},
            {"text": "Second", "line_num": 2, "conf": 88,
             "left": 0, "top": 30, "width": 60, "height": 20},
        ])
        _real_pyt.image_to_data.return_value = data

        text_lines, boxes_data = extract_detailed(make_pil_image(), "eng")

        assert len(text_lines) == 2
        assert text_lines[0] == "First"
        assert text_lines[1] == "Second"

    def test_to005_skip_low_confidence_and_empty(self):
        """TO-005: Words with conf < 0 or empty text are skipped."""
        data = make_tesseract_data([
            {"text": "Good", "line_num": 1, "conf": 90,
             "left": 0, "top": 0, "width": 50, "height": 20},
            {"text": "", "line_num": 1, "conf": 50,
             "left": 50, "top": 0, "width": 10, "height": 20},
            {"text": "Bad", "line_num": 1, "conf": -1,
             "left": 60, "top": 0, "width": 30, "height": 20},
        ])
        _real_pyt.image_to_data.return_value = data

        text_lines, boxes_data = extract_detailed(make_pil_image(), "eng")

        assert len(text_lines) == 1
        assert text_lines[0] == "Good"


# ---------------------------------------------------------------------------
# Tests — format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    """TO-006 to TO-008."""

    def test_to006_text_format(self):
        """TO-006: Text format returns UTF-8 encoded lines."""
        result = format_output(["Line 1", "Line 2"], [], 1, "txt")

        assert result == b"Line 1\nLine 2"

    def test_to007_json_format(self):
        """TO-007: JSON format returns proper structure with page_count."""
        boxes = [{"text": "Hi", "confidence": 0.9, "box": []}]
        result = format_output(["Hi"], boxes, 2, "json")
        parsed = json.loads(result)

        assert parsed["text"] == "Hi"
        assert parsed["lines"] == 1
        assert parsed["pages"] == 2
        assert len(parsed["details"]) == 1

    def test_to008_json_utf8(self):
        """TO-008: JSON handles non-ASCII (Vietnamese text)."""
        text = "Xin chào"
        result = format_output([text], [], 1, "json")
        parsed = json.loads(result)

        assert parsed["text"] == text


# ---------------------------------------------------------------------------
# Tests — _flush_line internals
# ---------------------------------------------------------------------------

class TestFlushLine:
    """TO-009: Line flushing logic."""

    def test_to009_flush_line_joins_words_and_averages_confidence(self):
        """TO-009: _flush_line joins words with space and averages confidence."""
        current_line = {
            "text": ["Hello", "World"],
            "confidences": [90, 80],
            "boxes": [
                [[0, 0], [40, 0], [40, 20], [0, 20]],
                [[50, 0], [95, 0], [95, 20], [50, 20]],
            ],
        }
        text_lines: list = []
        boxes_data: list = []

        _flush_line(current_line, text_lines, boxes_data)

        assert text_lines == ["Hello World"]
        assert boxes_data[0]["text"] == "Hello World"
        # (90 + 80) / 2 = 85 / 100 = 0.85
        assert boxes_data[0]["confidence"] == 0.85
        assert boxes_data[0]["box"] == current_line["boxes"]
