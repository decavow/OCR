"""Debug: test PaddleOCR basic functionality - GPU vs CPU, simple image."""
import sys
sys.path.insert(0, "../03_worker")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from paddleocr import PaddleOCR

# Create a simple test image with text
img = Image.new("RGB", (400, 100), "white")
draw = ImageDraw.Draw(img)
draw.text((10, 30), "Hello World Test 123", fill="black")
img.save("debug_simple.png")
img_np = np.array(img)
print(f"Test image: {img_np.shape}")

# Test GPU
print("\n--- GPU OCR ---")
ocr_gpu = PaddleOCR(use_gpu=True, lang="en", show_log=False, use_angle_cls=True)
result = ocr_gpu.ocr(img_np, cls=False)
if result and result[0]:
    for line in result[0]:
        print(f"  {line[1][0]} (conf={line[1][1]:.3f})")
else:
    print("  No text detected (GPU)")

# Test CPU
print("\n--- CPU OCR ---")
ocr_cpu = PaddleOCR(use_gpu=False, lang="en", show_log=False, use_angle_cls=True)
result = ocr_cpu.ocr(img_np, cls=False)
if result and result[0]:
    for line in result[0]:
        print(f"  {line[1][0]} (conf={line[1][1]:.3f})")
else:
    print("  No text detected (CPU)")

# Test on PDF page with CPU
print("\n--- CPU on PDF page 1 ---")
from pdf2image import convert_from_bytes
with open("data_test/1709.04109v4.pdf", "rb") as f:
    content = f.read()
pages = convert_from_bytes(content, dpi=200, first_page=1, last_page=1)
pdf_np = np.array(pages[0].convert("RGB"))
print(f"PDF page shape: {pdf_np.shape}")
result = ocr_cpu.ocr(pdf_np, cls=False)
if result and result[0]:
    print(f"Lines: {len(result[0])}")
    for line in result[0][:5]:
        print(f"  {line[1][0]} (conf={line[1][1]:.3f})")
    if len(result[0]) > 5:
        print(f"  ... +{len(result[0])-5} more")
else:
    print("  No text detected (CPU on PDF)")

import os
os.remove("debug_simple.png")
