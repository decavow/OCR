# OCR Platform Local MVP1 - Layer Processing Logic

> Version: 3.0 | Phase: Local MVP 1
> Aligned with: SA v3.1 + Actual Implementation

---

## 1. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM LAYERS OVERVIEW                                   │
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐ │
│  │                              EDGE LAYER                                       │ │
│  │            "Cổng vào + Kho chứa" - Không xử lý logic nghiệp vụ               │ │
│  │                                                                               │ │
│  │   ┌──────────────┐         ┌──────────────────────────────────────────┐     │ │
│  │   │   Frontend   │<--HTTP-->│            API Server                    │     │ │
│  │   │   (React)    │         │     (FastAPI - port 8000)                │     │ │
│  │   │  Sidebar nav │         │     /api/v1/* (all routes)               │     │ │
│  │   └──────────────┘         └──────────────┬───────────────────────────┘     │ │
│  │                                           │                                  │ │
│  │   ┌───────────────────────────────────────┼────────────────────────────┐    │ │
│  │   │              OBJECT STORAGE (MinIO)   │                             │    │ │
│  │   │   Buckets: uploads | results | deleted│ <-- API Server has creds   │    │ │
│  │   └───────────────────────────────────────┼────────────────────────────┘    │ │
│  │                                           │                                  │ │
│  └───────────────────────────────────────────┼──────────────────────────────────┘ │
│                                              │ internal calls                     │
│                                              │ + storage credentials              │
│  ┌───────────────────────────────────────────┼──────────────────────────────────┐ │
│  │                    ORCHESTRATION LAYER    │                                   │ │
│  │               "Bộ não điều phối"          v                                   │ │
│  │                                                                               │ │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌─────────────────────────┐    │ │
│  │   │  Auth   │  │ Upload  │  │     Job     │  │      File Proxy         │    │ │
│  │   │ Module  │  │ Module  │  │   Module    │  │       Module            │    │ │
│  │   │         │  │         │  │             │  │                         │    │ │
│  │   │Register │  │Validate │  │Create req   │  │Auth service (access_key)│    │ │
│  │   │Login    │  │Store    │  │Create jobs  │  │ACL check (ServiceType)  │    │ │
│  │   │Session  │  │(->Edge) │  │Retry logic  │  │Stream files (->Edge)    │    │ │
│  │   │is_admin │  │         │  │Heartbeat mon│  │                         │    │ │
│  │   └────┬────┘  └────┬────┘  └──────┬──────┘  └───────────┬─────────────┘    │ │
│  │        │            │              │                     │                   │ │
│  │   ┌────┴────────────┴──────────────┴─────────────────────┴──────────────┐   │ │
│  │   │                   ORCHESTRATION INFRASTRUCTURE                       │   │ │
│  │   │                                                                      │   │ │
│  │   │   ┌──────────────────────┐       ┌───────────────────────────────┐  │   │ │
│  │   │   │       SQLite         │       │      NATS JETSTREAM           │  │   │ │
│  │   │   │      DATABASE        │       │                               │  │   │ │
│  │   │   │                      │       │  Stream: OCR_JOBS             │  │   │ │
│  │   │   │ users, sessions      │       │  Subjects: ocr.{method}.tier{n}│ │   │ │
│  │   │   │ requests, jobs       │       │                               │  │   │ │
│  │   │   │ files                │       │  Stream: OCR_DLQ              │  │   │ │
│  │   │   │ service_types        │       │  Subjects: dlq.{method}.tier{n}│ │   │ │
│  │   │   │ service_instances    │       │                               │  │   │ │
│  │   │   │ heartbeats           │       │                               │  │   │ │
│  │   │   └──────────────────────┘       └───────────────┬───────────────┘  │   │ │
│  │   └──────────────────────────────────────────────────┼───────────────────┘   │ │
│  │                                                      │                       │ │
│  └──────────────────────────────────────────────────────┼───────────────────────┘ │
│                                                         │ pull (specific subject)  │
│                                                         v                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                          PROCESSING LAYER                                    │  │
│  │              "Nhà máy xử lý" - Multi-engine, NO business logic              │  │
│  │                                                                              │  │
│  │   ┌───────────────────────────────────────────────────────────────────────┐  │  │
│  │   │                     OCR WORKERS (Multiple Engines)                     │  │  │
│  │   │        (has access_key, NO storage credentials)                       │  │  │
│  │   │                                                                       │  │  │
│  │   │   ┌──────────────────────┐    ┌──────────────────────┐               │  │  │
│  │   │   │  PaddleOCR Worker   │    │  Tesseract Worker    │               │  │  │
│  │   │   │  (GPU - Dockerfile) │    │  (CPU - Dockerfile.cpu)│              │  │  │
│  │   │   │  deploy/paddle-text/ │    │  deploy/tesseract-cpu/│              │  │  │
│  │   │   └──────────────────────┘    └──────────────────────┘               │  │  │
│  │   │                                                                       │  │  │
│  │   │   Shared Flow:                                                        │  │  │
│  │   │   ┌────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────────┐      │  │  │
│  │   │   │REGISTER│->│  POLL    │->│ DOWNLOAD  │->│  PROCESS        │      │  │  │
│  │   │   │on start│  │  QUEUE   │  │via FILE   │  │(engine-specific)│      │  │  │
│  │   │   │        │  │ (NATS)   │  │  PROXY    │  │                 │      │  │  │
│  │   │   └────────┘  └──────────┘  └───────────┘  └────────┬────────┘      │  │  │
│  │   │                                                      │               │  │  │
│  │   │                                                ┌─────┴──────┐        │  │  │
│  │   │                                             Success      Error       │  │  │
│  │   │                                                │           │         │  │  │
│  │   │                                                v           v         │  │  │
│  │   │                                          ┌──────────┐ ┌──────────┐  │  │  │
│  │   │                                          │UPLOAD via│ │Report to │  │  │  │
│  │   │                                          │FILE PROXY│ │ORCHESTR. │  │  │  │
│  │   │                                          └──────────┘ └──────────┘  │  │  │
│  │   │                                                                       │  │  │
│  │   │   HEARTBEAT --> POST /api/v1/internal/heartbeat every 30s            │  │  │
│  │   │   CLEANUP   --> delete ALL local files after processing              │  │  │
│  │   └───────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                              │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  LAYER COMMUNICATION RULES:                                                         │
│  + Client <-> Edge (HTTP)                                                           │
│  + Edge <-> Orchestration (internal calls, storage creds)                           │
│  + Orchestration <-> Processing (Queue, File Proxy API, Heartbeat API)              │
│  x Processing -> Edge (FORBIDDEN - must go through Orchestration)                   │
│                                                                                     │
│  FILE ACCESS FLOW:                                                                  │
│  Worker -> File Proxy (Orch) -> MinIO (Edge)                                        │
│  Each step is between adjacent layers                                               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Edge Layer Processing

### 2.1 Frontend Logic Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FRONTEND HIGH-LEVEL FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                                                           │
│   │    START    │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                   │
│          v                                                                   │
│   ┌─────────────┐     No      ┌─────────────┐                              │
│   │Has Session? │────────────>│  Login/     │                              │
│   └──────┬──────┘             │  Register   │                              │
│          │ Yes                 └──────┬──────┘                              │
│          │                            │ Success                             │
│          │<───────────────────────────┘                                     │
│          v                                                                   │
│   ┌─────────────────────────────────────────────────┐                      │
│   │  Sidebar Navigation (MainLayout)                 │                      │
│   │  ├── Dashboard        (/dashboard)               │                      │
│   │  ├── Batches          (/batches)                 │                      │
│   │  ├── Upload           (/upload)                  │                      │
│   │  ├── Settings         (/settings)                │                      │
│   │  └── [Admin] Service Management (/admin/services)│                      │
│   └─────────────────────────┬───────────────────────┘                      │
│                             │                                               │
│          ┌──────────────────┼──────────────────────┐                       │
│          │                  │                      │                       │
│          v                  v                      v                       │
│   ┌──────────┐     ┌──────────────┐     ┌──────────────┐                  │
│   │Dashboard │     │Upload Page   │     │Admin Page    │                  │
│   │- Recent  │     │- Drag-drop   │     │- Service list│                  │
│   │  batches │     │- Config      │     │- Approve/    │                  │
│   │- Stats   │     │- Submit      │     │  Reject/     │                  │
│   └──────────┘     └──────┬───────┘     │  Disable     │                  │
│                           │              └──────────────┘                  │
│                           v                                                │
│                    POST /api/v1/upload                                      │
│                           │                                                │
│                           v                                                │
│                    ┌──────────────────────┐                                │
│                    │ Batch Detail Page    │                                │
│                    │ Poll GET /requests/id│                                │
│                    │ Show job statuses    │                                │
│                    │ Cancel button        │                                │
│                    └──────────┬───────────┘                                │
│                               │                                            │
│                      Terminal status reached                               │
│                               │                                            │
│                               v                                            │
│                    ┌──────────────────────┐                                │
│                    │ Result Viewer Page   │                                │
│                    │ Split-panel view     │                                │
│                    │ Download/Copy        │                                │
│                    └─────────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 API Server Logic Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API SERVER REQUEST FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   HTTP Request                                                               │
│        │                                                                     │
│        v                                                                     │
│   ┌─────────────────┐                                                       │
│   │   Middleware    │                                                       │
│   │  - Logging      │                                                       │
│   │  - Error handler│                                                       │
│   │  - Timing       │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            v                                                                 │
│   ┌─────────────────┐                                                       │
│   │   Router        │                                                       │
│   │  /api/v1/*      │ ---- User endpoints (session auth)                   │
│   │  /api/v1/admin/*│ ---- Admin endpoints (session auth + is_admin)       │
│   │  /api/v1/internal/*│ - Worker endpoints (access_key auth)              │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            v                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        AUTHENTICATION                                │   │
│   │                                                                      │   │
│   │   User Endpoints (/api/v1/*)                                        │   │
│   │   ├── Extract token from Authorization header (Bearer)              │   │
│   │   ├── Validate session.token in database                            │   │
│   │   └── Return 401 if invalid/expired                                 │   │
│   │                                                                      │   │
│   │   Admin Endpoints (/api/v1/admin/*)                                 │   │
│   │   ├── Same as user auth above                                       │   │
│   │   ├── Check user.is_admin = true                                    │   │
│   │   └── Return 403 if not admin                                       │   │
│   │                                                                      │   │
│   │   Internal Endpoints (/api/v1/internal/*)                           │   │
│   │   ├── Extract access_key from X-Access-Key header                   │   │
│   │   ├── Validate in service_types table (status = APPROVED)           │   │
│   │   └── Return 401 if invalid/not approved                            │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│            │                                                                 │
│            v                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       ENDPOINT HANDLER                               │   │
│   │                                                                      │   │
│   │   1. Validate request (Pydantic schema)                             │   │
│   │   2. Call Orchestration module (business logic)                     │   │
│   │   3. Return response (Pydantic schema)                              │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Orchestration Layer Processing

### 3.1 Auth Module Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTH MODULE FLOWS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  REGISTER: email, password                                                  │
│       │                                                                      │
│       ├── Check email unique -> Error if exists                             │
│       ├── Hash password (bcrypt)                                            │
│       ├── INSERT INTO users (is_admin = false)                              │
│       ├── Create session (generate token, separate from session.id)         │
│       └── Return { user, token, expires_at }                                │
│                                                                              │
│  LOGIN: email, password                                                     │
│       │                                                                      │
│       ├── Find user by email -> Error if not found                          │
│       ├── Verify password (bcrypt) -> Error if mismatch                     │
│       ├── Create new session (token = 64 random chars)                      │
│       └── Return { user, token, expires_at }                                │
│                                                                              │
│  VALIDATE SESSION (Dependency):                                             │
│       │                                                                      │
│       ├── Find session by token (NOT by id) -> 401 if not found             │
│       ├── Check session.is_expired -> 401 if expired                        │
│       └── Return User object (includes is_admin flag)                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Upload Module Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UPLOAD MODULE FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Input: files[], user_id, method="text_raw", tier=0,                       │
│          output_format="txt", retention_hours=168                           │
│         │                                                                    │
│         v                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    BATCH VALIDATION                                  │   │
│   │                                                                      │   │
│   │   Check: count <= 20, total size <= 50MB                             │   │
│   │   Fail -> 400 Error                                                  │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               ALL-FILES VALIDATION (validate ALL before storing)     │   │
│   │                                                                      │   │
│   │   for each file:                                                     │   │
│   │       - Check MIME type + magic bytes (PNG, JPEG, PDF)              │   │
│   │       - Check size <= 10MB                                           │   │
│   │       - If invalid -> add to skipped_files[], continue              │   │
│   │       - If valid -> add to valid_files[]                             │   │
│   │                                                                      │   │
│   │   NOTE: All files validated FIRST, then records created.            │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │         CREATE REQUEST + STORE FILES + CREATE JOBS + PUBLISH        │   │
│   │                                                                      │   │
│   │   1. INSERT INTO requests:                                          │   │
│   │      (user_id, method, tier, output_format, retention_hours,        │   │
│   │       status=PROCESSING, total_files, expires_at calculated)        │   │
│   │                                                                      │   │
│   │   2. For each valid_file:                                           │   │
│   │      a. Generate object_key (via storage utils)                     │   │
│   │      b. Upload to MinIO (Edge): bucket=uploads                     │   │
│   │      c. INSERT INTO files (request_id, original_name, object_key)   │   │
│   │      d. INSERT INTO jobs:                                           │   │
│   │         (request_id, file_id, status=SUBMITTED, method, tier,       │   │
│   │          retry_count=0, max_retries=3)                              │   │
│   │      e. Publish to NATS: ocr.{method}.tier{tier}                   │   │
│   │         JobMessage includes object_key field                        │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   Output: { request_id, total_files, valid_files, skipped_files[] }         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Job Module Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB MODULE FLOWS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ GET REQUEST STATUS                                                      ││
│  │                                                                          ││
│  │   1. Find request by ID, check owner (user_id match)                   ││
│  │   2. Load all jobs for request                                          ││
│  │   3. Aggregate status:                                                   ││
│  │                                                                          ││
│  │      ┌─────────────────────────────────────────────────────────────┐    ││
│  │      │ any(QUEUED, PROCESSING, RETRYING) -> PROCESSING             │    ││
│  │      │ all(COMPLETED)                     -> COMPLETED              │    ││
│  │      │ all(FAILED, DEAD_LETTER, REJECTED) -> FAILED                 │    ││
│  │      │ mix(COMPLETED + FAILED/DL/REJECTED)-> PARTIAL_SUCCESS        │    ││
│  │      │ all(CANCELLED)                     -> CANCELLED              │    ││
│  │      └─────────────────────────────────────────────────────────────┘    ││
│  │                                                                          ││
│  │   4. Return { request, jobs[], status, progress }                       ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ CANCEL REQUEST (only if jobs are QUEUED)                                ││
│  │                                                                          ││
│  │   For each job where status = QUEUED:                                   ││
│  │       Update status -> CANCELLED                                        ││
│  │                                                                          ││
│  │   Jobs already PROCESSING cannot be cancelled                           ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Retry Orchestrator Flow (Retry at Orchestration Layer)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RETRY ORCHESTRATOR FLOW                                  │
│                   (Retry logic in Orchestration, NOT Worker)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker reports error via PATCH /api/v1/internal/jobs/{id}/status          │
│   Body: { status: "error", error: "...", retriable: true/false }            │
│         │                                                                    │
│         v                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    ORCHESTRATOR RECEIVES ERROR                       │   │
│   │                                                                      │   │
│   │   1. Load job from database                                         │   │
│   │   2. Append error to error_history                                  │   │
│   │   3. Check: is retriable?                                           │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│         ┌──────┴──────┐                                                      │
│      retriable     non-retriable                                             │
│         │               │                                                    │
│         v               v                                                    │
│   ┌───────────────┐ ┌───────────────────────────────────────────────────┐   │
│   │Check retry_cnt│ │ Update status -> FAILED                            │   │
│   │< max_retries? │ │ Increment request.failed_files                    │   │
│   └───────┬───────┘ │ Check if request complete -> update request.status │   │
│           │         └───────────────────────────────────────────────────┘   │
│     ┌─────┴─────┐                                                            │
│   Yes          No                                                            │
│     │           │                                                            │
│     v           v                                                            │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │ RETRY PATH                        │ DEAD LETTER PATH                  │ │
│   │                                   │                                   │ │
│   │ 1. Update status -> RETRYING      │ 1. Update status -> DEAD_LETTER   │ │
│   │ 2. Increment retry_count          │ 2. Move to DLQ:                   │ │
│   │ 3. Calculate delay:               │    Publish to dlq.{method}.tier{n}│ │
│   │    delay = 1s x 2^retry_count     │ 3. Increment request.failed_files │ │
│   │    (1s, 2s, 4s)                   │ 4. Update request status          │ │
│   │ 4. Wait delay (scheduled task)    │                                   │ │
│   │ 5. Update status -> QUEUED        │                                   │ │
│   │ 6. Re-publish to queue:           │                                   │ │
│   │    ocr.{method}.tier{tier}        │                                   │ │
│   │                                   │                                   │ │
│   └───────────────────────────────────┴───────────────────────────────────┘ │
│                                                                              │
│   KEY POINT: Worker does NOT retry. Worker only reports error.              │
│   All retry decisions are made by Orchestrator.                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.5 Heartbeat Monitor Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HEARTBEAT MONITOR FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker sends heartbeat every 30 seconds:                                  │
│                                                                              │
│   POST /api/v1/internal/heartbeat                                           │
│   {                                                                          │
│     "instance_id": "ocr-paddle-abc123",                                     │
│     "access_key": "sk_xxx",                                                 │
│     "status": "processing",        // idle | processing | error             │
│     "current_job_id": "job_abc",   // null if idle                         │
│     "progress": {                                                           │
│       "files_completed": 2,                                                 │
│       "files_total": 5                                                      │
│     },                                                                       │
│     "error_count": 0                                                        │
│   }                                                                          │
│         │                                                                    │
│         v                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   ORCHESTRATOR HEARTBEAT HANDLER                     │   │
│   │                                                                      │   │
│   │   1. Validate access_key (ServiceType.status = APPROVED)            │   │
│   │   2. Update service_instances.last_heartbeat_at                     │   │
│   │   3. INSERT INTO heartbeats (all fields + received_at = now())      │   │
│   │   4. Return 200 OK                                                  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               HEARTBEAT MONITOR (Background Task)                    │   │
│   │                        Runs every 30 seconds                         │   │
│   │                                                                      │   │
│   │   For each registered service instance:                             │   │
│   │       │                                                              │   │
│   │       ├── Get latest heartbeat from instance                        │   │
│   │       │                                                              │   │
│   │       ├── No heartbeat for > HEARTBEAT_TIMEOUT (90s)?              │   │
│   │       │   └── Mark instance as DEAD                                 │   │
│   │       │       If instance had current_job_id:                      │   │
│   │       │           -> Return job to QUEUED (for another worker)     │   │
│   │       │                                                              │   │
│   │       ├── status = "error" continuously?                           │   │
│   │       │   └── Mark instance as UNHEALTHY                           │   │
│   │       │                                                              │   │
│   │       └── progress unchanged for > JOB_TIMEOUT?                    │   │
│   │           └── Mark instance as STALLED                             │   │
│   │               Return job to QUEUED                                  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 File Proxy Service Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FILE PROXY SERVICE FLOWS                               │
│                                                                              │
│   File Proxy is in ORCHESTRATION layer.                                     │
│   It calls EDGE layer (MinIO) using storage credentials.                    │
│   ACL validated against ServiceType (APPROVED status + allowed methods/tiers)│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ DOWNLOAD FILE (Worker requests file)                                    ││
│  │                                                                          ││
│  │   POST /api/v1/internal/file-proxy/download                             ││
│  │   Headers: X-Access-Key: {worker_access_key}                            ││
│  │   Body: { "job_id": "job_abc" }                                         ││
│  │         │                                                               ││
│  │         v                                                               ││
│  │   1. Validate access_key -> 401 if invalid                               ││
│  │   2. Find ServiceType by access_key (must be APPROVED)                  ││
│  │   3. Find job by job_id                                                 ││
│  │   4. Check ACL: service can access this job's file?                     ││
│  │      (job.method in service_type.allowed_methods &&                     ││
│  │       job.tier in service_type.allowed_tiers)                           ││
│  │      -> 403 if denied                                                    ││
│  │   5. Get file.object_key from database                                  ││
│  │   6. Call MinIO (Edge): GetObject(bucket=uploads, key)                  ││
│  │   7. Stream file to Worker                                              ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ UPLOAD RESULT (Worker uploads OCR result)                               ││
│  │                                                                          ││
│  │   POST /api/v1/internal/file-proxy/upload                               ││
│  │   Headers: X-Access-Key: {worker_access_key}                            ││
│  │   Body: multipart/form-data { job_id, file, processing_time_ms }        ││
│  │         │                                                               ││
│  │         v                                                               ││
│  │   1. Validate access_key -> 401 if invalid                               ││
│  │   2. Check ACL for job                                                  ││
│  │   3. Generate result key: results/{request_id}/{job_id}.{format}        ││
│  │   4. Call MinIO (Edge): PutObject(bucket=results, key, file)            ││
│  │   5. Return { result_path: key }                                        ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.7 Worker Registration Flow (NEW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WORKER REGISTRATION FLOW                                │
│             (Workers self-register on startup)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker starts up:                                                         │
│                                                                              │
│   POST /api/v1/internal/register                                            │
│   {                                                                          │
│     "service_type": "ocr-paddle",                                           │
│     "instance_id": "ocr-paddle-abc123",                                     │
│     "display_name": "PaddleOCR Text Raw",                                   │
│     "description": "GPU-accelerated Vietnamese OCR",                        │
│     "dev_contact": "dev@example.com",                                       │
│     "allowed_methods": ["text_raw"],                                        │
│     "allowed_tiers": [0],                                                   │
│     "access_key": "sk_local_paddle" (optional, for seeded services)         │
│   }                                                                          │
│         │                                                                    │
│         v                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   ORCHESTRATOR REGISTER HANDLER                      │   │
│   │                                                                      │   │
│   │   1. Check if ServiceType exists for this service_type               │   │
│   │                                                                      │   │
│   │   ┌──── Type NOT exists ────────────────────────────────────────┐   │   │
│   │   │ Create new ServiceType (status = PENDING)                    │   │   │
│   │   │ Create ServiceInstance (status = WAITING)                    │   │   │
│   │   │ Return { status: "waiting", message: "Pending admin approval"}│   │   │
│   │   └──────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌──── Type exists, status = APPROVED ─────────────────────────┐   │   │
│   │   │ Create ServiceInstance (status = ACTIVE)                     │   │   │
│   │   │ Return { status: "active", access_key: "sk_xxx" }           │   │   │
│   │   │ Worker can now start processing jobs                        │   │   │
│   │   └──────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌──── Type exists, status = PENDING/DISABLED ─────────────────┐   │   │
│   │   │ Create ServiceInstance (status = WAITING)                    │   │   │
│   │   │ Return { status: "waiting" }                                 │   │   │
│   │   └──────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   ┌──── Type exists, status = REJECTED ─────────────────────────┐   │   │
│   │   │ Return 403 { message: "Service type rejected" }             │   │   │
│   │   └──────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   DEREGISTER (graceful shutdown):                                           │
│   POST /api/v1/internal/deregister                                          │
│   -> Mark ServiceInstance status = DEAD                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.8 Admin Service Management Flow (NEW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ADMIN SERVICE MANAGEMENT FLOW                              │
│           (Admin approves/rejects/disables service types)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Admin (is_admin = true) accesses /admin/services page                     │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ LIST SERVICE TYPES (filtered by status)                              │   │
│   │                                                                      │   │
│   │   GET /api/v1/admin/service-types?status=PENDING                    │   │
│   │   Shows: type_id, display_name, description, instance_count,        │   │
│   │          dev_contact, registered_at                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   Admin actions:                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │ APPROVE  │  │  REJECT  │  │ DISABLE  │  │  ENABLE  │  │  DELETE  │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│        │             │             │             │             │          │
│        v             v             v             v             v          │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│   │PENDING   │ │PENDING   │ │APPROVED  │ │DISABLED  │ │Hard      │     │
│   │->APPROVED│ │->REJECTED│ │->DISABLED│ │->APPROVED│ │delete    │     │
│   │Generate  │ │Set reason│ │Instances │ │Instances │ │type +    │     │
│   │access_key│ │(modal)   │ │-> WAITING│ │-> ACTIVE │ │instances │     │
│   │Instances │ │Instances │ │          │ │          │ │          │     │
│   │-> ACTIVE │ │unchanged │ │          │ │          │ │          │     │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Processing Layer

### 4.1 Worker Main Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WORKER MAIN LOOP                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        WORKER STARTUP                                │   │
│   │                                                                      │   │
│   │   1. Load config:                                                   │   │
│   │      - WORKER_SERVICE_TYPE (e.g., "ocr-paddle")                    │   │
│   │      - Auto-generate instance_id ({type}-{hostname[:12]})          │   │
│   │      - WORKER_ACCESS_KEY (optional, empty = wait for approval)     │   │
│   │      - WORKER_FILTER_SUBJECT (e.g., ocr.text_raw.tier0)           │   │
│   │      - NO MINIO_* variables (enforced)                              │   │
│   │                                                                      │   │
│   │   2. POST /api/v1/internal/register (self-registration)            │   │
│   │      -> If APPROVED: receive access_key, proceed                   │   │
│   │      -> If PENDING: wait for admin approval                        │   │
│   │                                                                      │   │
│   │   3. Connect to NATS                                                │   │
│   │   4. Create consumer with specific subject (no wildcard)            │   │
│   │   5. Initialize OCR engine (PaddleOCR or Tesseract)                │   │
│   │   6. Start heartbeat background task                                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        MAIN POLL LOOP                                │   │
│   │                                                                      │   │
│   │   while running:                                                     │   │
│   │       │                                                              │   │
│   │       ├── Send heartbeat (if interval elapsed)                      │   │
│   │       │   { status: "idle", current_job_id: null }                  │   │
│   │       │                                                              │   │
│   │       v                                                              │   │
│   │   ┌─────────────────┐                                               │   │
│   │   │ Pull job from   │ <- NATS fetch(batch=1, timeout=1s)            │   │
│   │   │ queue           │                                               │   │
│   │   └────────┬────────┘                                               │   │
│   │            │                                                         │   │
│   │       ┌────┴────┐                                                   │   │
│   │    No Job      Got Job                                               │   │
│   │       │           │                                                 │   │
│   │       v           v                                                 │   │
│   │   sleep(1s)   Process Job (engine-specific)                        │   │
│   │       │           │                                                 │   │
│   │       └───────────┤                                                 │   │
│   │                   │                                                 │   │
│   │                   v                                                 │   │
│   │            ┌──────────────────────────────────────────────────┐    │   │
│   │            │ On Success: ACK message                          │    │   │
│   │            │ On Error:   ACK message + report error to Orch   │    │   │
│   │            │             (Worker does NOT NAK or retry)       │    │   │
│   │            └──────────────────────────────────────────────────┘    │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Job Processing Flow (Worker)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        JOB PROCESSING FLOW                                   │
│                                                                              │
│   KEY: Worker does NOT retry. Any error -> report to Orchestrator.          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Input: JobMessage { job_id, request_id, file_id, method, tier,            │
│                       output_format, object_key, retry_count }              │
│         │                                                                    │
│         v                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 1: NOTIFY ORCHESTRATOR - PROCESSING                            │   │
│   │                                                                      │   │
│   │   PATCH /api/v1/internal/jobs/{job_id}/status                       │   │
│   │   { status: "PROCESSING", worker_id: self.instance_id }            │   │
│   │                                                                      │   │
│   │   Update heartbeat: { status: "processing", current_job_id }        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 2: DOWNLOAD FILE VIA FILE PROXY                                 │   │
│   │                                                                      │   │
│   │   POST /api/v1/internal/file-proxy/download                         │   │
│   │   Headers: X-Access-Key: {access_key}                               │   │
│   │   Body: { job_id }                                                  │   │
│   │                                                                      │   │
│   │   Save to: /tmp/ocr_worker/{job_id}_input.{ext}                     │   │
│   │                                                                      │   │
│   │   Error? -> Go to ERROR HANDLING                                    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 3: OCR PROCESSING (Engine-specific)                             │   │
│   │                                                                      │   │
│   │   with timeout(JOB_TIMEOUT_SECONDS):                                │   │
│   │       # Engine dispatched based on service_type                     │   │
│   │       # PaddleOCR: preprocessing -> paddle inference -> postprocess │   │
│   │       # Tesseract: preprocessing -> tesseract OCR -> postprocess    │   │
│   │       result = engine.process(input_file)                           │   │
│   │                                                                      │   │
│   │   Save to: /tmp/ocr_worker/{job_id}_result.{format}                 │   │
│   │                                                                      │   │
│   │   Error? -> Go to ERROR HANDLING                                    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 4: UPLOAD RESULT VIA FILE PROXY                                 │   │
│   │                                                                      │   │
│   │   POST /api/v1/internal/file-proxy/upload                           │   │
│   │   Headers: X-Access-Key: {access_key}                               │   │
│   │   Body: multipart { job_id, file, processing_time_ms }              │   │
│   │                                                                      │   │
│   │   Error? -> Go to ERROR HANDLING                                    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 5: NOTIFY ORCHESTRATOR - COMPLETED                              │   │
│   │                                                                      │   │
│   │   PATCH /api/v1/internal/jobs/{job_id}/status                       │   │
│   │   {                                                                  │   │
│   │       status: "COMPLETED",                                          │   │
│   │       result_path: result_key,                                      │   │
│   │       processing_time_ms: elapsed                                   │   │
│   │   }                                                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 6: CLEANUP LOCAL FILES (MANDATORY)                              │   │
│   │                                                                      │   │
│   │   delete(/tmp/ocr_worker/{job_id}_*)                                │   │
│   │   Update heartbeat: { status: "idle", current_job_id: null }        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                v                                                             │
│           ACK message to NATS (job complete)                                │
│                                                                              │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      ERROR HANDLING                                  │   │
│   │                                                                      │   │
│   │   1. Classify error:                                                │   │
│   │      - Retriable: timeout, network error, temp file error           │   │
│   │      - Non-retriable: invalid file, corrupted, access denied        │   │
│   │                                                                      │   │
│   │   2. Report to Orchestrator (Worker does NOT decide retry):         │   │
│   │                                                                      │   │
│   │      PATCH /api/v1/internal/jobs/{job_id}/status                    │   │
│   │      {                                                               │   │
│   │          status: "ERROR",                                           │   │
│   │          error: "error message",                                    │   │
│   │          retriable: true/false                                      │   │
│   │      }                                                               │   │
│   │                                                                      │   │
│   │   3. Cleanup local files                                            │   │
│   │   4. ACK message to NATS (even on error)                            │   │
│   │   5. Update heartbeat: { status: "idle" }                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Sequence Diagrams

### 5.1 Upload & Process Flow (Full)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: UPLOAD & PROCESS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Client    Frontend   API Server   MinIO     Modules    NATS     Worker      │
│ (User)               (Edge:8000) (Edge)    (Orch)              (Processing) │
│   │          │          │          │          │         │          │        │
│   │ Select   │          │          │          │         │          │        │
│   │ files +  │          │          │          │         │          │        │
│   │ config   │          │          │          │         │          │        │
│   │─────────>│          │          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │ POST     │          │          │         │          │        │
│   │          │ /upload  │          │          │         │          │        │
│   │          │─────────>│          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │ validate │          │         │          │        │
│   │          │          │─────────────────────>         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │  PUT     │         │          │        │
│   │          │          │          │  files   │         │          │        │
│   │          │          │<─────────┼──────────│         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │  create  │         │          │        │
│   │          │          │          │  req+job │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ publish  │         │          │        │
│   │          │          │          │ jobs     │         │          │        │
│   │          │          │          │──────────┼────────>│          │        │
│   │          │          │          │          │         │          │        │
│   │          │<─────────│  request_id         │         │          │        │
│   │<─────────│          │          │          │         │          │        │
│   │ redirect │          │          │          │         │          │        │
│   │ to detail│          │          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │          │         │ pull     │        │
│   │          │          │          │          │         │ job      │        │
│   │          │          │          │          │         │<─────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ PATCH    │         │          │        │
│   │          │          │          │PROCESSING│         │          │        │
│   │          │          │          │<─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │download  │         │          │        │
│   │          │          │          │via proxy │         │          │        │
│   │          │          │          │<─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │          │         │ ┌──────┐ │        │
│   │          │          │          │          │         │ │ OCR  │ │        │
│   │          │          │          │          │         │ └──────┘ │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │upload    │         │          │        │
│   │          │          │          │via proxy │         │          │        │
│   │          │          │          │<─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ PATCH    │         │          │        │
│   │          │          │          │COMPLETED │         │          │        │
│   │          │          │          │<─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │ GET      │          │          │         │          │        │
│   │          │/requests/│          │          │         │          │        │
│   │          │ {id}     │          │          │         │          │        │
│   │          │─────────>│          │          │         │          │        │
│   │          │          │ query    │          │         │          │        │
│   │          │          │─────────────────────>         │          │        │
│   │          │<─────────│ status   │          │         │          │        │
│   │<─────────│ results  │          │          │         │          │        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Worker Registration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: WORKER REGISTRATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker              Orchestrator              Admin             Database  │
│     │                      │                     │                    │     │
│     │ POST /register       │                     │                    │     │
│     │ {service_type,       │                     │                    │     │
│     │  instance_id,        │                     │                    │     │
│     │  display_name, ...}  │                     │                    │     │
│     │─────────────────────>│                     │                    │     │
│     │                      │ Create ServiceType  │                    │     │
│     │                      │ (PENDING)           │                    │     │
│     │                      │─────────────────────────────────────────>│     │
│     │                      │ Create ServiceInstance                   │     │
│     │                      │ (WAITING)           │                    │     │
│     │                      │─────────────────────────────────────────>│     │
│     │<─────────────────────│                     │                    │     │
│     │ { status: "waiting" }│                     │                    │     │
│     │                      │                     │                    │     │
│     │  [Worker polls or waits]                   │                    │     │
│     │                      │                     │                    │     │
│     │                      │   Admin approves    │                    │     │
│     │                      │<────────────────────│                    │     │
│     │                      │ Update type APPROVED│                    │     │
│     │                      │ Generate access_key │                    │     │
│     │                      │ Update instances    │                    │     │
│     │                      │ -> ACTIVE           │                    │     │
│     │                      │─────────────────────────────────────────>│     │
│     │                      │                     │                    │     │
│     │  [Worker detects approval / re-registers]  │                    │     │
│     │─────────────────────>│                     │                    │     │
│     │<─────────────────────│                     │                    │     │
│     │ { status: "active",  │                     │                    │     │
│     │   access_key: "sk_x"}│                     │                    │     │
│     │                      │                     │                    │     │
│     │  [Worker starts processing jobs]           │                    │     │
│     │                      │                     │                    │     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Retry Flow (Orchestrator Handles Retry)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: ERROR & RETRY                                   │
│                 (Retry decisions made by Orchestrator)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker            Orchestrator              NATS                Database  │
│     │                    │                     │                      │     │
│     │ pull job           │                     │                      │     │
│     │<───────────────────┼─────────────────────│                      │     │
│     │                    │                     │                      │     │
│     │ PATCH status:      │                     │                      │     │
│     │ PROCESSING         │                     │                      │     │
│     │───────────────────>│                     │                      │     │
│     │                    │────────────────────────────────────────-->│     │
│     │                    │                     │                      │     │
│     │   [OCR fails]      │                     │                      │     │
│     │                    │                     │                      │     │
│     │ PATCH status:      │                     │                      │     │
│     │ ERROR              │                     │                      │     │
│     │ {error, retriable} │                     │                      │     │
│     │───────────────────>│                     │                      │     │
│     │                    │                     │                      │     │
│     │ ACK message        │                     │                      │     │
│     │────────────────────┼────────────────────>│                      │     │
│     │                    │                     │                      │     │
│     │                    │ retry_count=0<3     │                      │     │
│     │                    │ -> RETRYING         │                      │     │
│     │                    │ wait 1s             │                      │     │
│     │                    │ -> QUEUED           │                      │     │
│     │                    │────────────────────────────────────────-->│     │
│     │                    │ Re-publish job      │                      │     │
│     │                    │───────────────────->│                      │     │
│     │                    │                     │                      │     │
│     │   [...after 3 failures...]               │                      │     │
│     │                    │                     │                      │     │
│     │                    │ retry_count=3>=3    │                      │     │
│     │                    │ -> DEAD_LETTER      │                      │     │
│     │                    │ Move to DLQ         │                      │     │
│     │                    │───────────────────->│ dlq.{method}...      │     │
│     │                    │────────────────────────────────────────-->│     │
│     │                    │                     │                      │     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Heartbeat Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: HEARTBEAT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker              Orchestrator                    Database              │
│     │                      │                              │                 │
│     │ [every 30 seconds]   │                              │                 │
│     │                      │                              │                 │
│     │ POST /api/v1/        │                              │                 │
│     │ internal/heartbeat   │                              │                 │
│     │ {                    │                              │                 │
│     │   instance_id,       │                              │                 │
│     │   access_key,        │                              │                 │
│     │   status: "idle",    │                              │                 │
│     │   current_job_id:    │                              │                 │
│     │     null             │                              │                 │
│     │ }                    │                              │                 │
│     │─────────────────────>│                              │                 │
│     │                      │ validate access_key          │                 │
│     │                      │ (ServiceType APPROVED)       │                 │
│     │                      │                              │                 │
│     │                      │ UPDATE instances             │                 │
│     │                      │ last_heartbeat_at            │                 │
│     │                      │─────────────────────────────>│                 │
│     │                      │                              │                 │
│     │                      │ INSERT INTO heartbeats       │                 │
│     │                      │─────────────────────────────>│                 │
│     │                      │                              │                 │
│     │<─────────────────────│ 200 OK                       │                 │
│     │                      │                              │                 │
│     │                      │ ┌─────────────────────────┐  │                 │
│     │                      │ │ Heartbeat Monitor Task  │  │                 │
│     │                      │ │ (runs every 30s)        │  │                 │
│     │                      │ │                         │  │                 │
│     │                      │ │ For each instance:      │  │                 │
│     │                      │ │ - Check last heartbeat  │  │                 │
│     │                      │ │ - If > 90s -> DEAD      │  │                 │
│     │                      │ │ - If stalled -> reassign │  │                 │
│     │                      │ └─────────────────────────┘  │                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Job State Machine (Complete)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB STATE MACHINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌───────────────┐                                 │
│                           │   SUBMITTED   │                                 │
│                           │  (Job created)│                                 │
│                           └───────┬───────┘                                 │
│                                   │ Auto                                    │
│                                   v                                         │
│                           ┌───────────────┐                                 │
│                           │  VALIDATING   │                                 │
│                           │ (Check format)│                                 │
│                           └───────┬───────┘                                 │
│                                   │                                         │
│                          ┌────────┼────────┐                               │
│                          │                 │                               │
│                       Valid            Invalid                              │
│                          │                 │                               │
│                          v                 v                               │
│              ┌───────────────┐     ┌───────────────┐                       │
│              │    QUEUED     │     │   REJECTED    │                       │
│              │  (In queue)   │     │  (Terminal)   │                       │
│              └───────┬───────┘     └───────────────┘                       │
│                      │                                                      │
│          ┌───────────┼───────────┐                                         │
│          │           │           │                                         │
│     User Cancel  Worker picks  (stays in queue)                            │
│          │           │                                                      │
│          v           v                                                      │
│   ┌───────────┐┌───────────────┐                                           │
│   │ CANCELLED ││  PROCESSING   │                                           │
│   │(Terminal) ││ (OCR running) │                                           │
│   └───────────┘└───────┬───────┘                                           │
│                        │                                                    │
│           ┌────────────┼────────────┐                                      │
│           │            │            │                                      │
│        Success    Retriable    Non-retriable                               │
│           │        Error         Error                                     │
│           │            │            │                                      │
│           v            v            v                                      │
│    ┌───────────┐ ┌──────────┐ ┌───────────┐                               │
│    │ COMPLETED │ │ RETRYING │ │  FAILED   │                               │
│    │ (Success) │ │          │ │(Terminal) │                               │
│    └───────────┘ └────┬─────┘ └───────────┘                               │
│                       │                                                     │
│                       │ Orchestrator decides:                              │
│                 ┌─────┼──────┐                                             │
│               Yes           No                                              │
│            (retry<3)    (retry>=3)                                          │
│                 │            │                                              │
│                 v            v                                              │
│          ┌──────────┐ ┌───────────────┐                                    │
│          │  QUEUED  │ │  DEAD_LETTER  │                                    │
│          │(re-enter)│ │  (Terminal)   │                                    │
│          └──────────┘ └───────────────┘                                    │
│                                                                              │
│  Terminal States: COMPLETED, FAILED, REJECTED, CANCELLED, DEAD_LETTER      │
│                                                                              │
│  Request Status Aggregation:                                                │
│  ┌──────────────────┬──────────────────────────────────────────────────┐   │
│  │ PROCESSING       │ Any job QUEUED/PROCESSING/RETRYING               │   │
│  │ COMPLETED        │ All jobs COMPLETED                               │   │
│  │ PARTIAL_SUCCESS  │ Mix: >=1 COMPLETED + >=1 terminal failure        │   │
│  │ FAILED           │ All jobs FAILED/DEAD_LETTER/REJECTED            │   │
│  │ CANCELLED        │ All jobs CANCELLED                               │   │
│  └──────────────────┴──────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Inter-Layer Communication Summary

| From | To | Protocol | Auth | Data |
|------|-----|----------|------|------|
| Client | Frontend | HTTPS | - | HTML/JS |
| Frontend | API Server | HTTP/REST | Bearer token (session) | JSON |
| API Server | Modules | Function call | (internal) | Python objects |
| Upload Module | MinIO | S3 API | Storage creds | Binary |
| Job Module | NATS | Publish | - | JSON message |
| NATS | Worker | Pull | - | JSON message |
| Worker | Register | HTTP/REST | none (initial) | JSON |
| Worker | File Proxy | HTTP/REST | access_key (X-Access-Key) | Stream/JSON |
| File Proxy | MinIO | S3 API | Storage creds | Binary |
| Worker | Orchestrator | HTTP/REST | access_key (X-Access-Key) | JSON (status/heartbeat) |
| Admin | API Server | HTTP/REST | Bearer token + is_admin | JSON |
| All Modules | SQLite | SQL | - | Python objects |

**Layer Boundaries:**
- Edge <-> Orchestration: Storage credentials, internal function calls
- Orchestration <-> Processing: Queue (NATS), File Proxy API, Heartbeat API, Register API
- Processing -> Edge: **FORBIDDEN** (must go through Orchestration)

---

*Changelog v2.0 -> v3.0:*
- *Updated all internal endpoint URLs from `/internal/*` to `/api/v1/internal/*`*
- *Changed job status update from POST to PATCH*
- *Added Section 3.7: Worker Registration Flow (self-registration on startup)*
- *Added Section 3.8: Admin Service Management Flow (approve/reject/disable)*
- *Added Section 5.2: Worker Registration Sequence Diagram*
- *Updated Processing Layer: multi-engine support (PaddleOCR + Tesseract)*
- *Updated heartbeat to use `instance_id` instead of `service_id`*
- *Updated auth flow: Session.token is separate field, User has is_admin*
- *Updated File Proxy ACL: validates against ServiceType (not Service)*
- *Updated architecture overview diagram with multi-engine workers*
- *Backend port: 8080 -> 8000*
