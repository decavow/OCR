"""Debug PaddleOCR with upscaled image"""
from PIL import Image
import numpy as np

img = Image.open("data_test/paper_image.png").convert("RGB")
print(f"Original size: {img.size}")

# Upscale to ~2x
scale = 2.0
new_w, new_h = int(img.width * scale), int(img.height * scale)
img_up = img.resize((new_w, new_h), Image.LANCZOS)
print(f"Upscaled size: {img_up.size}")
image = np.array(img_up)

from paddleocr import PaddleOCR
ocr = PaddleOCR(use_gpu=True, lang="en", use_angle_cls=True, show_log=False)

print("\n=== Testing upscaled image ===")
result = ocr.ocr(image, cls=True)
print(f"Result type: {type(result)}")
if result is not None:
    print(f"Result length: {len(result)}")
    for i, page in enumerate(result):
        if page is None:
            print(f"Page {i}: None")
        else:
            print(f"Page {i}: {len(page)} lines")
            for j, line in enumerate(page[:10]):
                box, (text, conf) = line
                print(f"  [{j}] conf={conf:.3f} text=\"{text}\"")
            if len(page) > 10:
                print(f"  ... and {len(page) - 10} more lines")
else:
    print("Result is None!")

# Also try with 3x upscale
print("\n=== Testing 3x upscale ===")
scale3 = 3.0
img_up3 = img.resize((int(img.width * scale3), int(img.height * scale3)), Image.LANCZOS)
print(f"3x size: {img_up3.size}")
image3 = np.array(img_up3)
result3 = ocr.ocr(image3, cls=True)
if result3 and result3[0]:
    print(f"Lines found: {len(result3[0])}")
    for j, line in enumerate(result3[0][:10]):
        box, (text, conf) = line
        print(f"  [{j}] conf={conf:.3f} text=\"{text}\"")
    if len(result3[0]) > 10:
        print(f"  ... and {len(result3[0]) - 10} more lines")
else:
    print(f"Result: {result3}")
