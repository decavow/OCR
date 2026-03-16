# Output extraction and formatting for PaddleOCR-VL structured results

import json
import logging
import re
from html.parser import HTMLParser
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# V3 label mapping: PaddleX layout labels → standard region types
# ---------------------------------------------------------------------------
_V3_LABEL_MAP = {
    "text": "text",
    "paragraph": "text",
    "title": "title",
    "table": "table",
    "table_body": "table",
    "table_caption": "text",
    "figure": "figure",
    "image": "figure",
    "figure_caption": "text",
    "list": "list",
    "list_item": "list",
    "header": "text",
    "footer": "text",
    "reference": "text",
    "equation": "text",
    "seal": "figure",
}


def _strip_html_wrapper(html: str) -> str:
    """Strip <html><body>...</body></html> wrapper if present."""
    html = re.sub(r'</?html[^>]*>', '', html)
    html = re.sub(r'</?body[^>]*>', '', html)
    return html.strip()


def _is_valid_table_html(html: str) -> bool:
    """Check if table HTML has a valid structure (proper <tr> and <td>/<th> tags)."""
    if not html:
        return False
    cleaned = _strip_html_wrapper(html)
    # Must have at least one properly closed <tr>...</tr> with <td> or <th> inside
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', cleaned, re.DOTALL)
    if not rows:
        return False
    # At least one row must have properly closed cell tags
    for row in rows:
        cells = re.findall(r'<t[dh][^>]*>.*?</t[dh]>', row, re.DOTALL)
        if cells:
            return True
    return False


def _extract_text_from_table_res(table_res: dict) -> str:
    """Try to extract text content from a table res dict.

    PPStructure table res may contain 'rec_res' with OCR text results
    even when HTML generation fails.
    """
    texts = []
    # rec_res: list of (text, confidence) tuples
    rec_res = table_res.get("rec_res", [])
    for item in rec_res:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            texts.append(str(item[0]))
        elif isinstance(item, str):
            texts.append(item)
    return " ".join(texts)


def _parse_v3_block(block: dict) -> dict | None:
    """Parse a single PPStructureV3 block into a standard region dict.

    Handles blocks from PaddleX PP-StructureV3 pipeline output.
    Returns None if block has no usable content.
    """
    raw_label = (
        block.get("layout_label") or block.get("type") or "text"
    ).lower().strip()
    region_type = _V3_LABEL_MAP.get(raw_label, "text")

    # Extract bounding box
    bbox_raw = block.get("layout_bbox") or block.get("bbox") or [0, 0, 0, 0]
    try:
        bbox_list = bbox_raw.tolist() if hasattr(bbox_raw, "tolist") else list(bbox_raw)
        bbox = [int(x) for x in bbox_list[:4]] if len(bbox_list) >= 4 else [0, 0, 0, 0]
    except (TypeError, ValueError):
        bbox = [0, 0, 0, 0]

    if region_type == "table":
        html = block.get("table_html") or block.get("html") or ""
        # Also check nested res dict (PPStructure v2 compat)
        if not html and isinstance(block.get("res"), dict):
            html = block["res"].get("html", "")
        html = _strip_html_wrapper(html) if html else ""

        if html and _is_valid_table_html(html):
            return {
                "type": "table",
                "bbox": bbox,
                "html": html,
                "markdown": html_table_to_markdown(html),
            }
        # Fallback: extract text from table region
        rec_texts = block.get("rec_texts", [])
        if rec_texts:
            return {
                "type": "text",
                "bbox": bbox,
                "content": "\n".join(str(t) for t in rec_texts),
                "confidence": 0.0,
            }
        return None

    if region_type == "figure":
        return {"type": "figure", "bbox": bbox, "caption": None}

    # text, title, list
    rec_texts = block.get("rec_texts", [])
    rec_scores = block.get("rec_scores", [])

    if not rec_texts:
        # Try alternative content keys
        content = block.get("content") or block.get("text") or ""
        if not content:
            return None
        rec_texts = [content]

    content = "\n".join(str(t) for t in rec_texts)
    if not content.strip():
        return None

    avg_conf = (
        sum(float(s) for s in rec_scores) / len(rec_scores)
        if rec_scores
        else 0.0
    )
    return {
        "type": region_type,
        "bbox": bbox,
        "content": content,
        "confidence": round(avg_conf, 4),
    }


def extract_regions(raw_result: list, page_idx: int) -> Dict[str, Any]:
    """Extract structured regions from PPStructure output.

    PPStructure output format per region:
    {
        "type": "text" | "table" | "title" | "figure" | "list",
        "bbox": [x1, y1, x2, y2],
        "res": [  # for text/title/list
            { "text": "...", "confidence": 0.95, "text_region": [...] }
        ]
        # or for table:
        "res": {
            "html": "<table>...</table>",
            "cell_bbox": [...],
            "rec_res": [("text", 0.95), ...]
        }
    }
    """
    regions = []

    if not raw_result:
        return {"page_number": page_idx + 1, "regions": []}

    for item in raw_result:
        region_type = item.get("type", "text")
        bbox = item.get("bbox", [0, 0, 0, 0])

        if region_type == "table":
            table_res = item.get("res", {})
            # When table=False fallback, res may be a list of OCR results or a string
            if isinstance(table_res, dict):
                raw_html = table_res.get("html", "")
                html = _strip_html_wrapper(raw_html)

                if _is_valid_table_html(raw_html):
                    regions.append({
                        "type": "table",
                        "bbox": bbox,
                        "html": html,
                        "markdown": html_table_to_markdown(html),
                    })
                else:
                    # Invalid table HTML — try to salvage text from rec_res
                    fallback_text = _extract_text_from_table_res(table_res)
                    if fallback_text.strip():
                        logger.debug(
                            f"Table region at {bbox} has invalid HTML, "
                            f"falling back to text: {fallback_text[:80]}..."
                        )
                        regions.append({
                            "type": "text",
                            "bbox": bbox,
                            "content": fallback_text,
                            "confidence": 0.0,
                        })
                    else:
                        logger.debug(
                            f"Table region at {bbox} has invalid HTML "
                            "and no recoverable text, skipping"
                        )
            elif isinstance(table_res, list):
                # Fallback: treat table region as text
                text_parts = []
                for text_item in table_res:
                    if isinstance(text_item, dict):
                        text_parts.append(text_item.get("text", ""))
                regions.append({
                    "type": "text",
                    "bbox": bbox,
                    "content": " ".join(text_parts),
                    "confidence": 0.0,
                })
            else:
                regions.append({
                    "type": "text",
                    "bbox": bbox,
                    "content": str(table_res) if table_res else "",
                    "confidence": 0.0,
                })

        elif region_type in ("text", "title", "list"):
            res_list = item.get("res", [])
            text_parts = []
            confidence_sum = 0.0
            count = 0

            for text_item in res_list:
                text_parts.append(text_item.get("text", ""))
                confidence_sum += text_item.get("confidence", 0.0)
                count += 1

            content = "\n".join(text_parts)
            avg_confidence = confidence_sum / count if count > 0 else 0.0

            regions.append({
                "type": region_type,
                "bbox": bbox,
                "content": content,
                "confidence": round(avg_confidence, 4),
            })

        elif region_type == "figure":
            regions.append({
                "type": "figure",
                "bbox": bbox,
                "caption": None,
            })

    # Sort by reading order: top-to-bottom, then left-to-right
    regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

    # Log intermediate data structure
    _log_region_breakdown(regions, page_idx)

    return {
        "page_number": page_idx + 1,
        "regions": regions,
    }


def extract_regions_v3(raw_results: list, page_idx: int) -> Dict[str, Any]:
    """Extract structured regions from PPStructureV3 output.

    PPStructureV3 (PaddleX) may return results in several formats:
      A) List with one result dict containing ``parsing_result`` key
      B) List of block dicts each having ``layout_label``/``type``
      C) Legacy format with flat ``rec_texts``

    All formats are normalised to the standard
    ``{"page_number": N, "regions": [...]}`` structure.
    """
    regions: List[Dict[str, Any]] = []

    if not raw_results:
        return {"page_number": page_idx + 1, "regions": []}

    for r in raw_results:
        if not hasattr(r, "get"):
            continue

        # Format A: PaddleX PP-StructureV3 with parsing_result
        parsing_result = r.get("parsing_result")
        if parsing_result and isinstance(parsing_result, list):
            for block in parsing_result:
                if isinstance(block, dict):
                    region = _parse_v3_block(block)
                    if region:
                        regions.append(region)
            continue

        # Format B: Direct block with layout info
        if r.get("layout_label") or r.get("type"):
            region = _parse_v3_block(r)
            if region:
                regions.append(region)
            continue

        # Format C: Legacy flat rec_texts (no layout info)
        rec_texts = r.get("rec_texts", [])
        if rec_texts:
            rec_scores = r.get("rec_scores", [])
            avg_conf = (
                sum(float(s) for s in rec_scores) / len(rec_scores)
                if rec_scores
                else 0.0
            )
            bbox_raw = r.get("bbox") or r.get("layout_bbox") or [0, 0, 0, 0]
            try:
                bbox = (
                    [int(x) for x in bbox_raw.tolist()[:4]]
                    if hasattr(bbox_raw, "tolist")
                    else [int(x) for x in list(bbox_raw)[:4]]
                )
            except (TypeError, ValueError):
                bbox = [0, 0, 0, 0]
            regions.append({
                "type": "text",
                "bbox": bbox if len(bbox) >= 4 else [0, 0, 0, 0],
                "content": "\n".join(str(t) for t in rec_texts),
                "confidence": round(avg_conf, 4),
            })

    # Sort by reading order: top-to-bottom, then left-to-right
    regions.sort(
        key=lambda r: (r["bbox"][1], r["bbox"][0])
        if len(r.get("bbox", [])) >= 2
        else (0, 0)
    )
    _log_region_breakdown(regions, page_idx)

    return {"page_number": page_idx + 1, "regions": regions}


def _log_region_breakdown(regions: list, page_idx: int) -> None:
    """Log region type counts, confidence stats, and content preview."""
    type_counts = {}
    confidences = []
    for r in regions:
        t = r.get("type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
        if "confidence" in r:
            confidences.append(r["confidence"])

    counts_str = ", ".join(f"{v} {k}" for k, v in sorted(type_counts.items()))
    logger.debug(
        f"Page {page_idx + 1}: {len(regions)} regions ({counts_str})"
    )

    if confidences:
        logger.debug(
            f"  Confidence: min={min(confidences):.2f} "
            f"avg={sum(confidences)/len(confidences):.2f} "
            f"max={max(confidences):.2f}"
        )

    # Preview first few regions
    for r in regions[:5]:
        rtype = r.get("type", "?")
        bbox = r.get("bbox", [])
        if rtype in ("text", "title", "list"):
            content = r.get("content", "")[:80]
            conf = r.get("confidence", 0)
            logger.debug(f"  [{rtype}] bbox={bbox} conf={conf:.2f} {content!r}")
        elif rtype == "table":
            md_preview = r.get("markdown", "")[:60]
            logger.debug(f"  [table] bbox={bbox} md={md_preview!r}")
        elif rtype == "figure":
            logger.debug(f"  [figure] bbox={bbox}")
    if len(regions) > 5:
        logger.debug(f"  ... +{len(regions) - 5} more regions")


def extract_regions_from_raw_ocr(raw_ocr: list, page_idx: int) -> Dict[str, Any]:
    """Convert raw PaddleOCR output to structured region format.

    PaddleOCR.ocr() returns:
    [  # per page
        [  # list of detected text lines
            ([[x1,y1],[x2,y2],[x3,y3],[x4,y4]], ("text", confidence)),
            ...
        ]
    ]
    """
    regions = []

    if not raw_ocr:
        return {"page_number": page_idx + 1, "regions": []}

    # raw_ocr may be a list of pages or a single page result
    lines = raw_ocr
    if lines and isinstance(lines[0], list) and len(lines[0]) > 0:
        # Check if it's nested page list: [[ [box, (text, conf)], ... ]]
        first = lines[0]
        if isinstance(first, list) and len(first) > 0 and isinstance(first[0], list):
            # It's a list of pages, take the first (we process one image at a time)
            lines = first

    for line in lines:
        if not line or not isinstance(line, (list, tuple)) or len(line) < 2:
            continue

        box, text_info = line[0], line[1]

        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
            text = str(text_info[0])
            confidence = float(text_info[1])
        elif isinstance(text_info, str):
            text = text_info
            confidence = 0.0
        else:
            continue

        if not text.strip():
            continue

        # Convert 4-point box to [x1, y1, x2, y2] bounding box
        if box and len(box) >= 4:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        else:
            bbox = [0, 0, 0, 0]

        regions.append({
            "type": "text",
            "bbox": bbox,
            "content": text,
            "confidence": round(confidence, 4),
        })

    # Sort by reading order: top-to-bottom, then left-to-right
    regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

    if regions:
        confs = [r["confidence"] for r in regions]
        logger.debug(
            f"Page {page_idx + 1} (raw OCR): {len(regions)} text lines, "
            f"confidence [{min(confs):.2f} - {max(confs):.2f}]"
        )
        for r in regions[:3]:
            logger.debug(
                f"  bbox={r['bbox']} conf={r['confidence']:.2f} "
                f"{r['content'][:60]!r}"
            )
        if len(regions) > 3:
            logger.debug(f"  ... +{len(regions) - 3} more lines")
    else:
        logger.debug(f"Page {page_idx + 1} (raw OCR): 0 text lines")

    return {
        "page_number": page_idx + 1,
        "regions": regions,
    }


def extract_regions_v3_ocr_fallback(
    raw_results: list, page_idx: int
) -> Dict[str, Any]:
    """Extract text from PaddleOCR v3 pure OCR output (fallback path).

    PaddleOCR v3 ``predict()`` returns dicts with ``rec_texts``,
    ``rec_scores``, and ``rec_polys``.  Each text line becomes its own
    region for better reading-order granularity.
    """
    regions: List[Dict[str, Any]] = []

    if not raw_results:
        return {"page_number": page_idx + 1, "regions": []}

    for r in raw_results:
        if not hasattr(r, "get"):
            continue

        rec_texts = r.get("rec_texts", [])
        rec_scores = r.get("rec_scores", [])
        rec_polys = r.get("rec_polys", [])

        if not rec_texts:
            continue

        for i, text in enumerate(rec_texts):
            text_str = str(text).strip()
            if not text_str:
                continue

            score = float(rec_scores[i]) if i < len(rec_scores) else 0.0

            bbox = [0, 0, 0, 0]
            if i < len(rec_polys) and rec_polys[i] is not None:
                poly = rec_polys[i]
                if hasattr(poly, "tolist"):
                    poly = poly.tolist()
                if poly and len(poly) >= 4:
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]

            regions.append({
                "type": "text",
                "bbox": bbox,
                "content": text_str,
                "confidence": round(score, 4),
            })

    regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

    if regions:
        confs = [r["confidence"] for r in regions]
        logger.debug(
            f"Page {page_idx + 1} (v3 OCR fallback): {len(regions)} text lines, "
            f"confidence [{min(confs):.2f} - {max(confs):.2f}]"
        )

    return {"page_number": page_idx + 1, "regions": regions}


def assess_result_quality(pages: List[Dict[str, Any]]) -> bool:
    """Check if structured result quality is acceptable.

    Returns False when results are clearly garbage — e.g. all table regions
    with no valid HTML content and zero text blocks.
    """
    total_regions = 0
    valid_tables = 0
    text_blocks = 0
    empty_tables = 0

    for page in pages:
        for region in page.get("regions", []):
            total_regions += 1
            if region["type"] == "table":
                html = region.get("html", "")
                md = region.get("markdown", "")
                if html and md:
                    valid_tables += 1
                else:
                    empty_tables += 1
            elif region["type"] in ("text", "title", "list"):
                if region.get("content", "").strip():
                    text_blocks += 1

    if total_regions == 0:
        return False

    # No meaningful content at all
    if valid_tables == 0 and text_blocks == 0:
        logger.warning(
            f"Poor quality result: {total_regions} regions but "
            f"0 valid tables, 0 text blocks with content"
        )
        return False

    return True


def _strip_inner_html(text: str) -> str:
    """Remove HTML tags from cell content, preserving text."""
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# HTML table parser with colspan/rowspan support
# ---------------------------------------------------------------------------


class _TableHTMLParser(HTMLParser):
    """Parse HTML table structure including colspan and rowspan attributes."""

    def __init__(self):
        super().__init__()
        self.rows: List[List[dict]] = []
        self._current_row: List[dict] = []
        self._current_cell: List[str] = []
        self._in_cell = False
        self._cell_colspan = 1
        self._cell_rowspan = 1

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []
            try:
                self._cell_colspan = int(attrs_dict.get("colspan", 1))
            except (ValueError, TypeError):
                self._cell_colspan = 1
            try:
                self._cell_rowspan = int(attrs_dict.get("rowspan", 1))
            except (ValueError, TypeError):
                self._cell_rowspan = 1
        elif tag == "br" and self._in_cell:
            self._current_cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            content = " ".join("".join(self._current_cell).split())
            self._current_row.append({
                "content": content,
                "colspan": self._cell_colspan,
                "rowspan": self._cell_rowspan,
            })
        elif tag == "tr" and self._current_row:
            self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data)


def _build_table_grid(parsed_rows: List[List[dict]]) -> List[List[str]]:
    """Expand colspan/rowspan cells into a full rectangular grid."""
    if not parsed_rows:
        return []

    # Determine grid width
    max_cols = 0
    for row in parsed_rows:
        col_count = sum(cell["colspan"] for cell in row)
        max_cols = max(max_cols, col_count)

    num_rows = len(parsed_rows)
    # None = unfilled slot
    grid: list = [[None] * max_cols for _ in range(num_rows)]

    for row_idx, row in enumerate(parsed_rows):
        col_idx = 0
        for cell in row:
            # Advance past already-filled slots (from previous rowspan)
            while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                col_idx += 1
            if col_idx >= max_cols:
                break

            content = cell["content"]
            colspan = min(cell["colspan"], max_cols - col_idx)
            rowspan = min(cell["rowspan"], num_rows - row_idx)

            for dr in range(rowspan):
                for dc in range(colspan):
                    r, c = row_idx + dr, col_idx + dc
                    if r < num_rows and c < max_cols:
                        grid[r][c] = content

            col_idx += colspan

    return [[(cell if cell is not None else "") for cell in row] for row in grid]


def _grid_to_markdown(grid: List[List[str]]) -> str:
    """Convert a 2D string grid to a Markdown pipe table."""
    if not grid:
        return ""

    max_cols = max(len(row) for row in grid)
    for row in grid:
        while len(row) < max_cols:
            row.append("")

    md_rows = []
    for i, row in enumerate(grid):
        md_rows.append("| " + " | ".join(row) + " |")
        if i == 0:
            md_rows.append("|" + "|".join(["---"] * max_cols) + "|")

    return "\n".join(md_rows)


def _html_table_to_markdown_regex(cleaned: str) -> str:
    """Regex-based table conversion (fallback when HTMLParser fails)."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', cleaned, re.DOTALL)
    if not rows:
        return ""

    parsed_rows = []
    max_cols = 0
    for row in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        cells = [_strip_inner_html(c) for c in cells]
        if cells:
            max_cols = max(max_cols, len(cells))
            parsed_rows.append(cells)

    if not parsed_rows:
        return ""

    md_rows = []
    for i, cells in enumerate(parsed_rows):
        while len(cells) < max_cols:
            cells.append("")
        md_rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            md_rows.append("|" + "|".join(["---"] * max_cols) + "|")

    return "\n".join(md_rows)


def html_table_to_markdown(html: str) -> str:
    """Convert HTML table to Markdown table format.

    Handles colspan, rowspan, and inner HTML tags in cells.
    Falls back to simple regex parsing if HTMLParser encounters issues.
    """
    cleaned = _strip_html_wrapper(html)
    if not cleaned:
        return ""

    # Try structured parsing (handles colspan/rowspan)
    try:
        parser = _TableHTMLParser()
        parser.feed(cleaned)
        if parser.rows:
            grid = _build_table_grid(parser.rows)
            if grid:
                return _grid_to_markdown(grid)
    except Exception:
        pass

    # Fallback: simple regex
    return _html_table_to_markdown_regex(cleaned)


# ---------------------------------------------------------------------------
# Layout intelligence helpers
# ---------------------------------------------------------------------------


def _detect_heading_levels(regions: List[Dict]) -> None:
    """Detect heading levels based on bbox height.  Modifies *regions* in-place.

    Strategy:
      - 1 title → h1
      - 2 distinct heights → larger = h1, smaller = h2
      - 3+ distinct heights → percentile-based h1/h2/h3
    """
    titles = [
        r
        for r in regions
        if r.get("type") == "title" and len(r.get("bbox", [])) >= 4
    ]
    if not titles:
        return

    if len(titles) == 1:
        titles[0]["heading_level"] = 1
        return

    heights = [r["bbox"][3] - r["bbox"][1] for r in titles]
    unique_heights = sorted(set(heights), reverse=True)

    if len(unique_heights) == 1:
        for r in titles:
            r["heading_level"] = 1
    elif len(unique_heights) == 2:
        largest = unique_heights[0]
        for r in titles:
            h = r["bbox"][3] - r["bbox"][1]
            r["heading_level"] = 1 if h == largest else 2
    else:
        sorted_h = sorted(heights)
        p75 = sorted_h[max(0, int(len(sorted_h) * 0.75) - 1)]
        p25 = sorted_h[max(0, int(len(sorted_h) * 0.25))]
        for r in titles:
            h = r["bbox"][3] - r["bbox"][1]
            if h >= p75:
                r["heading_level"] = 1
            elif h >= p25:
                r["heading_level"] = 2
            else:
                r["heading_level"] = 3


def _reorder_by_columns(regions: List[Dict]) -> List[Dict]:
    """Detect two-column layout and reorder to left-column-first reading order.

    Returns *regions* unchanged when:
      - fewer than 3 regions
      - no clear vertical gap separating columns
      - all regions are full-width
    """
    if len(regions) < 3:
        return regions

    with_bbox = [
        r
        for r in regions
        if len(r.get("bbox", [])) >= 4 and r["bbox"][2] > r["bbox"][0]
    ]
    if len(with_bbox) < 3:
        return regions

    page_width = max(r["bbox"][2] for r in with_bbox)
    if page_width <= 0:
        return regions

    full_width_threshold = 0.7 * page_width
    full_width: List[Dict] = []
    narrow: List[Dict] = []

    for r in regions:
        bbox = r.get("bbox", [0, 0, 0, 0])
        if len(bbox) < 4 or bbox[2] <= bbox[0]:
            full_width.append(r)
            continue
        if (bbox[2] - bbox[0]) >= full_width_threshold:
            full_width.append(r)
        else:
            narrow.append(r)

    if len(narrow) < 2:
        return regions

    mid = page_width / 2
    left = [r for r in narrow if (r["bbox"][0] + r["bbox"][2]) / 2 < mid]
    right = [r for r in narrow if (r["bbox"][0] + r["bbox"][2]) / 2 >= mid]

    if not left or not right:
        return regions

    left_max_x = max(r["bbox"][2] for r in left)
    right_min_x = min(r["bbox"][0] for r in right)
    gap = right_min_x - left_max_x

    if gap < 0.03 * page_width:
        return regions  # No clear column gap

    left.sort(key=lambda r: r["bbox"][1])
    right.sort(key=lambda r: r["bbox"][1])
    full_width.sort(key=lambda r: r.get("bbox", [0, 0, 0, 0])[1])

    result: List[Dict] = []
    fw_idx = 0

    for col in [left, right]:
        for r in col:
            while (
                fw_idx < len(full_width)
                and full_width[fw_idx].get("bbox", [0, 0, 0, 0])[1] <= r["bbox"][1]
            ):
                result.append(full_width[fw_idx])
                fw_idx += 1
            result.append(r)

    while fw_idx < len(full_width):
        result.append(full_width[fw_idx])
        fw_idx += 1

    return result


def _split_list_items(content: str) -> List[str]:
    """Split list region content into individual items.

    Handles numbered (``1.``, ``2)``) and bullet (``-``, ``•``) markers.
    Falls back to the whole content as a single item.
    """
    if not content:
        return []

    lines = content.split("\n")
    items: List[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip existing bullet / number markers
        cleaned = re.sub(
            r"^[\-\•\*\u2022\u2023\u25e6\u2043\u2219]\s*", "", line
        )
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        if cleaned:
            items.append(cleaned)

    return items if items else ([content.strip()] if content.strip() else [])


def _filter_headers_footers(pages: List[Dict[str, Any]]) -> None:
    """Remove repeating headers/footers across pages.  Modifies *pages* in-place.

    Only applies when document has >= 3 pages.  Text appearing at similar
    positions (top/bottom 8%) on >= 60% of pages is considered repeating.
    Page-number patterns at the bottom are also filtered.
    """
    if len(pages) < 3:
        return

    # Estimate page height from max bbox y2 per page
    page_heights: List[float] = []
    for page in pages:
        regions = page.get("regions", [])
        ys = [
            r["bbox"][3]
            for r in regions
            if len(r.get("bbox", [])) >= 4 and r["bbox"][3] > 0
        ]
        page_heights.append(max(ys) if ys else 0)

    avg_height = sum(page_heights) / len(page_heights) if page_heights else 0
    if avg_height <= 0:
        return

    top_threshold = 0.08 * avg_height
    bottom_threshold = 0.92 * avg_height

    # Collect normalised text candidates per page
    header_texts: List[set] = []
    footer_texts: List[set] = []

    for page in pages:
        h_set: set = set()
        f_set: set = set()
        for region in page.get("regions", []):
            if region.get("type") not in ("text", "title"):
                continue
            content = region.get("content", "").strip()
            if not content:
                continue
            bbox = region.get("bbox", [0, 0, 0, 0])
            if len(bbox) < 4:
                continue
            # Normalise digits so page numbers match across pages
            normalised = re.sub(r"\b\d+\b", "#", content).strip()
            if bbox[1] < top_threshold:
                h_set.add(normalised)
            elif bbox[3] > bottom_threshold:
                f_set.add(normalised)
        header_texts.append(h_set)
        footer_texts.append(f_set)

    # Find texts appearing on >= 60% of pages
    threshold_count = len(pages) * 0.6

    header_counts: Dict[str, int] = {}
    footer_counts: Dict[str, int] = {}
    for texts in header_texts:
        for t in texts:
            header_counts[t] = header_counts.get(t, 0) + 1
    for texts in footer_texts:
        for t in texts:
            footer_counts[t] = footer_counts.get(t, 0) + 1

    repeating_headers = {t for t, c in header_counts.items() if c >= threshold_count}
    repeating_footers = {t for t, c in footer_counts.items() if c >= threshold_count}

    page_num_pattern = re.compile(
        r"^(Page\s+\d+|Trang\s+\d+|\d+)$", re.IGNORECASE
    )

    if not repeating_headers and not repeating_footers and not page_num_pattern:
        return

    removed = 0
    for page in pages:
        filtered: List[Dict] = []
        for region in page.get("regions", []):
            content = region.get("content", "").strip()
            bbox = region.get("bbox", [0, 0, 0, 0])
            should_remove = False

            if content and len(bbox) >= 4:
                normalised = re.sub(r"\b\d+\b", "#", content).strip()
                if bbox[1] < top_threshold and normalised in repeating_headers:
                    should_remove = True
                elif bbox[3] > bottom_threshold and normalised in repeating_footers:
                    should_remove = True
                elif bbox[3] > bottom_threshold and page_num_pattern.match(content):
                    should_remove = True

            if should_remove:
                removed += 1
            else:
                filtered.append(region)
        page["regions"] = filtered

    if removed:
        logger.debug(
            f"Filtered {removed} header/footer regions across {len(pages)} pages"
        )


def _merge_adjacent_paragraphs(regions: List[Dict]) -> List[Dict]:
    """Merge adjacent text regions that belong to the same paragraph.

    Two text regions are merged when both are type ``text``, their
    x-extent overlaps by > 50 %, and the vertical gap is < 1.5 x the
    average text-region height.
    """
    if len(regions) < 2:
        return regions

    text_heights = [
        r["bbox"][3] - r["bbox"][1]
        for r in regions
        if r.get("type") == "text"
        and len(r.get("bbox", [])) >= 4
        and r["bbox"][3] > r["bbox"][1]
    ]
    if not text_heights:
        return regions

    avg_height = sum(text_heights) / len(text_heights)
    merge_threshold = 1.5 * avg_height

    merged: List[Dict] = [regions[0]]

    for i in range(1, len(regions)):
        current = regions[i]
        prev = merged[-1]

        can_merge = (
            prev.get("type") == "text"
            and current.get("type") == "text"
            and len(prev.get("bbox", [])) >= 4
            and len(current.get("bbox", [])) >= 4
        )
        if can_merge:
            # X overlap ratio
            overlap_start = max(prev["bbox"][0], current["bbox"][0])
            overlap_end = min(prev["bbox"][2], current["bbox"][2])
            overlap_w = max(0, overlap_end - overlap_start)
            min_w = min(
                prev["bbox"][2] - prev["bbox"][0],
                current["bbox"][2] - current["bbox"][0],
            )
            x_ratio = overlap_w / min_w if min_w > 0 else 0

            y_gap = current["bbox"][1] - prev["bbox"][3]

            if x_ratio > 0.5 and 0 <= y_gap < merge_threshold:
                merged[-1] = {
                    "type": "text",
                    "bbox": [
                        min(prev["bbox"][0], current["bbox"][0]),
                        prev["bbox"][1],
                        max(prev["bbox"][2], current["bbox"][2]),
                        current["bbox"][3],
                    ],
                    "content": prev.get("content", "") + "\n" + current.get("content", ""),
                    "confidence": round(
                        (prev.get("confidence", 0) + current.get("confidence", 0)) / 2,
                        4,
                    ),
                }
                continue

        merged.append(current)

    if len(merged) < len(regions):
        logger.debug(
            f"Merged {len(regions) - len(merged)} adjacent text regions "
            f"({len(regions)} -> {len(merged)})"
        )
    return merged


_CAPTION_PATTERN = re.compile(
    r"^(Figure|Fig\.?|Hình|Ảnh|Image)\s*\.?\s*\d*",
    re.IGNORECASE,
)


def _extract_figure_captions(regions: List[Dict]) -> None:
    """Assign captions to figure regions from adjacent text.  Modifies in-place.

    When a text region immediately following a figure matches a caption
    keyword (Figure, Fig., Hình …), it is consumed as the figure's caption.
    """
    if len(regions) < 2:
        return

    indices_to_remove: set = set()

    for i, region in enumerate(regions):
        if region.get("type") != "figure":
            continue
        if i + 1 >= len(regions):
            continue

        next_region = regions[i + 1]
        if next_region.get("type") != "text":
            continue

        content = next_region.get("content", "").strip()
        if _CAPTION_PATTERN.match(content):
            region["caption"] = content
            indices_to_remove.add(i + 1)

    if indices_to_remove:
        for idx in sorted(indices_to_remove, reverse=True):
            regions.pop(idx)
        logger.debug(f"Extracted {len(indices_to_remove)} figure caption(s)")


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCR Result</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 960px; margin: 0 auto; padding: 2rem; line-height: 1.6; color: #333; }}
h1 {{ font-size: 1.5em; margin: 1.2em 0 0.6em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background-color: #f5f5f5; font-weight: 600; }}
tr:nth-child(even) {{ background-color: #fafafa; }}
.page-break {{ border-top: 2px solid #ccc; margin: 2em 0; padding-top: 0.5em; color: #666;
  font-size: 0.9em; font-weight: 600; }}
.figure {{ background: #f9f9f9; border: 1px dashed #ccc; padding: 1em;
  text-align: center; color: #999; margin: 1em 0; }}
figure {{ margin: 1em 0; text-align: center; }}
figcaption {{ font-size: 0.9em; color: #555; margin-top: 0.3em; font-style: italic; }}
ul {{ margin: 0.5em 0; }}
p {{ margin: 0.5em 0; }}
</style>
</head>
<body>
{content}
</body>
</html>"""


def _format_html(pages: List[Dict[str, Any]]) -> str:
    """Format structured results as a self-contained HTML document."""
    parts = []

    for page in pages:
        if len(pages) > 1:
            parts.append(
                f'<div class="page-break">Page {page["page_number"]}</div>'
            )

        for region in page["regions"]:
            rtype = region["type"]

            if rtype == "title":
                level = region.get("heading_level", 1)
                tag = f"h{min(level, 6)}"
                content = _escape_html(region.get("content", ""))
                parts.append(f"<{tag}>{content}</{tag}>")

            elif rtype == "table":
                html = region.get("html", "")
                if html:
                    parts.append(html)
                else:
                    md = region.get("markdown", "")
                    parts.append(f"<pre>{_escape_html(md)}</pre>")

            elif rtype == "list":
                items = _split_list_items(region.get("content", ""))
                if items:
                    parts.append("<ul>")
                    for item in items:
                        parts.append(f"  <li>{_escape_html(item)}</li>")
                    parts.append("</ul>")

            elif rtype == "text":
                content = _escape_html(region.get("content", ""))
                parts.append(f"<p>{content}</p>")

            elif rtype == "figure":
                caption = region.get("caption")
                if caption:
                    parts.append(
                        f'<figure><div class="figure">[Figure]</div>'
                        f"<figcaption>{_escape_html(caption)}</figcaption></figure>"
                    )
                else:
                    parts.append('<div class="figure">[Figure]</div>')

    content = "\n".join(parts)
    return _HTML_TEMPLATE.format(content=content)


def _format_markdown(pages: List[Dict[str, Any]]) -> str:
    """Format structured results as Markdown document."""
    parts = []

    for page in pages:
        if len(pages) > 1:
            parts.append(f"\n---\n\n## Page {page['page_number']}\n")

        for region in page["regions"]:
            rtype = region["type"]

            if rtype == "title":
                level = region.get("heading_level", 1)
                prefix = "#" * min(level, 6)
                parts.append(f"\n{prefix} {region['content']}\n")
            elif rtype == "table":
                md = region.get("markdown", "")
                if md:
                    parts.append(f"\n{md}\n")
            elif rtype == "list":
                items = _split_list_items(region.get("content", ""))
                for item in items:
                    parts.append(f"- {item}")
            elif rtype == "text":
                parts.append(f"\n{region['content']}\n")
            elif rtype == "figure":
                caption = region.get("caption")
                if caption:
                    parts.append(f"\n*[Figure: {caption}]*\n")
                else:
                    parts.append("\n*[Figure]*\n")

    result = "\n".join(parts).strip()
    return result + "\n" if result else ""


def format_structured_output(
    pages: List[Dict[str, Any]],
    output_format: str,
) -> bytes:
    """Format structured results as JSON, Markdown, HTML, or plain text."""

    # Step 1: Cross-page header/footer filtering (must run before per-page ops)
    _filter_headers_footers(pages)

    # Step 2: Per-page layout intelligence
    for page in pages:
        regions = page.get("regions", [])
        _detect_heading_levels(regions)
        regions = _reorder_by_columns(regions)
        _extract_figure_captions(regions)          # captions before merge
        regions = _merge_adjacent_paragraphs(regions)
        page["regions"] = regions

    if output_format == "json":
        total_regions = sum(len(p["regions"]) for p in pages)
        tables_found = sum(
            1 for p in pages for r in p["regions"] if r["type"] == "table"
        )
        text_blocks = sum(
            1 for p in pages for r in p["regions"] if r["type"] in ("text", "title")
        )

        output = {
            "pages": pages,
            "summary": {
                "total_pages": len(pages),
                "total_regions": total_regions,
                "tables_found": tables_found,
                "text_blocks": text_blocks,
            },
        }
        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")

    elif output_format == "md":
        return _format_markdown(pages).encode("utf-8")

    elif output_format == "html":
        return _format_html(pages).encode("utf-8")

    else:
        # Fallback: plain text
        text_parts = []
        for page in pages:
            for region in page["regions"]:
                if region["type"] == "table":
                    text_parts.append(region.get("markdown", ""))
                elif "content" in region:
                    text_parts.append(region["content"])
        return "\n".join(text_parts).encode("utf-8")
