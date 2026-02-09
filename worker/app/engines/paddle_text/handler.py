# PaddleOCR text extraction - Entry point

import logging
from typing import Dict, Any

from paddleocr import PaddleOCR

from app.engines.base import BaseHandler
from .preprocessing import load_image
from .postprocessing import extract_results, format_output

logger = logging.getLogger(__name__)

ENGINE_NAME = "paddleocr"
ENGINE_VERSION = "2.7.3"


class TextRawHandler(BaseHandler):
    """OCR handler using PaddleOCR for text extraction."""

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        logger.info(f"Initializing PaddleOCR (use_gpu={use_gpu}, lang={lang})")
        self.ocr = PaddleOCR(
            use_gpu=use_gpu,
            lang=lang,
            show_log=False,
        )

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Preprocessing
        img_array, size = load_image(file_content)

        # Inference
        logger.debug(f"Running OCR on image {size}")
        result = self.ocr.ocr(img_array, cls=True)

        # Postprocessing
        full_text, text_lines, boxes_data = extract_results(result)
        return format_output(full_text, text_lines, boxes_data, output_format)
