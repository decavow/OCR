"""Debug PaddleOCR output on paper_image.png"""
from PIL import Image
import numpy as np

img = Image.open("data_test/paper_image.png").convert("RGB")
image = np.array(img)
print(f"Image shape: {image.shape}")

from paddleocr import PaddleOCR
ocr = PaddleOCR(use_gpu=True, lang="en", use_angle_cls=True, show_log=False)
result = ocr.ocr(image, cls=True)
print(f"Result type: {type(result)}")
print(f"Result is None: {result is None}")
if result is not None:
    print(f"Result length: {len(result)}")
    for i, page in enumerate(result):
        print(f"Page {i}: type={type(page)}, is_None={page is None}")
        if page:
            print(f"  Lines: {len(page)}")
            for j, line in enumerate(page[:5]):
                print(f"  [{j}] {line}")
            if len(page) > 5:
                print(f"  ... and {len(page) - 5} more lines")
else:
    print("Result is None!")

# Also test PPStructure
print("\n=== PPStructure test ===")
from paddleocr import PPStructure
engine = PPStructure(use_gpu=True, lang="en", layout=True, table=True, ocr=True, show_log=False)
raw = engine(image)
print(f"PPStructure result: {len(raw)} regions")
for i, item in enumerate(raw[:3]):
    print(f"  [{i}] type={item.get('type')} bbox={item.get('bbox')} res_type={type(item.get('res'))}")
    res = item.get("res")
    if isinstance(res, dict):
        print(f"       keys={list(res.keys())}")
        if "html" in res:
            print(f"       html={res['html'][:100]}")
    elif isinstance(res, list):
        print(f"       items={len(res)}")
        if res:
            print(f"       first={res[0]}")
