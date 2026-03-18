# PaddleOCR-VL structured extraction - Entry point

import logging
from typing import Dict, Any, List

import os
import numpy as np

from app.engines.base import BaseHandler
from app.utils.gpu_memory import (
    set_gpu_memory_fraction, check_gpu_available,
    log_gpu_memory, cleanup_gpu_memory,
)
from .preprocessing import load_images, prepare_image
from .postprocessing import (
    extract_regions,
    extract_regions_from_raw_ocr,
    extract_regions_v3,
    extract_regions_v3_ocr_fallback,
    assess_result_quality,
    format_structured_output,
)
from .debug import DebugContext

logger = logging.getLogger(__name__)

ENGINE_NAME = "paddleocr-vl"

# Detect PaddleOCR version without importing (avoids paddlex double-init bug)
try:
    from importlib.metadata import version as _get_version
    _PADDLE_OCR_VERSION = _get_version("paddleocr")
    _IS_V3 = int(_PADDLE_OCR_VERSION.split(".")[0]) >= 3
except Exception:
    _PADDLE_OCR_VERSION = "unknown"
    _IS_V3 = False


class StructuredExtractHandler(BaseHandler):
    """OCR handler using PaddleOCR PP-Structure for structured extraction.

    Supports PaddleOCR v3.x (PPStructureV3) with fallback to v2.x (PPStructure).
    """

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        logger.info(f"Initializing PaddleOCR-VL v{_PADDLE_OCR_VERSION} (use_gpu={use_gpu}, lang={lang})")

        # GPU memory safety: set fraction limit before model load
        # PPStructureV3 loads multiple models (layout + table + OCR) — needs more memory
        if use_gpu:
            set_gpu_memory_fraction()
            log_gpu_memory("before PPStructure init")
            if not check_gpu_available(min_free_mb=800):
                logger.warning("Low GPU memory for PPStructure — attempting init anyway")

        if _IS_V3:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PPStructureV3
            self.engine = PPStructureV3(lang=lang)
            self._is_v3 = True
        else:
            from paddleocr import PPStructure
            self.engine = PPStructure(
                use_gpu=use_gpu, lang=lang,
                layout=True, table=True, ocr=True, show_log=False,
            )
            self._is_v3 = False

        if use_gpu:
            log_gpu_memory("after PPStructure init")

        # Lazy-init fallback OCR engine
        self._ocr_engine = None

    def _get_ocr_engine(self):
        """Get pure OCR engine for fallback."""
        if self._ocr_engine is None:
            from paddleocr import PaddleOCR
            if _IS_V3:
                self._ocr_engine = PaddleOCR(lang=self.lang)
            else:
                self._ocr_engine = PaddleOCR(
                    use_gpu=self.use_gpu, lang=self.lang,
                    use_angle_cls=True, show_log=False,
                )
        return self._ocr_engine

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": _PADDLE_OCR_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
            "capabilities": ["layout_analysis", "table_recognition", "text_ocr"],
        }

    def _run_engine(self, image):
        """Run PPStructure/PPStructureV3."""
        if self._is_v3:
            results = list(self.engine.predict(image))
            return results
        else:
            try:
                return self.engine(image)
            except (IndexError, ValueError) as e:
                logger.warning(f"PPStructure error: {e}")
                return []

    def _run_pure_ocr(self, image) -> list:
        """Run pure PaddleOCR (no layout)."""
        ocr = self._get_ocr_engine()
        if _IS_V3:
            return list(ocr.predict(image))
        return ocr.ocr(image, cls=True)

    @staticmethod
    def _ocr_result_is_empty(raw_ocr: list) -> bool:
        """Check if OCR returned empty/None result."""
        if not raw_ocr:
            return True
        return all(page is None for page in raw_ocr)

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        dbg = DebugContext()

        # Preprocessing
        images = load_images(file_content)
        logger.info(f"Processing {len(images)} page(s) with PPStructure")

        # Tier 1: PPStructure/PPStructureV3
        all_pages = []
        for page_idx, image in enumerate(images):
            dbg.save_input_image(image, page_idx)
            prepared = prepare_image(image)

            logger.debug(f"Structured OCR page {page_idx + 1}/{len(images)}")
            raw_result = self._run_engine(prepared)

            if self._is_v3:
                page_result = self._extract_v3_structured(raw_result, page_idx)
            else:
                dbg.save_raw_engine_output(raw_result, page_idx, "tier1")
                page_result = extract_regions(raw_result, page_idx)

            all_pages.append(page_result)

            # Free GPU memory after each page to prevent accumulation
            cleanup_gpu_memory()

        if self.use_gpu:
            log_gpu_memory("after structured extraction")

        quality_ok = assess_result_quality(all_pages)

        # Tier 2: Pure OCR fallback if structured failed
        if not quality_ok:
            logger.warning("Structured extraction poor quality, falling back to pure OCR")
            all_pages = []
            for page_idx, image in enumerate(images):
                prepared = prepare_image(image)
                raw_ocr = self._run_pure_ocr(prepared)

                if self._is_v3:
                    page_result = self._extract_v3_ocr_fallback(raw_ocr, page_idx)
                else:
                    if self._ocr_result_is_empty(raw_ocr):
                        page_result = {"page_number": page_idx + 1, "regions": []}
                    else:
                        page_result = extract_regions_from_raw_ocr(raw_ocr, page_idx)

                all_pages.append(page_result)

        dbg.save_pipeline_summary()
        # Final cleanup after all processing
        cleanup_gpu_memory()
        return format_structured_output(all_pages, output_format)

    def _extract_v3_structured(self, results: list, page_idx: int) -> Dict:
        """Extract structured regions from PPStructureV3 output.

        Delegates to ``extract_regions_v3`` in postprocessing which handles
        multiple V3 output formats (PaddleX parsing_result, direct blocks,
        legacy flat rec_texts).
        """
        return extract_regions_v3(results, page_idx)

    def _extract_v3_ocr_fallback(self, results: list, page_idx: int) -> Dict:
        """Extract text from pure OCR (v3) as fallback.

        Delegates to ``extract_regions_v3_ocr_fallback`` in postprocessing.
        """
        return extract_regions_v3_ocr_fallback(results, page_idx)
