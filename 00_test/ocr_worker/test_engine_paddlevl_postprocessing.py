"""Unit tests for paddle_vl postprocessing — VO-001 to VO-022.

Tests extract_regions, extract_regions_from_raw_ocr, assess_result_quality,
html_table_to_markdown, format_structured_output, and helper functions.
No PPStructure or PaddleOCR dependency needed.
"""

import json
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock heavy dependencies before any engine import triggers __init__.py
# ---------------------------------------------------------------------------
sys.modules.setdefault("paddleocr", MagicMock())

import pytest

from app.engines.paddle_vl.postprocessing import (
    extract_regions,
    extract_regions_from_raw_ocr,
    assess_result_quality,
    html_table_to_markdown,
    format_structured_output,
    _strip_html_wrapper,
    _is_valid_table_html,
    _extract_text_from_table_res,
)


# ---------------------------------------------------------------------------
# Helpers — build PPStructure-shaped data
# ---------------------------------------------------------------------------

def make_text_region(text: str = "sample text", confidence: float = 0.95,
                     bbox: list | None = None, region_type: str = "text"):
    """Create a PPStructure text/title/list region."""
    return {
        "type": region_type,
        "bbox": bbox or [0, 0, 100, 30],
        "res": [{"text": text, "confidence": confidence}],
    }


def make_table_region(html: str = "<table><tr><td>A</td></tr></table>",
                      bbox: list | None = None, rec_res: list | None = None):
    """Create a PPStructure table region."""
    res: dict = {"html": html}
    if rec_res is not None:
        res["rec_res"] = rec_res
    return {
        "type": "table",
        "bbox": bbox or [0, 50, 200, 150],
        "res": res,
    }


def make_figure_region(bbox: list | None = None):
    return {
        "type": "figure",
        "bbox": bbox or [0, 200, 100, 300],
    }


def make_page(regions: list, page_number: int = 1):
    return {"page_number": page_number, "regions": regions}


# ---------------------------------------------------------------------------
# Tests — extract_regions  (VO-001 to VO-006)
# ---------------------------------------------------------------------------

class TestExtractRegions:
    """VO-001 to VO-006: PPStructure region extraction."""

    def test_vo001_text_region(self):
        """VO-001: Text region is extracted with content and confidence."""
        raw = [make_text_region("Hello World", 0.95)]
        result = extract_regions(raw, 0)

        assert result["page_number"] == 1
        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "text"
        assert r["content"] == "Hello World"
        assert r["confidence"] == 0.95

    def test_vo002_table_region_valid_html(self):
        """VO-002: Table region with valid HTML produces table type with markdown."""
        html = "<table><tr><td>Col1</td><td>Col2</td></tr><tr><td>A</td><td>B</td></tr></table>"
        raw = [make_table_region(html)]
        result = extract_regions(raw, 0)

        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "table"
        assert "html" in r
        assert "markdown" in r
        assert "Col1" in r["markdown"]

    def test_vo003_table_invalid_html_fallback_rec_res(self):
        """VO-003: Table with invalid HTML falls back to text from rec_res."""
        raw = [make_table_region(
            html="<table></table>",
            rec_res=[("cell text", 0.8)],
        )]
        result = extract_regions(raw, 0)

        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "text"
        assert "cell text" in r["content"]

    def test_vo004_figure_region(self):
        """VO-004: Figure region has type 'figure' and no content."""
        raw = [make_figure_region()]
        result = extract_regions(raw, 0)

        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "figure"
        assert r.get("caption") is None

    def test_vo005_empty_result(self):
        """VO-005: Empty raw result returns empty regions list."""
        result = extract_regions([], 0)

        assert result["page_number"] == 1
        assert result["regions"] == []

    def test_vo006_none_result(self):
        """VO-006: None raw result returns empty regions list."""
        result = extract_regions(None, 0)

        assert result["page_number"] == 1
        assert result["regions"] == []


# ---------------------------------------------------------------------------
# Tests — extract_regions (continued: VO-007 to VO-009)
# ---------------------------------------------------------------------------

class TestExtractRegionsSorting:
    """VO-007 to VO-009: Sorting, title type, mixed regions."""

    def test_vo007_sorted_by_reading_order(self):
        """VO-007: Regions are sorted top-to-bottom, left-to-right."""
        raw = [
            make_text_region("Bottom", bbox=[0, 100, 200, 130]),
            make_text_region("Top", bbox=[0, 0, 200, 30]),
        ]
        result = extract_regions(raw, 0)

        assert result["regions"][0]["content"] == "Top"
        assert result["regions"][1]["content"] == "Bottom"

    def test_vo008_title_type(self):
        """VO-008: Title region type is preserved."""
        raw = [make_text_region("Title Text", region_type="title")]
        result = extract_regions(raw, 0)

        assert result["regions"][0]["type"] == "title"

    def test_vo009_table_res_as_list_fallback(self):
        """VO-009: Table with res as list (not dict) is handled as text."""
        raw = [{
            "type": "table",
            "bbox": [0, 0, 100, 50],
            "res": [{"text": "cell1"}, {"text": "cell2"}],
        }]
        result = extract_regions(raw, 0)

        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "text"
        assert "cell1" in r["content"]
        assert "cell2" in r["content"]


# ---------------------------------------------------------------------------
# Tests — extract_regions_from_raw_ocr
# ---------------------------------------------------------------------------

class TestExtractRegionsFromRawOcr:
    """Additional tests for raw OCR extraction."""

    def test_single_line(self):
        """Raw OCR single line produces one text region.

        PaddleOCR.ocr() returns: [[ [box, (text, conf)], ... ]]
        (list of pages, each page is a list of lines).
        """
        raw_ocr = [[
            [[[10, 10], [100, 10], [100, 30], [10, 30]], ("Hello", 0.95)],
        ]]
        result = extract_regions_from_raw_ocr(raw_ocr, 0)

        assert result["page_number"] == 1
        assert len(result["regions"]) == 1
        r = result["regions"][0]
        assert r["type"] == "text"
        assert r["content"] == "Hello"
        assert r["confidence"] == 0.95
        assert r["bbox"] == [10, 10, 100, 30]

    def test_empty_raw_ocr(self):
        """Empty raw OCR returns no regions."""
        result = extract_regions_from_raw_ocr([], 0)
        assert result["regions"] == []

    def test_skips_blank_text(self):
        """Lines with only whitespace text are skipped."""
        raw_ocr = [[
            [[[0, 0], [10, 0], [10, 10], [0, 10]], ("  ", 0.5)],
            [[[0, 20], [50, 20], [50, 40], [0, 40]], ("Real text", 0.9)],
        ]]
        result = extract_regions_from_raw_ocr(raw_ocr, 0)

        assert len(result["regions"]) == 1
        assert result["regions"][0]["content"] == "Real text"

    def test_string_text_info(self):
        """When text_info is a plain string, it is used with confidence=0.0."""
        raw_ocr = [[
            [[[0, 0], [50, 0], [50, 20], [0, 20]], "plain string"],
        ]]
        result = extract_regions_from_raw_ocr(raw_ocr, 0)

        assert len(result["regions"]) == 1
        assert result["regions"][0]["content"] == "plain string"
        assert result["regions"][0]["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Tests — assess_result_quality  (VO-010 to VO-012)
# ---------------------------------------------------------------------------

class TestAssessResultQuality:
    """VO-010 to VO-012."""

    def test_vo010_good_quality_with_text(self):
        """VO-010: Pages with text blocks return True."""
        pages = [make_page([
            {"type": "text", "bbox": [0, 0, 100, 30], "content": "Hello"},
        ])]
        assert assess_result_quality(pages) is True

    def test_vo011_no_regions_returns_false(self):
        """VO-011: No regions at all returns False."""
        pages = [make_page([])]
        assert assess_result_quality(pages) is False

    def test_vo012_only_empty_tables_returns_false(self):
        """VO-012: Only table regions with no valid HTML/markdown returns False."""
        pages = [make_page([
            {"type": "table", "bbox": [0, 0, 100, 100], "html": "", "markdown": ""},
        ])]
        assert assess_result_quality(pages) is False


# ---------------------------------------------------------------------------
# Tests — html_table_to_markdown  (VO-013 to VO-015)
# ---------------------------------------------------------------------------

class TestHtmlTableToMarkdown:
    """VO-013 to VO-015."""

    def test_vo013_simple_table(self):
        """VO-013: Simple 2-col table converts to markdown."""
        html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
        md = html_table_to_markdown(html)

        assert "| A | B |" in md
        assert "|---|---|" in md
        assert "| 1 | 2 |" in md

    def test_vo014_empty_html(self):
        """VO-014: Empty HTML returns empty string."""
        assert html_table_to_markdown("") == ""

    def test_vo015_uneven_rows_padded(self):
        """VO-015: Rows with fewer cells are padded to max column count."""
        html = "<table><tr><td>A</td><td>B</td><td>C</td></tr><tr><td>1</td></tr></table>"
        md = html_table_to_markdown(html)
        lines = md.strip().split("\n")

        # Header has 3 cols: | A | B | C |
        assert lines[0].count("|") == 4
        # Data row padded to 3 cols: | 1 |  |  |
        assert lines[2].count("|") == 4


# ---------------------------------------------------------------------------
# Tests — format_structured_output  (VO-016 to VO-018)
# ---------------------------------------------------------------------------

class TestFormatStructuredOutput:
    """VO-016 to VO-018."""

    def _sample_pages(self):
        return [make_page([
            {"type": "title", "bbox": [0, 0, 200, 40],
             "content": "Report Title", "confidence": 0.99},
            {"type": "text", "bbox": [0, 50, 200, 100],
             "content": "Body text here.", "confidence": 0.95},
        ])]

    def test_vo016_json_format(self):
        """VO-016: JSON format has pages and summary."""
        pages = self._sample_pages()
        result = format_structured_output(pages, "json")
        parsed = json.loads(result)

        assert "pages" in parsed
        assert "summary" in parsed
        assert parsed["summary"]["total_pages"] == 1
        assert parsed["summary"]["total_regions"] == 2
        assert parsed["summary"]["text_blocks"] == 2  # title + text

    def test_vo017_markdown_format(self):
        """VO-017: Markdown format contains title and text."""
        pages = self._sample_pages()
        result = format_structured_output(pages, "md")
        text = result.decode("utf-8")

        assert "# Report Title" in text
        assert "Body text here." in text

    def test_vo018_plain_text_format(self):
        """VO-018: Plain text fallback concatenates content."""
        pages = self._sample_pages()
        result = format_structured_output(pages, "txt")
        text = result.decode("utf-8")

        assert "Report Title" in text
        assert "Body text here." in text


# ---------------------------------------------------------------------------
# Tests — helper functions  (VO-019 to VO-022)
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """VO-019 to VO-022."""

    def test_vo019_strip_html_wrapper(self):
        """VO-019: <html><body> wrapper is stripped."""
        html = "<html><body><table><tr><td>X</td></tr></table></body></html>"
        result = _strip_html_wrapper(html)

        assert "<html>" not in result
        assert "<body>" not in result
        assert "<table>" in result

    def test_vo020_strip_html_wrapper_no_wrapper(self):
        """VO-020: Content without wrapper is returned unchanged (stripped)."""
        html = "<table><tr><td>Y</td></tr></table>"
        result = _strip_html_wrapper(html)

        assert result == html

    def test_vo021_is_valid_table_html_true(self):
        """VO-021: Valid table HTML with tr and td returns True."""
        html = "<table><tr><td>A</td></tr></table>"
        assert _is_valid_table_html(html) is True

    def test_vo022_is_valid_table_html_false(self):
        """VO-022: Table HTML without proper cells returns False."""
        # <table> with empty <tr> — no <td> or <th>
        assert _is_valid_table_html("<table><tr></tr></table>") is False
        assert _is_valid_table_html("") is False
        assert _is_valid_table_html(None) is False

    def test_extract_text_from_table_res_tuples(self):
        """_extract_text_from_table_res extracts text from (text, conf) tuples."""
        res = {"rec_res": [("cell1", 0.9), ("cell2", 0.8)]}
        text = _extract_text_from_table_res(res)

        assert text == "cell1 cell2"

    def test_extract_text_from_table_res_strings(self):
        """_extract_text_from_table_res handles plain string items."""
        res = {"rec_res": ["alpha", "beta"]}
        text = _extract_text_from_table_res(res)

        assert text == "alpha beta"

    def test_extract_text_from_table_res_empty(self):
        """_extract_text_from_table_res returns empty string when no rec_res."""
        text = _extract_text_from_table_res({})
        assert text == ""
