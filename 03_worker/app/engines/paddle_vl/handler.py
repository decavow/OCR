# PaddleOCR-VL structured extraction - Entry point

import logging
from typing import Dict, Any, List

import numpy as np
from paddleocr import PaddleOCR, PPStructure

from app.engines.base import BaseHandler
from .preprocessing import load_images, prepare_image
from .postprocessing import (
    extract_regions,
    extract_regions_from_raw_ocr,
    assess_result_quality,
    format_structured_output,
)

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

        # Lazy-init fallback engines
        self._fallback_engine = None
        self._ocr_engine_gpu = None
        self._ocr_engine_cpu = None

    def _get_fallback_engine(self) -> PPStructure:
        if self._fallback_engine is None:
            logger.info("Initializing fallback PPStructure engine (table=False)")
            self._fallback_engine = PPStructure(
                use_gpu=self.use_gpu,
                lang=self.lang,
                layout=True,
                table=False,
                ocr=True,
                show_log=False,
            )
        return self._fallback_engine

    def _get_ocr_engine(self, use_gpu: bool) -> PaddleOCR:
        """Get pure OCR engine (no layout analysis)."""
        if use_gpu:
            if self._ocr_engine_gpu is None:
                logger.info("Initializing pure PaddleOCR engine (GPU)")
                self._ocr_engine_gpu = PaddleOCR(
                    use_gpu=True,
                    lang=self.lang,
                    use_angle_cls=True,
                    show_log=False,
                )
            return self._ocr_engine_gpu
        else:
            if self._ocr_engine_cpu is None:
                logger.info("Initializing pure PaddleOCR engine (CPU fallback)")
                self._ocr_engine_cpu = PaddleOCR(
                    use_gpu=False,
                    lang=self.lang,
                    use_angle_cls=True,
                    show_log=False,
                )
            return self._ocr_engine_cpu

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
            "capabilities": ["layout_analysis", "table_recognition", "text_ocr"],
        }

    def _run_engine(self, image):
        """Run PPStructure with fallback to table=False if table matcher crashes."""
        try:
            return self.engine(image)
        except (IndexError, ValueError) as e:
            logger.warning(
                f"PPStructure table matcher error: {e}, "
                "retrying without table recognition"
            )
            fallback = self._get_fallback_engine()
            return fallback(image)

    def _run_fallback(self, image):
        """Run PPStructure without table recognition."""
        fallback = self._get_fallback_engine()
        return fallback(image)

    def _run_pure_ocr(self, image, use_gpu: bool = True) -> list:
        """Run pure PaddleOCR (no layout)."""
        ocr = self._get_ocr_engine(use_gpu)
        return ocr.ocr(image, cls=True)

    @staticmethod
    def _ocr_result_is_empty(raw_ocr: list) -> bool:
        """Check if PaddleOCR returned empty/None result."""
        if not raw_ocr:
            return True
        # PaddleOCR returns [None] when no text is detected
        return all(page is None for page in raw_ocr)

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Preprocessing
        images = load_images(file_content)

        # Inference per page
        all_pages = self._try_structured(images)

        # Fallback chain: PPStructure(table=False) → pure OCR GPU → pure OCR CPU
        if not assess_result_quality(all_pages):
            logger.warning(
                "Primary engine produced poor quality results. "
                "Retrying with fallback engine (table=False)..."
            )
            all_pages = self._try_structured_no_table(images)

        if not assess_result_quality(all_pages):
            logger.warning(
                "Fallback engine also produced poor quality. "
                "Using pure OCR (GPU)..."
            )
            all_pages = self._try_pure_ocr(images, use_gpu=True)

        if not assess_result_quality(all_pages):
            logger.warning(
                "GPU OCR returned no results. "
                "Retrying with CPU inference..."
            )
            all_pages = self._try_pure_ocr(images, use_gpu=False)

        # Postprocessing
        return format_structured_output(all_pages, output_format)

    def _try_structured(self, images: List[np.ndarray]) -> List[Dict]:
        all_pages = []
        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            logger.debug(f"Processing page {page_idx + 1}/{len(images)}")
            raw_regions = self._run_engine(image)
            page_result = extract_regions(raw_regions, page_idx)
            all_pages.append(page_result)
        return all_pages

    def _try_structured_no_table(self, images: List[np.ndarray]) -> List[Dict]:
        all_pages = []
        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            raw_regions = self._run_fallback(image)
            page_result = extract_regions(raw_regions, page_idx)
            all_pages.append(page_result)
        return all_pages

    def _try_pure_ocr(self, images: List[np.ndarray], use_gpu: bool = True) -> List[Dict]:
        all_pages = []
        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            mode = "GPU" if use_gpu else "CPU"
            logger.debug(f"Pure OCR ({mode}) page {page_idx + 1}/{len(images)}")
            raw_ocr = self._run_pure_ocr(image, use_gpu=use_gpu)

            if self._ocr_result_is_empty(raw_ocr):
                logger.warning(f"Pure OCR ({mode}) returned no text for page {page_idx + 1}")
                all_pages.append({"page_number": page_idx + 1, "regions": []})
            else:
                page_result = extract_regions_from_raw_ocr(raw_ocr, page_idx)
                all_pages.append(page_result)
        return all_pages
