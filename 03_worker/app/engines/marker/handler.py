# Marker (Surya OCR) — Formatted text extraction with structure preservation
# Engine: marker | Method: ocr_marker | GPU: Yes (VRAM peak ~5 GB, batch=8)

import logging
import os
import time
from typing import Dict, Any

from app.engines.base import BaseHandler
from app.utils.errors import PermanentError
from app.utils.gpu_memory import (
    set_torch_gpu_memory_fraction,
    check_torch_gpu_available,
    log_torch_gpu_memory,
    cleanup_torch_gpu_memory,
)
from .preprocessing import load_document
from .postprocessing import calculate_confidence, normalize_markdown, format_output

logger = logging.getLogger(__name__)

ENGINE_NAME = "marker"

# Batch size env vars MUST be set BEFORE importing marker/surya.
# These are read at module-load time by surya.
_DEFAULT_BATCH_SIZE = os.getenv("MARKER_BATCH_SIZE", "8")
os.environ.setdefault("DETECTOR_BATCH_SIZE", _DEFAULT_BATCH_SIZE)
os.environ.setdefault("RECOGNITION_BATCH_SIZE", _DEFAULT_BATCH_SIZE)
os.environ.setdefault("LAYOUT_BATCH_SIZE", _DEFAULT_BATCH_SIZE)
os.environ.setdefault("INFERENCE_RAM", os.getenv("INFERENCE_RAM", "8"))


def _parse_languages(lang: str) -> list[str]:
    """
    "en"    → ["en"]
    "vi"    → ["vi", "en"]   (Vietnamese always includes English)
    "en,vi" → ["en", "vi"]
    """
    langs = [l.strip() for l in lang.split(",") if l.strip()]
    if langs == ["vi"] or langs == ["vie"]:
        langs = ["vi", "en"]
    return langs


class FormattedTextHandler(BaseHandler):
    """OCR handler using Marker (Surya OCR) for formatted text extraction.

    Preserves document structure: headings, tables, lists, reading order.
    Supports PDF (native) and images (PNG, JPG, TIFF).
    Output formats: md, html, json.
    """

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        self.languages = _parse_languages(lang)
        self.use_llm = (
            os.getenv("MARKER_USE_LLM", "false").lower() == "true"
            and bool(os.getenv("GOOGLE_API_KEY"))
        )
        self.model_dict = None
        self._marker_version = "unknown"

        # GPU setup (torch-based, not paddle)
        if use_gpu:
            set_torch_gpu_memory_fraction()
            log_torch_gpu_memory("before Marker init")
            if not check_torch_gpu_available(min_free_mb=2000):
                logger.warning("Low GPU memory — attempting init anyway")

        self._load_models()

        if use_gpu:
            log_torch_gpu_memory("after Marker models loaded")

    def _load_models(self):
        """Load Surya models (one-time, ~15-30s, kept resident)."""
        logger.info(
            f"Loading Marker models "
            f"(languages={self.languages}, use_llm={self.use_llm})"
        )
        t = time.time()

        try:
            from marker.models import create_model_dict
            self.model_dict = create_model_dict()
        except ImportError:
            # Newer marker versions load models inside the converter
            self.model_dict = {}
            logger.info("create_model_dict not available — converter will load models")

        try:
            import marker
            self._marker_version = getattr(marker, "__version__", "unknown")
        except Exception:
            pass

        logger.info(
            f"Marker models loaded in {time.time() - t:.1f}s "
            f"(version={self._marker_version})"
        )

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": f"marker-pdf {self._marker_version}",
            "lang": self.lang,
            "languages": self.languages,
            "use_gpu": self.use_gpu,
            "use_llm": self.use_llm,
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        """
        Full pipeline: preprocess → marker inference → confidence → normalize → format.

        Args:
            file_content: PDF or image bytes.
            output_format: "md", "html", or "json".

        Returns:
            Formatted result as UTF-8 bytes.
        """
        temp_path = None
        try:
            # 1. Preprocessing: bytes → temp file
            temp_path, file_info = load_document(file_content)
            logger.info(
                f"Loaded document: format={file_info['format']}, "
                f"size={file_info['size_bytes']}B"
            )

            # 2. Marker inference (with OOM recovery)
            raw_markdown = self._run_inference(temp_path)
            logger.info(f"Marker output: {len(raw_markdown)} chars")

            # 3. Confidence scoring
            confidence, scoring = calculate_confidence(raw_markdown)
            logger.info(f"Confidence: {confidence:.4f}")

            # 4. Normalize markdown
            normalized_md, changes = normalize_markdown(raw_markdown)
            if changes["page_numbers_removed"] > 0:
                logger.debug(
                    f"Removed {changes['page_numbers_removed']} page numbers"
                )

            # 5. Format output
            result = format_output(normalized_md, confidence, output_format)

            # 6. Cleanup GPU
            cleanup_torch_gpu_memory()

            return result

        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _run_inference(self, file_path: str) -> str:
        """Run Marker pipeline with OOM recovery (batch 8 → 4 → PermanentError)."""
        from marker.converters.pdf import PdfConverter

        converter = PdfConverter(
            artifact_dict=self.model_dict,
            config={
                "languages": self.languages,
                "use_llm": self.use_llm,
            },
        )

        try:
            rendered = converter(file_path)
        except Exception as e:
            if "OutOfMemoryError" not in type(e).__name__:
                raise

            # --- OOM recovery: reduce batch and retry once ---
            cleanup_torch_gpu_memory()
            logger.warning(
                f"CUDA OOM with batch={_DEFAULT_BATCH_SIZE} — retrying with batch=4"
            )

            os.environ["DETECTOR_BATCH_SIZE"] = "4"
            os.environ["RECOGNITION_BATCH_SIZE"] = "4"
            os.environ["LAYOUT_BATCH_SIZE"] = "4"

            try:
                converter = PdfConverter(
                    artifact_dict=self.model_dict,
                    config={
                        "languages": self.languages,
                        "use_llm": self.use_llm,
                    },
                )
                rendered = converter(file_path)

                # Restore batch size for next job
                os.environ["DETECTOR_BATCH_SIZE"] = _DEFAULT_BATCH_SIZE
                os.environ["RECOGNITION_BATCH_SIZE"] = _DEFAULT_BATCH_SIZE
                os.environ["LAYOUT_BATCH_SIZE"] = _DEFAULT_BATCH_SIZE

            except Exception as e2:
                cleanup_torch_gpu_memory()
                if "OutOfMemoryError" in type(e2).__name__:
                    raise PermanentError(
                        "CUDA OOM with batch=4 — file too complex for available VRAM"
                    )
                raise

        return rendered.markdown if hasattr(rendered, "markdown") else str(rendered)
