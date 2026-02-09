# OCR Platform Local MVP1 - Code Structure

> Version: 2.1 | Phase: Local MVP 1
> Aligned with: SA v3.1

---

## 1. Root Directory Structure

```
ocr-platform/
├── docker-compose.yml          # Orchestration cho all services
├── .env.example                 # Environment template
├── .env                         # Local environment (gitignored)
├── README.md                    # Quick start guide
├── Makefile                     # Common commands shortcuts
│
├── frontend/                    # React SPA (Edge Layer)
├── backend/                     # FastAPI Monolith (Edge + Orchestration)
├── worker/                      # OCR Worker (Processing Layer)
├── data/                        # Persistent data (gitignored)
│   ├── ocr_platform.db          # SQLite database (Orchestration)
│   ├── nats/                    # NATS JetStream data (Orchestration)
│   └── minio/                   # MinIO object storage (Edge)
└── docs/                        # Documentation
```

**Layer Mapping:**
```
┌─────────────────────────────────────────────────────────────┐
│  EDGE LAYER                                                  │
│  ├── frontend/          (React SPA)                         │
│  ├── backend/app/api/   (API Server - entry point)          │
│  └── MinIO container    (Object Storage)                    │
├─────────────────────────────────────────────────────────────┤
│  ORCHESTRATION LAYER                                         │
│  ├── backend/app/modules/       (Auth, Upload, Job, FileProxy)│
│  ├── backend/app/infrastructure/ (DB, Queue, Storage Client)│
│  └── NATS container             (Message Queue)             │
├─────────────────────────────────────────────────────────────┤
│  PROCESSING LAYER                                            │
│  └── worker/            (OCR Worker - Tesseract)            │
└─────────────────────────────────────────────────────────────┘
```

**Removed from v2.0:**
- `scripts/` directory — services initialized via docker compose entrypoints
- `alembic/` — fresh build, no migration needed Phase 1
- `infrastructure/cleanup/` — no hard delete, files persist in MinIO

---

## 2. Frontend Structure (React + TypeScript + Vite)

> Cấu trúc frontend được thiết kế dựa trên sample UI — Result Viewer layout
> với split-panel (original image + extracted text), file navigation trong batch,
> và download options (TXT, JSON, Copy).

```
frontend/
├── Dockerfile
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
│
├── public/
│   └── favicon.ico
│
└── src/
    ├── main.tsx                 # Entry point
    ├── App.tsx                  # Root component + Router
    ├── vite-env.d.ts
    │
    ├── config/
    │   └── index.ts             # API_BASE_URL, constants
    │
    ├── types/
    │   ├── index.ts             # Export all types
    │   ├── auth.ts              # User, Session types
    │   ├── batch.ts             # Batch (= Request in backend) types
    │   ├── job.ts               # JobStatus enum (all states), Job type
    │   └── file.ts              # File, UploadFile, ResultFile types
    │
    ├── api/
    │   ├── client.ts            # Axios instance + interceptors
    │   ├── auth.ts              # login(), register(), logout(), getMe()
    │   ├── upload.ts            # uploadFiles(files, config)
    │   ├── batches.ts           # getBatches(), getBatch(id), cancelBatch(id)
    │   ├── jobs.ts              # getJob(id), getJobResult(id)
    │   └── files.ts             # getOriginalUrl(id), getResultUrl(id), downloadResult(id, format)
    │
    ├── hooks/
    │   ├── useAuth.ts           # Authentication state
    │   ├── usePolling.ts        # Status polling with configurable interval
    │   ├── useUpload.ts         # File upload with progress tracking
    │   ├── useBatchNavigation.ts # Navigate between files in a batch (prev/next)
    │   └── useKeyboard.ts       # Keyboard shortcuts (arrow keys for nav, Ctrl+C for copy)
    │
    ├── context/
    │   └── AuthContext.tsx      # Auth provider (user state, token)
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppHeader.tsx        # Top nav: logo, Dashboard/Batches/Settings links,
    │   │   │                        # notification bell, user avatar
    │   │   ├── Sidebar.tsx          # Optional sidebar for batch list
    │   │   ├── MainLayout.tsx       # Layout wrapper (header + content area)
    │   │   └── StatusBar.tsx        # Bottom bar: system status, OCR engine version
    │   │
    │   ├── auth/
    │   │   ├── LoginForm.tsx
    │   │   ├── RegisterForm.tsx
    │   │   └── ProtectedRoute.tsx
    │   │
    │   ├── upload/
    │   │   ├── DropZone.tsx         # Drag-drop area with file picker
    │   │   ├── FileList.tsx         # Selected files before upload
    │   │   ├── FileItem.tsx         # Single file row (name, size, type, status)
    │   │   ├── UploadConfig.tsx     # Output format selector (TXT/JSON),
    │   │   │                        # retention selector
    │   │   └── UploadProgress.tsx   # Upload progress bar
    │   │
    │   ├── batch/
    │   │   ├── BatchCard.tsx        # Batch summary: file count, status, date
    │   │   ├── BatchList.tsx        # List/grid of batches on Batches page
    │   │   ├── BatchStatus.tsx      # Status badge (Processing, Completed,
    │   │   │                        # Partial Success, Failed, Cancelled)
    │   │   ├── BatchFileList.tsx    # Files within a batch (for batch detail view)
    │   │   └── CancelButton.tsx     # Cancel batch (only if QUEUED jobs remain)
    │   │
    │   ├── result/
    │   │   ├── ResultViewer.tsx      # ★ Main split-panel component:
    │   │   │                         #   Left panel  = OriginalPreview
    │   │   │                         #   Right panel = ExtractedText
    │   │   │
    │   │   ├── OriginalPreview.tsx   # Left panel: image/PDF preview of source file
    │   │   │                         # Loads original from MinIO via presigned URL
    │   │   │
    │   │   ├── ExtractedText.tsx     # Right panel: OCR text result with
    │   │   │                         # line numbers, scroll sync
    │   │   │
    │   │   ├── ResultToolbar.tsx     # "Extracted Text Result" header bar:
    │   │   │                         # download TXT, download JSON, Copy button
    │   │   │
    │   │   ├── ResultMetadata.tsx    # Service, Tier, Processing Time, Version badges
    │   │   │
    │   │   ├── FileNavigator.tsx     # Breadcrumb: "← Back to Batch #1024"
    │   │   │                         # File name + Processed badge
    │   │   │                         # "< File 3 of 15 >" prev/next arrows
    │   │   │
    │   │   └── TextCursor.tsx        # Bottom-right: "Ln 22, Col 1" indicator
    │   │
    │   ├── job/
    │   │   ├── JobItem.tsx          # Job row in batch detail (file name + status)
    │   │   └── JobStatus.tsx        # All states: SUBMITTED, VALIDATING, QUEUED,
    │   │                            # PROCESSING, COMPLETED, PARTIAL_SUCCESS,
    │   │                            # FAILED, REJECTED, CANCELLED, DEAD_LETTER
    │   │
    │   └── common/
    │       ├── Button.tsx
    │       ├── IconButton.tsx       # For nav arrows, copy, download icons
    │       ├── Input.tsx
    │       ├── Select.tsx           # For output format selection
    │       ├── Badge.tsx            # Status badges, tier badges
    │       ├── Modal.tsx
    │       ├── Loading.tsx
    │       ├── Breadcrumb.tsx       # "← Back to Batch #1024" pattern
    │       └── ErrorMessage.tsx
    │
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── RegisterPage.tsx
    │   ├── DashboardPage.tsx        # Overview: recent batches, quick stats
    │   ├── BatchesPage.tsx          # ★ All batches list (nav: "Batches")
    │   ├── BatchDetailPage.tsx      # Single batch: file list + statuses
    │   ├── ResultViewerPage.tsx     # ★ Split-panel result viewer (from sample UI)
    │   ├── UploadPage.tsx           # File upload + config
    │   ├── SettingsPage.tsx         # User settings (from nav: "Settings")
    │   └── NotFoundPage.tsx
    │
    ├── utils/
    │   ├── formatters.ts            # Date, size, duration formatters
    │   ├── validators.ts            # Client-side file validation
    │   └── clipboard.ts             # Copy to clipboard utility
    │
    └── styles/
        ├── globals.css
        └── variables.css
```

**UI Flow (based on sample):**

```
Login ──▶ Dashboard ──▶ Upload Page (drag-drop + config)
                │                │
                │                ▼
                │         Batches Page ◄── nav link "Batches"
                │                │
                │                ▼
                ├──────▶ Batch Detail Page
                │         (file list, statuses, cancel button)
                │                │
                │                ▼ click file
                │
                └──────▶ Result Viewer Page ★
                          ┌──────────────────────────────────────┐
                          │ ← Back to Batch #1024                │
                          │ invoice_scan_003.jpg [Processed]     │
                          │                    < File 3 of 15 >  │
                          ├──────────────┬───────────────────────┤
                          │              │ Extracted Text Result │
                          │  Original    │ [TXT] [JSON] [Copy]  │
                          │  Preview     │                       │
                          │  (image/PDF) │ SERVICE: ocr_text_raw │
                          │              │ TIER: Local           │
                          │              │ TIME: 1.2s            │
                          │              │ VERSION: 1.0.4        │
                          │              │                       │
                          │              │ INVOICE #1024         │
                          │              │ Date: October 24...   │
                          │              │ ...                   │
                          ├──────────────┴───────────────────────┤
                          │ Original Source    Ln 22, Col 1      │
                          │ System Online    OCR Engine v2.1     │
                          └──────────────────────────────────────┘
```

**Key Frontend Decisions:**

| Decision | Rationale |
|----------|-----------|
| **UI dùng "Batch" thay vì "Request"** | Tự nhiên hơn cho user. Backend vẫn giữ `requests` table, frontend mapping Batch ↔ Request. |
| **Result Viewer split-panel** | Cho phép user so sánh source image với extracted text side-by-side. Quan trọng cho QA workflow. |
| **File navigator (prev/next)** | User duyệt qua nhiều files trong một batch nhanh chóng, không cần quay về batch detail. |
| **Download từ MinIO** | Result files lưu vĩnh viễn trong MinIO. User chọn download format (TXT/JSON). API trả presigned URL hoặc stream content. |
| **Copy button** | Quick action phổ biến nhất — copy text result vào clipboard. |
| **Line/Column indicator** | Hữu ích khi user cần reference vị trí cụ thể trong kết quả OCR. |
| **Status bar** | Hiển thị system health và OCR engine version. Observable by default. |

---

## 3. Backend Structure (FastAPI + Python)

```
backend/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
│
└── app/
    ├── __init__.py
    ├── main.py                  # FastAPI app entry, lifespan events, routers mount
    ├── config.py                # Settings from env vars (Pydantic BaseSettings)
    │
    ├── api/                     # API Layer (Edge)
    │   ├── __init__.py
    │   ├── deps.py              # Dependencies: get_db, get_current_user, get_storage
    │   │
    │   └── v1/
    │       ├── __init__.py
    │       ├── router.py        # Aggregate all routers
    │       │
    │       ├── endpoints/
    │       │   ├── __init__.py
    │       │   ├── auth.py      # POST /auth/register, /auth/login, /auth/logout, GET /auth/me
    │       │   ├── upload.py    # POST /upload (multipart files + config)
    │       │   ├── requests.py  # GET /requests, /requests/:id, POST /requests/:id/cancel
    │       │   ├── jobs.py      # GET /jobs/:id, /jobs/:id/result (text content)
    │       │   ├── files.py     # GET /files/:id/original-url, /files/:id/result-url,
    │       │   │                #     /files/:id/download?format=txt|json
    │       │   └── health.py    # GET /health (DB + NATS + MinIO readiness)
    │       │
    │       ├── internal/        # Internal endpoints (Worker ↔ Orchestration)
    │       │   ├── __init__.py
    │       │   ├── file_proxy.py    # POST /internal/file-proxy/download
    │       │   │                    # POST /internal/file-proxy/upload
    │       │   ├── heartbeat.py     # POST /internal/heartbeat
    │       │   └── job_status.py    # PATCH /internal/jobs/:id/status
    │       │
    │       └── schemas/
    │           ├── __init__.py
    │           ├── auth.py      # LoginRequest, RegisterRequest, UserResponse
    │           ├── upload.py    # UploadConfig (output_format, retention_hours)
    │           ├── request.py   # RequestResponse (total, completed, failed counts)
    │           ├── job.py       # JobStatus enum, JobResponse, JobResultResponse
    │           ├── file.py      # FileResponse, PresignedUrlResponse
    │           ├── file_proxy.py # FileProxyDownloadReq, FileProxyUploadReq
    │           ├── heartbeat.py # HeartbeatPayload
    │           └── common.py    # ErrorResponse, PaginatedResponse
    │
    ├── modules/                 # Business Logic (Orchestration Layer)
    │   ├── __init__.py
    │   │
    │   ├── auth/
    │   │   ├── __init__.py
    │   │   ├── service.py       # AuthService: register, login, logout, validate_session
    │   │   ├── utils.py         # hash_password(), verify_password()
    │   │   └── exceptions.py    # AuthError, InvalidCredentials, EmailExists
    │   │
    │   ├── upload/
    │   │   ├── __init__.py
    │   │   ├── service.py       # UploadService: process_upload(), validate_and_store()
    │   │   ├── validators.py    # validate_file(mime, magic_bytes, size), validate_batch()
    │   │   └── exceptions.py    # InvalidFileType, FileTooLarge, BatchTooLarge
    │   │
    │   ├── job/
    │   │   ├── __init__.py
    │   │   ├── service.py       # JobService: create_request, get_status, cancel
    │   │   ├── orchestrator.py  # RetryOrchestrator: handle_failure(), decide_retry_or_dlq()
    │   │   ├── state_machine.py # JobStateMachine: validate_transition(), get_request_status()
    │   │   ├── heartbeat_monitor.py # HeartbeatMonitor: check_workers(), detect_stalled()
    │   │   └── exceptions.py    # JobNotFound, InvalidTransition, AlreadyCancelled
    │   │
    │   └── file_proxy/
    │       ├── __init__.py
    │       ├── service.py       # FileProxyService: download_for_worker(), upload_from_worker()
    │       ├── access_control.py # verify_access_key(), check_job_file_acl()
    │       └── exceptions.py    # AccessDenied, ServiceNotRegistered, FileNotInJob
    │
    ├── infrastructure/          # Infrastructure Adapters
    │   ├── __init__.py
    │   │
    │   ├── database/
    │   │   ├── __init__.py
    │   │   ├── connection.py    # SQLite connection + WAL mode setup
    │   │   ├── models.py        # SQLAlchemy models (all tables)
    │   │   └── repositories/
    │   │       ├── __init__.py
    │   │       ├── base.py      # BaseRepository (CRUD helpers)
    │   │       ├── user.py      # UserRepository
    │   │       ├── session.py   # SessionRepository
    │   │       ├── request.py   # RequestRepository
    │   │       ├── job.py       # JobRepository
    │   │       ├── file.py      # FileRepository
    │   │       ├── service.py   # ServiceRepository
    │   │       └── heartbeat.py # HeartbeatRepository
    │   │
    │   ├── storage/
    │   │   ├── __init__.py
    │   │   ├── interface.py     # IStorageService (abstract)
    │   │   │                    # NOTE: Used by Edge layer (Upload via API context)
    │   │   │                    # and Orchestration layer (File Proxy with credentials).
    │   │   │                    # Processing layer MUST NOT import this module.
    │   │   ├── minio_client.py  # MinIOStorageService: upload, download, presigned_url,
    │   │   │                    # move_to_deleted (soft delete only, no hard purge)
    │   │   └── utils.py         # generate_object_key(), parse_object_key()
    │   │
    │   └── queue/
    │       ├── __init__.py
    │       ├── interface.py     # IQueueService (abstract)
    │       ├── nats_client.py   # NATSQueueService: publish, pull, ack, nak
    │       ├── subjects.py      # Subject patterns, DLQ subjects
    │       └── messages.py      # JobMessage dataclass
    │
    ├── core/
    │   ├── __init__.py
    │   ├── exceptions.py        # Base exceptions hierarchy
    │   ├── logging.py           # Structured JSON logger setup
    │   ├── lifespan.py          # ★ Application startup/shutdown:
    │   │                        #   startup: ensure NATS streams, MinIO buckets,
    │   │                        #            SQLite WAL, seed services
    │   │                        #   shutdown: close connections gracefully
    │   └── middleware.py        # Error handler, request timing, request logging
```

---

## 4. Worker Structure (Python - Processing Layer)

```
worker/
├── Dockerfile
├── requirements.txt
│
└── app/
    ├── __init__.py
    ├── main.py                  # Worker entry point, signal handlers, main loop
    ├── config.py                # Worker settings (NO MINIO_* vars)
    │
    ├── core/
    │   ├── __init__.py
    │   ├── worker.py            # OCRWorker class (poll → download → process → upload loop)
    │   ├── processor.py         # OCRProcessor: Tesseract wrapper
    │   ├── state.py             # WorkerState: tracking current job, progress
    │   └── shutdown.py          # ★ GracefulShutdown: SIGTERM/SIGINT handler
    │                            #   finish current job or NAK, cleanup, exit
    │
    ├── clients/
    │   ├── __init__.py
    │   ├── queue_client.py      # NATS pull subscriber (specific subject filter)
    │   ├── file_proxy_client.py # HTTP client: POST /internal/file-proxy/download|upload
    │   ├── orchestrator_client.py # HTTP client: PATCH /internal/jobs/:id/status
    │   └── heartbeat_client.py  # HTTP client: POST /internal/heartbeat (every 30s)
    │
    ├── handlers/
    │   ├── __init__.py
    │   ├── base.py              # BaseHandler (interface)
    │   └── text_raw.py          # TextRawHandler: Tesseract text extraction (Phase 1)
    │
    ├── utils/
    │   ├── __init__.py
    │   ├── errors.py            # classify_error() → retriable | non_retriable
    │   └── cleanup.py           # cleanup_local_files() — MUST run after every job
```

**Worker Constraints (unchanged):**
- **NO MINIO_* environment variables** — Worker cannot access storage directly
- **Has ACCESS_KEY** for File Proxy authentication
- **Does NOT retry** — reports errors to Orchestrator
- **Sends heartbeat** every 30 seconds
- **Cleans up local files** after each job
- **Handles SIGTERM gracefully** — finish or NAK current job before exit

---

## 5. Database Models (SQLite - Orchestration Layer)

```python
# backend/app/infrastructure/database/models.py

class User(Base):
    __tablename__ = "users"
    id: str                      # UUID, primary key
    email: str                   # Unique, validated
    password_hash: str           # bcrypt
    created_at: datetime
    deleted_at: datetime | None  # Soft delete

class Session(Base):
    __tablename__ = "sessions"
    id: str                      # UUID (token)
    user_id: str                 # FK -> users
    expires_at: datetime
    created_at: datetime

class Request(Base):
    __tablename__ = "requests"
    id: str                      # UUID
    user_id: str                 # FK -> users
    method: str                  # e.g., "text_raw"
    tier: int                    # e.g., 0
    output_format: str           # e.g., "txt", "json"
    retention_hours: int         # Per-request retention (for future use)
    status: str                  # Aggregated from jobs
    total_files: int
    completed_files: int         # Count of COMPLETED
    failed_files: int            # Count of FAILED + DEAD_LETTER
    created_at: datetime
    completed_at: datetime | None
    deleted_at: datetime | None

class Job(Base):
    __tablename__ = "jobs"
    id: str                      # UUID
    request_id: str              # FK -> requests
    file_id: str                 # FK -> files
    status: str                  # Full state machine
    method: str
    tier: int
    output_format: str
    retry_count: int             # 0-3
    max_retries: int             # Default 3
    error_history: str           # JSON array [{error, retriable, timestamp}]
    started_at: datetime | None
    completed_at: datetime | None
    processing_time_ms: int | None
    result_path: str | None      # Object key in results bucket (MinIO Edge)
    worker_id: str | None        # Which worker processed
    created_at: datetime
    deleted_at: datetime | None

class File(Base):
    __tablename__ = "files"
    id: str                      # UUID
    request_id: str              # FK -> requests
    original_name: str
    mime_type: str
    size_bytes: int
    page_count: int              # 1 for images
    object_key: str              # MinIO key in uploads bucket
    created_at: datetime
    deleted_at: datetime | None  # Soft delete only (no hard purge)

class Service(Base):
    __tablename__ = "services"
    id: str                      # e.g., "worker-ocr-text-tier0"
    access_key: str              # Unique, for File Proxy auth
    allowed_methods: str         # JSON array ["text_raw"]
    allowed_tiers: str           # JSON array [0]
    enabled: bool
    created_at: datetime

class Heartbeat(Base):
    __tablename__ = "heartbeats"
    id: int                      # Auto-increment
    service_id: str              # FK -> services
    status: str                  # idle, processing, uploading, error
    current_job_id: str | None
    files_completed: int
    files_total: int
    error_count: int
    received_at: datetime
```

**Changes from v2.0:**
- `File.purged_at` removed — no hard delete, files persist in MinIO indefinitely
- Soft delete (`deleted_at`) still supported for hiding from user, but file remains in storage

---

## 6. Docker Compose Services

> Tất cả services initialized bằng docker compose.
> Backend tự khởi tạo DB, NATS streams, MinIO buckets khi startup via lifespan events.
> Không cần external scripts.

```yaml
# docker-compose.yml

services:
  # === EDGE LAYER ===
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy

  # === EDGE + ORCHESTRATION (combined in Phase 1) ===
  backend:
    build: ./backend
    ports:
      - "8080:8080"
    environment:
      # Storage credentials (Edge layer — MinIO access)
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET_UPLOADS=uploads
      - MINIO_BUCKET_RESULTS=results
      - MINIO_BUCKET_DELETED=deleted
      # Queue (Orchestration layer)
      - NATS_URL=nats://nats:4222
      - NATS_STREAM_NAME=OCR_JOBS
      - NATS_DLQ_STREAM_NAME=OCR_DLQ
      # Database (Orchestration layer)
      - DATABASE_URL=sqlite:///./data/ocr_platform.db
      # Service registry (seed on startup)
      - SEED_SERVICES=worker-ocr-text-tier0:sk_local_text_tier0:text_raw:0
    depends_on:
      minio:
        condition: service_healthy
      nats:
        condition: service_started
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    ports:
      - "9000:9000"       # S3 API (Edge layer storage)
      - "9001:9001"       # Web Console (debug)
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - ./data/minio:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3

  # === ORCHESTRATION LAYER (infrastructure) ===
  nats:
    image: nats:latest
    ports:
      - "4222:4222"       # Client connections
      - "8222:8222"       # Monitoring
    command: ["--jetstream", "--store_dir=/data"]
    volumes:
      - ./data/nats:/data

  # === PROCESSING LAYER ===
  worker-ocr-text-tier0:
    build: ./worker
    environment:
      # Worker identity
      - WORKER_SERVICE_ID=worker-ocr-text-tier0
      - WORKER_ACCESS_KEY=sk_local_text_tier0
      - WORKER_FILTER_SUBJECT=ocr.text_raw.tier0
      # Connections (NO MINIO_* variables!)
      - NATS_URL=nats://nats:4222
      - FILE_PROXY_URL=http://backend:8080/internal/file-proxy
      - ORCHESTRATOR_URL=http://backend:8080/internal
      # Config
      - HEARTBEAT_INTERVAL_MS=30000
      - JOB_TIMEOUT_SECONDS=300
    depends_on:
      backend:
        condition: service_healthy
      nats:
        condition: service_started
    # Graceful shutdown: allow worker to finish current job
    stop_grace_period: 60s
```

**Startup Sequence:**
```
1. minio starts → healthcheck passes (S3 ready)
2. nats starts
3. backend starts → waits for minio healthy + nats started
   → lifespan startup:
     a. Connect SQLite, enable WAL mode, create tables
     b. Connect MinIO, ensure buckets exist (uploads, results, deleted)
     c. Connect NATS, ensure streams exist (OCR_JOBS, OCR_DLQ)
     d. Seed services from SEED_SERVICES env var
   → healthcheck passes (/health returns 200)
4. frontend starts → waits for backend healthy
5. worker starts → waits for backend healthy + nats started
   → connects NATS, subscribes to filter subject
   → starts heartbeat loop
   → starts job polling loop
```

---

## 7. Key Design Decisions (Aligned with SA v3.1)

| Decision | Rationale |
|----------|-----------|
| **MinIO in Edge Layer** | SA v3.1: "Edge layer lưu trữ file (object storage)" |
| **No hard delete** | Files persist in MinIO. Soft delete only (set `deleted_at`). Đơn giản cho Phase 1, user có thể download bất kỳ lúc nào. |
| **Docker compose init** | Fresh build — backend self-initializes via lifespan events. Không cần external scripts. |
| **UI dùng "Batch"** | Tự nhiên cho user. Backend giữ `requests` table, frontend mapping. |
| **Result Viewer split-panel** | Side-by-side comparison (source ↔ extracted text) thiết yếu cho QA. |
| **Presigned URLs cho download** | MinIO generate presigned URL → client download trực tiếp từ MinIO (Edge). Giảm load backend. |
| **Retry at Orchestrator** | Worker only reports errors; Orchestrator decides retry/fail/DLQ |
| **File Proxy in Backend** | Phase 1: module in Backend. Phase 2: separate service if needed |
| **Heartbeat table** | Track worker health, detect dead/stalled workers |
| **Full State Machine** | SUBMITTED → VALIDATING → QUEUED → PROCESSING → terminal states |
| **Graceful shutdown** | Worker handles SIGTERM, finishes current job before exit |
| **Health endpoint** | Backend /health checks DB + NATS + MinIO. Docker depends_on uses healthcheck. |

---

## 8. Import Dependencies Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND IMPORT FLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   api/endpoints/* (Edge Layer)                               │
│         │                                                    │
│         └──▶ modules/* (Orchestration Layer)                │
│                   │                                          │
│                   ├──▶ infrastructure/database/              │
│                   ├──▶ infrastructure/storage/ (→ Edge MinIO)│
│                   └──▶ infrastructure/queue/                 │
│                                                              │
│   api/internal/* (Worker ↔ Orchestration)                   │
│         │                                                    │
│         └──▶ modules/file_proxy/                            │
│                   │                                          │
│                   └──▶ infrastructure/storage/ (→ Edge MinIO)│
│                                                              │
│   core/lifespan.py (Application Lifecycle)                  │
│         │                                                    │
│         ├──▶ infrastructure/database/   (create tables)     │
│         ├──▶ infrastructure/storage/    (ensure buckets)    │
│         └──▶ infrastructure/queue/      (ensure streams)    │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      WORKER IMPORT FLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   main.py                                                    │
│         │                                                    │
│         ├──▶ core/shutdown.py  (signal handlers)            │
│         │                                                    │
│         └──▶ core/worker.py    (main loop)                  │
│                   │                                          │
│                   ├──▶ clients/queue_client.py (→ NATS)     │
│                   ├──▶ clients/file_proxy_client.py (→ Backend)│
│                   ├──▶ clients/orchestrator_client.py (→ Backend)│
│                   ├──▶ clients/heartbeat_client.py (→ Backend)│
│                   │                                          │
│                   └──▶ core/processor.py                    │
│                             │                                │
│                             └──▶ handlers/text_raw.py       │
│                                                              │
│   NOTE: Worker has NO storage imports.                       │
│         All file ops go through File Proxy HTTP client.      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. File Storage & Download Strategy (No Hard Delete)

**Nguyên tắc:** Files lưu vĩnh viễn trong MinIO (Edge layer). User có thể download bất kỳ lúc nào. Soft delete chỉ ẩn file khỏi UI, không xoá khỏi storage.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FILE LIFECYCLE (No Hard Delete)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Upload                                                                 │
│   Client ──POST /upload──▶ API (Edge) ──S3 Put──▶ MinIO uploads bucket  │
│                                                                          │
│   Processing                                                             │
│   Worker ──File Proxy──▶ MinIO uploads bucket (download source)         │
│   Worker ──File Proxy──▶ MinIO results bucket (upload result)           │
│                                                                          │
│   View Result                                                            │
│   Client ──GET /jobs/:id/result──▶ API reads text from MinIO results    │
│   (text content returned inline for Result Viewer display)               │
│                                                                          │
│   Download Original                                                      │
│   Client ──GET /files/:id/original-url──▶ API returns presigned URL     │
│   Client ──GET presigned URL──▶ MinIO uploads bucket (direct download)  │
│                                                                          │
│   Download Result                                                        │
│   Client ──GET /files/:id/result-url──▶ API returns presigned URL       │
│   Client ──GET presigned URL──▶ MinIO results bucket (direct download)  │
│                                                                          │
│   Soft Delete (user action)                                              │
│   Client ──DELETE /requests/:id──▶ API sets deleted_at in DB            │
│   File remains in MinIO. Hidden from UI queries. Can be recovered.      │
│                                                                          │
│   Recovery                                                               │
│   Client ──POST /requests/:id/recover──▶ API clears deleted_at          │
│   File reappears in UI.                                                  │
│                                                                          │
│   ★ No hard delete. No cleanup job. No purge.                           │
│   ★ Admin can manually clean MinIO via console (port 9001) if needed.   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Download Flow (kết hợp với Result Viewer UI):**

```
Result Viewer Page
    │
    ├── [View text inline]
    │   GET /api/v1/jobs/:id/result
    │   → Backend reads result file from MinIO results bucket
    │   → Returns text content as JSON { text: "...", lines: 22 }
    │   → ExtractedText component renders with line numbers
    │
    ├── [Click TXT button]
    │   GET /api/v1/files/:id/download?format=txt
    │   → Backend generates presigned URL for result file in MinIO
    │   → Returns URL, frontend triggers browser download
    │
    ├── [Click JSON button]
    │   GET /api/v1/files/:id/download?format=json
    │   → Backend wraps result in JSON structure:
    │     { filename, method, tier, processing_time, text, metadata }
    │   → Returns as downloadable JSON file
    │
    └── [Click Copy button]
        → Frontend copies ExtractedText content to clipboard
        → No backend call needed
```

---

## 10. Phase 1 Implementation Scope

### Must Have (Phase 1)
- [x] Layer separation: Edge (MinIO) / Orchestration / Processing
- [ ] Docker compose full stack with healthchecks
- [ ] Backend lifespan: auto-init DB + NATS streams + MinIO buckets + seed services
- [ ] All backend modules: auth, upload, job, file_proxy
- [ ] Health endpoint: GET /health
- [ ] Retry orchestrator (retry at Orchestration, not Worker)
- [ ] Full state machine: SUBMITTED → VALIDATING → QUEUED → PROCESSING → terminal states
- [ ] Dead Letter Queue (OCR_DLQ stream)
- [ ] Heartbeat protocol (worker → orchestrator)
- [ ] Worker with text_raw handler + graceful shutdown
- [ ] Result storage in MinIO + presigned URL download
- [ ] Frontend: Dashboard, Batches, Upload, Batch Detail, Result Viewer
- [ ] Result Viewer: split-panel, file navigation, TXT/JSON download, Copy

### Not in Scope (Phase 1)
- Hard delete / cleanup job — files persist in MinIO
- External init scripts — backend self-initializes
- Alembic migrations — fresh build, tables created on startup
- Billing module
- Notification system (SSE/WebSocket)
- Batch pull pattern for GPU workers
- Dynamic service registration (Admin dashboard)
- OAuth (Google, GitHub)
- Separate File Proxy service

---

*Changelog v2.0 → v2.1:*
- *Removed `scripts/` directory — docker compose + lifespan handles all initialization*
- *Removed `alembic/` — fresh build, no migration needed*
- *Removed `infrastructure/cleanup/` — no hard delete, files persist in MinIO*
- *Removed `File.purged_at` column — no hard purge*
- *Added `core/lifespan.py` — application startup/shutdown lifecycle*
- *Added `core/shutdown.py` to worker — graceful SIGTERM handling*
- *Added `health.py` endpoint — Docker healthcheck support*
- *Added `stop_grace_period: 60s` to worker in docker-compose*
- *Added healthchecks to docker-compose services*
- *Added `SEED_SERVICES` env var for service registration on startup*
- *Restructured frontend based on sample UI: Batch terminology, Result Viewer split-panel, file navigation, download options*
- *Added Section 9: File Storage & Download Strategy (No Hard Delete)*
- *Docker compose comment changed to `=== EDGE + ORCHESTRATION (combined in Phase 1) ===`*