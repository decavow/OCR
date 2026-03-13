# Sequence Diagram — PaddleVL Worker (StructuredExtractHandler)

> Engine: `paddle_vl` | Method: `structured_extract` | GPU: Yes (có CPU fallback)

## Tổng quan

Worker sử dụng PaddlePaddle PPStructure để phân tích layout tài liệu và trích xuất cấu trúc (text, title, table, list, figure). Có **fallback chain 4 cấp** khi engine chính thất bại.

## Sequence Diagram chính

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
    participant Handler as StructuredExtractHandler
    participant Pre as preprocessing.py
    participant PPStruct as PPStructure Engine
    participant Post as postprocessing.py

    Note over Main,Post: ===== PHASE 1: WORKER STARTUP =====

    Main->>Worker: OCRWorker(shutdown_handler)
    Worker->>Proc: OCRProcessor()
    Note right of Proc: OCR_ENGINE="paddle_vl"
    Proc->>Handler: StructuredExtractHandler(use_gpu, lang)

    Handler->>PPStruct: PPStructure(table=True, use_gpu=True, lang="en")
    Note right of PPStruct: Engine chính: layout analysis + table recognition
    PPStruct-->>Handler: primary engine ready

    Note right of Handler: Fallback engines được lazy-init<br/>(chỉ khởi tạo khi cần)

    Worker->>Orch: POST /register<br/>{service_type, allowed_methods: ["structured_extract"],<br/>engine_info, supported_output_formats: ["json","md","txt"]}
    Orch-->>Worker: {type_status: "APPROVED", access_key}
    Worker->>Queue: connect() → NATS JetStream<br/>stream="OCR_JOBS", subject filter
    Worker->>Worker: heartbeat.start()

    Note over Main,Post: ===== PHASE 2: NHẬN JOB =====

    Worker->>Queue: pull_job(timeout=5s)
    Queue-->>Worker: job = {job_id, file_id, method: "structured_extract", output_format: "json"}

    Note over Main,Post: ===== PHASE 3: XỬ LÝ JOB =====

    Worker->>State: start_job(job_id)
    Worker->>Orch: PATCH /jobs/{job_id}/status {status: "PROCESSING"}
    Worker->>FP: POST /file-proxy/download {job_id, file_id}
    FP-->>Worker: file_bytes

    Worker->>Proc: process(file_bytes, "json", "structured_extract")
    Proc->>Handler: process(file_bytes, "json")

    Note over Handler,Post: --- Preprocessing: Load & Upscale ---

    Handler->>Pre: load_images(file_bytes)
    alt File là PDF
        Pre->>Pre: pdf2image.convert_from_bytes(dpi=300)
        Pre->>Pre: Với mỗi trang: upscale nếu cần
        Note right of Pre: MIN_SHORT_SIDE = 1500<br/>MAX_LONG_SIDE = 4000<br/>Resize để đảm bảo chất lượng OCR
        Pre-->>Handler: images = [(np_array_page1, 1), (np_array_page2, 2), ...]
    else File là ảnh
        Pre->>Pre: PIL.Image.open() → RGB
        Pre->>Pre: Upscale nếu short_side < 1500
        Pre->>Pre: np.array(image)
        Pre-->>Handler: images = [(np_array, None)]
    end

    Note over Handler,Post: --- Inference: Xử lý từng trang ---

    loop Với mỗi (image, page_num)
        Handler->>Handler: _process_single_image(image)

        Note over Handler,PPStruct: Thử engine chính (PPStructure + table)
        Handler->>PPStruct: engine(image)
        PPStruct-->>Handler: raw_result = [{type, bbox, res, ...}, ...]

        Handler->>Post: extract_regions(raw_result)
        Post->>Post: Parse từng region:
        Note right of Post: type="text" → extract text content<br/>type="title" → extract title<br/>type="table" → convert HTML to Markdown<br/>type="list" → extract list items<br/>type="figure" → mark as figure region
        Post-->>Handler: regions = [{type, bbox, content, confidence}, ...]

        Handler->>Post: assess_result_quality(regions)
        Post->>Post: Kiểm tra: có regions? confidence đủ cao?

        alt Chất lượng ĐẠT
            Post-->>Handler: quality = "good"
            Handler->>Handler: Lưu kết quả trang này
        else Chất lượng KHÔNG ĐẠT → Fallback Chain
            Post-->>Handler: quality = "poor"
            Note over Handler,PPStruct: Xem Fallback Chain diagram bên dưới
        end
    end

    Note over Handler,Post: --- Postprocessing: Format output ---

    Handler->>Post: format_output(all_page_results, "json")
    alt output_format == "json"
        Post->>Post: JSON đầy đủ với regions, types, bboxes
        Post-->>Handler: json_bytes
    else output_format == "md"
        Post->>Post: Markdown: # titles, paragraphs, | tables |
        Post-->>Handler: md_bytes
    else output_format == "txt"
        Post->>Post: Plain text, bỏ metadata
        Post-->>Handler: text_bytes
    end

    Handler-->>Proc: result_bytes
    Proc-->>Worker: result_bytes

    Worker->>FP: POST /file-proxy/upload {job_id, file_id, base64(result)}
    FP-->>Worker: {result_key}
    Worker->>Orch: PATCH /jobs/{job_id}/status {status: "COMPLETED", engine_version}
    Worker->>Queue: ack(msg_id)
    Worker->>State: end_job()
```

## Fallback Chain (Chi tiết)

Đây là cơ chế quan trọng nhất của `paddle_vl` — khi engine chính cho kết quả kém, tự động thử engine đơn giản hơn.

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Handler as StructuredExtractHandler
    participant Engine1 as PPStructure<br/>(table=True, GPU)
    participant Engine2 as PPStructure<br/>(table=False, GPU)
    participant Engine3 as PaddleOCR<br/>(GPU)
    participant Engine4 as PaddleOCR<br/>(CPU)
    participant Post as postprocessing.py

    Note over Handler,Post: Fallback Chain — thử lần lượt cho đến khi đạt chất lượng

    rect
        Note over Handler,Engine1: Level 1: Full PPStructure (table + layout)
        Handler->>Engine1: engine(image)
        Engine1-->>Handler: result
        Handler->>Post: assess_result_quality(result)
        alt Chất lượng OK
            Post-->>Handler: ✅ Dùng kết quả này
        else Kết quả kém / lỗi
            Post-->>Handler: ❌ Thử level tiếp theo
        end
    end

    rect
        Note over Handler,Engine2: Level 2: PPStructure (layout only, không table)
        Handler->>Handler: Lazy init: PPStructure(table=False, use_gpu=True)
        Handler->>Engine2: engine(image)
        Engine2-->>Handler: result
        Handler->>Post: assess_result_quality(result)
        alt Chất lượng OK
            Post-->>Handler: ✅ Dùng kết quả này
        else Kết quả kém / lỗi
            Post-->>Handler: ❌ Thử level tiếp theo
        end
    end

    rect
        Note over Handler,Engine3: Level 3: Pure OCR (PaddleOCR GPU)
        Handler->>Handler: Lazy init: PaddleOCR(use_gpu=True)
        Handler->>Engine3: ocr(image)
        Engine3-->>Handler: ocr_result
        Handler->>Handler: Wrap thành regions format
        alt Có kết quả
            Handler->>Handler: ✅ Dùng kết quả này
        else Vẫn lỗi
            Handler->>Handler: ❌ Thử level cuối
        end
    end

    rect
        Note over Handler,Engine4: Level 4: Pure OCR (PaddleOCR CPU) — Last resort
        Handler->>Handler: Lazy init: PaddleOCR(use_gpu=False)
        Handler->>Engine4: ocr(image)
        Engine4-->>Handler: ocr_result
        alt Có kết quả
            Handler->>Handler: ✅ Dùng kết quả này (CPU fallback)
        else Hoàn toàn thất bại
            Handler->>Handler: ❌ Raise PermanentError
        end
    end
```

## Table Processing Detail

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant PPStruct as PPStructure
    participant Post as postprocessing.py
    participant Conv as html_table_to_markdown()

    PPStruct-->>Post: region = {type: "table", res: {html: "<table>...</table>"}}

    Post->>Post: Kiểm tra region.res.html tồn tại?

    alt Có HTML table
        Post->>Conv: html_table_to_markdown(html_string)
        Conv->>Conv: Parse HTML table structure
        Conv->>Conv: Extract headers + rows
        Conv->>Conv: Format: | col1 | col2 |
        Conv->>Conv: Add separator: |---|---|
        alt Parse thành công
            Conv-->>Post: markdown_table
        else HTML không hợp lệ
            Conv-->>Post: Fallback → plain text từ cells
        end
    else Không có HTML
        Post->>Post: Lấy text content trực tiếp
    end

    Post-->>Post: region = {type: "table", content: markdown_or_text, confidence}
```

## Chi tiết Data Flow

### Input
| Field | Type | Mô tả |
|-------|------|--------|
| `file_bytes` | `bytes` | Ảnh hoặc PDF |
| `output_format` | `str` | `"json"`, `"md"`, hoặc `"txt"` |

### Image Preprocessing Parameters
| Parameter | Giá trị | Mô tả |
|-----------|---------|--------|
| `MIN_SHORT_SIDE` | 1500 | Cạnh ngắn tối thiểu (upscale nếu nhỏ hơn) |
| `MAX_LONG_SIDE` | 4000 | Cạnh dài tối đa (downscale nếu lớn hơn) |
| PDF DPI | 300 | Resolution khi convert PDF sang ảnh |

### Region Types
| Type | Mô tả | Content Format |
|------|--------|---------------|
| `text` | Đoạn văn bản | Plain text |
| `title` | Tiêu đề | Plain text |
| `table` | Bảng | Markdown table hoặc HTML |
| `list` | Danh sách | Text với bullet points |
| `figure` | Hình ảnh/biểu đồ | `[Figure region]` placeholder |

### Output (JSON)
```json
{
  "pages": [
    {
      "page": 1,
      "regions": [
        {
          "type": "title",
          "content": "Tiêu đề tài liệu",
          "confidence": 0.95,
          "bbox": [x1, y1, x2, y2]
        },
        {
          "type": "text",
          "content": "Nội dung đoạn văn...",
          "confidence": 0.92,
          "bbox": [x1, y1, x2, y2]
        },
        {
          "type": "table",
          "content": "| Col1 | Col2 |\n|---|---|\n| val1 | val2 |",
          "confidence": 0.88,
          "bbox": [x1, y1, x2, y2]
        }
      ],
      "full_text": "Tổng hợp text trang 1"
    }
  ],
  "full_text": "Tổng hợp tất cả trang"
}
```

### Output (Markdown)
```markdown
# Tiêu đề tài liệu

Nội dung đoạn văn...

| Col1 | Col2 |
|---|---|
| val1 | val2 |
```

### Output (TXT)
```
Tiêu đề tài liệu
Nội dung đoạn văn...
Col1  Col2
val1  val2
```

## Fallback Chain Summary

| Level | Engine | GPU | Table Support | Khi nào dùng |
|:-----:|--------|:---:|:---:|--------------|
| 1 | PPStructure(table=True) | ✅ | ✅ | Mặc định — đầy đủ nhất |
| 2 | PPStructure(table=False) | ✅ | ❌ | Table engine lỗi |
| 3 | PaddleOCR | ✅ | ❌ | Layout analysis lỗi |
| 4 | PaddleOCR | ❌ | ❌ | GPU lỗi hoàn toàn |

## Error Classification

| Exception | Loại | Hành động |
|-----------|------|-----------|
| `ConnectionError`, `TimeoutError` | Retriable | NAK + retry 5s |
| `DownloadError`, `UploadError` | Retriable | NAK + retry 5s |
| `InvalidImageError` | Permanent | TERM |
| `PDFSyntaxError` | Permanent | TERM |
| Tất cả 4 fallback levels fail | Permanent | TERM |

## So sánh với các engine khác

| Tiêu chí | paddle_vl | paddle_text | tesseract |
|-----------|-----------|-------------|-----------|
| Method | `structured_extract` | `ocr_text_raw` | `ocr_text_raw` |
| Layout Analysis | ✅ | ❌ | ❌ |
| Table Recognition | ✅ (HTML→MD) | ❌ | ❌ |
| Multi-page PDF | ✅ | ❌ | ✅ |
| Fallback Chain | 4 levels | Không | Không |
| Output formats | json, md, txt | json, txt | json, txt |
| GPU required | Có (fallback CPU) | Có | Không |
| Image upscaling | ✅ (1500-4000px) | ❌ | ❌ |
| Phù hợp cho | Tài liệu phức tạp, bảng, form | Text đơn giản | CPU-only, multi-page |
