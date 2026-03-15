"""Phase D — OCRProcessor tests (mock engine handlers).

Tests WP-001 through WP-011: initialization with different engines,
process dispatch, get_engine_info, and create_handler factory.
"""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_processor(engine="paddle", use_gpu="true", lang="en"):
    """Create an OCRProcessor with mocked engine handler creation."""
    mock_handler = MagicMock()
    mock_handler.process = AsyncMock(return_value=b"ocr result")
    mock_handler.get_engine_info = MagicMock(return_value={
        "engine": engine,
        "version": "2.7.3",
        "lang": lang,
        "use_gpu": use_gpu == "true",
    })

    env = {
        "OCR_ENGINE": engine,
        "USE_GPU": use_gpu,
        "OCR_LANG": lang,
    }

    with patch("app.core.processor.os.getenv", side_effect=lambda k, d="": env.get(k, d)):
        with patch("app.core.processor.create_handler", return_value=mock_handler):
            from app.core.processor import OCRProcessor
            processor = OCRProcessor()

    return processor, mock_handler


def _install_engine_mocks():
    """Install mock engine modules into sys.modules so create_handler imports work."""
    mock_text_handler = MagicMock()
    mock_tess_handler = MagicMock()
    mock_vl_handler = MagicMock()

    # paddle_text
    paddle_text_mod = ModuleType("app.engines.paddle_text")
    paddle_text_mod.TextRawHandler = mock_text_handler
    paddle_text_handler = ModuleType("app.engines.paddle_text.handler")
    paddle_text_handler.TextRawHandler = mock_text_handler

    # tesseract
    tess_mod = ModuleType("app.engines.tesseract")
    tess_mod.TextRawTesseractHandler = mock_tess_handler
    tess_handler = ModuleType("app.engines.tesseract.handler")
    tess_handler.TextRawTesseractHandler = mock_tess_handler

    # paddle_vl
    vl_mod = ModuleType("app.engines.paddle_vl")
    vl_mod.StructuredExtractHandler = mock_vl_handler
    vl_handler = ModuleType("app.engines.paddle_vl.handler")
    vl_handler.StructuredExtractHandler = mock_vl_handler

    saved = {}
    for key in [
        "app.engines.paddle_text", "app.engines.paddle_text.handler",
        "app.engines.tesseract", "app.engines.tesseract.handler",
        "app.engines.paddle_vl", "app.engines.paddle_vl.handler",
    ]:
        saved[key] = sys.modules.get(key)

    sys.modules["app.engines.paddle_text"] = paddle_text_mod
    sys.modules["app.engines.paddle_text.handler"] = paddle_text_handler
    sys.modules["app.engines.tesseract"] = tess_mod
    sys.modules["app.engines.tesseract.handler"] = tess_handler
    sys.modules["app.engines.paddle_vl"] = vl_mod
    sys.modules["app.engines.paddle_vl.handler"] = vl_handler

    return mock_text_handler, mock_tess_handler, mock_vl_handler, saved


def _restore_modules(saved):
    """Restore sys.modules to original state."""
    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProcessorInit:
    """WP-001 to WP-003: __init__ with different engines."""

    # WP-001: default engine is paddle with ocr_paddle_text handler
    def test_init_paddle_default(self):
        processor, handler = _make_processor(engine="paddle")
        assert processor.engine == "paddle"
        assert "ocr_paddle_text" in processor.handlers
        assert processor.use_gpu is True

    # WP-002: tesseract engine forces gpu=False
    def test_init_tesseract_no_gpu(self):
        processor, handler = _make_processor(engine="tesseract", use_gpu="true")
        assert processor.engine == "tesseract"
        assert processor.use_gpu is False
        assert "ocr_paddle_text" in processor.handlers

    # WP-003: paddle_vl registers structured_extract method
    def test_init_paddle_vl(self):
        processor, handler = _make_processor(engine="paddle_vl")
        assert processor.engine == "paddle_vl"
        assert "structured_extract" in processor.handlers
        assert "ocr_paddle_text" not in processor.handlers


class TestProcessorProcess:
    """WP-004 to WP-006: process dispatching."""

    # WP-004: process dispatches to correct handler
    @pytest.mark.asyncio
    async def test_process_dispatches(self):
        processor, handler = _make_processor(engine="paddle")

        result = await processor.process(b"image bytes", "txt", "ocr_paddle_text")

        handler.process.assert_awaited_once_with(b"image bytes", "txt")
        assert result == b"ocr result"

    # WP-005: process unknown method raises ValueError
    @pytest.mark.asyncio
    async def test_process_unknown_method(self):
        processor, _ = _make_processor(engine="paddle")

        with pytest.raises(ValueError, match="Unknown OCR method"):
            await processor.process(b"data", "txt", "nonexistent_method")

    # WP-006: process with paddle_vl and structured_extract
    @pytest.mark.asyncio
    async def test_process_paddle_vl(self):
        processor, handler = _make_processor(engine="paddle_vl")

        result = await processor.process(b"pdf bytes", "json", "structured_extract")

        handler.process.assert_awaited_once_with(b"pdf bytes", "json")
        assert result == b"ocr result"


class TestProcessorEngineInfo:
    """WP-007: get_engine_info."""

    # WP-007: returns handler's engine info
    def test_get_engine_info(self):
        processor, handler = _make_processor(engine="paddle")

        info = processor.get_engine_info()

        assert info["engine"] == "paddle"
        assert info["version"] == "2.7.3"
        handler.get_engine_info.assert_called_once()


class TestCreateHandler:
    """WP-008 to WP-011: create_handler factory function."""

    # WP-008: create_handler paddle -> TextRawHandler
    def test_create_handler_paddle(self):
        mock_text, mock_tess, mock_vl, saved = _install_engine_mocks()
        try:
            from app.core.processor import create_handler, ENGINE_PADDLE
            handler = create_handler(ENGINE_PADDLE, use_gpu=True, lang="en")
            mock_text.assert_called_once_with(use_gpu=True, lang="en")
        finally:
            _restore_modules(saved)

    # WP-009: create_handler tesseract -> TextRawTesseractHandler
    def test_create_handler_tesseract(self):
        mock_text, mock_tess, mock_vl, saved = _install_engine_mocks()
        try:
            from app.core.processor import create_handler, ENGINE_TESSERACT
            handler = create_handler(ENGINE_TESSERACT, use_gpu=False, lang="en")
            mock_tess.assert_called_once_with(lang="en")
        finally:
            _restore_modules(saved)

    # WP-010: create_handler paddle_vl -> StructuredExtractHandler
    def test_create_handler_paddle_vl(self):
        mock_text, mock_tess, mock_vl, saved = _install_engine_mocks()
        try:
            from app.core.processor import create_handler, ENGINE_PADDLE_VL
            handler = create_handler(ENGINE_PADDLE_VL, use_gpu=True, lang="en")
            mock_vl.assert_called_once_with(use_gpu=True, lang="en")
        finally:
            _restore_modules(saved)

    # WP-011: create_handler unknown defaults to paddle
    def test_create_handler_unknown_defaults_paddle(self):
        mock_text, mock_tess, mock_vl, saved = _install_engine_mocks()
        try:
            from app.core.processor import create_handler
            handler = create_handler("unknown_engine", use_gpu=False, lang="vi")
            mock_text.assert_called_once_with(use_gpu=False, lang="vi")
        finally:
            _restore_modules(saved)
