# Hiện trạng xử lý OCR của các Worker

> Tài liệu mô tả chi tiết các bước xử lý mà mỗi engine worker hiện tại **đã implement** và **chưa implement**, đối chiếu với pipeline OCR hoàn chỉnh 6 bước.

## 1. Kiến trúc tổng quan

```
Job (NATS) → OCRWorker.process_job()
               ├── Download file    (FileProxyClient)
               ├── OCRProcessor.process(file_content, output_format, method)
               │     └── Handler.process(file_content, output_format)
               │           ├── preprocessing   → load/convert ảnh
               │           ├── inference        → chạy model OCR
               │           └── postprocessing   → extract + format output
               ├── Upload result    (FileProxyClient)
               └── Report status    (OrchestratorClient)
```

**File liên quan:**

| File | Vai trò |
|---|---|
| `app/core/worker.py` | Vòng lặp poll → download → process → upload |
| `app/core/processor.py` | Factory chọn engine handler theo `OCR_ENGINE` env |
| `app/engines/base.py` | Interface `BaseHandler` (abstract `process()`) |

**3 engine hiện tại:**

| Engine | Env `OCR_ENGINE` | Method đăng ký | Class | GPU |
|---|---|---|---|---|
| PaddleOCR Text | `paddle` (default) | `text_raw` | `TextRawHandler` | Yes |
| PaddleOCR VL | `paddle_vl` | `structured_extract` | `StructuredExtractHandler` | Yes |
| Tesseract | `tesseract` | `text_raw` | `TextRawTesseractHandler` | No |

---

## 2. Chi tiết từng engine

### 2.1. PaddleOCR Text (`paddle`)

**Mục đích:** OCR đơn giản — detect text line + đọc chữ, trả về plain text hoặc JSON.

**Files:**

- `app/engines/paddle_text/handler.py` — entry point
- `app/engines/paddle_text/preprocessing.py` — load ảnh
- `app/engines/paddle_text/postprocessing.py` — extract kết quả + format output

#### Flow xử lý

```
file_content (bytes)
  │
  ▼
[Preprocessing] load_image()
  • Image.open() → convert("RGB") → numpy array
  • Không xử lý gì thêm (không denoise, deskew, resize)
  • Chỉ hỗ trợ ảnh đơn, KHÔNG hỗ trợ PDF
  │
  ▼
[Inference] PaddleOCR.ocr(img_array, cls=True)
  • cls=True: bật angle classifier (xoay 0/180°)
  • Nội bộ PaddleOCR chạy: DB text detection → CRNN recognition
  • Trả về: [[[box], (text, confidence)], ...]
  │
  ▼
[Postprocessing] extract_results() → format_output()
  • Duyệt kết quả, lấy text + confidence (round 4 decimals) + box
  • Join text lines bằng "\n"
  • Không lọc confidence, không spell check, không sắp xếp reading order
  │
  ▼
Output:
  • txt: plain text UTF-8
  • json: {"text", "lines", "details": [{text, confidence, box}]}
```

#### Những gì CHƯA CÓ

- Không hỗ trợ PDF multi-page
- Không có tiền xử lý ảnh (deskew, denoise, contrast, binarization)
- Không có layout analysis (không phân biệt title/paragraph/table)
- Không lọc confidence thấp
- Không spell check / language correction
- Không sắp xếp reading order (phụ thuộc hoàn toàn vào PaddleOCR)

---

### 2.2. PaddleOCR VL (`paddle_vl`)

**Mục đích:** OCR có cấu trúc — phân tích layout tài liệu, nhận diện bảng, xuất Markdown/JSON.

**Files:**

- `app/engines/paddle_vl/handler.py` — entry point
- `app/engines/paddle_vl/preprocessing.py` — load ảnh + PDF multi-page
- `app/engines/paddle_vl/postprocessing.py` — extract regions + format output

#### Flow xử lý

```
file_content (bytes)
  │
  ▼
[Preprocessing] detect_file_type() → load_images()
  • Detect PDF bằng magic bytes (%PDF)
  • PDF: pdf2image.convert_from_bytes(dpi=300), hỗ trợ multi-page
  • Image: Image.open() đơn trang
  • Convert RGB → numpy array
  │
  ▼
  prepare_image()
  • Hiện tại: KHÔNG làm gì, chỉ return image
  • Code có comment TODO: "Additional preprocessing can be added here (deskew, denoise)"
  │
  ▼
[Inference] PPStructure(layout=True, table=True, ocr=True)
  • Xử lý từng page:
    - Layout detection (PP-PicoDet): phân vùng → text, title, list, figure, table
    - Table recognition: trả HTML <table>
    - Text OCR (CRNN): đọc chữ trong từng vùng text/title/list
  │
  ▼
[Postprocessing] extract_regions() → format_structured_output()
  • Xử lý từng region theo type:
    - text/title/list: nối text parts, tính avg confidence
    - table: lấy HTML → convert sang Markdown (regex-based)
    - figure: chỉ ghi nhận bbox, caption = None
  • Sắp xếp reading order: sort theo (bbox[1], bbox[0]) = top→bottom, left→right ✓
  • Không lọc confidence, không spell check
  │
  ▼
Output:
  • json: {"pages": [...], "summary": {total_pages, total_regions, tables_found, text_blocks}}
         Mỗi page chứa regions với type, bbox, content/html/markdown, confidence
  • md:   Title → "# heading", table → Markdown table, list → "- item", figure → "[Figure]"
         Multi-page có separator "---\n**Page N**"
  • txt:  Plain text fallback, tables vẫn render dạng Markdown
```

#### Những gì ĐÃ CÓ (nổi bật so với engine khác)

- Hỗ trợ PDF multi-page (300 DPI)
- Layout analysis: phân biệt text / title / list / table / figure
- Table detection + structure recognition (HTML → Markdown)
- Sắp xếp reading order theo tọa độ
- Output Markdown có cấu trúc

#### Những gì CHƯA CÓ

- Tiền xử lý ảnh (prepare_image() là stub rỗng)
- Không lọc confidence thấp
- Không spell check / language correction
- Không key-value extraction, NER, document classification
- HTML→Markdown conversion chỉ dùng regex đơn giản (có thể lỗi với bảng phức tạp, colspan/rowspan)

---

### 2.3. Tesseract (`tesseract`)

**Mục đích:** OCR text cơ bản, chạy CPU, không cần GPU. Hỗ trợ nhiều ngôn ngữ.

**Files:**

- `app/engines/tesseract/handler.py` — entry point + language mapping
- `app/engines/tesseract/preprocessing.py` — load ảnh + PDF
- `app/engines/tesseract/postprocessing.py` — extract kết quả + format output

#### Flow xử lý

```
file_content (bytes)
  │
  ▼
[Preprocessing] is_pdf() → load_images()
  • PDF: convert_from_bytes(dpi=200), multi-page
  • Image: Image.open() đơn trang
  │
  ▼
  prepare_image()
  • Cho phép mode "RGB" và "L" (grayscale) đi qua
  • Các mode khác (RGBA, P, CMYK...): convert sang "RGB"
  • Không denoise, deskew, contrast, resize
  │
  ▼
[Inference] Xử lý từng page:
  • Nếu output_format == "json":
      pytesseract.image_to_data() → trả dict với text, conf, left, top, width, height, line_num per word
  • Nếu output_format == "txt":
      pytesseract.image_to_string() → trả plain text
  • Tesseract tự động chạy PSM 3 (full page segmentation) + nội bộ Otsu binarization
  │
  ▼
[Postprocessing]
  • extract_detailed() (cho JSON):
    - Lọc bỏ text rỗng và conf < 0 (invalid tokens từ Tesseract)
    - Group words theo line_num → flush thành line
    - _flush_line(): nối words thành line text, tính avg confidence (chia 100 vì Tesseract dùng thang 0-100)
    - Tạo 4-corner box từ (left, top, width, height) cho mỗi word
  • extract_plain() (cho TXT):
    - Split text theo "\n", strip blank lines
  │
  ▼
Output:
  • txt: plain text UTF-8
  • json: {"text", "lines", "pages", "details": [{text, confidence, box}]}
```

#### Language mapping

```python
LANG_MAP = {
    "en": "eng", "vi": "vie", "ch": "chi_sim",
    "japan": "jpn", "korean": "kor", "fr": "fra", "de": "deu"
}
```

#### Những gì CHƯA CÓ

- Tiền xử lý ảnh chỉ convert color mode, không có denoise/deskew/contrast
- PDF convert ở 200 DPI (thấp hơn paddle_vl là 300 DPI)
- Không có layout analysis (phụ thuộc Tesseract PSM 3)
- Không detect/xử lý table
- Không spell check / language correction
- Không sắp xếp reading order (phụ thuộc Tesseract)
- Confidence filter chỉ lọc `conf < 0` (token invalid), không filter ngưỡng thực sự

---

## 3. Bảng so sánh tổng hợp

### 3.1. Bước 1 — Tiền xử lý ảnh (Image Preprocessing)

| Kỹ thuật | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Load ảnh + convert RGB | ✅ | ✅ | ✅ | Cả 3 đều có |
| Hỗ trợ PDF multi-page | ❌ | ✅ 300dpi | ✅ 200dpi | paddle chỉ xử lý ảnh đơn |
| Grayscale conversion | ❌ | ❌ | Cho qua L-mode | Không chủ động convert |
| Binarization (Otsu/adaptive) | ❌ | ❌ | ❌ | Chỉ xảy ra nội bộ thư viện |
| Denoising (Gaussian/median) | ❌ | ❌ | ❌ | Chưa implement |
| Deskew (chỉnh nghiêng) | ❌ | ❌ | ❌ | Chưa implement |
| Contrast adjustment (CLAHE) | ❌ | ❌ | ❌ | Chưa implement |
| Resize / Rescale | ❌ | ❌ | ❌ | Chưa implement |

**Đánh giá:** Tiền xử lý ảnh **rất yếu** ở cả 3 engine. Chỉ làm normalize format (RGB). Tất cả preprocessing thực sự (binarization, deskew) đều phụ thuộc vào xử lý nội bộ của thư viện OCR, không thể kiểm soát hay tùy chỉnh.

### 3.2. Bước 2 — Phát hiện vùng văn bản (Text Detection / Layout Analysis)

| Kỹ thuật | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Text line detection | ✅ DB model | ✅ PP-PicoDet | ✅ PSM 3 auto | Cả 3 đều detect line |
| Angle correction (xoay) | ✅ cls=True (0/180°) | ✅ nội bộ | ❌ | Tesseract không xoay |
| Document layout analysis | ❌ | ✅ | ❌ | Chỉ paddle_vl phân biệt vùng |
| Phân loại vùng (title/text/list/figure) | ❌ | ✅ | ❌ | Chỉ paddle_vl |
| Table detection | ❌ | ✅ | ❌ | Chỉ paddle_vl |
| Table structure recognition | ❌ | ✅ HTML output | ❌ | Chỉ paddle_vl |
| Word/char segmentation | ❌ | ❌ | Nội bộ | Không engine nào expose |

**Đánh giá:** Chỉ **paddle_vl** có layout analysis thực sự. Hai engine còn lại chỉ detect text line mà không hiểu cấu trúc tài liệu.

### 3.3. Bước 3 — Nhận dạng ký tự (Text Recognition)

| Kỹ thuật | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Line-level OCR | ✅ CRNN | ✅ CRNN per region | ✅ Tesseract LSTM | Core feature, cả 3 đều có |
| Table cell OCR | ❌ | ✅ | ❌ | Chỉ paddle_vl |
| Confidence score per line | ✅ | ✅ avg per region | ✅ avg per line | Cả 3 trả confidence |

**Đánh giá:** Đây là chức năng **core** và cả 3 engine đều đã implement. paddle_vl nổi bật với khả năng đọc nội dung trong table cell.

### 3.4. Bước 4 — Hậu xử lý (Post-processing)

| Kỹ thuật | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Confidence thresholding | ❌ | ❌ | Chỉ lọc `< 0` | Không có ngưỡng lọc thực sự |
| Reading order assembly | ❌ | ✅ sort (y, x) | ❌ | Chỉ paddle_vl sắp xếp |
| Spell checking | ❌ | ❌ | ❌ | Hoàn toàn chưa có |
| Language model correction | ❌ | ❌ | ❌ | Hoàn toàn chưa có |
| Regex normalization (ngày, SĐT) | ❌ | ❌ | ❌ | Chưa implement |
| HTML → Markdown (table) | ❌ | ✅ regex-based | ❌ | Chỉ paddle_vl |

**Đánh giá:** Hậu xử lý **rất thiếu**. Không engine nào có spell check hay language correction — đây là gap lớn nhất ảnh hưởng đến chất lượng kết quả, đặc biệt với tiếng Việt.

### 3.5. Bước 5 — Trích xuất thông tin có cấu trúc (Information Extraction)

| Kỹ thuật | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Key-Value extraction | ❌ | ❌ | ❌ | Chưa implement |
| NER (tên, địa chỉ, số tiền) | ❌ | ❌ | ❌ | Chưa implement |
| Document classification | ❌ | Gián tiếp (region type) | ❌ | paddle_vl chỉ phân loại vùng, không phân loại tài liệu |

**Đánh giá:** Bước này **hoàn toàn chưa được implement**. Nếu có nhu cầu trích xuất thông tin (CMND, hóa đơn, hợp đồng...) thì đây là phần cần phát triển thêm.

### 3.6. Bước 6 — Xuất kết quả (Output Formatting)

| Format | paddle | paddle_vl | tesseract | Ghi chú |
|---|:---:|:---:|:---:|---|
| Plain text (txt) | ✅ | ✅ | ✅ | Cả 3 |
| JSON (bbox + confidence) | ✅ | ✅ full structured | ✅ + page count | Cả 3 |
| Markdown | ❌ | ✅ | ❌ | Chỉ paddle_vl |
| Searchable PDF | ❌ | ❌ | ❌ | Chưa implement |

**Đánh giá:** Output cơ bản đã đủ cho hầu hết use case. Thiếu searchable PDF nếu cần.

---

## 4. Tóm tắt gap analysis

| Bước pipeline | Mức độ | Gap chính |
|---|---|---|
| 1. Tiền xử lý ảnh | 🔴 Rất yếu | Không có deskew, denoise, contrast. Phụ thuộc hoàn toàn vào thư viện nội bộ |
| 2. Text Detection / Layout | 🟡 Trung bình | paddle_vl tốt, 2 engine còn lại chỉ detect line, không hiểu layout |
| 3. Text Recognition | 🟢 Đã có | Core feature hoạt động ở cả 3 engine |
| 4. Hậu xử lý | 🔴 Rất yếu | Không spell check, không confidence filter, không language correction |
| 5. Information Extraction | 🔴 Chưa có | Không KV extraction, không NER, không doc classification |
| 6. Output Formatting | 🟡 Trung bình | Có txt/json/md, thiếu searchable PDF |

---

## 5. Reference: Cấu trúc source code

```
03_worker/app/
├── core/
│   ├── worker.py              # Main loop: poll → download → process → upload
│   ├── processor.py           # Engine factory (OCR_ENGINE env → Handler)
│   ├── shutdown.py            # Graceful shutdown handler
│   └── state.py               # Worker state tracking
├── engines/
│   ├── base.py                # BaseHandler interface
│   ├── paddle_text/
│   │   ├── handler.py         # TextRawHandler (PaddleOCR)
│   │   ├── preprocessing.py   # load_image() → RGB numpy
│   │   └── postprocessing.py  # extract_results() + format_output()
│   ├── paddle_vl/
│   │   ├── handler.py         # StructuredExtractHandler (PPStructure)
│   │   ├── preprocessing.py   # detect_file_type() + load_images() + prepare_image()
│   │   └── postprocessing.py  # extract_regions() + html_table_to_markdown() + format_structured_output()
│   └── tesseract/
│       ├── handler.py         # TextRawTesseractHandler (pytesseract)
│       ├── preprocessing.py   # is_pdf() + pdf_to_images() + load_images() + prepare_image()
│       └── postprocessing.py  # extract_detailed() + extract_plain() + _flush_line() + format_output()
├── clients/                   # HTTP clients (orchestrator, file proxy, queue, heartbeat)
├── config.py                  # Settings from env
└── utils/                     # Shared utilities
```
