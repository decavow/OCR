"""Phase E — Engine handler integration tests (mock OCR engines).

Tests EH-001 through EH-014: TextRawHandler, TextRawTesseractHandler,
and StructuredExtractHandler with mocked underlying engines.

Engine libraries (paddleocr, pytesseract, PPStructure, pdf2image) are not
installed in the test environment. We install mock modules in sys.modules
before importing handler code, then restore them after each test class.
"""

import json
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Install mock dependencies into sys.modules
# ---------------------------------------------------------------------------

_SAVED_MODULES = {}


def _save_and_mock(module_path, mock_module):
    """Save current module (if any) and install mock."""
    _SAVED_MODULES[module_path] = sys.modules.get(module_path)
    sys.modules[module_path] = mock_module


def _restore_modules():
    """Restore previously saved modules."""
    for key, val in _SAVED_MODULES.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val
    _SAVED_MODULES.clear()


def _install_paddleocr_mock():
    """Mock paddleocr module."""
    mod = ModuleType("paddleocr")
    mod.PaddleOCR = MagicMock()
    mod.PPStructure = MagicMock()
    _save_and_mock("paddleocr", mod)
    return mod


def _install_pytesseract_mock():
    """Mock pytesseract module."""
    mod = ModuleType("pytesseract")
    mod.get_tesseract_version = MagicMock(return_value="5.3.0")
    mod.image_to_string = MagicMock(return_value="")
    mod.image_to_data = MagicMock(return_value={})
    mod.pytesseract = MagicMock()
    mod.Output = MagicMock()
    mod.Output.DICT = "dict"
    _save_and_mock("pytesseract", mod)
    return mod


def _install_pdf2image_mock():
    """Mock pdf2image module."""
    mod = ModuleType("pdf2image")
    mod.convert_from_bytes = MagicMock(return_value=[])
    _save_and_mock("pdf2image", mod)
    return mod


def _install_pil_mock():
    """Ensure PIL.Image is available (it should be, but mock if not)."""
    try:
        from PIL import Image
    except ImportError:
        pil = ModuleType("PIL")
        pil_image = ModuleType("PIL.Image")
        pil_image.Image = MagicMock
        pil_image.open = MagicMock
        pil_image.fromarray = MagicMock
        pil_image.LANCZOS = 1
        pil.Image = pil_image
        _save_and_mock("PIL", pil)
        _save_and_mock("PIL.Image", pil_image)


# ---------------------------------------------------------------------------
# Remove cached engine modules to force re-import with mocks
# ---------------------------------------------------------------------------

def _clear_engine_modules():
    """Remove engine modules from sys.modules to force fresh import."""
    keys_to_remove = [k for k in sys.modules if k.startswith("app.engines.")]
    for k in keys_to_remove:
        _save_and_mock(k, sys.modules[k])
        del sys.modules[k]


# Install all mocks upfront
_install_paddleocr_mock()
_install_pytesseract_mock()
_install_pdf2image_mock()
_install_pil_mock()
_clear_engine_modules()


# ---------------------------------------------------------------------------
# TextRawHandler (PaddleOCR)
# ---------------------------------------------------------------------------

class TestTextRawHandler:
    """EH-001 to EH-003: PaddleOCR TextRawHandler."""

    def _make_handler(self):
        """Create a TextRawHandler with mocked PaddleOCR."""
        # Ensure fresh import
        paddleocr = sys.modules["paddleocr"]
        mock_engine = MagicMock()
        paddleocr.PaddleOCR.return_value = mock_engine

        from app.engines.paddle_text.handler import TextRawHandler
        handler = TextRawHandler(use_gpu=False, lang="en")

        return handler, mock_engine

    # EH-001: get_engine_info returns correct metadata
    def test_get_engine_info(self):
        handler, _ = self._make_handler()
        info = handler.get_engine_info()

        assert info["engine"] == "paddleocr"
        # Version comes from importlib.metadata; mocked paddleocr → "unknown"
        assert isinstance(info["version"], str)
        assert info["lang"] == "en"
        assert info["use_gpu"] is False

    # EH-002: process with txt format returns text bytes
    @pytest.mark.asyncio
    async def test_process_txt(self):
        handler, mock_engine = self._make_handler()

        # Mock PaddleOCR result structure:
        # [ [ [box, (text, confidence)], ... ] ]
        mock_engine.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("Hello World", 0.95)],
            [[[0, 25], [100, 25], [100, 45], [0, 45]], ("Second line", 0.88)],
        ]]

        with patch("app.engines.paddle_text.handler.load_images") as mock_load:
            mock_load.return_value = [(np.zeros((100, 100, 3), dtype=np.uint8), (100, 100))]
            result = await handler.process(b"fake image", "txt")

        assert b"Hello World" in result
        assert b"Second line" in result

    # EH-003: process with json format returns JSON bytes
    @pytest.mark.asyncio
    async def test_process_json(self):
        handler, mock_engine = self._make_handler()

        mock_engine.ocr.return_value = [[
            [[[0, 0], [50, 0], [50, 15], [0, 15]], ("Test", 0.99)],
        ]]

        with patch("app.engines.paddle_text.handler.load_images") as mock_load:
            mock_load.return_value = [(np.zeros((50, 50, 3), dtype=np.uint8), (50, 50))]
            result = await handler.process(b"fake image", "json")

        parsed = json.loads(result)
        assert "text" in parsed
        assert "details" in parsed
        assert parsed["lines"] == 1


# ---------------------------------------------------------------------------
# TextRawTesseractHandler
# ---------------------------------------------------------------------------

class TestTextRawTesseractHandler:
    """EH-004 to EH-008: Tesseract TextRawTesseractHandler."""

    def _make_handler(self, lang="en"):
        """Create a TextRawTesseractHandler with mocked pytesseract."""
        pytesseract = sys.modules["pytesseract"]
        pytesseract.get_tesseract_version = MagicMock(return_value="5.3.0")

        from app.engines.tesseract.handler import TextRawTesseractHandler
        handler = TextRawTesseractHandler(lang=lang)

        return handler

    # EH-004: init maps language code
    def test_init_lang_mapping(self):
        handler = self._make_handler(lang="vi")
        assert handler.lang == "vie"

    # EH-005: init raises when tesseract not found
    def test_init_tesseract_not_found(self):
        pytesseract = sys.modules["pytesseract"]
        orig = pytesseract.get_tesseract_version
        pytesseract.get_tesseract_version = MagicMock(
            side_effect=RuntimeError("not found")
        )

        try:
            from app.engines.tesseract.handler import TextRawTesseractHandler
            with pytest.raises(RuntimeError, match="Tesseract is not installed"):
                TextRawTesseractHandler(lang="en")
        finally:
            pytesseract.get_tesseract_version = orig

    # EH-006: get_engine_info returns correct metadata
    def test_get_engine_info(self):
        handler = self._make_handler(lang="en")
        info = handler.get_engine_info()

        assert info["engine"] == "tesseract"
        assert info["version"] == "5.3.0"
        assert info["lang"] == "eng"

    # EH-007: process txt returns text bytes
    @pytest.mark.asyncio
    async def test_process_txt(self):
        handler = self._make_handler()
        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (100, 100)

        with patch("app.engines.tesseract.handler.load_images", return_value=[mock_image]), \
             patch("app.engines.tesseract.handler.prepare_image", return_value=mock_image), \
             patch("app.engines.tesseract.handler.extract_plain", return_value=["Hello Tesseract"]), \
             patch("app.engines.tesseract.handler.format_output", return_value=b"Hello Tesseract"):

            result = await handler.process(b"image bytes", "txt")

        assert result == b"Hello Tesseract"

    # EH-008: process json uses extract_detailed
    @pytest.mark.asyncio
    async def test_process_json(self):
        handler = self._make_handler()
        mock_image = MagicMock()
        mock_image.mode = "RGB"
        mock_image.size = (100, 100)

        detail_lines = ["Line 1"]
        detail_boxes = [{"text": "Line 1", "confidence": 0.95, "box": []}]
        json_output = json.dumps({
            "text": "Line 1",
            "lines": 1,
            "pages": 1,
            "details": detail_boxes,
        }).encode()

        with patch("app.engines.tesseract.handler.load_images", return_value=[mock_image]), \
             patch("app.engines.tesseract.handler.prepare_image", return_value=mock_image), \
             patch("app.engines.tesseract.handler.extract_detailed", return_value=(detail_lines, detail_boxes)), \
             patch("app.engines.tesseract.handler.format_output", return_value=json_output):

            result = await handler.process(b"image bytes", "json")

        parsed = json.loads(result)
        assert "details" in parsed


# ---------------------------------------------------------------------------
# StructuredExtractHandler (PaddleOCR-VL)
# ---------------------------------------------------------------------------

class TestStructuredExtractHandler:
    """EH-009 to EH-014: PaddleOCR-VL StructuredExtractHandler."""

    def _make_handler(self):
        """Create a StructuredExtractHandler with mocked PPStructure."""
        paddleocr = sys.modules["paddleocr"]
        mock_engine = MagicMock()
        paddleocr.PPStructure.return_value = mock_engine
        paddleocr.PaddleOCR.return_value = MagicMock()

        from app.engines.paddle_vl.handler import StructuredExtractHandler
        handler = StructuredExtractHandler(use_gpu=False, lang="en")

        return handler, mock_engine

    # EH-009: get_engine_info returns correct metadata with capabilities
    def test_get_engine_info(self):
        handler, _ = self._make_handler()
        info = handler.get_engine_info()

        assert info["engine"] == "paddleocr-vl"
        # Version comes from importlib.metadata; mocked paddleocr → "unknown"
        assert isinstance(info["version"], str)
        assert "capabilities" in info
        assert "layout_analysis" in info["capabilities"]

    # EH-010: process with text regions returns structured output
    @pytest.mark.asyncio
    async def test_process_text_regions(self):
        handler, mock_engine = self._make_handler()

        # PPStructure output format
        raw_result = [
            {
                "type": "text",
                "bbox": [10, 10, 200, 30],
                "res": [
                    {"text": "Hello structured", "confidence": 0.92, "text_region": []},
                ],
            },
        ]
        mock_engine.return_value = raw_result

        with patch("app.engines.paddle_vl.handler.load_images") as mock_load, \
             patch("app.engines.paddle_vl.handler.prepare_image") as mock_prep, \
             patch("app.engines.paddle_vl.handler.assess_result_quality", return_value=True), \
             patch("app.engines.paddle_vl.handler.DebugContext"):
            mock_load.return_value = [np.zeros((100, 200, 3), dtype=np.uint8)]
            mock_prep.side_effect = lambda x: x

            result = await handler.process(b"image bytes", "json")

        parsed = json.loads(result)
        assert "pages" in parsed
        assert len(parsed["pages"]) == 1

    # EH-011: process falls back to pure OCR when quality is poor
    @pytest.mark.asyncio
    async def test_process_fallback_on_poor_quality(self):
        handler, mock_engine = self._make_handler()

        # Primary returns empty -> poor quality
        mock_engine.return_value = []

        # Set up fallback OCR engine (lazy-loaded via _get_ocr_engine)
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("Fallback text", 0.80)],
        ]]
        handler._ocr_engine = mock_ocr

        with patch("app.engines.paddle_vl.handler.load_images") as mock_load, \
             patch("app.engines.paddle_vl.handler.prepare_image") as mock_prep, \
             patch("app.engines.paddle_vl.handler.assess_result_quality", return_value=False), \
             patch("app.engines.paddle_vl.handler.DebugContext"):
            mock_load.return_value = [np.zeros((100, 100, 3), dtype=np.uint8)]
            mock_prep.side_effect = lambda x: x

            result = await handler.process(b"image", "txt")

        # Fallback OCR engine should have been used
        mock_ocr.ocr.assert_called()

    # EH-012: _run_engine catches IndexError and returns empty list
    def test_run_engine_fallback_on_error(self):
        handler, mock_engine = self._make_handler()
        mock_engine.side_effect = IndexError("table matcher crash")

        result = handler._run_engine(np.zeros((50, 50, 3), dtype=np.uint8))

        # v2 _run_engine catches IndexError/ValueError and returns []
        assert result == []

    # EH-013: _ocr_result_is_empty detects empty results
    def test_ocr_result_is_empty(self):
        handler, _ = self._make_handler()

        from app.engines.paddle_vl.handler import StructuredExtractHandler

        assert StructuredExtractHandler._ocr_result_is_empty(None) is True
        assert StructuredExtractHandler._ocr_result_is_empty([]) is True
        assert StructuredExtractHandler._ocr_result_is_empty([None]) is True
        assert StructuredExtractHandler._ocr_result_is_empty([None, None]) is True
        assert StructuredExtractHandler._ocr_result_is_empty([[]]) is False

    # EH-014: _run_pure_ocr delegates to lazy-loaded OCR engine
    def test_run_pure_ocr(self):
        handler, _ = self._make_handler()

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[
            [[[0, 0], [50, 0], [50, 15], [0, 15]], ("Pure OCR text", 0.97)],
        ]]
        # Set the lazy-loaded OCR engine directly
        handler._ocr_engine = mock_ocr

        img = np.zeros((50, 50, 3), dtype=np.uint8)
        result = handler._run_pure_ocr(img)

        mock_ocr.ocr.assert_called_once_with(img, cls=True)
        assert len(result) == 1
