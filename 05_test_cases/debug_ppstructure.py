"""Debug: check PPStructure fallback engine output format."""
import sys
sys.path.insert(0, "../03_worker")

from app.engines.paddle_vl.preprocessing import load_images, prepare_image
from paddleocr import PPStructure

with open("data_test/1709.04109v4.pdf", "rb") as f:
    content = f.read()
images = load_images(content)
print(f"Pages: {len(images)}")

# Fallback engine (table=False)
engine = PPStructure(use_gpu=True, lang="en", layout=True, table=False, ocr=True, show_log=False)
img = prepare_image(images[0])
result = engine(img)
print(f"\nRegions on page 1: {len(result)}")
for i, r in enumerate(result[:5]):
    rtype = r.get("type", "?")
    res = r.get("res", None)
    res_type = type(res).__name__
    print(f"\n  [{i}] type={rtype}, res_type={res_type}, keys={list(r.keys())}")
    if isinstance(res, list) and len(res) > 0:
        print(f"       res[0] type={type(res[0]).__name__}")
        if isinstance(res[0], dict):
            print(f"       res[0] keys={list(res[0].keys())}")
            print(f"       res[0] = {str(res[0])[:200]}")
        else:
            print(f"       res[0] = {str(res[0])[:200]}")
    elif isinstance(res, dict):
        print(f"       res keys={list(res.keys())}")
    else:
        print(f"       res = {str(res)[:200]}")
