# OCR Platform Local MVP1 - Layer Processing Logic

> Version: 2.0 | Phase: Local MVP 1
> Aligned with: SA v3.1

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM LAYERS OVERVIEW                                 │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                              EDGE LAYER                                     │ │
│  │            "Cổng vào + Kho chứa" - Không xử lý logic nghiệp vụ             │ │
│  │                                                                             │ │
│  │   ┌──────────────┐         ┌──────────────────────────────────────────┐   │ │
│  │   │   Frontend   │◄─HTTP──▶│            API Server                    │   │ │
│  │   │   (React)    │         │           (FastAPI)                      │   │ │
│  │   └──────────────┘         └──────────────┬───────────────────────────┘   │ │
│  │                                           │                                │ │
│  │   ┌───────────────────────────────────────┼────────────────────────────┐  │ │
│  │   │              OBJECT STORAGE (MinIO)   │                             │  │ │
│  │   │   Buckets: uploads | results | deleted│ ◄── API Server has creds   │  │ │
│  │   │                                       │                             │  │ │
│  │   └───────────────────────────────────────┼────────────────────────────┘  │ │
│  │                                           │                                │ │
│  └───────────────────────────────────────────┼────────────────────────────────┘ │
│                                              │ internal calls                   │
│                                              │ + storage credentials            │
│  ┌───────────────────────────────────────────┼────────────────────────────────┐ │
│  │                    ORCHESTRATION LAYER    │                                 │ │
│  │               "Bộ não điều phối"          ▼                                 │ │
│  │                                                                             │ │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌─────────────────────────┐  │ │
│  │   │  Auth   │  │ Upload  │  │     Job     │  │      File Proxy         │  │ │
│  │   │ Module  │  │ Module  │  │   Module    │  │       Module            │  │ │
│  │   │         │  │         │  │             │  │                         │  │ │
│  │   │Register │  │Validate │  │Create req   │  │Auth service (access_key)│  │ │
│  │   │Login    │  │Store    │  │Create jobs  │  │ACL check                │  │ │
│  │   │Session  │  │(→Edge)  │  │Retry logic  │  │Stream files (→Edge)     │  │ │
│  │   │         │  │         │  │Heartbeat mon│  │                         │  │ │
│  │   └────┬────┘  └────┬────┘  └──────┬──────┘  └───────────┬─────────────┘  │ │
│  │        │            │              │                     │                 │ │
│  │   ┌────┴────────────┴──────────────┴─────────────────────┴──────────────┐ │ │
│  │   │                   ORCHESTRATION INFRASTRUCTURE                       │ │ │
│  │   │                                                                      │ │ │
│  │   │   ┌──────────────────────┐       ┌───────────────────────────────┐  │ │ │
│  │   │   │       SQLite         │       │      NATS JETSTREAM           │  │ │ │
│  │   │   │      DATABASE        │       │                               │  │ │ │
│  │   │   │                      │       │  Stream: OCR_JOBS             │  │ │ │
│  │   │   │ users, sessions      │       │  Subjects: ocr.{method}.tier{n}│ │ │ │
│  │   │   │ requests, jobs       │       │                               │  │ │ │
│  │   │   │ files, services      │       │  Stream: OCR_DLQ              │  │ │ │
│  │   │   │ heartbeats           │       │  Subjects: dlq.ocr.>          │  │ │ │
│  │   │   │                      │       │                               │  │ │ │
│  │   │   └──────────────────────┘       └───────────────┬───────────────┘  │ │ │
│  │   │                                                  │                   │ │ │
│  │   └──────────────────────────────────────────────────┼───────────────────┘ │ │
│  │                                                      │                     │ │
│  └──────────────────────────────────────────────────────┼─────────────────────┘ │
│                                                         │ pull (specific subject)│
│                                                         ▼                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                          PROCESSING LAYER                                  │  │
│  │                  "Nhà máy xử lý" - Không có business logic                │  │
│  │                                                                            │  │
│  │   ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │   │                        OCR WORKER                                   │  │  │
│  │   │        (has access_key, NO storage credentials)                    │  │  │
│  │   │                                                                     │  │  │
│  │   │   ┌────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────────┐    │  │  │
│  │   │   │  POLL  │─▶│ DOWNLOAD │─▶│  PROCESS  │─▶│ UPLOAD + REPORT │    │  │  │
│  │   │   │ QUEUE  │  │via FILE  │  │(Tesseract)│  │  via FILE PROXY │    │  │  │
│  │   │   │ (NATS) │  │  PROXY   │  │           │  │                 │    │  │  │
│  │   │   └────────┘  └──────────┘  └─────┬─────┘  └─────────────────┘    │  │  │
│  │   │                                   │                                │  │  │
│  │   │                              Error?                                │  │  │
│  │   │                              ┌────┴────┐                           │  │  │
│  │   │                         Retriable   Non-retriable                  │  │  │
│  │   │                              │           │                         │  │  │
│  │   │                              ▼           ▼                         │  │  │
│  │   │                    ┌─────────────────────────────────────┐        │  │  │
│  │   │                    │  Report error to ORCHESTRATOR       │        │  │  │
│  │   │                    │  (Worker does NOT retry itself)     │        │  │  │
│  │   │                    └─────────────────────────────────────┘        │  │  │
│  │   │                                                                    │  │  │
│  │   │   HEARTBEAT ──▶ POST /internal/heartbeat every 30s                │  │  │
│  │   │   CLEANUP   ──▶ delete ALL local files after processing           │  │  │
│  │   │                                                                    │  │  │
│  │   └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  LAYER COMMUNICATION RULES:                                                       │
│  ✓ Client ↔ Edge (HTTP)                                                          │
│  ✓ Edge ↔ Orchestration (internal calls, storage creds)                          │
│  ✓ Orchestration ↔ Processing (Queue, File Proxy API, Heartbeat API)             │
│  ✗ Processing → Edge (FORBIDDEN - vượt cấp)                                      │
│                                                                                   │
│  FILE ACCESS FLOW:                                                                │
│  Worker → File Proxy (Orch) → MinIO (Edge)                                       │
│  Each step is between adjacent layers ✓                                          │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
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
│          ▼                                                                   │
│   ┌─────────────┐     No      ┌─────────────┐                              │
│   │Has Session? │────────────▶│  Login/     │                              │
│   └──────┬──────┘             │  Register   │                              │
│          │ Yes                 └──────┬──────┘                              │
│          │                            │ Success                             │
│          │◄───────────────────────────┘                                     │
│          ▼                                                                   │
│   ┌─────────────┐                                                           │
│   │  Dashboard  │◄─────────────────────────────────────┐                   │
│   └──────┬──────┘                                      │                   │
│          │                                              │                   │
│          ▼                                              │                   │
│   ┌─────────────────────────────────────┐              │                   │
│   │          Upload Page                 │              │                   │
│   │  ┌─────────────────────────────────┐│              │                   │
│   │  │ Select Files (drag-drop)        ││              │                   │
│   │  ├─────────────────────────────────┤│              │                   │
│   │  │ Config:                         ││              │                   │
│   │  │ • Output Format: [txt|json]     ││              │                   │
│   │  │ • Retention: [1h|6h|24h|7d]     ││              │                   │
│   │  └─────────────────────────────────┘│              │                   │
│   └──────────────┬──────────────────────┘              │                   │
│                  │ Submit                               │                   │
│                  ▼                                      │                   │
│   ┌─────────────────────────────────────┐              │                   │
│   │ Validate Files (client-side)        │              │                   │
│   │ • Type: PNG, JPEG, PDF              │              │                   │
│   │ • Size: ≤ 10MB each, ≤ 50MB total   │              │                   │
│   │ • Count: ≤ 20 files                 │              │                   │
│   └──────────────┬──────────────────────┘              │                   │
│                  │                                      │                   │
│                  ▼                                      │                   │
│   ┌─────────────────────────────────────┐              │                   │
│   │ POST /upload                         │              │                   │
│   │ (files + output_format + retention)  │              │                   │
│   └──────────────┬──────────────────────┘              │                   │
│                  │                                      │                   │
│                  ▼                                      │                   │
│   ┌─────────────────────────────────────┐              │                   │
│   │      Request Detail Page            │              │                   │
│   │                                     │              │                   │
│   │  Poll GET /requests/{id}            │              │                   │
│   │  every 2 seconds                    │◄─────────────┼──── Continue      │
│   │                                     │              │     Polling       │
│   │  Show:                              │              │                   │
│   │  • Progress: 3/5 completed          │              │                   │
│   │  • Job statuses (incl. REJECTED,    │              │                   │
│   │    DEAD_LETTER, CANCELLED)          │              │                   │
│   │  • Cancel button (if QUEUED)        │              │                   │
│   └──────────────┬──────────────────────┘              │                   │
│                  │                                      │                   │
│         ┌────────┼────────┬────────────┐               │                   │
│         │        │        │            │               │                   │
│     COMPLETED  PARTIAL  FAILED     Still processing    │                   │
│         │     SUCCESS     │            │               │                   │
│         ▼        ▼        ▼            └───────────────┘                   │
│   ┌──────────────────────────────────┐                                     │
│   │  Download Results / View Errors   │                                     │
│   └──────────────────────────────────┘                                     │
│                  │                                                          │
│                  └──────────────────────────────────────────────────────────┘
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
│        ▼                                                                     │
│   ┌─────────────────┐                                                       │
│   │   Middleware    │                                                       │
│   │  - Logging      │                                                       │
│   │  - Error handler│                                                       │
│   │  - Timing       │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                       │
│   │   Router        │                                                       │
│   │  /api/v1/*      │ ──── User endpoints (session auth)                   │
│   │  /internal/*    │ ──── Worker endpoints (access_key auth)              │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        AUTHENTICATION                                │   │
│   │                                                                      │   │
│   │   User Endpoints (/api/v1/*)                                        │   │
│   │   ├── Extract token from Cookie/Authorization header                │   │
│   │   ├── Validate session in database                                  │   │
│   │   └── Return 401 if invalid/expired                                 │   │
│   │                                                                      │   │
│   │   Internal Endpoints (/internal/*)                                  │   │
│   │   ├── Extract access_key from X-Access-Key header                   │   │
│   │   ├── Validate in services table                                    │   │
│   │   └── Return 401 if invalid/disabled                                │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│            │                                                                 │
│            ▼                                                                 │
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
│       ├── Check email unique → Error if exists                             │
│       ├── Hash password (bcrypt, cost=10)                                   │
│       ├── INSERT INTO users                                                 │
│       ├── Create session token                                              │
│       └── Return { user, token }                                            │
│                                                                              │
│  LOGIN: email, password                                                     │
│       │                                                                      │
│       ├── Find user by email → Error if not found                          │
│       ├── Verify password (bcrypt) → Error if mismatch                     │
│       ├── Create new session token                                          │
│       └── Return { user, token }                                            │
│                                                                              │
│  VALIDATE SESSION (Dependency):                                             │
│       │                                                                      │
│       ├── Find session by token → 401 if not found                         │
│       ├── Check expiry → 401 if expired                                    │
│       └── Return User object                                                │
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
│          output_format="txt", retention_hours=24                            │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    BATCH VALIDATION                                  │   │
│   │                                                                      │   │
│   │   Check: count ≤ 20, total size ≤ 50MB                              │   │
│   │   Fail → 400 Error                                                   │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                 PER-FILE VALIDATION LOOP                             │   │
│   │                                                                      │   │
│   │   for each file:                                                     │   │
│   │       • Check MIME type + magic bytes (PNG, JPEG, PDF)              │   │
│   │       • Check size ≤ 10MB                                            │   │
│   │       • If invalid → add to skipped_files[], continue               │   │
│   │       • If valid → add to valid_files[]                              │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              CREATE REQUEST + STORE FILES + CREATE JOBS              │   │
│   │                                                                      │   │
│   │   1. INSERT INTO requests:                                          │   │
│   │      (user_id, method, tier, output_format, retention_hours,        │   │
│   │       status=PROCESSING, total_files, completed_files=0, failed=0)  │   │
│   │                                                                      │   │
│   │   2. For each valid_file:                                           │   │
│   │      a. Upload to MinIO (Edge layer):                               │   │
│   │         bucket=uploads, key={user_id}/{request_id}/{file_id}.{ext}  │   │
│   │      b. INSERT INTO files (request_id, original_name, object_key)   │   │
│   │      c. INSERT INTO jobs:                                           │   │
│   │         (request_id, file_id, status=SUBMITTED, method, tier,       │   │
│   │          output_format, retry_count=0, max_retries=3)               │   │
│   │                                                                      │   │
│   │   3. Trigger VALIDATING → QUEUED for each job (see Job Module)      │   │
│   │                                                                      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
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
│  │ JOB CREATION & VALIDATION (called after upload)                         ││
│  │                                                                          ││
│  │   For each job (status = SUBMITTED):                                    ││
│  │       │                                                                 ││
│  │       ▼                                                                 ││
│  │   Update status → VALIDATING                                            ││
│  │       │                                                                 ││
│  │       ├── Validate file format/integrity                                ││
│  │       │                                                                 ││
│  │       ├─── Valid ──────────────────────────────────────┐                ││
│  │       │                                                │                ││
│  │       │    Update status → QUEUED                      │                ││
│  │       │    Publish to NATS: ocr.{method}.tier{tier}    │                ││
│  │       │                                                │                ││
│  │       └─── Invalid ───────────────────────────┐        │                ││
│  │                                               │        │                ││
│  │            Update status → REJECTED            │        │                ││
│  │            Log rejection reason               │        │                ││
│  │            Increment request.failed_files     │        │                ││
│  │                                               │        │                ││
│  └───────────────────────────────────────────────┴────────┴────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ GET REQUEST STATUS                                                      ││
│  │                                                                          ││
│  │   1. Find request by ID, check owner                                    ││
│  │   2. Load all jobs for request                                          ││
│  │   3. Aggregate status:                                                   ││
│  │                                                                          ││
│  │      ┌─────────────────────────────────────────────────────────────┐    ││
│  │      │ any(QUEUED, PROCESSING, RETRYING) → PROCESSING             │    ││
│  │      │ all(COMPLETED)                     → COMPLETED              │    ││
│  │      │ all(FAILED, DEAD_LETTER, REJECTED) → FAILED                 │    ││
│  │      │ mix(COMPLETED + FAILED/DL/REJECTED)→ PARTIAL_SUCCESS        │    ││
│  │      │ all(CANCELLED)                     → CANCELLED              │    ││
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
│  │       Update status → CANCELLED                                         ││
│  │       Remove from queue (if possible)                                   ││
│  │                                                                          ││
│  │   Jobs already PROCESSING cannot be cancelled                           ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Retry Orchestrator Flow (NEW - Retry at Orchestration Layer)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RETRY ORCHESTRATOR FLOW                                  │
│                   (Retry logic in Orchestration, NOT Worker)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker reports error via POST /internal/jobs/{id}/status                  │
│   Body: { status: "error", error: "...", retriable: true/false }            │
│         │                                                                    │
│         ▼                                                                    │
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
│         ▼               ▼                                                    │
│   ┌───────────────┐ ┌───────────────────────────────────────────────────┐   │
│   │Check retry_cnt│ │ Update status → FAILED                            │   │
│   │< max_retries? │ │ Increment request.failed_files                    │   │
│   └───────┬───────┘ │ Check if request complete → update request.status │   │
│           │         └───────────────────────────────────────────────────┘   │
│     ┌─────┴─────┐                                                            │
│   Yes          No                                                            │
│     │           │                                                            │
│     ▼           ▼                                                            │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │ RETRY PATH                        │ DEAD LETTER PATH                  │ │
│   │                                   │                                   │ │
│   │ 1. Update status → RETRYING       │ 1. Update status → DEAD_LETTER    │ │
│   │ 2. Increment retry_count          │ 2. Move to DLQ:                   │ │
│   │ 3. Calculate delay:               │    Publish to dlq.ocr.{method}... │ │
│   │    delay = 1s × 2^retry_count     │ 3. Increment request.failed_files │ │
│   │    (1s, 2s, 4s)                   │ 4. Update request status          │ │
│   │ 4. Wait delay (scheduled task)    │                                   │ │
│   │ 5. Update status → QUEUED         │                                   │ │
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

### 3.5 Heartbeat Monitor Flow (NEW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HEARTBEAT MONITOR FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker sends heartbeat every 30 seconds:                                  │
│                                                                              │
│   POST /internal/heartbeat                                                   │
│   {                                                                          │
│     "service_id": "worker-ocr-text-tier0",                                  │
│     "access_key": "sk_xxx",                                                 │
│     "status": "processing",        // idle | processing | uploading | error│
│     "current_job_id": "job_abc",   // null if idle                         │
│     "progress": {                                                           │
│       "files_completed": 2,                                                 │
│       "files_total": 5                                                      │
│     },                                                                       │
│     "error_count": 0                                                        │
│   }                                                                          │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   ORCHESTRATOR HEARTBEAT HANDLER                     │   │
│   │                                                                      │   │
│   │   1. Validate access_key                                            │   │
│   │   2. INSERT INTO heartbeats (all fields + received_at = now())      │   │
│   │   3. Return 200 OK                                                  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               HEARTBEAT MONITOR (Background Task)                    │   │
│   │                        Runs every 30 seconds                         │   │
│   │                                                                      │   │
│   │   For each registered service:                                      │   │
│   │       │                                                              │   │
│   │       ├── Get latest heartbeat                                      │   │
│   │       │                                                              │   │
│   │       ├── No heartbeat for > HEARTBEAT_TIMEOUT (90s)?              │   │
│   │       │   └── Mark worker as DEAD                                   │   │
│   │       │       If worker had current_job_id:                        │   │
│   │       │           → Return job to QUEUED (for another worker)      │   │
│   │       │                                                              │   │
│   │       ├── status = "error" continuously?                           │   │
│   │       │   └── Mark worker as UNHEALTHY                             │   │
│   │       │                                                              │   │
│   │       └── progress unchanged for > JOB_TIMEOUT?                    │   │
│   │           └── Mark worker as STALLED                               │   │
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
│   This is valid: Orchestration → Edge (adjacent layers)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ DOWNLOAD FILE (Worker requests file)                                    ││
│  │                                                                          ││
│  │   POST /internal/file-proxy/download                                    ││
│  │   Headers: X-Access-Key: {worker_access_key}                            ││
│  │   Body: { "job_id": "job_abc" }                                         ││
│  │         │                                                               ││
│  │         ▼                                                               ││
│  │   1. Validate access_key → 401 if invalid                               ││
│  │   2. Find service by access_key                                         ││
│  │   3. Find job by job_id                                                 ││
│  │   4. Check ACL: service can access this job's file?                     ││
│  │      (job.method in service.allowed_methods &&                          ││
│  │       job.tier in service.allowed_tiers)                                ││
│  │      → 403 if denied                                                    ││
│  │   5. Get file.object_key from database                                  ││
│  │   6. Call MinIO (Edge layer): GetObject(bucket=uploads, key)            ││
│  │   7. Stream file to Worker                                              ││
│  │   8. Log access for audit trail                                         ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ UPLOAD RESULT (Worker uploads OCR result)                               ││
│  │                                                                          ││
│  │   POST /internal/file-proxy/upload                                      ││
│  │   Headers: X-Access-Key: {worker_access_key}                            ││
│  │   Body: multipart/form-data { job_id, file, processing_time_ms }        ││
│  │         │                                                               ││
│  │         ▼                                                               ││
│  │   1. Validate access_key → 401 if invalid                               ││
│  │   2. Check ACL for job                                                  ││
│  │   3. Generate result key: results/{request_id}/{job_id}.{format}        ││
│  │   4. Call MinIO (Edge layer): PutObject(bucket=results, key, file)      ││
│  │   5. Return { result_path: key }                                        ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   LAYER FLOW:                                                                │
│                                                                              │
│   Processing Layer          Orchestration Layer           Edge Layer        │
│     Worker                    File Proxy                   MinIO            │
│       │                          │                          │               │
│       │  POST /download          │                          │               │
│       │  {job_id, access_key}    │                          │               │
│       │─────────────────────────►│                          │               │
│       │                          │  validate + ACL          │               │
│       │                          │                          │               │
│       │                          │  S3 GetObject            │               │
│       │                          │─────────────────────────►│               │
│       │                          │◄─────────────────────────│               │
│       │   stream file            │                          │               │
│       │◄─────────────────────────│                          │               │
│       │                          │                          │               │
│                                                                              │
│   Each arrow crosses exactly ONE layer boundary ✓                           │
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
│   │      - WORKER_SERVICE_ID                                            │   │
│   │      - WORKER_ACCESS_KEY                                            │   │
│   │      - WORKER_FILTER_SUBJECT (e.g., ocr.text_raw.tier0)            │   │
│   │      - NO MINIO_* variables (enforced)                              │   │
│   │                                                                      │   │
│   │   2. Connect to NATS                                                │   │
│   │   3. Create consumer with specific subject (no wildcard)            │   │
│   │   4. Initialize Tesseract engine                                    │   │
│   │   5. Start heartbeat background task                                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        MAIN POLL LOOP                                │   │
│   │                                                                      │   │
│   │   while running:                                                     │   │
│   │       │                                                              │   │
│   │       ├── Send heartbeat (if interval elapsed)                      │   │
│   │       │   { status: "idle", current_job_id: null }                  │   │
│   │       │                                                              │   │
│   │       ▼                                                              │   │
│   │   ┌─────────────────┐                                               │   │
│   │   │ Pull job from   │ ← NATS fetch(batch=1, timeout=1s)             │   │
│   │   │ queue           │                                               │   │
│   │   └────────┬────────┘                                               │   │
│   │            │                                                         │   │
│   │       ┌────┴────┐                                                   │   │
│   │    No Job      Got Job                                               │   │
│   │       │           │                                                 │   │
│   │       ▼           ▼                                                 │   │
│   │   sleep(1s)   Process Job                                           │   │
│   │       │           │                                                 │   │
│   │       └───────────┤                                                 │   │
│   │                   │                                                 │   │
│   │                   ▼                                                 │   │
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
│   KEY: Worker does NOT retry. Any error → report to Orchestrator.           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Input: JobMessage { job_id, request_id, file_id, method, tier,            │
│                       output_format, retry_count }                          │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 1: NOTIFY ORCHESTRATOR - PROCESSING                            │   │
│   │                                                                      │   │
│   │   POST /internal/jobs/{job_id}/status                               │   │
│   │   { status: "PROCESSING", started_at: now(), worker_id: self.id }   │   │
│   │                                                                      │   │
│   │   Update heartbeat: { status: "processing", current_job_id: job_id }│   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 2: DOWNLOAD FILE VIA FILE PROXY                                 │   │
│   │                                                                      │   │
│   │   POST /internal/file-proxy/download                                │   │
│   │   Headers: X-Access-Key: {access_key}                               │   │
│   │   Body: { job_id }                                                  │   │
│   │                                                                      │   │
│   │   Save to: /tmp/ocr_worker/{job_id}_input.{ext}                     │   │
│   │                                                                      │   │
│   │   Error? → Go to ERROR HANDLING                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 3: OCR PROCESSING                                               │   │
│   │                                                                      │   │
│   │   with timeout(JOB_TIMEOUT_SECONDS):                                │   │
│   │       result = tesseract.image_to_string(input_file)                │   │
│   │       # or other format based on output_format                      │   │
│   │                                                                      │   │
│   │   Save to: /tmp/ocr_worker/{job_id}_result.{format}                 │   │
│   │                                                                      │   │
│   │   Error? → Go to ERROR HANDLING                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 4: UPLOAD RESULT VIA FILE PROXY                                 │   │
│   │                                                                      │   │
│   │   Update heartbeat: { status: "uploading" }                         │   │
│   │                                                                      │   │
│   │   POST /internal/file-proxy/upload                                  │   │
│   │   Headers: X-Access-Key: {access_key}                               │   │
│   │   Body: multipart { job_id, file, processing_time_ms }              │   │
│   │                                                                      │   │
│   │   Error? → Go to ERROR HANDLING                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 5: NOTIFY ORCHESTRATOR - COMPLETED                              │   │
│   │                                                                      │   │
│   │   POST /internal/jobs/{job_id}/status                               │   │
│   │   {                                                                  │   │
│   │       status: "COMPLETED",                                          │   │
│   │       result_path: result_key,                                      │   │
│   │       processing_time_ms: elapsed,                                  │   │
│   │       completed_at: now()                                           │   │
│   │   }                                                                  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 6: CLEANUP LOCAL FILES (MANDATORY)                              │   │
│   │                                                                      │   │
│   │   delete(/tmp/ocr_worker/{job_id}_*)                                │   │
│   │                                                                      │   │
│   │   Update heartbeat: { status: "idle", current_job_id: null }        │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                             │
│                ▼                                                             │
│           ACK message to NATS (job complete)                                │
│                                                                              │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      ERROR HANDLING                                  │   │
│   │                                                                      │   │
│   │   1. Classify error:                                                │   │
│   │      • Retriable: timeout, network error, temp file error           │   │
│   │      • Non-retriable: invalid file, corrupted, access denied        │   │
│   │                                                                      │   │
│   │   2. Report to Orchestrator (Worker does NOT decide retry):         │   │
│   │                                                                      │   │
│   │      POST /internal/jobs/{job_id}/status                            │   │
│   │      {                                                               │   │
│   │          status: "ERROR",                                           │   │
│   │          error: "error message",                                    │   │
│   │          retriable: true/false                                      │   │
│   │      }                                                               │   │
│   │                                                                      │   │
│   │   3. Cleanup local files                                            │   │
│   │                                                                      │   │
│   │   4. ACK message to NATS (even on error - Orchestrator handles it)  │   │
│   │                                                                      │   │
│   │   5. Update heartbeat: { status: "idle" }                           │   │
│   │                                                                      │   │
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
│ (User)               (Edge)      (Edge)    (Orch)              (Processing) │
│   │          │          │          │          │         │          │        │
│   │ Select   │          │          │          │         │          │        │
│   │ files +  │          │          │          │         │          │        │
│   │ config   │          │          │          │         │          │        │
│   │─────────▶│          │          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │ POST     │          │          │         │          │        │
│   │          │ /upload  │          │          │         │          │        │
│   │          │─────────▶│          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │ validate │          │         │          │        │
│   │          │          │─────────────────────▶         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │  PUT     │         │          │        │
│   │          │          │          │  files   │         │          │        │
│   │          │          │◀─────────┼──────────│         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │  create  │         │          │        │
│   │          │          │          │  request │         │          │        │
│   │          │          │          │  + jobs  │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ validate │ publish │          │        │
│   │          │          │          │ → QUEUED │ jobs    │          │        │
│   │          │          │          │──────────┼────────▶│          │        │
│   │          │          │          │          │         │          │        │
│   │          │◀─────────│  request_id         │         │          │        │
│   │          │          │          │          │         │          │        │
│   │◀─────────│          │          │          │         │          │        │
│   │ redirect │          │          │          │         │          │        │
│   │ to detail│          │          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │          │         │ pull     │        │
│   │          │          │          │          │         │ job      │        │
│   │          │          │          │          │         │◀─────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ status:  │         │          │        │
│   │          │          │          │PROCESSING│         │          │        │
│   │          │          │          │◀─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │download  │         │          │        │
│   │          │          │          │via proxy │         │          │        │
│   │          │          │          │◀─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │          │  stream  │          │         │          │        │
│   │          │          │  file    │          │         │          │        │
│   │          │          │◀─────────│          │         │          │        │
│   │          │          │─────────────────────┼─────────┼─────────▶│        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │          │         │ ┌──────┐ │        │
│   │          │          │          │          │         │ │ OCR  │ │        │
│   │          │          │          │          │         │ └──────┘ │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │upload    │         │          │        │
│   │          │          │          │via proxy │         │          │        │
│   │          │          │          │◀─────────┼─────────┼──────────│        │
│   │          │          │  PUT     │          │         │          │        │
│   │          │          │  result  │          │         │          │        │
│   │          │          │◀─────────│          │         │          │        │
│   │          │          │─────────▶│          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │          │          │          │ status:  │         │          │        │
│   │          │          │          │COMPLETED │         │          │        │
│   │          │          │          │◀─────────┼─────────┼──────────│        │
│   │          │          │          │          │         │          │        │
│   │          │ GET      │          │          │         │          │        │
│   │          │/requests/│          │          │         │          │        │
│   │          │ {id}     │          │          │         │          │        │
│   │          │─────────▶│          │          │         │          │        │
│   │          │          │ query    │          │         │          │        │
│   │          │          │─────────────────────▶         │          │        │
│   │          │◀─────────│ status   │          │         │          │        │
│   │          │          │          │          │         │          │        │
│   │◀─────────│          │          │          │         │          │        │
│   │ show     │          │          │          │         │          │        │
│   │ results  │          │          │          │         │          │        │
│   │          │          │          │          │         │          │        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Retry Flow (Orchestrator Handles Retry)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: ERROR & RETRY                                   │
│                 (Retry decisions made by Orchestrator)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker            Orchestrator              NATS                Database  │
│     │                    │                     │                      │     │
│     │ pull job           │                     │                      │     │
│     │◀───────────────────┼─────────────────────│                      │     │
│     │                    │                     │                      │     │
│     │ POST status:       │                     │                      │     │
│     │ PROCESSING         │                     │                      │     │
│     │───────────────────▶│                     │                      │     │
│     │                    │──────────────────────────────────────────▶│     │
│     │                    │                     │                      │     │
│     │                    │                     │                      │     │
│     │   [OCR fails - timeout]                  │                      │     │
│     │                    │                     │                      │     │
│     │ POST status:       │                     │                      │     │
│     │ ERROR              │                     │                      │     │
│     │ {error: "timeout", │                     │                      │     │
│     │  retriable: true}  │                     │                      │     │
│     │───────────────────▶│                     │                      │     │
│     │                    │                     │                      │     │
│     │ ACK message        │                     │                      │     │
│     │────────────────────┼────────────────────▶│                      │     │
│     │                    │                     │                      │     │
│     │   (Worker done - goes back to polling)   │                      │     │
│     │                    │                     │                      │     │
│     │                    │ ┌────────────────────────────────────────┐│     │
│     │                    │ │ Orchestrator Retry Logic:             ││     │
│     │                    │ │                                        ││     │
│     │                    │ │ 1. retriable=true, retry_count=0<3   ││     │
│     │                    │ │ 2. Update status → RETRYING           ││     │
│     │                    │ │ 3. Increment retry_count → 1          ││     │
│     │                    │ │ 4. Wait delay: 1s × 2^0 = 1s          ││     │
│     │                    │ └────────────────────────────────────────┘│     │
│     │                    │                     │                      │     │
│     │                    │──────────────────────────────────────────▶│     │
│     │                    │                     │                      │     │
│     │                    │   [wait 1 second]   │                      │     │
│     │                    │                     │                      │     │
│     │                    │ Update → QUEUED     │                      │     │
│     │                    │──────────────────────────────────────────▶│     │
│     │                    │                     │                      │     │
│     │                    │ Re-publish job      │                      │     │
│     │                    │────────────────────▶│                      │     │
│     │                    │                     │                      │     │
│     │ pull job (retry 1) │                     │                      │     │
│     │◀───────────────────┼─────────────────────│                      │     │
│     │                    │                     │                      │     │
│     │   [...process fails again...]            │                      │     │
│     │                    │                     │                      │     │
│     │ POST status: ERROR │                     │                      │     │
│     │───────────────────▶│                     │                      │     │
│     │                    │ retry_count=1<3     │                      │     │
│     │                    │ delay = 2s          │                      │     │
│     │                    │ ...                 │                      │     │
│     │                    │                     │                      │     │
│     │   [...after 3 failures...]               │                      │     │
│     │                    │                     │                      │     │
│     │ POST status: ERROR │                     │                      │     │
│     │───────────────────▶│                     │                      │     │
│     │                    │                     │                      │     │
│     │                    │ retry_count=3≥3     │                      │     │
│     │                    │ → DEAD_LETTER       │                      │     │
│     │                    │                     │                      │     │
│     │                    │ Move to DLQ         │                      │     │
│     │                    │────────────────────▶│ dlq.ocr...           │     │
│     │                    │                     │                      │     │
│     │                    │──────────────────────────────────────────▶│     │
│     │                    │                     │   status=DEAD_LETTER │     │
│     │                    │                     │                      │     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Heartbeat Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEQUENCE: HEARTBEAT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Worker              Orchestrator                    Database              │
│     │                      │                              │                 │
│     │ [every 30 seconds]   │                              │                 │
│     │                      │                              │                 │
│     │ POST /internal/      │                              │                 │
│     │ heartbeat            │                              │                 │
│     │ {                    │                              │                 │
│     │   service_id,        │                              │                 │
│     │   access_key,        │                              │                 │
│     │   status: "idle",    │                              │                 │
│     │   current_job_id:    │                              │                 │
│     │     null             │                              │                 │
│     │ }                    │                              │                 │
│     │─────────────────────▶│                              │                 │
│     │                      │ validate                     │                 │
│     │                      │ access_key                   │                 │
│     │                      │                              │                 │
│     │                      │ INSERT INTO                  │                 │
│     │                      │ heartbeats                   │                 │
│     │                      │─────────────────────────────▶│                 │
│     │                      │                              │                 │
│     │◀─────────────────────│ 200 OK                       │                 │
│     │                      │                              │                 │
│     │                      │                              │                 │
│     │ [processing a job]   │                              │                 │
│     │                      │                              │                 │
│     │ POST /internal/      │                              │                 │
│     │ heartbeat            │                              │                 │
│     │ {                    │                              │                 │
│     │   status:"processing"│                              │                 │
│     │   current_job_id:    │                              │                 │
│     │     "job_abc",       │                              │                 │
│     │   progress: {        │                              │                 │
│     │     files_completed: │                              │                 │
│     │       2,             │                              │                 │
│     │     files_total: 5   │                              │                 │
│     │   }                  │                              │                 │
│     │ }                    │                              │                 │
│     │─────────────────────▶│                              │                 │
│     │                      │                              │                 │
│     │                      │ ┌─────────────────────────┐  │                 │
│     │                      │ │ Heartbeat Monitor Task  │  │                 │
│     │                      │ │ (runs every 30s)        │  │                 │
│     │                      │ │                         │  │                 │
│     │                      │ │ For each service:       │  │                 │
│     │                      │ │ - Check last heartbeat  │  │                 │
│     │                      │ │ - If > 90s → DEAD       │  │                 │
│     │                      │ │ - If stalled → reassign │  │                 │
│     │                      │ └─────────────────────────┘  │                 │
│     │                      │                              │                 │
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
│                                   ▼                                         │
│                           ┌───────────────┐                                 │
│                           │  VALIDATING   │                                 │
│                           │ (Check format)│                                 │
│                           └───────┬───────┘                                 │
│                                   │                                         │
│                          ┌────────┼────────┐                               │
│                          │                 │                               │
│                       Valid            Invalid                              │
│                          │                 │                               │
│                          ▼                 ▼                               │
│              ┌───────────────┐     ┌───────────────┐                       │
│              │    QUEUED     │     │   REJECTED    │                       │
│              │  (In queue)   │     │  (Terminal)   │                       │
│              └───────┬───────┘     └───────────────┘                       │
│                      │                                                      │
│          ┌───────────┼───────────┐                                         │
│          │           │           │                                         │
│     User Cancel  Worker picks  (stays in queue)                            │
│          │           │                                                      │
│          ▼           ▼                                                      │
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
│           ▼            ▼            ▼                                      │
│    ┌───────────┐ ┌──────────┐ ┌───────────┐                               │
│    │ COMPLETED │ │ RETRYING │ │  FAILED   │                               │
│    │ (Success) │ │          │ │(Terminal) │                               │
│    └───────────┘ └────┬─────┘ └───────────┘                               │
│                       │                                                     │
│                       │ Orchestrator decides:                              │
│                 ┌─────┼──────┐                                             │
│               Yes           No                                              │
│            (retry<3)    (retry≥3)                                          │
│                 │            │                                              │
│                 ▼            ▼                                              │
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
│  │ PARTIAL_SUCCESS  │ Mix: ≥1 COMPLETED + ≥1 terminal failure         │   │
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
| Frontend | API Server | HTTP/REST | Session token | JSON |
| API Server | Modules | Function call | (internal) | Python objects |
| Upload Module | MinIO | S3 API | Storage creds | Binary |
| Job Module | NATS | Publish | - | JSON message |
| NATS | Worker | Pull | - | JSON message |
| Worker | File Proxy | HTTP/REST | access_key | Stream/JSON |
| File Proxy | MinIO | S3 API | Storage creds | Binary |
| Worker | Orchestrator | HTTP/REST | access_key | JSON (status/heartbeat) |
| All Modules | SQLite | SQL | - | Python objects |

**Layer Boundaries:**
- Edge ↔ Orchestration: Storage credentials, internal function calls
- Orchestration ↔ Processing: Queue (NATS), File Proxy API, Heartbeat API
- Processing → Edge: **FORBIDDEN** (must go through Orchestration)
