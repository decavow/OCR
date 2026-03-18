# Full Flow Sequence Diagram — User Upload → Worker Output → Result Display

> Luồng xử lý end-to-end toàn bộ hệ thống OCR/IDP Platform

---

## 1. Diagram tổng quan (High-Level)

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant User as User (Browser)
    participant FE as Frontend<br/>(React + Vite)
    participant BE as Backend<br/>(FastAPI)
    participant DB as SQLite (WAL)
    participant MinIO as MinIO<br/>(Object Storage)
    participant NATS as NATS JetStream<br/>(Message Queue)
    participant Worker as OCR Worker<br/>(Paddle/Tesseract/VL)

    User->>FE: Chọn file + cấu hình OCR
    FE->>BE: POST /upload (multipart)
    BE->>DB: Tạo Request + File + Job records
    BE->>MinIO: Upload file gốc → uploads bucket
    BE->>NATS: Publish JobMessage → ocr.{method}.tier{tier}
    BE-->>FE: {request_id, files[]}

    NATS-->>Worker: Pull job message
    Worker->>BE: PATCH status → PROCESSING
    Worker->>BE: POST /file-proxy/download
    BE->>MinIO: GET file gốc
    MinIO-->>BE: file bytes
    BE-->>Worker: file bytes

    Worker->>Worker: OCR Processing (engine)
    Worker->>BE: POST /file-proxy/upload (result)
    BE->>MinIO: PUT result → results bucket
    Worker->>BE: PATCH status → COMPLETED
    Worker->>NATS: ACK message

    BE->>DB: Update Job + Request status

    loop Polling mỗi 2-5s
        FE->>BE: GET /requests/{id}
        BE->>DB: Query status
        BE-->>FE: {status, completed_files, jobs[]}
    end

    FE->>BE: GET /jobs/{id}/result
    BE->>MinIO: GET result file
    MinIO-->>BE: result bytes
    BE-->>FE: {text, metadata}
    FE-->>User: Hiển thị kết quả OCR
```

---

## 2. Phase 1 — User Upload (Chi tiết)

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant User as User (Browser)
    participant DZ as DropZone.tsx
    participant UC as UploadConfig.tsx
    participant API as upload.ts<br/>(Axios Client)
    participant EP as POST /upload<br/>(endpoints/upload.py)
    participant US as UploadService<br/>(modules/upload/)
    participant Val as validators.py
    participant DB as SQLite
    participant Repo as Repositories
    participant MinIO as MinIO
    participant NATS as NATS JetStream

    Note over User,NATS: === Frontend: Chọn file & cấu hình ===

    User->>DZ: Kéo thả / chọn file (drag & drop)
    DZ->>DZ: Filter ALLOWED_FILE_TYPES<br/>(JPEG, PNG, TIFF, PDF)
    DZ->>UC: onFilesSelected(files)

    User->>UC: Chọn cấu hình OCR
    Note right of UC: • method: ocr_paddle_text / structured_extract<br/>• tier: 0, 1, 2<br/>• output_format: txt / json / md / html<br/>• retention_hours: 1-720h

    UC->>API: uploadFiles(files, config, onProgress)
    API->>EP: POST /upload?method=ocr_paddle_text&tier=0&output_format=txt&retention_hours=168<br/>Content-Type: multipart/form-data<br/>Authorization: Bearer {token}<br/>Body: files[]

    Note over EP,NATS: === Backend: Validate & Store ===

    EP->>US: process_upload(files, config, user)

    US->>US: _validate_service_available(method, tier)
    US->>Repo: ServiceTypeRepository.get_approved()
    Repo->>DB: SELECT service_types WHERE status=APPROVED
    DB-->>Repo: approved_services[]
    Repo-->>US: Có service khả dụng cho method+tier

    US->>Val: validate_batch(files)
    Val->>Val: Kiểm tra số lượng file
    Val-->>US: OK

    loop Với mỗi file trong batch
        US->>US: _validate_single_file(file)
        US->>US: Đọc file bytes
        US->>Val: Validate MIME type (kiểm tra file signature thực tế)
        Val-->>US: ValidatedFile{filename, content, mime_type, file_id, job_id}
    end

    US->>Val: validate_total_batch_size(total_size)
    Note right of Val: Max 50MB/file, 200MB/batch
    Val-->>US: OK

    Note over US,NATS: === Tạo records & Store files ===

    US->>Repo: RequestRepository.create()
    Repo->>DB: INSERT Request (request_id, user_id, method, tier, output_format, status=PROCESSING, expires_at)
    DB-->>Repo: request record

    loop Với mỗi validated file
        US->>MinIO: storage.upload(bucket=uploads, key=users/{uid}/{req_id}/{file_id}/{filename}, data=bytes)
        MinIO-->>US: upload OK

        US->>Repo: FileRepository.create()
        Repo->>DB: INSERT File (file_id, request_id, original_name, mime_type, size_bytes, object_key)

        US->>Repo: JobRepository.create()
        Repo->>DB: INSERT Job (job_id, request_id, file_id, status=SUBMITTED, method, tier, retry_count=0)

        US->>Repo: JobRepository.update_status()
        Repo->>DB: UPDATE Job SET status=QUEUED

        US->>NATS: publish(subject="ocr.ocr_paddle_text.tier0", message=JobMessage)
        Note right of NATS: JobMessage:<br/>{job_id, file_id, request_id,<br/>method, tier, output_format,<br/>object_key}
        NATS-->>US: publish ACK (JetStream durability)
    end

    US-->>EP: UploadResponse
    EP-->>API: 200 OK
    Note right of API: Response:<br/>{request_id, status: "PROCESSING",<br/>total_files: N, files: [{id, name, mime, size}]}
    API-->>UC: upload success
    UC-->>User: Hiển thị request_id, chuyển sang màn hình theo dõi
```

---

## 3. Phase 2 — Worker Registration & Approval

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Main as main.py
    participant Worker as OCRWorker
    participant Proc as OCRProcessor
    participant Engine as OCR Engine<br/>(Paddle/Tesseract/VL)
    participant Orch as OrchestratorClient
    participant HB as HeartbeatClient
    participant Queue as QueueClient
    participant RegEP as POST /internal/register<br/>(Backend)
    participant HBEP as POST /internal/heartbeat<br/>(Backend)
    participant DB as SQLite
    participant NATS as NATS JetStream

    Note over Main,NATS: === Worker Startup ===

    Main->>Main: setup_logging() (stdout + file, 30-day retention)
    Main->>Main: GracefulShutdown() (SIGTERM/SIGINT handlers)
    Main->>Worker: OCRWorker(shutdown_handler)

    Worker->>Proc: OCRProcessor()
    Proc->>Engine: Init engine theo OCR_ENGINE env var
    Note right of Engine: paddle → TextRawHandler(gpu, lang)<br/>tesseract → TextRawTesseractHandler(lang)<br/>paddle_vl → StructuredExtractHandler(gpu, lang)
    Engine-->>Proc: handler ready

    Note over Worker,NATS: === Registration ===

    Worker->>Orch: register()
    Orch->>RegEP: POST /internal/register
    Note right of Orch: Body:<br/>{service_type: "ocr-text-tier0",<br/>instance_id: "ocr-text-tier0-abc123",<br/>allowed_methods: ["ocr_paddle_text"],<br/>allowed_tiers: [0],<br/>engine_info: {engine, version, lang},<br/>supported_output_formats: ["txt","json"]}

    RegEP->>DB: Tìm hoặc tạo ServiceType
    RegEP->>DB: Tạo ServiceInstance

    alt ServiceType đã APPROVED
        DB-->>RegEP: type_status=APPROVED
        RegEP-->>Orch: {type_status: "APPROVED", access_key: "xxx"}
        Orch-->>Worker: approved = true
        Worker->>Worker: Set access_key trên tất cả clients
    else ServiceType PENDING (cần admin duyệt)
        DB-->>RegEP: type_status=PENDING
        RegEP-->>Orch: {type_status: "PENDING", access_key: null}
        Orch-->>Worker: approved = false
    else ServiceType REJECTED
        RegEP-->>Orch: {type_status: "REJECTED"}
        Orch-->>Worker: REJECTED → set shutdown flag
    end

    Note over Worker,NATS: === Connect NATS (luôn chạy, kể cả chưa approved) ===

    Worker->>Queue: connect()
    Queue->>NATS: nats.connect(nats_url)
    Queue->>NATS: Pull subscription<br/>stream="OCR_JOBS"<br/>subject="ocr.ocr_paddle_text.tier0"<br/>consumer=service_type (shared, durable)
    NATS-->>Queue: subscription ready

    Note over Worker,NATS: === Start Heartbeat ===

    Worker->>HB: set_state(worker_state)
    Worker->>HB: set_action_callback(_handle_heartbeat_action)
    Worker->>HB: start()

    loop Mỗi 30 giây
        HB->>HBEP: POST /internal/heartbeat
        Note right of HB: Body:<br/>{instance_id, status: "idle"/"processing",<br/>current_job_id, files_completed,<br/>files_total, error_count}

        HBEP->>DB: Update instance.last_heartbeat
        HBEP->>DB: Check ServiceType.status

        alt action == "continue" (type APPROVED, instance ACTIVE)
            HBEP-->>HB: {action: "continue"}
            HB-->>Worker: _re_register_attempts = 0
        else action == "approved" (first-time approval)
            HBEP-->>HB: {action: "approved", access_key: "xxx"}
            HB-->>Worker: _handle_heartbeat_action("approved")
            Worker->>Worker: Set access_key, is_approved = true
        else action == "re_register" (instance lost, e.g. backend restart)
            HBEP-->>HB: {action: "re_register"}
            HB-->>Worker: _retry_registration()
            Note right of Worker: Exponential backoff: 0s, 5s, 10s, 20s, 40s... max 60s
        else action == "drain" (type DISABLED)
            HBEP-->>HB: {action: "drain"}
            HB-->>Worker: is_draining = true (hoàn thành job hiện tại rồi dừng)
        else action == "shutdown" (type REJECTED)
            HBEP-->>HB: {action: "shutdown", rejection_reason: "..."}
            HB-->>Worker: deregister + set shutdown flag
        end
    end
```

---

## 4. Phase 3 — Job Processing (Chi tiết nhất)

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Worker as OCRWorker
    participant State as WorkerState
    participant Queue as QueueClient
    participant NATS as NATS JetStream
    participant Orch as OrchestratorClient
    participant StatusEP as PATCH /internal/jobs/{id}/status
    participant FPClient as FileProxyClient
    participant FPEP as /internal/file-proxy
    participant FPSvc as FileProxyService
    participant MinIO as MinIO
    participant Proc as OCRProcessor
    participant Handler as Engine Handler<br/>(Paddle/Tesseract/VL)
    participant JobSvc as JobService
    participant DB as SQLite

    Note over Worker,DB: === Poll Job ===

    loop Main loop (while not shutdown)
        Worker->>Worker: Check: is_approved? is_draining?
        Worker->>Queue: pull_job(timeout=5s)
        Queue->>NATS: fetch(batch=1, timeout=5s)

        alt Không có message
            NATS-->>Queue: timeout (empty)
            Queue-->>Worker: None → tiếp tục loop
        else Có message
            NATS-->>Queue: message bytes
            Queue->>Queue: Parse JSON → job dict
            Queue-->>Worker: {job_id, file_id, request_id, method, tier, output_format, object_key, _msg_id}
        end
    end

    Note over Worker,DB: === Bắt đầu xử lý ===

    Worker->>State: start_job(job_id)
    State-->>Worker: status="processing", job_started_at=now

    Worker->>Orch: update_status(job_id, "PROCESSING")
    Orch->>StatusEP: PATCH /internal/jobs/{job_id}/status<br/>X-Access-Key: xxx<br/>{status: "PROCESSING"}

    alt 404 — Job not found (stale message)
        StatusEP-->>Orch: 404
        Orch-->>Worker: HTTPStatusError(404)
        Worker->>Queue: term(msg_id)
        Note right of Queue: Stale message → loại bỏ, return
    else 200 OK
        StatusEP->>JobSvc: update_job_status()
        JobSvc->>DB: UPDATE Job SET status=PROCESSING, started_at=now, worker_id=instance_id
        DB-->>JobSvc: OK
        JobSvc-->>StatusEP: OK
        StatusEP-->>Orch: 200
        Orch-->>Worker: OK
    end

    Note over Worker,DB: === Download file gốc từ MinIO ===

    Worker->>FPClient: download(job_id, file_id)
    FPClient->>FPEP: POST /internal/file-proxy/download<br/>X-Access-Key: xxx<br/>{job_id, file_id}

    FPEP->>FPSvc: download_for_worker(job_id, file_id, access_key)
    FPSvc->>FPSvc: Verify access_key → ServiceType
    FPSvc->>DB: Verify Job belongs to this ServiceType (ACL check)
    FPSvc->>DB: Get File record → object_key
    FPSvc->>MinIO: download(bucket=uploads, key=object_key)
    MinIO-->>FPSvc: file_bytes
    FPSvc-->>FPEP: file_bytes + metadata
    FPEP-->>FPClient: Response body=file_bytes<br/>Headers: X-Content-Type, X-File-Name
    FPClient-->>Worker: (file_bytes, content_type, filename)

    Note over Worker,DB: === OCR Processing ===

    Worker->>Proc: process(file_bytes, output_format, method)
    Proc->>Proc: Chọn handler theo method name

    Proc->>Handler: process(file_bytes, output_format)

    Note right of Handler: Preprocessing:<br/>• load_images (multi-page support)<br/>• PDF → images (pypdfium2 200 DPI / pdf2image 200 DPI)<br/>• Upscale/downscale nếu cần (paddle_vl only)<br/>• Convert RGB → numpy array

    Handler->>Handler: Preprocessing

    Note right of Handler: Inference:<br/>• PaddleOCR v2: ocr(img, cls=True)<br/>• PaddleOCR v3: predict(img)<br/>• PPStructure v2: engine(img)<br/>• PPStructureV3: engine.predict(img)<br/>• pytesseract: image_to_data()

    Handler->>Handler: Inference (OCR Engine)

    Note right of Handler: Postprocessing:<br/>• Extract text lines, boxes, confidence<br/>• Format output (json/txt/md/html)<br/>• Encode to UTF-8 bytes

    Handler->>Handler: Postprocessing

    Handler-->>Proc: result_bytes
    Proc-->>Worker: result_bytes

    Note over Worker,DB: === Upload kết quả lên MinIO ===

    Worker->>Worker: Determine content_type theo output_format
    Note right of Worker: json→"application/json"<br/>md→"text/markdown"<br/>html→"text/html"<br/>else→"text/plain"

    Worker->>FPClient: upload(job_id, file_id, result_bytes, content_type)
    FPClient->>FPClient: base64.b64encode(result_bytes)
    FPClient->>FPEP: POST /internal/file-proxy/upload<br/>X-Access-Key: xxx<br/>{job_id, file_id, content: base64, content_type}

    FPEP->>FPSvc: upload_from_worker(job_id, file_id, content, access_key)
    FPSvc->>FPSvc: Verify access_key + ACL
    FPSvc->>FPSvc: Generate result_key: users/{uid}/{req_id}/{file_id}/result.{ext}
    FPSvc->>MinIO: upload(bucket=results, key=result_key, data=decoded_bytes)
    MinIO-->>FPSvc: upload OK
    FPSvc->>DB: UPDATE Job SET result_path=result_key
    FPSvc-->>FPEP: {result_key}
    FPEP-->>FPClient: {result_key}
    FPClient-->>Worker: upload success

    Note over Worker,DB: === Cập nhật COMPLETED ===

    Worker->>Worker: engine_info = processor.get_engine_info()
    Worker->>Orch: update_status(job_id, "COMPLETED", engine_version="{engine} {version}")
    Orch->>StatusEP: PATCH /internal/jobs/{job_id}/status<br/>{status: "COMPLETED", engine_version: "paddleocr X.Y.Z"}

    StatusEP->>JobSvc: update_job_status()
    JobSvc->>JobSvc: Validate transition: PROCESSING → COMPLETED ✓
    JobSvc->>DB: UPDATE Job SET status=COMPLETED, completed_at=now, processing_time_ms, engine_version
    JobSvc->>DB: UPDATE Request SET completed_files = completed_files + 1

    JobSvc->>JobSvc: Recalculate request status (state machine)
    Note right of JobSvc: Nếu tất cả jobs COMPLETED → Request.status = COMPLETED<br/>Nếu còn jobs đang chạy → Request.status = PROCESSING<br/>Nếu mix COMPLETED + FAILED → PARTIAL_SUCCESS

    JobSvc->>DB: UPDATE Request SET status = (calculated)
    JobSvc-->>StatusEP: OK
    StatusEP-->>Orch: 200
    Orch-->>Worker: OK

    Worker->>Queue: ack(msg_id)
    Queue->>NATS: ACK message
    NATS-->>Queue: confirmed (message removed from queue)

    Note over Worker,DB: === Cleanup (finally block — luôn chạy) ===

    Worker->>State: end_job()
    State-->>Worker: current_job_id=None, status="idle", files_completed++
    Note right of State: end_job() chạy cả khi success và error
```

---

## 5. Phase 3b — Error & Retry Flow

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Worker as OCRWorker
    participant State as WorkerState
    participant Orch as OrchestratorClient
    participant StatusEP as Backend API
    participant JobSvc as JobService
    participant RetryOrch as RetryOrchestrator
    participant Queue as QueueClient
    participant NATS as NATS JetStream
    participant DB as SQLite

    Note over Worker,DB: === Lỗi xảy ra trong process_job() ===

    Note right of Worker: Worker dùng try/except bắt exception types:<br/>• RetriableError → retriable=true<br/>• PermanentError → retriable=false<br/>• Exception (khác) → retriable=true (conservative)

    alt RetriableError (timeout, connection, download/upload fail)
        Worker->>Worker: catch RetriableError

        Worker->>Orch: update_status(job_id, "FAILED", error=str(e), retriable=true)
        Orch->>StatusEP: PATCH /internal/jobs/{id}/status<br/>{status: "FAILED", error, retriable: true}
        StatusEP->>JobSvc: update_job_status()
        JobSvc->>DB: UPDATE Job SET status=FAILED

        JobSvc->>RetryOrch: handle_failure(job, error, retriable=true)
        RetryOrch->>RetryOrch: decide_retry_or_dlq(job)

        alt retry_count < MAX_RETRIES (3)
            RetryOrch->>DB: UPDATE Job SET retry_count++, status=QUEUED
            RetryOrch->>NATS: Re-publish JobMessage → ocr.{method}.tier{tier}
            Note right of NATS: Job quay lại queue để worker khác xử lý
        else retry_count >= MAX_RETRIES
            RetryOrch->>DB: UPDATE Job SET status=DEAD_LETTER
            RetryOrch->>NATS: Publish → dlq.{method}.tier{tier}
            Note right of NATS: Job vào Dead Letter Queue cho admin review
            RetryOrch->>DB: UPDATE Request failed_files++
        end

        Worker->>Queue: nak(msg_id, delay=5s)
        Queue->>NATS: NAK with delay
        Note right of NATS: Message available lại sau 5s

    else PermanentError (ảnh lỗi, PDF corrupt, format không hỗ trợ)
        Worker->>Worker: catch PermanentError

        Worker->>Orch: update_status(job_id, "FAILED", error=str(e), retriable=false)
        Orch->>StatusEP: PATCH {status: "FAILED", retriable: false}
        StatusEP->>JobSvc: update_job_status()
        JobSvc->>RetryOrch: handle_failure(job, error, retriable=false)
        RetryOrch->>DB: UPDATE Job SET status=DEAD_LETTER
        RetryOrch->>NATS: Publish → dlq.{method}.tier{tier}
        RetryOrch->>DB: UPDATE Request failed_files++

        Worker->>Queue: term(msg_id)
        Queue->>NATS: TERM message
        Note right of NATS: Message bị loại bỏ vĩnh viễn khỏi queue

    else Unexpected Exception (bất kỳ lỗi khác)
        Worker->>Worker: catch Exception (treated as retriable)
        Worker->>Orch: update_status(job_id, "FAILED", error=str(e), retriable=true)
        Worker->>Queue: nak(msg_id, delay=5s)

    else 404 khi report FAILED to backend
        Worker->>Queue: term(msg_id)
        Note right of Queue: Backend không biết job → loại bỏ, không retry

    else Job not found (404 khi report PROCESSING)
        Worker->>Queue: term(msg_id)
        Note right of Queue: Stale job message → loại bỏ, return sớm
    end

    Note over Worker,DB: === Cleanup (finally block — luôn chạy) ===

    Worker->>State: end_job()
    State-->>Worker: current_job_id=None, status="idle", files_completed++
    Worker->>State: record_error()
    State-->>Worker: error_count++

    Note over Worker,DB: === Request Status Recalculation ===
    Note right of DB: State Machine cho Request:<br/>• Còn job PROCESSING/QUEUED → PROCESSING<br/>• Tất cả COMPLETED → COMPLETED<br/>• Tất cả FAILED/DEAD_LETTER → FAILED<br/>• Tất cả CANCELLED → CANCELLED<br/>• Mix terminal states → PARTIAL_SUCCESS
```

---

## 6. Phase 4 — Frontend Polling & Hiển thị kết quả

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant User as User (Browser)
    participant JobUI as JobStatus.tsx
    participant ResultUI as ResultViewer.tsx
    participant JobAPI as jobs.ts / requests.ts
    participant ReqEP as GET /requests/{id}<br/>(endpoints/requests.py)
    participant JobEP as GET /jobs/{id}/result<br/>(endpoints/jobs.py)
    participant DB as SQLite
    participant MinIO as MinIO

    Note over User,MinIO: === Polling trạng thái ===

    loop Polling mỗi 2-5s (while status == PROCESSING)
        JobUI->>JobAPI: getRequestStatus(request_id)
        JobAPI->>ReqEP: GET /requests/{request_id}<br/>Authorization: Bearer {token}
        ReqEP->>DB: SELECT Request + Jobs WHERE request_id AND user_id
        DB-->>ReqEP: request + jobs[]
        ReqEP-->>JobAPI: RequestDetailResponse

        Note right of JobAPI: Response:<br/>{id, status: "PROCESSING",<br/>total_files: 2, completed_files: 1,<br/>failed_files: 0,<br/>jobs: [{id, file_id, status, processing_time_ms}]}

        JobAPI-->>JobUI: status update
        JobUI-->>User: Cập nhật UI:<br/>progress bar, per-file status
    end

    Note over User,MinIO: === Request hoàn thành ===

    JobAPI-->>JobUI: status = "COMPLETED" (hoặc PARTIAL_SUCCESS)
    JobUI-->>User: Hiển thị nút xem kết quả

    Note over User,MinIO: === Lấy kết quả OCR ===

    User->>ResultUI: Click xem kết quả job

    ResultUI->>JobAPI: getJobResult(job_id)
    JobAPI->>JobEP: GET /jobs/{job_id}/result?format=text<br/>Authorization: Bearer {token}
    JobEP->>DB: Verify job ownership (user_id qua request)
    JobEP->>DB: Get Job → result_path
    JobEP->>MinIO: download(bucket=results, key=result_path)
    MinIO-->>JobEP: result_bytes
    JobEP->>JobEP: Parse result content
    JobEP-->>JobAPI: ResultResponse

    Note right of JobAPI: Response:<br/>{text: "Extracted text...",<br/>lines: 45,<br/>metadata: {method, tier,<br/>processing_time_ms, engine_name}}

    JobAPI-->>ResultUI: result data
    ResultUI-->>User: Hiển thị:<br/>• Extracted text<br/>• Line count<br/>• Processing metadata

    Note over User,MinIO: === Download file kết quả (tùy chọn) ===

    User->>ResultUI: Click download
    ResultUI->>JobAPI: downloadResult(job_id)
    JobAPI->>JobEP: GET /jobs/{job_id}/download
    JobEP->>MinIO: download(bucket=results, key=result_path)
    MinIO-->>JobEP: result_bytes
    JobEP-->>JobAPI: Binary response<br/>Content-Disposition: attachment; filename="document_result.txt"
    JobAPI-->>ResultUI: file blob
    ResultUI-->>User: Browser download dialog

    Note over User,MinIO: === Presigned URL (tùy chọn) ===

    ResultUI->>JobAPI: getPresignedUrl(file_id, "result")
    JobAPI->>JobEP: GET /files/{file_id}/result-url
    JobEP->>MinIO: presigned_get_url(bucket, key, expires=3600)
    MinIO-->>JobEP: https://minio:9000/results/...?token=xxx
    JobEP-->>JobAPI: {url, expires_at}
    JobAPI-->>ResultUI: presigned URL (valid 1h)
```

---

## 7. Graceful Shutdown & Heartbeat Monitor

```mermaid
%%{init: {'theme': 'default'}}%%
sequenceDiagram
    autonumber
    participant Signal as OS Signal<br/>(SIGTERM/SIGINT)
    participant Shutdown as GracefulShutdown
    participant Worker as OCRWorker
    participant HB as HeartbeatClient
    participant Queue as QueueClient
    participant Orch as OrchestratorClient
    participant BE as Backend

    Note over Signal,BE: === Graceful Shutdown ===

    Signal->>Shutdown: SIGTERM / SIGINT
    Shutdown->>Shutdown: is_shutting_down = True
    Shutdown-->>Worker: Main loop kiểm tra shutdown flag

    Worker->>Worker: Hoàn thành job hiện tại (nếu có)

    Note over Worker,BE: === worker.stop() ===

    Worker->>HB: stop()
    HB->>HB: Cancel heartbeat loop task

    Worker->>Queue: disconnect()
    Queue->>Queue: nc.drain() → Close NATS connection

    Worker->>Orch: deregister(instance_id)
    Orch->>BE: POST /internal/deregister<br/>{instance_id: "ocr-text-tier0-abc123"}
    BE->>BE: Update ServiceInstance status=DEREGISTERED
    BE-->>Orch: OK

    Worker->>Worker: Log "Worker stopped"

    Note over Signal,BE: === Heartbeat Monitor (Backend side) ===

    Note right of BE: Backend scheduler chạy định kỳ:<br/>HeartbeatMonitor.detect_stalled()<br/>→ Tìm instances không heartbeat > threshold<br/>→ Mark instance STALLED<br/>→ Re-queue jobs đang PROCESSING của instance đó
```

---

## 8. Tổng hợp Data Flow

### Protocols & Connections

| Kết nối | Protocol | Mô tả |
|---------|----------|--------|
| User ↔ Frontend | HTTPS | Browser SPA |
| Frontend ↔ Backend | HTTP REST | Axios client, Bearer token auth |
| Backend ↔ SQLite | File I/O | WAL mode, async via aiosqlite |
| Backend ↔ MinIO | S3 API | Upload/download objects |
| Backend ↔ NATS | TCP | JetStream publish |
| Worker ↔ NATS | TCP | JetStream pull consumer |
| Worker ↔ Backend | HTTP REST | Internal API, X-Access-Key auth |

### MinIO Buckets

| Bucket | Nội dung | Path Pattern |
|--------|----------|-------------|
| `uploads` | File gốc (ảnh, PDF) | `users/{uid}/{req_id}/{file_id}/{filename}` |
| `results` | Kết quả OCR | `users/{uid}/{req_id}/{file_id}/result.{ext}` |
| `deleted` | File đã xóa (retention cleanup) | moved từ uploads/results |

### NATS Subjects & Streams

| Stream | Subject Pattern | Mục đích |
|--------|----------------|----------|
| `OCR_JOBS` | `ocr.{method}.tier{tier}` | Job queue chính |
| `OCR_DLQ` | `dlq.{method}.tier{tier}` | Dead Letter Queue |

### Database State Machine

```
Job States:
  SUBMITTED → QUEUED → PROCESSING → COMPLETED
                ↑          ↓
                ← ← ←  FAILED (retry)
                           ↓
                      DEAD_LETTER

Request States:
  PROCESSING → COMPLETED | FAILED | PARTIAL_SUCCESS | CANCELLED
```

### Error Classification (Worker)

| Exception | Loại | Worker Action | Backend Action |
|-----------|------|---------------|----------------|
| `RetriableError` | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| `ConnectionError` | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| `TimeoutError` | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| `DownloadError` | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| `UploadError` | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| `PermanentError` | Permanent | TERM | → DEAD_LETTER |
| `InvalidImageError` | Permanent | TERM | → DEAD_LETTER |
| `PDFSyntaxError` | Permanent | TERM | → DEAD_LETTER |
| `ValueError` | Permanent | TERM | → DEAD_LETTER |
| Unexpected Exception | Retriable | NAK (delay 5s) | retry_count++ → re-queue |
| Max retries exceeded | — | — | → DEAD_LETTER |
| 404 Job not found | — | TERM | — |

### Security & Access Control

| Layer | Mechanism | Mô tả |
|-------|-----------|--------|
| Frontend → Backend | Bearer Token | Session-based auth (self-host) |
| Worker → Backend | X-Access-Key | Cấp khi ServiceType APPROVED |
| File Access | ACL Check | Job phải thuộc ServiceType của worker |
| User Ownership | Request Check | Request phải thuộc user đang đăng nhập |
