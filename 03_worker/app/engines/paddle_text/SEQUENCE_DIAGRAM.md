# Sequence Diagram — PaddleText Worker (TextRawHandler)

> Engine: `paddle_text` | Method: `ocr_text_raw` | GPU: Yes

## Tổng quan

Worker sử dụng PaddleOCR để trích xuất text từ ảnh đơn. Luồng xử lý đi qua 3 giai đoạn: preprocessing → inference → postprocessing.

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
    participant Handler as TextRawHandler
    participant Pre as preprocessing.py
    participant Paddle as PaddleOCR Engine
    participant Post as postprocessing.py

    Note over Main,Post: ===== PHASE 1: WORKER STARTUP =====

    Main->>Worker: OCRWorker(shutdown_handler)
    Worker->>Proc: OCRProcessor()
    Proc->>Handler: TextRawHandler(use_gpu, lang)
    Handler->>Paddle: PaddleOCR(use_gpu=True, lang="en", show_log=False)
    Paddle-->>Handler: ocr engine ready

    Worker->>Orch: POST /register<br/>{service_type, instance_id, allowed_methods: ["ocr_text_raw"], engine_info}
    Orch-->>Worker: {type_status: "APPROVED", access_key: "xxx"}
    Worker->>Queue: connect() → NATS JetStream<br/>stream="OCR_JOBS", subject="ocr.ocr_text_raw.tier0"
    Worker->>Worker: heartbeat.start() (mỗi 30s)

    Note over Main,Post: ===== PHASE 2: JOB POLLING LOOP =====

    loop Mỗi vòng lặp (while not shutdown)
        Worker->>Queue: pull_job(timeout=5s)
        Queue-->>Worker: job = None (nếu không có việc)
        Note right of Worker: Tiếp tục polling...

        Queue-->>Worker: job = {job_id, file_id, method: "ocr_text_raw", output_format: "json"}
    end

    Note over Main,Post: ===== PHASE 3: XỬ LÝ JOB =====

    Worker->>State: start_job(job_id)
    State-->>Worker: status = "processing"

    Worker->>Orch: PATCH /jobs/{job_id}/status<br/>{status: "PROCESSING"}
    Orch-->>Worker: 200 OK

    Note over Worker,FP: 3a. Download file từ MinIO qua Backend

    Worker->>FP: POST /file-proxy/download<br/>{job_id, file_id}
    FP-->>Worker: file_bytes (image data)

    Note over Worker,Post: 3b. OCR Processing

    Worker->>Proc: process(file_bytes, "json", "ocr_text_raw")
    Proc->>Handler: process(file_bytes, "json")

    Note over Handler,Post: --- Preprocessing ---
    Handler->>Pre: load_image(file_bytes)
    Pre->>Pre: io.BytesIO(file_bytes) → PIL.Image.open()
    Pre->>Pre: image.convert("RGB")
    Pre->>Pre: np.array(image)
    Pre-->>Handler: numpy_array (RGB)

    Note over Handler,Post: --- Inference ---
    Handler->>Paddle: self.ocr.ocr(numpy_array, cls=True)
    Note right of Paddle: PaddleOCR thực hiện:<br/>1. Text Detection (DB)<br/>2. Direction Classification<br/>3. Text Recognition (CRNN)
    Paddle-->>Handler: ocr_result = [[[box, (text, confidence)], ...]]

    Note over Handler,Post: --- Postprocessing ---
    Handler->>Post: extract_results(ocr_result)
    Post->>Post: Duyệt qua từng line trong result[0]
    Post->>Post: Thu thập: text_lines[], boxes[], confidences[]
    Post->>Post: full_text = "\n".join(text_lines)
    Post-->>Handler: {full_text, text_lines, boxes, confidences}

    Handler->>Post: format_output(extracted, "json")
    alt output_format == "json"
        Post->>Post: JSON với full_text + lines[{text, confidence, box}]
        Post-->>Handler: json_bytes
    else output_format == "txt"
        Post->>Post: Plain text (full_text only)
        Post-->>Handler: text_bytes
    end

    Handler-->>Proc: result_bytes
    Proc-->>Worker: result_bytes

    Note over Worker,FP: 3c. Upload kết quả lên MinIO qua Backend

    Worker->>FP: POST /file-proxy/upload<br/>{job_id, file_id, content: base64(result), content_type}
    FP-->>Worker: {result_key: "results/..."}

    Note over Worker,Orch: 3d. Cập nhật trạng thái hoàn thành

    Worker->>Orch: PATCH /jobs/{job_id}/status<br/>{status: "COMPLETED", engine_version: "paddleocr 2.7.3"}
    Orch-->>Worker: 200 OK

    Worker->>Queue: ack(msg_id)
    Queue-->>Worker: ACK confirmed

    Worker->>State: end_job()
    State-->>Worker: status = "idle", files_completed++

    Note over Main,Post: ===== ERROR HANDLING =====

    rect
        Note over Worker,Post: Nếu xảy ra lỗi trong quá trình xử lý:

        alt RetriableError (download/upload timeout, connection error)
            Worker->>Orch: PATCH /jobs/{job_id}/status<br/>{status: "FAILED", error, retriable: true}
            Worker->>Queue: nak(msg_id, delay=5s)
            Note right of Queue: Message sẽ được retry sau 5s
        else PermanentError (ảnh không hợp lệ, format lỗi)
            Worker->>Orch: PATCH /jobs/{job_id}/status<br/>{status: "FAILED", error, retriable: false}
            Worker->>Queue: term(msg_id)
            Note right of Queue: Message bị loại bỏ vĩnh viễn
        end

        Worker->>State: record_error()
        State-->>Worker: error_count++
    end

    Note over Main,Post: ===== HEARTBEAT (song song, mỗi 30s) =====

    loop Mỗi 30 giây
        Worker->>Orch: POST /heartbeat<br/>{instance_id, status, current_job_id, files_completed, error_count}
        Orch-->>Worker: {action: "continue"}
        alt action == "drain"
            Worker->>Worker: is_draining = True → hoàn thành job hiện tại rồi dừng
        else action == "shutdown"
            Worker->>Orch: POST /deregister {instance_id}
            Worker->>Queue: disconnect()
            Worker->>Worker: exit
        end
    end
```

## Chi tiết Data Flow

### Input
| Field | Type | Mô tả |
|-------|------|--------|
| `file_bytes` | `bytes` | Dữ liệu ảnh (PNG, JPG, TIFF...) |
| `output_format` | `str` | `"json"` hoặc `"txt"` |

### Output (JSON format)
```json
{
  "full_text": "Toàn bộ text trích xuất",
  "lines": [
    {
      "text": "Dòng text",
      "confidence": 0.95,
      "box": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    }
  ]
}
```

### Output (TXT format)
```
Dòng 1
Dòng 2
...
```

## Error Classification

| Exception | Loại | Hành động |
|-----------|------|-----------|
| `ConnectionError`, `TimeoutError` | Retriable | NAK + retry sau 5s |
| `DownloadError`, `UploadError` | Retriable | NAK + retry sau 5s |
| `InvalidImageError`, `ValueError` | Permanent | TERM + không retry |
| `UnidentifiedImageError` | Permanent | TERM + không retry |
