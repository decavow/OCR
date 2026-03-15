"""Unit tests for paddle_text postprocessing — PO-001 to PO-011.

Tests extract_results and format_output without needing PaddleOCR installed.
"""

import json
import sys
from typing import List
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock heavy dependencies before any engine import triggers __init__.py
# ---------------------------------------------------------------------------
sys.modules.setdefault("paddleocr", MagicMock())

import pytest

from app.engines.paddle_text.postprocessing import extract_results, format_output


# ---------------------------------------------------------------------------
# Helpers — build PaddleOCR-shaped results
# ---------------------------------------------------------------------------

def make_box(x1: int = 0, y1: int = 0, x2: int = 100, y2: int = 30):
    """Create a 4-point bounding box [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]."""
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def make_line(text: str, confidence: float = 0.95, box=None):
    """Create a single PaddleOCR line: [bbox, (text, confidence)]."""
    if box is None:
        box = make_box()
    return [box, (text, confidence)]


def make_ocr_result(lines: list):
    """Wrap lines into PaddleOCR result format: [page0_lines]."""
    return [lines]


# ---------------------------------------------------------------------------
# Tests — extract_results
# ---------------------------------------------------------------------------

class TestExtractResults:
    """PO-001 to PO-006."""

    def test_po001_single_line(self):
        """PO-001: Single line is extracted correctly."""
        result = make_ocr_result([make_line("Hello World", 0.98)])
        full_text, text_lines, boxes_data = extract_results(result)

        assert full_text == "Hello World"
        assert text_lines == ["Hello World"]
        assert len(boxes_data) == 1
        assert boxes_data[0]["text"] == "Hello World"
        assert boxes_data[0]["confidence"] == 0.98

    def test_po002_multiple_lines(self):
        """PO-002: Multiple lines are joined with newline."""
        result = make_ocr_result([
            make_line("Line one", 0.9),
            make_line("Line two", 0.85),
            make_line("Line three", 0.92),
        ])
        full_text, text_lines, boxes_data = extract_results(result)

        assert full_text == "Line one\nLine two\nLine three"
        assert len(text_lines) == 3
        assert len(boxes_data) == 3

    def test_po003_confidence_rounding(self):
        """PO-003: Confidence is rounded to 4 decimal places."""
        result = make_ocr_result([make_line("text", 0.123456789)])
        _, _, boxes_data = extract_results(result)

        assert boxes_data[0]["confidence"] == 0.1235

    def test_po004_box_preserved(self):
        """PO-004: Bounding box coordinates are preserved."""
        box = make_box(10, 20, 200, 50)
        result = make_ocr_result([make_line("test", 0.9, box)])
        _, _, boxes_data = extract_results(result)

        assert boxes_data[0]["box"] == box

    def test_po005_empty_result_none(self):
        """PO-005: None result returns empty data."""
        full_text, text_lines, boxes_data = extract_results(None)

        assert full_text == ""
        assert text_lines == []
        assert boxes_data == []

    def test_po006_empty_result_list(self):
        """PO-006: Empty list result returns empty data."""
        full_text, text_lines, boxes_data = extract_results([])

        assert full_text == ""
        assert text_lines == []
        assert boxes_data == []


# ---------------------------------------------------------------------------
# Tests — format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    """PO-007 to PO-011."""

    def test_po007_text_format(self):
        """PO-007: Text format returns UTF-8 encoded full text."""
        result = format_output("Hello World", ["Hello World"], [], "txt")

        assert result == b"Hello World"

    def test_po008_json_format_structure(self):
        """PO-008: JSON format returns proper structure."""
        boxes = [{"text": "Hi", "confidence": 0.95, "box": make_box()}]
        result = format_output("Hi", ["Hi"], boxes, "json")
        parsed = json.loads(result)

        assert parsed["text"] == "Hi"
        assert parsed["lines"] == 1
        assert len(parsed["details"]) == 1
        assert parsed["details"][0]["text"] == "Hi"

    def test_po009_json_utf8_encoding(self):
        """PO-009: JSON output handles Unicode (Vietnamese, CJK)."""
        text = "Xin chào thế giới"
        result = format_output(text, [text], [], "json")
        parsed = json.loads(result)

        assert parsed["text"] == text

    def test_po010_text_multiline(self):
        """PO-010: Text format preserves multiline structure."""
        full_text = "Line 1\nLine 2\nLine 3"
        result = format_output(full_text, ["Line 1", "Line 2", "Line 3"], [], "txt")

        assert result == b"Line 1\nLine 2\nLine 3"

    def test_po011_empty_input(self):
        """PO-011: Empty text produces empty bytes for text format."""
        result = format_output("", [], [], "txt")

        assert result == b""
