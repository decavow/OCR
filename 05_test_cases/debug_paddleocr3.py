"""Debug PaddleOCR: CPU mode vs GPU mode"""
from PIL import Image
import numpy as np

img = Image.open("data_test/paper_image.png").convert("RGB")
image = np.array(img)
print(f"Image shape: {image.shape}")

from paddleocr import PaddleOCR

# Test CPU mode
print("\n=== CPU mode ===")
ocr_cpu = PaddleOCR(use_gpu=False, lang="en", use_angle_cls=True, show_log=False)
result = ocr_cpu.ocr(image, cls=True)
if result and result[0]:
    print(f"Lines found: {len(result[0])}")
    for j, line in enumerate(result[0][:10]):
        box, (text, conf) = line
        print(f"  [{j}] conf={conf:.3f} text=\"{text}\"")
    if len(result[0]) > 10:
        print(f"  ... and {len(result[0]) - 10} more lines")
else:
    print(f"No text detected. Result: {result}")
