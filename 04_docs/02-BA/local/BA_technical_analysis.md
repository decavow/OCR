# OCR Platform Phase 1 — Technical Business Analysis (Local MVP)

> Tài liệu phân tích kỹ thuật nghiệp vụ cho OCR Platform Phase 1 - Local MVP
> Version: 1.0 | Status: Draft
> References: `01-PO/local/PO_phase1_local.md`, `02-BA/local/BA_business_analysis.md`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Functional Requirements Specification](#2-functional-requirements-specification)
3. [System Architecture & Design](#3-system-architecture--design)
4. [API Specification](#4-api-specification)
5. [Data Dictionary & Schema Design](#5-data-dictionary--schema-design)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Test Strategy](#7-test-strategy)
8. [UI-Logic Specification](#8-ui-logic-specification)

---

## 1. System Overview

### 1.1. System Purpose & Scope

OCR Platform Phase 1 Local MVP là một prototype web app chạy hoàn toàn trên local environment. Mục đích là validate kiến trúc 3 lớp (Edge → Orchestration → Processing) trước khi deploy lên cloud.

**System Boundaries:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYSTEM CONTEXT (LOCAL MVP)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   [External Actors]                        [Local MVP System]                │
│                                                                               │
│   ┌──────────────┐                    ┌──────────────────────────────┐       │
│   │   Developer  │◄──────────────────▶│                              │       │
│   │   (Browser)  │   HTTP (localhost) │                              │       │
│   └──────────────┘                    │                              │       │
│                                       │      OCR Platform            │       │
│   ┌──────────────┐                    │      Local MVP               │       │
│   │   Tester     │◄──────────────────▶│                              │       │
│   │   (Browser)  │   HTTP (localhost) │   - Web Frontend             │       │
│   └──────────────┘                    │   - API Backend              │       │
│                                       │   - Worker Process           │       │
│                                       │   - Local Storage            │       │
│                                       │   - SQLite Database          │       │
│                                       │                              │       │
│                                       └──────────────────────────────┘       │
│                                                                               │
│   [NO External Services in Phase 1]                                          │
│   - No OAuth providers                                                        │
│   - No Cloud storage                                                          │
│   - No Payment gateway                                                        │
│   - No GPU cloud                                                              │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2. Modules / Services Chính

| Module | Trách nhiệm | Layer | Technology |
|---|---|---|---|
| **Web Frontend** | Giao diện người dùng, SPA | Edge | React/Vue/Next.js |
| **API Server** | REST API endpoints | Edge | Node.js/Python (FastAPI) |
| **Auth Module** | Authentication, session | Orchestration | bcrypt, JWT/session |
| **Upload Module** | File upload, validation | Edge | multer/FastAPI |
| **Job Module** | Job lifecycle, queue | Orchestration | Custom |
| **Worker Process** | OCR processing | Processing | Tesseract |
| **Queue** | Job queue management | Orchestration | In-memory / BullMQ |
| **Storage** | File storage | Edge | Local filesystem |
| **Database** | Metadata, state | Orchestration | SQLite |

### 1.3. Architecture Validation Goals

Phase 1 cần validate và lock các interface sau để đảm bảo smooth transition sang Phase 2:

| Interface | Phase 1 (Local) | Phase 2+ (Cloud) | Validation |
|---|---|---|---|
| File Storage | Local filesystem | Cloudflare R2 / S3 | Same API contract |
| Queue | In-memory / SQLite | Redis / Pub-Sub | Same job format |
| Database | SQLite | Firestore / PostgreSQL | Same schema structure |
| Worker | Single process | Containers on GPU | Same interface |
| Auth | Local session | OAuth + JWT | Extensible auth module |

---

## 2. Functional Requirements Specification

### 2.1. FR-L001: User Authentication

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L001 |
| **Module** | Auth Module |
| **Requirement** | Hệ thống cho phép người dùng đăng ký và đăng nhập bằng email/password |
| **Input** | Email (string), Password (string, min 6 chars) |
| **Processing Logic** | **Registration:**<br>1. Validate email format (RFC 5322)<br>2. Validate password length >= 6<br>3. Check email uniqueness in database<br>4. Hash password (bcrypt, cost 10)<br>5. Create user record in SQLite<br>6. Create session, return session token<br><br>**Login:**<br>1. Find user by email<br>2. Compare password with hash (bcrypt.compare)<br>3. If match, create session<br>4. Return session token |
| **Output** | Session token (cookie or localStorage), User profile |
| **Business Rules** | RULE-L001, RULE-L002, RULE-L003 |
| **Acceptance Criteria** | AC1: Register with valid email + password (6+ chars) → success<br>AC2: Register with existing email → error "Email already exists"<br>AC3: Register with password < 6 chars → error "Password too short"<br>AC4: Login with valid credentials → success, session created<br>AC5: Login with invalid credentials → error "Invalid credentials"<br>AC6: Logout → session cleared |
| **Priority** | Must |
| **Trace to BR** | PR-L001, PR-L002 |

### 2.2. FR-L002: Batch File Upload

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L002 |
| **Module** | Upload Module |
| **Requirement** | Hệ thống cho phép upload nhiều files cùng lúc với validation |
| **Input** | Multiple files (multipart form data) |
| **Processing Logic** | 1. Receive files from multipart request<br>2. For each file:<br>&nbsp;&nbsp;a. Validate MIME type (image/png, image/jpeg, application/pdf)<br>&nbsp;&nbsp;b. Validate magic bytes (first few bytes of file)<br>&nbsp;&nbsp;c. Validate size <= 10MB<br>&nbsp;&nbsp;d. If PDF, count pages <= 100 per file<br>3. Check total batch size <= 50MB<br>4. Check total files <= 20<br>5. For valid files:<br>&nbsp;&nbsp;a. Generate file_id (UUID)<br>&nbsp;&nbsp;b. Save to `./storage/uploads/{user_id}/{request_id}/{file_id}`<br>&nbsp;&nbsp;c. Create file metadata record<br>6. Return list of uploaded files with validation status |
| **Output** | Array of { file_id, filename, size, status, error? } |
| **Business Rules** | RULE-L004, RULE-L004b, RULE-L004c, RULE-L005, RULE-L006, RULE-L007 |
| **Acceptance Criteria** | See STORY-L002 in PO spec |
| **Priority** | Must |
| **Trace to BR** | PR-L003, PR-L004 |

**Decision Table: File Validation**

| MIME Type | Extension | Magic Bytes | Size ≤ 10MB | PDF Pages ≤ 100 | → Result |
|---|---|---|---|---|---|
| image/png | .png | 89 50 4E 47 | Y | N/A | Accept |
| image/jpeg | .jpg/.jpeg | FF D8 FF | Y | N/A | Accept |
| application/pdf | .pdf | 25 50 44 46 | Y | Y | Accept |
| application/pdf | .pdf | 25 50 44 46 | Y | N | Skip: "Too many pages" |
| any | any | any | N | any | Skip: "File too large" |
| other | other | other | any | any | Skip: "Unsupported format" |
| any | any | Invalid | any | any | Skip: "File corrupted" |

### 2.3. FR-L003: Job Creation & Submission

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L003 |
| **Module** | Job Module |
| **Requirement** | Hệ thống tạo request và jobs cho batch files |
| **Input** | user_id, file_ids[] |
| **Processing Logic** | 1. Validate all file_ids belong to user<br>2. Create request record:<br>&nbsp;&nbsp;- request_id = generate UUID<br>&nbsp;&nbsp;- user_id = authenticated user<br>&nbsp;&nbsp;- method = "ocr_text_raw" (fixed)<br>&nbsp;&nbsp;- tier = 0 (fixed)<br>&nbsp;&nbsp;- status = "SUBMITTED"<br>3. For each file_id:<br>&nbsp;&nbsp;a. Create job record:<br>&nbsp;&nbsp;&nbsp;&nbsp;- job_id = generate UUID<br>&nbsp;&nbsp;&nbsp;&nbsp;- request_id = above<br>&nbsp;&nbsp;&nbsp;&nbsp;- file_id = file_id<br>&nbsp;&nbsp;&nbsp;&nbsp;- status = "SUBMITTED"<br>&nbsp;&nbsp;&nbsp;&nbsp;- retry_count = 0<br>&nbsp;&nbsp;b. Transition job to QUEUED<br>&nbsp;&nbsp;c. Push job to queue<br>4. Return request_id |
| **Output** | request_id, estimated_time |
| **Business Rules** | RULE-L008, RULE-L009, RULE-L010 |
| **Acceptance Criteria** | AC1: Submit valid files → request created, jobs queued<br>AC2: Submit empty files → error "No files to process" |
| **Priority** | Must |
| **Trace to BR** | PR-L005 |

### 2.4. FR-L004: OCR Processing (Worker)

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L004 |
| **Module** | Worker Process |
| **Requirement** | Worker xử lý OCR job và lưu kết quả |
| **Input** | Job payload from queue (job_id, file_path, method) |
| **Processing Logic** | **Main Loop:**<br>1. Poll queue for next QUEUED job<br>2. If no job, wait WORKER_POLL_INTERVAL_MS, goto 1<br><br>**Process Job:**<br>1. Update job status → PROCESSING<br>2. Read file from local storage<br>3. Run OCR based on method:<br>&nbsp;&nbsp;- ocr_text_raw: Tesseract → plain text<br>4. If success:<br>&nbsp;&nbsp;a. Save result to `./storage/results/{job_id}/output.txt`<br>&nbsp;&nbsp;b. Save metadata to `./storage/results/{job_id}/metadata.json`<br>&nbsp;&nbsp;c. Update job status → COMPLETED<br>5. If error:<br>&nbsp;&nbsp;a. Classify error (retriable vs non-retriable)<br>&nbsp;&nbsp;b. If retriable AND retry_count < MAX_RETRIES:<br>&nbsp;&nbsp;&nbsp;&nbsp;- Increment retry_count<br>&nbsp;&nbsp;&nbsp;&nbsp;- Add error to error_history<br>&nbsp;&nbsp;&nbsp;&nbsp;- Update status → RETRYING<br>&nbsp;&nbsp;&nbsp;&nbsp;- Calculate delay (exponential backoff)<br>&nbsp;&nbsp;&nbsp;&nbsp;- Re-queue job after delay<br>&nbsp;&nbsp;c. Else:<br>&nbsp;&nbsp;&nbsp;&nbsp;- Update status → FAILED<br>&nbsp;&nbsp;&nbsp;&nbsp;- Store final error<br>6. Delete temp files<br>7. Goto Main Loop |
| **Output** | Result file in storage, job status update |
| **Business Rules** | RULE-L011 to RULE-L015e |
| **Acceptance Criteria** | AC1: Job processed successfully → status COMPLETED, result saved<br>AC2: Retriable error, retry < max → status RETRYING, re-queued<br>AC3: Retriable error, retry >= max → status FAILED<br>AC4: Non-retriable error → status FAILED immediately |
| **Priority** | Must |
| **Trace to BR** | PR-L006, PR-L007 |

**Pseudocode: Retry Logic**

```
function processJob(job):
    try:
        result = runOCR(job.file_path, job.method)
        saveResult(job.id, result)
        updateStatus(job.id, COMPLETED)
    catch error:
        if isRetriable(error) AND job.retry_count < MAX_RETRIES:
            job.retry_count += 1
            job.error_history.push({
                timestamp: now(),
                error: error.message,
                attempt: job.retry_count
            })
            updateStatus(job.id, RETRYING)
            delay = RETRY_BASE_DELAY * (2 ^ (job.retry_count - 1))
            scheduleRequeue(job.id, delay)
        else:
            updateStatus(job.id, FAILED, error.message)

function isRetriable(error):
    retriableErrors = [TIMEOUT, OCR_ENGINE_ERROR, TEMP_FAILURE]
    nonRetriableErrors = [INVALID_FILE, FILE_NOT_FOUND, CORRUPTED]
    return error.type in retriableErrors
```

### 2.5. FR-L005: Job Status Query

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L005 |
| **Module** | Job Module |
| **Requirement** | Hệ thống cung cấp API để query job/request status |
| **Input** | request_id hoặc job_id |
| **Processing Logic** | **Get Request Status:**<br>1. Verify request belongs to user<br>2. Get request record<br>3. Get all jobs for request<br>4. Calculate aggregated status:<br>&nbsp;&nbsp;- total, completed, failed, processing, retrying, queued<br>5. Return request with job list<br><br>**Get Job Status:**<br>1. Verify job belongs to user<br>2. Get job record with full details<br>3. If COMPLETED, include result_path<br>4. If FAILED, include error details<br>5. If RETRYING, include retry info |
| **Output** | Request/Job status object with all details |
| **Business Rules** | RULE-L016, RULE-L017 |
| **Acceptance Criteria** | AC1: Get request status → returns aggregated status<br>AC2: Get job status → returns current status with details<br>AC3: Access other user's job → error 403 |
| **Priority** | Must |
| **Trace to BR** | PR-L008, PR-L009 |

### 2.6. FR-L006: Result Retrieval

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L006 |
| **Module** | Job Module |
| **Requirement** | Hệ thống cho phép xem và download kết quả OCR |
| **Input** | job_id, format (txt/json) |
| **Processing Logic** | **View Result:**<br>1. Verify job belongs to user<br>2. Verify job status = COMPLETED<br>3. Read result from storage<br>4. Return result content<br><br>**Download Result:**<br>1. Verify job and status<br>2. Read result based on format:<br>&nbsp;&nbsp;- txt: plain text file<br>&nbsp;&nbsp;- json: { text, metadata }<br>3. Set appropriate headers<br>4. Stream file to client<br><br>**Download All (ZIP):**<br>1. Get all completed jobs for request<br>2. Create ZIP with all results<br>3. Stream ZIP to client |
| **Output** | Result content or file download |
| **Business Rules** | RULE-L018, RULE-L019 |
| **Acceptance Criteria** | AC1: View completed job result → returns text<br>AC2: Download TXT → downloads plain text file<br>AC3: Download JSON → downloads JSON with metadata<br>AC4: Download all → downloads ZIP with all results<br>AC5: Result expired → error "Result no longer available" |
| **Priority** | Must |
| **Trace to BR** | PR-L010, PR-L011 |

### 2.7. FR-L007: File Cleanup

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-L007 |
| **Module** | Background Job |
| **Requirement** | Hệ thống tự động xóa files hết hạn retention |
| **Input** | None (scheduled job) |
| **Processing Logic** | 1. Run every hour (cron/scheduled)<br>2. Query files where:<br>&nbsp;&nbsp;- created_at + retention < now()<br>3. For each expired file:<br>&nbsp;&nbsp;a. Delete file from storage<br>&nbsp;&nbsp;b. Update file record (deleted_at = now())<br>&nbsp;&nbsp;c. Log deletion<br>4. Query results where:<br>&nbsp;&nbsp;- created_at + retention < now()<br>5. For each expired result:<br>&nbsp;&nbsp;a. Delete result files from storage<br>&nbsp;&nbsp;b. Update job record (result_deleted = true)<br>&nbsp;&nbsp;c. Log deletion |
| **Output** | Cleanup log with deleted files count |
| **Business Rules** | RULE-L020, RULE-L021, RULE-L022 |
| **Acceptance Criteria** | AC1: Files older than retention → deleted<br>AC2: Results older than retention → deleted<br>AC3: Job metadata preserved after file deletion<br>AC4: Cleanup logs created |
| **Priority** | Should |
| **Trace to BR** | PR-L012 |

---

## 3. System Architecture & Design

### 3.1. Architecture Overview

**Architecture Style:** Modular Monolith with separate Worker Process

**Rationale cho Phase 1:**
- Simple deployment (npm start / docker-compose up)
- Easy debugging trên local
- Tất cả code trong 1 repo, dễ refactor
- Worker tách riêng để simulate distributed processing

**Key Architectural Decisions:**

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Deployment | Docker Compose | Manual processes | Consistent environment |
| API Framework | FastAPI / Express | Hono, Nest | Simple, well-documented |
| Database | SQLite | JSON files, PostgreSQL | Zero setup, SQL compatible |
| Queue | In-memory + SQLite | Redis, RabbitMQ | No external dependency |
| Storage | Local filesystem | MinIO | Simplest for local dev |
| OCR Engine | Tesseract | EasyOCR, PaddleOCR | Mature, well-tested |

### 3.2. Component Breakdown

| Service | Responsibility | Key Functions | Dependencies | Data Owned | Communication |
|---|---|---|---|---|---|
| **API Server** | HTTP endpoints | REST API, static files | SQLite, Storage | - | Sync (HTTP) |
| **Auth Module** | User identity | Login, register, session | SQLite | Users | Sync |
| **Upload Module** | File handling | Validate, save files | Storage, SQLite | Files | Sync |
| **Job Module** | Job orchestration | Create, query, update | SQLite, Queue | Requests, Jobs | Sync + Queue |
| **Worker** | OCR processing | Pull jobs, process, save | Queue, Storage, SQLite, Tesseract | - | Async (Queue) |
| **Cleanup Job** | Maintenance | Delete expired files | Storage, SQLite | - | Scheduled |

### 3.3. Data Flow - Job Processing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    JOB PROCESSING DATA FLOW (LOCAL MVP)                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  1. UPLOAD                                                                    │
│  ┌────────┐   multipart    ┌────────────┐   save    ┌────────────┐          │
│  │ Client │ ──────────────▶│ API Server │ ────────▶ │ Local      │          │
│  └────────┘   POST /upload └────────────┘           │ Filesystem │          │
│                                  │                  └────────────┘          │
│                                  │ insert                                    │
│                                  ▼                                           │
│                            ┌──────────┐                                      │
│                            │  SQLite  │ (files table)                        │
│                            └──────────┘                                      │
│                                                                               │
│  2. SUBMIT                                                                    │
│  ┌────────┐   POST /process ┌────────────┐                                   │
│  │ Client │ ───────────────▶│ API Server │                                   │
│  └────────┘                 └─────┬──────┘                                   │
│                                   │                                          │
│                    ┌──────────────┼──────────────┐                           │
│                    │ create       │ create       │ push                      │
│                    ▼              ▼              ▼                           │
│              ┌──────────┐   ┌──────────┐   ┌──────────┐                     │
│              │ requests │   │   jobs   │   │  Queue   │                     │
│              │  table   │   │  table   │   │(in-memory)│                    │
│              └──────────┘   └──────────┘   └──────────┘                     │
│                                                                               │
│  3. PROCESS                                                                   │
│  ┌──────────┐    poll     ┌────────────┐   read     ┌────────────┐          │
│  │  Queue   │ ───────────▶│   Worker   │ ─────────▶ │ Filesystem │          │
│  └──────────┘   get job   └────────────┘   file     └────────────┘          │
│                                  │                                           │
│                                  │ OCR (Tesseract)                          │
│                                  │                                           │
│                                  │ save result                               │
│                                  ▼                                           │
│                            ┌────────────┐                                    │
│                            │ Filesystem │ (./storage/results/)              │
│                            └────────────┘                                    │
│                                  │                                           │
│                                  │ update status                             │
│                                  ▼                                           │
│                            ┌──────────┐                                      │
│                            │  SQLite  │ (jobs table)                        │
│                            └──────────┘                                      │
│                                                                               │
│  4. QUERY STATUS                                                              │
│  ┌────────┐   GET /jobs/:id  ┌────────────┐   query   ┌──────────┐          │
│  │ Client │ ────────────────▶│ API Server │ ────────▶ │  SQLite  │          │
│  └────────┘                  └────────────┘           └──────────┘          │
│       ▲                            │                                         │
│       └────────────────────────────┘                                         │
│              return status                                                   │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.4. Layer Separation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         3-LAYER ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                          EDGE LAYER                                  │   │
│   │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │   │
│   │   │ Web Frontend │    │  API Server  │    │ File Storage │         │   │
│   │   │   (React)    │    │  (Express)   │    │ (Filesystem) │         │   │
│   │   └──────────────┘    └──────────────┘    └──────────────┘         │   │
│   │         │                    │                    ▲                  │   │
│   │         │                    │                    │                  │   │
│   │         └────────────────────┼────────────────────┘                  │   │
│   │                              │                                       │   │
│   └──────────────────────────────┼───────────────────────────────────────┘   │
│                                  │ API calls                                 │
│                                  ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      ORCHESTRATION LAYER                             │   │
│   │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │   │
│   │   │ Auth Module  │    │  Job Module  │    │    Queue     │         │   │
│   │   │              │    │              │    │  (in-memory) │         │   │
│   │   └──────────────┘    └──────────────┘    └──────────────┘         │   │
│   │         │                    │                    │                  │   │
│   │         └────────────────────┼────────────────────┘                  │   │
│   │                              │                                       │   │
│   │                        ┌─────┴─────┐                                 │   │
│   │                        │  SQLite   │                                 │   │
│   │                        │ Database  │                                 │   │
│   │                        └───────────┘                                 │   │
│   └──────────────────────────────┼───────────────────────────────────────┘   │
│                                  │ queue polling                             │
│                                  ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       PROCESSING LAYER                               │   │
│   │   ┌──────────────────────────────────────────────────────────────┐  │   │
│   │   │                     Worker Process                            │  │   │
│   │   │   ┌────────────┐    ┌────────────┐    ┌────────────┐        │  │   │
│   │   │   │ Queue Pull │───▶│  Tesseract │───▶│ Save Result│        │  │   │
│   │   │   └────────────┘    │    OCR     │    └────────────┘        │  │   │
│   │   │                     └────────────┘                           │  │   │
│   │   └──────────────────────────────────────────────────────────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│   NOTE: Layers communicate through defined interfaces, NOT direct access.   │
│   Worker accesses storage directly in Phase 1 (simplified for local).       │
│   Phase 2 will introduce File Proxy Service for proper layer separation.    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. API Specification

### 4.1. API Design Principles

- **Style:** REST
- **Base URL:** `http://localhost:3001/api/v1`
- **Versioning:** URI path (`/v1/`)
- **Authentication:** Session cookie (simple for MVP)
- **Error Format:** Consistent JSON structure

### 4.2. API Endpoint Catalog

#### 4.2.1. Auth Endpoints

```yaml
# Register
Endpoint: POST /api/v1/auth/register
Description: Create new user account
Authentication: None

Request:
  Body:
    {
      "email": "string (required, email format)",
      "password": "string (required, min 6 chars)"
    }

Response (201 Created):
    {
      "user": {
        "id": "usr_abc123",
        "email": "user@example.com",
        "created_at": "2024-01-15T10:30:00Z"
      },
      "message": "Registration successful"
    }

Error Responses:
  400: { "error": "VALIDATION_ERROR", "message": "Email format invalid" }
  400: { "error": "VALIDATION_ERROR", "message": "Password must be at least 6 characters" }
  409: { "error": "EMAIL_EXISTS", "message": "Email already exists" }
```

```yaml
# Login
Endpoint: POST /api/v1/auth/login
Description: Authenticate and create session
Authentication: None

Request:
  Body:
    {
      "email": "string (required)",
      "password": "string (required)"
    }

Response (200 OK):
    {
      "user": {
        "id": "usr_abc123",
        "email": "user@example.com"
      },
      "message": "Login successful"
    }
    # Sets session cookie

Error Responses:
  401: { "error": "INVALID_CREDENTIALS", "message": "Invalid email or password" }
```

```yaml
# Logout
Endpoint: POST /api/v1/auth/logout
Description: Clear session
Authentication: Required

Response (200 OK):
    {
      "message": "Logout successful"
    }
```

```yaml
# Get Current User
Endpoint: GET /api/v1/auth/me
Description: Get current authenticated user
Authentication: Required

Response (200 OK):
    {
      "user": {
        "id": "usr_abc123",
        "email": "user@example.com",
        "created_at": "2024-01-15T10:30:00Z"
      }
    }

Error Responses:
  401: { "error": "UNAUTHORIZED", "message": "Not authenticated" }
```

#### 4.2.2. Upload Endpoints

```yaml
# Upload Files
Endpoint: POST /api/v1/upload
Description: Upload multiple files
Authentication: Required
Content-Type: multipart/form-data

Request:
  Body (multipart):
    files[]: File[] (required, max 20 files)

Response (200 OK):
    {
      "uploaded": [
        {
          "file_id": "file_xyz789",
          "filename": "document.pdf",
          "size": 1024000,
          "format": "pdf",
          "page_count": 5,
          "status": "valid"
        }
      ],
      "skipped": [
        {
          "filename": "large.pdf",
          "reason": "File too large. Maximum 10MB"
        }
      ],
      "total_valid": 5,
      "total_size": 5120000
    }

Error Responses:
  400: { "error": "NO_FILES", "message": "No files provided" }
  400: { "error": "BATCH_TOO_LARGE", "message": "Total batch size exceeds 50MB" }
  400: { "error": "TOO_MANY_FILES", "message": "Maximum 20 files per batch" }
  401: { "error": "UNAUTHORIZED", "message": "Not authenticated" }
```

#### 4.2.3. Job Endpoints

```yaml
# Process Files (Submit Request)
Endpoint: POST /api/v1/requests
Description: Create request and queue jobs for processing
Authentication: Required

Request:
  Body:
    {
      "file_ids": ["file_xyz789", "file_abc123", ...] (required, array)
    }

Response (201 Created):
    {
      "request_id": "req_mno456",
      "status": "SUBMITTED",
      "jobs": [
        {
          "job_id": "job_pqr789",
          "file_id": "file_xyz789",
          "filename": "document.pdf",
          "status": "QUEUED"
        }
      ],
      "total_jobs": 5,
      "estimated_time_seconds": 150
    }

Error Responses:
  400: { "error": "NO_FILES", "message": "No file_ids provided" }
  400: { "error": "INVALID_FILES", "message": "Some file_ids not found" }
  401: { "error": "UNAUTHORIZED", "message": "Not authenticated" }
```

```yaml
# Get Request Status
Endpoint: GET /api/v1/requests/{request_id}
Description: Get request and all job statuses
Authentication: Required

Response (200 OK):
    {
      "request_id": "req_mno456",
      "status": "PROCESSING",
      "created_at": "2024-01-15T10:30:00Z",
      "summary": {
        "total": 5,
        "completed": 2,
        "processing": 1,
        "queued": 1,
        "retrying": 1,
        "failed": 0
      },
      "jobs": [
        {
          "job_id": "job_pqr789",
          "file_id": "file_xyz789",
          "filename": "document.pdf",
          "status": "COMPLETED",
          "result_available": true,
          "processing_time_ms": 2340
        },
        {
          "job_id": "job_stu012",
          "file_id": "file_def456",
          "filename": "invoice.png",
          "status": "RETRYING",
          "retry_count": 1,
          "last_error": "OCR engine timeout"
        }
      ]
    }

Error Responses:
  404: { "error": "NOT_FOUND", "message": "Request not found" }
  403: { "error": "FORBIDDEN", "message": "Access denied" }
```

```yaml
# Get Job Status
Endpoint: GET /api/v1/jobs/{job_id}
Description: Get single job status with full details
Authentication: Required

Response (200 OK - Completed):
    {
      "job_id": "job_pqr789",
      "request_id": "req_mno456",
      "file_id": "file_xyz789",
      "filename": "document.pdf",
      "status": "COMPLETED",
      "method": "ocr_text_raw",
      "tier": 0,
      "created_at": "2024-01-15T10:30:00Z",
      "started_at": "2024-01-15T10:30:05Z",
      "completed_at": "2024-01-15T10:30:08Z",
      "processing_time_ms": 2340,
      "result_available": true
    }

Response (200 OK - Failed):
    {
      "job_id": "job_stu012",
      "status": "FAILED",
      "retry_count": 3,
      "error": "Maximum retries exceeded",
      "error_history": [
        { "attempt": 1, "error": "OCR timeout", "timestamp": "..." },
        { "attempt": 2, "error": "OCR timeout", "timestamp": "..." },
        { "attempt": 3, "error": "OCR timeout", "timestamp": "..." }
      ]
    }

Error Responses:
  404: { "error": "NOT_FOUND", "message": "Job not found" }
  403: { "error": "FORBIDDEN", "message": "Access denied" }
```

#### 4.2.4. Result Endpoints

```yaml
# Get Result (View)
Endpoint: GET /api/v1/jobs/{job_id}/result
Description: Get OCR result content
Authentication: Required

Query Parameters:
  format: "text" | "json" (optional, default: "text")

Response (200 OK - text format):
    {
      "text": "Extracted text content here...",
      "metadata": {
        "filename": "document.pdf",
        "page_count": 5,
        "processing_time_ms": 2340,
        "service_version": "1.0.0"
      }
    }

Response (200 OK - json format):
    {
      "text": "Extracted text content here...",
      "filename": "document.pdf",
      "processing_time_ms": 2340,
      "service_version": "1.0.0",
      "extracted_at": "2024-01-15T10:30:08Z"
    }

Error Responses:
  404: { "error": "NOT_FOUND", "message": "Job not found" }
  400: { "error": "NOT_COMPLETED", "message": "Job not completed yet" }
  410: { "error": "EXPIRED", "message": "Result no longer available" }
```

```yaml
# Download Result
Endpoint: GET /api/v1/jobs/{job_id}/download
Description: Download result as file
Authentication: Required

Query Parameters:
  format: "txt" | "json" (required)

Response (200 OK):
    Content-Type: text/plain or application/json
    Content-Disposition: attachment; filename="document_ocr.txt"

    (file content)

Error Responses:
  404: { "error": "NOT_FOUND", "message": "Job not found" }
  400: { "error": "NOT_COMPLETED", "message": "Job not completed" }
  410: { "error": "EXPIRED", "message": "Result no longer available" }
```

```yaml
# Download All Results (ZIP)
Endpoint: GET /api/v1/requests/{request_id}/download
Description: Download all results as ZIP
Authentication: Required

Response (200 OK):
    Content-Type: application/zip
    Content-Disposition: attachment; filename="request_mno456_results.zip"

    (zip file content containing all result files)

Error Responses:
  404: { "error": "NOT_FOUND", "message": "Request not found" }
  400: { "error": "NO_RESULTS", "message": "No completed results available" }
```

### 4.3. Error Handling Strategy

**Error Response Format:**

```json
{
  "error": "ERROR_CODE",
  "message": "Human readable message",
  "details": {} // optional, additional info
}
```

**Error Codes:**

| Code | HTTP Status | Description |
|---|---|---|
| VALIDATION_ERROR | 400 | Input validation failed |
| NO_FILES | 400 | No files provided |
| BATCH_TOO_LARGE | 400 | Batch exceeds size limit |
| TOO_MANY_FILES | 400 | Too many files in batch |
| INVALID_FILES | 400 | Invalid file IDs |
| NOT_COMPLETED | 400 | Job not yet completed |
| UNAUTHORIZED | 401 | Not authenticated |
| INVALID_CREDENTIALS | 401 | Wrong email/password |
| FORBIDDEN | 403 | Access denied |
| NOT_FOUND | 404 | Resource not found |
| EMAIL_EXISTS | 409 | Email already registered |
| EXPIRED | 410 | Resource expired/deleted |
| INTERNAL_ERROR | 500 | Server error |

---

## 5. Data Dictionary & Schema Design

### 5.1. Database Schema (SQLite)

#### Users Table

```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,           -- UUID format: usr_xxx
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_users_email ON users(email);
```

#### Sessions Table

```sql
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,           -- UUID format: sess_xxx
    user_id         TEXT NOT NULL,
    token           TEXT NOT NULL UNIQUE,
    expires_at      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
```

#### Files Table

```sql
CREATE TABLE files (
    id              TEXT PRIMARY KEY,           -- UUID format: file_xxx
    user_id         TEXT NOT NULL,
    filename        TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    path            TEXT NOT NULL,
    size            INTEGER NOT NULL,
    format          TEXT NOT NULL,              -- png, jpeg, pdf
    page_count      INTEGER NOT NULL DEFAULT 1,
    mime_type       TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT,                        -- NULL if not deleted

    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_files_user ON files(user_id);
CREATE INDEX idx_files_uploaded ON files(uploaded_at);
```

#### Requests Table

```sql
CREATE TABLE requests (
    id              TEXT PRIMARY KEY,           -- UUID format: req_xxx
    user_id         TEXT NOT NULL,
    method          TEXT NOT NULL DEFAULT 'ocr_text_raw',
    tier            INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'SUBMITTED',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_requests_user ON requests(user_id);
CREATE INDEX idx_requests_status ON requests(status);
```

#### Jobs Table

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,           -- UUID format: job_xxx
    request_id      TEXT NOT NULL,
    file_id         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'SUBMITTED',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error           TEXT,                        -- Last error message
    error_history   TEXT,                        -- JSON array of errors
    result_path     TEXT,                        -- Path to result files
    processing_time_ms INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    started_at      TEXT,
    completed_at    TEXT,

    FOREIGN KEY (request_id) REFERENCES requests(id),
    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE INDEX idx_jobs_request ON jobs(request_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at);
```

#### Queue Table (Lightweight Queue Alternative)

```sql
-- Optional: If using SQLite-based queue instead of in-memory
CREATE TABLE job_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING, PROCESSING, DONE
    priority        INTEGER NOT NULL DEFAULT 0,
    scheduled_at    TEXT NOT NULL DEFAULT (datetime('now')),
    picked_at       TEXT,

    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE INDEX idx_queue_status ON job_queue(status, scheduled_at);
```

### 5.2. Data Dictionary

#### Users Table

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | TEXT | PK, UUID | User identifier | "usr_abc123" |
| email | TEXT | NOT NULL, UNIQUE | User email | "user@example.com" |
| password_hash | TEXT | NOT NULL | Bcrypt hash | "$2b$10$..." |
| created_at | TEXT | NOT NULL, ISO8601 | Creation timestamp | "2024-01-15T10:30:00Z" |
| updated_at | TEXT | NOT NULL, ISO8601 | Last update | "2024-01-15T10:30:00Z" |

#### Jobs Table

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | TEXT | PK, UUID | Job identifier | "job_xyz789" |
| request_id | TEXT | FK to requests | Parent request | "req_mno456" |
| file_id | TEXT | FK to files | Source file | "file_abc123" |
| status | TEXT | NOT NULL, ENUM | Current state | "PROCESSING" |
| retry_count | INTEGER | NOT NULL, >= 0 | Retry attempts | 1 |
| error | TEXT | NULL allowed | Last error message | "OCR timeout" |
| error_history | TEXT | NULL, JSON | All errors | "[{...}]" |
| result_path | TEXT | NULL allowed | Result file path | "./storage/results/job_xyz789/" |
| processing_time_ms | INTEGER | NULL allowed | Processing duration | 2340 |
| created_at | TEXT | NOT NULL | Submit time | "2024-01-15T10:30:00Z" |
| started_at | TEXT | NULL allowed | Processing start | "2024-01-15T10:30:05Z" |
| completed_at | TEXT | NULL allowed | Completion time | "2024-01-15T10:30:08Z" |

### 5.3. Job State Machine

```
                              ┌─────────────────┐
                              │   SUBMITTED     │
                              └────────┬────────┘
                                       │ Auto (immediate)
                                       ▼
                ┌──────────────────────────────────────────┐
                │                                          │
                │              ┌───────────────┐◄──────────┘
                │              │    QUEUED     │
                │              └───────┬───────┘
                │                      │ Worker picks
                │                      ▼
                │              ┌───────────────┐
                │              │  PROCESSING   │
                │              └───────┬───────┘
                │                      │
                │         ┌────────────┼────────────┐
                │         │            │            │
                │      Success     Retriable    Non-retriable
                │         │         Error         Error
                │         │            │            │
                │         ▼            ▼            ▼
                │   ┌──────────┐ ┌──────────┐ ┌──────────┐
                │   │COMPLETED │ │ RETRYING │ │  FAILED  │
                │   └──────────┘ └────┬─────┘ └──────────┘
                │                     │
                │                     │ After delay
                └─────────────────────┘ (back to QUEUED)
```

**Status Values:**

| Status | Description | Transitions To |
|---|---|---|
| SUBMITTED | Job just created | QUEUED |
| QUEUED | In queue waiting for worker | PROCESSING |
| PROCESSING | Worker is processing | COMPLETED, RETRYING, FAILED |
| RETRYING | Waiting for retry after error | QUEUED |
| COMPLETED | Successfully completed | Terminal |
| FAILED | Failed after max retries | Terminal |

**Transition Rules:**

| From | To | Trigger | Condition | Side Effect |
|---|---|---|---|---|
| SUBMITTED | QUEUED | Auto | - | Push to queue |
| QUEUED | PROCESSING | Worker picks | - | Set started_at |
| PROCESSING | COMPLETED | OCR success | - | Save result, set completed_at |
| PROCESSING | RETRYING | Error | retry_count < MAX_RETRIES AND retriable | Increment retry_count, schedule re-queue |
| PROCESSING | FAILED | Error | retry_count >= MAX_RETRIES OR non-retriable | Set final error |
| RETRYING | QUEUED | Delay elapsed | - | Re-push to queue |

---

## 6. Non-Functional Requirements

### 6.1. Performance (Local Environment)

| Metric | Target | Measurement | Priority |
|---|---|---|---|
| **API Response Time (P95)** | < 200ms | Local testing | Must |
| **File Upload (10MB)** | < 5s | Local testing | Must |
| **Job Processing (1 page)** | < 10s | End-to-end | Must |
| **Job Processing (10 pages PDF)** | < 60s | End-to-end | Must |
| **Queue Latency** | < 1s | Job QUEUED → PROCESSING | Must |
| **Status Query** | < 100ms | API response | Must |

### 6.2. Scalability (Phase 1 Local)

Phase 1 không yêu cầu scalability phức tạp, nhưng thiết kế phải **chuẩn bị cho scale**:

| Component | Phase 1 | Phase 2+ Ready |
|---|---|---|
| **API Server** | Single instance | Stateless, can add instances |
| **Worker** | Single process | Can run multiple workers |
| **Queue** | In-memory/SQLite | Interface ready for Redis |
| **Storage** | Local filesystem | Interface ready for S3/R2 |
| **Database** | SQLite | Schema compatible with PostgreSQL/Firestore |

### 6.3. Reliability

| Aspect | Target | Implementation |
|---|---|---|
| **Job Retry** | Max 3 retries | Exponential backoff |
| **Error Handling** | Graceful degradation | Proper error classification |
| **Data Integrity** | No data loss | Transaction-based operations |
| **Crash Recovery** | Resume from queue | Persistent job queue (SQLite) |

### 6.4. Security (Simplified for Local)

| Aspect | Phase 1 Implementation | Notes |
|---|---|---|
| **Authentication** | Session-based, bcrypt | Simple but secure |
| **Authorization** | User-scoped access | Each user sees only their data |
| **Password Storage** | Bcrypt (cost 10) | Industry standard |
| **Session** | Cookie + server-side | Simple session management |
| **Input Validation** | Server-side validation | Prevent malformed input |
| **File Validation** | MIME + magic bytes | Prevent malicious files |

### 6.5. Observability

| Layer | Implementation | Metrics |
|---|---|---|
| **Logging** | Console + file logs | Structured JSON logs |
| **Error Tracking** | Log to file | Error details with stack trace |
| **Job Metrics** | SQLite queries | Job counts by status, processing time |

**Key Metrics to Track:**

| Metric | Description | Target |
|---|---|---|
| Job Success Rate | % jobs COMPLETED / total | > 90% |
| First-attempt Success | % jobs COMPLETED without retry | > 80% |
| Avg Processing Time | SUBMITTED → COMPLETED | < 60s |
| Avg Queue Latency | QUEUED → PROCESSING | < 5s |
| Error Rate | % jobs FAILED | < 10% |

---

## 7. Test Strategy

### 7.1. Test Levels

| Test Level | Scope | Responsibility | Tools | Automation |
|---|---|---|---|---|
| **Unit** | Functions, utilities | Developer | Jest/pytest | 100% |
| **Integration** | API endpoints, DB | Developer | Supertest/pytest | 90% |
| **E2E** | Full user flows | Developer/QA | Playwright/Cypress | 80% |
| **Manual** | Exploratory, UX | QA | Manual | Manual |

### 7.2. Acceptance Criteria Matrix

| FR-ID | Scenario | Given | When | Then |
|---|---|---|---|---|
| FR-L001 | Happy: Register | New email | Submit registration | Account created |
| FR-L001 | Edge: Email exists | Existing email | Submit | Error "Email already exists" |
| FR-L001 | Edge: Short password | Password "12345" | Submit | Error "Password too short" |
| FR-L002 | Happy: Upload | Valid 5MB PDF | Upload | File saved, preview shown |
| FR-L002 | Edge: Large file | 15MB file | Upload | Skip: "File too large" |
| FR-L002 | Edge: Wrong format | DOC file | Upload | Skip: "Unsupported format" |
| FR-L003 | Happy: Submit | Valid files | Process All | Request created, jobs queued |
| FR-L004 | Happy: OCR | Valid image | Worker processes | Result saved, status COMPLETED |
| FR-L004 | Edge: Timeout | Slow processing | Timeout | Status RETRYING, retry scheduled |
| FR-L004 | Edge: Max retries | 3 failures | 3rd retry fails | Status FAILED |
| FR-L005 | Happy: Status | Ongoing request | Get status | Current status returned |
| FR-L006 | Happy: Download | Completed job | Download TXT | File downloads |
| FR-L006 | Edge: Expired | Deleted result | Download | Error "Result no longer available" |

### 7.3. Test Data Requirements

| Test Type | Data Source | Volume | Management |
|---|---|---|---|
| Unit tests | Mocks, fixtures | Minimal | In-repo |
| Integration | Seed scripts | 10 users, 50 files | Reset per run |
| E2E | Test files | 20 sample files | In test-data folder |
| OCR accuracy | Sample documents | 50 files (diverse) | Curated set |

**Sample Test Files:**

| File Type | Count | Characteristics |
|---|---|---|
| PNG images | 20 | Various sizes, text quality |
| JPEG images | 15 | Various compression levels |
| PDF documents | 15 | 1-10 pages, text + images |

---

## 8. UI-Logic Specification

### 8.1. SCR-L001: Login Page

| Trường | Nội dung |
|---|---|
| **Screen** | Login Page |
| **URL** | `/login` |
| **Access** | Public (unauthenticated) |
| **Layout** | Centered card, max-width 400px |
| **Input Fields** | Email input, Password input |
| **Actions** | Login button, Register link |
| **States** | Default, Loading, Error |
| **Validations** | Email format (client), Password required (client) |
| **Responsive** | Single column, full width on mobile |

**Validation Logic:**

| Field | Client Validation | Server Validation | Error Message |
|---|---|---|---|
| Email | Required, email format | Exists in DB | "Email format invalid" |
| Password | Required | Matches hash | "Invalid email or password" |

### 8.2. SCR-L002: Register Page

| Trường | Nội dung |
|---|---|
| **Screen** | Register Page |
| **URL** | `/register` |
| **Access** | Public |
| **Layout** | Centered card, max-width 400px |
| **Input Fields** | Email input, Password input, Confirm password |
| **Actions** | Register button, Login link |
| **States** | Default, Loading, Success, Error |
| **Validations** | Email format, Password min 6, Passwords match |
| **Responsive** | Single column |

### 8.3. SCR-L003: Dashboard

| Trường | Nội dung |
|---|---|
| **Screen** | Dashboard / Home |
| **URL** | `/` or `/dashboard` |
| **Access** | Authenticated |
| **Layout** | Header + main content area |
| **Components** | User info, Recent requests list, Upload button |
| **Actions** | Upload new, View request, Logout |
| **States** | Empty (no requests), With data |
| **Responsive** | Stacked on mobile |

### 8.4. SCR-L004: Batch Upload

| Trường | Nội dung |
|---|---|
| **Screen** | Batch Upload Page |
| **URL** | `/upload` |
| **Access** | Authenticated |
| **Layout** | Drop zone + file list + action bar |
| **Components** | Drag-drop zone, File picker, File list with previews, Progress bar |
| **Input Fields** | File picker (multiple), Folder picker |
| **Actions** | Add files, Remove file, Process All, Clear all |
| **States** | Empty, Uploading, Uploaded (with file list), Error |
| **Validations** | File size, format, batch limits |
| **Responsive** | Smaller drop zone on mobile, vertical file list |

**Component Behavior:**

| Component | Behavior |
|---|---|
| Drag-drop zone | Accepts files/folders, highlights on drag-over |
| File list | Shows thumbnail, name, size, status (valid/invalid) |
| Remove button | Removes individual file from list |
| Process All | Disabled if no valid files, submits all valid files |

### 8.5. SCR-L005: Request Status

| Trường | Nội dung |
|---|---|
| **Screen** | Request Status Page |
| **URL** | `/requests/{request_id}` |
| **Access** | Authenticated, owner only |
| **Layout** | Header + progress summary + job list |
| **Components** | Overall progress bar, Status summary, Job cards |
| **Data Display** | Request ID, Created time, Overall status, Per-job status |
| **Actions** | Refresh, View Result (per job), Download All |
| **States** | Loading, Processing, Partial Success, Complete, Failed |
| **Responsive** | Single column, stacked job cards |

**Status Display:**

| Overall Status | Display |
|---|---|
| All QUEUED | "Waiting in queue... (0/N)" |
| Some PROCESSING | "Processing... (X/N completed)" |
| All COMPLETED | "Completed! All N files processed" |
| Some FAILED | "Partial Success: X/N completed, Y failed" |
| All FAILED | "Failed: All files failed" |

**Auto-refresh (Optional):**

- Refresh every 5 seconds while any job is QUEUED or PROCESSING
- Stop auto-refresh when all jobs are terminal (COMPLETED/FAILED)

### 8.6. SCR-L006: Result Viewer

| Trường | Nội dung |
|---|---|
| **Screen** | Result Viewer |
| **URL** | `/jobs/{job_id}/result` |
| **Access** | Authenticated, owner only |
| **Layout** | Two-column: original (left) + result (right), or tabs on mobile |
| **Components** | Original image viewer, Extracted text display, Metadata panel |
| **Data Display** | Original file, Extracted text, Processing time, Service info |
| **Actions** | Download TXT, Download JSON, Back to request |
| **States** | Loading, Display, Error |
| **Responsive** | Tabs instead of columns on mobile |

---

## Summary

```
--- SUMMARY HANDOFF (BA Tech → Dev Team) ---
Phase: 1 - Local MVP
Purpose: Technical validation, prove architecture works

Functional Requirements: 7 FRs (FR-L001 to FR-L007)
- Auth: Register, Login, Session
- Upload: Batch file upload with validation
- Processing: Job creation, worker processing, retry
- Status: Query request/job status
- Results: View and download OCR results
- Cleanup: Automatic file cleanup

System Components:
- API Server (Express/FastAPI)
- Worker Process (Tesseract)
- SQLite Database
- Local Filesystem Storage
- In-memory Queue

API Endpoints: 12 endpoints
- Auth: 4 (register, login, logout, me)
- Upload: 1 (POST /upload)
- Jobs: 4 (create request, get request, get job, get result)
- Download: 3 (download result, download all)

Data Entities: 5 tables
- users, sessions, files, requests, jobs

State Machine: 6 states
- SUBMITTED → QUEUED → PROCESSING → COMPLETED/RETRYING/FAILED

NFRs Defined:
- Job processing < 60s for 10 pages
- API response < 200ms
- Queue latency < 1s

Test Strategy:
- Unit (100%), Integration (90%), E2E (80%)
- 50+ sample files for testing

Interfaces Ready for Phase 2:
- Storage interface (→ S3/R2)
- Queue interface (→ Redis/Pub-Sub)
- Database schema (→ PostgreSQL/Firestore)
- Worker interface (→ GPU containers)

--- ✅ PHASE 1 BA TECH COMPLETE ---
```
