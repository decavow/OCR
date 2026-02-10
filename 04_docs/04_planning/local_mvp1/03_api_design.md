# OCR Platform Local MVP1 - API Design

> Version: 2.0 | Phase: Local MVP 1
> Aligned with: SA v3.1

---

## 1. API Overview

| Aspect | Specification |
|--------|---------------|
| **Base URL** | `http://localhost:8080/api/v1` |
| **Internal URL** | `http://localhost:8080/internal` |
| **Protocol** | HTTP/1.1 (HTTPS in Phase 2) |
| **Format** | JSON |
| **User Auth** | Session token (Cookie or Authorization header) |
| **Worker Auth** | access_key (X-Access-Key header) |
| **Docs** | Swagger UI: `/docs`, ReDoc: `/redoc` |

---

## 2. Common Response Formats

### 2.1 Success Response

```json
{
    "success": true,
    "data": { ... },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

### 2.2 Error Response

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human readable message",
        "details": { ... }
    },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

### 2.3 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `INVALID_FILE` | 400 | File validation failed |
| `BATCH_TOO_LARGE` | 400 | Batch exceeds limits |
| `INVALID_CONFIG` | 400 | Invalid output_format or retention |
| `UNAUTHORIZED` | 401 | Missing or invalid auth |
| `INVALID_CREDENTIALS` | 401 | Wrong email/password |
| `SESSION_EXPIRED` | 401 | Session no longer valid |
| `INVALID_ACCESS_KEY` | 401 | Worker access_key invalid |
| `FORBIDDEN` | 403 | Access denied to resource |
| `NOT_FOUND` | 404 | Resource not found |
| `EMAIL_EXISTS` | 409 | Email already registered |
| `INVALID_TRANSITION` | 409 | Invalid job state transition |
| `INTERNAL_ERROR` | 500 | Server error |

---

## 3. Authentication Endpoints

### 3.1 Register User

```
POST /api/v1/auth/register
```

**Request:**
```json
{
    "email": "user@example.com",
    "password": "securePassword123"
}
```

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "user": {
            "id": "usr_abc123",
            "email": "user@example.com",
            "created_at": "2024-01-15T10:30:00Z"
        },
        "token": "ses_xyz789..."
    }
}
```

---

### 3.2 Login

```
POST /api/v1/auth/login
```

**Request:**
```json
{
    "email": "user@example.com",
    "password": "securePassword123"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "user": {
            "id": "usr_abc123",
            "email": "user@example.com",
            "created_at": "2024-01-15T10:30:00Z"
        },
        "token": "ses_xyz789..."
    }
}
```

---

### 3.3 Logout

```
POST /api/v1/auth/logout
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "message": "Logged out successfully"
    }
}
```

---

### 3.4 Get Current User

```
GET /api/v1/auth/me
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "user": {
            "id": "usr_abc123",
            "email": "user@example.com",
            "created_at": "2024-01-15T10:30:00Z"
        }
    }
}
```

---

## 4. Upload Endpoints

### 4.1 Upload Files (Create Request)

```
POST /api/v1/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**Request (Form Data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | File[] | Yes | Image/PDF files (max 20) |
| `method` | string | No | OCR method (default: `text_raw`) |
| `tier` | int | No | Processing tier (default: `0`) |
| `output_format` | string | No | Output format: `txt`, `json` (default: `txt`) |
| `retention_hours` | int | No | File retention: 1, 6, 24, 168 (default: 24) |

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "request": {
            "id": "req_abc123",
            "method": "text_raw",
            "tier": 0,
            "output_format": "txt",
            "retention_hours": 24,
            "status": "PROCESSING",
            "total_files": 5,
            "completed_files": 0,
            "failed_files": 0,
            "created_at": "2024-01-15T10:30:00Z"
        },
        "summary": {
            "total_files": 5,
            "valid_files": 4,
            "skipped_files": [
                {
                    "name": "document.exe",
                    "reason": "Invalid file type"
                }
            ]
        },
        "jobs": [
            {
                "id": "job_001",
                "file_name": "image1.png",
                "status": "SUBMITTED"
            }
        ]
    }
}
```

**Errors:**
| Code | Condition |
|------|-----------|
| `VALIDATION_ERROR` | No files provided |
| `BATCH_TOO_LARGE` | > 20 files or > 50MB total |
| `INVALID_FILE` | All files invalid (none processed) |
| `INVALID_CONFIG` | Invalid output_format or retention_hours |

---

## 5. Request Endpoints

### 5.1 List Requests

```
GET /api/v1/requests
Authorization: Bearer {token}
```

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page (max 100) |
| `status` | string | - | Filter by status |

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "requests": [
            {
                "id": "req_abc123",
                "method": "text_raw",
                "tier": 0,
                "output_format": "txt",
                "status": "COMPLETED",
                "total_files": 4,
                "completed_files": 4,
                "failed_files": 0,
                "created_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:35:00Z"
            },
            {
                "id": "req_def456",
                "method": "text_raw",
                "tier": 0,
                "output_format": "txt",
                "status": "PARTIAL_SUCCESS",
                "total_files": 5,
                "completed_files": 3,
                "failed_files": 2,
                "created_at": "2024-01-15T11:00:00Z",
                "completed_at": "2024-01-15T11:10:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 45,
            "total_pages": 3
        }
    }
}
```

---

### 5.2 Get Request Detail

```
GET /api/v1/requests/{request_id}
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "request": {
            "id": "req_abc123",
            "method": "text_raw",
            "tier": 0,
            "output_format": "txt",
            "retention_hours": 24,
            "status": "PARTIAL_SUCCESS",
            "total_files": 4,
            "completed_files": 3,
            "failed_files": 1,
            "created_at": "2024-01-15T10:30:00Z",
            "completed_at": "2024-01-15T10:35:00Z"
        },
        "jobs": [
            {
                "id": "job_001",
                "file": {
                    "id": "file_001",
                    "name": "image1.png",
                    "size_bytes": 102400,
                    "page_count": 1
                },
                "status": "COMPLETED",
                "result": {
                    "id": "res_001",
                    "format": "txt",
                    "processing_time_ms": 1250
                },
                "retry_count": 0,
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:02Z",
                "completed_at": "2024-01-15T10:30:05Z"
            },
            {
                "id": "job_002",
                "file": {
                    "id": "file_002",
                    "name": "corrupted.jpg",
                    "size_bytes": 204800,
                    "page_count": 1
                },
                "status": "DEAD_LETTER",
                "error": {
                    "message": "OCR processing failed after 3 retries",
                    "retriable": true
                },
                "retry_count": 3,
                "error_history": [
                    {"error": "timeout", "retriable": true, "at": "..."},
                    {"error": "timeout", "retriable": true, "at": "..."},
                    {"error": "timeout", "retriable": true, "at": "..."}
                ],
                "created_at": "2024-01-15T10:30:00Z"
            },
            {
                "id": "job_003",
                "file": {
                    "id": "file_003",
                    "name": "invalid.gif",
                    "size_bytes": 50000,
                    "page_count": 1
                },
                "status": "REJECTED",
                "error": {
                    "message": "Unsupported file format: GIF",
                    "retriable": false
                },
                "retry_count": 0,
                "created_at": "2024-01-15T10:30:00Z"
            }
        ]
    }
}
```

---

### 5.3 Cancel Request

```
POST /api/v1/requests/{request_id}/cancel
Authorization: Bearer {token}
```

**Description:** Cancel all jobs that are still in QUEUED status. Jobs already PROCESSING cannot be cancelled.

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "request_id": "req_abc123",
        "cancelled_jobs": 2,
        "already_processing": 1,
        "message": "2 jobs cancelled, 1 job already processing"
    }
}
```

**Errors:**
| Code | Condition |
|------|-----------|
| `NOT_FOUND` | Request not found |
| `FORBIDDEN` | Not owner of request |
| `INVALID_TRANSITION` | No jobs available to cancel |

---

### 5.4 Download Request Results (ZIP)

```
GET /api/v1/requests/{request_id}/download
Authorization: Bearer {token}
```

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_failed` | bool | false | Include error info for failed jobs |

**Response (200 OK):**
```
Content-Type: application/zip
Content-Disposition: attachment; filename="req_abc123_results.zip"

[ZIP file containing all result files]
```

---

## 6. Job Endpoints

### 6.1 Get Job Detail

```
GET /api/v1/jobs/{job_id}
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "job": {
            "id": "job_001",
            "request_id": "req_abc123",
            "file": {
                "id": "file_001",
                "name": "image1.png",
                "size_bytes": 102400,
                "mime_type": "image/png",
                "page_count": 1
            },
            "status": "COMPLETED",
            "method": "text_raw",
            "tier": 0,
            "output_format": "txt",
            "retry_count": 0,
            "max_retries": 3,
            "error_history": [],
            "result": {
                "id": "res_001",
                "format": "txt",
                "processing_time_ms": 1250
            },
            "worker_id": "worker-ocr-text-tier0",
            "created_at": "2024-01-15T10:30:00Z",
            "started_at": "2024-01-15T10:30:02Z",
            "completed_at": "2024-01-15T10:30:05Z"
        }
    }
}
```

---

### 6.2 Get Job Result (OCR Text)

```
GET /api/v1/jobs/{job_id}/result
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "job_id": "job_001",
        "format": "txt",
        "content": "This is the extracted text from the image...\nLine 2 of the text...",
        "metadata": {
            "word_count": 150,
            "confidence": 0.95
        }
    }
}
```

**Errors:**
| Code | Condition |
|------|-----------|
| `NOT_FOUND` | Job not found or no result yet |

---

### 6.3 Download Job Result (File)

```
GET /api/v1/jobs/{job_id}/download
Authorization: Bearer {token}
```

**Response (200 OK):**
```
Content-Type: text/plain
Content-Disposition: attachment; filename="image1_result.txt"

[file content]
```

---

## 7. File Recovery Endpoints

### 7.1 List Deleted Files

```
GET /api/v1/files/deleted
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "files": [
            {
                "id": "file_001",
                "name": "old_image.png",
                "size_bytes": 102400,
                "deleted_at": "2024-01-14T10:30:00Z",
                "expires_at": "2024-01-21T10:30:00Z",
                "recoverable": true
            }
        ]
    }
}
```

---

### 7.2 Recover Deleted File

```
POST /api/v1/files/{file_id}/recover
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "file": {
            "id": "file_001",
            "name": "old_image.png",
            "status": "recovered"
        }
    }
}
```

---

## 8. Internal Endpoints (Worker Use Only)

> These endpoints are for Worker ↔ Orchestrator communication.
> Authenticated via `X-Access-Key` header.

### 8.1 File Proxy - Download File

```
POST /internal/file-proxy/download
X-Access-Key: {worker_access_key}
```

**Request:**
```json
{
    "job_id": "job_abc123"
}
```

**Response (200 OK):**
```
Content-Type: image/png (or appropriate type)
Content-Disposition: inline

[binary file content - streamed]
```

**Errors:**
| Code | Condition |
|------|-----------|
| `INVALID_ACCESS_KEY` | Missing or invalid access_key |
| `FORBIDDEN` | Service not authorized for this job |
| `NOT_FOUND` | Job or file not found |

---

### 8.2 File Proxy - Upload Result

```
POST /internal/file-proxy/upload
X-Access-Key: {worker_access_key}
Content-Type: multipart/form-data
```

**Request (Form Data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | string | Yes | Job ID |
| `file` | File | Yes | Result file |
| `processing_time_ms` | int | No | Processing duration |

**Response (201 Created):**
```json
{
    "success": true,
    "data": {
        "result_path": "results/req_abc123/job_001.txt"
    }
}
```

---

### 8.3 Update Job Status

```
POST /internal/jobs/{job_id}/status
X-Access-Key: {worker_access_key}
```

**Request - Starting processing:**
```json
{
    "status": "PROCESSING",
    "started_at": "2024-01-15T10:30:02Z",
    "worker_id": "worker-ocr-text-tier0"
}
```

**Request - Completed:**
```json
{
    "status": "COMPLETED",
    "result_path": "results/req_abc123/job_001.txt",
    "processing_time_ms": 1250,
    "completed_at": "2024-01-15T10:30:05Z"
}
```

**Request - Error (Worker reports, Orchestrator decides):**
```json
{
    "status": "ERROR",
    "error": "OCR timeout after 300 seconds",
    "retriable": true
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "job_id": "job_001",
        "new_status": "COMPLETED"
    }
}
```

**Note:** When Worker reports `status: "ERROR"`, the Orchestrator will:
1. If `retriable=false` → Set job status to `FAILED`
2. If `retriable=true` and `retry_count < max_retries` → Set to `RETRYING`, schedule re-queue
3. If `retriable=true` and `retry_count >= max_retries` → Set to `DEAD_LETTER`

---

### 8.4 Heartbeat

```
POST /internal/heartbeat
X-Access-Key: {worker_access_key}
```

**Request:**
```json
{
    "service_id": "worker-ocr-text-tier0",
    "status": "processing",
    "current_job_id": "job_abc123",
    "progress": {
        "files_completed": 2,
        "files_total": 5
    },
    "error_count": 0
}
```

**Status values:**
- `idle` - Worker waiting for jobs
- `processing` - Worker processing a job
- `uploading` - Worker uploading result
- `error` - Worker in error state

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "acknowledged": true
    }
}
```

---

## 9. Health & Status Endpoints

### 9.1 Health Check

```
GET /api/v1/health
```

**Response (200 OK):**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 9.2 System Status (Debug)

```
GET /api/v1/status
Authorization: Bearer {admin_token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "database": {
            "status": "connected",
            "type": "sqlite"
        },
        "queue": {
            "status": "connected",
            "pending_jobs": 15,
            "dlq_jobs": 2
        },
        "storage": {
            "status": "connected",
            "buckets": ["uploads", "results", "deleted"]
        },
        "workers": {
            "registered": 1,
            "healthy": 1,
            "dead": 0,
            "last_heartbeats": [
                {
                    "service_id": "worker-ocr-text-tier0",
                    "status": "idle",
                    "last_seen": "2024-01-15T10:29:30Z"
                }
            ]
        }
    }
}
```

---

## 10. Job Status Enum

```python
class JobStatus(str, Enum):
    # Initial states
    SUBMITTED = "SUBMITTED"       # Job just created
    VALIDATING = "VALIDATING"     # File being validated

    # Active states
    QUEUED = "QUEUED"             # In queue, waiting for worker
    PROCESSING = "PROCESSING"     # Worker processing
    RETRYING = "RETRYING"         # Waiting for retry (after retriable error)

    # Terminal states - Success
    COMPLETED = "COMPLETED"       # Successfully done

    # Terminal states - Failure
    FAILED = "FAILED"             # Failed (non-retriable error)
    REJECTED = "REJECTED"         # File validation failed
    CANCELLED = "CANCELLED"       # User cancelled (only from QUEUED)
    DEAD_LETTER = "DEAD_LETTER"   # Exceeded max retries

class RequestStatus(str, Enum):
    PROCESSING = "PROCESSING"           # Any job still active
    COMPLETED = "COMPLETED"             # All jobs completed successfully
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS" # Mix of success and failure
    FAILED = "FAILED"                   # All jobs failed
    CANCELLED = "CANCELLED"             # All jobs cancelled
```

---

## 11. API Schemas (Pydantic)

### 11.1 Upload Schemas

```python
class UploadRequest(BaseModel):
    method: str = "text_raw"
    tier: int = 0
    output_format: Literal["txt", "json"] = "txt"
    retention_hours: Literal[1, 6, 24, 168] = 24  # 1h, 6h, 24h, 7d

class UploadResponse(BaseModel):
    request: RequestSummary
    summary: UploadSummary
    jobs: List[JobSummary]
```

### 11.2 Request Schemas

```python
class RequestResponse(BaseModel):
    id: str
    method: str
    tier: int
    output_format: str
    retention_hours: int
    status: RequestStatus
    total_files: int
    completed_files: int
    failed_files: int
    created_at: datetime
    completed_at: Optional[datetime]
```

### 11.3 Job Schemas

```python
class JobResponse(BaseModel):
    id: str
    request_id: str
    file: FileInfo
    status: JobStatus
    method: str
    tier: int
    output_format: str
    retry_count: int
    max_retries: int
    error_history: List[ErrorEntry]
    result: Optional[ResultInfo]
    worker_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### 11.4 Internal Schemas

```python
class FileProxyDownloadRequest(BaseModel):
    job_id: str

class JobStatusUpdate(BaseModel):
    status: Literal["PROCESSING", "COMPLETED", "ERROR"]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_path: Optional[str]
    processing_time_ms: Optional[int]
    worker_id: Optional[str]
    error: Optional[str]
    retriable: Optional[bool]

class HeartbeatPayload(BaseModel):
    service_id: str
    status: Literal["idle", "processing", "uploading", "error"]
    current_job_id: Optional[str]
    progress: Optional[ProgressInfo]
    error_count: int = 0

class ProgressInfo(BaseModel):
    files_completed: int
    files_total: int
```

---

## 12. Rate Limits (Phase 2)

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 10 | per minute |
| `/auth/register` | 5 | per minute |
| `/upload` | 20 | per minute |
| `/requests` | 100 | per minute |
| `/jobs/*/download` | 50 | per minute |
| `/internal/*` | 1000 | per minute |

---

## 13. Endpoint Summary by Layer

### Edge Layer (User-facing)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | - | Register user |
| POST | `/api/v1/auth/login` | - | Login |
| POST | `/api/v1/auth/logout` | Session | Logout |
| GET | `/api/v1/auth/me` | Session | Get current user |
| POST | `/api/v1/upload` | Session | Upload files |
| GET | `/api/v1/requests` | Session | List requests |
| GET | `/api/v1/requests/{id}` | Session | Get request detail |
| POST | `/api/v1/requests/{id}/cancel` | Session | Cancel request |
| GET | `/api/v1/requests/{id}/download` | Session | Download results ZIP |
| GET | `/api/v1/jobs/{id}` | Session | Get job detail |
| GET | `/api/v1/jobs/{id}/result` | Session | Get OCR result |
| GET | `/api/v1/jobs/{id}/download` | Session | Download result file |
| GET | `/api/v1/files/deleted` | Session | List deleted files |
| POST | `/api/v1/files/{id}/recover` | Session | Recover file |
| GET | `/api/v1/health` | - | Health check |

### Orchestration Layer (Internal - Worker use)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/internal/file-proxy/download` | access_key | Download source file |
| POST | `/internal/file-proxy/upload` | access_key | Upload result file |
| POST | `/internal/jobs/{id}/status` | access_key | Update job status |
| POST | `/internal/heartbeat` | access_key | Worker heartbeat |
