# Sequence Diagram — Tesseract Worker (TextRawTesseractHandler)

> Engine: `tesseract` | Method: `ocr_text_raw` | GPU: No (CPU only)

## Tổng quan

Worker sử dụng Tesseract OCR (pytesseract) để trích xuất text. Hỗ trợ cả ảnh đơn và PDF nhiều trang. Chạy hoàn toàn trên CPU.

## Sequence Diagram

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Main as main.py
    participant Worker as OCRWorker
    participant Queue as QueueClient<br/>(NATS JetStream)
    participant State as WorkerState
    participant Orch as OrchestratorClient<br/>(Backend API)
    participant FP as FileProxyClient<br/>(Backend API)
    participant Proc as OCRProcessor
    participant Handler as TextRawTesseractHandler
    participant Pre as preprocessing.py
    participant Tess as Tesseract Engine<br/>(pytesseract)
    participant Post as postprocessing.py

    Note over Main,Post: ===== PHASE 1: WORKER STARTUP =====

    Main->>Worker: OCRWorker(shutdown_handler)
    Worker->>Proc: OCRProcessor()
    Proc->>Handler: TextRawTesseractHandler(lang="en")
    Handler->>Handler: Detect tesseract path<br/>(Windows auto-detect hoặc TESSERACT_CMD)
    Handler->>Handler: Map language: "en"→"eng", "vi"→"vie", "ch"→"chi_sim"
    Handler-->>Proc: handler ready (CPU only)

    Worker->>Orch: POST /register<br/>{service_type, allowed_methods: ["ocr_text_raw"], engine_info}
    Orch-->>Worker: {type_status: "APPROVED", access_key: "xxx"}
    Worker->>Queue: connect() → NATS JetStream<br/>stream="OCR_JOBS", subject="ocr.ocr_text_raw.tier0"
    Worker->>Worker: heartbeat.start() (mỗi 30s)

    Note over Main,Post: ===== PHASE 2: JOB POLLING & NHẬN VIỆC =====

    loop Mỗi vòng lặp (while not shutdown)
        Worker->>Queue: pull_job(timeout=5s)
        Queue-->>Worker: job = {job_id, file_id, method: "ocr_text_raw", output_format}
    end

    Note over Main,Post: ===== PHASE 3: XỬ LÝ JOB =====

    Worker->>State: start_job(job_id)
    Worker->>Orch: PATCH /jobs/{job_id}/status {status: "PROCESSING"}

    Note over Worker,FP: 3a. Download file

    Worker->>FP: POST /file-proxy/download {job_id, file_id}
    FP-->>Worker: file_bytes + headers (X-Content-Type, X-File-Name)

    Note over Worker,Post: 3b. OCR Processing

    Worker->>Proc: process(file_bytes, output_format, "ocr_text_raw")
    Proc->>Handler: process(file_bytes, output_format)

    Note over Handler,Post: --- Preprocessing: Phát hiện loại file ---
    Handler->>Pre: load_images(file_bytes)

    alt File là PDF
        Pre->>Pre: Detect PDF header (b"%PDF")
        Pre->>Pre: pdf2image.convert_from_bytes(file_bytes, dpi=300)
        Pre->>Pre: Tạo list images từ mỗi trang PDF
        Pre-->>Handler: images = [(page_1_img, 1), (page_2_img, 2), ...]
    else File là ảnh đơn
        Pre->>Pre: PIL.Image.open(BytesIO(file_bytes))
        Pre->>Pre: prepare_image() → convert RGB hoặc L
        Pre-->>Handler: images = [(image, None)]
    end

    Note over Handler,Post: --- Inference: Xử lý từng trang ---

    loop Với mỗi (image, page_num) trong images
        Handler->>Pre: prepare_image(image)
        Pre->>Pre: Convert sang RGB hoặc Grayscale (L)
        Pre-->>Handler: prepared_image

        alt output_format == "json" (cần bounding box)
            Handler->>Post: extract_detailed(prepared_image, lang="eng")
            Post->>Tess: pytesseract.image_to_data(image, lang, output_type=DICT)
            Note right of Tess: Tesseract trả về:<br/>text[], conf[], left[], top[],<br/>width[], height[] cho mỗi word
            Tess-->>Post: data_dict
            Post->>Post: Filter: chỉ lấy text có conf > 0 và text.strip() != ""
            Post->>Post: Group words thành lines (theo line_num)
            Post->>Post: Tính bounding box cho mỗi line
            Post->>Post: Tính confidence trung bình mỗi line (0-100 scale)
            Post-->>Handler: lines = [{text, confidence, box: [x,y,w,h]}]
        else output_format == "txt" (chỉ cần text)
            Handler->>Post: extract_plain(prepared_image, lang="eng")
            Post->>Tess: pytesseract.image_to_string(image, lang)
            Tess-->>Post: raw_text
            Post->>Post: text.strip()
            Post-->>Handler: plain_text
        end

        Handler->>Handler: Lưu kết quả vào all_results[]<br/>(kèm page_num nếu multi-page)
    end

    Note over Handler,Post: --- Postprocessing: Format output ---
    Handler->>Post: format_output(all_results, output_format)

    alt output_format == "json"
        Post->>Post: Tạo JSON structure
        Note right of Post: Single page: {full_text, lines[]}<br/>Multi page: {pages: [{page, full_text, lines[]}], full_text}
        Post-->>Handler: json_bytes
    else output_format == "txt"
        alt Multi-page
            Post->>Post: Join với "--- Page X ---" separator
        else Single page
            Post->>Post: Plain text
        end
        Post-->>Handler: text_bytes
    end

    Handler-->>Proc: result_bytes
    Proc-->>Worker: result_bytes

    Note over Worker,FP: 3c. Upload kết quả

    Worker->>FP: POST /file-proxy/upload<br/>{job_id, file_id, content: base64(result), content_type}
    FP-->>Worker: {result_key: "results/..."}

    Note over Worker,Orch: 3d. Cập nhật trạng thái

    Worker->>Orch: PATCH /jobs/{job_id}/status<br/>{status: "COMPLETED", engine_version: "tesseract 5.x"}
    Worker->>Queue: ack(msg_id)
    Worker->>State: end_job()

    Note over Main,Post: ===== ERROR HANDLING =====

    rect
        alt RetriableError
            Worker->>Orch: PATCH status {FAILED, retriable: true}
            Worker->>Queue: nak(msg_id, delay=5s)
        else PermanentError (PDF lỗi, ảnh không đọc được)
            Worker->>Orch: PATCH status {FAILED, retriable: false}
            Worker->>Queue: term(msg_id)
        end
        Worker->>State: record_error()
    end

    Note over Main,Post: ===== HEARTBEAT (song song) =====

    loop Mỗi 30 giây
        Worker->>Orch: POST /heartbeat {instance_id, status, current_job_id, ...}
        Orch-->>Worker: {action: "continue" | "drain" | "shutdown"}
    end
```

## Chi tiết: Xử lý Multi-page PDF

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Handler as TextRawTesseractHandler
    participant Pre as preprocessing.py
    participant Tess as Tesseract
    participant Post as postprocessing.py

    Note over Handler,Post: PDF 3 trang

    Handler->>Pre: load_images(pdf_bytes)
    Pre->>Pre: Detect PDF header → pdf2image.convert_from_bytes(dpi=300)
    Pre-->>Handler: [(img_page1, 1), (img_page2, 2), (img_page3, 3)]

    Handler->>Tess: OCR page 1
    Tess-->>Handler: result_page_1

    Handler->>Tess: OCR page 2
    Tess-->>Handler: result_page_2

    Handler->>Tess: OCR page 3
    Tess-->>Handler: result_page_3

    Handler->>Post: format_output([result_1, result_2, result_3], "json")

    Note right of Post: JSON output cho multi-page:
    Post-->>Handler: {"pages": [<br/>  {"page": 1, "full_text": "...", "lines": [...]},<br/>  {"page": 2, "full_text": "...", "lines": [...]},<br/>  {"page": 3, "full_text": "...", "lines": [...]}<br/>], "full_text": "all pages combined"}
```

## Chi tiết Data Flow

### Input
| Field | Type | Mô tả |
|-------|------|--------|
| `file_bytes` | `bytes` | Ảnh (PNG, JPG, TIFF) hoặc PDF |
| `output_format` | `str` | `"json"` hoặc `"txt"` |

### Language Mapping
| Input | Tesseract Code |
|-------|---------------|
| `en` | `eng` |
| `vi` | `vie` |
| `ch` | `chi_sim` |
| `ja` | `jpn` |
| `ko` | `kor` |

### Output (JSON - Single Page)
```json
{
  "full_text": "Toàn bộ text",
  "lines": [
    {
      "text": "Dòng text",
      "confidence": 85.5,
      "box": [x, y, width, height]
    }
  ]
}
```

### Output (JSON - Multi Page)
```json
{
  "pages": [
    {
      "page": 1,
      "full_text": "Text trang 1",
      "lines": [{"text": "...", "confidence": 90.2, "box": [x,y,w,h]}]
    },
    {
      "page": 2,
      "full_text": "Text trang 2",
      "lines": [...]
    }
  ],
  "full_text": "Tổng hợp tất cả trang"
}
```

### Output (TXT - Multi Page)
```
--- Page 1 ---
Nội dung trang 1

--- Page 2 ---
Nội dung trang 2
```

## Error Classification

| Exception | Loại | Hành động |
|-----------|------|-----------|
| `ConnectionError`, `TimeoutError` | Retriable | NAK + retry 5s |
| `DownloadError`, `UploadError` | Retriable | NAK + retry 5s |
| `PDFSyntaxError` | Permanent | TERM |
| `UnidentifiedImageError` | Permanent | TERM |
| `TesseractNotFoundError` | Permanent | TERM |

## So sánh với PaddleText

| Tiêu chí | Tesseract | PaddleText |
|-----------|-----------|------------|
| GPU | Không | Có |
| Multi-page PDF | Có | Không |
| Confidence scale | 0-100 | 0.0-1.0 |
| Box format | `[x, y, w, h]` | `[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]` |
| Tốc độ | Chậm hơn | Nhanh hơn (GPU) |
