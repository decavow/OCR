# OCR Platform — Technical Business Analysis

> Tài liệu phân tích kỹ thuật nghiệp vụ cho OCR Platform
> Version: 1.0 | Status: Draft
> References: `01-PO/PO_product_spec.md`, `02-BA/BA_business_analysis.md`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Functional Requirements Specification](#2-functional-requirements-specification)
3. [System Architecture & Design](#3-system-architecture--design)
4. [Data Dictionary & Schema Design](#4-data-dictionary--schema-design)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Test Strategy](#6-test-strategy)
7. [UI-Logic Specification](#7-ui-logic-specification)

---

## 1. System Overview

### 1.1. System Purpose & Scope

OCR Platform là hệ thống web cho phép người dùng upload tài liệu (ảnh, PDF), chọn phương pháp và mức hạ tầng xử lý OCR, và nhận kết quả structured output. Hệ thống sử dụng mô hình pre-paid credit để thanh toán.

**System Boundaries:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM CONTEXT                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   [External Actors]                        [OCR Platform System]             │
│                                                                               │
│   ┌──────────────┐                    ┌──────────────────────────────┐       │
│   │  End Users   │◄──────────────────▶│                              │       │
│   │  (Web UI)    │   HTTP/HTTPS       │                              │       │
│   └──────────────┘                    │                              │       │
│                                       │                              │       │
│   ┌──────────────┐                    │      OCR Platform           │       │
│   │   Google     │◄──────────────────▶│                              │       │
│   │   OAuth      │   OAuth 2.0        │   - Web Frontend             │       │
│   └──────────────┘                    │   - API Backend              │       │
│                                       │   - Orchestrator             │       │
│   ┌──────────────┐                    │   - Workers                  │       │
│   │   GitHub     │◄──────────────────▶│   - Storage                  │       │
│   │   OAuth      │   OAuth 2.0        │   - Database                 │       │
│   └──────────────┘                    │                              │       │
│                                       │                              │       │
│   ┌──────────────┐                    │                              │       │
│   │   Stripe     │◄──────────────────▶│                              │       │
│   │   Payment    │   REST API         │                              │       │
│   └──────────────┘                    └──────────────────────────────┘       │
│                                                     ▲                        │
│   ┌──────────────┐                                  │                        │
│   │  GPU Cloud   │◄─────────────────────────────────┘                        │
│   │ (Vast.ai,    │   Worker Management API                                   │
│   │  RunPod)     │                                                           │
│   └──────────────┘                                                           │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2. Modules / Services Chính

| Module | Trách nhiệm | Layer |
|---|---|---|
| **Web Frontend** | Giao diện người dùng, SPA | Edge (Cloudflare Pages) |
| **API Gateway** | Routing, rate limiting, auth | Edge (Cloudflare Workers) |
| **Auth Service** | Xác thực, OAuth, session | Orchestration (GCP) |
| **Upload Service** | Presigned URL, file validation | Edge + Orchestration |
| **Job Service** | Job lifecycle, queue management | Orchestration (GCP) |
| **Billing Service** | Credit management, Stripe integration | Orchestration (GCP) |
| **Notification Service** | In-app notifications, SSE | Orchestration (GCP) |
| **Worker Manager** | Worker provisioning, heartbeat | Orchestration (GCP) |
| **OCR Worker** | OCR processing (Tesseract, etc.) | Processing (GPU) |
| **Storage** | File storage, lifecycle | Edge (Cloudflare R2) |
| **Database** | Metadata, state | Orchestration (Firestore) |

---

## 2. Functional Requirements Specification

### 2.1. FR-001: User Authentication

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-001 |
| **Module** | Auth Service |
| **Requirement** | Hệ thống cho phép người dùng đăng ký và đăng nhập bằng email/password hoặc OAuth (Google, GitHub) |
| **Input** | Email, password (email flow) hoặc OAuth code (OAuth flow) |
| **Processing Logic** | 1. Validate email format (RFC 5322)<br>2. Validate password policy (min 8 chars, 1 upper, 1 number)<br>3. Check email uniqueness (registration)<br>4. Hash password (bcrypt, cost 12)<br>5. Create user record<br>6. Generate JWT session token (1h expiry, refresh token 30d) |
| **Output** | JWT token pair (access + refresh), user profile |
| **Business Rules** | RULE-001, RULE-002, RULE-003, RULE-004, RULE-005, RULE-006 |
| **Acceptance Criteria** | See STORY-001, STORY-002, STORY-003 in PO spec |
| **Priority** | Must |
| **Trace to BR** | BR-001 (User Registration) |

### 2.2. FR-002: File Upload

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-002 |
| **Module** | Upload Service |
| **Requirement** | Hệ thống cho phép upload file ảnh/PDF với validation ngay lập tức |
| **Input** | File binary (multipart upload hoặc presigned URL) |
| **Processing Logic** | 1. Client requests presigned upload URL<br>2. Server generates presigned URL (15 min expiry)<br>3. Client uploads directly to R2<br>4. Server receives upload complete webhook<br>5. Validate: MIME type, magic bytes, file size (≤50MB), PDF page count (≤100)<br>6. Generate thumbnail/preview<br>7. Store file metadata |
| **Output** | File ID, preview URL, validation status |
| **Business Rules** | RULE-007, RULE-008, RULE-009, RULE-010 |
| **Acceptance Criteria** | See STORY-004, STORY-005 in PO spec |
| **Priority** | Must |
| **Trace to BR** | BR-002 (File Upload) |

**Decision Table: File Validation**

| MIME Type | Extension | Magic Bytes | Size ≤ 50MB | PDF Pages ≤ 100 | → Result |
|---|---|---|---|---|---|
| image/* | .png/.jpg/... | Valid image | Y | N/A | Accept |
| image/* | .png/.jpg/... | Valid image | N | N/A | Reject: "File too large" |
| application/pdf | .pdf | %PDF | Y | Y | Accept |
| application/pdf | .pdf | %PDF | Y | N | Reject: "Too many pages" |
| application/pdf | .pdf | %PDF | N | Y | Reject: "File too large" |
| other | other | other | any | any | Reject: "Unsupported format" |
| any | any | Invalid | any | any | Reject: "File corrupted" |

### 2.3. FR-003: OCR Job Submission

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-003 |
| **Module** | Job Service |
| **Requirement** | Hệ thống cho phép submit job OCR với method và tier đã chọn |
| **Input** | file_id, method, tier, retention_days |
| **Processing Logic** | 1. Validate file exists and belongs to user<br>2. Calculate credit cost: base_price(method) × tier_mult × pages<br>3. Check credit balance ≥ cost<br>4. START TRANSACTION<br>5. Hold credit (create hold transaction)<br>6. Create job record (status: SUBMITTED)<br>7. COMMIT TRANSACTION<br>8. Push job to validation queue<br>9. Return job_id |
| **Output** | job_id, estimated_time |
| **Business Rules** | RULE-015, RULE-016, RULE-017, RULE-019, RULE-020 |
| **Acceptance Criteria** | See STORY-006, STORY-007, STORY-008 in PO spec |
| **Priority** | Must |
| **Trace to BR** | BR-003 (OCR Processing) |

### 2.4. FR-004: Job Status Tracking

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-004 |
| **Module** | Job Service, Notification Service |
| **Requirement** | Hệ thống cung cấp real-time status updates cho jobs |
| **Input** | job_id, user_id (for authorization) |
| **Processing Logic** | 1. Verify job belongs to user<br>2. Establish SSE connection<br>3. Subscribe to job status changes (Firestore listener)<br>4. On status change: push to SSE stream<br>5. Include: status, timestamp, queue_position (if QUEUED), progress (if PROCESSING)<br>6. On COMPLETED: include result_url<br>7. On FAILED: include error_reason, refund_confirmation |
| **Output** | SSE stream with status events |
| **Business Rules** | RULE-021, RULE-022, RULE-023 |
| **Acceptance Criteria** | See STORY-009 in PO spec |
| **Priority** | Must |
| **Trace to BR** | BR-004 (Status Tracking) |

### 2.5. FR-005: OCR Processing (Worker)

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-005 |
| **Module** | OCR Worker |
| **Requirement** | Worker xử lý OCR job và upload kết quả |
| **Input** | Job payload from queue (job_id, file_url, method, config) |
| **Processing Logic** | 1. Pull job from tier-specific queue<br>2. Download file from presigned URL<br>3. Select OCR engine based on method<br>4. Process OCR:<br>&nbsp;&nbsp;- ocr_simple: Tesseract → plain text<br>&nbsp;&nbsp;- ocr_table: Table detection → JSON + CSV<br>&nbsp;&nbsp;- ocr_code: Code-aware OCR → Markdown<br>5. Calculate confidence scores<br>6. Upload result to R2<br>7. Update job status to COMPLETED<br>8. Send heartbeat throughout<br>9. Delete local files |
| **Output** | Result file in R2, job status update |
| **Business Rules** | RULE-016, RULE-037, RULE-038 |
| **Acceptance Criteria** | Result accuracy ≥ 95% for standard documents |
| **Priority** | Must |
| **Trace to BR** | BR-003 (OCR Processing) |

### 2.6. FR-006: Credit Management

| Trường | Nội dung |
|---|---|
| **FR-ID** | FR-006 |
| **Module** | Billing Service |
| **Requirement** | Hệ thống quản lý credit: top-up, hold, deduct, refund |
| **Input** | Varies by operation (amount, job_id, transaction_type) |
| **Processing Logic** | **Top-up:**<br>1. Receive Stripe webhook (payment_intent.succeeded)<br>2. Verify webhook signature<br>3. Add credit to account<br>4. Create transaction record<br><br>**Hold:**<br>1. Verify balance ≥ amount<br>2. Subtract from balance<br>3. Create HOLD transaction with job_id<br><br>**Deduct:**<br>1. Find HOLD transaction for job_id<br>2. Change transaction type to DEDUCT<br><br>**Refund:**<br>1. Find HOLD transaction for job_id<br>2. Add amount back to balance<br>3. Change transaction type to REFUND |
| **Output** | Updated balance, transaction record |
| **Business Rules** | RULE-019, RULE-023, RULE-026, RULE-027, RULE-028, RULE-036 |
| **Acceptance Criteria** | Credit operations are atomic, no over-deduction |
| **Priority** | Must |
| **Trace to BR** | BR-005 (Billing) |

---

## 3. System Architecture & Design

### 3.1. Architecture Overview

**Architecture Style:** Modular Monolith with event-driven async processing

**Rationale:**
- Team size nhỏ (2-3 dev) → Monolith phù hợp hơn microservices
- Có async processing (OCR) → Event-driven pattern
- Scale từng phần (workers) → Modular để tách sau

**Key Architectural Decisions:**

| Decision | Choice | Alternatives Considered | Rationale |
|---|---|---|---|
| File flow | Direct to storage (presigned URL) | Through API server | Giảm load API, faster upload |
| Queue per tier | Separate queues | Single queue with priority | Tránh tier thấp block tier cao |
| Worker pull model | Pull-based | Push-based | Simpler scaling, worker controls load |
| Real-time updates | SSE | WebSocket | Simpler, sufficient for one-way push |
| Database | Firestore | PostgreSQL | Scale to zero, document model fits |

### 3.2. Component Breakdown

| Service | Responsibility | Key Functions | Dependencies | Data Owned | Communication |
|---|---|---|---|---|---|
| **API Gateway** | Request routing, auth check | Route, validate JWT, rate limit | Auth Service | None | Sync (REST) |
| **Auth Service** | User identity | Login, register, OAuth, token management | Firestore, OAuth providers | Users, Sessions | Sync (REST) |
| **Upload Service** | File ingestion | Presigned URL, validation, thumbnail | R2, Firestore | Files (metadata) | Sync (REST) |
| **Job Service** | Job orchestration | Create, status, cancel, retry | Firestore, Pub/Sub | Jobs, Batches | Sync + Async |
| **Billing Service** | Credit management | Top-up, hold, deduct, refund | Firestore, Stripe | BillingAccounts, Transactions | Sync (REST) |
| **Notification Service** | User notifications | Push, store, mark read | Firestore | Notifications | Async (SSE) |
| **Worker Manager** | Worker lifecycle | Start, stop, heartbeat, scale | GPU providers API, Firestore | Workers | Async |
| **OCR Worker** | OCR processing | Process, upload result | R2, Pub/Sub, Firestore | None (stateless) | Async (Queue) |

### 3.3. Data Architecture

#### 3.3.1. Data Flow - Job Processing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         JOB PROCESSING DATA FLOW                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  1. UPLOAD                                                                    │
│  ┌────────┐    presigned    ┌────────┐    file     ┌────────┐               │
│  │ Client │ ──────URL─────▶ │   R2   │ ◀────────── │ Client │               │
│  └────────┘                 └────────┘    upload   └────────┘               │
│                                  │                                           │
│                                  │ webhook / metadata                        │
│                                  ▼                                           │
│                            ┌──────────┐                                      │
│                            │ Firestore│  (file metadata)                     │
│                            └──────────┘                                      │
│                                                                               │
│  2. SUBMIT                                                                    │
│  ┌────────┐    submit    ┌──────────┐   credit    ┌──────────┐              │
│  │ Client │ ──────────▶  │ Job Svc  │ ──check───▶ │Billing   │              │
│  └────────┘    job       └──────────┘   hold      │ Svc      │              │
│                               │                   └──────────┘              │
│                               │ job created                                  │
│                               ▼                                              │
│                          ┌──────────┐                                        │
│                          │ Firestore│  (job record)                          │
│                          └──────────┘                                        │
│                               │                                              │
│                               │ publish                                      │
│                               ▼                                              │
│                          ┌──────────┐                                        │
│                          │ Pub/Sub  │  (tier-specific queue)                 │
│                          └──────────┘                                        │
│                                                                               │
│  3. PROCESS                                                                   │
│  ┌──────────┐    pull    ┌──────────┐   download  ┌────────┐                │
│  │ Pub/Sub  │ ─────────▶ │  Worker  │ ──────────▶ │   R2   │                │
│  └──────────┘    job     └──────────┘   file      └────────┘                │
│                               │                                              │
│                               │ OCR process                                  │
│                               │                                              │
│                               │ upload result                                │
│                               ▼                                              │
│                          ┌────────┐                                          │
│                          │   R2   │  (result file)                           │
│                          └────────┘                                          │
│                               │                                              │
│                               │ update status                                │
│                               ▼                                              │
│                          ┌──────────┐                                        │
│                          │ Firestore│  (job COMPLETED)                       │
│                          └──────────┘                                        │
│                                                                               │
│  4. NOTIFY                                                                    │
│  ┌──────────┐   listener  ┌──────────┐    SSE     ┌────────┐                │
│  │ Firestore│ ──────────▶ │Notif Svc │ ─────────▶ │ Client │                │
│  └──────────┘   trigger   └──────────┘   push     └────────┘                │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.2. Storage Strategy

| Storage Type | Technology | Data Stored | Retention |
|---|---|---|---|
| **Document DB** | Firestore | Users, Jobs, Batches, Transactions, Notifications, Workers | Permanent (except Notifications 30d, Jobs 90d) |
| **Object Storage** | Cloudflare R2 | Source files, Result files | User-defined (1h-30d source, 7-30d result) |
| **Cache** | Cloudflare KV / Redis | Session cache, rate limit counters | TTL-based |
| **Queue** | GCP Pub/Sub | Job queue (per tier) | Until consumed |

### 3.4. Integration Architecture

| External System | Direction | Protocol | Data Exchanged | Frequency | Auth | Error Handling |
|---|---|---|---|---|---|---|
| **Google OAuth** | In | OAuth 2.0 | User identity | On login | OAuth | Retry, fallback to email |
| **GitHub OAuth** | In | OAuth 2.0 | User identity | On login | OAuth | Retry, fallback to email |
| **Stripe** | Bi-directional | REST + Webhook | Payments, refunds | On top-up | API Key + Webhook signature | Retry, manual review |
| **Cloudflare R2** | Bi-directional | S3 API | Files | Frequent | API Key | Retry |
| **Vast.ai** | Out | REST | Worker provisioning | On scale | API Key | Retry, fallback provider |
| **RunPod** | Out | REST | Worker provisioning | On scale | API Key | Retry, fallback provider |

---

## 4. Data Dictionary & Schema Design

### 4.1. Data Dictionary

#### Users Collection

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | string | PK, auto-generated | User ID | "usr_abc123" |
| email | string | Required, unique, email format | User email | "user@example.com" |
| password_hash | string | Required (null if OAuth-only) | Bcrypt hash | "$2b$12$..." |
| oauth_providers | array | Optional | Linked OAuth providers | ["google", "github"] |
| created_at | timestamp | Required, auto | Creation time | 2024-01-15T10:30:00Z |
| updated_at | timestamp | Required, auto | Last update | 2024-01-15T10:30:00Z |

#### Jobs Collection

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | string | PK, auto-generated | Job ID | "job_xyz789" |
| user_id | string | FK to Users, required | Owner | "usr_abc123" |
| batch_id | string | FK to Batches, optional | Parent batch | "bat_def456" |
| file_id | string | Required | Source file reference | "file_ghi789" |
| file_name | string | Required | Original filename | "invoice.pdf" |
| page_count | integer | Required, min 1 | Number of pages | 10 |
| method | enum | Required | OCR method | "ocr_simple" / "ocr_table" / "ocr_code" |
| tier | integer | Required, 0-4 | Infrastructure tier | 2 |
| status | enum | Required | Current state | "QUEUED" |
| credit_amount | integer | Required, min 0 | Credit cost | 4000 |
| retention_days | integer | Required, 1-30 | File retention | 7 |
| result_path | string | Optional | Result file path | "results/job_xyz789/output.json" |
| confidence | float | Optional, 0-1 | Average confidence | 0.95 |
| error_reason | string | Optional | Error message if failed | "Timeout exceeded" |
| retry_count | integer | Default 0 | Number of retries | 1 |
| created_at | timestamp | Required | Submit time | 2024-01-15T10:30:00Z |
| started_at | timestamp | Optional | Processing start | 2024-01-15T10:31:00Z |
| completed_at | timestamp | Optional | Completion time | 2024-01-15T10:32:00Z |

#### BillingAccounts Collection

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | string | PK, auto-generated | Account ID | "acc_mno123" |
| user_id | string | FK to Users, unique | Owner | "usr_abc123" |
| balance | integer | Required, min 0 | Current balance (VND) | 500000 |
| total_topup | integer | Default 0 | Lifetime top-up | 1000000 |
| total_spent | integer | Default 0 | Lifetime spent | 500000 |
| created_at | timestamp | Required | Creation time | 2024-01-15T10:30:00Z |

#### Transactions Collection

| Field | Data Type | Constraints | Description | Example |
|---|---|---|---|---|
| id | string | PK, auto-generated | Transaction ID | "txn_pqr456" |
| account_id | string | FK to BillingAccounts | Account | "acc_mno123" |
| type | enum | Required | Transaction type | "TOPUP" / "HOLD" / "DEDUCT" / "REFUND" |
| amount | integer | Required | Amount (positive) | 100000 |
| balance_after | integer | Required | Balance after transaction | 600000 |
| job_id | string | Optional | Related job | "job_xyz789" |
| stripe_payment_id | string | Optional | Stripe reference | "pi_xxx" |
| description | string | Optional | Human-readable desc | "Top-up 100,000 VND" |
| created_at | timestamp | Required | Transaction time | 2024-01-15T10:30:00Z |

### 4.2. Job State Machine

```
                                        ┌─────────────────┐
                                        │   SUBMITTED     │
                                        │ (credit held)   │
                                        └────────┬────────┘
                                                 │
                                   ┌─────────────▼─────────────┐
                                   │        VALIDATING         │
                                   └─────────────┬─────────────┘
                                                 │
                           ┌─────────────────────┼─────────────────────┐
                           │ valid               │                      │ invalid
                           ▼                     │                      ▼
                    ┌──────────────┐             │               ┌──────────────┐
                    │    QUEUED    │             │               │   REJECTED   │
                    └──────┬───────┘             │               │  (refunded)  │
                           │                     │               └──────────────┘
          ┌────────────────┤                     │
          │ user cancel    │ worker picks        │
          ▼                ▼                     │
   ┌──────────────┐ ┌──────────────┐             │
   │  CANCELLED   │ │  DISPATCHED  │             │
   │  (refunded)  │ └──────┬───────┘             │
   └──────────────┘        │                     │
                           │                     │
                           ▼                     │
                    ┌──────────────┐             │
                    │  PROCESSING  │◄────────────┘
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │ success        │ timeout/error  │ error (no retry left)
          ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │  COMPLETED   │ │   RETRYING   │ │    FAILED    │
   │  (deducted)  │ └──────┬───────┘ │  (refunded)  │
   └──────────────┘        │         └──────────────┘
                           │
                           │ re-queue
                           ▼
                    ┌──────────────┐
                    │    QUEUED    │ (retry)
                    └──────┬───────┘
                           │
                           │ retry also fails
                           ▼
                    ┌──────────────┐
                    │ DEAD_LETTER  │
                    │  (refunded)  │
                    └──────────────┘
```

**Transition Rules:**

| From | To | Trigger | Guard | Action |
|---|---|---|---|---|
| SUBMITTED | VALIDATING | Auto | - | Validate file |
| VALIDATING | QUEUED | Validation pass | File valid | Push to queue |
| VALIDATING | REJECTED | Validation fail | File invalid | Refund credit |
| QUEUED | DISPATCHED | Worker picks | Worker available | Assign to worker |
| QUEUED | CANCELLED | User cancel | - | Refund credit |
| DISPATCHED | PROCESSING | Worker starts | - | Update started_at |
| PROCESSING | COMPLETED | OCR success | - | Deduct credit, save result |
| PROCESSING | RETRYING | Timeout/Error | retry_count < 1 | Increment retry_count |
| PROCESSING | FAILED | Error | retry_count >= 1 | Refund credit |
| RETRYING | QUEUED | Auto | - | Re-push to queue |
| Any error state | DEAD_LETTER | - | - | Refund, alert admin |

---

## 5. Non-Functional Requirements

### 5.1. Performance

| Metric | Target | Measurement | Priority |
|---|---|---|---|
| **API Response Time (P50)** | < 200ms | APM monitoring | Must |
| **API Response Time (P95)** | < 500ms | APM monitoring | Must |
| **File Upload (50MB)** | < 60s | End-to-end test | Must |
| **Job Complete (Tier 0, 10 pages)** | < 5 min | End-to-end test | Must |
| **Job Complete (Tier 4, 10 pages)** | < 1 min | End-to-end test | Should |
| **Concurrent Users** | 100+ | Load test | Must |
| **Page Load Time (LCP)** | < 2.5s | Lighthouse | Should |

### 5.2. Scalability

| Component | Horizontal | Vertical | Scaling Strategy |
|---|---|---|---|
| **API Gateway** | ✅ | ❌ | Cloudflare Workers auto-scale |
| **Orchestrator** | ✅ | ✅ | Cloud Run auto-scale (0-10 instances) |
| **Workers** | ✅ | ❌ | On-demand provisioning (0-N per tier) |
| **Firestore** | ✅ | N/A | Managed, auto-scale |
| **R2** | ✅ | N/A | Managed, unlimited |
| **Pub/Sub** | ✅ | N/A | Managed, auto-scale |

### 5.3. Availability & DR

| Aspect | Target | Strategy |
|---|---|---|
| **Uptime SLA** | 99.5% (Phase 2), 99.9% (Phase 3) | Managed services, multi-AZ |
| **RTO** | 4 hours (MVP), 1 hour (Scale) | Backup restore, infra as code |
| **RPO** | 24 hours (MVP), 1 hour (Scale) | Daily backup, point-in-time recovery |
| **Backup** | Daily (Firestore), lifecycle (R2) | GCP managed backup |
| **DR Region** | Single region MVP, multi-region Phase 3 | Cross-region replication |

### 5.4. Security

| Aspect | Implementation |
|---|---|
| **Data Encryption at Rest** | R2: default encryption, Firestore: Google-managed |
| **Data Encryption in Transit** | TLS 1.3 for all connections |
| **Authentication** | JWT (1h access, 30d refresh), OAuth 2.0 |
| **Authorization** | User-scoped access, API key for workers |
| **Secrets Management** | GCP Secret Manager, Cloudflare Secrets |
| **Input Validation** | Schema validation (Zod), sanitization |
| **Rate Limiting** | 100 req/min/user, 10 uploads/min/user |
| **File Validation** | MIME type + magic bytes + size + page count |
| **Audit Logging** | All write operations logged with user_id |
| **PII Handling** | No PII in logs, password hashed |

### 5.5. Observability

| Layer | Tool | Metrics |
|---|---|---|
| **Infrastructure** | GCP Cloud Monitoring | CPU, Memory, Network |
| **Application** | Structured logging + custom metrics | Latency, Error rate, Queue depth |
| **User** | Analytics (future) | Page views, conversions |
| **Tracing** | OpenTelemetry + Cloud Trace | Request traces |

**Key Alerts:**

| Alert | Condition | Severity |
|---|---|---|
| API Error Rate High | > 5% errors in 5 min | Critical |
| Queue Depth High | > 100 jobs pending for > 10 min | Warning |
| Worker Heartbeat Missing | No heartbeat for > 60s | Critical |
| Payment Webhook Failed | Stripe webhook 4xx/5xx | Critical |
| Refund Rate High | > 10% jobs refunded in 1 hour | Warning |
| Storage Usage High | R2 > 80% quota | Warning |

---

## 6. Test Strategy

### 6.1. Test Levels

| Test Level | Scope | Responsibility | Tools | Automation |
|---|---|---|---|---|
| **Unit** | Functions, utilities | Developer | Vitest, pytest | 100% automated |
| **Integration** | API endpoints, DB | Developer | Supertest, pytest | 90% automated |
| **E2E** | User flows | QA | Playwright | 80% automated |
| **Performance** | Load, stress | DevOps | k6 | Automated |
| **Security** | OWASP Top 10 | Security/QA | OWASP ZAP | Semi-automated |
| **UAT** | Business scenarios | PO, QA | Manual | Manual |

### 6.2. Acceptance Criteria Matrix

| FR-ID | Scenario | Given | When | Then |
|---|---|---|---|---|
| FR-001 | Happy: Register | New email | Submit registration | Account created, logged in |
| FR-001 | Edge: Email exists | Existing email | Submit registration | Error "Email already registered" |
| FR-001 | Edge: Weak password | Password "123" | Submit registration | Error with password requirements |
| FR-002 | Happy: Upload image | Valid 10MB JPEG | Upload | File accepted, preview shown |
| FR-002 | Edge: Large file | 60MB file | Upload | Error "File too large" |
| FR-002 | Edge: Wrong format | DOC file | Upload | Error "Unsupported format" |
| FR-003 | Happy: Submit job | Valid file, sufficient credit | Submit | Job created, status page shown |
| FR-003 | Edge: No credit | Valid file, 0 credit | Submit | Error "Insufficient credit" |
| FR-005 | Happy: OCR complete | Job processing | Worker finishes | Status COMPLETED, result available |
| FR-005 | Edge: Timeout | Job processing > timeout | Timeout | Retry once, then FAILED, refunded |
| FR-006 | Happy: Top-up | Select 100k package | Pay via Stripe | Credit added, transaction recorded |
| FR-006 | Edge: Payment failed | Select package | Stripe declines | Error "Payment failed", no credit |

### 6.3. Test Data Requirements

| Test Type | Data Source | Volume | Management |
|---|---|---|---|
| Unit tests | Fixtures, mocks | Minimal | In-repo |
| Integration tests | Seed scripts | ~100 records | Reset per run |
| E2E tests | Test accounts | 10 users, 50 files | Cleanup after run |
| Performance tests | Generated data | 1000 users, 10000 jobs | Separate environment |
| OCR accuracy tests | Sample documents | 100 files (diverse types) | Curated test set |

---

## 7. UI-Logic Specification

### 7.1. SCR-005: Upload Page

| Trường | Nội dung |
|---|---|
| **Screen** | Upload Page — File selection and upload |
| **URL** | /upload |
| **Access** | Authenticated users |
| **Layout** | Single column, centered content, max-width 800px |
| **Input Fields** | Drag-drop zone, File picker button |
| **Actions** | Upload, Remove file, Continue to config |
| **States** | Empty, Uploading (progress), Uploaded (preview), Error |
| **Interactions** | Drag-drop, Click to browse, Progress bar, Remove button |
| **Notifications** | Toast on error (size, format) |
| **Responsive** | Stack vertically on mobile, smaller drop zone |

**Validation Logic:**

| Field | Validation | Error Message |
|---|---|---|
| File format | PNG, JPEG, TIFF, BMP, WEBP, PDF | "Unsupported format. Supported: PNG, JPEG, TIFF, BMP, WEBP, PDF" |
| File size | ≤ 50MB | "File too large. Maximum 50MB" |
| PDF pages | ≤ 100 (checked server-side) | "Too many pages. Maximum 100 pages" |
| Batch size | ≤ 200MB total, ≤ 50 files | "Batch too large" / "Too many files" |

### 7.2. SCR-006: Configuration Page

| Trường | Nội dung |
|---|---|
| **Screen** | Configuration Page — Method and tier selection |
| **URL** | /upload/config |
| **Access** | Authenticated users with uploaded file |
| **Layout** | Two sections: Method cards (3), Tier cards (5), Summary sidebar |
| **Input Fields** | Radio selection for method, Radio selection for tier, Slider for retention |
| **Actions** | Select method, Select tier, Adjust retention, Submit job |
| **States** | Default (nothing selected), Configured (both selected), Submitting |
| **Interactions** | Card click to select, Slider drag, Cost recalculation on change |
| **Notifications** | Toast on insufficient credit, Modal for confirmation |
| **Responsive** | Cards stack vertically, Summary at bottom |

**Business Logic:**

| Action | Logic | Update |
|---|---|---|
| Select method | Store method choice | Recalculate cost, update estimate |
| Select tier | Store tier choice | Recalculate cost, update estimate |
| Adjust retention | Store retention_days | Update retention display |
| Submit | Validate credit, hold, create job | Redirect to status page |

**Cost Calculation (client-side preview):**
```
cost = base_price[method] × tier_multiplier[tier] × page_count
estimate_time = base_time[method] × page_count × tier_factor[tier]
```

### 7.3. SCR-007: Job Status Page

| Trường | Nội dung |
|---|---|
| **Screen** | Job Status Page — Real-time tracking |
| **URL** | /jobs/{job_id} |
| **Access** | Job owner only |
| **Layout** | Status indicator (top), Timeline (middle), Actions (bottom) |
| **Data Display** | Status badge, Progress (if available), Queue position, Timestamps |
| **Actions** | Cancel (if QUEUED), View Result (if COMPLETED), Download |
| **States** | Loading, Live (SSE connected), Disconnected (fallback polling) |
| **Interactions** | Auto-update via SSE, Cancel button, Result link |
| **Notifications** | Inline status changes, Toast on complete/fail |
| **Responsive** | Single column, timeline vertical |

**SSE Event Handling:**

| Event | UI Update |
|---|---|
| status_change | Update status badge, add timeline entry |
| progress | Update progress indicator |
| queue_position | Update queue position display |
| completed | Show "View Result" button, success toast |
| failed | Show error reason, refund confirmation |

---

## Summary

```
--- SUMMARY HANDOFF #2 (BA Tech → SA) ---
Functional Requirements: FR-001 (Auth), FR-002 (Upload), FR-003 (Submit), FR-004 (Tracking), FR-005 (Processing), FR-006 (Billing)
System Components: API Gateway, Auth Service, Upload Service, Job Service, Billing Service, Notification Service, Worker Manager, OCR Worker
Data Entities: Users, Jobs, Batches, BillingAccounts, Transactions, Notifications
Integration Points: Google OAuth, GitHub OAuth, Stripe, Cloudflare R2, Vast.ai, RunPod
NFRs Defined: API P95 < 500ms, Job < 5min (T0), 99.5% uptime, TLS everywhere, rate limiting
Test Coverage: Unit (100%), Integration (90%), E2E (80%), Performance, Security
State Machine: 10 job states with defined transitions and side effects
--- ✅ PHASE 2 COMPLETE (Technical Analysis) ---
```
