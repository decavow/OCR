"""Unit tests for Marker engine handler (FormattedTextHandler).

Tests MH-001 through MH-016: initialization, language parsing, engine info,
process pipeline, OOM recovery, and GPU management.

All heavy dependencies (marker, torch, surya) are mocked.
"""

import json
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from pathlib import Path
WORKER_ROOT = Path(__file__).parent.parent.parent / "03_worker"
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))


# ---------------------------------------------------------------------------
# Mock setup: install mock modules BEFORE importing handler
# ---------------------------------------------------------------------------

_SAVED_MODULES = {}


def _save_and_mock(module_path, mock_module):
    _SAVED_MODULES[module_path] = sys.modules.get(module_path)
    sys.modules[module_path] = mock_module


def _restore_modules():
    for key, val in _SAVED_MODULES.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val
    _SAVED_MODULES.clear()


def _install_marker_mocks():
    """Install mock marker/surya modules."""
    # marker top-level
    marker_mod = ModuleType("marker")
    marker_mod.__version__ = "1.2.3"
    _save_and_mock("marker", marker_mod)

    # marker.models
    marker_models = ModuleType("marker.models")
    marker_models.create_model_dict = MagicMock(return_value={})
    _save_and_mock("marker.models", marker_models)

    # marker.converters
    marker_converters = ModuleType("marker.converters")
    _save_and_mock("marker.converters", marker_converters)

    # marker.converters.pdf
    marker_pdf = ModuleType("marker.converters.pdf")
    mock_converter_class = MagicMock()
    marker_pdf.PdfConverter = mock_converter_class
    _save_and_mock("marker.converters.pdf", marker_pdf)

    return mock_converter_class


def _install_gpu_memory_mocks():
    """Mock the torch GPU memory functions that the handler imports."""
    gpu_mod = sys.modules.get("app.utils.gpu_memory")
    if gpu_mod is None:
        gpu_mod = ModuleType("app.utils.gpu_memory")
        _save_and_mock("app.utils.gpu_memory", gpu_mod)
    else:
        _SAVED_MODULES["app.utils.gpu_memory"] = gpu_mod

    # Add torch GPU functions that the handler expects
    gpu_mod.set_torch_gpu_memory_fraction = MagicMock()
    gpu_mod.check_torch_gpu_available = MagicMock(return_value=True)
    gpu_mod.log_torch_gpu_memory = MagicMock()
    gpu_mod.cleanup_torch_gpu_memory = MagicMock()

    return gpu_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_marker_modules():
    """Remove cached marker engine modules to force fresh import with mocks."""
    keys = [k for k in sys.modules if "app.engines.marker" in k]
    saved = {k: sys.modules.pop(k) for k in keys}
    yield
    # Restore after test
    for k, v in saved.items():
        sys.modules[k] = v
    _restore_modules()


# ---------------------------------------------------------------------------
# Language parsing
# ---------------------------------------------------------------------------

class TestParseLanguages:
    """MH-001 to MH-004: _parse_languages behavior."""

    def _parse(self, lang):
        _install_gpu_memory_mocks()
        _install_marker_mocks()
        # Clear so fresh import picks up mocks
        sys.modules.pop("app.engines.marker.handler", None)
        from app.engines.marker.handler import _parse_languages
        return _parse_languages(lang)

    # MH-001: English only
    def test_english_only(self):
        assert self._parse("en") == ["en"]

    # MH-002: Vietnamese always includes English
    def test_vietnamese_includes_english(self):
        result = self._parse("vi")
        assert "vi" in result
        assert "en" in result

    # MH-003: Vietnamese (vie code) also includes English
    def test_vietnamese_vie_code(self):
        result = self._parse("vie")
        assert "vi" in result or "vie" in result
        assert "en" in result

    # MH-004: Comma-separated languages
    def test_comma_separated(self):
        result = self._parse("en,vi")
        assert result == ["en", "vi"]


# ---------------------------------------------------------------------------
# Handler initialization and engine info
# ---------------------------------------------------------------------------

class TestFormattedTextHandler:
    """MH-005 to MH-010: init and get_engine_info."""

    def _make_handler(self, use_gpu=False, lang="en"):
        gpu_mod = _install_gpu_memory_mocks()
        mock_converter_class = _install_marker_mocks()
        sys.modules.pop("app.engines.marker.handler", None)
        from app.engines.marker.handler import FormattedTextHandler
        handler = FormattedTextHandler(use_gpu=use_gpu, lang=lang)
        return handler, mock_converter_class, gpu_mod

    # MH-005: Init sets correct attributes
    def test_init_attributes(self):
        handler, _, _ = self._make_handler(use_gpu=False, lang="en")
        assert handler.use_gpu is False
        assert handler.lang == "en"
        assert handler.languages == ["en"]
        assert handler.use_llm is False

    # MH-006: Init with Vietnamese
    def test_init_vietnamese(self):
        handler, _, _ = self._make_handler(use_gpu=False, lang="vi")
        assert handler.lang == "vi"
        assert "vi" in handler.languages
        assert "en" in handler.languages

    # MH-007: get_engine_info returns correct metadata
    def test_engine_info(self):
        handler, _, _ = self._make_handler(use_gpu=False, lang="en")
        info = handler.get_engine_info()
        assert info["engine"] == "marker"
        assert "marker-pdf" in info["version"]
        assert info["lang"] == "en"
        assert info["use_gpu"] is False
        assert info["use_llm"] is False

    # MH-008: GPU init calls gpu memory functions when use_gpu=True
    def test_gpu_init_calls(self):
        handler, _, gpu_mod = self._make_handler(use_gpu=True, lang="en")
        gpu_mod.set_torch_gpu_memory_fraction.assert_called_once()
        assert gpu_mod.log_torch_gpu_memory.call_count >= 2
        gpu_mod.check_torch_gpu_available.assert_called_once_with(min_free_mb=2000)

    # MH-009: No GPU calls when use_gpu=False
    def test_no_gpu_calls_when_disabled(self):
        handler, _, gpu_mod = self._make_handler(use_gpu=False, lang="en")
        gpu_mod.set_torch_gpu_memory_fraction.assert_not_called()
        gpu_mod.log_torch_gpu_memory.assert_not_called()

    # MH-010: use_llm is False when env var not set
    def test_use_llm_default_false(self):
        handler, _, _ = self._make_handler()
        assert handler.use_llm is False


# ---------------------------------------------------------------------------
# Process pipeline
# ---------------------------------------------------------------------------

class TestFormattedTextHandlerProcess:
    """MH-011 to MH-016: process pipeline with mocked inference."""

    def _make_handler_with_process(self, use_gpu=False, lang="en"):
        gpu_mod = _install_gpu_memory_mocks()
        mock_converter_class = _install_marker_mocks()
        sys.modules.pop("app.engines.marker.handler", None)
        from app.engines.marker.handler import FormattedTextHandler
        handler = FormattedTextHandler(use_gpu=use_gpu, lang=lang)
        return handler, mock_converter_class, gpu_mod

    # MH-011: Full process pipeline with md output
    @pytest.mark.asyncio
    async def test_process_md(self):
        handler, mock_converter_class, _ = self._make_handler_with_process()

        # Mock converter instance to return markdown
        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Test\n\nHello world from Marker."
        mock_converter_instance = MagicMock(return_value=mock_rendered)
        mock_converter_class.return_value = mock_converter_instance

        # Create valid PDF bytes for preprocessing
        pdf_bytes = b"%PDF-1.0 test content"

        result = await handler.process(pdf_bytes, "md")

        assert isinstance(result, bytes)
        text = result.decode("utf-8")
        assert "Hello world from Marker" in text

    # MH-012: Full process pipeline with json output
    @pytest.mark.asyncio
    async def test_process_json(self):
        handler, mock_converter_class, _ = self._make_handler_with_process()

        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Title\n\nA paragraph of text."
        mock_converter_instance = MagicMock(return_value=mock_rendered)
        mock_converter_class.return_value = mock_converter_instance

        pdf_bytes = b"%PDF-1.0 test content"
        result = await handler.process(pdf_bytes, "json")

        parsed = json.loads(result)
        assert "confidence" in parsed
        assert "blocks" in parsed
        assert parsed["blocks_count"] == len(parsed["blocks"])

    # MH-013: Full process pipeline with html output
    @pytest.mark.asyncio
    async def test_process_html(self):
        handler, mock_converter_class, _ = self._make_handler_with_process()

        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Hello\n\nWorld"
        mock_converter_instance = MagicMock(return_value=mock_rendered)
        mock_converter_class.return_value = mock_converter_instance

        pdf_bytes = b"%PDF-1.0 test content"
        result = await handler.process(pdf_bytes, "html")

        html = result.decode("utf-8")
        assert "<!DOCTYPE html>" in html
        assert "Hello" in html

    # MH-014: Temp file is cleaned up after process
    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self):
        handler, mock_converter_class, _ = self._make_handler_with_process()

        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Test"
        mock_converter_instance = MagicMock(return_value=mock_rendered)
        mock_converter_class.return_value = mock_converter_instance

        pdf_bytes = b"%PDF-1.0 content"
        captured_paths = []

        original_load = None
        sys.modules.pop("app.engines.marker.handler", None)
        from app.engines.marker import handler as handler_mod
        original_load = handler_mod.load_document

        def capturing_load(content):
            path, info = original_load(content)
            captured_paths.append(path)
            return path, info

        handler_mod.load_document = capturing_load
        try:
            handler_obj = handler_mod.FormattedTextHandler(use_gpu=False, lang="en")
            await handler_obj.process(pdf_bytes, "md")
        finally:
            handler_mod.load_document = original_load

        # Temp file should be deleted
        for p in captured_paths:
            assert not os.path.exists(p), f"Temp file not cleaned up: {p}"

    # MH-015: OOM recovery — first OOM triggers batch reduction and retry
    @pytest.mark.asyncio
    async def test_oom_recovery(self):
        handler, mock_converter_class, gpu_mod = self._make_handler_with_process()

        # First call raises OOM, second succeeds
        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Recovered"

        class FakeOOM(Exception):
            pass

        FakeOOM.__name__ = "OutOfMemoryError"

        call_count = [0]

        def converter_factory(**kwargs):
            converter_instance = MagicMock()
            def call_side_effect(path):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise FakeOOM("CUDA out of memory")
                return mock_rendered
            converter_instance.side_effect = call_side_effect
            converter_instance.__call__ = call_side_effect
            return converter_instance

        mock_converter_class.side_effect = converter_factory

        pdf_bytes = b"%PDF-1.0 content"
        result = await handler.process(pdf_bytes, "md")

        text = result.decode("utf-8")
        assert "Recovered" in text
        # cleanup should have been called for OOM
        gpu_mod.cleanup_torch_gpu_memory.assert_called()

    # MH-016: Process dispatches cleanup_torch_gpu_memory at end
    @pytest.mark.asyncio
    async def test_gpu_cleanup_after_process(self):
        handler, mock_converter_class, gpu_mod = self._make_handler_with_process()

        mock_rendered = MagicMock()
        mock_rendered.markdown = "# Done"
        mock_converter_instance = MagicMock(return_value=mock_rendered)
        mock_converter_class.return_value = mock_converter_instance

        pdf_bytes = b"%PDF-1.0 content"
        await handler.process(pdf_bytes, "md")

        gpu_mod.cleanup_torch_gpu_memory.assert_called()
