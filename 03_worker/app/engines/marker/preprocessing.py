# Preprocessing: file bytes → temp file with correct extension (required by Marker)

import io
import os
import tempfile

from PIL import Image


def load_document(file_content: bytes) -> tuple[str, dict]:
    """
    Detect format from raw bytes and save to a temp file
    with the correct extension (Marker uses the extension to choose provider).

    Returns:
        (temp_file_path, file_info_dict)
    """
    info = {"size_bytes": len(file_content)}

    # PDF detection via magic bytes
    if file_content[:5] == b"%PDF-":
        info["format"] = "pdf"
        suffix = ".pdf"
    else:
        # Try as image via PIL
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                fmt = (img.format or "png").lower()
                info["format"] = fmt
                info["dimensions"] = {"width": img.width, "height": img.height}
                suffix_map = {"jpeg": ".jpg", "png": ".png", "tiff": ".tiff", "bmp": ".bmp"}
                suffix = suffix_map.get(fmt, f".{fmt}")
        except Exception:
            info["format"] = "unknown"
            suffix = ".bin"

    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(file_content)

    info["temp_path"] = temp_path
    return temp_path, info
