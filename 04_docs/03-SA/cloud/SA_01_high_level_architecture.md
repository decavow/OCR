# OCR Platform — System Architecture Document (SAD)

> Tài liệu kiến trúc hệ thống high-level cho OCR Platform
> Version: 1.0 | Status: Draft
> References: `01-PO/PO_product_spec.md`, `02-BA/BA_business_analysis.md`, `02-BA/BA_technical_analysis.md`

---

## Table of Contents

1. [Executive Summary](#section-1-executive-summary)
2. [Architecture Overview](#section-2-architecture-overview)
3. [Technology Stack](#section-3-technology-stack)
4. [Data Architecture](#section-4-data-architecture)
5. [Integration & Communication](#section-5-integration--communication)
6. [Infrastructure & Deployment](#section-6-infrastructure--deployment)
7. [Security](#section-7-security)
8. [Non-Functional Requirements](#section-8-non-functional-requirements)
9. [Risks & Trade-offs](#section-9-risks--trade-offs)

---

## SECTION 1: EXECUTIVE SUMMARY

### 1.1. Mục tiêu và phạm vi hệ thống

OCR Platform là nền tảng web cho phép người dùng upload tài liệu (ảnh, PDF), chọn phương pháp xử lý OCR phù hợp (text thuần, bảng biểu, mã nguồn), và nhận kết quả structured output. Hệ thống sử dụng mô hình pre-paid credit, hỗ trợ 5 mức hạ tầng (tiers) với các đặc điểm bảo mật, tốc độ, và giá khác nhau.

Phạm vi kiến trúc bao gồm:
- Web frontend (SPA)
- API backend và orchestration layer
- GPU-based OCR workers (multi-provider)
- File storage và metadata database
- Billing integration (Stripe)
- Real-time notifications

### 1.2. Design Principles

| Principle | Description |
|---|---|
| **Simplicity First** | Ưu tiên giải pháp đơn giản nhất có thể. Modular monolith thay vì microservices. Managed services thay vì self-hosted. |
| **Cost Efficiency** | Tối ưu chi phí cho SMB: scale-to-zero cho orchestrator, on-demand GPU workers, free tiers của cloud services. |
| **API-First** | Mọi component giao tiếp qua well-defined APIs. Frontend và backend hoàn toàn tách biệt. |
| **Security by Default** | TLS everywhere, presigned URLs cho file access, secrets management, input validation. |
| **Stateless Application** | Application servers không lưu state. State nằm trong database và storage. Dễ scale và recover. |
| **Observable by Design** | Structured logging, trace ID xuyên suốt, health checks, alerts từ ngày đầu. |

### 1.3. Key Features

| Feature | Description |
|---|---|
| **3-Layer Architecture** | Edge (Cloudflare) → Orchestration (GCP) → Processing (GPU). File không đi qua orchestration. |
| **Tier-based Processing** | 5 tiers (0-4) với queue riêng biệt, tránh tier thấp block tier cao. Tier 0,4 always-on. |
| **Pull-based Workers** | Workers chủ động pull job từ queue, self-managed workload. |
| **Real-time Status** | SSE-based real-time updates, không cần polling. |
| **Atomic Credit Operations** | Firestore transactions đảm bảo tính toàn vẹn credit (hold/deduct/refund). |
| **Auto Worker Scaling** | Orchestrator tự động bật/tắt workers theo queue depth. |

---

## SECTION 2: ARCHITECTURE OVERVIEW

### 2.1. Architectural Style

| Trường | Nội dung |
|---|---|
| **Architecture Pattern** | **Modular Monolith** với **Event-driven** async processing |
| **Tại sao chọn pattern này?** | Team size nhỏ (2-3 dev) không cần complexity của microservices. Tuy nhiên, OCR processing cần async/background processing nên dùng event-driven pattern cho phần workers. Modular monolith cho phép tách service sau khi scale. |
| **Khi nào cần chuyển đổi?** | Khi có > 5 dev teams cần deploy độc lập, hoặc khi một module cần scale technology khác biệt (ví dụ: billing cần strong consistency → tách ra dùng PostgreSQL). |

**Bổ sung pattern:**

```python
# Factory pattern cho OCR method selection
OCR_HANDLERS = {
    "ocr_simple": TesseractSimpleHandler,
    "ocr_table": TableTransformerHandler,
    "ocr_code": CodeAwareOCRHandler,
}

def get_ocr_handler(method: str) -> OCRHandler:
    return OCR_HANDLERS[method]()
```

```python
# Config-as-code cho tier configuration
TIER_CONFIG = {
    0: {"name": "Local", "multiplier": 1, "provider": "self-hosted", "always_on": True},
    1: {"name": "Standard", "multiplier": 2, "provider": "vastai", "always_on": False},
    2: {"name": "Enhanced", "multiplier": 4, "provider": "runpod", "always_on": False},
    3: {"name": "Dedicated", "multiplier": 8, "provider": "runpod", "always_on": False},
    4: {"name": "VIP", "multiplier": 20, "provider": "vip-cluster", "always_on": True},
}
```

### 2.2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    OCR PLATFORM ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              EDGE LAYER (Cloudflare)                                  │   │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                   │   │
│   │  │   Cloudflare     │  │   Cloudflare     │  │   Cloudflare     │                   │   │
│   │  │     Pages        │  │     Workers      │  │       R2         │                   │   │
│   │  │   (Frontend)     │  │  (API Gateway)   │  │   (Storage)      │                   │   │
│   │  │                  │  │                  │  │                  │                   │   │
│   │  │  • SPA hosting   │  │  • Routing       │  │  • Source files  │                   │   │
│   │  │  • CDN           │  │  • Rate limiting │  │  • Result files  │                   │   │
│   │  │  • SSL           │  │  • Auth check    │  │  • Presigned URL │                   │   │
│   │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘                   │   │
│   └───────────┼─────────────────────┼─────────────────────┼─────────────────────────────┘   │
│               │                     │                     │                                  │
│               │    HTTPS            │    HTTPS            │    S3 API                       │
│               │                     ▼                     │                                  │
│   ┌───────────┼─────────────────────────────────────────────────────────────────────────┐   │
│   │           │             ORCHESTRATION LAYER (GCP)                                    │   │
│   │           │                                                                          │   │
│   │  ┌────────▼─────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        CLOUD RUN (Orchestrator)                               │   │   │
│   │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │   │
│   │  │  │ Auth Service │  │ Job Service  │  │Billing Svc   │  │ Notif Service│      │   │   │
│   │  │  │              │  │              │  │              │  │              │      │   │   │
│   │  │  │ • Login      │  │ • Create job │  │ • Hold       │  │ • Push (SSE) │      │   │   │
│   │  │  │ • Register   │  │ • Status     │  │ • Deduct     │  │ • Store      │      │   │   │
│   │  │  │ • OAuth      │  │ • Cancel     │  │ • Refund     │  │ • Mark read  │      │   │   │
│   │  │  │ • Token      │  │ • History    │  │ • Stripe     │  │              │      │   │   │
│   │  │  └──────────────┘  └──────┬───────┘  └──────────────┘  └──────────────┘      │   │   │
│   │  │                           │                                                   │   │   │
│   │  │  ┌──────────────┐         │         ┌──────────────┐                         │   │   │
│   │  │  │Upload Service│         │         │Worker Manager│                         │   │   │
│   │  │  │              │         │         │              │                         │   │   │
│   │  │  │ • Presigned  │         │         │ • Start/Stop │                         │   │   │
│   │  │  │ • Validate   │         │         │ • Heartbeat  │                         │   │   │
│   │  │  │ • Metadata   │         │         │ • Scale      │                         │   │   │
│   │  │  └──────────────┘         │         └──────┬───────┘                         │   │   │
│   │  └───────────────────────────┼────────────────┼─────────────────────────────────┘   │   │
│   │                              │                │                                      │   │
│   │                              │ publish        │ manage                               │   │
│   │                              ▼                ▼                                      │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                           GCP Pub/Sub (Queues)                                │   │   │
│   │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │   │
│   │  │  │ Tier 0   │  │ Tier 1   │  │ Tier 2   │  │ Tier 3   │  │ Tier 4   │       │   │   │
│   │  │  │  Queue   │  │  Queue   │  │  Queue   │  │  Queue   │  │  Queue   │       │   │   │
│   │  │  │ (FIFO)   │  │ (FIFO)   │  │ (FIFO)   │  │ (FIFO)   │  │ (FIFO)   │       │   │   │
│   │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │   │   │
│   │  └───────┼─────────────┼─────────────┼─────────────┼─────────────┼──────────────┘   │   │
│   │          │             │             │             │             │                   │   │
│   │  ┌───────┴─────────────┴─────────────┴─────────────┴─────────────┴──────────────┐   │   │
│   │  │                           FIRESTORE (Database)                                │   │   │
│   │  │  Users │ Jobs │ Batches │ BillingAccounts │ Transactions │ Notifications     │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                               │
│                                          │ pull                                              │
│                                          ▼                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           PROCESSING LAYER (GPU Workers)                              │   │
│   │                                                                                       │   │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                   │   │
│   │  │   Tier 0 Worker  │  │  Tier 1 Worker   │  │  Tier 2-4 Worker │                   │   │
│   │  │   (Self-hosted)  │  │    (Vast.ai)     │  │    (RunPod)      │                   │   │
│   │  │                  │  │                  │  │                  │                   │   │
│   │  │  1. Pull job     │  │  1. Pull job     │  │  1. Pull job     │                   │   │
│   │  │  2. Download file│  │  2. Download file│  │  2. Download file│                   │   │
│   │  │  3. OCR process  │  │  3. OCR process  │  │  3. OCR process  │                   │   │
│   │  │  4. Upload result│  │  4. Upload result│  │  4. Upload result│                   │   │
│   │  │  5. Update status│  │  5. Update status│  │  5. Update status│                   │   │
│   │  │  6. Heartbeat    │  │  6. Heartbeat    │  │  6. Heartbeat    │                   │   │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘                   │   │
│   │                                                                                       │   │
│   │  OCR Engines:                                                                        │   │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                   │   │
│   │  │ Tesseract 5.x    │  │ Table Transformer│  │ Code-aware OCR   │                   │   │
│   │  │ (ocr_simple)     │  │ (ocr_table)      │  │ (ocr_code)       │                   │   │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘                   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3. Danh sách thành phần chính và trách nhiệm

#### 1. Web Frontend (Edge Layer - Cloudflare Pages)

Web Frontend là Single Page Application (SPA) được host trên Cloudflare Pages, phục vụ giao diện người dùng cho toàn bộ platform. Frontend không chứa business logic, chỉ gọi API và render UI.

Frontend xử lý các flow chính: authentication, file upload (direct to R2 via presigned URL), job configuration và submission, real-time status tracking (via SSE), result viewing, và billing management. Responsive design hỗ trợ desktop và mobile browsers.

#### 2. API Gateway (Edge Layer - Cloudflare Workers)

API Gateway là entry point cho mọi API requests từ frontend. Chạy trên Cloudflare Workers edge network để minimize latency globally.

Responsibilities:
- **Routing:** Map incoming requests đến appropriate backend service
- **Authentication check:** Validate JWT token, reject unauthorized requests
- **Rate limiting:** Enforce per-user rate limits (100 req/min, 10 uploads/min)
- **Request validation:** Basic schema validation trước khi forward
- **CORS handling:** Cross-origin configuration

API Gateway không chứa business logic, chỉ forward requests đến Cloud Run orchestrator.

#### 3. Auth Service (Orchestration Layer)

Auth Service quản lý toàn bộ user identity và authentication flow. Đây là internal service trong Cloud Run orchestrator.

Flow chi tiết:
```
┌────────────┐     ┌────────────┐     ┌────────────┐
│   Email    │     │  Register  │     │   Create   │
│  Password  │────▶│  Validate  │────▶│   User     │────▶ JWT Token
└────────────┘     └────────────┘     └────────────┘

┌────────────┐     ┌────────────┐     ┌────────────┐
│   OAuth    │     │  Exchange  │     │   Find/    │
│   Code     │────▶│   Token    │────▶│Create User │────▶ JWT Token
└────────────┘     └────────────┘     └────────────┘
```

JWT tokens có 1h access expiry và 30d refresh expiry. Refresh tokens stored in Firestore.

#### 4. Upload Service (Edge + Orchestration Layer)

Upload Service xử lý file ingestion với pattern presigned URL để files không đi qua application server.

Flow:
```
┌────────┐  1. Request   ┌──────────┐  2. Generate  ┌────────┐
│ Client │─────URL─────▶│ Upload   │─────URL─────▶│   R2   │
└────────┘               │ Service  │               └────────┘
    │                    └──────────┘                   │
    │                                                    │
    │ 3. Direct upload (via presigned URL)              │
    └───────────────────────────────────────────────────┘
    │
    │ 4. Upload complete notification
    ▼
┌──────────┐  5. Validate  ┌──────────┐  6. Store   ┌──────────┐
│ Upload   │────file───────│ Validate │───metadata─▶│Firestore │
│ Service  │               └──────────┘              └──────────┘
└──────────┘
```

Validation includes: MIME type check, magic bytes verification, file size (≤50MB), PDF page count (≤100).

#### 5. Job Service (Orchestration Layer)

Job Service là core orchestration component quản lý toàn bộ job lifecycle. Đây là critical path của hệ thống.

Responsibilities:
- **Job Creation:** Validate input, calculate credit, create job record, publish to queue
- **Status Management:** Track state transitions, update timestamps
- **Queue Management:** Publish to tier-specific queue, handle dead letter
- **Retry Logic:** Orchestrate retry (max 1) khi worker fail

Job States và Transitions (see BA Technical for full state diagram):
- SUBMITTED → VALIDATING → QUEUED → DISPATCHED → PROCESSING → COMPLETED
- Error paths: REJECTED, CANCELLED, FAILED, RETRYING, DEAD_LETTER

Credit operations are atomic with job creation via Firestore transactions.

#### 6. Billing Service (Orchestration Layer)

Billing Service quản lý credit lifecycle và Stripe integration.

| Operation | Input | Process | Output |
|---|---|---|---|
| Top-up | Stripe webhook | Verify signature → Add credit → Create txn | Updated balance |
| Hold | job_id, amount | Check balance → Subtract → Create HOLD txn | hold_id |
| Deduct | hold_id | Convert HOLD to DEDUCT | Final transaction |
| Refund | hold_id | Add back to balance → Convert to REFUND | Updated balance |

All credit operations use Firestore transactions to ensure ACID properties.

#### 7. Notification Service (Orchestration Layer)

Notification Service handles in-app notifications via Server-Sent Events (SSE).

```
┌──────────┐  Firestore  ┌──────────┐    SSE     ┌────────┐
│Firestore │───listener──│  Notif   │───stream──▶│ Client │
│(Job doc) │   trigger   │ Service  │           └────────┘
└──────────┘             └──────────┘
```

Notification types: job_completed, job_failed, job_retrying, batch_completed, credit_low, credit_refunded, file_expiring.

Notifications stored in Firestore for 30 days, with read/unread status.

#### 8. Worker Manager (Orchestration Layer)

Worker Manager controls GPU worker lifecycle based on queue status.

Logic:
```python
def manage_workers():
    for tier in [1, 2, 3]:  # Tier 0, 4 always-on
        queue_depth = get_queue_depth(tier)
        active_workers = get_active_workers(tier)

        if queue_depth > 0 and active_workers == 0:
            start_worker(tier)
        elif queue_depth == 0 and worker_idle_time(tier) > IDLE_THRESHOLD[tier]:
            stop_worker(tier)
```

Heartbeat monitoring: Workers send heartbeat every 15s. Missing 4 heartbeats (60s) → worker considered dead → job marked FAILED.

#### 9. OCR Workers (Processing Layer)

OCR Workers are stateless GPU containers that process OCR jobs. They run on different providers based on tier.

| Tier | Provider | Characteristics |
|---|---|---|
| 0 | Self-hosted | Local machine, no SLA, cheapest |
| 1 | Vast.ai | Shared GPU, spot instances, best-effort |
| 2 | RunPod | Shared GPU, enhanced encryption, SLA 99.5% |
| 3 | RunPod | Dedicated GPU, zero-retention, SLA 99.9% |
| 4 | VIP Cluster | Isolated network, E2E encryption, SLA 99.95% |

Worker Processing Pipeline:
```
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
│  Pull   │──▶│ Download │──▶│   OCR    │──▶│  Upload  │──▶│  Update  │──▶│ Cleanup │
│  Job    │   │   File   │   │ Process  │   │  Result  │   │  Status  │   │  Files  │
└─────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │Tesseract │ │  Table   │ │Code-aware│
              │(simple)  │ │Transform │ │  OCR     │
              └──────────┘ └──────────┘ └──────────┘
```

Workers delete local files immediately after processing for security.

#### 10. Storage - Cloudflare R2 (Edge Layer)

R2 serves as object storage for all files with S3-compatible API.

| Bucket | Content | Lifecycle |
|---|---|---|
| sources | Uploaded source files | User-defined (1h-30d, default 24h) |
| results | OCR output files | User-defined (1-30d, default 7d) |

Access control: All access via presigned URLs with time-limited validity (15min upload, 1h download, 2h worker access).

#### 11. Database - Firestore (Orchestration Layer)

Firestore is the single source of truth for all non-file data.

Collections:
- **users:** User accounts, auth info
- **jobs:** Job records with status, timestamps
- **batches:** Batch groupings
- **billingAccounts:** Credit balances
- **transactions:** All credit movements
- **notifications:** User notifications
- **workers:** Worker status, heartbeats

Firestore cho phép scale-to-zero (không tốn tiền khi không có traffic), phù hợp với MVP cost constraints.

---

## SECTION 3: TECHNOLOGY STACK

### 3.1. Tech Stack Table

| Technology | Vai trò | Lý do sử dụng |
|---|---|---|
| **Cloudflare Pages** | Frontend hosting | Cloudflare Pages cung cấp global CDN với zero configuration, automatic HTTPS, và integration tốt với Workers. Free tier đủ cho MVP. So với Vercel/Netlify, Pages có advantage là nằm trong cùng ecosystem với Workers và R2, giảm latency và simplify architecture. |
| **Cloudflare Workers** | API Gateway, Edge functions | Workers chạy trên edge network với cold start < 5ms, so với Lambda/Cloud Functions có cold start 100-500ms. Rate limiting và routing ở edge giảm load cho backend. Free tier 100k requests/day đủ cho MVP. |
| **Cloudflare R2** | Object storage | R2 có S3-compatible API nhưng **zero egress fees**, quan trọng khi serve files. So với S3 ($0.09/GB egress), R2 tiết kiệm significant costs. Lifecycle rules tự động xoá files. |
| **GCP Cloud Run** | Orchestrator hosting | Cloud Run cho phép scale-to-zero, chỉ tính tiền khi có requests. So với EC2/GCE always-on, tiết kiệm 80%+ cho MVP traffic. Container-based deployment đơn giản hơn Kubernetes. |
| **GCP Firestore** | NoSQL Database | Firestore có serverless pricing (pay-per-operation), scale-to-zero, phù hợp MVP. Document model fit với data structure (users, jobs). Free tier: 50k reads, 20k writes/day. So với PostgreSQL, không cần manage connections, replicas. Trade-off: limited query capabilities, nhưng đủ cho use cases hiện tại (lookup by ID, filter by user). |
| **GCP Pub/Sub** | Message Queue | Pub/Sub cung cấp managed message queue với exactly-once delivery option. Separate topic per tier đảm bảo isolation. So với Redis Streams, Pub/Sub có better durability và scaling. So với Kafka, đơn giản hơn nhiều và managed. |
| **GCP Cloud Scheduler** | Cron jobs | Scheduler triggers periodic tasks: cleanup expired files, worker health check, billing reconciliation. Managed service, không cần maintain cron server. |
| **Stripe** | Payment processing | Stripe là industry standard cho payments, PCI compliant, excellent API và documentation. Stripe Elements cho secure card input. Webhook cho async payment confirmation. 2.9% + $0.30 per transaction. |
| **Tesseract 5.x** | OCR Engine (ocr_simple) | Tesseract là open-source OCR engine với best balance accuracy/cost. Version 5 có LSTM-based recognition, 95%+ accuracy cho printed text. So với Google Vision API ($1.5/1000 images), Tesseract is free và self-hosted, giảm per-page cost. |
| **Table Transformer** | OCR Engine (ocr_table) | Microsoft Table Transformer model cho table detection và structure recognition. Output structured JSON với rows/columns. Chạy trên GPU, accuracy cao hơn rule-based approaches. |
| **Python** | Worker runtime | Python có best ecosystem cho OCR và ML (Tesseract bindings, PyTorch, transformers). Workers cần GPU processing, Python có mature CUDA support. |
| **TypeScript** | Frontend + Backend | TypeScript cho type safety across full stack. Frontend: React/Vue SPA. Backend (Workers, Cloud Run): TypeScript hoặc Python. Consistency giảm context switching. |

**Environment Variations:**

| Environment | Storage | Database | Queue |
|---|---|---|---|
| Local Dev | MinIO (S3 compat) | Firestore Emulator | Redis/In-memory |
| Staging | R2 | Firestore | Pub/Sub |
| Production | R2 | Firestore | Pub/Sub |

---

## SECTION 4: DATA ARCHITECTURE

### 4.1. Domain Model Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN MODEL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│                                                                               │
│   ┌──────────────┐                                                           │
│   │     USER     │                                                           │
│   │              │                                                           │
│   │  id          │                                                           │
│   │  email       │                                                           │
│   │  auth_info   │                                                           │
│   └──────┬───────┘                                                           │
│          │                                                                    │
│          │ 1:1                                                               │
│          ▼                                                                    │
│   ┌──────────────┐         1:N          ┌──────────────┐                     │
│   │   BILLING    │◀─────────────────────│ TRANSACTION  │                     │
│   │   ACCOUNT    │                      │              │                     │
│   │              │                      │  type        │                     │
│   │  balance     │                      │  amount      │                     │
│   │  totals      │                      │  job_ref     │                     │
│   └──────────────┘                      └──────────────┘                     │
│          │                                     │                              │
│          │                                     │ N:1 (optional)              │
│          │                                     ▼                              │
│          │ 1:N                          ┌──────────────┐                     │
│          │                              │     JOB      │         1:1         │
│          └─────────────────────────────▶│              │◀─────────────────┐  │
│                                         │  status      │                  │  │
│   ┌──────────────┐         N:1          │  method      │           ┌──────┴──┴───┐
│   │    BATCH     │◀─────────────────────│  tier        │           │   RESULT    │
│   │              │                      │  file_ref    │           │             │
│   │  config      │                      │  timestamps  │           │  path       │
│   │  retention   │                      └──────────────┘           │  format     │
│   └──────────────┘                                                 │  confidence │
│                                                                    └─────────────┘
│                                                                               │
│   ┌──────────────┐         N:1                                               │
│   │ NOTIFICATION │◀──────────────────── USER                                 │
│   │              │                                                           │
│   │  type        │                                                           │
│   │  message     │                                                           │
│   │  read        │                                                           │
│   └──────────────┘                                                           │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Chiến lược lưu trữ

| Storage Type | Công nghệ | Dữ liệu lưu trữ |
|---|---|---|
| **Document Database** | Firestore | All metadata: users, jobs, batches, billing, transactions, notifications. Source of truth cho business data. |
| **Object Storage** | Cloudflare R2 | Binary files: source images/PDFs (sources/), OCR results (results/). Accessed via presigned URLs. |
| **Edge Cache** | Cloudflare KV | Session cache, rate limit counters, config cache. Low latency access from edge. |
| **Message Queue** | GCP Pub/Sub | Job queues (1 per tier), dead letter queue. Durable, at-least-once delivery. |

### 4.3. Data Flow

**Upload Flow:**
```
┌────────┐    presigned URL    ┌────────┐    direct upload    ┌────────┐
│ Client │ ◀───────────────── │ Server │                      │   R2   │
│        │ ──────────────────▶│        │                      │        │
│        │    request URL      │        │                      │        │
│        │ ────────────────────────────────────────────────────▶        │
└────────┘    upload file (presigned)                          └────────┘
                                                                    │
                        webhook / poll                              │
                        ┌───────────────────────────────────────────┘
                        ▼
                   ┌──────────┐    store metadata    ┌──────────┐
                   │  Server  │ ──────────────────▶ │Firestore │
                   └──────────┘                      └──────────┘
```

**Processing Flow:**
```
┌──────────┐  publish  ┌──────────┐   pull    ┌──────────┐
│Job Service│────────▶│ Pub/Sub  │◀─────────│  Worker  │
└──────────┘          └──────────┘           └──────────┘
                                                  │
                         download file            │
    ┌────────────────────────────────────────────┘
    ▼
┌────────┐                                   ┌──────────┐
│   R2   │                                   │  Worker  │
│(source)│◀──────────────────────────────────│  (OCR)   │
└────────┘                                   └──────────┘
                                                  │
                         upload result            │
    ┌────────────────────────────────────────────┘
    ▼
┌────────┐                                   ┌──────────┐  update   ┌──────────┐
│   R2   │                                   │  Worker  │──status──▶│Firestore │
│(result)│                                   └──────────┘           └──────────┘
└────────┘
```

### 4.4. Caching Layer

Hệ thống không có complex caching requirements trong MVP. Các cache points:

| Cache | Purpose | Implementation | TTL |
|---|---|---|---|
| **Session Cache** | Validate JWT without DB hit | Cloudflare KV | Match token expiry |
| **Rate Limit Counters** | Track request counts | Cloudflare KV | 1 minute sliding window |
| **Config Cache** | Tier config, pricing | Cloudflare KV | 5 minutes |

Future consideration: Result caching cho repeated queries (same document hash → cached result).

### 4.5. Data Governance

**Access Control:**
- All data is user-scoped (no cross-user access)
- Jobs only accessible by owner (user_id check in all queries)
- Files accessed via presigned URLs with short expiry
- Admin access requires separate elevated permissions

**Data Lifecycle:**
| Data Type | Retention | Deletion Method |
|---|---|---|
| Source files | 1h-30d (user choice, default 24h) | R2 lifecycle rules + backup cron |
| Result files | 1-30d (user choice, default 7d) | R2 lifecycle rules + backup cron |
| Job metadata | 90 days | Firestore TTL policy |
| Notifications | 30 days | Firestore TTL policy |
| Billing history | 2 years | Compliance requirement |
| Audit logs | 2 years | Compliance requirement |

**File Deletion Guarantee:**
1. R2 lifecycle rules (primary)
2. Daily cron job verifies and deletes missed files (backup)
3. Weekly audit script reports discrepancies (monitoring)

**Audit Logging:**
- All write operations logged: user_id, action, resource_id, timestamp
- Sensitive data NOT logged: passwords, file contents, card numbers
- Logs retained 2 years for compliance

---

## SECTION 5: INTEGRATION & COMMUNICATION

### 5.1. Giao tiếp nội bộ

| Pattern | Use Case | Implementation | Ghi chú |
|---|---|---|---|
| **Sync (REST)** | Frontend ↔ API Gateway ↔ Orchestrator | HTTPS, JSON, < 500ms P95 | Standard request-response |
| **Async (Queue)** | Job submission → Worker processing | Pub/Sub, JSON payload | Decouples submission from processing |
| **Event-driven** | Job status → Notifications | Firestore triggers → SSE | Real-time updates |
| **SSE** | Server → Client notifications | HTTP streaming | One-way push, simpler than WebSocket |

**Communication Rules:**
- Workers process jobs sequentially (no parallel within one worker)
- All services are stateless, state in Firestore
- Queue technology abstracted via interface for future migration

### 5.2. Message Queue Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE QUEUE ARCHITECTURE                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────────┐                                                           │
│   │  Job Service │                                                           │
│   │  (Producer)  │                                                           │
│   └──────┬───────┘                                                           │
│          │                                                                    │
│          │ publish (with tier routing)                                        │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                          GCP Pub/Sub                                  │   │
│   │                                                                       │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │   │
│   │  │tier-0-jobs│ │tier-1-jobs│ │tier-2-jobs│ │tier-3-jobs│ │tier-4- │ │   │
│   │  │  (topic)  │ │  (topic)  │ │  (topic)  │ │  (topic)  │ │  jobs  │ │   │
│   │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬───┘ │   │
│   │        │             │             │             │            │      │   │
│   │        │             │             │             │            │      │   │
│   │  ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌────▼───┐ │   │
│   │  │  tier-0   │ │  tier-1   │ │  tier-2   │ │  tier-3   │ │tier-4  │ │   │
│   │  │   sub     │ │   sub     │ │   sub     │ │   sub     │ │  sub   │ │   │
│   │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬───┘ │   │
│   │        │             │             │             │            │      │   │
│   └────────┼─────────────┼─────────────┼─────────────┼────────────┼──────┘   │
│            │             │             │             │            │          │
│            │ pull        │ pull        │ pull        │ pull       │ pull     │
│            ▼             ▼             ▼             ▼            ▼          │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│   │ Tier 0 Worker│ │ Tier 1 Worker│ │Tier 2 Worker │ │ Tier 3/4     │       │
│   │ (Self-hosted)│ │  (Vast.ai)   │ │  (RunPod)    │ │   Workers    │       │
│   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│                                                                               │
│   Dead Letter Queue (failed after retry):                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                        dead-letter-jobs (topic)                       │   │
│   │                             → Admin review                            │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Message Format:**
```json
{
  "job_id": "job_xyz789",
  "file_url": "https://presigned-url-to-source-file",
  "method": "ocr_table",
  "tier": 2,
  "page_count": 10,
  "config": {
    "language": "eng+vie",
    "output_format": "json"
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Consumer Strategy:**
- Each tier subscription has max 1 worker pulling (Phase 1)
- Phase 3: Multiple workers per tier with message acknowledgment
- Message visibility timeout: 30 minutes (max job processing time)

**Retry Mechanism:**
- Worker failure: Message returns to queue (nack)
- Retry count tracked in job record
- After 1 retry failure: Move to dead letter queue

### 5.3. Tích hợp hệ thống bên ngoài

| External System | Integration Method | Purpose | Ghi chú |
|---|---|---|---|
| **Google OAuth** | OAuth 2.0 | User authentication | Redirect flow, get email + name |
| **GitHub OAuth** | OAuth 2.0 | User authentication | Redirect flow, get email + name |
| **Stripe** | REST API + Webhooks | Payments | Checkout Session for top-up, Webhook for confirmation |
| **Vast.ai** | REST API | Tier 1 worker provisioning | Start/stop instances on demand |
| **RunPod** | REST API | Tier 2-3 worker provisioning | Start/stop pods on demand |

### 5.4. API Design Principles

- **Style:** REST (JSON over HTTPS)
- **Versioning:** URI-based (`/api/v1/...`)
- **Authentication:** Bearer token (JWT)
- **Rate Limiting:** 100 req/min/user, 429 Too Many Requests
- **Pagination:** Cursor-based for lists
- **Error Format:** `{"error": "ERROR_CODE", "message": "...", "details": {...}}`

---

## SECTION 6: INFRASTRUCTURE & DEPLOYMENT

### 6.1. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     CLOUDFLARE (Global Edge)                         │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│   │  │  Pages   │  │ Workers  │  │    R2    │  │    KV    │            │   │
│   │  │ (Static) │  │(Functions│  │(Storage) │  │ (Cache)  │            │   │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      │ HTTPS                                │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      GCP (asia-southeast1)                           │   │
│   │                                                                       │   │
│   │  ┌────────────────────────────────────────────────────────────────┐ │   │
│   │  │                     Cloud Run (Orchestrator)                    │ │   │
│   │  │    Min: 0, Max: 10 instances                                   │ │   │
│   │  │    CPU: 1, Memory: 512MB                                       │ │   │
│   │  │    Concurrency: 80 requests/instance                           │ │   │
│   │  └────────────────────────────────────────────────────────────────┘ │   │
│   │                                                                       │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐                           │   │
│   │  │Firestore │  │ Pub/Sub  │  │ Scheduler│                           │   │
│   │  │(Database)│  │ (Queue)  │  │  (Cron)  │                           │   │
│   │  └──────────┘  └──────────┘  └──────────┘                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      GPU PROVIDERS                                    │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│   │  │  Self-hosted │  │   Vast.ai    │  │   RunPod     │              │   │
│   │  │   (Tier 0)   │  │   (Tier 1)   │  │  (Tier 2-3)  │              │   │
│   │  │  Always On   │  │  On-demand   │  │  On-demand   │              │   │
│   │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│   │                                                                       │   │
│   │  ┌──────────────────────────────────────────────────────────────────┐│   │
│   │  │                    VIP Cluster (Tier 4)                          ││   │
│   │  │              Isolated, Always On, E2E Encryption                 ││   │
│   │  └──────────────────────────────────────────────────────────────────┘│   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2. Container Orchestration

| Component | Deployment Strategy | Scaling |
|---|---|---|
| Orchestrator (Cloud Run) | Automatic deployment on push | 0-10 instances, CPU-based autoscale |
| Workers (GPU) | Docker containers, on-demand | 0-1 per tier (Phase 1), 0-N (Phase 3) |

### 6.3. Environments

| Environment | Purpose | Infrastructure |
|---|---|---|
| **Local** | Development | Docker Compose, MinIO, Firestore Emulator, Redis |
| **Staging** | Pre-production testing | Cloudflare (free), GCP (minimal), Tier 0 only |
| **Production** | Live system | Full Cloudflare + GCP, all tiers |

### 6.4. CI/CD Pipeline Overview

```
Code Push → Lint/Test → Build → Deploy Staging → Integration Tests → Manual Approval → Deploy Production
```

---

## SECTION 7: SECURITY

### 7.1. Authentication & Authorization

**Authentication:**
- JWT-based with access token (1h) + refresh token (30d)
- OAuth 2.0 for Google and GitHub
- Passwords hashed with bcrypt (cost 12)

**Authorization:**

| Role | Permissions |
|---|---|
| **Anonymous** | View public pages only |
| **User** | CRUD own resources (jobs, files), view own billing |
| **Admin** | All user permissions + view all jobs, manage dead letter queue, manual refunds |

**Permission Levels:**
- **User-level:** All resources scoped by user_id
- **Resource-level:** Job owner can view/cancel, others get 403

### 7.2. Data Protection

| Aspect | Implementation |
|---|---|
| **Encryption at Rest** | R2: default AES-256, Firestore: Google-managed encryption |
| **Encryption in Transit** | TLS 1.3 for all connections |
| **Secrets Management** | GCP Secret Manager for API keys, Cloudflare Secrets for edge |
| **PII Handling** | No PII in logs, passwords never stored in plain text |

### 7.3. Security Controls

| Control | Description |
|---|---|
| **Input Validation** | Schema validation (Zod) for all API inputs |
| **Rate Limiting** | 100 req/min/user at edge, 10 uploads/min |
| **Audit Logging** | All write operations logged with user_id |
| **File Validation** | MIME type + magic bytes + size + virus scan (future) |
| **Dependency Scanning** | Automated Dependabot + npm audit in CI |
| **Container Scanning** | Trivy scan in CI pipeline |

---

## SECTION 8: NON-FUNCTIONAL REQUIREMENTS

### 8.1. Performance Targets

| Metric | Target | Notes |
|---|---|---|
| API Response (P95) | < 500ms | Excluding file upload |
| File Upload (50MB) | < 60s | Direct to R2 |
| Job Complete (Tier 0, 10 pages) | < 5 min | Including queue wait |
| Job Complete (Tier 4, 10 pages) | < 1 min | Premium tier |
| Concurrent Users | 100+ | Per region |

### 8.2. Scalability Strategy

| Component | Horizontal | Vertical | Notes |
|---|---|---|---|
| API Gateway (Workers) | ✅ Auto | ❌ | Cloudflare edge auto-scales |
| Orchestrator (Cloud Run) | ✅ Auto | ✅ | 0-10 instances |
| Workers (GPU) | ✅ Manual/Auto | ❌ | 0-N per tier |
| Firestore | ✅ Auto | N/A | Managed |
| R2 | ✅ Auto | N/A | Managed |

### 8.3. Availability & Disaster Recovery

| Aspect | Strategy |
|---|---|
| **Target Availability** | 99.5% (Phase 2), 99.9% (Phase 3) |
| **Database Backup** | Daily automatic (Firestore), PITR enabled |
| **Object Storage** | R2 erasure coding (11 nines durability) |
| **RPO** | 24h (MVP), 1h (Scale) |
| **RTO** | 4h (MVP), 1h (Scale) |

### 8.4. Monitoring & Alerting

**Monitoring Stack:**

| Layer | Tools | Metrics |
|---|---|---|
| Infrastructure | GCP Cloud Monitoring | CPU, Memory, Network |
| Application | Structured logs + custom metrics | Latency, Error rate, Queue depth |
| Edge | Cloudflare Analytics | Request volume, Cache hit rate |

**Key Alerts:**
1. Error rate > 5% for 5 minutes → Critical
2. Queue depth > 100 for 10 minutes → Warning
3. Worker heartbeat missing > 60s → Critical
4. Refund rate > 10% per hour → Warning
5. Storage usage > 80% → Warning
6. Payment webhook failures → Critical

---

## SECTION 9: RISKS & TRADE-OFFS

### 9.1. Kiến trúc Trade-offs đã chấp nhận

| Decision | Trade-off | Rationale |
|---|---|---|
| Firestore thay vì PostgreSQL | Limited query capabilities, no JOINs | Scale-to-zero, simple data model đủ cho use cases, tiết kiệm chi phí |
| Pub/Sub thay vì Redis Streams | Higher latency, more complex setup | Better durability, managed service, separate queues per tier dễ hơn |
| SSE thay vì WebSocket | One-way only | Simpler implementation, sufficient for push notifications, better Cloudflare compatibility |
| Workers pull thay vì push | Workers need polling logic | Simpler scaling, workers control their own load, easier recovery |
| Presigned URL thay vì streaming qua server | Extra round-trip for URL | Files không đi qua server, giảm load và bandwidth costs |
| Modular Monolith thay vì Microservices | All modules deploy together | Team nhỏ, faster development, simpler infrastructure |

### 9.2. Rủi ro chính và giảm thiểu

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Vast.ai spot instances preempted | Job failure | Medium | Retry logic, fallback to RunPod (Phase 3) |
| OCR accuracy below expectations | User churn, refunds | Medium | Clear accuracy expectations, easy refund policy, model improvements |
| Stripe integration issues | Cannot receive payments | Low | Sandbox testing, webhook retry, manual backup process |
| Firestore costs spike | Over budget | Low | Monitor usage, set budget alerts, consider migration trigger |
| DDoS attack | Service unavailable | Low | Cloudflare protection, rate limiting |
| Data breach | Reputation, legal | Low | Encryption, audit logs, security reviews |

### 9.3. Technical Debt đã biết

| Item | Description | Priority |
|---|---|---|
| No circuit breaker | External calls (Stripe, GPU providers) không có circuit breaker | P1 — trước production |
| Basic retry logic | Chưa có exponential backoff đầy đủ | P2 |
| Manual worker scaling | Phase 1 chỉ có 0/1 worker per tier | P2 — Phase 3 auto-scale |
| No caching layer | Không có Redis cache cho frequent queries | P3 — khi cần |
| Single region | Chỉ asia-southeast1 | P3 — Phase 3 multi-region |

---

## Traceability

| SA Component | BA Process | PO Feature |
|---|---|---|
| Auth Service | UC-001 (Register) | F-001 User Authentication |
| Upload Service | UC-002 (Upload) | F-002 File Upload |
| Job Service | UC-003 (Submit), UC-004 (Track) | F-003 OCR Processing, F-004 Job Tracking |
| OCR Worker | UC-003 (Submit) | F-003 OCR Processing |
| Billing Service | UC-006 (Top Up) | F-006 Credit System |
| Notification Service | - | F-008 In-app Notifications |
| R2 Storage | UC-002, UC-005 | F-002, F-005 |
| Firestore | All | All |

---

*Lưu ý: Tài liệu này cung cấp cái nhìn high-level về kiến trúc hệ thống. Chi tiết implementation và configuration được mô tả trong các tài liệu:*
- *SA_02_mid_level_design.md — cho component interaction và API contracts*
- *SA_03_low_level_design.md — cho infrastructure và deployment details*
