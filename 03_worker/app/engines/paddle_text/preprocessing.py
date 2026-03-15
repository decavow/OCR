# Image preprocessing for PaddleOCR (supports PNG/JPG/PDF)

import logging
import os
from io import BytesIO

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# PDF magic bytes
_PDF_MAGIC = b"%PDF"


def _is_pdf(file_content: bytes) -> bool:
    return file_content[:4] == _PDF_MAGIC


MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "5"))


def _pdf_to_images(file_content: bytes, max_pages: int = 0) -> list[Image.Image]:
    """Convert PDF pages to PIL Images using pypdfium2.

    Args:
        max_pages: Max pages to render. 0 = use MAX_PDF_PAGES env default.
    """
    import pypdfium2 as pdfium

    limit = max_pages or MAX_PDF_PAGES

    pdf = pdfium.PdfDocument(file_content)
    total = len(pdf)
    pages_to_render = min(total, limit)
    logger.info(f"PDF has {total} pages, rendering {pages_to_render}")

    images = []
    for i in range(pages_to_render):
        page = pdf[i]
        # Render at 200 DPI (faster than 300, still good for OCR)
        bitmap = page.render(scale=200 / 72)
        pil_image = bitmap.to_pil()
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        images.append(pil_image)
        logger.debug(f"PDF page {i+1}/{pages_to_render}: {pil_image.size}")
    pdf.close()
    return images


def load_image(file_content: bytes) -> tuple[np.ndarray, tuple[int, int]]:
    """Load image bytes and convert to numpy array for PaddleOCR.

    For PDF: renders first page only (single-page OCR).
    Use load_images() for multi-page PDF.

    Returns:
        (img_array, image_size) tuple
    """
    if _is_pdf(file_content):
        images = _pdf_to_images(file_content)
        if not images:
            raise ValueError("PDF has no pages")
        image = images[0]
    else:
        image = Image.open(BytesIO(file_content))

    # PaddleOCR requires RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    size = image.size
    img_array = np.array(image)

    logger.debug(f"Loaded image {size}, shape={img_array.shape}")
    return img_array, size


def load_images(file_content: bytes) -> list[tuple[np.ndarray, tuple[int, int]]]:
    """Load all pages (PDF) or single image as list of (array, size).

    Returns:
        List of (img_array, image_size) tuples
    """
    if _is_pdf(file_content):
        pil_images = _pdf_to_images(file_content)
    else:
        img = Image.open(BytesIO(file_content))
        pil_images = [img]

    results = []
    for image in pil_images:
        if image.mode != "RGB":
            image = image.convert("RGB")
        results.append((np.array(image), image.size))

    return results
