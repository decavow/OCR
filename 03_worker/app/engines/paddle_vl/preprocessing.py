# Image preprocessing for PaddleOCR-VL (multi-page PDF support)

import logging
from io import BytesIO
from typing import List

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# PPStructure needs sufficient resolution for layout detection.
# Images with shorter side below this threshold will be upscaled.
MIN_SHORT_SIDE = 1500
MAX_LONG_SIDE = 4000


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
    """Prepare image for PPStructure inference.

    Upscales small images so layout detection and OCR work reliably.
    """
    h, w = image.shape[:2]
    short_side = min(h, w)
    long_side = max(h, w)

    if short_side < MIN_SHORT_SIDE:
        scale = MIN_SHORT_SIDE / short_side
        # Don't exceed max long side
        if long_side * scale > MAX_LONG_SIDE:
            scale = MAX_LONG_SIDE / long_side
        if scale > 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            logger.info(
                f"Upscaling image from {w}x{h} to {new_w}x{new_h} "
                f"(scale={scale:.2f}x) for better layout detection"
            )
            pil_img = Image.fromarray(image)
            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
            image = np.array(pil_img)

    return image
