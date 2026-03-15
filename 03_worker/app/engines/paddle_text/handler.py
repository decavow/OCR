# PaddleOCR text extraction - Entry point
# Supports PaddleOCR v3.x (predict API) with fallback to v2.x (ocr API)

import logging
import os
from typing import Dict, Any

from paddleocr import PaddleOCR

from app.engines.base import BaseHandler
from .preprocessing import load_image, load_images
from .postprocessing import extract_results, format_output

logger = logging.getLogger(__name__)

ENGINE_NAME = "paddleocr"

# Detect PaddleOCR version without importing (avoids paddlex double-init bug)
try:
    from importlib.metadata import version as _get_version
    _PADDLE_OCR_VERSION = _get_version("paddleocr")
    _IS_V3 = int(_PADDLE_OCR_VERSION.split(".")[0]) >= 3
except Exception:
    _PADDLE_OCR_VERSION = "unknown"
    _IS_V3 = False


class TextRawHandler(BaseHandler):
    """OCR handler using PaddleOCR for text extraction."""

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        logger.info(f"Initializing PaddleOCR v{_PADDLE_OCR_VERSION} (use_gpu={use_gpu}, lang={lang})")

        if _IS_V3:
            # PaddleOCR v3.x: no use_gpu/show_log params
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            self.ocr = PaddleOCR(lang=lang)
        else:
            # PaddleOCR v2.x: legacy API
            self.ocr = PaddleOCR(use_gpu=use_gpu, lang=lang, show_log=False)

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": _PADDLE_OCR_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Load all pages (PDF may have multiple)
        pages = load_images(file_content)
        logger.info(f"Processing {len(pages)} page(s)")

        all_text_lines = []
        all_boxes_data = []

        for page_idx, (img_array, size) in enumerate(pages):
            logger.debug(f"OCR page {page_idx + 1}/{len(pages)}, size={size}")

            if _IS_V3:
                results = self.ocr.predict(img_array)
                _, text_lines, boxes_data = self._extract_v3(results)
            else:
                result = self.ocr.ocr(img_array, cls=True)
                _, text_lines, boxes_data = extract_results(result)

            all_text_lines.extend(text_lines)
            all_boxes_data.extend(boxes_data)

        full_text = "\n".join(all_text_lines)
        return format_output(full_text, all_text_lines, all_boxes_data, output_format)

    @staticmethod
    def _extract_v3(results) -> tuple:
        """Extract text from PaddleOCR v3.x predict() output."""
        text_lines = []
        boxes_data = []

        for r in results:
            rec_texts = r.get("rec_texts", [])
            rec_scores = r.get("rec_scores", [])
            rec_polys = r.get("rec_polys", [])

            for i, text in enumerate(rec_texts):
                score = rec_scores[i] if i < len(rec_scores) else 0.0
                poly = rec_polys[i] if i < len(rec_polys) else None
                text_lines.append(text)

                # poly can be numpy array — use len() instead of bool()
                box = []
                if poly is not None and len(poly) > 0:
                    box = [[int(p[0]), int(p[1])] for p in poly]

                boxes_data.append({
                    "text": text,
                    "confidence": round(float(score), 4),
                    "box": box,
                })

        full_text = "\n".join(text_lines)
        return full_text, text_lines, boxes_data
