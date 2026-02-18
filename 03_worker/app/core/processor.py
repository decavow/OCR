# OCRProcessor: Supports PaddleOCR (GPU) and Tesseract (CPU)

import logging
import os
from typing import Dict, Any

from app.engines.base import BaseHandler

logger = logging.getLogger(__name__)

# Engine types
ENGINE_PADDLE = "paddle"
ENGINE_TESSERACT = "tesseract"
ENGINE_PADDLE_VL = "paddle_vl"


def create_handler(engine: str, use_gpu: bool, lang: str) -> BaseHandler:
    """Factory function to create OCR handler based on engine type."""
    if engine == ENGINE_TESSERACT:
        from app.engines.tesseract import TextRawTesseractHandler
        return TextRawTesseractHandler(lang=lang)
    elif engine == ENGINE_PADDLE_VL:
        from app.engines.paddle_vl import StructuredExtractHandler
        return StructuredExtractHandler(use_gpu=use_gpu, lang=lang)
    else:
        # Default: PaddleOCR
        from app.engines.paddle_text import TextRawHandler
        return TextRawHandler(use_gpu=use_gpu, lang=lang)


class OCRProcessor:
    """OCR processing engine supporting multiple backends."""

    def __init__(self):
        # Engine selection via environment
        engine = os.getenv("OCR_ENGINE", ENGINE_PADDLE).lower()
        use_gpu = os.getenv("USE_GPU", "true").lower() == "true"
        lang = os.getenv("OCR_LANG", "en")

        # Tesseract doesn't use GPU
        if engine == ENGINE_TESSERACT:
            use_gpu = False

        logger.info(f"Initializing OCR processor (engine={engine}, gpu={use_gpu}, lang={lang})")

        self.engine = engine
        self.lang = lang
        self.use_gpu = use_gpu

        # Paddle-VL registers "structured_extract" method instead of "text_raw"
        if engine == ENGINE_PADDLE_VL:
            self.handlers = {
                "structured_extract": create_handler(engine, use_gpu, lang),
            }
        else:
            self.handlers = {
                "text_raw": create_handler(engine, use_gpu, lang),
            }

    def get_engine_info(self) -> Dict[str, Any]:
        """Return engine information for registration."""
        handler = next(iter(self.handlers.values()), None)
        if handler and hasattr(handler, "get_engine_info"):
            return handler.get_engine_info()
        return {
            "engine": self.engine,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
        }

    async def process(
        self,
        file_content: bytes,
        output_format: str,
        method: str = "text_raw",
    ) -> bytes:
        """
        Process file with OCR.

        Args:
            file_content: Image/PDF bytes
            output_format: Output format (txt, json)
            method: OCR method (text_raw, etc.)

        Returns:
            Processed result as bytes
        """
        handler = self.handlers.get(method)
        if not handler:
            raise ValueError(f"Unknown OCR method: {method}")

        return await handler.process(file_content, output_format)
