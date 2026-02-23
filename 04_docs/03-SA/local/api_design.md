# OCR Platform Local MVP1 - API Design

> Version: 3.1 | Phase: Local MVP 1
> Aligned with: SA v3.1 + Actual Code (synced 2025-02)

---

## 1. API Overview

| Aspect | Specification |
|--------|---------------|
| **Base URL** | `http://localhost:8000/api/v1` |
| **Internal URL** | `http://localhost:8000/api/v1/internal` |
| **Admin URL** | `http://localhost:8000/api/v1/admin` |
| **Protocol** | HTTP/1.1 (HTTPS in Phase 2) |
| **Format** | JSON |
| **User Auth** | Session token (Authorization: Bearer {token}) |
| **Admin Auth** | Session token + user.is_admin = true |
| **Worker Auth** | access_key (X-Access-Key header) |
| **Docs** | Swagger UI: `/docs`, ReDoc: `/redoc` |

> **NOTE:** All routes (public, admin, internal) share the `/api/v1` prefix.
> Internal endpoints are at `/api/v1/internal/*`, NOT `/internal/*`.

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
| `INVALID_ACCESS_KEY` | 401 | Worker access_key invalid or type not APPROVED |
| `FORBIDDEN` | 403 | Access denied to resource |
| `ADMIN_REQUIRED` | 403 | Admin privileges required |
| `SERVICE_REJECTED` | 403 | Service type permanently rejected |
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
            "is_admin": false,
            "created_at": "2024-01-15T10:30:00Z"
        },
        "token": "ses_xyz789...",
        "expires_at": "2024-01-16T10:30:00Z"
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
            "is_admin": false,
            "created_at": "2024-01-15T10:30:00Z"
        },
        "token": "ses_xyz789...",
        "expires_at": "2024-01-16T10:30:00Z"
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
            "is_admin": false,
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
| `output_format` | string | No | Output format: `txt`, `json`, `md` (default: `txt`). Available formats depend on selected service's `supported_output_formats`. |
| `retention_hours` | int | No | File retention (default: 168 = 7 days) |

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
            "retention_hours": 168,
            "status": "PROCESSING",
            "total_files": 5,
            "completed_files": 0,
            "failed_files": 0,
            "expires_at": "2024-01-22T10:30:00Z",
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

**Response (200 OK):** Same as v2.0 (includes jobs array with full detail).

---

### 5.3 Cancel Request

```
POST /api/v1/requests/{request_id}/cancel
Authorization: Bearer {token}
```

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
            "file_id": "file_001",
            "status": "COMPLETED",
            "method": "text_raw",
            "tier": 0,
            "retry_count": 0,
            "max_retries": 3,
            "error_history": [],
            "started_at": "2024-01-15T10:30:02Z",
            "completed_at": "2024-01-15T10:30:05Z",
            "processing_time_ms": 1250,
            "result_path": "results/req_abc123/job_001.txt",
            "worker_id": "ocr-paddle-abc123",
            "created_at": "2024-01-15T10:30:00Z"
        }
    }
}
```

> **NOTE:** Job does NOT have `output_format` field. Output format is on the Request level.

---

### 6.2 Get Job Result (OCR Text)

```
GET /api/v1/jobs/{job_id}/result
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "text": "This is the extracted text...",
    "lines": 15,
    "metadata": {
        "method": "text_raw",
        "tier": "0",
        "processing_time_ms": 1250,
        "version": "1.0.0"
    }
}
```

### 6.3 Download Job Result

```
GET /api/v1/jobs/{job_id}/download
Authorization: Bearer {token}
```

**Response:** File content (streaming) with appropriate Content-Type header.

---

## 7. File Endpoints

### 7.1 Get File Metadata

```
GET /api/v1/files/{file_id}
Authorization: Bearer {token}
```

### 7.2 Get Original File URL

```
GET /api/v1/files/{file_id}/original-url
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "url": "https://...",
        "expires_at": "2024-01-15T11:30:00Z"
    }
}
```

### 7.3 Get Result File URL

```
GET /api/v1/files/{file_id}/result-url
Authorization: Bearer {token}
```

### 7.4 Download Original File

```
GET /api/v1/files/{file_id}/download
Authorization: Bearer {token}
```

**Response:** File content (streaming) with appropriate Content-Type header.

---

## 8. Admin Endpoints (NEW)

> Requires `Authorization: Bearer {token}` with `user.is_admin = true`.

### 8.1 List Service Types

```
GET /api/v1/admin/service-types
Authorization: Bearer {admin_token}
```

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | - | Filter: PENDING, APPROVED, DISABLED, REJECTED |

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "service_types": [
            {
                "id": "ocr-paddle",
                "display_name": "PaddleOCR Text Raw",
                "description": "GPU-accelerated OCR",
                "status": "PENDING",
                "access_key": null,
                "allowed_methods": ["text_raw"],
                "allowed_tiers": [0],
                "supported_output_formats": ["txt", "json"],
                "dev_contact": "dev@example.com",
                "max_instances": 0,
                "instance_count": 1,
                "registered_at": "2024-01-15T10:30:00Z"
            }
        ]
    }
}
```

### 8.2 Approve Service Type

```
POST /api/v1/admin/service-types/{type_id}/approve
Authorization: Bearer {admin_token}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "id": "ocr-paddle",
        "status": "APPROVED",
        "access_key": "sk_generated_xxx",
        "approved_at": "2024-01-15T10:35:00Z"
    }
}
```

### 8.3 Reject Service Type

```
POST /api/v1/admin/service-types/{type_id}/reject
Authorization: Bearer {admin_token}
```

**Request:**
```json
{
    "reason": "Unverified OCR engine"
}
```

### 8.4 Disable/Enable Service Type

```
POST /api/v1/admin/service-types/{type_id}/disable
POST /api/v1/admin/service-types/{type_id}/enable
Authorization: Bearer {admin_token}
```

### 8.5 Delete Service Type

```
DELETE /api/v1/admin/service-types/{type_id}
Authorization: Bearer {admin_token}
```

### 8.6 List Service Instances

```
GET /api/v1/admin/service-instances
Authorization: Bearer {admin_token}
```

### 8.7 Admin Dashboard

```
GET /api/v1/admin/dashboard/stats
GET /api/v1/admin/dashboard/recent-requests?page=1&page_size=20
GET /api/v1/admin/dashboard/users?page=1&page_size=50
GET /api/v1/admin/dashboard/job-volume?hours=24
GET /api/v1/admin/dashboard/service-instances?type_id=...&status=...
Authorization: Bearer {admin_token}
```

> Dashboard endpoints provide system KPI stats, recent requests from all users,
> user list with request counts, hourly job volume with latency, and service instance health.

---

## 9. Services Endpoint (Public)

```
GET /api/v1/services
Authorization: Bearer {token}
```

Returns list of available (APPROVED) service types that have at least one active worker instance.

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": "ocr-paddle",
                "display_name": "PaddleOCR Text Raw",
                "description": "GPU-accelerated OCR",
                "allowed_methods": ["text_raw"],
                "allowed_tiers": [0],
                "supported_output_formats": ["txt", "json"],
                "active_instances": 1
            },
            {
                "id": "ocr-paddle-vl",
                "display_name": "PaddleOCR-VL Structured Extract",
                "description": "GPU-accelerated structured data extraction (tables, layouts)",
                "allowed_methods": ["structured_extract"],
                "allowed_tiers": [0],
                "supported_output_formats": ["json", "md"],
                "active_instances": 1
            }
        ],
        "total": 2
    }
}
```

> **NOTE:** `supported_output_formats` is declared by workers during registration and stored on ServiceType.
> Frontend uses this field to dynamically filter available output formats based on selected method.

---

## 10. Internal Endpoints (Worker Use Only)

> These endpoints are for Worker <-> Orchestrator communication.
> Base URL: `http://ocr-backend:8000/api/v1/internal`
> Authenticated via `X-Access-Key` header (validated against ServiceType, status=APPROVED).

### 10.1 Worker Registration

```
POST /api/v1/internal/register
```

**Request:**
```json
{
    "service_type": "ocr-paddle",
    "instance_id": "ocr-paddle-abc123def456",
    "display_name": "PaddleOCR Text Raw",
    "description": "GPU-accelerated Vietnamese OCR",
    "dev_contact": "dev@example.com",
    "allowed_methods": ["text_raw"],
    "allowed_tiers": [0],
    "supported_output_formats": ["txt", "json"],
    "access_key": "sk_local_paddle"
}
```

**Response (200 OK) - Type APPROVED:**
```json
{
    "success": true,
    "data": {
        "status": "active",
        "access_key": "sk_local_paddle",
        "message": "Instance registered and active"
    }
}
```

**Response (200 OK) - Type PENDING:**
```json
{
    "success": true,
    "data": {
        "status": "waiting",
        "message": "Service type pending admin approval"
    }
}
```

**Response (403) - Type REJECTED:**
```json
{
    "success": false,
    "error": {
        "code": "SERVICE_REJECTED",
        "message": "Service type has been rejected"
    }
}
```

### 10.2 Worker Deregistration

```
POST /api/v1/internal/deregister
```

**Request:**
```json
{
    "instance_id": "ocr-paddle-abc123def456"
}
```

---

### 10.3 File Proxy - Download File

```
POST /api/v1/internal/file-proxy/download
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

---

### 10.4 File Proxy - Upload Result

```
POST /api/v1/internal/file-proxy/upload
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

### 10.5 Update Job Status

```
PATCH /api/v1/internal/jobs/{job_id}/status
X-Access-Key: {worker_access_key}
```

> **NOTE:** This is PATCH (not POST as in v2.0).

**Request - Starting processing:**
```json
{
    "status": "PROCESSING",
    "worker_id": "ocr-paddle-abc123"
}
```

**Request - Completed:**
```json
{
    "status": "COMPLETED",
    "result_path": "results/req_abc123/job_001.txt",
    "processing_time_ms": 1250
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

---

### 10.6 Heartbeat

```
POST /api/v1/internal/heartbeat
X-Access-Key: {worker_access_key}
```

**Request:**
```json
{
    "instance_id": "ocr-paddle-abc123",
    "status": "processing",
    "current_job_id": "job_abc123",
    "files_completed": 2,
    "files_total": 5,
    "error_count": 0
}
```

> **NOTE:** Fields are flat (no nested `progress` object).

**Status values:**
- `idle` - Worker waiting for jobs
- `processing` - Worker processing a job
- `error` - Worker in error state

**Response (200 OK):**
```json
{
    "success": true,
    "received_at": "2024-01-15T10:30:30Z",
    "action": "continue",
    "access_key": null,
    "rejection_reason": null
}
```

**Response `action` values:**
- `continue` - Keep current state (waiting or processing)
- `approved` - Type was just approved, `access_key` included in response
- `drain` - Type was disabled, finish current job then stop
- `shutdown` - Type was rejected, `rejection_reason` included

---

## 11. Health & Status Endpoints

### 11.1 Health Check

```
GET /api/v1/health
```

> No authentication required. Used by Docker healthcheck.

**Response (200 OK):**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 12. Job Status Enum

```python
class JobStatus(str, Enum):
    # Initial states
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"

    # Active states
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    # NOTE: No RETRYING state. Retry transitions go FAILED → QUEUED directly.

    # Terminal states - Success
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"  # Also used at Job level in code

    # Terminal states - Failure
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"

class RequestStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # NOTE: Request status aggregation (get_request_status) is defined
    # in state_machine.py but NOT YET IMPLEMENTED (stub).

class ServiceTypeStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISABLED = "DISABLED"
    REJECTED = "REJECTED"

class ServiceInstanceStatus(str, Enum):
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    PROCESSING = "PROCESSING"
    DRAINING = "DRAINING"
    DEAD = "DEAD"
```

---

## 13. API Schemas (Pydantic)

### 13.1 Upload Schemas

```python
class UploadRequest(BaseModel):
    method: str = "text_raw"
    tier: int = 0
    output_format: str = "txt"  # Dynamic: validated against service's supported_output_formats
    retention_hours: int = 168  # 7 days default
```

### 13.2 Request Schemas

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
    expires_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]
```

### 13.3 Job Schemas

```python
class JobResponse(BaseModel):
    id: str
    request_id: str
    file: FileInfo
    status: JobStatus
    method: str
    tier: int
    # NOTE: No output_format (lives on Request)
    retry_count: int
    max_retries: int
    error_history: List[ErrorEntry]
    result: Optional[ResultInfo]
    worker_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### 13.4 Internal Schemas

```python
class RegisterRequest(BaseModel):
    service_type: str
    instance_id: str
    display_name: str = ""
    description: str = ""
    dev_contact: Optional[str] = None
    allowed_methods: List[str] = ["text_raw"]
    allowed_tiers: List[int] = [0]
    supported_output_formats: List[str] = ["txt", "json"]  # Formats this worker can produce
    access_key: Optional[str] = None  # For seeded services

class JobStatusUpdate(BaseModel):
    status: Literal["PROCESSING", "COMPLETED", "ERROR"]
    worker_id: Optional[str]
    result_path: Optional[str]
    processing_time_ms: Optional[int]
    error: Optional[str]
    retriable: Optional[bool]

class HeartbeatPayload(BaseModel):
    instance_id: str
    status: Literal["idle", "processing", "error"]
    current_job_id: Optional[str]
    files_completed: int = 0   # Flat fields, no nested progress object
    files_total: int = 0
    error_count: int = 0

class HeartbeatResponse(BaseModel):
    success: bool
    received_at: str                    # ISO 8601 UTC
    action: str                         # "continue", "approved", "drain", "shutdown"
    access_key: Optional[str] = None    # Set when action="approved"
    rejection_reason: Optional[str] = None  # Set when action="shutdown"
```

---

## 14. Endpoint Summary by Layer

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
| GET | `/api/v1/jobs/{id}` | Session | Get job detail |
| GET | `/api/v1/jobs/{id}/result` | Session | Get OCR result |
| GET | `/api/v1/jobs/{id}/download` | Session | Download result file |
| GET | `/api/v1/files/{id}` | Session | Get file metadata |
| GET | `/api/v1/files/{id}/original-url` | Session | Get original presigned URL |
| GET | `/api/v1/files/{id}/result-url` | Session | Get result presigned URL |
| GET | `/api/v1/files/{id}/download` | Session | Download original file |
| GET | `/api/v1/services` | Session | List available services |
| GET | `/api/v1/health` | - | Health check |

### Admin Layer (Admin-only)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/admin/service-types` | Admin | List service types |
| POST | `/api/v1/admin/service-types/{id}/approve` | Admin | Approve type |
| POST | `/api/v1/admin/service-types/{id}/reject` | Admin | Reject type |
| POST | `/api/v1/admin/service-types/{id}/disable` | Admin | Disable type |
| POST | `/api/v1/admin/service-types/{id}/enable` | Admin | Enable type |
| DELETE | `/api/v1/admin/service-types/{id}` | Admin | Delete type |
| GET | `/api/v1/admin/service-instances` | Admin | List instances |
| GET | `/api/v1/admin/dashboard/stats` | Admin | System KPI stats |
| GET | `/api/v1/admin/dashboard/recent-requests` | Admin | All users' requests |
| GET | `/api/v1/admin/dashboard/users` | Admin | User list + counts |
| GET | `/api/v1/admin/dashboard/job-volume` | Admin | Hourly job volume |
| GET | `/api/v1/admin/dashboard/service-instances` | Admin | Instance health |

### Orchestration Layer (Internal - Worker use)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/internal/register` | none/access_key | Register worker |
| POST | `/api/v1/internal/deregister` | access_key | Deregister worker |
| POST | `/api/v1/internal/file-proxy/download` | access_key | Download source file |
| POST | `/api/v1/internal/file-proxy/upload` | access_key | Upload result file |
| **PATCH** | `/api/v1/internal/jobs/{id}/status` | access_key | Update job status |
| POST | `/api/v1/internal/heartbeat` | access_key | Worker heartbeat |

---

*Changelog v2.0 -> v3.0:*
- *Base URL port: 8080 -> 8000*
- *Internal URL: `/internal/*` -> `/api/v1/internal/*`*
- *Job status update: POST -> **PATCH***
- *Added `User.is_admin` to auth responses*
- *Added `Request.expires_at` to request responses*
- *Added `Session.token` / `expires_at` to auth responses*
- *Removed `Job.output_format` from job responses (lives on Request)*
- *Heartbeat uses `instance_id` instead of `service_id`*
- *Heartbeat status: removed "uploading" (only idle, processing, error)*
- *Default retention_hours: 24 -> 168 (7 days)*
- *Added Section 8: Admin Endpoints (service type CRUD)*
- *Added Section 9: Services Endpoint (public)*
- *Added Section 10.1-10.2: Worker Register/Deregister*
- *Added ServiceTypeStatus + ServiceInstanceStatus enums*
- *File Proxy ACL validates against ServiceType (not legacy Service)*
- *Removed Section 7 (File Recovery) and 5.4 (Download ZIP) -- not implemented*
- *Removed Section 9.2 (System Status Debug) -- not implemented*
