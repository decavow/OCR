# OCR Platform Local MVP1 - Code Structure

> Version: 3.0 | Phase: Local MVP 1
> Aligned with: SA v3.1 + Actual Implementation

---

## 1. Root Directory Structure

```
ocr-platform/
├── docker-compose.yml          # Infrastructure + Backend (NO frontend/worker)
├── .env                         # Shared env vars (loaded by all compose files)
├── Makefile                     # Dev commands: up, down, workers, admin
│
├── 01_frontend/                 # React SPA (Edge Layer)
├── 02_backend/                  # FastAPI Monolith (Edge + Orchestration)
├── 03_worker/                   # OCR Workers (Processing Layer)
├── 00_test/                     # Test suites (backend, infras, worker)
├── 04_docs/                     # Documentation
├── data/                        # Persistent data (gitignored)
│   ├── ocr_fresh.db             # SQLite database (Orchestration)
│   ├── nats/                    # NATS JetStream data (Orchestration)
│   └── minio/                   # MinIO object storage (Edge)
├── collection_tool.py           # Utility script
├── ocr.md                       # Project notes
└── ocr_structure.md             # Structure reference
```

**Layer Mapping:**
```
┌─────────────────────────────────────────────────────────────┐
│  EDGE LAYER                                                  │
│  ├── 01_frontend/          (React SPA)                      │
│  ├── 02_backend/app/api/   (API Server - entry point)       │
│  └── MinIO container       (Object Storage)                 │
├─────────────────────────────────────────────────────────────┤
│  ORCHESTRATION LAYER                                         │
│  ├── 02_backend/app/modules/       (Auth, Upload, Job, FileProxy)│
│  ├── 02_backend/app/infrastructure/ (DB, Queue, Storage Client)│
│  └── NATS container                (Message Queue)          │
├─────────────────────────────────────────────────────────────┤
│  PROCESSING LAYER                                            │
│  └── 03_worker/            (OCR Workers - Multi-Engine)     │
│      ├── engines/paddle_text/  (PaddleOCR - GPU)            │
│      └── engines/tesseract/    (Tesseract - CPU)            │
└─────────────────────────────────────────────────────────────┘
```

**Deployment Model:**
- **Root docker-compose.yml**: Infrastructure (MinIO, NATS) + Backend only
- **Workers**: Each engine has its own `docker-compose.yml` in `03_worker/deploy/<name>/`
- **Frontend**: Runs separately (dev server or own compose)

---

## 2. Frontend Structure (React + TypeScript + Vite)

> UI layout: Sidebar navigation + main content area.
> Result Viewer: split-panel (original image + extracted text), file navigation, download options.
> Admin panel: Service Type management (approve/reject/disable).

```
01_frontend/
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
    │   └── index.ts             # API_BASE_URL from VITE_API_BASE_URL
    │
    ├── types/
    │   ├── index.ts             # Export all types
    │   ├── auth.ts              # User (incl. is_admin), LoginRequest, AuthResponse
    │   ├── batch.ts             # BatchStatus enum, Batch type, BatchListResponse
    │   ├── job.ts               # JobStatus enum (all states), Job, ErrorEntry, JobResult
    │   └── file.ts              # FileInfo, UploadFile, UploadConfig, PresignedUrlResponse
    │
    ├── api/
    │   ├── client.ts            # Axios instance + interceptors (Bearer token)
    │   ├── auth.ts              # login(), register(), logout(), getMe()
    │   ├── upload.ts            # uploadFiles(files, config)
    │   ├── batches.ts           # getBatches(), getBatch(id), cancelBatch(id)
    │   ├── jobs.ts              # getJob(id), getJobResult(id)
    │   ├── files.ts             # getOriginalUrl(id), getResultUrl(id), downloadResult(id, format)
    │   ├── services.ts          # Service-related API calls
    │   └── admin.ts             # Admin API: service type CRUD (approve, reject, disable, delete)
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
    │   │   ├── MainLayout.tsx       # Sidebar + Outlet (main content area)
    │   │   ├── Sidebar.tsx          # Navigation: Dashboard, Batches, Upload, Settings
    │   │   │                        # Admin section: Service Management (if is_admin)
    │   │   ├── AppHeader.tsx        # Exists but NOT used in MainLayout
    │   │   └── StatusBar.tsx        # Bottom bar (TODO/stub)
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
    │   │   ├── UploadConfig.tsx     # Output format selector, retention selector
    │   │   └── UploadProgress.tsx   # Upload progress bar
    │   │
    │   ├── batch/
    │   │   ├── BatchCard.tsx        # Batch summary: file count, status, date
    │   │   ├── BatchList.tsx        # List/grid of batches on Batches page
    │   │   ├── BatchStatus.tsx      # Status badge (all states incl. PARTIAL_SUCCESS)
    │   │   ├── BatchFileList.tsx    # Files within a batch (for batch detail view)
    │   │   └── CancelButton.tsx     # Cancel batch (only if QUEUED jobs remain)
    │   │
    │   ├── result/
    │   │   ├── ResultViewer.tsx      # Split-panel: OriginalPreview + ExtractedText
    │   │   ├── OriginalPreview.tsx   # Left panel: image/PDF preview
    │   │   ├── ExtractedText.tsx     # Right panel: OCR text with line numbers
    │   │   ├── ResultToolbar.tsx     # Download TXT, download JSON, Copy button
    │   │   ├── ResultMetadata.tsx    # Service, Tier, Processing Time badges
    │   │   ├── FileNavigator.tsx     # Breadcrumb + "< File 3 of 15 >" navigation
    │   │   └── TextCursor.tsx        # Bottom-right "Ln 22, Col 1" indicator
    │   │
    │   ├── job/
    │   │   ├── JobItem.tsx          # Job row in batch detail
    │   │   └── JobStatus.tsx        # All states including DEAD_LETTER
    │   │
    │   └── common/
    │       ├── Button.tsx
    │       ├── IconButton.tsx
    │       ├── Input.tsx
    │       ├── Select.tsx
    │       ├── Badge.tsx
    │       ├── Modal.tsx
    │       ├── Loading.tsx
    │       ├── Breadcrumb.tsx
    │       └── ErrorMessage.tsx
    │
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── RegisterPage.tsx
    │   ├── DashboardPage.tsx        # Overview: recent batches, quick stats
    │   ├── BatchesPage.tsx          # All batches list
    │   ├── BatchDetailPage.tsx      # Single batch: file list + statuses
    │   ├── ResultViewerPage.tsx     # Split-panel result viewer
    │   ├── UploadPage.tsx           # File upload + config
    │   ├── SettingsPage.tsx         # User settings
    │   ├── AdminServicesPage.tsx    # Admin: Service Type management (CRUD)
    │   └── NotFoundPage.tsx
    │
    ├── utils/
    │   ├── formatters.ts
    │   ├── validators.ts
    │   └── clipboard.ts
    │
    └── styles/
        ├── globals.css              # Dark theme CSS variables
        └── variables.css
```

**Routes (from App.tsx):**

| Route | Page | Auth | Admin |
|-------|------|------|-------|
| `/login` | LoginPage | Public | - |
| `/register` | RegisterPage | Public | - |
| `/`, `/dashboard` | DashboardPage | Protected | - |
| `/batches` | BatchesPage | Protected | - |
| `/batches/:id` | BatchDetailPage | Protected | - |
| `/batches/:batchId/files/:fileId` | ResultViewerPage | Protected | - |
| `/upload` | UploadPage | Protected | - |
| `/settings` | SettingsPage | Protected | - |
| `/admin/services` | AdminServicesPage | Protected | Admin only |

**Key Frontend Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Sidebar navigation (not top nav)** | MainLayout uses Sidebar + Outlet. AppHeader exists but is unused. |
| **UI dùng "Batch" thay vi "Request"** | Backend giữ `requests` table, frontend mapping Batch = Request. |
| **Admin-only Service Management** | Sidebar shows "Service Management" link only if `user.is_admin`. |
| **Result Viewer split-panel** | Side-by-side comparison (source ↔ extracted text) for QA. |
| **Dark theme** | CSS variables for dark theme in globals.css. |

---

## 3. Backend Structure (FastAPI + Python)

```
02_backend/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
│
└── app/
    ├── __init__.py
    ├── main.py                  # FastAPI app entry, lifespan events, routers mount
    ├── config.py                # Settings from env vars (Pydantic BaseSettings)
    ├── cli.py                   # CLI commands: create-admin, promote, demote
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
    │       │   ├── jobs.py      # GET /jobs/:id, /jobs/:id/result
    │       │   ├── files.py     # GET /files/:id/original-url, /files/:id/result-url
    │       │   ├── health.py    # GET /health (DB + NATS + MinIO readiness)
    │       │   ├── services.py  # GET /services (public service info)
    │       │   │
    │       │   └── admin/       # Admin-only endpoints
    │       │       ├── __init__.py
    │       │       ├── service_types.py      # CRUD for service types (approve, reject, disable)
    │       │       └── service_instances.py  # Manage service instances
    │       │
    │       ├── internal/        # Internal endpoints (Worker <-> Orchestration)
    │       │   ├── __init__.py
    │       │   ├── register.py      # POST /internal/register, /internal/deregister
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
    │           ├── job.py       # JobStatus enum, JobResponse
    │           ├── file.py      # FileResponse, PresignedUrlResponse
    │           ├── file_proxy.py # FileProxyDownloadReq, FileProxyUploadReq
    │           ├── heartbeat.py # HeartbeatPayload
    │           ├── register.py  # Worker registration schemas
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
    │   │   ├── heartbeat_monitor.py # HeartbeatMonitor: check_instances(), detect_stalled()
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
    │   │       ├── base.py          # BaseRepository (CRUD helpers)
    │   │       ├── user.py          # UserRepository
    │   │       ├── session.py       # SessionRepository
    │   │       ├── request.py       # RequestRepository
    │   │       ├── job.py           # JobRepository
    │   │       ├── file.py          # FileRepository
    │   │       ├── service.py       # ServiceRepository (legacy)
    │   │       ├── service_type.py  # ServiceTypeRepository
    │   │       ├── service_instance.py # ServiceInstanceRepository
    │   │       └── heartbeat.py     # HeartbeatRepository
    │   │
    │   ├── storage/
    │   │   ├── __init__.py
    │   │   ├── interface.py     # IStorageService (abstract)
    │   │   ├── minio_client.py  # MinIOStorageService: upload, download, presigned_url
    │   │   ├── exceptions.py    # StorageError, ObjectNotFoundError
    │   │   └── utils.py         # generate_object_key(), parse_object_key()
    │   │
    │   └── queue/
    │       ├── __init__.py
    │       ├── interface.py     # IQueueService (abstract)
    │       ├── nats_client.py   # NATSQueueService: publish, pull, ack, nak
    │       ├── subjects.py      # get_subject(), get_dlq_subject(), parse_subject()
    │       └── messages.py      # JobMessage dataclass (incl. object_key field)
    │
    ├── core/
    │   ├── __init__.py
    │   ├── exceptions.py        # Base exceptions hierarchy
    │   ├── logging.py           # Structured JSON logger setup
    │   ├── lifespan.py          # Application startup/shutdown:
    │   │                        #   startup: DB tables, MinIO buckets, NATS streams,
    │   │                        #            seed services (dev convenience)
    │   │                        #   shutdown: close connections gracefully
    │   └── middleware.py        # Error handler, request timing, request logging
```

**Router Mounting (from router.py):**

| Prefix | Module | Tags |
|--------|--------|------|
| `/auth` | `endpoints/auth.py` | auth |
| `/upload` | `endpoints/upload.py` | upload |
| `/requests` | `endpoints/requests.py` | requests |
| `/jobs` | `endpoints/jobs.py` | jobs |
| `/files` | `endpoints/files.py` | files |
| `/health` | `endpoints/health.py` | health |
| `/services` | `endpoints/services.py` | services |
| `/admin/service-types` | `endpoints/admin/service_types.py` | admin |
| `/admin/service-instances` | `endpoints/admin/service_instances.py` | admin |
| `/internal` | `internal/register.py` | internal |
| `/internal/file-proxy` | `internal/file_proxy.py` | internal |
| `/internal` | `internal/heartbeat.py` | internal |
| `/internal` | `internal/job_status.py` | internal |

> All routes are prefixed with `/api/v1` by `main.py`.
> Internal endpoints are at `/api/v1/internal/*` (NOT `/internal/*`).

---

## 4. Worker Structure (Python - Processing Layer)

```
03_worker/
├── Dockerfile               # GPU-capable (PaddleOCR + CUDA)
├── Dockerfile.cpu           # CPU-only (Tesseract)
├── requirements.txt
├── setup_gpu.sh             # GPU environment setup (Linux)
├── setup_gpu.bat            # GPU environment setup (Windows)
│
├── app/
│   ├── __init__.py
│   ├── main.py              # Worker entry point, signal handlers, main loop
│   ├── config.py            # Worker settings (NO MINIO_* vars)
│   │                        # Uses WORKER_SERVICE_TYPE + hostname for instance_id
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── worker.py        # OCRWorker class (poll -> download -> process -> upload)
│   │   ├── processor.py     # OCRProcessor: engine dispatching
│   │   ├── state.py         # WorkerState: tracking current job, progress
│   │   └── shutdown.py      # GracefulShutdown: SIGTERM/SIGINT handler
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── queue_client.py      # NATS pull subscriber (specific subject filter)
│   │   ├── file_proxy_client.py # HTTP client: POST /internal/file-proxy/download|upload
│   │   ├── orchestrator_client.py # HTTP client: PATCH /internal/jobs/:id/status
│   │   └── heartbeat_client.py  # HTTP client: POST /internal/heartbeat (every 30s)
│   │
│   ├── engines/                  # Multi-engine OCR support
│   │   ├── __init__.py
│   │   ├── base.py               # BaseEngine (interface)
│   │   │
│   │   ├── paddle_text/          # PaddleOCR engine (GPU)
│   │   │   ├── __init__.py
│   │   │   ├── handler.py        # TextRawHandler: PaddleOCR text extraction
│   │   │   ├── preprocessing.py  # Image preprocessing for Paddle
│   │   │   └── postprocessing.py # Result formatting
│   │   │
│   │   └── tesseract/            # Tesseract engine (CPU)
│   │       ├── __init__.py
│   │       ├── handler.py        # TextRawTesseractHandler: Tesseract extraction
│   │       ├── preprocessing.py  # Image preprocessing for Tesseract
│   │       └── postprocessing.py # Result formatting
│   │
│   └── utils/
│       ├── __init__.py
│       ├── errors.py            # classify_error() -> retriable | non_retriable
│       └── cleanup.py           # cleanup_local_files() -- MUST run after every job
│
└── deploy/                      # Per-engine deployment configs
    ├── paddle-text/             # PaddleOCR GPU deployment
    │   ├── docker-compose.yml   # Uses nvidia runtime, GPU resources
    │   └── .env.example         # WORKER_SERVICE_TYPE=ocr-paddle, etc.
    │
    └── tesseract-cpu/           # Tesseract CPU deployment
        ├── docker-compose.yml   # CPU-only, lighter resources
        └── .env.example         # WORKER_SERVICE_TYPE=ocr-tesseract, etc.
```

**Worker Identity Model:**
- `WORKER_SERVICE_TYPE`: The type of worker (e.g., `ocr-paddle`, `ocr-tesseract`)
- `WORKER_SERVICE_ID` (optional): Explicit instance ID override
- Auto-generated `instance_id`: `{service_type}-{hostname[:12]}` (Docker container ID)

**Worker Constraints (unchanged):**
- **NO MINIO_* environment variables** -- Worker cannot access storage directly
- **Has ACCESS_KEY** for File Proxy authentication (or empty if waiting for approval)
- **Does NOT retry** -- reports errors to Orchestrator
- **Sends heartbeat** every 30 seconds
- **Cleans up local files** after each job
- **Handles SIGTERM gracefully** -- finish or NAK current job before exit
- **Self-registers** on startup via POST /internal/register

---

## 5. Database Models (SQLite - Orchestration Layer)

```python
# 02_backend/app/infrastructure/database/models.py

class User(Base):
    __tablename__ = "users"
    id: str                      # UUID, primary key
    email: str                   # Unique, indexed
    password_hash: str           # bcrypt
    is_admin: bool               # Admin flag (default False)
    created_at: datetime
    deleted_at: datetime | None  # Soft delete

class Session(Base):
    __tablename__ = "sessions"
    id: str                      # UUID (primary key, NOT the token)
    user_id: str                 # FK -> users
    token: str                   # Unique, indexed (64 chars, used for auth)
    expires_at: datetime
    created_at: datetime

class Request(Base):
    __tablename__ = "requests"
    id: str                      # UUID
    user_id: str                 # FK -> users
    method: str                  # e.g., "text_raw"
    tier: int                    # e.g., 0
    output_format: str           # e.g., "txt", "json"
    retention_hours: int         # Default 168 (7 days)
    status: str                  # Aggregated from jobs
    total_files: int
    completed_files: int         # Count of COMPLETED
    failed_files: int            # Count of FAILED + DEAD_LETTER
    created_at: datetime
    expires_at: datetime | None  # Calculated expiry
    completed_at: datetime | None
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
    deleted_at: datetime | None

class Job(Base):
    __tablename__ = "jobs"
    id: str                      # UUID
    request_id: str              # FK -> requests
    file_id: str                 # FK -> files
    status: str                  # Full state machine
    method: str
    tier: int
    # NOTE: No output_format field on Job (lives on Request)
    retry_count: int             # 0-3
    max_retries: int             # Default 3
    error_history: str           # JSON array [{error, retriable, timestamp}]
    started_at: datetime | None
    completed_at: datetime | None
    processing_time_ms: int | None
    result_path: str | None      # Object key in results bucket (MinIO Edge)
    worker_id: str | None        # Which worker instance processed
    created_at: datetime
    deleted_at: datetime | None

# === Service Type / Instance Model (replaces legacy Service) ===

class ServiceTypeStatus:
    PENDING = "PENDING"          # Waiting for admin approval
    APPROVED = "APPROVED"        # Active, instances can process jobs
    DISABLED = "DISABLED"        # Temporarily paused
    REJECTED = "REJECTED"        # Permanently rejected (terminal)

class ServiceInstanceStatus:
    WAITING = "WAITING"          # Type not yet approved
    ACTIVE = "ACTIVE"            # Idle, ready for jobs
    PROCESSING = "PROCESSING"    # Currently processing a job
    DRAINING = "DRAINING"        # Finishing current job, won't take new
    DEAD = "DEAD"                # Shutdown/disconnected

class ServiceType(Base):
    __tablename__ = "service_types"
    id: str                      # e.g., "ocr-paddle", "ocr-tesseract"
    display_name: str            # e.g., "Vietnamese Text OCR"
    description: str | None      # Dev description
    status: str                  # ServiceTypeStatus (PENDING/APPROVED/DISABLED/REJECTED)
    access_key: str | None       # Unique, for File Proxy auth (generated on approve)
    allowed_methods: str         # JSON array ["text_raw"]
    allowed_tiers: str           # JSON array [0]
    engine_info: str | None      # JSON {name, version, capabilities}
    dev_contact: str | None      # Dev email/contact
    max_instances: int           # 0 = unlimited
    registered_at: datetime
    approved_at: datetime | None
    approved_by: str | None
    rejected_at: datetime | None
    rejection_reason: str | None

class ServiceInstance(Base):
    __tablename__ = "service_instances"
    id: str                      # e.g., "ocr-paddle-abc123def456"
    service_type_id: str         # FK -> service_types
    status: str                  # ServiceInstanceStatus
    registered_at: datetime
    last_heartbeat_at: datetime
    current_job_id: str | None
    instance_metadata: str | None # JSON {hostname, engine_version, ...}

class Heartbeat(Base):
    __tablename__ = "heartbeats"
    id: int                      # Auto-increment
    instance_id: str             # FK -> service_instances (NOT service_id)
    status: str                  # idle, processing, error
    current_job_id: str | None
    files_completed: int
    files_total: int
    error_count: int
    received_at: datetime

# DEPRECATED: Legacy Service model (kept for migration compatibility)
class Service(Base):
    __tablename__ = "services"
    # ... (legacy, use ServiceType + ServiceInstance instead)
```

**Key Changes from Planning v2.1:**
- `User.is_admin` added for admin role management
- `Session.token` is a separate field (Session.id is UUID, not the token)
- `Request.expires_at` added for expiry tracking
- `Request.retention_hours` defaults to 168 (7 days), not 24
- `Job.output_format` removed (lives on Request only)
- `Service` replaced by `ServiceType` + `ServiceInstance` two-level model
- `Heartbeat.instance_id` references `ServiceInstance` (not `service_id`)

---

## 6. Docker Compose Services

> Root docker-compose.yml contains **only infrastructure + backend**.
> Workers and frontend are deployed separately.
> Backend auto-initializes DB, NATS streams, MinIO buckets via lifespan events.

```yaml
# docker-compose.yml

services:
  # === INFRASTRUCTURE ===
  minio:
    image: minio/minio:latest
    container_name: ocr-minio
    ports:
      - "${MINIO_PORT}:9000"           # S3 API
      - "${MINIO_CONSOLE_PORT}:9001"   # Web Console
    environment:
      - MINIO_ROOT_USER=${MINIO_ROOT_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
    volumes:
      - ./data/minio:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    networks:
      - ocr-network

  nats:
    image: nats:latest
    container_name: ocr-nats
    ports:
      - "${NATS_PORT}:4222"            # Client connections
      - "${NATS_MONITOR_PORT}:8222"    # Monitoring
    command: ["--jetstream", "--store_dir=/data", "-m", "8222"]
    volumes:
      - ./data/nats:/data
    networks:
      - ocr-network

  # === BACKEND (Edge + Orchestration) ===
  backend:
    build: ./backend
    container_name: ocr-backend
    ports:
      - "${BACKEND_PORT}:8000"         # API on port 8000
    environment:
      - MINIO_ENDPOINT=${MINIO_ENDPOINT}         # ocr-minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - MINIO_BUCKET_UPLOADS=${MINIO_BUCKET_UPLOADS}
      - MINIO_BUCKET_RESULTS=${MINIO_BUCKET_RESULTS}
      - MINIO_BUCKET_DELETED=${MINIO_BUCKET_DELETED}
      - NATS_URL=${NATS_URL}                     # nats://ocr-nats:4222
      - DATABASE_URL=${DATABASE_URL}              # sqlite:///./data/ocr_fresh.db
      - SEED_SERVICES=${SEED_SERVICES}            # DEV: seed service types
    depends_on:
      minio:
        condition: service_healthy
      nats:
        condition: service_started
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    networks:
      - ocr-network

networks:
  ocr-network:
    name: ocr-network
    driver: bridge
```

**Worker Docker Compose (separate files):**

```yaml
# 03_worker/deploy/tesseract-cpu/docker-compose.yml (example)
services:
  ocr-tesseract:
    build:
      context: ../../
      dockerfile: Dockerfile.cpu
    env_file: ../../.env            # Loads shared env vars
    environment:
      - WORKER_SERVICE_TYPE=ocr-tesseract
      - WORKER_ACCESS_KEY=sk_local_tesseract   # DEV: pre-seeded key
    networks:
      - ocr-network

# 03_worker/deploy/paddle-text/docker-compose.yml (example)
services:
  ocr-paddle:
    build:
      context: ../../
      dockerfile: Dockerfile        # GPU Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]    # Nvidia GPU
    env_file: ../../.env
    environment:
      - WORKER_SERVICE_TYPE=ocr-paddle
      - WORKER_ACCESS_KEY=sk_local_paddle
    networks:
      - ocr-network
```

**Startup Sequence:**
```
1. minio starts -> healthcheck passes (S3 ready)
2. nats starts
3. backend starts -> waits for minio healthy + nats started
   -> lifespan startup:
     a. Connect SQLite, enable WAL mode, create tables
     b. Connect MinIO, ensure buckets exist (uploads, results, deleted)
     c. Connect NATS, ensure streams exist (OCR_JOBS, OCR_DLQ)
     d. Seed service types from SEED_SERVICES env var (dev convenience)
   -> healthcheck passes (/health returns 200)
4. Workers start (separately) -> connect to ocr-network
   -> POST /internal/register (self-registration)
   -> If type APPROVED: get access_key, start processing
   -> If type PENDING: wait for admin approval
   -> Start heartbeat loop
   -> Start job polling loop
```

**Makefile Commands:**

| Command | Description |
|---------|-------------|
| `make up` | Start infrastructure + backend |
| `make down` | Stop infrastructure + backend |
| `make build` | Build backend image |
| `make logs` | Tail backend logs |
| `make dev` | Development mode |
| `make worker-paddle` | Start PaddleOCR worker (GPU) |
| `make worker-tesseract` | Start Tesseract worker (CPU) |
| `make workers` | Start all workers |
| `make workers-down` | Stop all workers |
| `make create-admin EMAIL=... PASS=...` | Create admin user |
| `make promote EMAIL=...` | Promote user to admin |
| `make demote EMAIL=...` | Demote admin to user |
| `make all` | Start everything |
| `make all-down` | Stop everything |

---

## 7. Key Design Decisions (Aligned with SA v3.1 + Implementation)

| Decision | Rationale |
|----------|-----------|
| **MinIO in Edge Layer** | SA v3.1: "Edge layer lưu trữ file (object storage)" |
| **No hard delete** | Files persist in MinIO. Soft delete only (set `deleted_at`). |
| **Docker compose split** | Root compose = infra + backend. Workers = separate compose per engine. |
| **ServiceType + ServiceInstance** | Two-level model: admin manages types, system manages instances. |
| **Worker self-registration** | Workers POST /internal/register on startup. Admin approves types. |
| **Multi-engine support** | PaddleOCR (GPU) + Tesseract (CPU) with separate deploy configs. |
| **Internal API under /api/v1** | All routes (public + internal) share same `/api/v1` prefix. |
| **Retry at Orchestrator** | Worker only reports errors; Orchestrator decides retry/fail/DLQ. |
| **Heartbeat via instance_id** | Heartbeat tracks individual instances, not service types. |
| **Admin CLI tools** | Makefile targets: create-admin, promote, demote via cli.py. |
| **Container name networking** | Uses `ocr-minio`, `ocr-nats`, `ocr-backend` for cross-compose DNS. |
| **Shared .env** | Single `.env` file loaded by root compose and all worker compose files. |

---

## 8. Import Dependencies Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND IMPORT FLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   api/endpoints/* (Edge Layer)                               │
│         │                                                    │
│         └──> modules/* (Orchestration Layer)                 │
│                   │                                          │
│                   ├──> infrastructure/database/               │
│                   ├──> infrastructure/storage/ (-> Edge MinIO)│
│                   └──> infrastructure/queue/                  │
│                                                              │
│   api/endpoints/admin/* (Admin - requires is_admin)          │
│         │                                                    │
│         └──> infrastructure/database/repositories/           │
│              (service_type, service_instance)                 │
│                                                              │
│   api/internal/* (Worker <-> Orchestration)                  │
│         │                                                    │
│         ├──> modules/file_proxy/                             │
│         │         └──> infrastructure/storage/ (-> Edge MinIO)│
│         │                                                    │
│         └──> infrastructure/database/repositories/           │
│              (service_type, service_instance for register)    │
│                                                              │
│   core/lifespan.py (Application Lifecycle)                   │
│         │                                                    │
│         ├──> infrastructure/database/   (create tables)      │
│         ├──> infrastructure/storage/    (ensure buckets)     │
│         └──> infrastructure/queue/      (ensure streams)     │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      WORKER IMPORT FLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   main.py                                                    │
│         │                                                    │
│         ├──> core/shutdown.py  (signal handlers)             │
│         │                                                    │
│         └──> core/worker.py    (main loop)                   │
│                   │                                          │
│                   ├──> clients/queue_client.py (-> NATS)     │
│                   ├──> clients/file_proxy_client.py (-> Backend)│
│                   ├──> clients/orchestrator_client.py (-> Backend)│
│                   ├──> clients/heartbeat_client.py (-> Backend)│
│                   │                                          │
│                   └──> core/processor.py                     │
│                             │                                │
│                             ├──> engines/paddle_text/handler.py│
│                             └──> engines/tesseract/handler.py │
│                                                              │
│   NOTE: Worker has NO storage imports.                       │
│         All file ops go through File Proxy HTTP client.      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. File Storage & Download Strategy (No Hard Delete)

**Unchanged from v2.1** -- Files persist in MinIO. Soft delete only. Presigned URLs for download.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FILE LIFECYCLE (No Hard Delete)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Upload                                                                 │
│   Client --POST /upload--> API (Edge) --S3 Put--> MinIO uploads bucket  │
│                                                                          │
│   Processing                                                             │
│   Worker --File Proxy--> MinIO uploads bucket (download source)         │
│   Worker --File Proxy--> MinIO results bucket (upload result)           │
│                                                                          │
│   Download (via presigned URL)                                           │
│   Client --GET /files/:id/original-url--> presigned URL --> MinIO       │
│   Client --GET /files/:id/result-url--> presigned URL --> MinIO         │
│                                                                          │
│   Soft Delete (user action)                                              │
│   Client --DELETE--> API sets deleted_at in DB                           │
│   File remains in MinIO, hidden from UI.                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Phase 1 Implementation Scope

### Implemented
- [x] Layer separation: Edge (MinIO) / Orchestration / Processing
- [x] Docker compose: infra + backend (workers separate)
- [x] Backend lifespan: auto-init DB + NATS + MinIO + seed services
- [x] All backend modules: auth, upload, job, file_proxy
- [x] Health endpoint: GET /health
- [x] Full state machine: SUBMITTED -> VALIDATING -> QUEUED -> PROCESSING -> terminal
- [x] Retry orchestrator (retry at Orchestration, not Worker)
- [x] Dead Letter Queue (OCR_DLQ stream)
- [x] Heartbeat protocol (instance -> orchestrator)
- [x] Multi-engine worker: PaddleOCR (GPU) + Tesseract (CPU)
- [x] Worker self-registration (POST /internal/register)
- [x] Admin panel: Service Type management (approve/reject/disable)
- [x] Admin CLI: create-admin, promote, demote
- [x] Frontend: Dashboard, Batches, Upload, Batch Detail, Result Viewer
- [x] Result Viewer: split-panel, file navigation, TXT/JSON download, Copy
- [x] ServiceType + ServiceInstance two-level model
- [x] Sidebar navigation with admin-only section

### Not in Scope (Phase 1)
- Hard delete / cleanup job
- External init scripts (backend self-initializes)
- Alembic migrations (fresh build)
- Billing module
- Notification system (SSE/WebSocket)
- OAuth (Google, GitHub)
- Separate File Proxy service

---

*Changelog v2.1 -> v3.0:*
- *Directories renamed: `frontend/` -> `01_frontend/`, `backend/` -> `02_backend/`, `worker/` -> `03_worker/`, `docs/` -> `04_docs/`*
- *Added `00_test/` directory for test suites*
- *Backend port changed: 8080 -> 8000*
- *Database file: `ocr_platform.db` -> `ocr_fresh.db`*
- *Internal API path: `/internal/*` -> `/api/v1/internal/*`*
- *`Service` model replaced by `ServiceType` + `ServiceInstance` two-level model*
- *Worker `handlers/` replaced by `engines/` with multi-engine support (PaddleOCR + Tesseract)*
- *Worker deploy model: each engine has own `docker-compose.yml` in `deploy/`*
- *Frontend/workers removed from root docker-compose.yml*
- *Container names prefixed: `ocr-minio`, `ocr-nats`, `ocr-backend`*
- *Added admin panel: `AdminServicesPage.tsx`, admin API endpoints*
- *Added `User.is_admin`, `Session.token`, `Request.expires_at` fields*
- *Removed `Job.output_format` (lives on Request)*
- *Added worker self-registration (POST /internal/register + /deregister)*
- *Added `cli.py` + Makefile admin commands (create-admin, promote, demote)*
- *Network: named `ocr-network` with bridge driver*
- *Shared `.env` file loaded by all compose files*
