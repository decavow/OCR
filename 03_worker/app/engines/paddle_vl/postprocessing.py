# Output extraction and formatting for PaddleOCR-VL structured results

import json
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


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

            content = " ".join(text_parts)
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


def html_table_to_markdown(html: str) -> str:
    """Convert HTML table to Markdown table format.

    Handles inner HTML tags in cells, pads rows with uneven column counts.
    """
    cleaned = _strip_html_wrapper(html)

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', cleaned, re.DOTALL)
    if not rows:
        return ""

    # First pass: determine max column count
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

    # Second pass: build markdown with consistent column count
    md_rows = []
    for i, cells in enumerate(parsed_rows):
        while len(cells) < max_cols:
            cells.append("")
        md_rows.append("| " + " | ".join(cells) + " |")

        if i == 0:
            md_rows.append("|" + "|".join(["---"] * max_cols) + "|")

    return "\n".join(md_rows)


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
                content = _escape_html(region.get("content", ""))
                parts.append(f"<h1>{content}</h1>")

            elif rtype == "table":
                html = region.get("html", "")
                if html:
                    parts.append(html)
                else:
                    md = region.get("markdown", "")
                    parts.append(f"<pre>{_escape_html(md)}</pre>")

            elif rtype == "list":
                content = region.get("content", "")
                parts.append("<ul>")
                parts.append(f"  <li>{_escape_html(content)}</li>")
                parts.append("</ul>")

            elif rtype == "text":
                content = _escape_html(region.get("content", ""))
                parts.append(f"<p>{content}</p>")

            elif rtype == "figure":
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
                parts.append(f"\n# {region['content']}\n")
            elif rtype == "table":
                md = region.get("markdown", "")
                if md:
                    parts.append(f"\n{md}\n")
            elif rtype == "list":
                parts.append(f"- {region['content']}")
            elif rtype == "text":
                parts.append(f"\n{region['content']}\n")
            elif rtype == "figure":
                parts.append("\n*[Figure]*\n")

    result = "\n".join(parts).strip()
    return result + "\n" if result else ""


def format_structured_output(
    pages: List[Dict[str, Any]],
    output_format: str,
) -> bytes:
    """Format structured results as JSON, Markdown, HTML, or plain text."""

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
