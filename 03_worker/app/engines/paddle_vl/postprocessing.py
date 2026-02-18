# Output extraction and formatting for PaddleOCR-VL structured results

import json
import re
from typing import List, Dict, Any


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
            "cell_bbox": [...]
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
            html = table_res.get("html", "")
            regions.append({
                "type": "table",
                "bbox": bbox,
                "html": html,
                "markdown": html_table_to_markdown(html),
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


def html_table_to_markdown(html: str) -> str:
    """Convert HTML table to Markdown table format."""
    rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
    if not rows:
        return ""

    md_rows = []
    for i, row in enumerate(rows):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        cells = [c.strip() for c in cells]
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
