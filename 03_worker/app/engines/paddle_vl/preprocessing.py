# Image preprocessing for PaddleOCR-VL (multi-page PDF support)

import logging
from io import BytesIO
from typing import List

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def detect_file_type(file_content: bytes) -> str:
    """Detect file type from magic bytes."""
    if file_content[:4] == b'%PDF':
        return "pdf"
    return "image"


def load_images(file_content: bytes) -> List[np.ndarray]:
    """Load file bytes and convert to list of numpy arrays.

    Handles both single images and multi-page PDFs.
    """
    file_type = detect_file_type(file_content)

    if file_type == "pdf":
        from pdf2image import convert_from_bytes
        pil_images = convert_from_bytes(file_content, dpi=300)
        logger.info(f"Loaded PDF with {len(pil_images)} pages")
    else:
        pil_images = [Image.open(BytesIO(file_content))]

    images = []
    for img in pil_images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(np.array(img))

    return images


def prepare_image(image: np.ndarray) -> np.ndarray:
    """Prepare image for PPStructure inference."""
    # PPStructure expects RGB numpy array (same as PaddleOCR)
    # Additional preprocessing can be added here (deskew, denoise)
    return image
