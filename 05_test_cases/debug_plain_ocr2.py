"""Debug: check plain PaddleOCR output - try BGR conversion and lower DPI."""
import sys
sys.path.insert(0, "../03_worker")

import numpy as np
from PIL import Image
from io import BytesIO
from paddleocr import PaddleOCR
import cv2

with open("data_test/1709.04109v4.pdf", "rb") as f:
    content = f.read()

# Try lower DPI
from pdf2image import convert_from_bytes
pil_images = convert_from_bytes(content, dpi=150)
print(f"Pages: {len(pil_images)}")

img_rgb = np.array(pil_images[0].convert("RGB"))
print(f"RGB shape: {img_rgb.shape}")

# PaddleOCR expects BGR by default
img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
print(f"BGR shape: {img_bgr.shape}")

ocr = PaddleOCR(use_gpu=True, lang="en", show_log=False)

# Test with BGR
result = ocr.ocr(img_bgr, cls=True)
print(f"\nBGR result[0]: {type(result[0]) if result else 'None'}")
if result and result[0]:
    print(f"Lines: {len(result[0])}")
    for line in result[0][:5]:
        text, conf = line[1]
        print(f"  conf={conf:.3f} text={text[:80]}")
    if len(result[0]) > 5:
        print(f"  ... +{len(result[0])-5} more")
else:
    # Try with RGB
    print("\nTrying RGB...")
    result = ocr.ocr(img_rgb, cls=True)
    print(f"RGB result[0]: {type(result[0]) if result else 'None'}")
    if result and result[0]:
        print(f"Lines: {len(result[0])}")
        for line in result[0][:5]:
            text, conf = line[1]
            print(f"  conf={conf:.3f} text={text[:80]}")
