# Image preprocessing for PaddleOCR

import logging
from io import BytesIO

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def load_image(file_content: bytes) -> tuple[np.ndarray, tuple[int, int]]:
    """Load image bytes and convert to numpy array for PaddleOCR.

    Returns:
        (img_array, image_size) tuple
    """
    image = Image.open(BytesIO(file_content))

    # PaddleOCR requires RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    size = image.size
    img_array = np.array(image)

    logger.debug(f"Loaded image {size}, shape={img_array.shape}")
    return img_array, size
