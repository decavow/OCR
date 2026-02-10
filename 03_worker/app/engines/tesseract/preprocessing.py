# Image preprocessing for Tesseract

import logging
from io import BytesIO
from typing import List

from PIL import Image
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)


def is_pdf(file_content: bytes) -> bool:
    """Check if file is PDF by magic bytes."""
    return file_content[:4] == b'%PDF'


def pdf_to_images(file_content: bytes, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF to list of PIL Images."""
    logger.info("Converting PDF to images...")
    images = convert_from_bytes(file_content, dpi=dpi)
    logger.info(f"Converted PDF to {len(images)} page(s)")
    return images


def load_images(file_content: bytes) -> List[Image.Image]:
    """Load file content into list of PIL Images.

    Handles both image files and PDFs (multi-page).
    """
    if is_pdf(file_content):
        return pdf_to_images(file_content)
    return [Image.open(BytesIO(file_content))]


def prepare_image(image: Image.Image) -> Image.Image:
    """Prepare a single image for Tesseract OCR."""
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return image
