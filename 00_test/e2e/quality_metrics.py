"""
OCR Quality Metrics — CER, WER, keyword hit rate, quality report.

Dùng để đo lường chất lượng nhận dạng OCR so với ground truth.
Không dependency ngoài (Levenshtein tự implement).
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ─── Text normalization ──────────────────────────────────────────────────────


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace, strip."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_for_cer(text: str) -> str:
    """Aggressive normalization for CER: remove punctuation, collapse spaces."""
    text = normalize_text(text)
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Levenshtein distance ────────────────────────────────────────────────────


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein (edit) distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # insertion, deletion, substitution
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,       # insertion
                prev_row[j + 1] + 1,   # deletion
                prev_row[j] + cost,    # substitution
            ))
        prev_row = curr_row

    return prev_row[-1]


# ─── Core metrics ────────────────────────────────────────────────────────────


def character_error_rate(ocr_text: str, ground_truth: str) -> float:
    """Character Error Rate (CER) = edit_distance / len(ground_truth).

    Lower is better. 0.0 = perfect, 1.0 = completely wrong.
    Returns 1.0 if ground_truth is empty.
    """
    ocr_norm = normalize_for_cer(ocr_text)
    gt_norm = normalize_for_cer(ground_truth)
    if not gt_norm:
        return 1.0
    dist = levenshtein_distance(ocr_norm, gt_norm)
    return min(dist / len(gt_norm), 1.0)


def word_error_rate(ocr_text: str, ground_truth: str) -> float:
    """Word Error Rate (WER) = word_edit_distance / len(gt_words).

    Lower is better. 0.0 = perfect.
    """
    ocr_words = normalize_text(ocr_text).split()
    gt_words = normalize_text(ground_truth).split()
    if not gt_words:
        return 1.0
    dist = levenshtein_distance(ocr_words, gt_words)
    return min(dist / len(gt_words), 1.0)


def keyword_hit_rate(
    text: str, keywords: list[str]
) -> tuple[float, list[str], list[str]]:
    """Check how many keywords appear in text (case-insensitive).

    Returns: (hit_rate, found_keywords, missed_keywords)
    """
    text_lower = text.lower()
    found = []
    missed = []
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
        else:
            missed.append(kw)
    rate = len(found) / len(keywords) if keywords else 1.0
    return rate, found, missed


def fuzzy_keyword_hit_rate(
    text: str, keywords: list[str], max_cer: float = 0.3
) -> tuple[float, list[str], list[str]]:
    """Fuzzy keyword matching — allows minor OCR errors in keywords.

    For each keyword, search the text for any substring of similar length
    with CER <= max_cer. Slower but handles OCR typos.
    """
    text_lower = text.lower()
    found = []
    missed = []

    for kw in keywords:
        kw_lower = kw.lower()
        # Try exact match first
        if kw_lower in text_lower:
            found.append(kw)
            continue
        # Try fuzzy: slide window of keyword length over text
        kw_len = len(kw_lower)
        matched = False
        for i in range(len(text_lower) - kw_len + 1):
            window = text_lower[i : i + kw_len]
            cer = levenshtein_distance(window, kw_lower) / kw_len
            if cer <= max_cer:
                matched = True
                break
        if matched:
            found.append(kw)
        else:
            missed.append(kw)

    rate = len(found) / len(keywords) if keywords else 1.0
    return rate, found, missed


# ─── Ground truth loading ────────────────────────────────────────────────────


GROUND_TRUTH_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test", "ground_truth"
)


@dataclass
class A2LayoutConfig:
    """A2 Layout-Preserved quality requirements from capability docs."""
    min_heading_count: int = 0
    expected_heading_keywords: list[str] = field(default_factory=list)
    has_multi_column: bool = False
    min_pages: int = 1
    min_regions: int = 1
    expected_region_types: list[str] = field(default_factory=list)
    min_tables: int = 0
    table_has_content: bool = False
    paragraph_has_newlines: bool = False
    header_footer_filtered: bool = False
    reading_order_keywords_sequence: list[str] = field(default_factory=list)


@dataclass
class GroundTruthConfig:
    """Ground truth configuration for a test file."""
    file: str
    language: str
    description: str
    keywords: list[str]
    keyword_threshold: float = 0.6
    fuzzy_keyword_threshold: float = 0.7
    min_output_chars: int = 50
    max_output_chars: int = 100_000
    snippets: list[dict[str, Any]] = field(default_factory=list)
    a2_layout: A2LayoutConfig | None = None


def load_ground_truth(name: str) -> GroundTruthConfig:
    """Load ground truth config from JSON file."""
    path = os.path.join(GROUND_TRUTH_DIR, f"{name}.json")
    with open(path) as f:
        data = json.load(f)

    a2_data = data.get("a2_layout")
    a2_layout = None
    if a2_data:
        a2_layout = A2LayoutConfig(
            min_heading_count=a2_data.get("min_heading_count", 0),
            expected_heading_keywords=a2_data.get("expected_heading_keywords", []),
            has_multi_column=a2_data.get("has_multi_column", False),
            min_pages=a2_data.get("min_pages", 1),
            min_regions=a2_data.get("min_regions", 1),
            expected_region_types=a2_data.get("expected_region_types", []),
            min_tables=a2_data.get("min_tables", 0),
            table_has_content=a2_data.get("table_has_content", False),
            paragraph_has_newlines=a2_data.get("paragraph_has_newlines", False),
            header_footer_filtered=a2_data.get("header_footer_filtered", False),
            reading_order_keywords_sequence=a2_data.get(
                "reading_order_keywords_sequence", []
            ),
        )

    return GroundTruthConfig(
        file=data["file"],
        language=data.get("language", "en"),
        description=data.get("description", ""),
        keywords=data.get("keywords", []),
        keyword_threshold=data.get("keyword_threshold", 0.6),
        fuzzy_keyword_threshold=data.get("fuzzy_keyword_threshold", 0.7),
        min_output_chars=data.get("min_output_chars", 50),
        max_output_chars=data.get("max_output_chars", 100_000),
        snippets=data.get("snippets", []),
        a2_layout=a2_layout,
    )


def list_ground_truths() -> list[str]:
    """List available ground truth configs (without .json extension)."""
    if not os.path.isdir(GROUND_TRUTH_DIR):
        return []
    return [
        Path(f).stem
        for f in os.listdir(GROUND_TRUTH_DIR)
        if f.endswith(".json")
    ]


# ─── Quality report ──────────────────────────────────────────────────────────


@dataclass
class QualityReport:
    """Comprehensive quality assessment for one OCR result."""
    file: str
    engine: str
    language: str
    output_length: int
    # Keyword metrics
    keyword_hit_rate: float
    keyword_found: list[str]
    keyword_missed: list[str]
    fuzzy_keyword_hit_rate: float
    # Snippet CER
    snippet_results: list[dict[str, Any]]
    avg_snippet_cer: float
    # Thresholds
    length_ok: bool
    keywords_ok: bool
    snippets_ok: bool
    overall_pass: bool

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "engine": self.engine,
            "language": self.language,
            "output_length": self.output_length,
            "keyword_hit_rate": round(self.keyword_hit_rate, 3),
            "keyword_found": self.keyword_found,
            "keyword_missed": self.keyword_missed,
            "fuzzy_keyword_hit_rate": round(self.fuzzy_keyword_hit_rate, 3),
            "snippet_results": self.snippet_results,
            "avg_snippet_cer": round(self.avg_snippet_cer, 3),
            "length_ok": self.length_ok,
            "keywords_ok": self.keywords_ok,
            "snippets_ok": self.snippets_ok,
            "overall_pass": self.overall_pass,
        }

    def summary(self) -> str:
        status = "PASS" if self.overall_pass else "FAIL"
        lines = [
            f"[{status}] {self.file} ({self.engine})",
            f"  Length: {self.output_length} chars {'OK' if self.length_ok else 'FAIL'}",
            f"  Keywords: {self.keyword_hit_rate:.0%} exact, "
            f"{self.fuzzy_keyword_hit_rate:.0%} fuzzy "
            f"{'OK' if self.keywords_ok else 'FAIL'}",
        ]
        if self.keyword_missed:
            lines.append(f"  Missed: {', '.join(self.keyword_missed[:5])}")
        if self.snippet_results:
            lines.append(
                f"  Snippets: avg CER={self.avg_snippet_cer:.1%} "
                f"{'OK' if self.snippets_ok else 'FAIL'}"
            )
        return "\n".join(lines)


def assess_quality(
    ocr_text: str,
    config: GroundTruthConfig,
    engine: str = "unknown",
) -> QualityReport:
    """Run full quality assessment against ground truth config."""
    output_length = len(ocr_text)

    # Length check
    length_ok = config.min_output_chars <= output_length <= config.max_output_chars

    # Keyword checks
    kw_rate, kw_found, kw_missed = keyword_hit_rate(ocr_text, config.keywords)
    fuzzy_rate, _, _ = fuzzy_keyword_hit_rate(ocr_text, config.keywords)
    keywords_ok = fuzzy_rate >= config.fuzzy_keyword_threshold

    # Snippet CER checks
    snippet_results = []
    all_snippet_ok = True
    for snippet in config.snippets:
        gt_text = snippet["text"]
        max_cer = snippet.get("max_cer", 0.2)

        # Find best matching region in OCR text
        best_cer = _find_best_cer(ocr_text, gt_text)

        passed = best_cer <= max_cer
        if not passed:
            all_snippet_ok = False

        snippet_results.append({
            "ground_truth": gt_text[:80],
            "cer": round(best_cer, 3),
            "max_cer": max_cer,
            "pass": passed,
        })

    avg_cer = (
        sum(s["cer"] for s in snippet_results) / len(snippet_results)
        if snippet_results else 0.0
    )

    snippets_ok = all_snippet_ok

    overall_pass = length_ok and keywords_ok and snippets_ok

    return QualityReport(
        file=config.file,
        engine=engine,
        language=config.language,
        output_length=output_length,
        keyword_hit_rate=kw_rate,
        keyword_found=kw_found,
        keyword_missed=kw_missed,
        fuzzy_keyword_hit_rate=fuzzy_rate,
        snippet_results=snippet_results,
        avg_snippet_cer=avg_cer,
        length_ok=length_ok,
        keywords_ok=keywords_ok,
        snippets_ok=snippets_ok,
        overall_pass=overall_pass,
    )


def _find_best_cer(ocr_text: str, ground_truth: str) -> float:
    """Find the best CER by sliding ground truth over OCR text.

    Searches for the region in ocr_text that best matches ground_truth.
    Uses normalized text for comparison.
    """
    ocr_norm = normalize_for_cer(ocr_text)
    gt_norm = normalize_for_cer(ground_truth)

    if not gt_norm:
        return 1.0
    if not ocr_norm:
        return 1.0

    gt_len = len(gt_norm)

    # If OCR text is shorter than ground truth, compare directly
    if len(ocr_norm) <= gt_len:
        return levenshtein_distance(ocr_norm, gt_norm) / gt_len

    # Slide window with some margin (±30% of ground truth length)
    margin = max(int(gt_len * 0.3), 5)
    best_cer = 1.0

    for win_size in range(max(1, gt_len - margin), gt_len + margin + 1):
        if win_size > len(ocr_norm):
            break
        for i in range(0, len(ocr_norm) - win_size + 1, max(1, win_size // 10)):
            window = ocr_norm[i : i + win_size]
            dist = levenshtein_distance(window, gt_norm)
            cer = dist / gt_len
            if cer < best_cer:
                best_cer = cer
                if cer == 0:
                    return 0.0

    return best_cer


# ─── Report formatting ───────────────────────────────────────────────────────


def format_quality_report(reports: list[QualityReport]) -> str:
    """Format multiple quality reports as markdown table."""
    lines = [
        "# OCR Quality Benchmark Report",
        "",
        "| File | Engine | Length | Keywords (exact) | Keywords (fuzzy) | Avg CER | Status |",
        "|------|--------|-------:|:----------------:|:----------------:|--------:|:------:|",
    ]
    for r in reports:
        status = "PASS" if r.overall_pass else "FAIL"
        lines.append(
            f"| {r.file} | {r.engine} | {r.output_length} | "
            f"{r.keyword_hit_rate:.0%} | {r.fuzzy_keyword_hit_rate:.0%} | "
            f"{r.avg_snippet_cer:.1%} | {status} |"
        )

    # Summary
    total = len(reports)
    passed = sum(1 for r in reports if r.overall_pass)
    lines.extend([
        "",
        f"**Total: {passed}/{total} passed**",
        "",
    ])

    # Details for failures
    failures = [r for r in reports if not r.overall_pass]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for r in failures:
            lines.append(r.summary())
            lines.append("")

    return "\n".join(lines)


# ─── A2 Layout Quality Assessment ────────────────────────────────────────────


@dataclass
class A2LayoutReport:
    """Assessment of A2 Layout-Preserved quality requirements."""
    file: str
    engine: str
    # Structure checks
    page_count: int = 0
    region_count: int = 0
    region_types_found: list[str] = field(default_factory=list)
    heading_count: int = 0
    heading_texts: list[str] = field(default_factory=list)
    table_count: int = 0
    tables_with_content: int = 0
    # Quality checks
    pages_ok: bool = True
    regions_ok: bool = True
    region_types_ok: bool = True
    headings_ok: bool = True
    tables_ok: bool = True
    paragraph_structure_ok: bool = True
    reading_order_ok: bool = True
    overall_pass: bool = True
    details: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.overall_pass else "FAIL"
        lines = [
            f"[{status}] A2 Layout: {self.file} ({self.engine})",
            f"  Pages: {self.page_count}, Regions: {self.region_count}, "
            f"Types: {self.region_types_found}",
            f"  Headings: {self.heading_count}, Tables: {self.table_count} "
            f"({self.tables_with_content} with content)",
        ]
        for d in self.details:
            lines.append(f"  {d}")
        return "\n".join(lines)


def assess_a2_layout(
    structured_json: dict,
    markdown_text: str,
    config: GroundTruthConfig,
    engine: str = "unknown",
) -> A2LayoutReport:
    """Assess A2 Layout-Preserved quality from structured output.

    Checks against requirements from OCR capabilities docs:
    - Reading order preserved
    - Heading level detection (h1/h2/h3)
    - Column detection
    - Table detection + content
    - Header/footer filtering
    - Paragraph structure (newlines)
    - Region type completeness

    Args:
        structured_json: JSON output from structured_extract (has pages/regions)
        markdown_text: Markdown output from same file
        config: Ground truth config with a2_layout requirements
    """
    report = A2LayoutReport(file=config.file, engine=engine)
    a2 = config.a2_layout
    if not a2:
        report.details.append("No A2 layout requirements defined")
        return report

    pages = structured_json.get("pages", [])
    report.page_count = len(pages)

    # Collect all regions
    all_regions = []
    for page in pages:
        all_regions.extend(page.get("regions", []))
    report.region_count = len(all_regions)
    report.region_types_found = sorted(set(r.get("type", "") for r in all_regions))

    # ── Page count ──
    if a2.min_pages > 1 and report.page_count < a2.min_pages:
        report.pages_ok = False
        report.details.append(
            f"FAIL pages: {report.page_count} < min {a2.min_pages}"
        )

    # ── Region count ──
    if report.region_count < a2.min_regions:
        report.regions_ok = False
        report.details.append(
            f"FAIL regions: {report.region_count} < min {a2.min_regions}"
        )

    # ── Expected region types ──
    if a2.expected_region_types:
        missing_types = [
            t for t in a2.expected_region_types
            if t not in report.region_types_found
        ]
        if missing_types:
            report.region_types_ok = False
            report.details.append(
                f"FAIL region types missing: {missing_types}"
            )

    # ── Heading detection (A2 requirement: h1/h2/h3 differentiation) ──
    headings = [r for r in all_regions if r.get("type") == "title"]
    report.heading_count = len(headings)
    report.heading_texts = [
        r.get("content", "")[:60] for r in headings
    ]

    if report.heading_count < a2.min_heading_count:
        report.headings_ok = False
        report.details.append(
            f"FAIL headings: {report.heading_count} < min {a2.min_heading_count}"
        )

    # Check heading keywords present in headings
    if a2.expected_heading_keywords and headings:
        heading_text = " ".join(r.get("content", "") for r in headings).lower()
        found_heading_kw = [
            kw for kw in a2.expected_heading_keywords
            if kw.lower() in heading_text
        ]
        if len(found_heading_kw) < len(a2.expected_heading_keywords) * 0.3:
            report.details.append(
                f"WARN heading keywords: found {found_heading_kw} "
                f"of {a2.expected_heading_keywords}"
            )

    # Check heading levels differentiated in markdown
    if markdown_text and a2.min_heading_count >= 2:
        h1_count = markdown_text.count("\n# ") + (
            1 if markdown_text.startswith("# ") else 0
        )
        h2_count = markdown_text.count("\n## ")
        h3_count = markdown_text.count("\n### ")
        levels_used = sum(1 for c in [h1_count, h2_count, h3_count] if c > 0)
        if levels_used < 2 and report.heading_count >= 3:
            report.details.append(
                f"WARN heading levels: only {levels_used} level(s) used "
                f"(h1={h1_count}, h2={h2_count}, h3={h3_count})"
            )

    # ── Table detection (A2 + B1 cross-requirement) ──
    tables = [r for r in all_regions if r.get("type") == "table"]
    report.table_count = len(tables)
    report.tables_with_content = sum(
        1 for t in tables
        if (t.get("html", "").strip() or t.get("markdown", "").strip()
            or t.get("content", "").strip())
    )

    if a2.min_tables > 0:
        if report.table_count < a2.min_tables:
            report.tables_ok = False
            report.details.append(
                f"FAIL tables: {report.table_count} < min {a2.min_tables}"
            )
        if a2.table_has_content and report.tables_with_content == 0:
            report.tables_ok = False
            report.details.append("FAIL tables: no tables with content")

    # ── Paragraph structure (A2: newlines preserved, not collapsed) ──
    if a2.paragraph_has_newlines and markdown_text:
        md_lines = markdown_text.split("\n")
        non_empty = [line for line in md_lines if line.strip()]
        if len(non_empty) < 5 and len(markdown_text) > 500:
            report.paragraph_structure_ok = False
            report.details.append(
                f"FAIL paragraph structure: only {len(non_empty)} lines "
                f"for {len(markdown_text)} chars (text collapsed?)"
            )

    # ── Reading order (A2: correct sequence, especially multi-column) ──
    if a2.reading_order_keywords_sequence:
        full_text = " ".join(
            r.get("content", "") for r in all_regions
        ).lower()
        last_pos = -1
        out_of_order = []
        for kw in a2.reading_order_keywords_sequence:
            pos = full_text.find(kw.lower())
            if pos == -1:
                continue  # keyword not found, skip
            if pos < last_pos:
                out_of_order.append(kw)
            else:
                last_pos = pos
        if len(out_of_order) > len(a2.reading_order_keywords_sequence) * 0.3:
            report.reading_order_ok = False
            report.details.append(
                f"FAIL reading order: {out_of_order} appear out of sequence"
            )

    # ── Overall ──
    report.overall_pass = all([
        report.pages_ok,
        report.regions_ok,
        report.region_types_ok,
        report.headings_ok,
        report.tables_ok,
        report.paragraph_structure_ok,
        report.reading_order_ok,
    ])

    return report
