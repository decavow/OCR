"""Debug: check plain PaddleOCR output on PDF."""
import sys
sys.path.insert(0, "../03_worker")

from app.engines.paddle_vl.preprocessing import load_images, prepare_image
from paddleocr import PaddleOCR
import numpy as np

with open("data_test/1709.04109v4.pdf", "rb") as f:
    content = f.read()
images = load_images(content)
print(f"Pages: {len(images)}")

ocr = PaddleOCR(use_gpu=True, lang="en", show_log=False)

# Test page 1
img = prepare_image(images[0])
print(f"Image shape: {img.shape}, dtype: {img.dtype}")

result = ocr.ocr(img, cls=True)
print(f"\nResult type: {type(result)}")
print(f"Result length: {len(result) if result else 0}")

if result:
    print(f"result[0] type: {type(result[0])}")
    if result[0]:
        print(f"result[0] length: {len(result[0])}")
        for i, line in enumerate(result[0][:5]):
            bbox = line[0]
            text, conf = line[1]
            print(f"  [{i}] conf={conf:.3f} text={text[:80]}")
        if len(result[0]) > 5:
            print(f"  ... +{len(result[0])-5} more lines")
    else:
        print("result[0] is empty/None")
else:
    print("Result is empty/None")
