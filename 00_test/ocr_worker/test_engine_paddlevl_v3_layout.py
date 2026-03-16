"""Unit tests for V3 extraction and layout intelligence — TV3-001 to TV3-049.

Tests extract_regions_v3, extract_regions_v3_ocr_fallback, _parse_v3_block,
_detect_heading_levels, _reorder_by_columns, _split_list_items,
_filter_headers_footers, _merge_adjacent_paragraphs, _extract_figure_captions,
html_table_to_markdown (colspan/rowspan), and format_structured_output.

No PPStructure or PaddleOCR dependency needed.
"""

import json
import sys
from unittest.mock import MagicMock

# Mock heavy dependencies before any engine import
sys.modules.setdefault("paddleocr", MagicMock())

import pytest

from app.engines.paddle_vl.postprocessing import (
    extract_regions_v3,
    extract_regions_v3_ocr_fallback,
    extract_regions,
    _parse_v3_block,
    _detect_heading_levels,
    _reorder_by_columns,
    _split_list_items,
    _filter_headers_footers,
    _merge_adjacent_paragraphs,
    _extract_figure_captions,
    html_table_to_markdown,
    format_structured_output,
    _V3_LABEL_MAP,
)


# ---------------------------------------------------------------------------
# Helpers — build V3-shaped data
# ---------------------------------------------------------------------------

def make_v3_parsing_result(blocks: list) -> list:
    """Wrap blocks in PaddleX PPStructureV3 format (Format A)."""
    return [{"parsing_result": blocks}]


def make_v3_text_block(
    text: str = "sample text",
    label: str = "text",
    bbox: list | None = None,
    scores: list | None = None,
):
    """Create a V3 text/title/list block."""
    return {
        "layout_label": label,
        "layout_bbox": bbox or [10, 20, 500, 50],
        "rec_texts": [text],
        "rec_scores": scores or [0.95],
    }


def make_v3_multiline_block(
    texts: list[str],
    label: str = "text",
    bbox: list | None = None,
    scores: list | None = None,
):
    """Create a V3 block with multiple text lines."""
    return {
        "layout_label": label,
        "layout_bbox": bbox or [10, 20, 500, 100],
        "rec_texts": texts,
        "rec_scores": scores or [0.95] * len(texts),
    }


def make_v3_table_block(
    html: str = "<table><tr><td>A</td><td>B</td></tr></table>",
    bbox: list | None = None,
):
    """Create a V3 table block."""
    return {
        "layout_label": "table",
        "layout_bbox": bbox or [10, 200, 500, 400],
        "table_html": html,
    }


def make_v3_figure_block(bbox: list | None = None):
    """Create a V3 figure block."""
    return {
        "layout_label": "figure",
        "layout_bbox": bbox or [10, 300, 300, 500],
    }


def make_page(regions: list, page_number: int = 1):
    return {"page_number": page_number, "regions": regions}


# ---------------------------------------------------------------------------
# Tests — _parse_v3_block (TV3-001 to TV3-006)
# ---------------------------------------------------------------------------

class TestParseV3Block:
    """TV3-001 to TV3-006: Parsing individual V3 blocks."""

    def test_tv3_001_text_block(self):
        """TV3-001: Text block parsed with correct type, content, bbox, confidence."""
        block = make_v3_text_block("Hello World", "text", [10, 20, 200, 50], [0.95])
        region = _parse_v3_block(block)

        assert region is not None
        assert region["type"] == "text"
        assert region["content"] == "Hello World"
        assert region["bbox"] == [10, 20, 200, 50]
        assert region["confidence"] == 0.95

    def test_tv3_002_title_block(self):
        """TV3-002: Title block preserves type."""
        block = make_v3_text_block("Document Title", "title", [10, 10, 400, 60])
        region = _parse_v3_block(block)

        assert region["type"] == "title"
        assert region["content"] == "Document Title"

    def test_tv3_003_table_block_valid_html(self):
        """TV3-003: Table block with valid HTML produces table region with markdown."""
        block = make_v3_table_block(
            "<table><tr><td>Col1</td><td>Col2</td></tr>"
            "<tr><td>A</td><td>B</td></tr></table>"
        )
        region = _parse_v3_block(block)

        assert region is not None
        assert region["type"] == "table"
        assert "html" in region
        assert "markdown" in region
        assert "Col1" in region["markdown"]
        assert "Col2" in region["markdown"]

    def test_tv3_004_figure_block(self):
        """TV3-004: Figure block has correct type and no content."""
        block = make_v3_figure_block([50, 100, 300, 400])
        region = _parse_v3_block(block)

        assert region is not None
        assert region["type"] == "figure"
        assert region["bbox"] == [50, 100, 300, 400]
        assert region.get("caption") is None

    def test_tv3_005_list_block(self):
        """TV3-005: List block preserves type."""
        block = make_v3_text_block("- Item one", "list", [10, 50, 300, 80])
        region = _parse_v3_block(block)

        assert region["type"] == "list"
        assert region["content"] == "- Item one"

    def test_tv3_006_empty_block_returns_none(self):
        """TV3-006: Block with no text content returns None."""
        block = {"layout_label": "text", "layout_bbox": [0, 0, 100, 50], "rec_texts": []}
        region = _parse_v3_block(block)

        assert region is None

    def test_tv3_006b_whitespace_only_returns_none(self):
        """TV3-006b: Block with only whitespace returns None."""
        block = make_v3_text_block("   ", "text")
        region = _parse_v3_block(block)

        assert region is None

    def test_tv3_006c_label_mapping(self):
        """TV3-006c: PaddleX labels are mapped to standard types."""
        assert _V3_LABEL_MAP["paragraph"] == "text"
        assert _V3_LABEL_MAP["table_body"] == "table"
        assert _V3_LABEL_MAP["image"] == "figure"
        assert _V3_LABEL_MAP["list_item"] == "list"

    def test_tv3_006d_paragraph_label_mapped_to_text(self):
        """TV3-006d: 'paragraph' label becomes 'text' type."""
        block = {
            "layout_label": "paragraph",
            "layout_bbox": [10, 10, 200, 50],
            "rec_texts": ["Some paragraph"],
            "rec_scores": [0.9],
        }
        region = _parse_v3_block(block)

        assert region["type"] == "text"

    def test_tv3_006e_table_invalid_html_fallback_to_text(self):
        """TV3-006e: Table with invalid HTML falls back to text from rec_texts."""
        block = {
            "layout_label": "table",
            "layout_bbox": [10, 100, 400, 300],
            "table_html": "<table></table>",
            "rec_texts": ["cell1", "cell2"],
        }
        region = _parse_v3_block(block)

        assert region is not None
        assert region["type"] == "text"
        assert "cell1" in region["content"]

    def test_tv3_006f_table_no_html_no_text_returns_none(self):
        """TV3-006f: Table with no HTML and no text returns None."""
        block = {
            "layout_label": "table",
            "layout_bbox": [10, 100, 400, 300],
            "table_html": "",
        }
        region = _parse_v3_block(block)

        assert region is None

    def test_tv3_006g_multiline_content(self):
        """TV3-006g: Multiple rec_texts are joined with newlines."""
        block = make_v3_multiline_block(["Line 1", "Line 2", "Line 3"])
        region = _parse_v3_block(block)

        assert region["content"] == "Line 1\nLine 2\nLine 3"

    def test_tv3_006h_fallback_content_key(self):
        """TV3-006h: Block with 'content' key instead of rec_texts is handled."""
        block = {
            "layout_label": "text",
            "layout_bbox": [10, 10, 200, 50],
            "content": "Fallback content",
        }
        region = _parse_v3_block(block)

        assert region is not None
        assert region["content"] == "Fallback content"

    def test_tv3_006i_fallback_type_key(self):
        """TV3-006i: Block with 'type' key instead of layout_label is handled."""
        block = {
            "type": "title",
            "bbox": [10, 10, 200, 50],
            "rec_texts": ["Title via type key"],
            "rec_scores": [0.99],
        }
        region = _parse_v3_block(block)

        assert region["type"] == "title"
        assert region["content"] == "Title via type key"
        assert region["bbox"] == [10, 10, 200, 50]


# ---------------------------------------------------------------------------
# Tests — extract_regions_v3 (TV3-007 to TV3-012)
# ---------------------------------------------------------------------------

class TestExtractRegionsV3:
    """TV3-007 to TV3-012: Full V3 extraction pipeline."""

    def test_tv3_007_format_a_parsing_result(self):
        """TV3-007: PaddleX format with parsing_result is parsed correctly."""
        blocks = [
            make_v3_text_block("Title", "title", [10, 10, 400, 60]),
            make_v3_text_block("Body text", "text", [10, 70, 400, 120]),
            make_v3_table_block(
                "<table><tr><td>X</td></tr></table>", [10, 130, 400, 250]
            ),
        ]
        results = make_v3_parsing_result(blocks)
        page = extract_regions_v3(results, 0)

        assert page["page_number"] == 1
        assert len(page["regions"]) == 3

        types = [r["type"] for r in page["regions"]]
        assert "title" in types
        assert "text" in types
        assert "table" in types

    def test_tv3_008_format_b_direct_blocks(self):
        """TV3-008: Direct block format (each result is a block)."""
        results = [
            {
                "layout_label": "title",
                "layout_bbox": [10, 10, 400, 50],
                "rec_texts": ["Main Title"],
                "rec_scores": [0.99],
            },
            {
                "layout_label": "text",
                "layout_bbox": [10, 60, 400, 120],
                "rec_texts": ["Paragraph content"],
                "rec_scores": [0.95],
            },
        ]
        page = extract_regions_v3(results, 0)

        assert len(page["regions"]) == 2
        assert page["regions"][0]["type"] == "title"
        assert page["regions"][1]["type"] == "text"

    def test_tv3_009_format_c_legacy_flat(self):
        """TV3-009: Legacy format with flat rec_texts (no layout info)."""
        results = [
            {
                "rec_texts": ["Line 1", "Line 2"],
                "rec_scores": [0.9, 0.85],
            },
        ]
        page = extract_regions_v3(results, 0)

        assert len(page["regions"]) == 1
        assert page["regions"][0]["type"] == "text"
        assert "Line 1\nLine 2" == page["regions"][0]["content"]

    def test_tv3_010_empty_results(self):
        """TV3-010: Empty results return empty regions."""
        page = extract_regions_v3([], 0)
        assert page["page_number"] == 1
        assert page["regions"] == []

    def test_tv3_011_none_results(self):
        """TV3-011: None results return empty regions."""
        page = extract_regions_v3(None, 0)
        assert page["regions"] == []

    def test_tv3_012_reading_order_sorted(self):
        """TV3-012: Regions are sorted by reading order (y then x)."""
        blocks = [
            make_v3_text_block("Bottom", "text", [10, 200, 400, 230]),
            make_v3_text_block("Top", "text", [10, 10, 400, 40]),
            make_v3_text_block("Middle", "text", [10, 100, 400, 130]),
        ]
        results = make_v3_parsing_result(blocks)
        page = extract_regions_v3(results, 0)

        contents = [r["content"] for r in page["regions"]]
        assert contents == ["Top", "Middle", "Bottom"]

    def test_tv3_012b_mixed_formats_in_same_result(self):
        """TV3-012b: A result with parsing_result uses Format A, ignores others."""
        results = [
            {
                "parsing_result": [
                    make_v3_text_block("From parsing_result", "text"),
                ],
                "rec_texts": ["Should be ignored"],
            },
        ]
        page = extract_regions_v3(results, 0)

        assert len(page["regions"]) == 1
        assert page["regions"][0]["content"] == "From parsing_result"


# ---------------------------------------------------------------------------
# Tests — extract_regions_v3_ocr_fallback (TV3-013 to TV3-016)
# ---------------------------------------------------------------------------

class TestExtractRegionsV3OcrFallback:
    """TV3-013 to TV3-016: V3 pure OCR fallback extraction."""

    def test_tv3_013_basic_ocr_fallback(self):
        """TV3-013: OCR fallback extracts text lines from rec_texts."""
        results = [
            {
                "rec_texts": ["Hello", "World"],
                "rec_scores": [0.95, 0.90],
                "rec_polys": [
                    [[10, 10], [100, 10], [100, 30], [10, 30]],
                    [[10, 40], [100, 40], [100, 60], [10, 60]],
                ],
            },
        ]
        page = extract_regions_v3_ocr_fallback(results, 0)

        assert page["page_number"] == 1
        assert len(page["regions"]) == 2
        assert page["regions"][0]["content"] == "Hello"
        assert page["regions"][0]["confidence"] == 0.95
        assert page["regions"][0]["bbox"] == [10, 10, 100, 30]
        assert page["regions"][1]["content"] == "World"

    def test_tv3_014_empty_ocr_fallback(self):
        """TV3-014: Empty results return empty regions."""
        page = extract_regions_v3_ocr_fallback([], 0)
        assert page["regions"] == []

    def test_tv3_015_skips_blank_text(self):
        """TV3-015: Blank text lines are skipped."""
        results = [
            {
                "rec_texts": ["", "  ", "Real text"],
                "rec_scores": [0.5, 0.5, 0.9],
                "rec_polys": [None, None, [[0, 0], [50, 0], [50, 20], [0, 20]]],
            },
        ]
        page = extract_regions_v3_ocr_fallback(results, 0)

        assert len(page["regions"]) == 1
        assert page["regions"][0]["content"] == "Real text"

    def test_tv3_016_no_polys_uses_zero_bbox(self):
        """TV3-016: Missing polys default to [0,0,0,0] bbox."""
        results = [{"rec_texts": ["No poly"], "rec_scores": [0.8], "rec_polys": []}]
        page = extract_regions_v3_ocr_fallback(results, 0)

        assert len(page["regions"]) == 1
        assert page["regions"][0]["bbox"] == [0, 0, 0, 0]


# ---------------------------------------------------------------------------
# Tests — text joining fix (TV3-017)
# ---------------------------------------------------------------------------

class TestTextJoiningFix:
    """TV3-017: Verify text joining preserves line breaks."""

    def test_tv3_017_v2_text_join_uses_newline(self):
        """TV3-017: V2 extract_regions joins multiple text items with newline."""
        raw = [
            {
                "type": "text",
                "bbox": [0, 0, 200, 60],
                "res": [
                    {"text": "First line", "confidence": 0.95},
                    {"text": "Second line", "confidence": 0.90},
                ],
            }
        ]
        result = extract_regions(raw, 0)

        r = result["regions"][0]
        assert r["content"] == "First line\nSecond line"

    def test_tv3_017b_v3_text_join_uses_newline(self):
        """TV3-017b: V3 extraction joins rec_texts with newline."""
        blocks = [make_v3_multiline_block(["Para line 1", "Para line 2"])]
        results = make_v3_parsing_result(blocks)
        page = extract_regions_v3(results, 0)

        assert page["regions"][0]["content"] == "Para line 1\nPara line 2"


# ---------------------------------------------------------------------------
# Tests — _detect_heading_levels (TV3-018 to TV3-022)
# ---------------------------------------------------------------------------

class TestDetectHeadingLevels:
    """TV3-018 to TV3-022: Heading level detection."""

    def test_tv3_018_single_title_is_h1(self):
        """TV3-018: Single title gets heading_level=1."""
        regions = [
            {"type": "title", "bbox": [0, 0, 400, 60], "content": "Main Title"},
        ]
        _detect_heading_levels(regions)

        assert regions[0]["heading_level"] == 1

    def test_tv3_019_two_heights_h1_h2(self):
        """TV3-019: Two distinct heights → larger=h1, smaller=h2."""
        regions = [
            {"type": "title", "bbox": [0, 0, 400, 60], "content": "Big Title"},
            {"type": "title", "bbox": [0, 100, 400, 130], "content": "Small Title"},
            {"type": "text", "bbox": [0, 140, 400, 170], "content": "Body"},
        ]
        _detect_heading_levels(regions)

        assert regions[0]["heading_level"] == 1  # height=60
        assert regions[1]["heading_level"] == 2  # height=30
        # text region should not have heading_level
        assert "heading_level" not in regions[2]

    def test_tv3_020_same_height_all_h1(self):
        """TV3-020: All titles with same height get h1."""
        regions = [
            {"type": "title", "bbox": [0, 0, 400, 40], "content": "Title A"},
            {"type": "title", "bbox": [0, 100, 400, 140], "content": "Title B"},
        ]
        _detect_heading_levels(regions)

        assert regions[0]["heading_level"] == 1
        assert regions[1]["heading_level"] == 1

    def test_tv3_021_three_heights_h1_h2_h3(self):
        """TV3-021: Three distinct heights → h1/h2/h3."""
        regions = [
            {"type": "title", "bbox": [0, 0, 400, 80], "content": "H1"},     # height=80
            {"type": "title", "bbox": [0, 100, 400, 150], "content": "H2"},   # height=50
            {"type": "title", "bbox": [0, 200, 400, 220], "content": "H3"},   # height=20
            {"type": "title", "bbox": [0, 250, 400, 330], "content": "H1b"},  # height=80
        ]
        _detect_heading_levels(regions)

        # H1 (height=80) should be level 1
        assert regions[0]["heading_level"] == 1
        assert regions[3]["heading_level"] == 1
        # H2 (height=50) should be level 2
        assert regions[1]["heading_level"] == 2
        # H3 (height=20) should be level 3
        assert regions[2]["heading_level"] == 3

    def test_tv3_022_no_titles_no_change(self):
        """TV3-022: No title regions → no changes."""
        regions = [
            {"type": "text", "bbox": [0, 0, 400, 30], "content": "Body text"},
        ]
        _detect_heading_levels(regions)

        assert "heading_level" not in regions[0]

    def test_tv3_022b_titles_without_bbox_skipped(self):
        """TV3-022b: Titles without valid bbox are skipped."""
        regions = [
            {"type": "title", "bbox": [], "content": "No bbox"},
            {"type": "title", "bbox": [0, 0, 400, 50], "content": "Has bbox"},
        ]
        _detect_heading_levels(regions)

        assert "heading_level" not in regions[0]
        assert regions[1]["heading_level"] == 1


# ---------------------------------------------------------------------------
# Tests — _reorder_by_columns (TV3-023 to TV3-026)
# ---------------------------------------------------------------------------

class TestReorderByColumns:
    """TV3-023 to TV3-026: Column detection and reordering."""

    def test_tv3_023_single_column_unchanged(self):
        """TV3-023: Single-column layout is not reordered."""
        regions = [
            {"type": "text", "bbox": [10, 10, 500, 40], "content": "Line 1"},
            {"type": "text", "bbox": [10, 50, 500, 80], "content": "Line 2"},
            {"type": "text", "bbox": [10, 90, 500, 120], "content": "Line 3"},
        ]
        result = _reorder_by_columns(regions)

        contents = [r["content"] for r in result]
        assert contents == ["Line 1", "Line 2", "Line 3"]

    def test_tv3_024_two_columns_reordered(self):
        """TV3-024: Two-column layout reads left column first, then right."""
        # Page width ~1000px. Left column: x 10-450. Right column: x 550-990.
        regions = [
            {"type": "text", "bbox": [10, 10, 450, 40], "content": "Left 1"},
            {"type": "text", "bbox": [550, 10, 990, 40], "content": "Right 1"},
            {"type": "text", "bbox": [10, 50, 450, 80], "content": "Left 2"},
            {"type": "text", "bbox": [550, 50, 990, 80], "content": "Right 2"},
        ]
        result = _reorder_by_columns(regions)

        contents = [r["content"] for r in result]
        assert contents == ["Left 1", "Left 2", "Right 1", "Right 2"]

    def test_tv3_025_full_width_title_preserved(self):
        """TV3-025: Full-width title stays at correct position."""
        regions = [
            {"type": "title", "bbox": [10, 10, 990, 60], "content": "Full Title"},
            {"type": "text", "bbox": [10, 70, 450, 100], "content": "Left"},
            {"type": "text", "bbox": [550, 70, 990, 100], "content": "Right"},
            {"type": "text", "bbox": [10, 110, 450, 140], "content": "Left 2"},
        ]
        result = _reorder_by_columns(regions)

        # Title should come first (full-width, y=10 before others at y=70)
        assert result[0]["content"] == "Full Title"
        # Then left column
        assert result[1]["content"] == "Left"
        assert result[2]["content"] == "Left 2"
        # Then right column
        assert result[3]["content"] == "Right"

    def test_tv3_026_too_few_regions_unchanged(self):
        """TV3-026: Fewer than 3 regions are not reordered."""
        regions = [
            {"type": "text", "bbox": [10, 10, 200, 40], "content": "A"},
            {"type": "text", "bbox": [500, 10, 900, 40], "content": "B"},
        ]
        result = _reorder_by_columns(regions)

        assert result == regions

    def test_tv3_026b_no_clear_gap_unchanged(self):
        """TV3-026b: No clear column gap → no reordering."""
        # All regions are close together (no column gap)
        regions = [
            {"type": "text", "bbox": [10, 10, 300, 40], "content": "A"},
            {"type": "text", "bbox": [290, 50, 600, 80], "content": "B"},
            {"type": "text", "bbox": [10, 90, 300, 120], "content": "C"},
        ]
        result = _reorder_by_columns(regions)

        # Should not reorder (overlap means no clear column gap)
        contents = [r["content"] for r in result]
        assert contents == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Tests — _split_list_items (TV3-027 to TV3-029)
# ---------------------------------------------------------------------------

class TestSplitListItems:
    """TV3-027 to TV3-029: List item splitting."""

    def test_tv3_027_newline_separated(self):
        """TV3-027: Items separated by newlines are split."""
        items = _split_list_items("Item one\nItem two\nItem three")
        assert items == ["Item one", "Item two", "Item three"]

    def test_tv3_028_bullet_markers_stripped(self):
        """TV3-028: Bullet markers are stripped from items."""
        items = _split_list_items("- First\n• Second\n* Third")
        assert items == ["First", "Second", "Third"]

    def test_tv3_028b_numbered_markers_stripped(self):
        """TV3-028b: Numbered markers are stripped."""
        items = _split_list_items("1. First\n2) Second\n3. Third")
        assert items == ["First", "Second", "Third"]

    def test_tv3_029_single_item_fallback(self):
        """TV3-029: Single item without markers returns as-is."""
        items = _split_list_items("Just one item")
        assert items == ["Just one item"]

    def test_tv3_029b_empty_content(self):
        """TV3-029b: Empty content returns empty list."""
        assert _split_list_items("") == []
        assert _split_list_items("   ") == []


# ---------------------------------------------------------------------------
# Tests — format_structured_output with layout enhancements (TV3-030)
# ---------------------------------------------------------------------------

class TestFormatWithLayoutEnhancements:
    """TV3-030: Format output with heading levels and column reorder."""

    def _make_pages_with_headings(self):
        return [make_page([
            {"type": "title", "bbox": [0, 0, 400, 60], "content": "Main Title",
             "confidence": 0.99},
            {"type": "text", "bbox": [0, 70, 400, 120], "content": "Body text.",
             "confidence": 0.95},
            {"type": "title", "bbox": [0, 130, 400, 160], "content": "Subtitle",
             "confidence": 0.98},
            {"type": "text", "bbox": [0, 170, 400, 220], "content": "More text.",
             "confidence": 0.92},
        ])]

    def test_tv3_030_markdown_heading_levels(self):
        """TV3-030: Markdown output uses ## for smaller titles."""
        pages = self._make_pages_with_headings()
        result = format_structured_output(pages, "md")
        text = result.decode("utf-8")

        # Main Title (height=60) → h1, Subtitle (height=30) → h2
        assert "# Main Title" in text
        assert "## Subtitle" in text
        # Verify h1 is NOT ##
        assert "## Main Title" not in text
        assert "Body text." in text

    def test_tv3_030b_html_heading_levels(self):
        """TV3-030b: HTML output uses <h1> and <h2> tags."""
        pages = self._make_pages_with_headings()
        result = format_structured_output(pages, "html")
        text = result.decode("utf-8")

        assert "<h1>Main Title</h1>" in text
        assert "<h2>Subtitle</h2>" in text

    def test_tv3_030c_json_includes_heading_level(self):
        """TV3-030c: JSON output includes heading_level in region data."""
        pages = self._make_pages_with_headings()
        result = format_structured_output(pages, "json")
        parsed = json.loads(result)

        titles = [
            r for r in parsed["pages"][0]["regions"] if r["type"] == "title"
        ]
        assert titles[0]["heading_level"] == 1
        assert titles[1]["heading_level"] == 2

    def test_tv3_030d_markdown_list_split(self):
        """TV3-030d: Markdown output splits list items."""
        pages = [make_page([
            {"type": "list", "bbox": [0, 0, 400, 100],
             "content": "- Apple\n- Banana\n- Cherry"},
        ])]
        result = format_structured_output(pages, "md")
        text = result.decode("utf-8")

        assert "- Apple" in text
        assert "- Banana" in text
        assert "- Cherry" in text

    def test_tv3_030e_html_list_split(self):
        """TV3-030e: HTML output splits list items into <li> tags."""
        pages = [make_page([
            {"type": "list", "bbox": [0, 0, 400, 100],
             "content": "Item A\nItem B"},
        ])]
        result = format_structured_output(pages, "html")
        text = result.decode("utf-8")

        assert "<li>Item A</li>" in text
        assert "<li>Item B</li>" in text

    def test_tv3_030f_plain_text_fallback(self):
        """TV3-030f: Plain text output still works with layout enhancements."""
        pages = [make_page([
            {"type": "title", "bbox": [0, 0, 400, 60], "content": "Title"},
            {"type": "text", "bbox": [0, 70, 400, 100], "content": "Body"},
        ])]
        result = format_structured_output(pages, "txt")
        text = result.decode("utf-8")

        assert "Title" in text
        assert "Body" in text


# ===========================================================================
# Sprint 3 — Tests TV3-031 to TV3-049
# ===========================================================================


# ---------------------------------------------------------------------------
# Tests — _filter_headers_footers (TV3-031 to TV3-035)
# ---------------------------------------------------------------------------

class TestFilterHeadersFooters:
    """TV3-031 to TV3-035: Header/footer detection and removal."""

    @staticmethod
    def _make_multipage_doc(num_pages: int = 5, page_height: int = 1000):
        """Build a multi-page document with repeating header/footer."""
        pages = []
        for i in range(num_pages):
            regions = [
                # Repeating header (top 5%)
                {"type": "text", "bbox": [10, 10, 400, 40],
                 "content": "Company Report 2026", "confidence": 0.95},
                # Body
                {"type": "title", "bbox": [10, 100, 400, 150],
                 "content": f"Section {i + 1}", "confidence": 0.99},
                {"type": "text", "bbox": [10, 160, 400, 500],
                 "content": f"Content of section {i + 1}.", "confidence": 0.92},
                # Repeating footer with page number
                {"type": "text", "bbox": [10, 950, 400, 990],
                 "content": f"Page {i + 1}", "confidence": 0.90},
            ]
            pages.append(make_page(regions, page_number=i + 1))
        return pages

    def test_tv3_031_filters_repeating_header(self):
        """TV3-031: Repeating header text removed across pages."""
        pages = self._make_multipage_doc(5)
        _filter_headers_footers(pages)

        for page in pages:
            contents = [r.get("content", "") for r in page["regions"]]
            assert "Company Report 2026" not in contents

    def test_tv3_032_filters_page_numbers(self):
        """TV3-032: Page number patterns at bottom are filtered."""
        pages = self._make_multipage_doc(5)
        _filter_headers_footers(pages)

        for page in pages:
            contents = [r.get("content", "") for r in page["regions"]]
            for c in contents:
                assert not c.startswith("Page ")

    def test_tv3_033_body_content_preserved(self):
        """TV3-033: Non-repeating body content is preserved."""
        pages = self._make_multipage_doc(5)
        _filter_headers_footers(pages)

        for i, page in enumerate(pages):
            contents = [r.get("content", "") for r in page["regions"]]
            assert f"Section {i + 1}" in contents
            assert f"Content of section {i + 1}." in contents

    def test_tv3_034_skips_fewer_than_3_pages(self):
        """TV3-034: No filtering when document has < 3 pages."""
        pages = self._make_multipage_doc(2)
        total_before = sum(len(p["regions"]) for p in pages)
        _filter_headers_footers(pages)
        total_after = sum(len(p["regions"]) for p in pages)

        assert total_after == total_before

    def test_tv3_035_non_repeating_top_bottom_kept(self):
        """TV3-035: Unique text at top/bottom is not removed."""
        unique_headers = [
            "Introduction", "Background Analysis",
            "Results Discussion", "Final Conclusion",
        ]
        pages = []
        for i in range(4):
            regions = [
                # Unique header per page (genuinely different text)
                {"type": "text", "bbox": [10, 10, 400, 40],
                 "content": unique_headers[i], "confidence": 0.9},
                # Body in the middle zone (not top/bottom 8%)
                {"type": "text", "bbox": [10, 200, 400, 500],
                 "content": f"Body of section {unique_headers[i]}", "confidence": 0.95},
                # Bottom anchor to set page height ~ 1000
                {"type": "text", "bbox": [10, 800, 400, 850],
                 "content": f"Conclusion for {unique_headers[i]}", "confidence": 0.90},
            ]
            pages.append(make_page(regions, page_number=i + 1))

        total_before = sum(len(p["regions"]) for p in pages)
        _filter_headers_footers(pages)
        total_after = sum(len(p["regions"]) for p in pages)

        # No regions removed (all content is unique per page)
        assert total_after == total_before


# ---------------------------------------------------------------------------
# Tests — html_table_to_markdown colspan/rowspan (TV3-036 to TV3-039)
# ---------------------------------------------------------------------------

class TestTableColspanRowspan:
    """TV3-036 to TV3-039: Table parsing with colspan and rowspan."""

    def test_tv3_036_colspan(self):
        """TV3-036: colspan=2 expands cell across columns."""
        html = (
            "<table>"
            '<tr><td colspan="2">Merged</td><td>C</td></tr>'
            "<tr><td>A</td><td>B</td><td>C</td></tr>"
            "</table>"
        )
        md = html_table_to_markdown(html)

        lines = md.strip().split("\n")
        # Header row should have 3 columns, first two are "Merged"
        assert lines[0].count("|") >= 4  # | Merged | Merged | C |
        assert "Merged" in lines[0]
        assert "A" in lines[2]
        assert "B" in lines[2]

    def test_tv3_037_rowspan(self):
        """TV3-037: rowspan=2 fills cell in subsequent row."""
        html = (
            "<table>"
            '<tr><td rowspan="2">Span</td><td>B1</td></tr>'
            "<tr><td>B2</td></tr>"
            "</table>"
        )
        md = html_table_to_markdown(html)

        lines = md.strip().split("\n")
        # Both data rows should contain "Span"
        assert "Span" in lines[0]
        assert "Span" in lines[2]
        assert "B1" in lines[0]
        assert "B2" in lines[2]

    def test_tv3_038_simple_table_unchanged(self):
        """TV3-038: Simple table without spans still works correctly."""
        html = (
            "<table>"
            "<tr><th>H1</th><th>H2</th></tr>"
            "<tr><td>A</td><td>B</td></tr>"
            "</table>"
        )
        md = html_table_to_markdown(html)

        assert "H1" in md
        assert "H2" in md
        assert "A" in md
        assert "B" in md
        assert "---" in md  # separator row

    def test_tv3_039_mixed_colspan_rowspan(self):
        """TV3-039: Table with both colspan and rowspan."""
        html = (
            "<table>"
            '<tr><td colspan="2">Wide</td></tr>'
            '<tr><td rowspan="2">Tall</td><td>R2C2</td></tr>'
            "<tr><td>R3C2</td></tr>"
            "</table>"
        )
        md = html_table_to_markdown(html)

        assert "Wide" in md
        assert "Tall" in md
        assert "R2C2" in md
        assert "R3C2" in md


# ---------------------------------------------------------------------------
# Tests — _merge_adjacent_paragraphs (TV3-040 to TV3-043)
# ---------------------------------------------------------------------------

class TestMergeAdjacentParagraphs:
    """TV3-040 to TV3-043: Paragraph merging for adjacent text regions."""

    def test_tv3_040_adjacent_text_merged(self):
        """TV3-040: Two close text regions in same column are merged."""
        regions = [
            {"type": "text", "bbox": [10, 10, 400, 40], "content": "First part.",
             "confidence": 0.95},
            {"type": "text", "bbox": [10, 42, 400, 72], "content": "Second part.",
             "confidence": 0.90},
        ]
        result = _merge_adjacent_paragraphs(regions)

        assert len(result) == 1
        assert "First part." in result[0]["content"]
        assert "Second part." in result[0]["content"]

    def test_tv3_041_different_types_not_merged(self):
        """TV3-041: Title followed by text is not merged."""
        regions = [
            {"type": "title", "bbox": [10, 10, 400, 50], "content": "Title",
             "confidence": 0.99},
            {"type": "text", "bbox": [10, 52, 400, 82], "content": "Body",
             "confidence": 0.95},
        ]
        result = _merge_adjacent_paragraphs(regions)

        assert len(result) == 2

    def test_tv3_042_distant_text_not_merged(self):
        """TV3-042: Text regions far apart vertically are not merged."""
        regions = [
            {"type": "text", "bbox": [10, 10, 400, 40], "content": "Top",
             "confidence": 0.95},
            {"type": "text", "bbox": [10, 300, 400, 330], "content": "Bottom",
             "confidence": 0.90},
        ]
        result = _merge_adjacent_paragraphs(regions)

        assert len(result) == 2

    def test_tv3_043_different_columns_not_merged(self):
        """TV3-043: Text regions in different columns are not merged."""
        regions = [
            {"type": "text", "bbox": [10, 10, 200, 40], "content": "Left col",
             "confidence": 0.95},
            {"type": "text", "bbox": [500, 12, 700, 42], "content": "Right col",
             "confidence": 0.90},
        ]
        result = _merge_adjacent_paragraphs(regions)

        assert len(result) == 2

    def test_tv3_043b_merged_bbox_expanded(self):
        """TV3-043b: Merged region bbox spans both originals."""
        regions = [
            {"type": "text", "bbox": [10, 10, 400, 40], "content": "A",
             "confidence": 0.90},
            {"type": "text", "bbox": [15, 42, 395, 72], "content": "B",
             "confidence": 0.80},
        ]
        result = _merge_adjacent_paragraphs(regions)

        assert len(result) == 1
        assert result[0]["bbox"] == [10, 10, 400, 72]


# ---------------------------------------------------------------------------
# Tests — _extract_figure_captions (TV3-044 to TV3-047)
# ---------------------------------------------------------------------------

class TestExtractFigureCaptions:
    """TV3-044 to TV3-047: Figure caption extraction."""

    def test_tv3_044_figure_with_caption(self):
        """TV3-044: Text starting with 'Figure' is assigned as caption."""
        regions = [
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
            {"type": "text", "bbox": [10, 310, 400, 340],
             "content": "Figure 1. Architecture diagram", "confidence": 0.9},
        ]
        _extract_figure_captions(regions)

        assert regions[0]["caption"] == "Figure 1. Architecture diagram"
        assert len(regions) == 1  # caption text region consumed

    def test_tv3_045_figure_with_vietnamese_caption(self):
        """TV3-045: Vietnamese caption keyword 'Hình' is recognized."""
        regions = [
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
            {"type": "text", "bbox": [10, 310, 400, 340],
             "content": "Hình 2. Sơ đồ kiến trúc", "confidence": 0.9},
        ]
        _extract_figure_captions(regions)

        assert regions[0]["caption"] == "Hình 2. Sơ đồ kiến trúc"
        assert len(regions) == 1

    def test_tv3_046_figure_without_caption(self):
        """TV3-046: Regular text after figure is not consumed as caption."""
        regions = [
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
            {"type": "text", "bbox": [10, 310, 400, 340],
             "content": "The results show that...", "confidence": 0.9},
        ]
        _extract_figure_captions(regions)

        assert regions[0]["caption"] is None
        assert len(regions) == 2

    def test_tv3_047_no_adjacent_text(self):
        """TV3-047: Figure at end of page with no next region."""
        regions = [
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
        ]
        _extract_figure_captions(regions)

        assert regions[0]["caption"] is None
        assert len(regions) == 1


# ---------------------------------------------------------------------------
# Tests — format_structured_output with Sprint 3 features (TV3-048 to TV3-049)
# ---------------------------------------------------------------------------

class TestFormatWithSprint3Features:
    """TV3-048 to TV3-049: Full pipeline with Sprint 3 enhancements."""

    def test_tv3_048_markdown_figure_caption(self):
        """TV3-048: Markdown output shows figure with caption."""
        pages = [make_page([
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
            {"type": "text", "bbox": [10, 310, 400, 340],
             "content": "Figure 1. Test image", "confidence": 0.9},
        ])]
        result = format_structured_output(pages, "md")
        text = result.decode("utf-8")

        assert "*[Figure: Figure 1. Test image]*" in text

    def test_tv3_049_html_figure_caption(self):
        """TV3-049: HTML output wraps figure caption in <figcaption>."""
        pages = [make_page([
            {"type": "figure", "bbox": [10, 10, 400, 300], "caption": None},
            {"type": "text", "bbox": [10, 310, 400, 340],
             "content": "Fig. 3 System overview", "confidence": 0.9},
        ])]
        result = format_structured_output(pages, "html")
        text = result.decode("utf-8")

        assert "<figcaption>" in text
        assert "Fig. 3 System overview" in text
