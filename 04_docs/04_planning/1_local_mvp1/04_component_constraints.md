# OCR Platform Local MVP1 - Component Output Constraints

> Version: 3.0 | Phase: Local MVP 1
> Aligned with: SA v3.1 + Actual Implementation

---

## 1. Overview

Constraints cho output của từng component. Mỗi component phải tuân thủ các ràng buộc này để đảm bảo tính nhất quán và đúng layer separation.

---

## 2. Layer Constraints (CRITICAL)

### 2.1 Layer Communication Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER CONSTRAINTS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   EDGE LAYER                                                                 │
│   ├── Components: Frontend, API Server (port 8000), MinIO                   │
│   ├── Can access: Orchestration (via internal calls)                        │
│   └── MinIO credentials: YES (API Server has them)                          │
│                                                                              │
│   ORCHESTRATION LAYER                                                        │
│   ├── Components: Auth, Upload, Job, File Proxy + NATS + SQLite            │
│   ├── Can access: Edge (File Proxy has storage creds)                       │
│   ├── Can access: Processing (via Queue, File Proxy API, Register API)      │
│   └── MinIO credentials: YES (File Proxy has them)                          │
│                                                                              │
│   PROCESSING LAYER                                                           │
│   ├── Components: OCR Workers (PaddleOCR, Tesseract)                        │
│   ├── Can access: Orchestration (via File Proxy, Heartbeat, Register)       │
│   ├── CANNOT access: Edge (FORBIDDEN)                                       │
│   └── MinIO credentials: NO (must use File Proxy)                           │
│                                                                              │
│   FORBIDDEN PATHS:                                                           │
│   x Worker -> MinIO (Processing -> Edge)                                    │
│   x Worker -> SQLite directly (Processing -> Orchestration internals)       │
│                                                                              │
│   VALID PATHS:                                                               │
│   + Worker -> File Proxy -> MinIO                                           │
│   + Worker -> Orchestrator API -> SQLite                                    │
│   + Worker -> Register API (self-registration on startup)                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Worker Environment Constraints

| Environment Variable | ALLOWED | FORBIDDEN |
|---------------------|---------|-----------|
| `WORKER_SERVICE_TYPE` | yes | |
| `WORKER_SERVICE_ID` (optional override) | yes | |
| `WORKER_ACCESS_KEY` (optional, empty=pending) | yes | |
| `WORKER_FILTER_SUBJECT` | yes | |
| `WORKER_DISPLAY_NAME` | yes | |
| `WORKER_DESCRIPTION` | yes | |
| `WORKER_DEV_CONTACT` | yes | |
| `WORKER_ALLOWED_METHODS` | yes | |
| `WORKER_ALLOWED_TIERS` | yes | |
| `NATS_URL` | yes | |
| `FILE_PROXY_URL` | yes | |
| `ORCHESTRATOR_URL` | yes | |
| `MINIO_ENDPOINT` | | FORBIDDEN |
| `MINIO_ACCESS_KEY` | | FORBIDDEN |
| `MINIO_SECRET_KEY` | | FORBIDDEN |
| `DATABASE_URL` | | FORBIDDEN |

---

## 3. Frontend Constraints

### 3.1 Input Validation (Client-side)

| Constraint | Rule | Error Message |
|------------|------|---------------|
| **Email Format** | Valid email regex | "Invalid email format" |
| **Password Length** | >= 8 characters | "Password must be at least 8 characters" |
| **File Type** | PNG, JPEG, PDF only | "Only PNG, JPEG, and PDF files are allowed" |
| **File Size** | <= 10MB per file | "File size must not exceed 10MB" |
| **Batch Count** | <= 20 files | "Maximum 20 files per upload" |
| **Batch Size** | <= 50MB total | "Total upload size must not exceed 50MB" |
| **Output Format** | Dynamic per service (`txt`, `json`, `md`) — filtered from `supported_output_formats` via services API | "Invalid output format" |

### 3.2 State Constraints

| State | Constraint |
|-------|------------|
| **Auth Token** | Stored in localStorage, sent as Bearer token |
| **Upload Config** | output_format and retention_hours required |
| **Polling** | Stop when request status is terminal |
| **Session** | Clear on logout or 401 response, redirect to /login |
| **Admin Routes** | Only accessible if user.is_admin = true |

### 3.3 UI Display Constraints

| Component | Constraint |
|-----------|------------|
| **Layout** | Sidebar navigation (NOT top header) |
| **Job Status Badge** | Must show all states including REJECTED, DEAD_LETTER |
| **Request Status** | Must show PARTIAL_SUCCESS correctly |
| **Cancel Button** | Only show if any job is QUEUED |
| **Retry Count** | Show retry_count/max_retries for failed jobs |
| **Admin Section** | Show in sidebar only if user.is_admin = true |
| **Service Management** | Filter by status: ALL/PENDING/APPROVED/DISABLED/REJECTED |

---

## 4. API Server Constraints

### 4.1 Request Validation

| Endpoint | Field | Constraint | Rejection |
|----------|-------|------------|-----------|
| `/auth/register` | email | Valid email, unique | 400/409 |
| `/auth/register` | password | 8-128 chars | 400 |
| `/upload` | files | 1-20 files | 400 |
| `/upload` | files | Total <= 50MB | 400 |
| `/upload` | output_format | Must be in selected service's `supported_output_formats` (e.g. `txt`, `json`, `md`) | 400 |
| All protected | token | Valid session (lookup by token field) | 401 |
| `/admin/*` | user | Must have is_admin = true | 403 |
| `/requests/{id}` | owner | Must match user_id | 403 |
| `/internal/*` | access_key | Valid ServiceType with APPROVED status | 401 |

### 4.2 Response Constraints

| Aspect | Constraint |
|--------|------------|
| **Response Time** | < 200ms for non-upload endpoints |
| **Upload Response** | < 5s per file |
| **Timestamps** | ISO 8601 format with timezone (UTC) |
| **IDs** | UUID v4 (36 chars) |
| **Error Response** | Must include code, message |
| **Job Status** | Must be valid enum value |

### 4.3 Authentication Constraints

| Aspect | Constraint |
|--------|------------|
| **Session Token** | 64 random chars (stored in sessions.token field) |
| **Session ID** | UUID (separate from token) |
| **Token Lifetime** | 24 hours (session_expire_hours) |
| **Password Hash** | bcrypt |
| **access_key Format** | `sk_` prefix + identifier |
| **Token Storage** | Frontend stores in localStorage, sends as Bearer |

---

## 5. Upload Module Constraints

### 5.1 File Validation

| Validation | Method | Pass | Fail |
|------------|--------|------|------|
| **MIME Type** | HTTP header | image/png, image/jpeg, application/pdf | Skip file |
| **Magic Bytes** | File header | Match signature | Skip file |
| **File Size** | Content-Length | <= 10MB | Skip file |
| **Batch Count** | Array length | <= 20 | Reject batch |
| **Batch Size** | Sum | <= 50MB | Reject batch |

> **NOTE:** All files are validated FIRST, then records are created for valid files.

### 5.2 Storage Output Constraints

| Aspect | Constraint |
|--------|------------|
| **Bucket** | `uploads` (Edge layer) |
| **Object Key** | Generated by `generate_object_key()` (storage utils) |

### 5.3 Job Creation Constraints

| Field | Constraint |
|-------|------------|
| **Initial Status** | `SUBMITTED` |
| **method** | Copy from request |
| **tier** | Copy from request |
| **retry_count** | 0 |
| **max_retries** | 3 (default) |
| **output_format** | NOT on Job (lives on Request only) |

---

## 6. Job Module Constraints

### 6.1 State Machine Transitions (CRITICAL)

| From | To | Trigger | Valid? |
|------|-----|---------|--------|
| SUBMITTED | VALIDATING | Auto | yes |
| VALIDATING | QUEUED | File valid | yes |
| VALIDATING | REJECTED | File invalid | yes |
| QUEUED | PROCESSING | Worker picks | yes |
| QUEUED | CANCELLED | User cancel | yes |
| PROCESSING | COMPLETED | Success | yes |
| PROCESSING | RETRYING | Retriable error | yes |
| PROCESSING | FAILED | Non-retriable error | yes |
| RETRYING | QUEUED | Delay elapsed, retry < max | yes |
| RETRYING | DEAD_LETTER | retry >= max | yes |
| * | * | Any other | INVALID |

### 6.2 Retry Constraints (Orchestrator)

| Aspect | Constraint |
|--------|------------|
| **Who retries** | Orchestrator (NOT Worker) |
| **Max Retries** | 3 (max_retries field) |
| **Backoff Formula** | delay = 1s x 2^retry_count |
| **Delays** | 1s, 2s, 4s |
| **Retriable Errors** | Timeout, network, temp file |
| **Non-retriable** | Invalid file, corrupted, access denied |
| **After max retries** | Move to DEAD_LETTER, publish to DLQ |

### 6.3 Request Status Aggregation

| Condition | Status |
|-----------|--------|
| Any job QUEUED/PROCESSING/RETRYING | `PROCESSING` |
| All jobs COMPLETED | `COMPLETED` |
| All jobs FAILED/DEAD_LETTER/REJECTED | `FAILED` |
| Mix: >=1 COMPLETED + >=1 terminal failure | `PARTIAL_SUCCESS` |
| All jobs CANCELLED | `CANCELLED` |

### 6.4 Job Output Fields

| Field | When Set | Value |
|-------|----------|-------|
| `started_at` | QUEUED -> PROCESSING | Current timestamp |
| `completed_at` | -> COMPLETED/FAILED/DEAD_LETTER | Current timestamp |
| `processing_time_ms` | -> COMPLETED | Actual duration |
| `result_path` | -> COMPLETED | Object key in results bucket |
| `worker_id` | -> PROCESSING | Instance ID of worker |
| `retry_count` | -> RETRYING | Increment |
| `error_history` | -> RETRYING/FAILED | Append error |

---

## 7. File Proxy Service Constraints

### 7.1 Access Control (ACL)

| Check | Constraint | Fail Response |
|-------|------------|---------------|
| **access_key present** | X-Access-Key header | 401 |
| **access_key valid** | Exists in service_types table | 401 |
| **ServiceType status** | Must be APPROVED | 401 |
| **Method authorized** | job.method in service_type.allowed_methods | 403 |
| **Tier authorized** | job.tier in service_type.allowed_tiers | 403 |
| **Job exists** | Job record found | 404 |
| **File exists** | File record found | 404 |

### 7.2 Download Constraints

| Aspect | Constraint |
|--------|------------|
| **Endpoint** | POST /api/v1/internal/file-proxy/download |
| **Request Body** | `{ job_id }` |
| **Response** | Streaming file content |
| **Content-Type** | Match file's MIME type |

### 7.3 Upload Constraints

| Aspect | Constraint |
|--------|------------|
| **Endpoint** | POST /api/v1/internal/file-proxy/upload |
| **Result Bucket** | `results` (Edge layer) |
| **Result Key** | `{request_id}/{job_id}.{format}` |
| **Max Size** | 5MB |

---

## 8. NATS Queue Constraints

### 8.1 Stream Configuration

| Stream | Config | Value |
|--------|--------|-------|
| **OCR_JOBS** | Subjects | `ocr.>` |
| | Storage | File |
| | Max Age | 24h |
| **OCR_DLQ** | Subjects | `dlq.>` |
| | Storage | File |
| | Max Age | 7d |

### 8.2 Subject Pattern

| Pattern | Example | Description |
|---------|---------|-------------|
| `ocr.{method}.tier{tier}` | `ocr.text_raw.tier0`, `ocr.structured_extract.tier0` | Normal jobs |
| `dlq.{method}.tier{tier}` | `dlq.text_raw.tier0`, `dlq.structured_extract.tier0` | Dead letter |

> **NOTE:** DLQ subject is `dlq.{method}.tier{tier}` (not `dlq.ocr.{method}.tier{tier}`).

### 8.3 Message Constraints (JobMessage)

| Field | Type | Constraint |
|-------|------|------------|
| `job_id` | string | Valid job ID |
| `request_id` | string | Valid request ID |
| `file_id` | string | Valid file ID |
| `method` | string | Exact match |
| `tier` | int | Exact match |
| `output_format` | string | `txt`, `json`, or `md` (depends on service) |
| `object_key` | string | MinIO object key (NEW) |
| `retry_count` | int | 0-3 |

### 8.4 Consumer Constraints

| Aspect | Constraint |
|--------|------------|
| **Filter** | Specific subject (e.g., `ocr.text_raw.tier0`) |
| **No Wildcard** | Workers MUST NOT use wildcards |
| **Batch Size** | 1 (Phase 1) |
| **Ack Policy** | Explicit |

---

## 9. OCR Worker Constraints

### 9.1 Configuration

| Config | Type | Default | Constraint |
|--------|------|---------|------------|
| `WORKER_SERVICE_TYPE` | string | ocr-text-tier0 | Service type identifier |
| `WORKER_SERVICE_ID` | string | auto | Optional explicit instance ID override |
| `WORKER_ACCESS_KEY` | string | (empty) | Empty = wait for approval |
| `WORKER_FILTER_SUBJECT` | string | - | Specific subject |
| `WORKER_DISPLAY_NAME` | string | OCR Worker | Human-readable name |
| `WORKER_ALLOWED_METHODS` | string | text_raw | Comma-separated methods |
| `WORKER_ALLOWED_TIERS` | string | 0 | Comma-separated tiers |
| `HEARTBEAT_INTERVAL_MS` | int | 30000 | >= 10000 |
| `JOB_TIMEOUT_SECONDS` | int | 300 | 60-600 |

### 9.2 Processing Constraints

| Aspect | Constraint |
|--------|------------|
| **Storage Access** | FORBIDDEN - use File Proxy only |
| **Concurrency** | 1 job at a time (Phase 1) |
| **Timeout** | JOB_TIMEOUT_SECONDS |
| **Temp Directory** | `/tmp/ocr_worker/` (configurable via TEMP_DIR) |
| **Input File** | `/tmp/ocr_worker/{job_id}_input.{ext}` |
| **Output File** | `/tmp/ocr_worker/{job_id}_result.{format}` |
| **Cleanup** | MANDATORY after every job |
| **Engines** | PaddleOCR (GPU) or Tesseract (CPU), engine-specific |
| **Self-registration** | POST /api/v1/internal/register on startup |
| **Instance ID** | Auto-generated: `{service_type}-{hostname[:12]}` |

### 9.3 Retry Behavior (CRITICAL)

| Aspect | Constraint |
|--------|------------|
| **Who retries** | ORCHESTRATOR (not Worker) |
| **Worker action on error** | Report to Orchestrator, then ACK message |
| **Worker NEVER** | NAK message, wait and retry, keep message |
| **Error classification** | Worker classifies as retriable/non-retriable |
| **Error report** | PATCH /api/v1/internal/jobs/{id}/status with error details |

### 9.4 Heartbeat Constraints

| Aspect | Constraint |
|--------|------------|
| **Interval** | Every HEARTBEAT_INTERVAL_MS (30s) |
| **Endpoint** | POST /api/v1/internal/heartbeat |
| **Required Fields** | instance_id, status, current_job_id |
| **Status Values** | idle, processing, error |
| **On idle** | current_job_id = null |

### 9.5 Output Constraints

| Output | Constraint |
|--------|------------|
| **Format** | txt, json (text_raw workers); json, md (structured_extract workers) |
| **Encoding** | UTF-8 |
| **Line Endings** | LF (Unix) |
| **Max Size** | 5MB |

### 9.6 Engine Constraints

| Engine | Deployment | Runtime | Handler |
|--------|-----------|---------|---------|
| **PaddleOCR** | `deploy/paddle-text/` | Dockerfile (GPU, nvidia) | `engines/paddle_text/handler.py` |
| **PaddleOCR-VL** | `deploy/paddle-vl/` | Dockerfile (GPU, nvidia) | `engines/paddle_vl/handler.py` |
| **Tesseract** | `deploy/tesseract-cpu/` | Dockerfile.cpu (CPU) | `engines/tesseract/handler.py` |

Each engine has: `handler.py`, `preprocessing.py`, `postprocessing.py`

---

## 10. MinIO Storage Constraints (Edge Layer)

### 10.1 Bucket Configuration

| Bucket | Purpose | Who Writes | Who Reads |
|--------|---------|------------|-----------|
| `uploads` | Source files | API Server (Edge) | File Proxy (Orch) |
| `results` | OCR output | File Proxy (Orch) | API Server (Edge) |
| `deleted` | Soft-deleted | File Proxy (Orch) | File Proxy (Orch) |

### 10.2 Access Control

| Component | Layer | Has Credentials? |
|-----------|-------|------------------|
| API Server | Edge | YES |
| Upload Module | Orchestration (via Edge context) | YES |
| File Proxy | Orchestration | YES |
| Worker | Processing | NO (FORBIDDEN) |

### 10.3 Object Key Patterns

| Bucket | Pattern | Example |
|--------|---------|---------|
| `uploads` | Generated by `generate_object_key()` | `usr_abc/req_123/file_001.png` |
| `results` | `{request_id}/{job_id}.{format}` | `req_123/job_001.txt` |

---

## 11. SQLite Database Constraints

### 11.1 Connection

| Aspect | Constraint |
|--------|------------|
| **Mode** | WAL (Write-Ahead Logging) |
| **Location** | `./data/ocr_fresh.db` |
| **Concurrency** | ~100 writes/sec with WAL |
| **Busy Timeout** | 5000ms |

### 11.2 Table Constraints

**jobs table:**
| Column | Constraint |
|--------|------------|
| status | Valid JobStatus enum |
| retry_count | 0 to max_retries |
| max_retries | Default 3 |
| error_history | JSON array, max 4 entries |
| output_format | NOT present (lives on requests table) |

**requests table:**
| Column | Constraint |
|--------|------------|
| status | Valid RequestStatus enum |
| output_format | `txt`, `json`, or `md` (validated against service's supported_output_formats) |
| retention_hours | Default 168 (7 days) |
| expires_at | Calculated from created_at + retention_hours |
| completed_files + failed_files <= total_files | Always |

**service_types table:**
| Column | Constraint |
|--------|------------|
| status | PENDING, APPROVED, DISABLED, REJECTED |
| access_key | Unique, generated on approval, nullable |
| allowed_methods | JSON array |
| allowed_tiers | JSON array |
| supported_output_formats | JSON array (default: `["txt","json"]`), declared by worker at registration |

**service_instances table:**
| Column | Constraint |
|--------|------------|
| status | WAITING, ACTIVE, PROCESSING, DRAINING, DEAD |
| service_type_id | FK -> service_types |
| last_heartbeat_at | Updated on each heartbeat |

**heartbeats table:**
| Column | Constraint |
|--------|------------|
| instance_id | FK -> service_instances (NOT service_id) |
| status | `idle`, `processing`, `error` |
| received_at | Auto-set to current timestamp |

---

## 12. Service Type / Instance Constraints (NEW)

### 12.1 Service Type Lifecycle

| Transition | Trigger | Side Effects |
|-----------|---------|--------------|
| (new) -> PENDING | Worker registers new type | Instances created as WAITING |
| PENDING -> APPROVED | Admin approves | Generate access_key, instances -> ACTIVE |
| PENDING -> REJECTED | Admin rejects (with reason) | Terminal state |
| APPROVED -> DISABLED | Admin disables | Instances -> WAITING |
| DISABLED -> APPROVED | Admin enables | Instances -> ACTIVE |

### 12.2 Service Instance Lifecycle

| Transition | Trigger | Side Effects |
|-----------|---------|--------------|
| (new) -> WAITING | Type is PENDING/DISABLED | Worker cannot process jobs |
| (new) -> ACTIVE | Type is APPROVED | Worker can process jobs |
| ACTIVE -> PROCESSING | Worker picks job | current_job_id set |
| PROCESSING -> ACTIVE | Job completes | current_job_id cleared |
| * -> DEAD | Worker deregisters or heartbeat timeout | Job returned to QUEUED |

### 12.3 Admin Constraints

| Action | Constraint |
|--------|------------|
| **Approve** | Only PENDING types can be approved |
| **Reject** | Only PENDING types can be rejected, requires reason |
| **Disable** | Only APPROVED types can be disabled |
| **Enable** | Only DISABLED types can be enabled |
| **Delete** | Hard delete type + all instances |
| **Admin creation** | Via CLI: `make create-admin EMAIL=... PASS=...` |
| **Promote/Demote** | Via CLI: `make promote EMAIL=...`, `make demote EMAIL=...` |

---

## 13. Error Handling Constraints

### 13.1 Error Classification (Worker)

| Error Type | Examples | retriable |
|------------|----------|-----------|
| Timeout | OCR timeout, download timeout | true |
| Network | Connection refused, DNS failure | true |
| Temp File | Disk full, permission denied | true |
| Invalid File | Corrupted, unsupported format | false |
| Not Found | File deleted, wrong ID | false |
| Access Denied | Invalid access_key, type not approved | false |

### 13.2 Error Reporting

| Aspect | Constraint |
|--------|------------|
| **Error message** | Max 1000 chars |
| **error_history** | Max 4 entries (1 initial + 3 retries) |
| **Stack trace** | Log only, NOT in API response |
| **Sensitive data** | NEVER include passwords, tokens, access_keys |

---

## 14. Performance Constraints

| Metric | Target | Component |
|--------|--------|-----------|
| **API Response** | < 200ms (p95) | API Server |
| **File Upload** | < 5s per 10MB | Upload Module |
| **OCR Processing** | < 60s per 1MB | Worker |
| **Status Polling** | < 100ms | Job Module |
| **Queue Latency** | < 2s | NATS |
| **File Proxy** | < 500ms overhead | File Proxy |
| **Heartbeat** | < 200ms round-trip | Worker |

---

## 15. Validation Chain Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION CHAIN                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FRONTEND (Edge)                                                            │
│   ├── Email format                                                          │
│   ├── Password length >= 8                                                  │
│   ├── File type (extension)                                                 │
│   ├── File size <= 10MB                                                     │
│   ├── Batch count <= 20                                                     │
│   ├── Total size <= 50MB                                                    │
│   ├── output_format valid                                                   │
│   └── Admin route guard (is_admin check)                                    │
│                                                                              │
│   API SERVER (Edge)                                                          │
│   ├── Pydantic schema validation                                            │
│   ├── Session token valid (user endpoints, lookup by token)                 │
│   ├── is_admin check (admin endpoints)                                      │
│   ├── access_key valid + ServiceType APPROVED (internal endpoints)          │
│   └── Resource ownership check                                              │
│                                                                              │
│   UPLOAD MODULE (Orchestration)                                              │
│   ├── MIME type check                                                       │
│   ├── Magic bytes check                                                     │
│   ├── File size check                                                       │
│   ├── Batch limits check                                                    │
│   └── All files validated FIRST, then records created                       │
│                                                                              │
│   JOB MODULE (Orchestration)                                                 │
│   ├── State transition valid                                                │
│   ├── Retry logic (retriable, count < max)                                  │
│   └── Request status aggregation                                            │
│                                                                              │
│   FILE PROXY (Orchestration)                                                 │
│   ├── access_key valid                                                      │
│   ├── ServiceType status = APPROVED                                         │
│   ├── Method/tier authorized (from ServiceType)                             │
│   └── Job/file exists                                                       │
│                                                                              │
│   WORKER (Processing)                                                        │
│   ├── Self-registration on startup                                          │
│   ├── File readable                                                         │
│   ├── Processing timeout                                                    │
│   ├── Error classification                                                  │
│   └── Result valid                                                          │
│                                                                              │
│   LAYER CONSTRAINT: Worker CANNOT access MinIO directly                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16. Configuration Parameters Summary

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BACKEND_PORT` | 8000 | API server port |
| `DATABASE_URL` | sqlite:///./data/ocr_fresh.db | Database location |
| `MAX_FILE_SIZE_MB` | 10 | Per file |
| `MAX_BATCH_SIZE_MB` | 50 | Total batch |
| `MAX_FILES_PER_BATCH` | 20 | File count |
| `MAX_RETRIES` | 3 | Per job |
| `RETRY_BASE_DELAY_MS` | 1000 | Backoff base |
| `JOB_TIMEOUT_SECONDS` | 300 | OCR timeout |
| `DEFAULT_RETENTION_HOURS` | 168 | Default 7 days |
| `HEARTBEAT_INTERVAL_MS` | 30000 | Heartbeat |
| `HEARTBEAT_TIMEOUT_SECONDS` | 90 | Dead detection |
| `SESSION_EXPIRE_HOURS` | 24 | User session |
| `DEFAULT_OUTPUT_FORMAT` | txt | OCR output |
| `SEED_SERVICES` | (varies) | Dev: seed service types |
| `NATS_STREAM_NAME` | OCR_JOBS | Job stream |
| `NATS_DLQ_STREAM_NAME` | OCR_DLQ | Dead letter stream |

---

*Changelog v2.0 -> v3.0:*
- *Backend port: 8080 -> 8000*
- *Database: `ocr_platform.db` -> `ocr_fresh.db`*
- *Internal endpoints: `/internal/*` -> `/api/v1/internal/*`*
- *Job status update: POST -> PATCH*
- *Removed `Job.output_format` constraint (lives on Request)*
- *Default retention_hours: 24 -> 168 (7 days)*
- *Session.token is separate from Session.id*
- *Heartbeat uses `instance_id` (not `service_id`)*
- *Heartbeat status: removed "uploading", only idle/processing/error*
- *File Proxy ACL: validates against ServiceType (not legacy Service)*
- *DLQ subject: `dlq.{method}.tier{tier}` (not `dlq.ocr.{method}.tier{tier}`)*
- *JobMessage includes `object_key` field*
- *Added Section 12: Service Type / Instance Constraints*
- *Added Worker self-registration and multi-engine constraints*
- *Added Admin constraints (approve/reject/disable/enable/delete)*
- *Added worker environment variables for registration info*
