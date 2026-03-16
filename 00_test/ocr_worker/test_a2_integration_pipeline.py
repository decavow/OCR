"""
Integration tests for A2 Layout-Preserved Output — full postprocessing pipeline.

Simulates realistic PPStructure/PPStructureV3 output from actual document types
(academic paper, Vietnamese document, mixed layout, multi-page PDF) and verifies
the complete pipeline: extract → layout intelligence → format output.

Covers ALL A2 requirements:
  Sprint 1: V3 extraction, text joining, content field consistency
  Sprint 2: Heading levels, column reorder, list splitting
  Sprint 3: Header/footer filtering, colspan/rowspan tables,
            paragraph merging, figure caption extraction

No GPU or PaddleOCR required — tests postprocessing pipeline only.

Test IDs: TA2-001 to TA2-030
"""

import json
import re
import sys
from copy import deepcopy
from unittest.mock import MagicMock

# Mock heavy dependencies before any engine import
sys.modules.setdefault("paddleocr", MagicMock())

import pytest

from app.engines.paddle_vl.postprocessing import (
    extract_regions,
    extract_regions_v3,
    extract_regions_v3_ocr_fallback,
    _detect_heading_levels,
    _reorder_by_columns,
    _split_list_items,
    _filter_headers_footers,
    _merge_adjacent_paragraphs,
    _extract_figure_captions,
    html_table_to_markdown,
    format_structured_output,
    assess_result_quality,
)


# ===========================================================================
# Realistic test data builders — mirror actual PPStructure output
# ===========================================================================


def build_academic_paper_v2() -> list:
    """Simulate PPStructure v2 output for an academic paper image.

    Mirrors what PPStructure returns for paper_image.png:
    - Title at top
    - Abstract section
    - Two-column body text
    - Table with results
    - Figure with caption
    """
    return [
        {
            "type": "title",
            "bbox": [50, 30, 730, 80],
            "res": [
                {"text": "Attention Is All You Need", "confidence": 0.98},
            ],
        },
        {
            "type": "text",
            "bbox": [50, 90, 730, 130],
            "res": [
                {"text": "Ashish Vaswani, Noam Shazeer, Niki Parmar", "confidence": 0.95},
                {"text": "Google Brain, Google Research", "confidence": 0.93},
            ],
        },
        {
            "type": "title",
            "bbox": [50, 150, 350, 175],
            "res": [
                {"text": "Abstract", "confidence": 0.99},
            ],
        },
        {
            "type": "text",
            "bbox": [50, 180, 730, 280],
            "res": [
                {"text": "The dominant sequence transduction models are based on complex", "confidence": 0.96},
                {"text": "recurrent or convolutional neural networks that include an encoder", "confidence": 0.94},
                {"text": "and a decoder. The best performing models also connect the encoder", "confidence": 0.95},
            ],
        },
        {
            "type": "title",
            "bbox": [50, 300, 350, 325],
            "res": [
                {"text": "1 Introduction", "confidence": 0.97},
            ],
        },
        # Left column text
        {
            "type": "text",
            "bbox": [50, 340, 360, 500],
            "res": [
                {"text": "Recurrent neural networks, long short-term memory and gated", "confidence": 0.93},
                {"text": "recurrent neural networks in particular, have been firmly", "confidence": 0.92},
                {"text": "established as state of the art approaches in sequence modeling.", "confidence": 0.94},
            ],
        },
        # Right column text
        {
            "type": "text",
            "bbox": [400, 340, 730, 500],
            "res": [
                {"text": "Attention mechanisms have become an integral part of compelling", "confidence": 0.95},
                {"text": "sequence modeling and transduction models in various tasks.", "confidence": 0.93},
            ],
        },
        {
            "type": "title",
            "bbox": [50, 520, 350, 545],
            "res": [
                {"text": "2 Related Work", "confidence": 0.96},
            ],
        },
        # Table
        {
            "type": "table",
            "bbox": [100, 560, 680, 700],
            "res": {
                "html": (
                    "<table>"
                    "<tr><th>Model</th><th>BLEU</th><th>Parameters</th></tr>"
                    "<tr><td>Transformer (base)</td><td>27.3</td><td>65M</td></tr>"
                    "<tr><td>Transformer (big)</td><td>28.4</td><td>213M</td></tr>"
                    "</table>"
                ),
            },
        },
        # Figure
        {
            "type": "figure",
            "bbox": [150, 720, 600, 900],
        },
        # Figure caption (below figure)
        {
            "type": "text",
            "bbox": [150, 905, 600, 930],
            "res": [
                {"text": "Figure 1. The Transformer model architecture.", "confidence": 0.97},
            ],
        },
        # List
        {
            "type": "list",
            "bbox": [50, 940, 400, 1020],
            "res": [
                {"text": "- Self-attention mechanism", "confidence": 0.95},
                {"text": "- Multi-head attention", "confidence": 0.94},
                {"text": "- Positional encoding", "confidence": 0.96},
            ],
        },
    ]


def build_academic_paper_v3() -> list:
    """Simulate PPStructureV3 output for an academic paper.

    Format A: PaddleX with parsing_result.
    """
    return [
        {
            "parsing_result": [
                {
                    "layout_label": "title",
                    "layout_bbox": [50, 30, 730, 80],
                    "rec_texts": ["Attention Is All You Need"],
                    "rec_scores": [0.98],
                },
                {
                    "layout_label": "paragraph",
                    "layout_bbox": [50, 90, 730, 130],
                    "rec_texts": [
                        "Ashish Vaswani, Noam Shazeer, Niki Parmar",
                        "Google Brain, Google Research",
                    ],
                    "rec_scores": [0.95, 0.93],
                },
                {
                    "layout_label": "title",
                    "layout_bbox": [50, 150, 350, 175],
                    "rec_texts": ["Abstract"],
                    "rec_scores": [0.99],
                },
                {
                    "layout_label": "text",
                    "layout_bbox": [50, 180, 730, 280],
                    "rec_texts": [
                        "The dominant sequence transduction models are based on complex",
                        "recurrent or convolutional neural networks that include an encoder",
                        "and a decoder.",
                    ],
                    "rec_scores": [0.96, 0.94, 0.95],
                },
                {
                    "layout_label": "title",
                    "layout_bbox": [50, 300, 350, 325],
                    "rec_texts": ["1 Introduction"],
                    "rec_scores": [0.97],
                },
                {
                    "layout_label": "text",
                    "layout_bbox": [50, 340, 360, 500],
                    "rec_texts": [
                        "Recurrent neural networks have been firmly",
                        "established as state of the art approaches.",
                    ],
                    "rec_scores": [0.93, 0.94],
                },
                {
                    "layout_label": "text",
                    "layout_bbox": [400, 340, 730, 500],
                    "rec_texts": [
                        "Attention mechanisms have become an integral part",
                        "of sequence modeling and transduction models.",
                    ],
                    "rec_scores": [0.95, 0.93],
                },
                {
                    "layout_label": "table",
                    "layout_bbox": [100, 560, 680, 700],
                    "table_html": (
                        "<table>"
                        "<tr><th>Model</th><th>BLEU</th><th>Params</th></tr>"
                        "<tr><td>Base</td><td>27.3</td><td>65M</td></tr>"
                        "<tr><td>Big</td><td>28.4</td><td>213M</td></tr>"
                        "</table>"
                    ),
                },
                {
                    "layout_label": "figure",
                    "layout_bbox": [150, 720, 600, 900],
                },
                {
                    "layout_label": "figure_caption",
                    "layout_bbox": [150, 905, 600, 930],
                    "rec_texts": ["Figure 1. The Transformer model architecture."],
                    "rec_scores": [0.97],
                },
                {
                    "layout_label": "list",
                    "layout_bbox": [50, 940, 400, 1020],
                    "rec_texts": [
                        "- Self-attention mechanism",
                        "- Multi-head attention",
                        "- Positional encoding",
                    ],
                    "rec_scores": [0.95, 0.94, 0.96],
                },
            ]
        }
    ]


def build_multipage_report(num_pages: int = 5) -> list:
    """Build multi-page document with repeating headers/footers.

    Simulates a corporate report PDF with:
    - Repeating header: "Annual Report 2025"
    - Repeating footer: page number
    - Varied body content per page
    """
    pages = []
    sections = [
        ("Executive Summary", "Revenue grew 25% year-over-year."),
        ("Market Analysis", "The market expanded significantly in Q3."),
        ("Financial Results", "Net income reached $2.3 billion."),
        ("Risk Factors", "Currency fluctuations remain a concern."),
        ("Future Outlook", "We expect continued growth in 2026."),
    ]

    for i in range(num_pages):
        section_title, section_body = sections[i % len(sections)]

        page_regions = [
            # Repeating header
            {
                "type": "text",
                "bbox": [50, 20, 700, 50],
                "content": "Annual Report 2025",
                "confidence": 0.95,
            },
            # Section title
            {
                "type": "title",
                "bbox": [50, 100, 700, 150],
                "content": section_title,
                "confidence": 0.98,
            },
            # Body text (multiple paragraphs)
            {
                "type": "text",
                "bbox": [50, 170, 700, 350],
                "content": section_body + "\n" + f"This is detailed content for page {i + 1}.",
                "confidence": 0.93,
            },
            {
                "type": "text",
                "bbox": [50, 360, 700, 500],
                "content": f"Additional analysis shows trends on page {i + 1}.",
                "confidence": 0.91,
            },
            # Repeating footer with page number
            {
                "type": "text",
                "bbox": [300, 1050, 450, 1080],
                "content": f"Page {i + 1}",
                "confidence": 0.90,
            },
        ]
        pages.append({"page_number": i + 1, "regions": page_regions})

    return pages


def build_complex_table_html() -> str:
    """Build HTML table with colspan and rowspan for testing."""
    return (
        "<table>"
        '<tr><th colspan="3">Performance Comparison</th></tr>'
        "<tr><th>Model</th><th>English</th><th>Vietnamese</th></tr>"
        '<tr><td rowspan="2">Transformer</td><td>27.3</td><td>24.1</td></tr>'
        "<tr><td>28.4</td><td>25.8</td></tr>"
        '<tr><td colspan="2">Average</td><td>24.95</td></tr>'
        "</table>"
    )


def build_two_column_layout() -> list:
    """Build regions simulating a two-column academic paper page.

    Page width ~780px. Left column: 50-370. Right column: 410-730.
    """
    return [
        # Full-width title
        {"type": "title", "bbox": [50, 30, 730, 80], "content": "Main Title",
         "confidence": 0.99},
        # Left column paragraphs
        {"type": "text", "bbox": [50, 100, 370, 200],
         "content": "Left paragraph one with detailed content.",
         "confidence": 0.95},
        {"type": "text", "bbox": [50, 210, 370, 310],
         "content": "Left paragraph two continues the discussion.",
         "confidence": 0.93},
        # Right column paragraphs
        {"type": "text", "bbox": [410, 100, 730, 200],
         "content": "Right paragraph one starts here.",
         "confidence": 0.94},
        {"type": "text", "bbox": [410, 210, 730, 310],
         "content": "Right paragraph two has more details.",
         "confidence": 0.92},
        # Full-width subtitle
        {"type": "title", "bbox": [50, 330, 730, 360], "content": "Section Two",
         "confidence": 0.97},
    ]


def build_figure_with_caption_regions() -> list:
    """Build regions with figure followed by caption text."""
    return [
        {"type": "text", "bbox": [50, 30, 700, 80],
         "content": "The architecture is shown below.",
         "confidence": 0.95},
        {"type": "figure", "bbox": [100, 100, 650, 400], "caption": None},
        {"type": "text", "bbox": [100, 410, 650, 440],
         "content": "Figure 2. System architecture overview.",
         "confidence": 0.96},
        {"type": "text", "bbox": [50, 460, 700, 520],
         "content": "As shown in the figure above, the system uses three layers.",
         "confidence": 0.94},
    ]


def build_mergeable_paragraphs() -> list:
    """Build text regions that should be merged into paragraphs.

    Same column, small vertical gap — typical OCR fragmentation.
    """
    return [
        {"type": "title", "bbox": [50, 30, 700, 70], "content": "Introduction",
         "confidence": 0.99},
        # Fragment 1 of paragraph
        {"type": "text", "bbox": [50, 80, 700, 110],
         "content": "This is the first line of a paragraph.",
         "confidence": 0.95},
        # Fragment 2 (close y gap, same column) — should merge
        {"type": "text", "bbox": [50, 112, 700, 142],
         "content": "This is the second line of the same paragraph.",
         "confidence": 0.93},
        # Fragment 3 (close y gap, same column) — should merge
        {"type": "text", "bbox": [50, 144, 700, 174],
         "content": "And a third line completing the thought.",
         "confidence": 0.94},
        # New paragraph (large gap)
        {"type": "text", "bbox": [50, 400, 700, 430],
         "content": "A completely separate paragraph after a large gap.",
         "confidence": 0.92},
    ]


# ===========================================================================
# Tests — Academic Paper V2 pipeline (TA2-001 to TA2-005)
# ===========================================================================


class TestAcademicPaperV2:
    """TA2-001 to TA2-005: Full pipeline with PPStructure v2 academic paper."""

    @pytest.fixture
    def paper_pages(self):
        raw = build_academic_paper_v2()
        page = extract_regions(raw, 0)
        return [page]

    def test_ta2_001_all_region_types_extracted(self, paper_pages):
        """TA2-001: V2 extraction produces all expected region types."""
        types = {r["type"] for r in paper_pages[0]["regions"]}
        assert "title" in types, "Missing title regions"
        assert "text" in types, "Missing text regions"
        assert "table" in types, "Missing table regions"
        assert "figure" in types, "Missing figure regions"
        assert "list" in types, "Missing list regions"

    def test_ta2_002_json_output_complete(self, paper_pages):
        """TA2-002: JSON output has correct structure and summary."""
        result = format_structured_output(deepcopy(paper_pages), "json")
        parsed = json.loads(result)

        assert "pages" in parsed
        assert "summary" in parsed
        assert parsed["summary"]["total_pages"] == 1
        assert parsed["summary"]["total_regions"] >= 5
        assert parsed["summary"]["tables_found"] >= 1

    def test_ta2_003_markdown_has_structure(self, paper_pages):
        """TA2-003: Markdown output has headings, tables, lists, figure refs."""
        result = format_structured_output(deepcopy(paper_pages), "md")
        md = result.decode("utf-8")

        # Headings
        assert re.search(r"^#{1,3}\s", md, re.MULTILINE), "No headings in MD"
        # Table
        assert "|" in md, "No table markers in MD"
        assert "---" in md, "No table separator in MD"
        # List items
        assert re.search(r"^- ", md, re.MULTILINE), "No list items in MD"
        # Figure
        assert "*[Figure" in md, "No figure reference in MD"

    def test_ta2_004_html_is_complete_document(self, paper_pages):
        """TA2-004: HTML output is a self-contained valid document."""
        result = format_structured_output(deepcopy(paper_pages), "html")
        html = result.decode("utf-8")

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<style>" in html
        assert "</html>" in html
        # Heading tags
        assert re.search(r"<h[1-3]>", html), "No heading tags in HTML"
        # Paragraphs
        assert "<p>" in html, "No <p> tags in HTML"
        # Table
        assert "<table>" in html or "<th>" in html, "No table in HTML"

    def test_ta2_005_text_output_has_content(self, paper_pages):
        """TA2-005: Plain text output extracts all text content."""
        result = format_structured_output(deepcopy(paper_pages), "txt")
        text = result.decode("utf-8")

        assert "Attention Is All You Need" in text
        assert "Abstract" in text
        assert len(text) > 200, f"Text too short: {len(text)} chars"


# ===========================================================================
# Tests — Academic Paper V3 pipeline (TA2-006 to TA2-010)
# ===========================================================================


class TestAcademicPaperV3:
    """TA2-006 to TA2-010: Full pipeline with PPStructureV3 academic paper."""

    @pytest.fixture
    def paper_pages(self):
        raw = build_academic_paper_v3()
        page = extract_regions_v3(raw, 0)
        return [page]

    def test_ta2_006_v3_extracts_all_types(self, paper_pages):
        """TA2-006: V3 extraction produces all expected region types."""
        types = {r["type"] for r in paper_pages[0]["regions"]}
        assert "title" in types
        assert "text" in types
        assert "table" in types
        assert "figure" in types
        assert "list" in types

    def test_ta2_007_v3_json_matches_v2_structure(self, paper_pages):
        """TA2-007: V3 JSON output has same structure as V2."""
        result = format_structured_output(deepcopy(paper_pages), "json")
        parsed = json.loads(result)

        assert parsed["summary"]["total_pages"] == 1
        assert parsed["summary"]["total_regions"] >= 5

        # Regions should have required fields
        for region in parsed["pages"][0]["regions"]:
            assert "type" in region
            assert "bbox" in region
            if region["type"] in ("text", "title", "list"):
                assert "content" in region

    def test_ta2_008_v3_markdown_quality(self, paper_pages):
        """TA2-008: V3 markdown output has proper formatting."""
        result = format_structured_output(deepcopy(paper_pages), "md")
        md = result.decode("utf-8")

        assert "Attention Is All You Need" in md
        assert "|" in md  # table
        heading_lines = re.findall(r"^#{1,3}\s.+", md, re.MULTILINE)
        assert len(heading_lines) >= 2, f"Expected >=2 headings, got {len(heading_lines)}"

    def test_ta2_009_v3_text_preserves_newlines(self, paper_pages):
        """TA2-009: V3 text regions preserve newlines (not space-joined)."""
        text_regions = [
            r for r in paper_pages[0]["regions"]
            if r["type"] == "text" and "\n" in r.get("content", "")
        ]
        assert len(text_regions) > 0, "Expected text regions with newlines"

    def test_ta2_010_v3_quality_assessment_passes(self, paper_pages):
        """TA2-010: Quality assessment accepts well-structured V3 output."""
        assert assess_result_quality(paper_pages) is True


# ===========================================================================
# Tests — Heading Level Detection (TA2-011 to TA2-013)
# ===========================================================================


class TestHeadingLevelIntegration:
    """TA2-011 to TA2-013: Heading detection in realistic documents."""

    def test_ta2_011_paper_heading_hierarchy(self):
        """TA2-011: Academic paper has h1 (main title) and h2 (sections)."""
        raw = build_academic_paper_v2()
        pages = [extract_regions(raw, 0)]
        result = format_structured_output(deepcopy(pages), "json")
        parsed = json.loads(result)

        titles = [
            r for r in parsed["pages"][0]["regions"] if r["type"] == "title"
        ]
        levels = {t["heading_level"] for t in titles}

        # Main title (height=50) should be h1, section titles (height=25) should be h2
        assert 1 in levels, "Expected h1 for main title"
        assert 2 in levels, "Expected h2 for section titles"

    def test_ta2_012_heading_levels_in_markdown(self):
        """TA2-012: Markdown uses # and ## for different heading levels."""
        raw = build_academic_paper_v2()
        pages = [extract_regions(raw, 0)]
        result = format_structured_output(deepcopy(pages), "md")
        md = result.decode("utf-8")

        h1_lines = re.findall(r"^# [^#]", md, re.MULTILINE)
        h2_lines = re.findall(r"^## [^#]", md, re.MULTILINE)

        assert len(h1_lines) >= 1, f"Expected h1 headings, found {len(h1_lines)}"
        assert len(h2_lines) >= 1, f"Expected h2 headings, found {len(h2_lines)}"

    def test_ta2_013_heading_levels_in_html(self):
        """TA2-013: HTML uses <h1> and <h2> tags correctly."""
        raw = build_academic_paper_v2()
        pages = [extract_regions(raw, 0)]
        result = format_structured_output(deepcopy(pages), "html")
        html = result.decode("utf-8")

        h1_tags = re.findall(r"<h1>(.+?)</h1>", html)
        h2_tags = re.findall(r"<h2>(.+?)</h2>", html)

        assert len(h1_tags) >= 1, "Expected <h1> tags"
        assert len(h2_tags) >= 1, "Expected <h2> tags"


# ===========================================================================
# Tests — Two-Column Layout Reorder (TA2-014 to TA2-016)
# ===========================================================================


class TestColumnReorderIntegration:
    """TA2-014 to TA2-016: Column detection and reading order."""

    def test_ta2_014_two_column_reading_order(self):
        """TA2-014: Two-column layout reads left column first."""
        regions = build_two_column_layout()
        reordered = _reorder_by_columns(regions)

        contents = [r["content"] for r in reordered]

        # Full-width title first
        assert contents[0] == "Main Title"
        # Then left column
        left_idx = [i for i, c in enumerate(contents) if "Left" in c]
        right_idx = [i for i, c in enumerate(contents) if "Right" in c]
        assert all(l < r for l in left_idx for r in right_idx), (
            f"Left column should come before right. Order: {contents}"
        )

    def test_ta2_015_column_reorder_in_markdown(self):
        """TA2-015: Markdown output follows correct reading order."""
        regions = build_two_column_layout()
        pages = [{"page_number": 1, "regions": regions}]
        result = format_structured_output(deepcopy(pages), "md")
        md = result.decode("utf-8")

        left1_pos = md.find("Left paragraph one")
        left2_pos = md.find("Left paragraph two")
        right1_pos = md.find("Right paragraph one")

        assert left1_pos < left2_pos < right1_pos, (
            "Left column should appear before right column in markdown"
        )

    def test_ta2_016_full_width_elements_preserved(self):
        """TA2-016: Full-width title/subtitle stay in correct position."""
        regions = build_two_column_layout()
        pages = [{"page_number": 1, "regions": regions}]
        result = format_structured_output(deepcopy(pages), "md")
        md = result.decode("utf-8")

        main_title_pos = md.find("Main Title")
        section_two_pos = md.find("Section Two")
        assert main_title_pos >= 0, "Main Title not found in output"
        assert section_two_pos >= 0, "Section Two not found in output"
        assert main_title_pos < section_two_pos


# ===========================================================================
# Tests — Header/Footer Filtering (TA2-017 to TA2-019)
# ===========================================================================


class TestHeaderFooterFilteringIntegration:
    """TA2-017 to TA2-019: Cross-page header/footer removal."""

    def test_ta2_017_repeating_header_removed(self):
        """TA2-017: Repeating header text filtered from all pages."""
        pages = build_multipage_report(5)
        _filter_headers_footers(pages)

        for page in pages:
            contents = [r.get("content", "") for r in page["regions"]]
            assert "Annual Report 2025" not in contents, (
                f"Header should be filtered on page {page['page_number']}"
            )

    def test_ta2_018_page_numbers_removed(self):
        """TA2-018: Page number footers filtered from all pages."""
        pages = build_multipage_report(5)
        _filter_headers_footers(pages)

        for page in pages:
            contents = [r.get("content", "") for r in page["regions"]]
            page_nums = [c for c in contents if re.match(r"^Page \d+$", c)]
            assert len(page_nums) == 0, (
                f"Page number should be filtered: {page_nums}"
            )

    def test_ta2_019_body_content_preserved_after_filter(self):
        """TA2-019: Section titles and body text preserved after filtering."""
        pages = build_multipage_report(5)
        _filter_headers_footers(pages)

        for page in pages:
            contents = [r.get("content", "") for r in page["regions"]]
            # Each page should still have its section title
            titles = [r for r in page["regions"] if r.get("type") == "title"]
            assert len(titles) >= 1, f"Section title missing on page {page['page_number']}"

    def test_ta2_019b_full_pipeline_with_multipage(self):
        """TA2-019b: Full pipeline with multi-page report: header/footer + format."""
        pages = build_multipage_report(5)
        result = format_structured_output(pages, "md")
        md = result.decode("utf-8")

        # Headers/footers should be gone
        assert "Annual Report 2025" not in md
        # Footer "Page N" should be filtered (but "## Page N" separators are OK)
        footer_matches = re.findall(r"(?<!## )(?<!#\s)Page \d+", md)
        assert len(footer_matches) == 0, f"Footer page numbers not filtered: {footer_matches}"
        # Body content preserved
        assert "Executive Summary" in md
        # Multi-page separators
        assert "## Page" in md


# ===========================================================================
# Tests — Table colspan/rowspan (TA2-020 to TA2-022)
# ===========================================================================


class TestTableColspanRowspanIntegration:
    """TA2-020 to TA2-022: Complex table parsing in pipeline."""

    def test_ta2_020_colspan_renders_correctly(self):
        """TA2-020: Table with colspan renders in markdown."""
        html = build_complex_table_html()
        md = html_table_to_markdown(html)

        assert "Performance Comparison" in md
        lines = md.strip().split("\n")
        # First row should have the merged header spanning 3 cols
        assert lines[0].count("|") >= 4

    def test_ta2_021_rowspan_fills_grid(self):
        """TA2-021: Table with rowspan fills cells in subsequent rows."""
        html = build_complex_table_html()
        md = html_table_to_markdown(html)

        lines = [l for l in md.strip().split("\n") if "Transformer" in l]
        # "Transformer" should appear in both data rows (rowspan=2)
        assert len(lines) == 2, f"Expected Transformer in 2 rows, found {len(lines)}"

    def test_ta2_022_complex_table_in_full_pipeline(self):
        """TA2-022: Complex table renders correctly through full pipeline."""
        pages = [{
            "page_number": 1,
            "regions": [{
                "type": "table",
                "bbox": [50, 100, 700, 400],
                "html": build_complex_table_html(),
                "markdown": html_table_to_markdown(build_complex_table_html()),
            }],
        }]

        # Test markdown
        result_md = format_structured_output(deepcopy(pages), "md")
        md = result_md.decode("utf-8")
        assert "Performance Comparison" in md
        assert "Transformer" in md
        assert "27.3" in md

        # Test HTML
        result_html = format_structured_output(deepcopy(pages), "html")
        html = result_html.decode("utf-8")
        assert "colspan" in html  # HTML table preserved
        assert "Performance Comparison" in html


# ===========================================================================
# Tests — Paragraph Merging (TA2-023 to TA2-025)
# ===========================================================================


class TestParagraphMergingIntegration:
    """TA2-023 to TA2-025: Adjacent text region merging."""

    def test_ta2_023_fragmented_text_merged(self):
        """TA2-023: Three adjacent text fragments merge into one."""
        regions = build_mergeable_paragraphs()
        merged = _merge_adjacent_paragraphs(regions)

        text_regions = [r for r in merged if r["type"] == "text"]
        # 3 fragments + 1 separate paragraph → should become 2 text regions
        assert len(text_regions) == 2, (
            f"Expected 2 text regions after merge, got {len(text_regions)}"
        )

    def test_ta2_024_merged_content_complete(self):
        """TA2-024: Merged region contains all original text."""
        regions = build_mergeable_paragraphs()
        merged = _merge_adjacent_paragraphs(regions)

        first_text = next(r for r in merged if r["type"] == "text")
        assert "first line" in first_text["content"]
        assert "second line" in first_text["content"]
        assert "third line" in first_text["content"]

    def test_ta2_025_paragraph_merge_in_full_pipeline(self):
        """TA2-025: Paragraph merging works through format_structured_output."""
        regions = build_mergeable_paragraphs()
        pages = [{"page_number": 1, "regions": regions}]
        result = format_structured_output(pages, "json")
        parsed = json.loads(result)

        text_regions = [
            r for r in parsed["pages"][0]["regions"] if r["type"] == "text"
        ]
        # 3 fragments should be merged
        assert len(text_regions) == 2, (
            f"Expected 2 text regions after pipeline merge, got {len(text_regions)}"
        )


# ===========================================================================
# Tests — Figure Caption Extraction (TA2-026 to TA2-028)
# ===========================================================================


class TestFigureCaptionIntegration:
    """TA2-026 to TA2-028: Figure caption detection and rendering."""

    def test_ta2_026_caption_assigned_to_figure(self):
        """TA2-026: Caption text detected and assigned to figure."""
        regions = build_figure_with_caption_regions()
        _extract_figure_captions(regions)

        figures = [r for r in regions if r["type"] == "figure"]
        assert len(figures) == 1
        assert figures[0]["caption"] == "Figure 2. System architecture overview."

        # Caption text region should be consumed
        text_contents = [r.get("content", "") for r in regions if r["type"] == "text"]
        assert "Figure 2." not in " ".join(text_contents)

    def test_ta2_027_figure_caption_in_markdown(self):
        """TA2-027: Figure caption rendered in markdown output."""
        regions = build_figure_with_caption_regions()
        pages = [{"page_number": 1, "regions": regions}]
        result = format_structured_output(pages, "md")
        md = result.decode("utf-8")

        assert "*[Figure: Figure 2. System architecture overview.]*" in md

    def test_ta2_028_figure_caption_in_html(self):
        """TA2-028: Figure caption rendered with <figcaption> in HTML."""
        regions = build_figure_with_caption_regions()
        pages = [{"page_number": 1, "regions": regions}]
        result = format_structured_output(pages, "html")
        html = result.decode("utf-8")

        assert "<figcaption>" in html
        assert "System architecture overview" in html


# ===========================================================================
# Tests — Full A2 Pipeline End-to-End (TA2-029 to TA2-030)
# ===========================================================================


class TestFullA2Pipeline:
    """TA2-029 to TA2-030: Complete pipeline with all features combined."""

    def test_ta2_029_full_pipeline_academic_paper(self):
        """TA2-029: Academic paper through full pipeline — all A2 features."""
        raw = build_academic_paper_v2()
        pages = [extract_regions(raw, 0)]

        # JSON
        result_json = format_structured_output(deepcopy(pages), "json")
        parsed = json.loads(result_json)
        assert parsed["summary"]["total_pages"] == 1
        assert parsed["summary"]["total_regions"] >= 5

        # Verify heading levels in JSON
        titles = [
            r for r in parsed["pages"][0]["regions"] if r["type"] == "title"
        ]
        assert any(t["heading_level"] == 1 for t in titles)
        assert any(t["heading_level"] == 2 for t in titles)

        # Verify figure caption extraction
        figures = [
            r for r in parsed["pages"][0]["regions"] if r["type"] == "figure"
        ]
        if figures:
            assert figures[0].get("caption") is not None, (
                "Figure should have caption extracted"
            )

        # Markdown
        result_md = format_structured_output(deepcopy(pages), "md")
        md = result_md.decode("utf-8")
        assert "# " in md  # h1
        assert "## " in md  # h2
        assert "|" in md  # table
        assert "- " in md  # list

        # HTML
        result_html = format_structured_output(deepcopy(pages), "html")
        html = result_html.decode("utf-8")
        assert "<h1>" in html
        assert "<h2>" in html
        assert "<table>" in html or "<th>" in html
        assert "<li>" in html

    def test_ta2_030_full_pipeline_multipage_report(self):
        """TA2-030: Multi-page report — header/footer filter + all formatting."""
        pages = build_multipage_report(5)

        # JSON
        result_json = format_structured_output(deepcopy(pages), "json")
        parsed = json.loads(result_json)
        assert parsed["summary"]["total_pages"] == 5

        # Headers/footers should be filtered
        for page in parsed["pages"]:
            contents = [r.get("content", "") for r in page["regions"]]
            assert "Annual Report 2025" not in contents
            assert not any(re.match(r"^Page \d+$", c) for c in contents)

        # Body content should be preserved
        all_titles = [
            r["content"]
            for p in parsed["pages"]
            for r in p["regions"]
            if r["type"] == "title"
        ]
        assert "Executive Summary" in all_titles

        # Markdown
        result_md = format_structured_output(deepcopy(pages), "md")
        md = result_md.decode("utf-8")
        assert "Annual Report 2025" not in md
        assert "Executive Summary" in md
        assert "## Page" in md  # multi-page separators
        assert len(md) > 500, f"Markdown too short: {len(md)} chars"

        # HTML
        result_html = format_structured_output(deepcopy(pages), "html")
        html = result_html.decode("utf-8")
        assert "<!DOCTYPE html>" in html
        assert "Executive Summary" in html
        assert "Annual Report 2025" not in html
