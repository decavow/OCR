"""Debug: try PaddleOCR with file path, cls=False, and verify image content."""
import sys
sys.path.insert(0, "../03_worker")

import numpy as np
from PIL import Image
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

with open("data_test/1709.04109v4.pdf", "rb") as f:
    content = f.read()

pil_images = convert_from_bytes(content, dpi=200)
print(f"Pages: {len(pil_images)}")

# Save page 1 to disk for testing
img = pil_images[0]
img.save("debug_page1.png")
print(f"Saved page 1: {img.size} (WxH)")

ocr = PaddleOCR(use_gpu=True, lang="en", show_log=False, use_angle_cls=True)

# Test 1: file path
print("\n--- Test 1: file path ---")
result = ocr.ocr("debug_page1.png")
print(f"result type: {type(result)}, len: {len(result) if result else 0}")
if result and result[0]:
    print(f"Lines: {len(result[0])}")
    for line in result[0][:5]:
        text, conf = line[1]
        print(f"  conf={conf:.3f} text={text[:80]}")
    if len(result[0]) > 5:
        print(f"  ... +{len(result[0])-5} more")
else:
    print("No text detected")

# Test 2: numpy array without cls
print("\n--- Test 2: numpy array, cls=False ---")
img_np = np.array(img.convert("RGB"))
result = ocr.ocr(img_np, cls=False)
print(f"result type: {type(result)}, len: {len(result) if result else 0}")
if result and result[0]:
    print(f"Lines: {len(result[0])}")
    for line in result[0][:5]:
        text, conf = line[1]
        print(f"  conf={conf:.3f} text={text[:80]}")
else:
    print("No text detected")

# Test 3: smaller image
print("\n--- Test 3: resized 50% ---")
small = img.resize((img.width // 2, img.height // 2))
small_np = np.array(small.convert("RGB"))
print(f"Small shape: {small_np.shape}")
result = ocr.ocr(small_np, cls=False)
if result and result[0]:
    print(f"Lines: {len(result[0])}")
    for line in result[0][:5]:
        text, conf = line[1]
        print(f"  conf={conf:.3f} text={text[:80]}")
else:
    print("No text detected")

import os
os.remove("debug_page1.png")
