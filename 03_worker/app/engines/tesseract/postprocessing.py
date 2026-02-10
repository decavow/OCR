# Output extraction and formatting for Tesseract

import json
from typing import List, Dict, Any, Tuple

import pytesseract
from PIL import Image


def extract_detailed(image: Image.Image, lang: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Extract text with bounding boxes from a single image.

    Returns:
        (text_lines, boxes_data) tuple
    """
    data = pytesseract.image_to_data(
        image,
        lang=lang,
        output_type=pytesseract.Output.DICT,
    )

    text_lines = []
    boxes_data = []
    current_line = {"text": [], "boxes": [], "confidences": []}
    last_line_num = -1

    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue

        line_num = data["line_num"][i]
        conf = data["conf"][i]

        # Skip low confidence (Tesseract uses -1 for invalid)
        if conf < 0:
            continue

        # New line detected
        if line_num != last_line_num and current_line["text"]:
            _flush_line(current_line, text_lines, boxes_data)
            current_line = {"text": [], "boxes": [], "confidences": []}

        current_line["text"].append(text)
        current_line["confidences"].append(conf)
        current_line["boxes"].append([
            [data["left"][i], data["top"][i]],
            [data["left"][i] + data["width"][i], data["top"][i]],
            [data["left"][i] + data["width"][i], data["top"][i] + data["height"][i]],
            [data["left"][i], data["top"][i] + data["height"][i]],
        ])
        last_line_num = line_num

    # Don't forget last line
    if current_line["text"]:
        _flush_line(current_line, text_lines, boxes_data)

    return text_lines, boxes_data


def extract_plain(image: Image.Image, lang: str) -> List[str]:
    """Extract plain text lines from a single image."""
    text = pytesseract.image_to_string(image, lang=lang)
    return [line for line in text.strip().split("\n") if line.strip()]


def format_output(
    text_lines: List[str],
    boxes_data: List[Dict[str, Any]],
    page_count: int,
    output_format: str,
) -> bytes:
    """Format OCR result as text or JSON bytes."""
    full_text = "\n".join(text_lines)

    if output_format == "json":
        output = {
            "text": full_text,
            "lines": len(text_lines),
            "pages": page_count,
            "details": boxes_data,
        }
        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        return full_text.encode("utf-8")


def _flush_line(
    current_line: dict,
    text_lines: List[str],
    boxes_data: List[Dict[str, Any]],
) -> None:
    """Flush accumulated words into a completed line."""
    line_text = " ".join(current_line["text"])
    avg_conf = sum(current_line["confidences"]) / len(current_line["confidences"])
    text_lines.append(line_text)
    boxes_data.append({
        "text": line_text,
        "confidence": round(avg_conf / 100, 4),  # Tesseract uses 0-100
        "box": current_line["boxes"],
    })
