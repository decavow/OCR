"""Unit tests for Marker engine postprocessing module.

Tests MPost-001 through MPost-025: confidence scoring, markdown normalization,
JSON block parsing, and output formatting.
"""

import json
import sys

import pytest

from pathlib import Path
WORKER_ROOT = Path(__file__).parent.parent.parent / "03_worker"
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from app.engines.marker.postprocessing import (
    calculate_confidence,
    normalize_markdown,
    format_output,
    _markdown_to_json,
)


# ===========================================================================
# Confidence scoring
# ===========================================================================

class TestCalculateConfidence:
    """MPost-001 to MPost-008: heuristic confidence scoring."""

    # MPost-001: Normal Vietnamese text → high confidence
    def test_normal_vietnamese(self):
        text = "Đây là một đoạn văn bản tiếng Việt bình thường, chứa nhiều từ."
        score, details = calculate_confidence(text)
        assert score >= 0.7
        assert "unknown_char_ratio" in details
        assert "avg_word_len" in details

    # MPost-002: Normal English text → high confidence
    def test_normal_english(self):
        text = "This is a normal English paragraph with multiple words and sentences."
        score, details = calculate_confidence(text)
        assert score >= 0.8

    # MPost-003: Empty input → zero confidence
    def test_empty_input(self):
        score, details = calculate_confidence("")
        assert score == 0.0
        assert "note" in details

    # MPost-004: Whitespace-only input → zero confidence
    def test_whitespace_only(self):
        score, details = calculate_confidence("   \n\n  \t  ")
        assert score == 0.0

    # MPost-005: High unknown char ratio → lower confidence
    def test_high_unknown_chars(self):
        # Lots of CJK/unusual chars
        text = "中文 日本語 한국어 العربية " * 10
        score, _ = calculate_confidence(text)
        normal_score, _ = calculate_confidence("Normal English text with good words.")
        assert score < normal_score

    # MPost-006: Very short words → penalized
    def test_short_words(self):
        text = "a b c d e f g h i j k l m n"
        score, details = calculate_confidence(text)
        assert details["avg_word_len"] < 2.0
        assert score < 1.0

    # MPost-007: Very long words → penalized
    def test_long_words(self):
        text = "a" * 30 + " " + "b" * 30 + " " + "c" * 30
        score, details = calculate_confidence(text)
        assert details["avg_word_len"] > 25.0
        assert score < 1.0

    # MPost-008: Score is clamped between 0 and 1
    def test_score_clamping(self):
        # Even worst case should be >= 0
        bad_text = "中" * 100
        score, _ = calculate_confidence(bad_text)
        assert 0.0 <= score <= 1.0

        good_text = "Hello world"
        score2, _ = calculate_confidence(good_text)
        assert 0.0 <= score2 <= 1.0


# ===========================================================================
# Markdown normalization
# ===========================================================================

class TestNormalizeMarkdown:
    """MPost-009 to MPost-016: page number removal and whitespace trimming."""

    # MPost-009: Removes "- 5 -" style page numbers
    def test_dash_page_number(self):
        text = "Some text\n- 5 -\nMore text"
        result, changes = normalize_markdown(text)
        assert "- 5 -" not in result
        assert changes["page_numbers_removed"] == 1

    # MPost-010: Removes "— 3 —" style page numbers (em dash)
    def test_emdash_page_number(self):
        text = "Paragraph\n— 3 —\nNext paragraph"
        result, changes = normalize_markdown(text)
        assert "— 3 —" not in result
        assert changes["page_numbers_removed"] == 1

    # MPost-011: Removes "Page 5" style page numbers
    def test_page_keyword(self):
        text = "Content\nPage 12\nMore content"
        result, changes = normalize_markdown(text)
        assert "Page 12" not in result
        assert changes["page_numbers_removed"] == 1

    # MPost-012: Removes standalone digits (1-4 digit numbers)
    def test_standalone_digits(self):
        text = "First page\n1\nSecond page\n23\nThird page"
        result, changes = normalize_markdown(text)
        assert changes["page_numbers_removed"] == 2

    # MPost-013: Does NOT remove numbers in context
    def test_preserves_numbers_in_context(self):
        text = "There are 42 items in the list"
        result, changes = normalize_markdown(text)
        assert "42" in result
        assert changes["page_numbers_removed"] == 0

    # MPost-014: Trims excessive blank lines (3+ → 2)
    def test_trim_blank_lines(self):
        text = "Para 1\n\n\n\n\nPara 2"
        result, changes = normalize_markdown(text)
        assert "\n\n\n" not in result
        assert changes["whitespace_trimmed"] is True

    # MPost-015: Keeps up to 2 blank lines
    def test_preserves_double_blank(self):
        text = "Para 1\n\nPara 2"
        result, changes = normalize_markdown(text)
        assert "Para 1\n\nPara 2" in result

    # MPost-016: Multiple page numbers removed
    def test_multiple_page_numbers(self):
        text = "Content\n- 1 -\nMore\nPage 2\nEnd\n3"
        result, changes = normalize_markdown(text)
        assert changes["page_numbers_removed"] == 3


# ===========================================================================
# JSON block parsing
# ===========================================================================

class TestMarkdownToJson:
    """MPost-017 to MPost-022: _markdown_to_json block parsing."""

    # MPost-017: Heading detection
    def test_heading(self):
        md = "# Title\n\nSome text"
        result = _markdown_to_json(md, 0.9)
        blocks = result["blocks"]
        headings = [b for b in blocks if b["type"] == "heading"]
        assert len(headings) == 1
        assert headings[0]["content"] == "Title"
        assert headings[0]["level"] == 1

    # MPost-018: Heading levels (h1-h6)
    def test_heading_levels(self):
        md = "# H1\n## H2\n### H3"
        result = _markdown_to_json(md, 0.8)
        headings = [b for b in result["blocks"] if b["type"] == "heading"]
        assert len(headings) == 3
        assert headings[0]["level"] == 1
        assert headings[1]["level"] == 2
        assert headings[2]["level"] == 3

    # MPost-019: Table detection
    def test_table(self):
        md = "| Col A | Col B |\n|---|---|\n| val1 | val2 |"
        result = _markdown_to_json(md, 0.9)
        tables = [b for b in result["blocks"] if b["type"] == "table"]
        assert len(tables) == 1
        assert "Col A" in tables[0]["content"]

    # MPost-020: List detection (bullet and numbered)
    def test_list(self):
        md = "- item 1\n- item 2\n\n1. first\n2. second"
        result = _markdown_to_json(md, 0.9)
        lists = [b for b in result["blocks"] if b["type"] == "list"]
        assert len(lists) == 2

    # MPost-021: Code block detection
    def test_code_block(self):
        md = "```python\nprint('hello')\n```"
        result = _markdown_to_json(md, 0.9)
        codes = [b for b in result["blocks"] if b["type"] == "code"]
        assert len(codes) == 1
        assert codes[0]["language"] == "python"
        assert "print('hello')" in codes[0]["content"]

    # MPost-022: Confidence and block count in output
    def test_metadata(self):
        md = "# Title\n\nParagraph text."
        result = _markdown_to_json(md, 0.85)
        assert result["confidence"] == 0.85
        assert result["blocks_count"] == len(result["blocks"])

    # MPost-022b: Paragraph detection
    def test_paragraph(self):
        md = "This is a simple paragraph."
        result = _markdown_to_json(md, 0.9)
        paragraphs = [b for b in result["blocks"] if b["type"] == "paragraph"]
        assert len(paragraphs) == 1
        assert paragraphs[0]["content"] == "This is a simple paragraph."


# ===========================================================================
# Output formatting
# ===========================================================================

class TestFormatOutput:
    """MPost-023 to MPost-025: format_output for md/html/json."""

    # MPost-023: md format returns UTF-8 bytes
    def test_md_format(self):
        md = "# Hello\n\nWorld"
        result = format_output(md, 0.9, "md")
        assert isinstance(result, bytes)
        assert result == md.encode("utf-8")

    # MPost-024: json format returns valid JSON with blocks
    def test_json_format(self):
        md = "# Title\n\nParagraph text."
        result = format_output(md, 0.85, "json")
        parsed = json.loads(result)
        assert "confidence" in parsed
        assert "blocks" in parsed
        assert parsed["confidence"] == 0.85

    # MPost-025: html format returns HTML with template
    def test_html_format(self):
        md = "# Hello\n\nWorld"
        result = format_output(md, 0.9, "html")
        html = result.decode("utf-8")
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html
        # Content should be in there
        assert "Hello" in html
        assert "World" in html

    # MPost-025b: unsupported format raises ValueError
    def test_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported output format"):
            format_output("text", 0.9, "xlsx")
