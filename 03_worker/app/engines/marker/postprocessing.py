# Postprocessing: confidence scoring, markdown normalization, output formatting.

import json
import re


# ---------------------------------------------------------------------------
# Confidence scoring (4 heuristic signals)
# ---------------------------------------------------------------------------

_VN_LATIN_PATTERN = re.compile(
    r'[a-zA-Z0-9\s'
    r'àáảãạăắằẳẵặâấầẩẫậ'
    r'èéẻẽẹêếềểễệ'
    r'ìíỉĩị'
    r'òóỏõọôốồổỗộơớờởỡợ'
    r'ùúủũụưứừửữự'
    r'ỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬ'
    r'ÈÉẺẼẸÊẾỀỂỄỆ'
    r'ÌÍỈĨỊ'
    r'ÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢ'
    r'ÙÚỦŨỤƯỨỪỬỮỰ'
    r'ỲÝỶỸỴĐ'
    r'\.,;:!?\-\(\)\[\]{}\|/\\@#$%^&*+=<>\'\"~`_\n\r\t]'
)


def calculate_confidence(raw_markdown: str) -> tuple[float, dict]:
    """Heuristic confidence scoring. Returns (score, details)."""
    if not raw_markdown or not raw_markdown.strip():
        return 0.0, {"note": "empty input"}

    score = 1.0
    details = {}
    text = raw_markdown
    total_chars = len(text)

    # Signal 1: Unknown char ratio
    known_chars = len(_VN_LATIN_PATTERN.findall(text))
    unknown_ratio = 1.0 - (known_chars / total_chars) if total_chars > 0 else 0
    if unknown_ratio > 0.15:
        score -= 0.30
    elif unknown_ratio > 0.05:
        score -= 0.15
    details["unknown_char_ratio"] = round(unknown_ratio, 4)

    # Signal 2: Average word length
    words = text.split()
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
    if avg_word_len < 2.0:
        score -= 0.15
    elif avg_word_len > 25.0:
        score -= 0.20
    details["avg_word_len"] = round(avg_word_len, 2)

    # Signal 3: Whitespace ratio
    ws_count = sum(1 for c in text if c in (' ', '\t'))
    ws_ratio = ws_count / total_chars if total_chars > 0 else 0
    if ws_ratio > 0.60 or ws_ratio < 0.05:
        score -= 0.10
    details["whitespace_ratio"] = round(ws_ratio, 4)

    # Signal 4: Empty line ratio
    lines = text.split("\n")
    empty_lines = sum(1 for line in lines if not line.strip())
    empty_ratio = empty_lines / len(lines) if lines else 0
    if empty_ratio > 0.50:
        score -= 0.15
    details["empty_line_ratio"] = round(empty_ratio, 4)

    score = max(0.0, min(1.0, score))
    return score, details


# ---------------------------------------------------------------------------
# Markdown normalization
# ---------------------------------------------------------------------------

def normalize_markdown(raw_markdown: str) -> tuple[str, dict]:
    """Remove page numbers and trim excessive whitespace."""
    text = raw_markdown
    changes = {"page_numbers_removed": 0, "whitespace_trimmed": False}

    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^[\-—]\s*\d+\s*[\-—]$', stripped):
            changes["page_numbers_removed"] += 1
            continue
        if re.match(r'^[Pp]age\s+\d+$', stripped):
            changes["page_numbers_removed"] += 1
            continue
        if re.match(r'^\d{1,4}$', stripped) and len(stripped) <= 4:
            changes["page_numbers_removed"] += 1
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    original_len = len(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip() + "\n"
    if len(text) != original_len:
        changes["whitespace_trimmed"] = True

    return text, changes


# ---------------------------------------------------------------------------
# Markdown → JSON block parser
# ---------------------------------------------------------------------------

def _markdown_to_json(markdown: str, confidence: float) -> dict:
    blocks = []
    current_block = None
    in_code = False
    code_lang = ""
    code_lines = []

    def flush():
        nonlocal current_block
        if current_block and current_block.get("content", "").strip():
            blocks.append(current_block)
        current_block = None

    for line in markdown.split("\n"):
        if line.strip().startswith("```"):
            if in_code:
                blocks.append({"type": "code", "content": "\n".join(code_lines), "language": code_lang})
                code_lines, code_lang, in_code = [], "", False
            else:
                flush()
                in_code = True
                code_lang = line.strip()[3:].strip()
            continue

        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()

        heading_m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_m:
            flush()
            blocks.append({"type": "heading", "content": heading_m.group(2).strip(), "level": len(heading_m.group(1))})
            continue

        if stripped.startswith("|"):
            if re.match(r'^\|[\s\-:]+\|', stripped):
                if current_block and current_block["type"] == "table":
                    current_block["content"] += "\n" + line
                continue
            if current_block is None or current_block["type"] != "table":
                flush()
                current_block = {"type": "table", "content": line}
            else:
                current_block["content"] += "\n" + line
            continue

        if re.match(r'^[\-\*\•]\s+', stripped) or re.match(r'^\d+[.)]\s+', stripped):
            if current_block is None or current_block["type"] != "list":
                flush()
                current_block = {"type": "list", "content": stripped}
            else:
                current_block["content"] += "\n" + stripped
            continue

        if not stripped:
            flush()
            continue

        if current_block is None or current_block["type"] != "paragraph":
            flush()
            current_block = {"type": "paragraph", "content": stripped}
        else:
            current_block["content"] += " " + stripped

    if in_code and code_lines:
        blocks.append({"type": "code", "content": "\n".join(code_lines), "language": code_lang})
    else:
        flush()

    return {"confidence": round(confidence, 4), "blocks_count": len(blocks), "blocks": blocks}


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  pre {{ background: #f5f5f5; padding: 1rem; overflow-x: auto; border-radius: 4px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def format_output(normalized_md: str, confidence: float, output_format: str) -> bytes:
    """Format normalized markdown into requested output. Returns UTF-8 bytes."""
    if output_format == "md":
        return normalized_md.encode("utf-8")

    if output_format == "html":
        try:
            import markdown as md_lib
            html_body = md_lib.markdown(normalized_md, extensions=["tables", "fenced_code"])
        except ImportError:
            html_body = f"<pre>{normalized_md}</pre>"
        return _HTML_TEMPLATE.format(body=html_body).encode("utf-8")

    if output_format == "json":
        result = _markdown_to_json(normalized_md, confidence)
        return json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")

    raise ValueError(f"Unsupported output format: {output_format}")
