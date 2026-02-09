# Output extraction and formatting for PaddleOCR

import json
from typing import List, Dict, Any


def extract_results(ocr_result) -> tuple[str, List[str], List[Dict[str, Any]]]:
    """Extract text lines and box data from PaddleOCR result.

    Returns:
        (full_text, text_lines, boxes_data) tuple
    """
    text_lines = []
    boxes_data = []

    if ocr_result and ocr_result[0]:
        for line in ocr_result[0]:
            box = line[0]       # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text_info = line[1]  # (text, confidence)

            text = text_info[0]
            confidence = text_info[1]

            text_lines.append(text)
            boxes_data.append({
                "text": text,
                "confidence": round(confidence, 4),
                "box": box,
            })

    full_text = "\n".join(text_lines)
    return full_text, text_lines, boxes_data


def format_output(
    full_text: str,
    text_lines: List[str],
    boxes_data: List[Dict[str, Any]],
    output_format: str,
) -> bytes:
    """Format OCR result as text or JSON bytes."""
    if output_format == "json":
        output = {
            "text": full_text,
            "lines": len(text_lines),
            "details": boxes_data,
        }
        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        return full_text.encode("utf-8")
