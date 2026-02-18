# PaddleOCR-VL structured extraction - Entry point

import logging
from typing import Dict, Any

from paddleocr import PPStructure

from app.engines.base import BaseHandler
from .preprocessing import load_images, prepare_image
from .postprocessing import extract_regions, format_structured_output

logger = logging.getLogger(__name__)

ENGINE_NAME = "paddleocr-vl"
ENGINE_VERSION = "2.7.3"


class StructuredExtractHandler(BaseHandler):
    """OCR handler using PaddleOCR PP-Structure for structured extraction."""

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        logger.info(f"Initializing PaddleOCR-VL (use_gpu={use_gpu}, lang={lang})")

        self.engine = PPStructure(
            use_gpu=use_gpu,
            lang=lang,
            layout=True,
            table=True,
            ocr=True,
            show_log=False,
        )

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
            "capabilities": ["layout_analysis", "table_recognition", "text_ocr"],
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Preprocessing
        images = load_images(file_content)

        # Inference per page
        all_pages = []
        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            logger.debug(f"Processing page {page_idx + 1}/{len(images)}")

            # PPStructure returns list of region dicts
            raw_regions = self.engine(image)

            page_result = extract_regions(raw_regions, page_idx)
            all_pages.append(page_result)

        # Postprocessing
        return format_structured_output(all_pages, output_format)
