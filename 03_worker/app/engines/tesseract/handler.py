# Tesseract OCR text extraction - Entry point

import logging
import os
import shutil
from typing import Dict, Any

import pytesseract

from app.engines.base import BaseHandler
from .preprocessing import load_images, prepare_image
from .postprocessing import extract_detailed, extract_plain, format_output

logger = logging.getLogger(__name__)

# Auto-detect Tesseract path on Windows
_WINDOWS_DEFAULT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _configure_tesseract_path():
    """Set pytesseract.tesseract_cmd if not already in PATH."""
    # Env var override
    custom_cmd = os.environ.get("TESSERACT_CMD")
    if custom_cmd:
        pytesseract.pytesseract.tesseract_cmd = custom_cmd
        return

    # Already in PATH
    if shutil.which("tesseract"):
        return

    # Try Windows default install paths
    for path in _WINDOWS_DEFAULT_PATHS:
        if os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Tesseract found at: {path}")
            return


_configure_tesseract_path()

# Language mapping: our codes -> Tesseract codes
LANG_MAP = {
    "en": "eng",
    "vi": "vie",
    "vie": "vie",
    "ch": "chi_sim",
    "chinese": "chi_sim",
    "japan": "jpn",
    "jpn": "jpn",
    "korean": "kor",
    "kor": "kor",
    "fr": "fra",
    "de": "deu",
}


class TextRawTesseractHandler(BaseHandler):
    """OCR handler using Tesseract for text extraction (CPU-based)."""

    def __init__(self, lang: str = "en", **kwargs):
        self.lang = LANG_MAP.get(lang, lang)
        logger.info(f"Initializing Tesseract OCR (lang={self.lang})")

        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            raise RuntimeError("Tesseract is not installed or not in PATH") from e

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "tesseract",
            "version": str(pytesseract.get_tesseract_version()),
            "lang": self.lang,
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Preprocessing
        images = load_images(file_content)

        # Inference + extraction (per page)
        all_text_lines = []
        all_boxes_data = []

        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            logger.debug(f"Processing page {page_idx + 1}/{len(images)}, size: {image.size}")

            if output_format == "json":
                text_lines, boxes_data = extract_detailed(image, self.lang)
                all_boxes_data.extend(boxes_data)
            else:
                text_lines = extract_plain(image, self.lang)

            all_text_lines.extend(text_lines)

        # Postprocessing
        return format_output(all_text_lines, all_boxes_data, len(images), output_format)
