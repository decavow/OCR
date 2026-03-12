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

    return {
        "page_number": page_idx + 1,
        "regions": regions,
    }


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


def html_table_to_markdown(html: str) -> str:
    """Convert HTML table to Markdown table format."""
    # Strip wrapper tags if present
    cleaned = _strip_html_wrapper(html)

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', cleaned, re.DOTALL)
    if not rows:
        return ""

    md_rows = []
    for i, row in enumerate(rows):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        cells = [c.strip() for c in cells]
        if not cells:
            continue
        md_rows.append("| " + " | ".join(cells) + " |")

        # Add separator after header row
        if i == 0:
            md_rows.append("|" + "|".join(["---"] * len(cells)) + "|")

    return "\n".join(md_rows)


def format_structured_output(
    pages: List[Dict[str, Any]],
    output_format: str,
) -> bytes:
    """Format structured results as JSON, Markdown, or plain text."""

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
        md_parts = []
        for page in pages:
            if len(pages) > 1:
                md_parts.append(f"---\n**Page {page['page_number']}**\n")

            for region in page["regions"]:
                if region["type"] == "title":
                    md_parts.append(f"# {region['content']}\n")
                elif region["type"] == "table":
                    md_parts.append(region.get("markdown", "") + "\n")
                elif region["type"] == "list":
                    md_parts.append(f"- {region['content']}\n")
                elif region["type"] == "text":
                    md_parts.append(region["content"] + "\n")
                elif region["type"] == "figure":
                    md_parts.append("[Figure]\n")

        return "\n".join(md_parts).encode("utf-8")

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
