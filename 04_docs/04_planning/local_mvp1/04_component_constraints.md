# OCR Platform Local MVP1 - Component Output Constraints

> Version: 2.0 | Phase: Local MVP 1
> Aligned with: SA v3.1

---

## 1. Overview

Tài liệu này định nghĩa các constraints cho output của từng component. Mỗi component phải tuân thủ các ràng buộc này để đảm bảo tính nhất quán và đúng layer separation.

---

## 2. Layer Constraints (CRITICAL)

### 2.1 Layer Communication Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER CONSTRAINTS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   EDGE LAYER                                                                 │
│   ├── Components: Frontend, API Server, MinIO (Object Storage)              │
│   ├── Can access: Orchestration (via internal calls)                        │
│   └── MinIO credentials: YES (API Server has them)                          │
│                                                                              │
│   ORCHESTRATION LAYER                                                        │
│   ├── Components: Auth, Upload, Job, File Proxy modules + NATS + SQLite     │
│   ├── Can access: Edge (File Proxy has storage creds)                       │
│   ├── Can access: Processing (via Queue, File Proxy API)                    │
│   └── MinIO credentials: YES (File Proxy has them)                          │
│                                                                              │
│   PROCESSING LAYER                                                           │
│   ├── Components: OCR Worker                                                 │
│   ├── Can access: Orchestration (via File Proxy API, Heartbeat API)         │
│   ├── CANNOT access: Edge (FORBIDDEN - vượt cấp)                            │
│   └── MinIO credentials: NO (must use File Proxy)                           │
│                                                                              │
│   FORBIDDEN PATHS:                                                           │
│   ✗ Worker → MinIO (Processing → Edge)                                      │
│   ✗ Worker → SQLite directly (Processing → Orchestration internals)         │
│                                                                              │
│   VALID PATHS:                                                               │
│   ✓ Worker → File Proxy → MinIO                                             │
│   ✓ Worker → Orchestrator API → SQLite                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Worker Environment Constraints

| Environment Variable | ALLOWED | FORBIDDEN |
|---------------------|---------|-----------|
| `WORKER_SERVICE_ID` | ✅ | |
| `WORKER_ACCESS_KEY` | ✅ | |
| `WORKER_FILTER_SUBJECT` | ✅ | |
| `NATS_URL` | ✅ | |
| `FILE_PROXY_URL` | ✅ | |
| `ORCHESTRATOR_URL` | ✅ | |
| `MINIO_ENDPOINT` | | ❌ FORBIDDEN |
| `MINIO_ACCESS_KEY` | | ❌ FORBIDDEN |
| `MINIO_SECRET_KEY` | | ❌ FORBIDDEN |
| `DATABASE_URL` | | ❌ FORBIDDEN |

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
| **Output Format** | `txt` or `json` | "Invalid output format" |
| **Retention** | 1, 6, 24, or 168 hours | "Invalid retention period" |

### 3.2 State Constraints

| State | Constraint |
|-------|------------|
| **Auth Token** | Must be present for protected routes |
| **Upload Config** | output_format and retention_hours required |
| **Polling** | Stop when request status is terminal |
| **Session** | Clear on logout or 401 response |

### 3.3 UI Display Constraints

| Component | Constraint |
|-----------|------------|
| **Job Status Badge** | Must show all states including REJECTED, DEAD_LETTER |
| **Request Status** | Must show PARTIAL_SUCCESS correctly |
| **Cancel Button** | Only show if any job is QUEUED |
| **Retry Count** | Show retry_count/max_retries for failed jobs |

---

## 4. API Server Constraints

### 4.1 Request Validation

| Endpoint | Field | Constraint | Rejection |
|----------|-------|------------|-----------|
| `/auth/register` | email | Valid email, unique | 400/409 |
| `/auth/register` | password | 8-128 chars | 400 |
| `/upload` | files | 1-20 files | 400 |
| `/upload` | files | Total <= 50MB | 400 |
| `/upload` | output_format | `txt` or `json` | 400 |
| `/upload` | retention_hours | 1, 6, 24, or 168 | 400 |
| All protected | token | Valid session | 401 |
| `/requests/{id}` | owner | Must match user | 403 |
| `/internal/*` | access_key | Valid, enabled service | 401 |

### 4.2 Response Constraints

| Aspect | Constraint |
|--------|------------|
| **Response Time** | < 200ms for non-upload endpoints |
| **Upload Response** | < 5s per file |
| **Timestamps** | ISO 8601 format with timezone (UTC) |
| **IDs** | Prefixed (usr_, req_, job_, file_, res_) |
| **Error Response** | Must include code, message |
| **Job Status** | Must be valid enum value |

### 4.3 Authentication Constraints

| Aspect | Constraint |
|--------|------------|
| **User Token Format** | `ses_` prefix + 32 random chars |
| **Token Lifetime** | 24 hours (SESSION_EXPIRES_HOURS) |
| **Password Hash** | bcrypt, cost factor 10 |
| **access_key Format** | `sk_` prefix + identifier |

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
| **Filename** | Sanitize | Alphanumeric + underscore | Rename |

### 5.2 Storage Output Constraints

| Aspect | Constraint |
|--------|------------|
| **Bucket** | `uploads` (Edge layer) |
| **Object Key** | `{user_id}/{request_id}/{file_id}.{ext}` |
| **File ID** | `file_` + 12 alphanumeric |

### 5.3 Job Creation Constraints

| Field | Constraint |
|-------|------------|
| **Initial Status** | `SUBMITTED` |
| **method** | Copy from request |
| **tier** | Copy from request |
| **output_format** | Copy from request |
| **retry_count** | 0 |
| **max_retries** | 3 (default) |

---

## 6. Job Module Constraints

### 6.1 State Machine Transitions (CRITICAL)

| From | To | Trigger | Valid? |
|------|-----|---------|--------|
| SUBMITTED | VALIDATING | Auto | ✅ |
| VALIDATING | QUEUED | File valid | ✅ |
| VALIDATING | REJECTED | File invalid | ✅ |
| QUEUED | PROCESSING | Worker picks | ✅ |
| QUEUED | CANCELLED | User cancel | ✅ |
| PROCESSING | COMPLETED | Success | ✅ |
| PROCESSING | RETRYING | Retriable error | ✅ |
| PROCESSING | FAILED | Non-retriable error | ✅ |
| RETRYING | QUEUED | Delay elapsed, retry < max | ✅ |
| RETRYING | DEAD_LETTER | retry >= max | ✅ |
| * | * | Any other | ❌ INVALID |

### 6.2 Retry Constraints (Orchestrator)

| Aspect | Constraint |
|--------|------------|
| **Who retries** | Orchestrator (NOT Worker) |
| **Max Retries** | 3 (max_retries field) |
| **Backoff Formula** | delay = 1s × 2^retry_count |
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
| Mix: ≥1 COMPLETED + ≥1 terminal failure | `PARTIAL_SUCCESS` |
| All jobs CANCELLED | `CANCELLED` |

### 6.4 Job Output Fields

| Field | When Set | Value |
|-------|----------|-------|
| `started_at` | QUEUED → PROCESSING | Current timestamp |
| `completed_at` | → COMPLETED/FAILED/DEAD_LETTER | Current timestamp |
| `processing_time_ms` | → COMPLETED | Actual duration |
| `result_path` | → COMPLETED | Object key in results bucket |
| `worker_id` | → PROCESSING | Service ID of worker |
| `retry_count` | → RETRYING | Increment |
| `error_history` | → RETRYING/FAILED | Append error |

---

## 7. File Proxy Service Constraints

### 7.1 Access Control (ACL)

| Check | Constraint | Fail Response |
|-------|------------|---------------|
| **access_key present** | X-Access-Key header | 401 |
| **access_key valid** | Exists in services table | 401 |
| **Service enabled** | service.enabled = true | 401 |
| **Method authorized** | job.method in service.allowed_methods | 403 |
| **Tier authorized** | job.tier in service.allowed_tiers | 403 |
| **Job exists** | Job record found | 404 |
| **File exists** | File record found | 404 |

### 7.2 Download Constraints

| Aspect | Constraint |
|--------|------------|
| **Endpoint** | POST /internal/file-proxy/download |
| **Request Body** | `{ job_id }` |
| **Response** | Streaming file content |
| **Content-Type** | Match file's MIME type |
| **Logging** | Log every access (audit trail) |

### 7.3 Upload Constraints

| Aspect | Constraint |
|--------|------------|
| **Endpoint** | POST /internal/file-proxy/upload |
| **Result Bucket** | `results` (Edge layer) |
| **Result Key** | `{request_id}/{job_id}.{format}` |
| **Max Size** | 5MB |
| **Allowed Formats** | txt (Phase 1), json (Phase 2) |

---

## 8. NATS Queue Constraints

### 8.1 Stream Configuration

| Stream | Config | Value |
|--------|--------|-------|
| **OCR_JOBS** | Subjects | `ocr.>` |
| | Storage | File |
| | Max Age | 24h |
| | Retention | Limits (1GB) |
| **OCR_DLQ** | Subjects | `dlq.ocr.>` |
| | Storage | File |
| | Max Age | 7d |

### 8.2 Subject Pattern

| Pattern | Example | Description |
|---------|---------|-------------|
| `ocr.{method}.tier{tier}` | `ocr.text_raw.tier0` | Normal jobs |
| `dlq.ocr.{method}.tier{tier}` | `dlq.ocr.text_raw.tier0` | Dead letter |

### 8.3 Message Constraints

| Field | Type | Constraint |
|-------|------|------------|
| `job_id` | string | Valid job ID |
| `request_id` | string | Valid request ID |
| `file_id` | string | Valid file ID |
| `method` | string | Exact match (no wildcard) |
| `tier` | int | Exact match |
| `output_format` | string | `txt` or `json` |
| `retry_count` | int | 0-3 |
| `error_history` | array | JSON serializable |

### 8.4 Consumer Constraints

| Aspect | Constraint |
|--------|------------|
| **Filter** | Specific subject (e.g., `ocr.text_raw.tier0`) |
| **No Wildcard** | Workers MUST NOT use wildcards |
| **Batch Size** | 1 (Phase 1) |
| **Ack Policy** | Explicit |
| **Ack Wait** | 30s |

---

## 9. OCR Worker Constraints

### 9.1 Configuration

| Config | Type | Default | Constraint |
|--------|------|---------|------------|
| `WORKER_SERVICE_ID` | string | - | Must match services table |
| `WORKER_ACCESS_KEY` | string | - | Must be valid |
| `WORKER_FILTER_SUBJECT` | string | - | Specific subject |
| `HEARTBEAT_INTERVAL_MS` | int | 30000 | >= 10000 |
| `JOB_TIMEOUT_SECONDS` | int | 300 | 60-600 |

### 9.2 Processing Constraints

| Aspect | Constraint |
|--------|------------|
| **Storage Access** | FORBIDDEN - use File Proxy only |
| **Concurrency** | 1 job at a time (Phase 1) |
| **Timeout** | JOB_TIMEOUT_SECONDS |
| **Temp Directory** | `/tmp/ocr_worker/` |
| **Input File** | `/tmp/ocr_worker/{job_id}_input.{ext}` |
| **Output File** | `/tmp/ocr_worker/{job_id}_result.{format}` |
| **Cleanup** | MANDATORY after every job |

### 9.3 Retry Behavior (CRITICAL)

| Aspect | Constraint |
|--------|------------|
| **Who retries** | ORCHESTRATOR (not Worker) |
| **Worker action on error** | Report to Orchestrator, then ACK message |
| **Worker NEVER** | NAK message, wait and retry, keep message |
| **Error classification** | Worker classifies as retriable/non-retriable |
| **Error report** | POST /internal/jobs/{id}/status with error details |

### 9.4 Heartbeat Constraints

| Aspect | Constraint |
|--------|------------|
| **Interval** | Every HEARTBEAT_INTERVAL_MS (30s) |
| **Endpoint** | POST /internal/heartbeat |
| **Required Fields** | service_id, status, current_job_id |
| **Status Values** | idle, processing, uploading, error |
| **On idle** | current_job_id = null |

### 9.5 Output Constraints

| Output | Constraint |
|--------|------------|
| **Format** | txt (Phase 1), json (Phase 2) |
| **Encoding** | UTF-8 |
| **Line Endings** | LF (Unix) |
| **Max Size** | 5MB |

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
| API Server | Edge | ✅ YES |
| Upload Module | Orchestration (via Edge context) | ✅ YES |
| File Proxy | Orchestration | ✅ YES |
| Worker | Processing | ❌ NO (FORBIDDEN) |

### 10.3 Object Key Patterns

| Bucket | Pattern | Example |
|--------|---------|---------|
| `uploads` | `{user_id}/{request_id}/{file_id}.{ext}` | `usr_abc/req_123/file_001.png` |
| `results` | `{request_id}/{job_id}.{format}` | `req_123/job_001.txt` |
| `deleted` | `{bucket}/{timestamp}/{original_key}` | `uploads/1705312200/usr_abc/...` |

---

## 11. SQLite Database Constraints

### 11.1 Connection

| Aspect | Constraint |
|--------|------------|
| **Mode** | WAL (Write-Ahead Logging) |
| **Location** | `./data/ocr_platform.db` |
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
| output_format | `txt` or `json` |

**requests table:**
| Column | Constraint |
|--------|------------|
| status | Valid RequestStatus enum |
| output_format | `txt` or `json` |
| retention_hours | 1, 6, 24, or 168 |
| completed_files + failed_files <= total_files | Always |

**heartbeats table:**
| Column | Constraint |
|--------|------------|
| status | `idle`, `processing`, `uploading`, `error` |
| received_at | Auto-set to current timestamp |

---

## 12. Error Handling Constraints

### 12.1 Error Classification (Worker)

| Error Type | Examples | retriable |
|------------|----------|-----------|
| Timeout | OCR timeout, download timeout | true |
| Network | Connection refused, DNS failure | true |
| Temp File | Disk full, permission denied | true |
| Invalid File | Corrupted, unsupported format | false |
| Not Found | File deleted, wrong ID | false |
| Access Denied | Invalid access_key, disabled | false |

### 12.2 Error Reporting

| Aspect | Constraint |
|--------|------------|
| **Error message** | Max 1000 chars |
| **error_history** | Max 4 entries (1 initial + 3 retries) |
| **Stack trace** | Log only, NOT in API response |
| **Sensitive data** | NEVER include passwords, tokens |

---

## 13. Performance Constraints

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

## 14. Validation Chain Summary

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
│   └── retention_hours valid                                                 │
│                                                                              │
│   API SERVER (Edge)                                                          │
│   ├── Pydantic schema validation                                            │
│   ├── Session token valid (user endpoints)                                  │
│   ├── access_key valid (internal endpoints)                                 │
│   └── Resource ownership check                                              │
│                                                                              │
│   UPLOAD MODULE (Orchestration)                                              │
│   ├── MIME type check                                                       │
│   ├── Magic bytes check                                                     │
│   ├── File size check                                                       │
│   └── Batch limits check                                                    │
│                                                                              │
│   JOB MODULE (Orchestration)                                                 │
│   ├── State transition valid                                                │
│   ├── Retry logic (retriable, count < max)                                  │
│   └── Request status aggregation                                            │
│                                                                              │
│   FILE PROXY (Orchestration)                                                 │
│   ├── access_key valid                                                      │
│   ├── Service enabled                                                       │
│   ├── Method/tier authorized                                                │
│   └── Job/file exists                                                       │
│                                                                              │
│   WORKER (Processing)                                                        │
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

## 15. Configuration Parameters Summary

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_FILE_SIZE_MB` | 10 | Per file |
| `MAX_BATCH_SIZE_MB` | 50 | Total batch |
| `MAX_FILES_PER_BATCH` | 20 | File count |
| `MAX_RETRIES` | 3 | Per job |
| `RETRY_BASE_DELAY_MS` | 1000 | Backoff base |
| `JOB_TIMEOUT_SECONDS` | 300 | OCR timeout |
| `FILE_RETENTION_HOURS` | 24 | Default retention |
| `RESULT_RETENTION_DAYS` | 7 | Result files |
| `WORKER_POLL_INTERVAL_MS` | 1000 | Queue poll |
| `HEARTBEAT_INTERVAL_MS` | 30000 | Heartbeat |
| `HEARTBEAT_TIMEOUT_SECONDS` | 90 | Dead detection |
| `SESSION_EXPIRES_HOURS` | 24 | User session |
| `SOFT_DELETE_RETENTION_DAYS` | 7 | Recovery window |
| `DEFAULT_OUTPUT_FORMAT` | txt | OCR output |
