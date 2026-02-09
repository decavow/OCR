# OCR Platform Phase 1 — Business Analysis Document (Local MVP)

> Tài liệu phân tích nghiệp vụ cho OCR Platform Phase 1 - Local MVP
> Version: 1.0 | Status: Draft
> References: `01-PO/local/PO_phase1_local.md`

---

## Table of Contents

1. [Product Brief](#1-product-brief)
2. [User & Problem Analysis](#2-user--problem-analysis)
3. [Product Requirements](#3-product-requirements)
4. [Core Use Cases](#4-core-use-cases)
5. [Glossary & Domain Model](#5-glossary--domain-model)

---

## 1. Product Brief

### 1.1. Product Vision & Elevator Pitch

**One-liner:**
> Local MVP là một prototype web app cho phép team phát triển validate luồng OCR end-to-end trên môi trường local trước khi đầu tư vào infrastructure cloud.

**Elevator Pitch (30 giây):**

> Trước khi xây dựng hệ thống OCR production với nhiều tiers và services, team cần chứng minh kiến trúc 3 lớp (Edge → Orchestration → Processing) hoạt động đúng.
>
> Local MVP cho phép batch upload files (PNG, JPEG, PDF), xử lý OCR với 1 service (ocr_text_raw), và xem/download kết quả. Tất cả chạy trên máy local.
>
> Mục tiêu: Validate end-to-end flow, lock architectural decisions, và chuẩn bị interfaces cho Phase 2 (Cloud).

**Phase 1 Purpose:**

Phase 1 **KHÔNG phải sản phẩm cho end-user**, mà là technical validation để:
- Chốt các quyết định kiến trúc cốt lõi
- Validate data flow pattern giữa các layers
- Thiết lập data model schema
- Chuẩn bị interface cho scale controller (Phase 3)

### 1.2. Scope Boundaries

**In Scope (Phase 1 Local):**

| Capability | Description |
|---|---|
| 1 OCR Service | `ocr_text_raw` — Extract text thuần, không format |
| 1 Tier | Local (Tier 0) — Chạy trên máy local |
| Batch Upload | Nhiều file hoặc folder (PNG, JPEG, PDF) |
| Simple Auth | Email/password, không OAuth |
| Job Tracking | Polling-based, không real-time |
| Result Output | TXT, JSON format |
| Retry Mechanism | Max 3 lần, exponential backoff |
| Local Infrastructure | Filesystem storage, in-memory queue, SQLite |

**Out of Scope (Deferred to Phase 2+):**

| Capability | Phase |
|---|---|
| Multiple OCR services (table, formatted, handwriting) | Phase 2 |
| Multiple tiers (Cloud, Enhanced, Dedicated, VIP) | Phase 2-3 |
| OAuth login (Google, GitHub) | Phase 2 |
| Billing/Credit system | Phase 2 |
| Real-time notifications (SSE/WebSocket) | Phase 2 |
| Cloud deployment | Phase 2 |
| Auto-scaling | Phase 3 |
| File Proxy Service | Phase 2 |

### 1.3. Problem Statement

```
[Team phát triển] đang gặp vấn đề [cần validate kiến trúc OCR 3 lớp trước khi deploy cloud]
khi [lên kế hoạch xây dựng hệ thống OCR production].

Hậu quả nếu không validate:
- Rủi ro lớn khi scale: phát hiện lỗi thiết kế ở giai đoạn sau
- Chi phí sửa lỗi kiến trúc cao gấp 10-100 lần
- Các quyết định thiết kế không được test trước

Hiện tại:
- Chưa có prototype để validate kiến trúc 3 lớp
- Chưa có data model được test với real data flow
- Chưa có interface definitions cho các layers
```

### 1.4. Architecture Validation Goals

Phase 1 cần validate và "lock" các quyết định sau:

| Quyết định | Mô tả | Validation Criteria |
|---|---|---|
| **Job Lifecycle** | State machine: SUBMITTED → QUEUED → PROCESSING → COMPLETED/FAILED/RETRYING | State transitions hoạt động đúng |
| **Data Flow Pattern** | Client → Edge → Orchestrator → Worker → Edge → Client | File và metadata truyền đúng qua các layer |
| **Data Model** | Schema cho users, requests, jobs, files | Query patterns hoạt động hiệu quả |
| **Layer Separation** | Edge, Orchestration, Processing tách biệt | Các layer có thể deploy độc lập |
| **Queue Pattern** | Job dispatch qua queue, worker pull-based | Worker pull và process job thành công |
| **Retry Mechanism** | Exponential backoff, max retries, error classification | Retry hoạt động đúng, không infinite loop |
| **Batch Processing** | Một request chứa nhiều files | Batch upload, partial success handling |
| **Configurable Params** | Timeout, retries, estimated time via env vars | Params có thể thay đổi mà không rebuild |

---

## 2. User & Problem Analysis

### 2.1. User Personas (Phase 1)

Phase 1 là internal prototype, target audience là team phát triển:

#### Persona 1: Dev — Backend Developer (Primary)

| Trường | Nội dung |
|---|---|
| **Persona Name** | Dev — Backend Developer |
| **Demographics** | Developer trong team, quen với local development, sử dụng terminal và IDE |
| **Goal** | 1. Validate job processing flow hoạt động đúng<br>2. Test data model và query patterns<br>3. Chốt API contracts giữa các layers |
| **Pain Point** | Không có prototype để test kiến trúc trước khi code production |
| **Current Solution** | Mockups, diagrams, giả định chưa được validate |
| **Why Use Local MVP?** | Cần môi trường thực tế để test architectural decisions |
| **Key Expectation** | Luồng job từ submit đến complete hoạt động ổn định |

#### Persona 2: QA — Quality Assurance (Secondary)

| Trường | Nội dung |
|---|---|
| **Persona Name** | QA — Tester |
| **Demographics** | QA engineer, test cả manual và automation |
| **Goal** | 1. Test các happy path và error cases<br>2. Validate data consistency qua các states |
| **Pain Point** | Chưa có môi trường local để test full flow |
| **Current Solution** | Unit tests riêng lẻ, chưa test end-to-end |
| **Why Use Local MVP?** | Có thể test full flow trên local mà không cần cloud |
| **Key Expectation** | Mọi edge cases được handle đúng |

### 2.2. User Journey Map (Core Flow)

```
[Access Website] → [Register] → [Login] → [Upload Files] → [Process] → [Check Status] → [View/Download]
       │              │            │            │              │              │               │
       ▼              ▼            ▼            ▼              ▼              ▼               ▼
   Open browser   Create new   Enter creds   Select files   Click         Refresh page    Verify output
   go to URL      account      login         drag-drop      "Process All"  to check       download
   (< 1 min)      (< 1 min)    (< 30s)       (< 2 min)      (< 1 min)     status          (< 2 min)
```

**Journey Detail:**

| Stage | User Action | User Feeling | Validation Opportunity |
|---|---|---|---|
| **Access** | Navigate to application URL | Expecting simple UI | Application loads, login page displays |
| **Register** | Create account with email/password | Quick, no friction | Registration works, validation works |
| **Login** | Enter credentials and login | Expecting fast response | Auth flow works, session persists |
| **Upload** | Select multiple files or drag-drop | Want batch support | Batch upload works, validation works |
| **Process** | Click Process All | Confident in system | Job created, enters queue |
| **Check Status** | Refresh page to see progress | Want to see progress | Status updates correctly through states |
| **View/Download** | See and download result | Verify accuracy | Result accurate, download works |

---

## 3. Product Requirements

### 3.1. Feature Prioritization Matrix

| Feature ID | Tên feature | User Value (1-5) | Business Value (1-5) | Dev Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| F-L001 | Simple Authentication | 4 | 5 | S | Must | Phase 1 |
| F-L002 | Batch Upload | 5 | 5 | M | Must | Phase 1 |
| F-L003 | OCR Processing | 5 | 5 | L | Must | Phase 1 |
| F-L004 | Job Status (Polling) | 4 | 4 | M | Must | Phase 1 |
| F-L005 | Result Viewing & Download | 5 | 4 | M | Must | Phase 1 |
| F-L006 | File Lifecycle | 3 | 3 | S | Should | Phase 1 |

**Legend:**
- User/Business Value: 1 (Low) - 5 (High)
- Dev Effort: S (Small), M (Medium), L (Large)

### 3.2. Product Requirements (Lean Format)

#### PR-L001: User Registration (F-L001)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L001 |
| **Feature** | F-L001 Simple Authentication |
| **User Story** | Với tư cách developer, tôi muốn đăng ký tài khoản để test authentication flow |
| **Acceptance Criteria** | AC1: Đăng ký với email hợp lệ + password (min 6 chars) → thành công<br>AC2: Email đã tồn tại → hiển thị lỗi "Email already exists"<br>AC3: Password < 6 chars → hiển thị lỗi "Password too short" |
| **Business Rules** | RULE-L001, RULE-L002, RULE-L003 |
| **Priority** | Must |
| **Notes** | Simplified password policy (min 6 chars only). No email verification. No OAuth. |

#### PR-L002: User Login (F-L001)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L002 |
| **Feature** | F-L001 Simple Authentication |
| **User Story** | Với tư cách developer, tôi muốn đăng nhập để access dashboard |
| **Acceptance Criteria** | AC1: Đăng nhập với credentials đúng → redirect to dashboard<br>AC2: Credentials sai → hiển thị lỗi "Invalid credentials"<br>AC3: Logout → session cleared, redirect to login |
| **Business Rules** | RULE-L003 |
| **Priority** | Must |
| **Notes** | Session stored in cookie/localStorage. Simple session management. |

#### PR-L003: Batch File Upload (F-L002)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L003 |
| **Feature** | F-L002 Batch Upload |
| **User Story** | Với tư cách user, tôi muốn upload nhiều files hoặc folder để process batch |
| **Acceptance Criteria** | AC1: Upload valid files (PNG, JPEG, PDF) via file picker → files saved<br>AC2: Upload folder → all valid files in folder saved<br>AC3: Single file > 10MB → error "File too large. Maximum 10MB per file"<br>AC4: Batch > 50MB total → error "Batch too large. Maximum 50MB total"<br>AC5: More than 20 files → error "Too many files. Maximum 20 files per batch"<br>AC6: Unsupported format → file skipped with warning<br>AC7: Corrupted file → file skipped with warning |
| **Business Rules** | RULE-L004, RULE-L004b, RULE-L004c, RULE-L005, RULE-L006, RULE-L007 |
| **Priority** | Must |
| **Notes** | Support drag-and-drop. PDF each page = 1 unit. Store in ./storage/uploads/{user_id}/{request_id}/ |

#### PR-L004: View Upload & Remove Files (F-L002)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L004 |
| **Feature** | F-L002 Batch Upload |
| **User Story** | Với tư cách user, tôi muốn xem danh sách files đã upload và remove files không cần |
| **Acceptance Criteria** | AC1: After upload → see file list with previews<br>AC2: Click remove → file removed from list<br>AC3: See total count và total size |
| **Business Rules** | RULE-L007 |
| **Priority** | Must |
| **Notes** | Preview as thumbnail for images. Show filename and size. |

#### PR-L005: Process All Files (F-L003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L005 |
| **Feature** | F-L003 OCR Processing |
| **User Story** | Với tư cách user, tôi muốn process tất cả files đã upload với OCR |
| **Acceptance Criteria** | AC1: Click "Process All" → request created with all files<br>AC2: Request status = SUBMITTED initially<br>AC3: All files use same config (ocr_text_raw, Tier 0)<br>AC4: Redirect to request status page |
| **Business Rules** | RULE-L008, RULE-L009, RULE-L010 |
| **Priority** | Must |
| **Notes** | Fixed: method=ocr_text_raw, tier=Local. No method/tier selection in Phase 1. |

#### PR-L006: Job Processing by Worker (F-L003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L006 |
| **Feature** | F-L003 OCR Processing |
| **User Story** | Với tư cách worker service, tôi muốn pull và process jobs từ queue |
| **Acceptance Criteria** | AC1: Worker polls queue → receives oldest QUEUED job<br>AC2: Job picked up → status PROCESSING<br>AC3: OCR success → result stored, status COMPLETED<br>AC4: OCR error + retry < max → status RETRYING, re-queued<br>AC5: OCR error + retry >= max → status FAILED with error details<br>AC6: No jobs in queue → worker waits and polls again |
| **Business Rules** | RULE-L011, RULE-L012, RULE-L013, RULE-L014, RULE-L015, RULE-L015b |
| **Priority** | Must |
| **Notes** | Worker as separate process. Direct access to local storage. Tesseract OCR engine. |

#### PR-L007: Retry Mechanism (F-L003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L007 |
| **Feature** | F-L003 OCR Processing |
| **User Story** | Với tư cách system, tôi muốn tự động retry failed jobs để handle transient errors |
| **Acceptance Criteria** | AC1: Retriable error + retry < max → job RETRYING, re-queued after delay<br>AC2: Exponential backoff delay: 1s, 2s, 4s...<br>AC3: Success after retry → COMPLETED with retry history preserved<br>AC4: Fail after max retries → FAILED with full error history<br>AC5: Non-retriable error (invalid file) → FAILED immediately, no retry |
| **Business Rules** | RULE-L015, RULE-L015b, RULE-L015c, RULE-L015d, RULE-L015e |
| **Priority** | Must |
| **Notes** | Retriable: timeout, OCR engine error. Non-retriable: invalid file, corrupted. |

#### PR-L008: Job Status Tracking (F-L004)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L008 |
| **Feature** | F-L004 Job Status (Polling) |
| **User Story** | Với tư cách user, tôi muốn xem status của processing jobs |
| **Acceptance Criteria** | AC1: View job page → see current status<br>AC2: Refresh page → status updated if changed<br>AC3: Status COMPLETED → show link to view/download result<br>AC4: Status FAILED → show error message<br>AC5: Status PROCESSING → show loading indicator<br>AC6: Status RETRYING → show "Retrying... (attempt X/3)" |
| **Business Rules** | RULE-L016, RULE-L017 |
| **Priority** | Must |
| **Notes** | Manual refresh only. Optional: auto-refresh every 5s. Simple UI: status text + timestamp. |

#### PR-L009: Batch Status Overview (F-L004)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L009 |
| **Feature** | F-L004 Job Status (Polling) |
| **User Story** | Với tư cách user, tôi muốn xem overall status của batch request |
| **Acceptance Criteria** | AC1: Request page shows overall progress (e.g., "3/5 files done")<br>AC2: Show individual file status (completed, processing, failed, retrying)<br>AC3: Partial success: show "4/5 completed, 1 failed" |
| **Business Rules** | - |
| **Priority** | Must |
| **Notes** | Batch can have partial success. Failed files don't block successful ones. |

#### PR-L010: View Result (F-L005)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L010 |
| **Feature** | F-L005 Result Viewing & Download |
| **User Story** | Với tư cách user, tôi muốn xem OCR result trên web |
| **Acceptance Criteria** | AC1: Job COMPLETED → click "View Result" → see extracted text<br>AC2: Optional: see original image side-by-side<br>AC3: Multi-file batch → navigate between files<br>AC4: Show processing time and service info |
| **Business Rules** | RULE-L018, RULE-L019 |
| **Priority** | Must |
| **Notes** | Simple text display. Processing time in metadata. |

#### PR-L011: Download Result (F-L005)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L011 |
| **Feature** | F-L005 Result Viewing & Download |
| **User Story** | Với tư cách user, tôi muốn download OCR result |
| **Acceptance Criteria** | AC1: Click "Download TXT" → plain text file downloads<br>AC2: Click "Download JSON" → JSON file with text + metadata<br>AC3: Batch: download individual results or all as ZIP |
| **Business Rules** | RULE-L018, RULE-L019 |
| **Priority** | Must |
| **Notes** | Output formats: TXT, JSON only. No DOCX, CSV, XLSX in Phase 1. |

#### PR-L012: File Cleanup (F-L006)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-L012 |
| **Feature** | F-L006 File Lifecycle |
| **User Story** | Với tư cách system, tôi muốn tự động xóa old files để storage không grow indefinitely |
| **Acceptance Criteria** | AC1: Files older than retention (default 24h) → deleted<br>AC2: Result files also deleted when expired<br>AC3: Job metadata retained after file deletion<br>AC4: Cleanup job logs which files were deleted |
| **Business Rules** | RULE-L020, RULE-L021, RULE-L022 |
| **Priority** | Should |
| **Notes** | Simple cleanup script running hourly. Configurable retention via env var. |

### 3.3. Business Rules Summary

| Rule ID | Tên quy tắc | Mô tả chi tiết |
|---|---|---|
| **RULE-L001** | Unique Email | Email phải unique trong hệ thống |
| **RULE-L002** | Simple Password | Minimum 6 characters (simplified for MVP) |
| **RULE-L003** | Session Storage | Session stored in cookie/localStorage |
| **RULE-L004** | Max File Size | 10MB per file |
| **RULE-L004b** | Max Batch Size | 50MB total per batch |
| **RULE-L004c** | Max Files Per Batch | 20 files per batch |
| **RULE-L005** | Supported Formats | PNG, JPEG, PDF only |
| **RULE-L006** | Local Storage | Files stored on local filesystem |
| **RULE-L007** | File Validation | Validate before store, skip invalid files |
| **RULE-L008** | Single Service | ocr_text_raw only in Phase 1 |
| **RULE-L009** | Single Tier | Tier 0 (Local) only in Phase 1 |
| **RULE-L010** | Auto Queue | Job enters queue immediately after submit |
| **RULE-L011** | Worker Pull | Worker polls queue for jobs |
| **RULE-L012** | Pull-based Worker | Worker pulls, not pushed |
| **RULE-L013** | Single Job Processing | One job at a time per worker |
| **RULE-L014** | Job Timeout | Configurable via JOB_TIMEOUT_SECONDS (default 300s) |
| **RULE-L015** | Max Retries | Configurable via MAX_RETRIES (default 3) |
| **RULE-L015b** | Retry Delay | Exponential backoff (1s, 2s, 4s...) |
| **RULE-L015c** | Retriable Errors | Timeout, OCR engine error, temporary failures |
| **RULE-L015d** | Non-retriable Errors | Invalid file format, file not found, corrupted file |
| **RULE-L015e** | Retry Metadata | Store retry_count, error_history[], last_error |
| **RULE-L016** | Manual Refresh | Status updates via page refresh (polling) |
| **RULE-L017** | No Real-time | No SSE/WebSocket in Phase 1 |
| **RULE-L018** | Output Formats | TXT, JSON only in Phase 1 |
| **RULE-L019** | JSON Metadata | Include text, filename, processing_time, service_version |
| **RULE-L020** | Default Retention | 24 hours |
| **RULE-L021** | Cleanup Schedule | Every hour |
| **RULE-L022** | Metadata Retention | Keep job metadata even after file deletion |

### 3.4. Configurable Parameters

| Parameter | Env Variable | Default | Mô tả |
|---|---|---|---|
| Job Timeout | `JOB_TIMEOUT_SECONDS` | 300 (5 min) | Max time for a job before timeout |
| Max Retries | `MAX_RETRIES` | 3 | Maximum retry attempts |
| Retry Base Delay | `RETRY_BASE_DELAY_MS` | 1000 | Base delay for exponential backoff (ms) |
| Estimated Time Factor | `ESTIMATE_TIME_FACTOR` | 1.0 | Multiplier for estimated time calculation |
| File Retention | `FILE_RETENTION_HOURS` | 24 | Hours before files are auto-deleted |
| Max File Size | `MAX_FILE_SIZE_MB` | 10 | Maximum size per file (MB) |
| Max Batch Size | `MAX_BATCH_SIZE_MB` | 50 | Maximum total batch size (MB) |
| Max Files Per Batch | `MAX_FILES_PER_BATCH` | 20 | Maximum files per batch |
| Worker Poll Interval | `WORKER_POLL_INTERVAL_MS` | 1000 | Worker queue polling interval (ms) |

---

## 4. Core Use Cases (MVP Only)

### UC-L001: Register Account

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L001 |
| **Use Case Name** | Register new account |
| **Actor(s)** | Developer/Tester |
| **User Story** | PR-L001 |
| **Trigger** | User opens application for the first time |
| **Main Flow** | 1. User navigates to localhost:3000<br>2. User sees Login page, clicks "Register"<br>3. User enters email and password<br>4. System validates email format and password length<br>5. System creates account<br>6. System redirects to dashboard |
| **Alternative Flows** | - |
| **Exception Flows** | 4a. Email exists → error "Email already exists"<br>4b. Password < 6 chars → error "Password too short" |
| **Postconditions** | User has active account, logged in, on dashboard |
| **Business Rules** | RULE-L001, RULE-L002, RULE-L003 |
| **MVP Notes** | No email verification. Password hash with bcrypt. |

### UC-L002: Batch Upload Files

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L002 |
| **Use Case Name** | Upload multiple files for OCR |
| **Actor(s)** | Logged-in User |
| **User Story** | PR-L003, PR-L004 |
| **Trigger** | User clicks "Upload" button |
| **Main Flow** | 1. User clicks upload button or drag-drops files<br>2. User selects multiple files or folder<br>3. System validates each file (format, size)<br>4. Valid files are uploaded to local storage<br>5. System shows file list with previews<br>6. User can remove individual files<br>7. User sees total count and "Process All" button |
| **Alternative Flows** | 2a. User uses folder picker instead of file picker |
| **Exception Flows** | 3a. File > 10MB → skip with warning "File too large"<br>3b. Unsupported format → skip with warning<br>3c. Total > 50MB → error "Batch too large"<br>3d. > 20 files → error "Too many files"<br>3e. All files invalid → error "No valid files" |
| **Postconditions** | Valid files uploaded, ready for processing |
| **Business Rules** | RULE-L004, RULE-L004b, RULE-L004c, RULE-L005, RULE-L006, RULE-L007 |
| **MVP Notes** | Direct upload to local filesystem. Support drag-and-drop. |

### UC-L003: Process Files

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L003 |
| **Use Case Name** | Process uploaded files with OCR |
| **Actor(s)** | Logged-in User with uploaded files |
| **User Story** | PR-L005 |
| **Trigger** | User clicks "Process All" |
| **Main Flow** | 1. User clicks "Process All" button<br>2. System creates request with all files<br>3. System creates job for each file<br>4. Jobs enter queue (status QUEUED)<br>5. System redirects to request status page<br>6. User sees "Processing... (0/N files done)" |
| **Alternative Flows** | - |
| **Exception Flows** | 2a. No files → error "No files to process" |
| **Postconditions** | Request created, jobs queued, user viewing status |
| **Business Rules** | RULE-L008, RULE-L009, RULE-L010 |
| **MVP Notes** | Fixed config: method=ocr_text_raw, tier=Local. No config selection. |

### UC-L004: Worker Processes Job

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L004 |
| **Use Case Name** | Worker processes OCR job |
| **Actor(s)** | Worker Service (automated) |
| **User Story** | PR-L006, PR-L007 |
| **Trigger** | Jobs in queue, worker polling |
| **Main Flow** | 1. Worker polls queue<br>2. Worker receives oldest QUEUED job<br>3. Job status → PROCESSING<br>4. Worker downloads file from local storage<br>5. Worker runs OCR (Tesseract)<br>6. Worker saves result to local storage<br>7. Job status → COMPLETED<br>8. Worker deletes temp files<br>9. Worker polls for next job |
| **Alternative Flows** | 6a. No jobs in queue → worker waits 1s, polls again |
| **Exception Flows** | 5a. OCR error + retriable → status RETRYING, re-queue after delay<br>5b. OCR error + non-retriable → status FAILED<br>5c. Timeout → status RETRYING or FAILED based on retry count |
| **Postconditions** | Job completed or failed, result stored if success |
| **Business Rules** | RULE-L011 to RULE-L015e |
| **MVP Notes** | Tesseract OCR engine. Exponential backoff for retries. |

### UC-L005: Track Job Status

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L005 |
| **Use Case Name** | Track processing status |
| **Actor(s)** | Logged-in User with submitted jobs |
| **User Story** | PR-L008, PR-L009 |
| **Trigger** | User on request status page |
| **Main Flow** | 1. User views request status page<br>2. System displays overall progress (X/N files done)<br>3. System displays individual job statuses<br>4. User refreshes page to update<br>5. All jobs complete → shows "Completed" with result links |
| **Alternative Flows** | 4a. Auto-refresh enabled → page auto-updates every 5s |
| **Exception Flows** | 5a. Some jobs failed → shows "Partial Success: X/N completed, Y failed"<br>5b. All jobs failed → shows "Failed" with error details |
| **Postconditions** | User knows current status |
| **Business Rules** | RULE-L016, RULE-L017 |
| **MVP Notes** | Polling-based only. No real-time push. Simple status display. |

### UC-L006: View and Download Result

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L006 |
| **Use Case Name** | View OCR result and download |
| **Actor(s)** | Logged-in User with completed job |
| **User Story** | PR-L010, PR-L011 |
| **Trigger** | User clicks "View Result" on completed job |
| **Main Flow** | 1. User clicks "View Result"<br>2. System displays extracted text<br>3. Optional: system shows original image side-by-side<br>4. User reviews result<br>5. User clicks download button<br>6. User selects format (TXT or JSON)<br>7. Browser downloads file |
| **Alternative Flows** | 5a. Batch: user downloads all as ZIP |
| **Exception Flows** | 2a. Result expired → error "Result no longer available" |
| **Postconditions** | User has viewed/downloaded result |
| **Business Rules** | RULE-L018, RULE-L019, RULE-L020 |
| **MVP Notes** | TXT and JSON formats only. Shows processing time in metadata. |

### UC-L007: Job Retry (Automatic)

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-L007 |
| **Use Case Name** | Automatic job retry |
| **Actor(s)** | System (automated) |
| **User Story** | PR-L007 |
| **Trigger** | Job fails with retriable error |
| **Main Flow** | 1. Job fails with retriable error (timeout, OCR error)<br>2. System checks retry_count < max_retries<br>3. Job status → RETRYING<br>4. System calculates delay (exponential backoff)<br>5. After delay, job re-enters queue (status QUEUED)<br>6. Worker picks up job, increments retry_count<br>7. Job processes again |
| **Alternative Flows** | 7a. Success after retry → COMPLETED, retry history preserved |
| **Exception Flows** | 2a. retry_count >= max_retries → FAILED with full error history<br>1a. Non-retriable error → FAILED immediately (no retry) |
| **Postconditions** | Job either succeeds after retry or fails permanently |
| **Business Rules** | RULE-L015, RULE-L015b, RULE-L015c, RULE-L015d, RULE-L015e |
| **MVP Notes** | Exponential backoff: 1s, 2s, 4s, 8s... Error history preserved for debugging. |

---

## 5. Glossary & Domain Model

### 5.1. Business Glossary

| Thuật ngữ | Định nghĩa | Ví dụ |
|---|---|---|
| **Request** | Một batch submission chứa nhiều files với cùng config | Request ID: req_abc123 |
| **Job** | Một unit công việc xử lý OCR cho một file | Job ID: job_xyz789 |
| **Worker** | Process xử lý OCR, chạy như separate service | Local worker process |
| **Queue** | Hàng đợi jobs. In-memory hoặc lightweight queue | In-memory queue |
| **Tier** | Mức hạ tầng xử lý. Phase 1 chỉ có Tier 0 (Local) | Tier 0 = Local |
| **Method** | Phương pháp OCR. Phase 1 chỉ có ocr_text_raw | ocr_text_raw |
| **Retry** | Việc xử lý lại job khi gặp lỗi tạm thời | Max 3 retries |
| **Exponential Backoff** | Delay tăng dần giữa các lần retry (1s, 2s, 4s...) | Retry delay |
| **Retriable Error** | Lỗi có thể retry (timeout, OCR engine error) | Timeout error |
| **Non-retriable Error** | Lỗi không thể retry (invalid file, corrupted) | Invalid file format |
| **Partial Success** | Request có một số files thành công, một số thất bại | 4/5 files completed |
| **Retention** | Thời gian lưu trữ file trước khi tự động xóa | 24 hours |

### 5.2. Domain Model (High-Level)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOMAIN MODEL (PHASE 1 LOCAL)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────┐           ┌──────────┐           ┌──────────┐                │
│   │   USER   │───1:N────▶│ REQUEST  │───1:N────▶│   JOB    │                │
│   └──────────┘           └──────────┘           └────┬─────┘                │
│                                                      │                       │
│                                                      │ 1:1 (if completed)    │
│                                                      ▼                       │
│                                                 ┌──────────┐                 │
│                                                 │  RESULT  │                 │
│                                                 └──────────┘                 │
│                                                                               │
│   ┌──────────┐                                                               │
│   │   FILE   │◀──1:1──── JOB (source file)                                  │
│   └──────────┘                                                               │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Entity Details:**

| Entity | Mô tả | Key Business Attributes | Relationships |
|---|---|---|---|
| **User** | Developer/Tester sử dụng hệ thống | email, password_hash, created_at | 1:N Requests |
| **Request** | Một batch submission với nhiều files | id, user_id, status, created_at | N:1 User, 1:N Jobs |
| **Job** | Một file cần xử lý OCR | id, request_id, file_id, status, retry_count, error_history | N:1 Request, 1:1 File, 1:1 Result |
| **File** | File được upload | id, filename, path, size, format, uploaded_at | 1:1 Job |
| **Result** | Kết quả OCR của một job | id, job_id, text, output_path, processing_time | 1:1 Job |

### 5.3. Job State Machine

```
┌───────────────┐
│   SUBMITTED   │
│ (Job created) │
└───────┬───────┘
        │ Auto (immediate)
        ▼
┌───────────────┐◄─────────────────────────┐
│    QUEUED     │                          │
│ (In queue)    │                          │
└───────┬───────┘                          │
        │ Worker picks up                  │
        ▼                                  │
┌───────────────┐                          │
│  PROCESSING   │                          │
│ (OCR running) │                          │
└───────┬───────┘                          │
        │                                  │
   ┌────┴────────────┐                     │
   │                 │                     │
Success           Error                    │
   │                 │                     │
   │          ┌──────┴──────┐              │
   │          │             │              │
   │    retry < max    retry >= max        │
   │          │             │              │
   ▼          ▼             ▼              │
┌──────┐  ┌────────┐    ┌──────┐           │
│DONE  │  │RETRYING│    │FAILED│           │
│      │  │        │    │      │           │
└──────┘  └────┬───┘    └──────┘           │
               │                           │
               └───────────────────────────┘
                    (back to queue)
```

**State Details:**

| State | Mô tả | Triggers Transition To |
|---|---|---|
| SUBMITTED | Job vừa được tạo | QUEUED (auto) |
| QUEUED | Đang chờ worker | PROCESSING |
| PROCESSING | Worker đang xử lý | COMPLETED / RETRYING / FAILED |
| RETRYING | Đang chờ retry | QUEUED (after delay) |
| COMPLETED | Hoàn thành thành công | Terminal |
| FAILED | Thất bại sau max retries | Terminal |

---

## Summary

```
--- SUMMARY HANDOFF (BA Biz → BA Tech) ---
Phase: 1 - Local MVP
Purpose: Technical validation, NOT end-user product
Target Users: Dev Team, QA (internal only)
Features: 6 features (F-L001 to F-L006)
Requirements: 12 product requirements (PR-L001 to PR-L012)
Use Cases: 7 use cases (UC-L001 to UC-L007)
Business Rules: 27 rules (RULE-L001 to RULE-L022 + sub-rules)

Scope:
- 1 OCR Service: ocr_text_raw
- 1 Tier: Local (Tier 0)
- Formats: PNG, JPEG, PDF
- Batch upload: Max 20 files, 50MB total
- Retry mechanism: Max 3 retries, exponential backoff
- Local infrastructure: Filesystem, in-memory queue, SQLite

Success Criteria:
- End-to-end flow works: Batch Upload → OCR → Download
- Job state machine works (including RETRYING)
- Retry mechanism with exponential backoff
- 3 layers separate, can run independently
- 50+ test jobs complete successfully

Key Decisions to Lock:
1. Job lifecycle state machine
2. Data model schema
3. API contract between layers
4. Queue interface (ready for Redis/NATS)
5. Storage interface (ready for S3/R2)
6. Worker interface (ready for scaling)
7. Retry mechanism pattern

--- ✅ PHASE 1 BA BIZ COMPLETE ---
```
