# Add PaddleOCR-VL Worker - Structured Data Extraction

> Version: 1.0 | Phase: 2 - Add Worker
> Depends on: Local MVP1 (Phase 1)

---

## 1. Overview

### 1.1 Context

Hien tai he thong co 1 worker duy nhat dang chay: **Tesseract** (CPU) cho viec extract text thuan (method: `text_raw`).
Worker PaddleOCR text thuan cung da co code nhung chua trien khai.

**Van de:** Khi user upload tai lieu co cau truc (hoa don, bang bieu, form, receipt...), `text_raw` chi tra ve plain text, **mat toan bo layout va cau truc du lieu**.

### 1.2 Muc tieu

Them 1 worker moi su dung **PaddleOCR-VL (Vision-Language model)** de:
- Chay tren **GPU** (CUDA)
- Extract data **giu nguyen cau truc** (bang, form, key-value pairs)
- Tra ve ket qua dang **structured JSON** hoac **Markdown** (giu layout)
- Dang ky method moi: **`structured_extract`** (tach biet voi `text_raw`)

### 1.3 PaddleOCR-VL la gi?

PaddleOCR-VL (Vision-Language) su dung PP-OCRv4 ket hop voi layout analysis va table recognition:
- **Layout Analysis**: Phan vung trang tai lieu (text, table, figure, title, list)
- **Table Recognition**: Nhan dien cau truc bang va chuyen thanh HTML/Markdown
- **Key-Value Extraction**: Nhan dien cap key-value trong form
- **Reading Order Detection**: Xac dinh thu tu doc dung

---

## 2. High-Level Architecture

### 2.1 Vi tri trong he thong

Worker moi nam o **Processing Layer**, song song voi cac worker hien tai. Khong thay doi bat ky thanh phan nao o Edge hay Orchestration layer ngoai viec them method moi.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROCESSING LAYER                              │
│                                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│   │  Tesseract Worker│  │ PaddleOCR Worker │  │ PaddleOCR-VL    │ │
│   │  (CPU)           │  │ (GPU - text_raw) │  │ Worker (GPU)    │ │
│   │                  │  │                  │  │                  │ │
│   │  method:         │  │  method:         │  │  method:         │ │
│   │  text_raw        │  │  text_raw        │  │  structured_     │ │
│   │                  │  │                  │  │  extract          │ │
│   │  subject:        │  │  subject:        │  │                  │ │
│   │  ocr.text_raw.   │  │  ocr.text_raw.   │  │  subject:        │ │
│   │  tier0           │  │  tier0           │  │  ocr.structured_ │ │
│   │                  │  │                  │  │  extract.tier0    │ │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                      │
│   Tat ca worker deu:                                                │
│   - Self-register qua POST /api/v1/internal/register                │
│   - Poll NATS queue theo subject rieng                              │
│   - Download/Upload qua File Proxy                                  │
│   - Gui heartbeat moi 30s                                           │
│   - KHONG co storage credentials                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Tong quan flow cho structured_extract

```
User upload tai lieu (PDF/image)
    │
    │  chon method = "structured_extract"
    │  chon output_format = "json" hoac "md"
    v
Backend tao Job, publish NATS
    │  subject: ocr.structured_extract.tier0
    v
PaddleOCR-VL Worker pull job
    │
    v
┌─────────────────────────────────────────────────────────────┐
│  PADDLE-OCR-VL PROCESSING PIPELINE                           │
│                                                              │
│  1. Preprocessing                                            │
│     - Load image/PDF -> per-page images                     │
│     - Convert to RGB numpy array                            │
│     - (Optional) Deskew, denoise                            │
│                                                              │
│  2. Layout Analysis (PP-StructureV2)                        │
│     - Detect regions: text, table, figure, title, list      │
│     - Determine reading order                               │
│     - Output: list of regions with type + bbox              │
│                                                              │
│  3. Per-Region Processing                                    │
│     ├── TEXT region  -> PP-OCRv4 text recognition           │
│     ├── TABLE region -> Table structure recognition         │
│     │                   -> Cell text extraction              │
│     │                   -> Output: HTML <table> or Markdown │
│     ├── TITLE region -> PP-OCRv4 text (marked as heading)   │
│     └── LIST region  -> PP-OCRv4 text (marked as list)      │
│                                                              │
│  4. Postprocessing                                           │
│     - Assemble regions theo reading order                   │
│     - Format output:                                        │
│       * json -> structured JSON (regions, tables, text)     │
│       * md   -> Markdown giu layout                         │
│       * txt  -> fallback plain text                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    │
    v
Upload result qua File Proxy -> MinIO results bucket
    │
    v
User xem ket qua tren Result Viewer (structured view)
```

---

## 3. Worker Logic Chi Tiet

### 3.1 Engine: StructuredExtractHandler

Day la handler moi, ke thua `BaseHandler`, xu ly logic dac thu cua structured extraction.

```
┌─────────────────────────────────────────────────────────────────┐
│                  StructuredExtractHandler                         │
│                                                                  │
│  __init__(use_gpu, lang):                                       │
│     │                                                            │
│     ├── Init PP-StructureV2 (layout + table + ocr)              │
│     │   paddleocr.PPStructure(                                  │
│     │       use_gpu=True,                                       │
│     │       lang=lang,                                          │
│     │       layout=True,          # Enable layout analysis      │
│     │       table=True,           # Enable table recognition    │
│     │       ocr=True,             # Enable OCR for each region  │
│     │       show_log=False                                      │
│     │   )                                                       │
│     │                                                            │
│     └── Warm up model (first inference is slow)                 │
│                                                                  │
│  process(file_content, output_format) -> bytes:                 │
│     │                                                            │
│     ├── [Preprocessing]                                         │
│     │   images = load_images(file_content)  # PDF -> pages      │
│     │                                                            │
│     ├── [Inference - per page]                                  │
│     │   for page in images:                                     │
│     │       regions = self.engine(page)                         │
│     │       # regions = [                                       │
│     │       #   { "type": "text",  "bbox": [...], "res": ...}, │
│     │       #   { "type": "table", "bbox": [...], "res": ...}, │
│     │       #   { "type": "title", "bbox": [...], "res": ...}, │
│     │       # ]                                                 │
│     │       page_result = extract_regions(regions)              │
│     │       all_pages.append(page_result)                       │
│     │                                                            │
│     └── [Postprocessing]                                        │
│         return format_structured_output(all_pages, output_format)│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Preprocessing Module

```
preprocessing.py
│
├── load_images(file_content: bytes) -> List[np.ndarray]
│   │
│   ├── Detect file type (PDF vs Image)
│   ├── PDF: pdf2image.convert_from_bytes() -> list of PIL Images
│   ├── Image: PIL.Image.open()
│   ├── Convert all to RGB
│   └── Return list of numpy arrays
│
├── prepare_image(image: np.ndarray) -> np.ndarray
│   │
│   ├── Ensure RGB format
│   ├── (Optional) Auto-orient via EXIF
│   └── Return cleaned numpy array
│
└── Notes:
    - Reuse pattern tu engines/tesseract/preprocessing.py
    - Them multi-page PDF support (quan trong cho tai lieu dai)
```

### 3.3 Postprocessing Module

```
postprocessing.py
│
├── extract_regions(raw_result) -> PageResult
│   │
│   ├── Parse PaddleOCR PPStructure output
│   ├── For each region:
│   │   ├── "text"  -> { type, bbox, content: str, confidence }
│   │   ├── "table" -> { type, bbox, html: str, cells: [...] }
│   │   ├── "title" -> { type, bbox, content: str, level: int }
│   │   ├── "list"  -> { type, bbox, items: [...] }
│   │   └── "figure"-> { type, bbox, caption: str | null }
│   │
│   └── Sort by reading order (top-to-bottom, left-to-right)
│
├── format_structured_output(pages, output_format) -> bytes
│   │
│   ├── output_format == "json":
│   │   {
│   │     "pages": [
│   │       {
│   │         "page_number": 1,
│   │         "width": 2480, "height": 3508,
│   │         "regions": [
│   │           {
│   │             "type": "title",
│   │             "bbox": [x1, y1, x2, y2],
│   │             "content": "Invoice #12345"
│   │           },
│   │           {
│   │             "type": "table",
│   │             "bbox": [x1, y1, x2, y2],
│   │             "html": "<table>...</table>",
│   │             "cells": [
│   │               { "row": 0, "col": 0, "text": "Item", "is_header": true },
│   │               { "row": 1, "col": 0, "text": "Widget A" }
│   │             ]
│   │           },
│   │           {
│   │             "type": "text",
│   │             "bbox": [x1, y1, x2, y2],
│   │             "content": "Thank you for your purchase.",
│   │             "confidence": 0.95
│   │           }
│   │         ]
│   │       }
│   │     ],
│   │     "summary": {
│   │       "total_pages": 1,
│   │       "total_regions": 3,
│   │       "tables_found": 1,
│   │       "text_blocks": 2
│   │     }
│   │   }
│   │
│   ├── output_format == "md":
│   │   # Invoice #12345
│   │
│   │   | Item     | Qty | Price |
│   │   |----------|-----|-------|
│   │   | Widget A | 2   | $10   |
│   │
│   │   Thank you for your purchase.
│   │
│   └── output_format == "txt":
│       (fallback: plain text, same as text_raw)
│
└── table_to_markdown(html_table: str) -> str
    # Convert HTML table output from PaddleOCR to Markdown table
```

### 3.4 Sequence Diagram: Structured Extract Job

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              SEQUENCE: STRUCTURED EXTRACT JOB                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User       Frontend    Backend     NATS       PaddleOCR-VL    File Proxy  │
│   │            │           │          │          Worker           │         │
│   │            │           │          │            │              │         │
│   │  Upload    │           │          │            │              │         │
│   │  file +   │           │          │            │              │         │
│   │  method=  │           │          │            │              │         │
│   │  structured│          │          │            │              │         │
│   │  _extract │           │          │            │              │         │
│   │───────────>           │          │            │              │         │
│   │            │  POST    │          │            │              │         │
│   │            │ /upload  │          │            │              │         │
│   │            │ method=  │          │            │              │         │
│   │            │ structured│         │            │              │         │
│   │            │ _extract │          │            │              │         │
│   │            │─────────>│          │            │              │         │
│   │            │          │          │            │              │         │
│   │            │          │ Store in │            │              │         │
│   │            │          │ MinIO    │            │              │         │
│   │            │          │          │            │              │         │
│   │            │          │ Publish  │            │              │         │
│   │            │          │ ocr.     │            │              │         │
│   │            │          │ structured│           │              │         │
│   │            │          │ _extract.│            │              │         │
│   │            │          │ tier0    │            │              │         │
│   │            │          │─────────>│            │              │         │
│   │            │          │          │            │              │         │
│   │            │<─────────│          │            │              │         │
│   │<───────────│ req_id   │          │            │              │         │
│   │            │          │          │            │              │         │
│   │            │          │          │  Pull job  │              │         │
│   │            │          │          │<───────────│              │         │
│   │            │          │          │            │              │         │
│   │            │          │          │  PATCH     │              │         │
│   │            │          │          │  PROCESSING│              │         │
│   │            │          │<─────────┼────────────│              │         │
│   │            │          │          │            │              │         │
│   │            │          │          │  Download  │              │         │
│   │            │          │          │  via proxy │              │         │
│   │            │          │          │            │─────────────>│         │
│   │            │          │          │            │<─────────────│         │
│   │            │          │          │            │              │         │
│   │            │          │          │  ┌────────────────────┐   │         │
│   │            │          │          │  │ 1. Layout Analysis │   │         │
│   │            │          │          │  │ 2. Region Extract  │   │         │
│   │            │          │          │  │ 3. Table Recognize │   │         │
│   │            │          │          │  │ 4. OCR per region  │   │         │
│   │            │          │          │  │ 5. Assemble output │   │         │
│   │            │          │          │  └────────────────────┘   │         │
│   │            │          │          │            │              │         │
│   │            │          │          │  Upload    │              │         │
│   │            │          │          │  result    │              │         │
│   │            │          │          │            │─────────────>│         │
│   │            │          │          │            │<─────────────│         │
│   │            │          │          │            │              │         │
│   │            │          │          │  PATCH     │              │         │
│   │            │          │          │  COMPLETED │              │         │
│   │            │          │<─────────┼────────────│              │         │
│   │            │          │          │            │              │         │
│   │  Poll      │          │          │            │              │         │
│   │  status    │          │          │            │              │         │
│   │───────────>│  GET     │          │            │              │         │
│   │            │ /requests│          │            │              │         │
│   │            │ /{id}    │          │            │              │         │
│   │            │─────────>│          │            │              │         │
│   │            │<─────────│          │            │              │         │
│   │<───────────│ COMPLETED│          │            │              │         │
│   │            │          │          │            │              │         │
│   │  View      │          │          │            │              │         │
│   │  result    │          │          │            │              │         │
│   │───────────>│ GET      │          │            │              │         │
│   │            │/jobs/{id}│          │            │              │         │
│   │            │/result   │          │            │              │         │
│   │            │─────────>│          │            │              │         │
│   │            │<─────────│ Structured JSON / Markdown          │         │
│   │<───────────│          │          │            │              │         │
│   │            │          │          │            │              │         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Code Structure

### 4.1 Files can them/sua trong Worker (03_worker/)

```
03_worker/
├── Dockerfile.vl                       # [NEW] GPU Dockerfile cho PaddleOCR-VL
│
├── app/
│   ├── core/
│   │   └── processor.py                # [EDIT] Them ENGINE_PADDLE_VL + handler
│   │
│   └── engines/
│       ├── base.py                      # [NO CHANGE] BaseHandler interface
│       │
│       ├── paddle_text/                 # [NO CHANGE] Existing PaddleOCR text_raw
│       │   ├── __init__.py
│       │   ├── handler.py
│       │   ├── preprocessing.py
│       │   └── postprocessing.py
│       │
│       ├── tesseract/                   # [NO CHANGE] Existing Tesseract text_raw
│       │   ├── __init__.py
│       │   ├── handler.py
│       │   ├── preprocessing.py
│       │   └── postprocessing.py
│       │
│       └── paddle_vl/                   # [NEW] PaddleOCR-VL structured extract
│           ├── __init__.py              # Export StructuredExtractHandler
│           ├── handler.py               # StructuredExtractHandler(BaseHandler)
│           ├── preprocessing.py         # load_images(), prepare_image()
│           └── postprocessing.py        # extract_regions(), format_structured_output()
│
└── deploy/
    └── paddle-vl/                       # [NEW] Deploy config cho PaddleOCR-VL
        ├── docker-compose.yml           # GPU, nvidia runtime
        └── .env.example                 # WORKER_SERVICE_TYPE=ocr-paddle-vl
```

### 4.2 Files can sua trong Backend (02_backend/)

```
02_backend/
└── app/
    ├── infrastructure/database/
    │   ├── models.py                    # [EDIT] ServiceType: them cot supported_output_formats
    │   └── repositories/
    │       └── service_type.py          # [EDIT] register(): luu supported_output_formats
    │
    └── api/v1/
        ├── schemas/
        │   ├── register.py              # [EDIT] ServiceRegistrationRequest: them field
        │   └── upload.py                # [EDIT] Bo Literal constraint cho output_format
        │                                #   -> str (validate dong qua services API)
        │
        ├── internal/
        │   └── register.py              # [EDIT] Truyen supported_output_formats khi register
        │
        └── endpoints/
            └── services.py              # [EDIT] AvailableServiceResponse: tra ve supported_output_formats
```

> **Note:** Khong can sua logic Orchestration layer (Job module, Retry, Heartbeat, File Proxy, NATS subject routing).
> Subject `ocr.structured_extract.tier0` se tu dong duoc route dung nho JetStream wildcard `ocr.>`.
> Worker tu dang ky voi `allowed_methods=["structured_extract"]`.

### 4.3 Files can sua trong Frontend (01_frontend/)

```
01_frontend/
└── src/
    ├── config/
    │   └── index.ts                     # [EDIT] Xoa OUTPUT_FORMATS hardcode
    │
    ├── api/
    │   └── services.ts                  # [EDIT] AvailableService type: them supported_output_formats
    │
    ├── components/
    │   ├── upload/
    │   │   └── UploadConfig.tsx         # [EDIT] Doc output formats tu services API, filter theo method
    │   │
    │   └── result/
    │       └── ExtractedText.tsx         # [EDIT] Render Markdown khi output_format=md
    │
    └── types/
        └── file.ts                      # [EDIT] UploadConfig.output_format: string (khong con Literal)
```

### 4.4 Chi tiet thay doi tung file

#### 4.4.1 `03_worker/app/core/processor.py` (EDIT)

```python
# Them constant va factory branch:

ENGINE_PADDLE = "paddle"
ENGINE_TESSERACT = "tesseract"
ENGINE_PADDLE_VL = "paddle_vl"        # NEW


def create_handler(engine: str, use_gpu: bool, lang: str) -> BaseHandler:
    if engine == ENGINE_TESSERACT:
        from app.engines.tesseract import TextRawTesseractHandler
        return TextRawTesseractHandler(lang=lang)
    elif engine == ENGINE_PADDLE_VL:                                    # NEW
        from app.engines.paddle_vl import StructuredExtractHandler      # NEW
        return StructuredExtractHandler(use_gpu=use_gpu, lang=lang)     # NEW
    else:
        from app.engines.paddle_text import TextRawHandler
        return TextRawHandler(use_gpu=use_gpu, lang=lang)


class OCRProcessor:
    def __init__(self):
        engine = os.getenv("OCR_ENGINE", ENGINE_PADDLE).lower()
        use_gpu = os.getenv("USE_GPU", "true").lower() == "true"
        lang = os.getenv("OCR_LANG", "en")

        if engine == ENGINE_TESSERACT:
            use_gpu = False

        self.handlers = {
            "text_raw": create_handler(engine, use_gpu, lang),
        }

        # Paddle-VL engine registers "structured_extract" method
        if engine == ENGINE_PADDLE_VL:                                  # NEW
            self.handlers["structured_extract"] = self.handlers.pop(    # NEW
                "text_raw",                                             # NEW
                create_handler(engine, use_gpu, lang)                   # NEW
            )                                                           # NEW
```

#### 4.4.2 `03_worker/app/engines/paddle_vl/handler.py` (NEW)

```python
# PaddleOCR-VL structured extraction - Entry point

import logging
from typing import Dict, Any

from paddleocr import PPStructure

from app.engines.base import BaseHandler
from .preprocessing import load_images, prepare_image
from .postprocessing import extract_regions, format_structured_output

logger = logging.getLogger(__name__)

ENGINE_NAME = "paddleocr-vl"
ENGINE_VERSION = "2.7.3"


class StructuredExtractHandler(BaseHandler):
    """OCR handler using PaddleOCR PP-Structure for structured extraction."""

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        self.use_gpu = use_gpu
        self.lang = lang
        logger.info(f"Initializing PaddleOCR-VL (use_gpu={use_gpu}, lang={lang})")

        self.engine = PPStructure(
            use_gpu=use_gpu,
            lang=lang,
            layout=True,
            table=True,
            ocr=True,
            show_log=False,
        )

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "lang": self.lang,
            "use_gpu": self.use_gpu,
            "capabilities": ["layout_analysis", "table_recognition", "text_ocr"],
        }

    async def process(self, file_content: bytes, output_format: str) -> bytes:
        # Preprocessing
        images = load_images(file_content)

        # Inference per page
        all_pages = []
        for page_idx, image in enumerate(images):
            image = prepare_image(image)
            logger.debug(f"Processing page {page_idx + 1}/{len(images)}")

            # PPStructure returns list of region dicts
            raw_regions = self.engine(image)

            page_result = extract_regions(raw_regions, page_idx)
            all_pages.append(page_result)

        # Postprocessing
        return format_structured_output(all_pages, output_format)
```

#### 4.4.3 `03_worker/app/engines/paddle_vl/preprocessing.py` (NEW)

```python
# Image preprocessing for PaddleOCR-VL (multi-page PDF support)

import logging
from io import BytesIO
from typing import List

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


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
    """Prepare image for PPStructure inference."""
    # PPStructure expects RGB numpy array (same as PaddleOCR)
    # Additional preprocessing can be added here (deskew, denoise)
    return image
```

#### 4.4.4 `03_worker/app/engines/paddle_vl/postprocessing.py` (NEW)

```python
# Output extraction and formatting for PaddleOCR-VL structured results

import json
import re
from typing import List, Dict, Any


def extract_regions(raw_result: list, page_idx: int) -> Dict[str, Any]:
    """Extract structured regions from PPStructure output.

    PPStructure output format per region:
    {
        "type": "text" | "table" | "title" | "figure" | "list",
        "bbox": [x1, y1, x2, y2],
        "res": [  # for text/title/list
            { "text": "...", "confidence": 0.95, "text_region": [...] }
        ]
        # or for table:
        "res": {
            "html": "<table>...</table>",
            "cell_bbox": [...]
        }
    }
    """
    regions = []

    if not raw_result:
        return {"page_number": page_idx + 1, "regions": []}

    for item in raw_result:
        region_type = item.get("type", "text")
        bbox = item.get("bbox", [0, 0, 0, 0])

        if region_type == "table":
            table_res = item.get("res", {})
            html = table_res.get("html", "")
            regions.append({
                "type": "table",
                "bbox": bbox,
                "html": html,
                "markdown": html_table_to_markdown(html),
            })

        elif region_type in ("text", "title", "list"):
            res_list = item.get("res", [])
            text_parts = []
            confidence_sum = 0.0
            count = 0

            for text_item in res_list:
                text_parts.append(text_item.get("text", ""))
                confidence_sum += text_item.get("confidence", 0.0)
                count += 1

            content = " ".join(text_parts)
            avg_confidence = confidence_sum / count if count > 0 else 0.0

            regions.append({
                "type": region_type,
                "bbox": bbox,
                "content": content,
                "confidence": round(avg_confidence, 4),
            })

        elif region_type == "figure":
            regions.append({
                "type": "figure",
                "bbox": bbox,
                "caption": None,
            })

    # Sort by reading order: top-to-bottom, then left-to-right
    regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

    return {
        "page_number": page_idx + 1,
        "regions": regions,
    }


def html_table_to_markdown(html: str) -> str:
    """Convert HTML table to Markdown table format."""
    # Basic conversion - extract rows and cells
    rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
    if not rows:
        return ""

    md_rows = []
    for i, row in enumerate(rows):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        cells = [c.strip() for c in cells]
        md_rows.append("| " + " | ".join(cells) + " |")

        # Add separator after header row
        if i == 0:
            md_rows.append("|" + "|".join(["---"] * len(cells)) + "|")

    return "\n".join(md_rows)


def format_structured_output(
    pages: List[Dict[str, Any]],
    output_format: str,
) -> bytes:
    """Format structured results as JSON, Markdown, or plain text."""

    if output_format == "json":
        # Count summary
        total_regions = sum(len(p["regions"]) for p in pages)
        tables_found = sum(
            1 for p in pages for r in p["regions"] if r["type"] == "table"
        )
        text_blocks = sum(
            1 for p in pages for r in p["regions"] if r["type"] in ("text", "title")
        )

        output = {
            "pages": pages,
            "summary": {
                "total_pages": len(pages),
                "total_regions": total_regions,
                "tables_found": tables_found,
                "text_blocks": text_blocks,
            },
        }
        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")

    elif output_format == "md":
        md_parts = []
        for page in pages:
            if len(pages) > 1:
                md_parts.append(f"---\n**Page {page['page_number']}**\n")

            for region in page["regions"]:
                if region["type"] == "title":
                    md_parts.append(f"# {region['content']}\n")
                elif region["type"] == "table":
                    md_parts.append(region.get("markdown", "") + "\n")
                elif region["type"] == "list":
                    md_parts.append(f"- {region['content']}\n")
                elif region["type"] == "text":
                    md_parts.append(region["content"] + "\n")
                elif region["type"] == "figure":
                    md_parts.append("[Figure]\n")

        return "\n".join(md_parts).encode("utf-8")

    else:
        # Fallback: plain text
        text_parts = []
        for page in pages:
            for region in page["regions"]:
                if region["type"] == "table":
                    text_parts.append(region.get("markdown", ""))
                elif "content" in region:
                    text_parts.append(region["content"])
        return "\n".join(text_parts).encode("utf-8")
```

#### 4.4.5 `03_worker/Dockerfile.vl` (NEW)

```dockerfile
# Worker Dockerfile with PaddleOCR-VL (PP-Structure) GPU support
# Base: NVIDIA CUDA 11.8 with cuDNN 8

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

RUN python -m pip install --upgrade pip

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir paddlepaddle-gpu==2.6.1 paddleocr==2.7.3

# PPStructure requires layout model - pre-download
RUN python -c "from paddleocr import PPStructure; PPStructure(use_gpu=False, show_log=False)"

COPY . .

# Environment variables
ENV OCR_ENGINE=paddle_vl
ENV USE_GPU=true
ENV OCR_LANG=en
ENV LOG_LEVEL=INFO
ENV NATS_URL=nats://ocr-nats:4222
ENV FILE_PROXY_URL=http://ocr-backend:8000/api/v1/internal/file-proxy
ENV ORCHESTRATOR_URL=http://ocr-backend:8000/api/v1/internal

CMD ["python", "-m", "app.main"]
```

#### 4.4.6 `03_worker/deploy/paddle-vl/docker-compose.yml` (NEW)

```yaml
# OCR Worker - PaddleOCR-VL (GPU, Structured Extraction)
#
# Usage (from project root):
#   docker-compose -f 03_worker/deploy/paddle-vl/docker-compose.yml up -d

services:
  worker-paddle-vl:
    build:
      context: ../..
      dockerfile: Dockerfile.vl
    env_file:
      - ../../../.env
      - .env
    stop_grace_period: 60s
    networks:
      - ocr-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

networks:
  ocr-network:
    external: true
    name: ocr-network
```

#### 4.4.7 `03_worker/deploy/paddle-vl/.env.example` (NEW)

```env
# PaddleOCR-VL Worker - Specific Config

# Identity
WORKER_SERVICE_TYPE=ocr-paddle-vl
WORKER_DISPLAY_NAME=PaddleOCR-VL (GPU)
WORKER_DESCRIPTION=PaddleOCR Vision-Language structured extraction with GPU acceleration

# Credentials
WORKER_ACCESS_KEY=sk_local_paddle_vl

# Queue routing
WORKER_FILTER_SUBJECT=ocr.structured_extract.tier0

# Capabilities
WORKER_ALLOWED_METHODS=structured_extract
WORKER_ALLOWED_TIERS=0

# OCR Settings
OCR_ENGINE=paddle_vl
USE_GPU=true
OCR_LANG=vie
```

### 4.5 Thay doi Backend

#### `02_backend/app/api/v1/schemas/upload.py` (EDIT)

```python
class UploadConfig(BaseModel):
    output_format: str = "txt"           # CHANGE: bo Literal, validate dong qua services
    retention_hours: int = 168
```

> **Note:** `method` da duoc truyen nhu query param trong `upload.py` endpoint (line 53).
> `output_format` bo Literal constraint vi formats duoc khai bao dong boi workers.
> Validate phia backend (optional): check output_format co trong supported_output_formats cua services co method tuong ung.

### 4.6 Thay doi Frontend (tong quan)

| File | Thay doi |
|------|----------|
| `config/index.ts` | Xoa `OUTPUT_FORMATS` hardcode |
| `services.ts` | Them `supported_output_formats` vao `AvailableService` type |
| `UploadConfig.tsx` | Doc output formats tu services API, filter dong theo method da chon |
| `UploadConfig.tsx` | Auto-reset output_format khi doi method (neu format hien tai khong hop le) |
| `file.ts` (types) | `output_format: string` (khong con `'txt' | 'json'`) |
| `ExtractedText.tsx` | Render Markdown output khi format=md (dung react-markdown) |

### 4.7 Thay doi Makefile

```makefile
# Them target moi:
worker-paddle-vl:
	docker-compose -f 03_worker/deploy/paddle-vl/docker-compose.yml up -d

# Update workers target:
workers: worker-paddle worker-tesseract worker-paddle-vl

# Update workers-down:
workers-down:
	docker-compose -f 03_worker/deploy/paddle-text/docker-compose.yml down
	docker-compose -f 03_worker/deploy/tesseract-cpu/docker-compose.yml down
	docker-compose -f 03_worker/deploy/paddle-vl/docker-compose.yml down
```

---

## 5. Dynamic Output Formats (Backend-Driven)

### 5.1 Van de

Hien tai `OUTPUT_FORMATS` duoc **hardcode** trong frontend (`config/index.ts`):
```typescript
export const OUTPUT_FORMATS = ['txt', 'json'] as const
```

Khi them worker moi voi format khac (md, html), neu chi them vao list nay thi **tat ca format hien thi cho moi method**, ke ca method khong ho tro.

### 5.2 Giai phap: Worker tu khai bao supported_output_formats

Moi worker tu khai bao output formats ma no ho tro khi register.
Frontend doc tu API `/services/available` va filter dong theo method user chon.

**Khong can sua frontend moi khi them worker moi.**

### 5.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│              SUPPORTED OUTPUT FORMATS - DATA FLOW                    │
│                                                                      │
│  Worker .env                                                        │
│  ┌──────────────────────────────────────────────┐                  │
│  │ WORKER_SUPPORTED_FORMATS=json,md             │  # NEW env var   │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  Worker config.py                                                   │
│  ┌──────────────────────────────────────────────┐                  │
│  │ @property                                     │                  │
│  │ def worker_supported_formats(self) -> List:   │  # NEW property │
│  │     formats = os.getenv(                      │                  │
│  │       "WORKER_SUPPORTED_FORMATS", "txt,json") │                  │
│  │     return [f.strip() for f in ...]           │                  │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  Worker orchestrator_client.py register()                           │
│  ┌──────────────────────────────────────────────┐                  │
│  │ payload = {                                   │                  │
│  │   "service_type": "ocr-paddle-vl",           │                  │
│  │   "allowed_methods": ["structured_extract"],  │                  │
│  │   "supported_output_formats": ["json", "md"], │  # NEW field    │
│  │   ...                                         │                  │
│  │ }                                             │                  │
│  └──────────────────────┬───────────────────────┘                  │
│                         │ POST /api/v1/internal/register            │
│                         v                                           │
│  Backend register.py (schema)                                       │
│  ┌──────────────────────────────────────────────┐                  │
│  │ class ServiceRegistrationRequest:             │                  │
│  │   supported_output_formats: List[str]         │  # NEW field    │
│  │     = ["txt", "json"]                         │  # default      │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  Backend models.py - ServiceType                                    │
│  ┌──────────────────────────────────────────────┐                  │
│  │ supported_output_formats: Mapped[str]         │  # NEW column   │
│  │   = mapped_column(Text, default='["txt",     │  # JSON array   │
│  │     "json"]')                                 │                  │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  Backend ServiceTypeRepository.register()                           │
│  ┌──────────────────────────────────────────────┐                  │
│  │ service_type.supported_output_formats =       │  # Save to DB   │
│  │   json.dumps(data.supported_output_formats)   │                  │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  API GET /services/available                                        │
│  ┌──────────────────────────────────────────────┐                  │
│  │ AvailableServiceResponse:                     │                  │
│  │   id: "ocr-paddle-vl"                        │                  │
│  │   allowed_methods: ["structured_extract"]     │                  │
│  │   supported_output_formats: ["json", "md"]    │  # NEW field    │
│  │   active_instances: 1                         │                  │
│  └──────────────────────┬───────────────────────┘                  │
│                         │                                           │
│                         v                                           │
│  Frontend UploadConfig.tsx                                          │
│  ┌──────────────────────────────────────────────┐                  │
│  │ // User chon method = "structured_extract"   │                  │
│  │ // -> Tim services co method nay              │                  │
│  │ // -> Lay union cua supported_output_formats  │                  │
│  │ // -> Hien thi ["json", "md"] trong dropdown  │                  │
│  │                                               │                  │
│  │ // User chon method = "text_raw"              │                  │
│  │ // -> Hien thi ["txt", "json"]                │                  │
│  └──────────────────────────────────────────────┘                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 Thay doi chi tiet theo tung file

#### 5.4.1 Worker: `.env` (them var)

```env
# Tesseract worker:
WORKER_SUPPORTED_FORMATS=txt,json

# PaddleOCR-VL worker:
WORKER_SUPPORTED_FORMATS=json,md
```

#### 5.4.2 Worker: `config.py` (them property)

```python
@property
def worker_supported_formats(self) -> List[str]:
    formats_str = os.getenv("WORKER_SUPPORTED_FORMATS", "txt,json")
    return [f.strip() for f in formats_str.split(",") if f.strip()]
```

#### 5.4.3 Worker: `orchestrator_client.py` (them field trong register payload)

```python
async def register(self, ..., supported_output_formats: List[str] = None) -> dict:
    payload = {
        ...
        "supported_output_formats": supported_output_formats or ["txt", "json"],
    }
```

#### 5.4.4 Worker: `worker.py` (truyen formats khi register)

```python
async def _register(self) -> dict:
    return await self.orchestrator.register(
        ...
        supported_output_formats=settings.worker_supported_formats,   # NEW
    )
```

#### 5.4.5 Backend: `schemas/register.py` (them field)

```python
class ServiceRegistrationRequest(BaseModel):
    ...
    supported_output_formats: List[str] = ["txt", "json"]   # NEW
```

#### 5.4.6 Backend: `models.py` - ServiceType (them column)

```python
class ServiceType(Base):
    ...
    supported_output_formats: Mapped[str] = mapped_column(
        Text, default='["txt","json"]'
    )   # JSON array
```

#### 5.4.7 Backend: `repositories/service_type.py` (luu khi register)

```python
def register(self, ..., supported_output_formats=None) -> ServiceType:
    ...
    service_type.supported_output_formats = json.dumps(
        supported_output_formats or ["txt", "json"]
    )
```

#### 5.4.8 Backend: `endpoints/services.py` (tra ve trong API response)

```python
class AvailableServiceResponse(BaseModel):
    ...
    supported_output_formats: List[str]   # NEW

# Trong handler:
items.append(AvailableServiceResponse(
    ...
    supported_output_formats=json.loads(st.supported_output_formats),
))
```

#### 5.4.9 Backend: `endpoints/upload.py` (validate format vs method) - OPTIONAL

```python
# Optional: validate output_format phu hop voi method
# Bang cach check cac services co method nay co ho tro format do khong
# Neu khong -> 400 Bad Request
```

#### 5.4.10 Frontend: `UploadConfig.tsx` (filter dong)

```typescript
// Thay vi doc tu OUTPUT_FORMATS (hardcode), doc tu services API:
function getFormatsForMethod(services: AvailableService[], method: string): string[] {
  const formats = new Set<string>()
  for (const svc of services) {
    if (svc.allowed_methods.includes(method)) {
      for (const f of svc.supported_output_formats) {
        formats.add(f)
      }
    }
  }
  return formats.size > 0 ? Array.from(formats) : ['txt']  // fallback
}

// Trong component:
const availableFormats = getFormatsForMethod(services, config.method)

// Reset output_format khi user doi method va format hien tai khong con hop le
useEffect(() => {
  if (!availableFormats.includes(config.output_format)) {
    onChange({ ...config, output_format: availableFormats[0] })
  }
}, [config.method])
```

#### 5.4.11 Frontend: xoa hardcode `OUTPUT_FORMATS`

```typescript
// config/index.ts
// XOA:  export const OUTPUT_FORMATS = ['txt', 'json'] as const
// THEM: (khong can, vi da doc tu API)
```

### 5.5 Ket qua

Khi user chon method tren Upload page:

| Method chon | Services match | Output formats hien thi |
|-------------|---------------|------------------------|
| `text_raw` | ocr-tesseract (txt,json), ocr-paddle (txt,json) | **txt, json** |
| `structured_extract` | ocr-paddle-vl (json,md) | **json, md** |
| (tuong lai) `handwriting` | ocr-handwrite (txt,json,pdf) | **txt, json, pdf** |

**Loi ich:**
- Them worker moi -> chi can khai bao env var -> frontend tu dong cap nhat
- Khong can deploy lai frontend khi them worker
- Backend la single source of truth cho supported formats

---

## 6. Cac Thay Doi Khong Can Thuc Hien

Nhung phan **KHONG** can sua nho kien truc hien tai da ho tro:

| Component | Ly do khong can sua |
|-----------|---------------------|
| NATS Stream config | `OCR_JOBS` da subscribe `ocr.>` wildcard, tu dong nhan `ocr.structured_extract.tier0` |
| Job State Machine | Khong thay doi - van la SUBMITTED -> QUEUED -> PROCESSING -> COMPLETED |
| Retry Orchestrator | Van hoat dong nhu cu voi method moi |
| File Proxy | ACL check dua tren `allowed_methods` cua ServiceType, worker tu dang ky |
| Heartbeat | Khong thay doi |
| Worker Registration | Worker tu dang ky voi `allowed_methods=["structured_extract"]` |
| Admin Panel | Admin approve/reject ServiceType `ocr-paddle-vl` nhu binh thuong |
| Database Schema | Chi them 1 cot `supported_output_formats` vao `service_types` (phan 5) |

---

## 6. Checklist Implementation

### Phase 2a: Worker Core (khong can frontend)

- [ ] Tao `03_worker/app/engines/paddle_vl/__init__.py`
- [ ] Tao `03_worker/app/engines/paddle_vl/handler.py` (StructuredExtractHandler)
- [ ] Tao `03_worker/app/engines/paddle_vl/preprocessing.py`
- [ ] Tao `03_worker/app/engines/paddle_vl/postprocessing.py`
- [ ] Edit `03_worker/app/core/processor.py` (them ENGINE_PADDLE_VL)
- [ ] Tao `03_worker/Dockerfile.vl`
- [ ] Tao `03_worker/deploy/paddle-vl/docker-compose.yml`
- [ ] Tao `03_worker/deploy/paddle-vl/.env.example` (copy thanh `.env`)
- [ ] Test worker chay doc lap (manual: gui job qua NATS, kiem tra output)

### Phase 2b: Backend - Dynamic Output Formats

- [ ] Edit `02_backend/app/infrastructure/database/models.py` (them cot `supported_output_formats` vao ServiceType)
- [ ] Edit `02_backend/app/api/v1/schemas/register.py` (them field `supported_output_formats`)
- [ ] Edit `02_backend/app/api/v1/internal/register.py` (truyen supported_output_formats khi register)
- [ ] Edit `02_backend/app/infrastructure/database/repositories/service_type.py` (luu supported_output_formats)
- [ ] Edit `02_backend/app/api/v1/endpoints/services.py` (tra ve supported_output_formats)
- [ ] Edit `02_backend/app/api/v1/schemas/upload.py` (bo Literal constraint cho output_format)
- [ ] Re-create DB (hoac migrate) de them cot moi

### Phase 2c: Worker config - Khai bao formats

- [ ] Edit `03_worker/app/config.py` (them `worker_supported_formats` property)
- [ ] Edit `03_worker/app/clients/orchestrator_client.py` (them field trong register payload)
- [ ] Edit `03_worker/app/core/worker.py` (truyen formats khi register)
- [ ] Edit `03_worker/deploy/tesseract-cpu/.env.example` (them WORKER_SUPPORTED_FORMATS=txt,json)
- [ ] Edit `03_worker/deploy/paddle-text/.env.example` (them WORKER_SUPPORTED_FORMATS=txt,json)
- [ ] Edit `03_worker/deploy/paddle-vl/.env.example` (them WORKER_SUPPORTED_FORMATS=json,md)

### Phase 2d: Frontend - Dynamic Output Format Dropdown

- [ ] Edit `01_frontend/src/config/index.ts` (xoa OUTPUT_FORMATS hardcode)
- [ ] Edit `01_frontend/src/api/services.ts` (them supported_output_formats vao type)
- [ ] Edit `01_frontend/src/components/upload/UploadConfig.tsx` (filter output formats theo method)
- [ ] Edit `01_frontend/src/types/file.ts` (output_format: string)
- [ ] Edit `01_frontend/src/components/result/ExtractedText.tsx` (render Markdown)
- [ ] Edit Makefile (them worker-paddle-vl target)
- [ ] Test E2E: upload -> structured_extract -> view result

### Phase 2c: Testing & Polish

- [ ] Test voi cac loai tai lieu: hoa don, bang bieu, form
- [ ] Test multi-page PDF
- [ ] Test error handling (file khong hop le, timeout)
- [ ] Test admin approval flow cho ServiceType moi
- [ ] Performance benchmark: thoi gian xu ly vs text_raw
