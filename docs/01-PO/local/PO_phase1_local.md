# OCR Platform Phase 1 — Product Specification (Local MVP)

> Tài liệu Product Specification cho Phase 1 - Local MVP
> Version: 1.0 | Status: Draft
> Scope: Chứng minh luồng end-to-end hoạt động trên môi trường local với 1 OCR service

---

## Table of Contents

1. [Context & Objective](#part-1-context--objective)
2. [Target Audience](#part-2-target-audience)
3. [Functional Requirements](#part-3-functional-requirements)
4. [User Experience](#part-4-user-experience)
5. [Success Metrics](#part-5-success-metrics)
6. [Roadmap](#part-6-roadmap)
7. [Constraints](#part-7-constraints)

---

## PART 1: CONTEXT & OBJECTIVE

### 1.1. Problem Statement

Phase 1 Local MVP tập trung giải quyết một vấn đề kỹ thuật cốt lõi:

```
Team phát triển cần CHỨNG MINH luồng OCR end-to-end hoạt động trước khi đầu tư vào infrastructure cloud.
Hậu quả nếu không validate: Rủi ro lớn khi scale, phát hiện lỗi thiết kế muộn, cost cao để sửa.
Hiện tại: Chưa có prototype để validate kiến trúc 3 lớp (Edge → Orchestration → Processing).
```

**Phase 1 không phải sản phẩm cho end-user**, mà là technical validation để:
- Chốt các quyết định kiến trúc cốt lõi
- Validate data flow pattern
- Thiết lập data model
- Chuẩn bị interface cho scale controller

### 1.2. Product Objective

| Trường | Nội dung |
|---|---|
| **What** | Local MVP là một prototype web app cho phép batch upload files (ảnh, PDF), xử lý OCR bằng 1 service (ocr_text_raw), và xem/download kết quả. Chạy hoàn toàn trên máy local. |
| **Why** | Validate kiến trúc 3 lớp và luồng xử lý job trước khi deploy lên cloud. Giảm rủi ro phát hiện lỗi thiết kế ở giai đoạn sau. |
| **How** | Triển khai đầy đủ 3 lớp (Edge, Orchestration, Processing) trên local environment với các thành phần lightweight (in-memory queue, local storage, database emulator). Bao gồm batch processing và retry mechanism. |

### 1.3. Project Scope

| Phạm vi | Nội dung |
|---|---|
| **In Scope (Phase 1)** | • 1 OCR service: `ocr_text_raw` (extract text thuần)<br>• 1 tier: Local (Tier 0)<br>• **Batch upload** (nhiều file hoặc folder: PNG, JPEG, PDF)<br>• Auth đơn giản (email/password, không OAuth)<br>• Job status tracking (polling, không real-time)<br>• Xem/download kết quả (TXT, JSON)<br>• **Retry mechanism** (tối đa 3 lần)<br>• Không billing (miễn phí)<br>• Queue in-memory hoặc lightweight<br>• Storage local (filesystem)<br>• Database emulator (hoặc SQLite) |
| **Out of Scope** | • Multiple OCR services<br>• Multiple tiers (Cloud, Enhanced, etc.)<br>• OAuth login<br>• Billing/Credit system<br>• Real-time notifications (SSE/WebSocket)<br>• Production database<br>• Cloud deployment<br>• Auto-scaling |
| **Deferred to Phase 2** | • Full tier support (Tier 1-4)<br>• Multiple OCR services<br>• OAuth login<br>• Billing system<br>• Real-time notifications<br>• Cloud infrastructure<br>• File Proxy Service |

### 1.4. Architecture Validation Goals

Phase 1 cần validate và "khoá" các quyết định sau:

| Quyết định | Mô tả | Validation criteria |
|---|---|---|
| **Job Lifecycle** | State machine: SUBMITTED → QUEUED → PROCESSING → COMPLETED/FAILED/RETRYING | State transitions hoạt động đúng |
| **Data Flow Pattern** | Client → Edge → Orchestrator → Worker → Edge → Client | File và metadata truyền đúng qua các layer |
| **Data Model** | Schema cho users, requests, jobs, files | Query patterns hoạt động hiệu quả |
| **Layer Separation** | Edge, Orchestration, Processing tách biệt | Các layer có thể deploy độc lập, giao tiếp với nhau qua đầu API |
| **Queue Pattern** | Job dispatch qua queue, worker pull-based | Worker pull và process job thành công |
| **Retry Mechanism** | Exponential backoff, max retries, error classification | Retry hoạt động đúng, không infinite loop |
| **Batch Processing** | Một request chứa nhiều files | Batch upload, partial success handling |
| **Configurable Params** | Timeout, retries, estimated time via env vars | Params có thể thay đổi mà không cần rebuild |
| **Scale Controller Interface** | Interface để bật/tắt worker | Interface sẵn sàng cho auto-scale (Phase 3) |

---

## PART 2: TARGET AUDIENCE

### 2.1. User Personas (Phase 1)

Phase 1 là internal prototype, target audience là team phát triển:

#### Persona 1: Dev — Backend Developer

| Trường | Nội dung |
|---|---|
| **Persona Name** | Dev — Backend Developer |
| **Role / Bối cảnh** | Phát triển và test backend services |
| **Goals** | 1. Validate job processing flow hoạt động<br>2. Test data model và query patterns |
| **Key Expectation** | Luồng job từ submit đến complete hoạt động ổn định |

#### Persona 2: QA — Quality Assurance

| Trường | Nội dung |
|---|---|
| **Persona Name** | QA — Tester |
| **Role / Bối cảnh** | Test chức năng và edge cases |
| **Goals** | 1. Test các happy path và error cases<br>2. Validate data consistency |
| **Key Expectation** | Có thể test full flow trên local mà không cần cloud |

### 2.2. Primary vs. Secondary Users

| Loại | Persona | Vai trò | Ghi chú |
|---|---|---|---|
| **Primary** | Dev Team | Phát triển và validate | Focus chính |
| **Secondary** | QA | Testing | Support testing |
| **Future** | End User | Sử dụng sản phẩm | Phase 2+ |

---

## PART 3: FUNCTIONAL REQUIREMENTS

### 3.1. Feature List

| Feature ID | Module | Tên feature | Mô tả ngắn | Priority | Phase |
|---|---|---|---|---|---|
| **F-L001** | Auth | Simple Authentication | Đăng ký, đăng nhập email/password | Must | Phase 1 |
| **F-L002** | Upload | Batch Upload | Upload nhiều file (PNG, JPEG, PDF) <br> *limit size = 10MB* | Must | Phase 1 |
| **F-L003** | Processing | OCR Processing | Xử lý OCR với service ocr_text_raw | Must | Phase 1 |
| **F-L004** | Tracking | Job Status (Polling) | Xem trạng thái job bằng refresh/polling | Must | Phase 1 |
| **F-L005** | Output | Result Viewing & Download | Xem và download kết quả (TXT, JSON) | Must | Phase 1 |
| **F-L006** | Storage | File Lifecycle | Lưu file local, xoá theo thời gian | Should | Phase 1 |

### 3.2. User Stories & Acceptance Criteria

---

#### Module: Simple Authentication (F-L001)

```
[STORY-L001] (Priority: Must | Phase: 1)

As a developer,
I want to register and login with email/password,
So that I can test the authentication flow.

Acceptance Criteria:
  AC1: Given I am on registration page, When I enter email + password (min 6 chars), Then account is created.
  AC2: Given I enter an existing email, When I submit, Then I see error "Email already exists".
  AC3: Given valid credentials, When I login, Then I am redirected to dashboard.
  AC4: Given invalid credentials, When I login, Then I see error "Invalid credentials".
  AC5: Given I am logged in, When I click logout, Then session is cleared.

Business Rules:
  - RULE-L001: Email must be unique
  - RULE-L002: Password minimum 6 characters (simplified for MVP)
  - RULE-L003: Session stored in cookie/localStorage

Notes:
  - Không cần email verification
  - Không cần password reset
  - Không cần OAuth
  - Password hash với bcrypt
```

---

#### Module: Batch Upload (F-L002)

```
[STORY-L002] (Priority: Must | Phase: 1)

As a user,
I want to upload multiple files or a folder,
So that I can process them with OCR in batch.

Acceptance Criteria:
  AC1: Given I select valid files (PNG, JPEG, PDF) via file picker, When upload completes, Then all files are saved to local storage.
  AC2: Given I select a folder, When upload completes, Then all valid files in folder are saved.
  AC3: Given total batch size > 50MB, When I try to upload, Then I see error "Batch too large. Maximum 50MB total."
  AC4: Given single file > 10MB, When I try to upload, Then I see error "File too large. Maximum 10MB per file."
  AC5: Given unsupported format (MP4, TIFF, etc.), When I try to upload, Then invalid files are skipped with warning.
  AC6: Given some files are corrupted, When I try to upload, Then corrupted files are skipped with warning, valid files proceed.
  AC7: Given upload succeeds, Then I see file list with previews and "Process All" button.
  AC8: Given I click "Process All", Then a single request is created containing all files.

Business Rules:
  - RULE-L004: Max file size per file: 10MB
  - RULE-L004b: Max batch size: 50MB total
  - RULE-L004c: Max files per batch: 20 files
  - RULE-L005: Supported formats: PNG, JPEG, PDF
  - RULE-L006: File stored in local filesystem (configurable path)
  - RULE-L007: File validation before storing (skip invalid, continue with valid)

Notes:
  - Support drag-and-drop for files/folder
  - PDF files: mỗi page = 1 unit để tính toán
  - File path: ./storage/uploads/{user_id}/{request_id}/{file_id}
  - Một request chứa nhiều files, tất cả dùng chung config
```

---

#### Module: OCR Processing (F-L003)

```
[STORY-L003] (Priority: Must | Phase: 1)

As a user,
I want to process my uploaded image with OCR,
So that I can extract text from it.

Acceptance Criteria:
  AC1: Given I have uploaded a file, When I click "Process", Then job is created with status SUBMITTED.
  AC2: Given job is created, Then job is automatically queued (status → QUEUED).
  AC3: Given worker picks up job, Then status changes to PROCESSING.
  AC4: Given OCR completes successfully, Then status changes to COMPLETED and result is stored.
  AC5: Given OCR fails, Then status changes to FAILED with error message.

Business Rules:
  - RULE-L008: Only ocr_text_raw service available
  - RULE-L009: Only Tier 0 (Local) available
  - RULE-L010: Job enters queue immediately after submit
  - RULE-L011: Worker polls queue for new jobs

Notes:
  - Không chọn method (fixed: ocr_text_raw)
  - Không chọn tier (fixed: Local)
  - Không chọn output format (fixed: txt)
  - Không billing check
```

```
[STORY-L004] (Priority: Must | Phase: 1)

As a worker service,
I want to pull jobs from queue and process them,
So that OCR results are generated.

Acceptance Criteria:
  AC1: Given jobs are in queue, When worker polls, Then worker receives oldest QUEUED job.
  AC2: Given worker receives job, Then job status changes to PROCESSING.
  AC3: Given worker completes OCR, Then result is stored and job status → COMPLETED.
  AC4: Given worker encounters error AND retry_count < max_retries, Then job status → RETRYING and re-queued.
  AC5: Given worker encounters error AND retry_count >= max_retries, Then job status → FAILED with error details.
  AC6: Given no jobs in queue, When worker polls, Then worker waits and polls again.

Business Rules:
  - RULE-L012: Worker là pull-based (không push)
  - RULE-L013: Một worker xử lý một job tại một thời điểm
  - RULE-L014: Worker timeout: configurable, default = TIMEOUT_SECONDS (env var)
  - RULE-L015: Max retries: configurable, default = MAX_RETRIES (env var, mặc định 3)
  - RULE-L015b: Retry delay: exponential backoff (1s, 2s, 4s, ...)

Notes:
  - Worker chạy như separate process
  - Worker truy cập trực tiếp local storage (không qua File Proxy)
  - OCR engine: Tesseract hoặc tương đương
  - Mỗi retry tăng retry_count trong job metadata
```

```
[STORY-L004b] (Priority: Must | Phase: 1)

As a system,
I want to automatically retry failed jobs,
So that transient errors don't cause permanent failures.

Acceptance Criteria:
  AC1: Given job fails with retriable error, When retry_count < max_retries, Then job is re-queued with status RETRYING.
  AC2: Given job is RETRYING, When worker picks it up, Then job status → PROCESSING and retry_count increments.
  AC3: Given job succeeds after retry, Then status → COMPLETED (retry history preserved in metadata).
  AC4: Given job fails after max retries, Then status → FAILED with full error history.
  AC5: Given job has non-retriable error (e.g., invalid file), Then status → FAILED immediately (no retry).

Business Rules:
  - RULE-L015c: Retriable errors: timeout, OCR engine error, temporary failures
  - RULE-L015d: Non-retriable errors: invalid file format, file not found, corrupted file
  - RULE-L015e: Retry metadata stored: retry_count, error_history[], last_error

Notes:
  - Exponential backoff giúp tránh overload khi có lỗi hệ thống
  - Error history giúp debug và improve
```

---

#### Module: Job Status Tracking (F-L004)

```
[STORY-L005] (Priority: Must | Phase: 1)

As a user,
I want to see the status of my processing job,
So that I know when my result is ready.

Acceptance Criteria:
  AC1: Given job is submitted, When I view job page, Then I see current status.
  AC2: Given I refresh the page, Then status is updated if changed.
  AC3: Given job status is COMPLETED, Then I see link to view/download result.
  AC4: Given job status is FAILED, Then I see error message.
  AC5: Given job is PROCESSING, Then I see spinner/loading indicator.

Business Rules:
  - RULE-L016: Status cập nhật qua manual refresh (polling)
  - RULE-L017: Không real-time push (SSE/WebSocket) trong Phase 1

Notes:
  - Có thể thêm auto-refresh mỗi 5s (optional)
  - UI đơn giản: status text + timestamp
```

---

#### Module: Result Viewing & Download (F-L005)

```
[STORY-L006] (Priority: Must | Phase: 1)

As a user,
I want to view and download OCR result,
So that I can use the extracted text.

Acceptance Criteria:
  AC1: Given job is COMPLETED, When I click "View Result", Then I see extracted text.
  AC2: Given I view result, Then I can see original image side-by-side (optional).
  AC3: Given I click "Download TXT", Then plain text file downloads.
  AC4: Given I click "Download JSON", Then JSON file downloads with text + metadata.
  AC5: Given result page, Then I see processing time and service info.

Business Rules:
  - RULE-L018: Output formats: TXT, JSON
  - RULE-L019: JSON includes: text, filename, processing_time, service_version

Notes:
  - Không DOCX, CSV, XLSX (Phase 2)
  - Result stored in ./storage/results/{job_id}/
```

---

#### Module: File Lifecycle (F-L006)

```
[STORY-L007] (Priority: Should | Phase: 1)

As a system,
I want to delete old files after retention period,
So that storage doesn't grow indefinitely.

Acceptance Criteria:
  AC1: Given file retention is set (default 24h), When retention expires, Then file is deleted.
  AC2: Given job result, When retention expires, Then result file is also deleted.
  AC3: Given file is deleted, Then job metadata still exists (for history).
  AC4: Given cleanup runs, Then log shows which files were deleted.

Business Rules:
  - RULE-L020: Default retention: 24 hours
  - RULE-L021: Cleanup job runs every hour (cron/scheduled task)
  - RULE-L022: Metadata retained even after file deletion

Notes:
  - Có thể implement bằng simple cleanup script
  - Configurable retention via environment variable
```

---

### 3.3. Business Rules Summary

| Rule ID | Tên quy tắc | Mô tả | Story |
|---|---|---|---|
| **RULE-L001** | Unique Email | Email phải unique | STORY-L001 |
| **RULE-L002** | Simple Password | Min 6 characters | STORY-L001 |
| **RULE-L003** | Session Storage | Cookie/localStorage | STORY-L001 |
| **RULE-L004** | Max File Size | 10MB per file | STORY-L002 |
| **RULE-L004b** | Max Batch Size | 50MB total | STORY-L002 |
| **RULE-L004c** | Max Files Per Batch | 20 files | STORY-L002 |
| **RULE-L005** | Supported Formats | PNG, JPEG, PDF | STORY-L002 |
| **RULE-L006** | Local Storage | Filesystem storage | STORY-L002 |
| **RULE-L007** | File Validation | Validate before store, skip invalid | STORY-L002 |
| **RULE-L008** | Single Service | ocr_text_raw only | STORY-L003 |
| **RULE-L009** | Single Tier | Tier 0 (Local) only | STORY-L003 |
| **RULE-L010** | Auto Queue | Immediate queue after submit | STORY-L003 |
| **RULE-L011** | Worker Pull | Worker polls queue | STORY-L003 |
| **RULE-L012** | Pull-based Worker | Worker pulls, not pushed | STORY-L004 |
| **RULE-L013** | Single Job Processing | One job at a time | STORY-L004 |
| **RULE-L014** | Job Timeout | Configurable (TIMEOUT_SECONDS) | STORY-L004 |
| **RULE-L015** | Max Retries | Configurable (MAX_RETRIES, default 3) | STORY-L004, L004b |
| **RULE-L015b** | Retry Delay | Exponential backoff | STORY-L004b |
| **RULE-L015c** | Retriable Errors | Timeout, OCR engine error, temp failures | STORY-L004b |
| **RULE-L015d** | Non-retriable Errors | Invalid file, not found, corrupted | STORY-L004b |
| **RULE-L015e** | Retry Metadata | Store retry_count, error_history | STORY-L004b |
| **RULE-L016** | Manual Refresh | Polling-based status | STORY-L005 |
| **RULE-L017** | No Real-time | No SSE/WebSocket | STORY-L005 |
| **RULE-L018** | Output Formats | TXT, JSON | STORY-L006 |
| **RULE-L019** | JSON Metadata | Include processing info | STORY-L006 |
| **RULE-L020** | Default Retention | 24 hours | STORY-L007 |
| **RULE-L021** | Cleanup Schedule | Every hour | STORY-L007 |
| **RULE-L022** | Metadata Retention | Keep metadata after file delete | STORY-L007 |

### 3.4. Configurable Parameters

Các tham số sau được cấu hình qua environment variables hoặc config file:

| Parameter | Env Variable | Default | Mô tả |
|---|---|---|---|
| **Job Timeout** | `JOB_TIMEOUT_SECONDS` | 300 (5 min) | Thời gian tối đa cho 1 job trước khi timeout |
| **Max Retries** | `MAX_RETRIES` | 3 | Số lần retry tối đa khi job fail |
| **Retry Base Delay** | `RETRY_BASE_DELAY_MS` | 1000 | Delay cơ sở cho exponential backoff (ms) |
| **Estimated Time Factor** | `ESTIMATE_TIME_FACTOR` | 1.0 | Hệ số nhân cho estimated time (tuỳ infra) |
| **File Retention** | `FILE_RETENTION_HOURS` | 24 | Thời gian giữ file trước khi xoá |
| **Max File Size** | `MAX_FILE_SIZE_MB` | 10 | Kích thước tối đa mỗi file (MB) |
| **Max Batch Size** | `MAX_BATCH_SIZE_MB` | 50 | Kích thước tối đa mỗi batch (MB) |
| **Max Files Per Batch** | `MAX_FILES_PER_BATCH` | 20 | Số file tối đa mỗi batch |
| **Worker Poll Interval** | `WORKER_POLL_INTERVAL_MS` | 1000 | Khoảng thời gian worker poll queue |

**Estimated Processing Time Formula:**

```
estimated_time = base_time × page_count × ESTIMATE_TIME_FACTOR

Trong đó:
- base_time: Thời gian cơ sở cho 1 page (từ OCR service config)
- page_count: Số trang (images = 1, PDF = số trang)
- ESTIMATE_TIME_FACTOR: Hệ số phụ thuộc infrastructure (local = 1.0, slow machine = 2.0, etc.)
```

**OCR Service Config (cho mỗi service):**

| Config | Mô tả | Ví dụ |
|---|---|---|
| `base_time_per_page` | Thời gian xử lý 1 page (seconds) | 5s cho ocr_text_raw |
| `supported_formats` | Formats được hỗ trợ | ["png", "jpeg", "pdf"] |
| `max_page_count` | Số trang tối đa | 100 |

---

## PART 4: USER EXPERIENCE

### 4.1. User Flows

#### Flow 1: Batch Upload & Process (Happy Path)

```
Flow Name: Batch Upload Complete Flow
Actor: Developer/Tester
Trigger: User opens application
Precondition: Application running on localhost

HAPPY PATH:
  1. User navigates to localhost:3000 (or configured port)
  2. User sees Login page → clicks "Register"
  3. User enters email + password → account created
  4. User redirected to Dashboard (empty state)
  5. User clicks "Upload" → file picker opens
  6. User selects multiple files or folder (PNG, JPEG, PDF)
  7. Files upload with progress bar → all files validated
  8. User sees file list with previews and total count
  9. User can remove individual files from batch
  10. User clicks "Process All"
  11. Request created → user sees Request Status page
  12. User refreshes page → sees "Processing... (3/5 files done)"
  13. User refreshes again → sees "Completed"
  14. User clicks "View Results" → sees results for all files
  15. User downloads individual results or all as ZIP
  16. Flow complete

ALTERNATIVE PATHS:
  - At step 6: Some files invalid → warning shown, valid files continue
  - At step 6: Single file too large → file skipped with warning
  - At step 12: Some jobs fail → partial success shown

ERROR / EDGE CASES:
  - Worker not running → jobs stay QUEUED indefinitely
  - All files invalid → error, cannot process
  - Batch too large → error, reduce files

BUSINESS RULES APPLIED: RULE-L001 to RULE-L022
```

#### Flow 2: Job Retry & Failure

```
Flow Name: Job Retry and Failure Handling
Actor: Developer/Tester
Trigger: OCR processing encounters retriable error
Precondition: File uploaded and job submitted

RETRY FLOW:
  1. User submits job → status SUBMITTED
  2. Job moves to QUEUED
  3. Worker picks up job → status PROCESSING
  4. OCR encounters retriable error (timeout, temp failure)
  5. Job status → RETRYING (retry_count = 1)
  6. User refreshes page → sees "Retrying... (attempt 1/3)"
  7. After delay, job re-queued → QUEUED
  8. Worker picks up again → PROCESSING
  9. If success → COMPLETED
  10. If fail again → repeat retry up to max_retries

FAILURE FLOW (after max retries):
  1. Job fails 3 times (max_retries reached)
  2. Job status → FAILED with full error history
  3. User sees "Failed after 3 attempts: [last error]"
  4. User can view error history for debugging
  5. User can try uploading different file

NON-RETRIABLE FAILURE:
  1. OCR encounters non-retriable error (invalid file, corrupted)
  2. Job immediately → FAILED (no retry)
  3. User sees "Failed: Invalid file format"

ERROR DETAILS TO SHOW:
  - "OCR timeout: Processing took too long (attempt 2/3)"
  - "Retrying in 4 seconds..."
  - "Failed after 3 attempts: [error details]"
  - "Error history: [list of all errors]"

BUSINESS RULES APPLIED: RULE-L014, RULE-L015, RULE-L015b-e
```

#### Flow 3: Partial Success (Batch)

```
Flow Name: Batch Partial Success
Actor: Developer/Tester
Trigger: Some files in batch fail
Precondition: Multiple files uploaded

FLOW:
  1. User uploads 5 files → creates request
  2. Jobs process: 3 succeed, 1 retrying, 1 failed
  3. User sees: "Processing... 3/5 completed, 1 retrying, 1 failed"
  4. After retries complete: 4/5 succeeded, 1/5 failed
  5. User sees: "Partial Success: 4/5 files completed"
  6. User can download successful results
  7. User can view error details for failed file
  8. User can retry failed file manually (re-upload)

BUSINESS RULES APPLIED: RULE-L004c, RULE-L015
```

### 4.2. Screen / Page Inventory

| Screen ID | Tên màn hình | Mục đích | Components | Ghi chú |
|---|---|---|---|---|
| **SCR-L001** | Login | Sign in | Email input, password input, login button, register link | Minimal design |
| **SCR-L002** | Register | Create account | Email input, password input, confirm password, register button | Minimal design |
| **SCR-L003** | Dashboard | Home | User info, recent requests list, upload button | Empty state cho user mới |
| **SCR-L004** | Batch Upload | File selection | Drag-drop zone, file picker (multi), folder picker, file list, remove buttons, process all button | Support multi-file/folder |
| **SCR-L005** | Request Status | Track request | Overall progress, file list with individual status, retry info, timestamps | Shows batch progress |
| **SCR-L006** | Result Viewer | View output | File selector, original image, extracted text, download buttons | Navigate between files |
| **SCR-L007** | Request History | Past requests | Request list with status, file count, click to detail | Simple table |
| **SCR-L008** | Error Details | View errors | Error message, retry history, error timeline | For debugging |

### 4.3. Job State Machine

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
Success         Error                      │
   │                 │                     │
   │          ┌──────┴──────┐              │
   │          │             │              │
   │    retry < max    retry >= max        │
   │          │             │              │
   ▼          ▼             ▼              │
┌──────┐  ┌────────┐    ┌──────┐           │
│DONE  │  │RETRYING│───►│FAILED│           │
│      │  │        │    │      │           │
└──────┘  └────┬───┘    └──────┘           │
               │                           │
               └───────────────────────────┘
                    (back to queue)
```

**State Details:**

| State | Mô tả | Transition to |
|---|---|---|
| SUBMITTED | Job vừa được tạo | QUEUED (auto) |
| QUEUED | Đang chờ worker | PROCESSING |
| PROCESSING | Worker đang xử lý | COMPLETED / RETRYING / FAILED |
| RETRYING | Đang chờ retry | QUEUED (after delay) |
| COMPLETED | Hoàn thành thành công | Terminal |
| FAILED | Thất bại sau max retries | Terminal |

**Transition Details:**

| From | To | Trigger | Condition |
|---|---|---|---|
| SUBMITTED | QUEUED | Auto | - |
| QUEUED | PROCESSING | Worker picks | - |
| PROCESSING | COMPLETED | Success | - |
| PROCESSING | RETRYING | Error | retry_count < max_retries AND retriable_error |
| PROCESSING | FAILED | Error | retry_count >= max_retries OR non_retriable_error |
| RETRYING | QUEUED | Delay elapsed | exponential backoff |

**Note:** Phase 1 không có CANCELLED (defer to Phase 2 khi có billing)

---

## PART 5: SUCCESS METRICS

### 5.1. Phase 1 Success Criteria

Phase 1 là technical validation, không đo user metrics. Success criteria:

| Tiêu chí | Mục tiêu | Cách kiểm tra |
|---|---|---|
| **End-to-end flow** | Upload → Process → Download hoạt động | Manual test 20 files |
| **Job lifecycle** | All states transition correctly | Automated test |
| **Layer separation** | 3 layers chạy độc lập | Deploy từng layer riêng |
| **Data integrity** | File không corrupt qua các layers | Hash comparison |
| **Performance** | Job complete < 60s cho file 1MB | Timing test |
| **Error handling** | Errors propagate correctly | Error injection test |
| **Storage lifecycle** | Files deleted after retention | Wait 24h + verify |

### 5.2. Technical Metrics

| Metric | Định nghĩa | Target |
|---|---|---|
| **Job Success Rate** | % jobs COMPLETED / total (including after retry) | > 90% |
| **First-attempt Success Rate** | % jobs COMPLETED without retry | > 80% |
| **Retry Success Rate** | % retried jobs that eventually succeed | > 50% |
| **Avg Processing Time** | Time from SUBMITTED to COMPLETED | < 60 seconds |
| **Avg Retry Count** | Average retries for successful jobs | < 1.5 |
| **Queue Latency** | Time in QUEUED state | < 5 seconds |
| **Error Rate** | % jobs FAILED (after all retries) | < 10% |
| **Batch Success Rate** | % requests with all files completed | > 85% |
| **Storage Usage** | Disk space used | Track, no target |

### 5.3. Validation Checklist

Trước khi chuyển sang Phase 2, phải hoàn thành:

- [ ] All stories pass acceptance criteria
- [ ] Job state machine hoạt động đúng (including RETRYING state)
- [ ] 3 layers có thể start/stop độc lập
- [ ] Data model schema finalized
- [ ] Queue interface defined (ready for real queue)
- [ ] Storage interface defined (ready for cloud storage)
- [ ] Worker interface defined (ready for scaling)
- [ ] Retry mechanism hoạt động với exponential backoff
- [ ] Batch upload hoạt động với partial success handling
- [ ] Configurable params hoạt động qua env vars
- [ ] 50 test jobs completed successfully (including retry scenarios)
- [ ] Edge cases documented

---

## PART 6: ROADMAP

### 6.1. Phase 1 Timeline

| Tuần | Milestone | Deliverables |
|---|---|---|
| **W1** | Setup & Architecture | Project setup, folder structure, database schema, interfaces |
| **W2** | Backend Core | Auth endpoints, file upload, job creation |
| **W3** | Worker & Queue | Queue implementation, worker service, OCR integration |
| **W4** | Frontend | UI pages (Login, Dashboard, Upload, Status, Result) |
| **W5** | Integration & Testing | End-to-end integration, testing, bug fixes |
| **W6** | Polish & Handoff | Documentation, cleanup, Phase 2 prep |

### 6.2. Phase 1 Deliverables

| Deliverable | Mô tả | Owner |
|---|---|---|
| **Web App** | Frontend SPA (React/Vue/etc.) | Frontend dev |
| **Edge Service** | API server + static hosting | Backend dev |
| **Orchestrator** | Job management, queue | Backend dev |
| **Worker** | OCR processing service | Backend/ML dev |
| **Database** | Schema + emulator setup | Backend dev |
| **Documentation** | Setup guide, API docs | All |

### 6.3. Phase 2 Preview

Sau Phase 1, Phase 2 sẽ mở rộng:

| Area | Phase 1 | Phase 2 |
|---|---|---|
| **OCR Services** | 1 (ocr_text_raw) | 4 (thêm table, formatted, handwriting) |
| **Tiers** | 1 (Local) | 2+ (thêm Cloud tiers) |
| **Upload** | Batch (PNG, JPEG, PDF) | + TIFF, BMP, WEBP |
| **Auth** | Email/password | + OAuth (Google, GitHub) |
| **Status** | Polling | Real-time (SSE) |
| **Billing** | None | Credit system |
| **Storage** | Local | Cloud (R2/S3) |
| **Queue** | In-memory | Production queue (Redis/etc.) |
| **Database** | Emulator | Production DB |
| **Retry** | Basic (exponential backoff) | + Dead letter queue, alerts |

---

## PART 7: CONSTRAINTS

### 7.1. Technical Constraints

| Constraint | Mô tả | Ảnh hưởng |
|---|---|---|
| **Local only** | Không cloud services | Tất cả chạy trên máy dev |
| **Single worker** | 1 worker instance | Không parallel processing |
| **In-memory queue** | Queue mất data khi restart | Dev/test only |
| **Local storage** | Filesystem storage | Không cloud backup |
| **Database emulator** | SQLite hoặc in-memory | Không persist across sessions (optional) |
| **No TLS** | HTTP only trên localhost | Chỉ chạy local |

### 7.2. Simplified Components

| Component | Full Version | Phase 1 Version |
|---|---|---|
| **Queue** | Redis/RabbitMQ/NATS | In-memory queue hoặc SQLite |
| **Storage** | S3/R2 | Local filesystem |
| **Database** | Firestore/PostgreSQL | SQLite hoặc JSON files |
| **Auth** | OAuth + Session | Simple email/password |
| **Notifications** | SSE real-time | Manual refresh |
| **File Proxy** | Dedicated service | Direct access |

### 7.3. Development Requirements

| Requirement | Detail |
|---|---|
| **OS** | Windows, macOS, hoặc Linux |
| **Runtime** | Node.js 18+ (hoặc Python 3.10+ nếu chọn) |
| **OCR Engine** | Tesseract 5.x installed locally |
| **Storage** | 1GB+ disk space |
| **Memory** | 4GB+ RAM |
| **Ports** | 3000 (web), 3001 (API), 3002 (worker) - configurable |

### 7.4. Assumptions

| # | Giả định | Nếu sai thì? | Validation |
|---|---|---|---|
| A-L01 | Tesseract đủ tốt cho text extraction | Thay engine khác | Test với 50+ images |
| A-L02 | In-memory queue đủ cho dev/test | Dùng SQLite queue | Test với 100 jobs |
| A-L03 | Single worker đủ cho testing | Parallel workers later | Phase 2 |
| A-L04 | Local storage đủ cho testing | Mount thêm disk | Monitor usage |

### 7.5. Risks

| Risk | Xác suất | Tác động | Mitigation |
|---|---|---|---|
| Tesseract accuracy thấp | Medium | Kết quả không tốt | Chấp nhận cho MVP, improve Phase 2 |
| Worker crash | Medium | Job stuck | Manual restart, add health check |
| Storage full | Low | Upload fails | Monitor disk, warn at 80% |
| Performance slow | Low | Bad dev experience | Optimize later |

---

## Summary

### Scope Summary
- **6 features** (F-L001 to F-L006)
- **8 user stories** (STORY-L001 to STORY-L007, L004b)
- **8 screens** (SCR-L001 to SCR-L008)
- **27 business rules** (RULE-L001 to RULE-L022 + L004b,c + L015b-e)

### Phase 1 Focus
- **1 OCR Service:** ocr_text_raw
- **1 Tier:** Local (Tier 0)
- **Formats:** PNG, JPEG, PDF
- **Batch upload:** Multi-file và folder support
- **Retry mechanism:** Configurable max retries với exponential backoff
- **Configurable params:** Timeout, retries, estimated time factor
- **Local infrastructure:** Filesystem, in-memory queue, SQLite

### Success Criteria
- End-to-end flow hoạt động: Batch Upload → OCR → Download
- Job state machine hoạt động đúng (including RETRYING)
- Retry mechanism hoạt động với exponential backoff
- 3 layers tách biệt, có thể chạy độc lập
- 50+ test jobs hoàn thành thành công
- Partial success handling cho batch

### Key Decisions to Lock
1. Job lifecycle state machine (with RETRYING state)
2. Data model schema
3. API contract giữa các layers
4. Queue interface (ready for Redis/NATS)
5. Storage interface (ready for S3/R2)
6. Worker interface (ready for scaling)
7. Configurable parameters interface
8. Retry mechanism pattern

### Configurable Parameters
- `JOB_TIMEOUT_SECONDS` - Job timeout
- `MAX_RETRIES` - Max retry attempts
- `ESTIMATE_TIME_FACTOR` - Infrastructure-dependent timing factor
- `MAX_FILE_SIZE_MB`, `MAX_BATCH_SIZE_MB`, `MAX_FILES_PER_BATCH`

### Next Steps
1. Setup project structure
2. Define API contracts (OpenAPI)
3. Implement core backend với configurable params
4. Implement worker service với retry logic
5. Implement frontend với batch upload
6. Integration testing (including retry scenarios)
7. Documentation

---

```
--- SUMMARY HANDOFF (PO → Dev Team) ---
Phase: 1 - Local MVP
Scope: 1 OCR service (ocr_text_raw), 1 tier (Local), batch upload (PNG, JPEG, PDF)
Stories: STORY-L001 to STORY-L007, STORY-L004b
Rules: RULE-L001 to RULE-L022, plus retry rules (L015b-e)
Screens: 8 screens (including batch upload, error details)
Timeline: 6 weeks
Features: Batch upload, Retry mechanism, Configurable params
Goal: Validate end-to-end flow và lock architectural decisions
Not included: Billing, OAuth, real-time notifications, cloud deployment
--- END PHASE 1 SPEC ---
```
