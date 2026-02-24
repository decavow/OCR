"""
Test cases for OCR Processor (PaddleOCR).
"""

import json
import pytest


class TestTextRawHandler:
    """Tests for TextRawHandler with PaddleOCR."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        from app.handlers.ocr_text_raw import TextRawHandler

        # Try GPU first, fallback to CPU
        try:
            return TextRawHandler(use_gpu=True, lang="en")
        except Exception:
            return TextRawHandler(use_gpu=False, lang="en")

    @pytest.mark.asyncio
    async def test_handler_initialization(self):
        """Should initialize PaddleOCR handler."""
        from app.handlers.ocr_text_raw import TextRawHandler

        # Try GPU
        try:
            handler = TextRawHandler(use_gpu=True, lang="en")
            assert handler.ocr is not None
        except Exception:
            # Fallback to CPU
            handler = TextRawHandler(use_gpu=False, lang="en")
            assert handler.ocr is not None

    @pytest.mark.asyncio
    async def test_process_minimal_png(self, handler, sample_png):
        """Should process minimal PNG without error."""
        result = await handler.process(sample_png, "txt")

        assert isinstance(result, bytes)
        # Minimal image may not have text, but should not crash

    @pytest.mark.asyncio
    async def test_process_image_with_text(self, handler, test_image_with_text):
        """Should extract text from image."""
        img_bytes, expected_text = test_image_with_text

        result = await handler.process(img_bytes, "txt")
        result_text = result.decode("utf-8")

        # Check if some text was extracted
        assert len(result_text.strip()) > 0

        # Check if expected text is in result (case-insensitive)
        # Note: OCR may not be 100% accurate
        if expected_text:
            # At least some words should match
            expected_words = expected_text.lower().split()
            result_lower = result_text.lower()
            matches = sum(1 for word in expected_words if word in result_lower)
            assert matches > 0, f"Expected words from '{expected_text}' in '{result_text}'"

    @pytest.mark.asyncio
    async def test_output_format_txt(self, handler, test_image_with_text):
        """Should return plain text for txt format."""
        img_bytes, _ = test_image_with_text

        result = await handler.process(img_bytes, "txt")

        assert isinstance(result, bytes)
        text = result.decode("utf-8")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_output_format_json(self, handler, test_image_with_text):
        """Should return JSON for json format."""
        img_bytes, _ = test_image_with_text

        result = await handler.process(img_bytes, "json")

        assert isinstance(result, bytes)
        data = json.loads(result.decode("utf-8"))

        # Check required fields
        assert "text" in data
        assert "lines" in data
        assert isinstance(data["lines"], int)

    @pytest.mark.asyncio
    async def test_json_includes_details(self, handler, test_image_with_text):
        """Should include bounding boxes and confidence in JSON."""
        img_bytes, _ = test_image_with_text

        result = await handler.process(img_bytes, "json")
        data = json.loads(result.decode("utf-8"))

        # Check for details array
        if "details" in data and len(data["details"]) > 0:
            detail = data["details"][0]
            assert "text" in detail
            assert "confidence" in detail
            assert "box" in detail

    @pytest.mark.asyncio
    async def test_handles_rgba_image(self, handler):
        """Should handle RGBA images (with alpha channel)."""
        from PIL import Image
        import io

        # Create RGBA image
        img = Image.new('RGBA', (100, 50), color=(255, 255, 255, 128))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')

        result = await handler.process(buffer.getvalue(), "txt")
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_handles_grayscale_image(self, handler):
        """Should handle grayscale images."""
        from PIL import Image
        import io

        # Create grayscale image
        img = Image.new('L', (100, 50), color=255)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')

        result = await handler.process(buffer.getvalue(), "txt")
        assert isinstance(result, bytes)


class TestOCRProcessor:
    """Tests for OCRProcessor wrapper."""

    @pytest.mark.asyncio
    async def test_processor_initialization(self):
        """Should initialize processor with handlers."""
        from app.core.processor import OCRProcessor

        processor = OCRProcessor()
        assert "ocr_text_raw" in processor.handlers

    @pytest.mark.asyncio
    async def test_processor_ocr_text_raw_method(self, test_image_with_text):
        """Should process with ocr_text_raw method."""
        from app.core.processor import OCRProcessor

        processor = OCRProcessor()
        img_bytes, _ = test_image_with_text

        result = await processor.process(
            file_content=img_bytes,
            output_format="txt",
            method="ocr_text_raw"
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_processor_unknown_method(self, sample_png):
        """Should raise error for unknown method."""
        from app.core.processor import OCRProcessor

        processor = OCRProcessor()

        with pytest.raises(ValueError, match="Unknown"):
            await processor.process(
                file_content=sample_png,
                output_format="txt",
                method="unknown_method"
            )
