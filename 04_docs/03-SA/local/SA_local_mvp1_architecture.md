# OCR Platform — Local MVP Phase 1 System Architecture Document (SAD)

> Kiến trúc hệ thống cho Phase 1 Local MVP
> Version: 3.1 | Status: Draft
> References: `01-PO/local/PO_phase1_local.md`, `02-BA/local/BA_business_analysis.md`, `Scope_Requirements.md`

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

OCR Platform Local MVP là một **local demo của production system** — sử dụng production-grade components (NATS JetStream, MinIO) chạy trong Docker để mirror cloud architecture. Mục tiêu là validate và demo full system locally trước khi deploy lên cloud, đồng thời đảm bảo cùng codebase chạy được ở cả hai môi trường.

Phạm vi kiến trúc bao gồm: React frontend và MinIO object storage ở Edge layer, FastAPI backend (chứa Orchestrator + File Proxy) cùng NATS JetStream và SQLite ở Orchestration layer, và OCR worker ở Processing layer. Architecture sẵn sàng để add thêm OCR services mà không cần refactor. Tất cả chạy với một lệnh `docker compose up`.

**Phase 1 scope (theo Requirements):**
- 1 method (`ocr_text_raw`), 1 tier (Tier 0 — Local).
- Upload batch files, xem status bằng polling, xem/download kết quả.
- Auth đơn giản (email/password), chưa có billing (mọi request miễn phí).
- Orchestrator là single process chạy cùng backend server.
- Khoá các quyết định kiến trúc cốt lõi: job lifecycle, data flow pattern (File Proxy), data model, layer separation (Storage ở Edge, File Proxy ở Orchestration), service authentication interface.

### 1.2. Design Principles

| Principle | Description |
|---|---|
| **Production Parity** | Demo phải mirror production architecture nhiều nhất có thể. Sử dụng production-grade components (NATS, MinIO) thay vì mock/in-memory. Đảm bảo cùng code chạy được ở cả local và cloud. Data flow pattern (Worker → File Proxy → Storage) giống production. |
| **No Layer Bypassing** | Mỗi layer chỉ giao tiếp trực tiếp với layer liền kề, không vượt cấp. Worker (Processing) KHÔNG truy cập trực tiếp Storage (Edge). Mọi file access từ Processing layer phải qua File Proxy (Orchestration). Orchestration layer giao tiếp với Edge layer để access Storage. |
| **Multi-Service Ready** | Architecture thiết kế để add thêm OCR services (table, handwriting, structured extract, etc.) mà không cần refactor. Subject-based queue routing với required filters. Mỗi service có worker riêng với access_key. Workers declare `supported_output_formats` at registration for dynamic format discovery. |
| **Layer Separation** | 3 layers rõ ràng: Edge (API + Frontend + Object Storage), Orchestration (Job Management + File Proxy + Queue + Database), Processing (OCR Workers). Mỗi layer có trách nhiệm riêng biệt, giao tiếp qua well-defined interfaces. |
| **Fail-Safe Processing** | Mọi job failure phải được handle gracefully. Retry mechanism với exponential backoff tại tầng orchestrator. Error classification để phân biệt retriable vs non-retriable errors. Dead letter queue cho jobs vượt quá max retries. |
| **Soft Delete Everything** | Không hard delete ngay — files move to deleted bucket, metadata giữ `deleted_at`. Users có thể recover trong 7 ngày. Audit trail preserved. |
| **Observable by Default** | Mọi state transition được log. Job status trackable qua polling. Error history preserved để debug. Heartbeat từ workers cung cấp capacity và health signals. Web UIs cho NATS và MinIO để debug. |

### 1.3. Key Features

| Feature | Description |
|---|---|
| **3-Layer Architecture** | Edge (API + Frontend + Object Storage), Orchestration (Job Management + File Proxy + Queue + Database), Processing (OCR Workers). Storage nằm ở Edge layer theo đúng requirement. Layers giao tiếp qua well-defined interfaces, không vượt cấp. |
| **File Proxy Service** | Module trung gian trong Orchestration layer, là điểm duy nhất ngoài Edge có storage credentials. Worker (Processing) phải gọi File Proxy để download/upload files. File Proxy gọi sang Edge layer (Object Storage) để thực hiện file operations. |
| **Service Registration & Authentication** | Mỗi OCR Service được Admin đăng ký và cấp access_key. Service dùng key này để authenticate với File Proxy và pull jobs từ queue. Service không đăng ký → không thể hoạt động. |
| **NATS JetStream Queue** | Sử dụng NATS JetStream với native subject-based routing. Subject pattern: `{task}.{method}.tier{tier}`. Message persistence đảm bảo không mất jobs khi restart. Sẵn sàng cho multi-service expansion. |
| **Full Job State Machine** | Job lifecycle đầy đủ: SUBMITTED → VALIDATING → QUEUED → PROCESSING → COMPLETED / PARTIAL_SUCCESS / FAILED / CANCELLED / DEAD_LETTER. State machine transitions defined trong `state_machine.py`. **Note:** Không có RETRYING state, retry path là FAILED → QUEUED trực tiếp. |
| **Exponential Backoff Retry** | **⚠️ STUB** — Design: Retry tại tầng orchestrator (không retry trong worker). Retry mechanism với delay tăng dần (1s → 2s → 4s). `RetryOrchestrator` class tồn tại nhưng các methods chưa implement. |
| **Batch Processing** | Một request chứa nhiều files (max 20). Partial success handling — files thành công không bị block bởi files thất bại. Download kết quả riêng lẻ hoặc ZIP. |
| **Heartbeat Protocol** | Worker gửi heartbeat mỗi 30s, Orchestrator nhận và trả action response (`continue`/`approved`/`drain`/`shutdown`). **⚠️ Background monitor** (phát hiện worker dead/stalled) chưa implement — `HeartbeatMonitor` class tồn tại nhưng là stub. Worker chết sẽ giữ status ACTIVE trong DB. |
| **Configurable Parameters** | Timeout, max retries, file limits, output format, retention đều configurable. Không cần rebuild để thay đổi parameters. |
| **Soft Delete & Recovery** | Files không bị hard delete — move to deleted bucket. Users có thể recover trong 7 ngày. Audit trail preserved cho compliance. |

---

## SECTION 2: ARCHITECTURE OVERVIEW

### 2.1. Architectural Style

| Trường | Nội dung |
|---|---|
| **Architecture Pattern** | **Modular Monolith với Worker Separation**. Backend là một monolith chứa các modules (Auth, Upload, Job, File Proxy). Worker là process riêng biệt communicate qua Queue và File Proxy API. Frontend là SPA riêng biệt. Object Storage là infrastructure service thuộc Edge layer. |
| **Tại sao chọn pattern này?** | Team size nhỏ (2-3 dev), timeline ngắn (6 weeks), complexity vừa phải. Modular monolith cho phép phát triển nhanh, dễ debug, trong khi vẫn giữ boundaries rõ ràng giữa modules và layers. Worker tách riêng vì cần process isolation, không được access storage trực tiếp (phải qua File Proxy), và có thể scale độc lập trong tương lai. |
| **Khi nào cần chuyển đổi?** | Khi cần scale worker independently (Phase 3), hoặc khi team > 5 dev và cần deploy modules riêng. Trigger: queue depth thường xuyên > 100 jobs, hoặc processing latency không đáp ứng SLA. File Proxy có thể tách thành service riêng khi cần scale independently. |

**Queue Pattern bổ sung:**

Hệ thống sử dụng **Subject-based Queue Routing** pattern. Mỗi job được publish với subject chứa thông tin routing (task, method, tier). Workers subscribe với filter cụ thể để chỉ nhận jobs phù hợp với capabilities của mình.

Pattern này cho phép:
- Phase 1: Một worker subscribe filter cụ thể `ocr.text_raw.tier0`
- Phase 2+: Workers chuyên biệt theo method hoặc tier (e.g., `ocr.table.tier0`, `ocr.text_raw.tier1`)

### 2.2. High-Level Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                      OCR PLATFORM — LOCAL MVP PHASE 1                              │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐ │
│  │                                EDGE LAYER                                     │ │
│  │         Nhận request từ client, lưu trữ file, phục vụ giao diện web          │ │
│  │                         Không xử lý logic nghiệp vụ                           │ │
│  │                                                                               │ │
│  │   ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐    │ │
│  │   │   WEB FRONTEND    │    │    API SERVER      │    │  OBJECT STORAGE   │    │ │
│  │   │   (React SPA)     │◄──▶│ (FastAPI+Uvicorn)  │───▶│     (MinIO)       │    │ │
│  │   │                   │HTTP│                    │S3  │                   │    │ │
│  │   │ • Login/Register  │    │ • REST endpoints   │API │ Buckets:          │    │ │
│  │   │ • Batch Upload    │    │ • File upload      │    │ • uploads         │    │ │
│  │   │ • Request Status  │    │ • Authentication   │    │ • results         │    │ │
│  │   │ • Result Viewer   │    │ • Request validate │    │ • deleted         │    │ │
│  │   │ • Download Mgr    │    │ • Route to modules │    │                   │    │ │
│  │   │                   │    │                    │    │ S3-compatible API  │    │ │
│  │   └───────────────────┘    └────────┬───────────┘    └─────────┬─────────┘    │ │
│  │                                     │                          │               │ │
│  └─────────────────────────────────────┼──────────────────────────┼───────────────┘ │
│                                        │ internal calls           │ storage creds   │
│                                        │                          │ (Edge ↔ Orch)   │
│  ┌─────────────────────────────────────┼──────────────────────────┼───────────────┐ │
│  │                    ORCHESTRATION LAYER                          │               │ │
│  │        Xử lý logic nghiệp vụ, điều phối job, quản lý services │               │ │
│  │                                                                │               │ │
│  │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┴─────────┐    │ │
│  │   │ AUTH MODULE  │ │UPLOAD MODULE │ │  JOB MODULE  │ │   FILE PROXY     │    │ │
│  │   │              │ │              │ │              │ │     MODULE       │    │ │
│  │   │ • Register   │ │ • Validate   │ │ • Create req │ │                  │    │ │
│  │   │ • Login/Out  │ │ • Store file │ │ • Create jobs│ │ • Auth service   │    │ │
│  │   │ • Session    │ │   (via Edge  │ │ • Status qry │ │   (access_key)   │    │ │
│  │   │              │ │    Storage)  │ │ • Retry logic│ │ • ACL check      │    │ │
│  │   │              │ │              │ │ • Heartbeat  │ │ • Stream files   │    │ │
│  │   │              │ │              │ │ • Cancel     │ │   from/to Edge   │    │ │
│  │   │              │ │              │ │              │ │   Storage        │    │ │
│  │   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────────────────┘    │ │
│  │          │                │                │                                   │ │
│  │          ▼                ▼                ▼                                   │ │
│  │   ┌──────────────────────────────────────────────────────────────────────┐    │ │
│  │   │                   ORCHESTRATION INFRASTRUCTURE                       │    │ │
│  │   │                                                                      │    │ │
│  │   │   ┌──────────────────────┐           ┌──────────────────────┐        │    │ │
│  │   │   │       SQLite         │           │   NATS JETSTREAM     │        │    │ │
│  │   │   │      DATABASE        │           │     (Docker)         │        │    │ │
│  │   │   │                      │           │                      │        │    │ │
│  │   │   │ • users, sessions    │           │ Subjects:            │        │    │ │
│  │   │   │ • requests, jobs     │           │ • ocr.{method}.      │        │    │ │
│  │   │   │ • files, services    │           │   tier{tier}         │        │    │ │
│  │   │   │ • heartbeats         │           │                      │        │    │ │
│  │   │   │                      │           │ Dead Letter:         │        │    │ │
│  │   │   │                      │           │ • dlq.ocr.>          │        │    │ │
│  │   │   └──────────────────────┘           └──────────┬───────────┘        │    │ │
│  │   │                                                 │                    │    │ │
│  │   └─────────────────────────────────────────────────┼────────────────────┘    │ │
│  │                                                     │                         │ │
│  └─────────────────────────────────────────────────────┼─────────────────────────┘ │
│                                                        │                           │
│                                                        │ pull with filter          │
│                                                        │ (specific subject)        │
│                                                        ▼                           │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                            PROCESSING LAYER                                   │  │
│  │              Chỉ xử lý OCR, không có business logic                           │  │
│  │                                                                               │  │
│  │   ┌───────────────────────────────────────────────────────────────────────┐  │  │
│  │   │                          OCR WORKER                                    │  │  │
│  │   │              (has access_key, NO storage credentials)                  │  │  │
│  │   │                                                                        │  │  │
│  │   │   ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐         │  │  │
│  │   │   │  POLL    │─▶│  DOWNLOAD  │─▶│   OCR    │─▶│   UPLOAD   │         │  │  │
│  │   │   │  QUEUE   │  │  via FILE  │  │ PROCESS  │  │  via FILE  │         │  │  │
│  │   │   │  (NATS)  │  │   PROXY    │  │ (Engine) │  │   PROXY    │         │  │  │
│  │   │   └──────────┘  └────────────┘  └────┬─────┘  └────────────┘         │  │  │
│  │   │                                      │                                │  │  │
│  │   │                                 Error?                                │  │  │
│  │   │                                 ┌────┴────┐                           │  │  │
│  │   │                            Retriable   Non-retriable                  │  │  │
│  │   │                                 │           │                         │  │  │
│  │   │                                 ▼           ▼                         │  │  │
│  │   │                          [Report to Orchestrator]                     │  │  │
│  │   │                       (Orchestrator handles retry)                    │  │  │
│  │   │                                                                        │  │  │
│  │   │   HEARTBEAT ──▶ sends status, progress, errors to Orchestrator        │  │  │
│  │   │   CLEANUP   ──▶ delete all local files after processing               │  │  │
│  │   │                                                                        │  │  │
│  │   └───────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                               │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  Access Points:                                                                     │
│  • Frontend:      http://localhost:3000                                             │
│  • API:           http://localhost:8000/api/v1                                      │
│  • MinIO Console: http://localhost:9001 (browse stored files)                       │
│                                                                                     │
│  KEY RULES:                                                                         │
│  • Object Storage (MinIO) thuộc EDGE LAYER — nhận file từ client, phục vụ download │
│  • File Proxy thuộc ORCHESTRATION LAYER — cầu nối duy nhất (ngoài Edge) access      │
│    Storage. File Proxy gọi sang Edge Storage bằng storage credentials.              │
│  • Worker thuộc PROCESSING LAYER — KHÔNG có storage credentials, gọi File Proxy.   │
│  • Luồng: Worker → File Proxy (Orch) → Object Storage (Edge)                       │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3. Layer Responsibilities Summary

Trước khi đi vào chi tiết từng component, cần hiểu rõ ranh giới trách nhiệm giữa 3 layers. Đây là quyết định kiến trúc cốt lõi được khoá từ Phase 1 theo requirement:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER RESPONSIBILITIES                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   EDGE LAYER — "Cổng vào + Kho chứa"                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  ✓ Nhận request từ client (API Server)                      │   │
│   │  ✓ Phục vụ giao diện web (Frontend SPA)                     │   │
│   │  ✓ Lưu trữ file — Object Storage (MinIO)                   │   │
│   │  ✗ KHÔNG xử lý logic nghiệp vụ                             │   │
│   │  ✗ KHÔNG điều phối job                                       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ORCHESTRATION LAYER — "Bộ não điều phối"                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  ✓ Xử lý logic nghiệp vụ (Job Module, Auth Module)         │   │
│   │  ✓ Điều phối job (Queue — NATS JetStream)                   │   │
│   │  ✓ Lưu metadata (Database — SQLite)                         │   │
│   │  ✓ File Proxy — cầu nối duy nhất (ngoài Edge) access        │   │
│   │    Storage, kiểm soát ai được lấy file nào                   │   │
│   │  ✗ KHÔNG lưu trữ binary files                               │   │
│   │  ✗ KHÔNG xử lý OCR                                          │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   PROCESSING LAYER — "Nhà máy xử lý"                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  ✓ Xử lý OCR (Tesseract/PaddleOCR/EasyOCR)                   │   │
│   │  ✓ Gửi heartbeat về Orchestrator                             │   │
│   │  ✓ Gọi File Proxy để download/upload files                   │   │
│   │  ✗ KHÔNG có storage credentials                              │   │
│   │  ✗ KHÔNG truy cập Object Storage trực tiếp                   │   │
│   │  ✗ KHÔNG có business logic                                   │   │
│   │  ✗ KHÔNG retry (report lỗi về Orchestrator)                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   Giao tiếp chỉ giữa layers liền kề:                               │
│                                                                      │
│   Client ←→ Edge ←→ Orchestration ←→ Processing                    │
│                                                                      │
│   ✗ Client → Orchestration (vượt cấp)                              │
│   ✗ Processing → Edge/Storage (vượt cấp)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4. Danh sách thành phần chính và trách nhiệm

#### 2.4.1. Web Frontend — React SPA (Edge Layer)

Web Frontend là Single Page Application (SPA) cung cấp giao diện cho users (Dev/QA) tương tác với hệ thống. Frontend giao tiếp với API Server qua HTTP REST calls.

Frontend bao gồm các pages: Login/Register để authenticate, Dashboard hiển thị recent requests, Upload page với drag-drop và file picker hỗ trợ batch upload (tối đa 20 files) kèm lựa chọn output format và retention, Request Status page hiển thị progress của batch với individual job statuses, và Result Viewer để xem/download kết quả OCR.

Luồng xử lý chính:
```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   Login    │───▶│  Dashboard │───▶│   Upload   │───▶│   Status   │───▶ View Result
└────────────┘    └────────────┘    │ + Config   │    └────────────┘
                                    │(format,    │
                                    │ retention) │
                                    └────────────┘
```

#### 2.4.2. API Server — FastAPI (Edge Layer)

API Server là entry point cho tất cả HTTP requests từ frontend. Sử dụng **FastAPI** với Uvicorn ASGI server cho async I/O performance. Server thực hiện authentication check (validate session), request validation (Pydantic schemas), và routing đến các internal modules trong Orchestration layer.

API Server nằm ở Edge layer vì nó trực tiếp nhận request từ client. Tuy nhiên, nó delegate tất cả business logic sang Orchestration layer modules. API Server cũng có quyền truy cập Object Storage (MinIO) vì cùng nằm trong Edge layer — dùng cho upload files từ client và serve download requests.

FastAPI auto-generate OpenAPI docs tại `/docs` (Swagger UI) và `/redoc`.

#### 2.4.3. Object Storage — MinIO (Edge Layer)

MinIO là S3-compatible object storage **nằm ở Edge layer** theo đúng requirement: "Edge layer nhận request từ client, lưu trữ file (object storage), phục vụ giao diện web."

**Tại sao Object Storage thuộc Edge layer?**

Object Storage đóng vai trò "kho chứa" cho files mà client upload lên và download về. Nó là nơi đầu tiên file được lưu khi client gửi lên (qua API Server cùng Edge layer), và là nơi cuối cùng client lấy kết quả về. Đây là trách nhiệm của Edge layer — tiếp nhận và phục vụ dữ liệu cho client.

Orchestration layer (File Proxy) có storage credentials để đọc/ghi files, nhưng **File Proxy không sở hữu storage** — nó chỉ là proxy. Processing layer (Worker) thì hoàn toàn không có storage credentials.

**Buckets:**

| Bucket | Purpose | Who Writes | Who Reads |
|---|---|---|---|
| `uploads` | Source files từ client | API Server (Edge) | File Proxy (Orch) → stream to Worker |
| `results` | OCR output | File Proxy (Orch) ← upload from Worker | API Server (Edge) → serve to client |
| `deleted` | Soft-deleted files | File Proxy (Orch) moves here | File Proxy (Orch) for recovery |

**Quyền truy cập MinIO:**

| Entity | Layer | Có Storage Credentials? | Lý do |
|---|---|---|---|
| API Server | Edge | ✅ | Cùng Edge layer với Storage. Upload files từ client, serve downloads. |
| Upload Module | Orchestration (via Edge) | ✅ (gọi qua API Server context) | Upload module chạy trong API Server process, dùng credentials của Edge. |
| File Proxy | Orchestration | ✅ | Là cầu nối duy nhất (ngoài Edge) được phép access Storage. Dùng credentials riêng hoặc shared với Edge. |
| OCR Worker | Processing | ❌ | Vượt cấp nếu access trực tiếp. Phải gọi File Proxy. |

#### 2.4.4. Auth Module (Orchestration Layer)

Auth Module quản lý user authentication với simple email/password flow. Module thực hiện user registration (validate email uniqueness, hash password với bcrypt), login (verify credentials, create session), và session management (validate token, logout).

Session được lưu trong SQLite với expiry time. Token trả về client qua cookie hoặc response body. Mỗi API request cần kèm token để authenticate.

**Phase 2 sẽ thêm:** OAuth (Google, GitHub), rate limiting per user.

#### 2.4.5. Upload Module (Orchestration Layer)

Upload Module xử lý file uploads và validation. Luồng xử lý:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Receive   │───▶│   Validate  │───▶│    Store    │───▶│   Create    │
│    Files    │    │  Each File  │    │  to MinIO   │    │ File Record │
│  (via API   │    │             │    │ (Edge layer │    │  (in DB)    │
│   Server)   │    │             │    │  Storage)   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

Validation bao gồm: kiểm tra MIME type và magic bytes (chỉ PNG, JPEG, PDF), kiểm tra file size (max 10MB per file), kiểm tra batch size (max 50MB total, max 20 files), và đếm pages cho PDF. Files invalid được skip với warning, files valid tiếp tục xử lý.

Files được upload lên MinIO bucket `uploads` với object key: `{user_id}/{request_id}/{file_id}.{ext}`. Module tạo record trong database để track file metadata và object key. MinIO S3-compatible API đảm bảo cùng code sẽ hoạt động với cloud storage ở Phase 2.

**Lưu ý về layer access:** Upload Module nằm trong Orchestration layer nhưng chạy trong cùng process với API Server (Edge layer). Khi Upload Module cần ghi file vào MinIO, nó sử dụng storage credentials có sẵn trong API Server context (Edge layer). Đây là giao tiếp hợp lệ giữa hai layers liền kề (Orchestration → Edge). Chỉ Processing layer mới bị cấm access Storage trực tiếp.

#### 2.4.6. Job Module (Orchestration Layer)

Job Module là core của orchestration, quản lý lifecycle của requests và jobs. Khi user click "Process All", module thực hiện:

1. **Validate** request configuration (method, tier, output_format, retention).
2. Tạo **Request record** chứa tất cả files + configuration.
3. Tạo **Job record** cho mỗi file, initial status = SUBMITTED.
4. Validate từng file (format, integrity) → status = VALIDATING → QUEUED hoặc REJECTED.
5. Publish valid jobs vào Queue với subject pattern `ocr.{method}.tier{tier}`.

Job Module cũng đảm nhiệm:
- **Status queries**: Aggregate job statuses để tính request status (PROCESSING nếu có job đang chạy, COMPLETED nếu tất cả done, PARTIAL_SUCCESS nếu mix success/fail).
- **Retry orchestration**: Khi worker report job failure với retriable error, Job Module quyết định retry hoặc move to dead letter.
- **Heartbeat processing**: Nhận heartbeat từ workers, detect dead/stalled workers, reassign jobs nếu cần.
- **Cancel handling**: Cho phép cancel jobs đang QUEUED (chưa bắt đầu xử lý).

**Phase 2 sẽ thêm:** Billing hooks (credit check trước submit, deduct & hold, finalize/refund), notification triggers.

#### 2.4.7. File Proxy Module (Orchestration Layer)

File Proxy Module là **cầu nối duy nhất ngoài Edge layer** cho phép Processing layer (Workers) access files trong Object Storage (Edge layer). Module này nằm trong Backend monolith ở Phase 1 (có thể tách thành service riêng ở Phase 2+).

**Vị trí trong kiến trúc:**
- File Proxy nằm ở **Orchestration layer**.
- Object Storage (MinIO) nằm ở **Edge layer**.
- File Proxy có storage credentials để gọi sang Edge layer — đây là giao tiếp hợp lệ giữa layers liền kề.
- Processing layer (Worker) gọi File Proxy — cũng là giao tiếp giữa layers liền kề.
- Kết quả: Worker → File Proxy (Orch) → Storage (Edge) — mỗi bước đều chỉ giao tiếp với layer liền kề.

**Trách nhiệm:**
- Authenticate OCR Service qua access_key (được Admin cấp khi đăng ký service).
- Kiểm tra quyền truy cập: service X có được access file Y không.
- Gọi sang Edge layer (MinIO) để stream files cho Worker (download) hoặc nhận files từ Worker (upload result).
- Log mọi file access cho audit trail.

**Tại sao cần File Proxy thay vì cho Worker access trực tiếp MinIO?**
- **Layer Separation**: Requirement nói rõ: "Mỗi layer chỉ giao tiếp trực tiếp với layer liền kề, không vượt cấp." Worker (Processing) → Storage (Edge) là vượt cấp. Phải đi qua File Proxy (Orchestration).
- **Security**: Worker có thể chạy trên infrastructure không tin cậy (cloud GPU, spot instances). Không nên cấp storage credentials.
- **Access Control**: File Proxy kiểm soát chặt chẽ ai được lấy file nào. Worker chỉ access được files thuộc jobs mà nó đang xử lý.
- **Audit**: Mọi file access đều đi qua một điểm, dễ log và audit.
- **Production Parity**: Requirement yêu cầu pattern này cho production. Phase 1 implement sẵn để không cần refactor.

**API Endpoints (internal):**

| Endpoint | Method | Description |
|---|---|---|
| `POST /internal/file-proxy/download` | POST | Worker download source file. Body: `{job_id, access_key}` |
| `POST /internal/file-proxy/upload` | POST | Worker upload result file. Body: `{job_id, access_key, file}` |

**Luồng xử lý download (minh hoạ layer communication):**

```
Processing Layer          Orchestration Layer           Edge Layer
  Worker                    File Proxy                   MinIO (Storage)
    │                          │                            │
    │  POST /download          │                            │
    │  {job_id, access_key}    │                            │
    │─────────────────────────►│                            │
    │                          │  1. Verify access_key      │
    │                          │  2. Check job→file ACL     │
    │                          │  3. Get file object_key    │
    │                          │     from DB                │
    │                          │                            │
    │                          │  S3 GetObject              │
    │                          │───────────────────────────►│
    │                          │◄──────────────────────────│
    │   Stream file            │                            │
    │◄─────────────────────────│                            │
    │                          │                            │

    Layer adjacency: Worker→FileProxy (Processing→Orch) ✓
                     FileProxy→MinIO (Orch→Edge) ✓
                     Worker→MinIO (Processing→Edge) ✗ KHÔNG CHO PHÉP
```

**Phase 1 Simplification:** File Proxy chạy như module trong Backend (cùng process). access_key validation đơn giản (static key per service trong config). Phase 2 sẽ thêm dynamic key management qua Admin dashboard, và có thể tách File Proxy thành service riêng.

#### 2.4.8. NATS JetStream Queue (Orchestration Layer)

NATS JetStream là message broker chạy trong Docker container, nằm trong **Orchestration layer** vì chức năng chính là điều phối jobs (logic nghiệp vụ). Hỗ trợ native subject-based routing và message persistence. Mỗi job message chứa: job_id, request_id, file_id, method, tier, output_format, retry_count, và error_history.

**Subject Pattern:**
```
{task}.{method}.tier{tier}

Trong đó:
- task: Loại tác vụ (ocr, preprocess, postprocess, etc.)
- method: Phương thức cụ thể (text_raw, table, formatted, etc.)
- tier: Infrastructure tier (tier0=local, tier1=cloud, etc.)

Phase 1:
- ocr.text_raw.tier0             → OCR text extraction trên local
- ocr.structured_extract.tier0   → Structured data extraction (tables, layouts) trên local

Phase 2+:
- ocr.table.tier1           → OCR table extraction trên cloud
- ocr.formatted.tier0       → OCR formatted trên local
- preprocess.deskew.tier0   → Preprocessing deskew
- postprocess.format.tier0  → Postprocessing format conversion
```

**Dead Letter Queue:**

Jobs vượt quá max retries (3 lần) được move sang Dead Letter Queue:

```
Dead Letter Subject: dlq.ocr.{method}.tier{tier}
Ví dụ: dlq.ocr.text_raw.tier0
```

Jobs trong DLQ có status = DEAD_LETTER. Phase 1: admin review manually. Phase 2: auto-refund credit và notify user.

**Consumer Configuration:**

Mỗi worker subscribe với filter **cụ thể** — không dùng wildcards:

| Worker | Subscribe Subject | Description |
|---|---|---|
| `worker-ocr-text-tier0` | `ocr.text_raw.tier0` | OCR text extraction local |
| `worker-ocr-structured-tier0` | `ocr.structured_extract.tier0` | Structured data extraction local (PaddleOCR-VL) |
| `worker-ocr-table-tier0` | `ocr.table.tier0` | OCR table extraction local (Phase 2) |
| `worker-ocr-text-tier1` | `ocr.text_raw.tier1` | OCR text extraction cloud (Phase 2) |

**Multi-Service Ready:**

Architecture hỗ trợ thêm OCR services mới bằng cách:
1. Admin đăng ký service mới và cấp access_key.
2. Define new subject (e.g., `ocr.handwriting.tier0`).
3. Deploy new worker với filter tương ứng và access_key.
4. Update Job Module để route jobs đến subject mới.

Không cần thay đổi core queue infrastructure, File Proxy, hay storage system.

#### 2.4.9. OCR Worker (Processing Layer)

Worker là separate process chạy độc lập, poll queue để nhận jobs. Worker được cấp **access_key** để authenticate với File Proxy, nhưng **KHÔNG có storage credentials**.

**Quy tắc quan trọng:**
- Worker KHÔNG truy cập Object Storage (Edge layer) trực tiếp — đây là vượt cấp.
- Worker gọi File Proxy API (Orchestration layer) để download source files và upload results — giao tiếp giữa layers liền kề.
- Worker gửi heartbeat định kỳ về Orchestrator.
- Worker xoá tất cả local files sau khi xử lý xong (cleanup).
- Trong worker, không retry: failure ở bất kỳ bước nào → report fail về Orchestrator. Retry logic nằm ở tầng Orchestrator.

**Luồng xử lý chi tiết:**

1. **Poll Queue**: Worker gọi `queue.pull(filter="ocr.text_raw.tier0")`. Nếu không có job, wait `WORKER_POLL_INTERVAL_MS` rồi poll lại.

2. **Notify Orchestrator**: Nhận job → gọi Orchestrator API để update status sang PROCESSING, set started_at timestamp.

3. **Download File via File Proxy**: Gọi `POST /internal/file-proxy/download` với job_id và access_key. File Proxy (Orch layer) verify quyền, gọi sang MinIO (Edge layer), stream file về worker.

4. **OCR Process**: Gọi OCR engine (Tesseract/PaddleOCR/EasyOCR) để extract text. Có timeout protection (`JOB_TIMEOUT_SECONDS`). Output format theo request configuration (Phase 1: `txt`).

5. **Upload Result via File Proxy**: Gọi `POST /internal/file-proxy/upload` với job_id, access_key, và result file. File Proxy lưu vào MinIO bucket `results` (Edge layer).

6. **Update Status**: Gọi Orchestrator API → COMPLETED với result_path và processing_time. Hoặc report error nếu failure.

7. **Cleanup**: Xoá tất cả downloaded files và generated results khỏi local disk.

**Heartbeat Protocol:**

Worker gửi heartbeat định kỳ về Orchestrator (default: mỗi 30 giây):

```
POST /internal/heartbeat
{
  "service_id": "worker-ocr-text-tier0",
  "access_key": "sk_xxx",
  "status": "processing",              // idle | processing | uploading | error
  "current_job_id": "job_abc123",      // null nếu idle
  "progress": {
    "files_completed": 2,
    "files_total": 5
  },
  "started_at": "2024-01-15T10:30:00Z",
  "error_count": 0
}
```

Orchestrator dùng heartbeat data để:
- Phát hiện worker dead (mất heartbeat quá `HEARTBEAT_TIMEOUT_SECONDS`).
- Phát hiện worker stalled (heartbeat đều nhưng progress không đổi).
- Phát hiện worker unhealthy (error_count tăng liên tục).

**Error Handling trong Worker:**

Worker phân loại errors thành hai loại và **report về Orchestrator** (không tự retry):

| Error Type | Examples | Worker Action |
|---|---|---|
| Retriable | Timeout, OCR engine crash, temp file access error | Report error với `retriable=true` |
| Non-retriable | Invalid file format, corrupted file, file not found | Report error với `retriable=false` |

**Retry Logic (tại Orchestrator):**

```
┌─────────────────────┐
│Worker reports error  │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────┐     No      ┌──────────────────┐
│ Is retriable?        │────────────▶│ Mark FAILED      │
└──────────┬───────────┘             │ (terminal)       │
           │ Yes                     └──────────────────┘
           ▼
┌──────────────────────┐     No      ┌──────────────────┐
│ retry_count < max(3)?│────────────▶│ Move to DLQ      │
└──────────┬───────────┘             │ (DEAD_LETTER)    │
           │ Yes                     └──────────────────┘
           ▼
┌──────────────────────┐
│ Mark RETRYING        │
│ Increment retry_count│
│ Calculate delay:     │
│   1s × 2^(retry)     │
│ Re-publish to queue  │
│ with delay           │
└──────────────────────┘
```

**Worker Batch Pull (Phase 2+ Enhancement):**

Phase 1: Worker pull **từng job một** (1 job = 1 file) cho Tesseract (CPU-based). GPU engines (PaddleOCR, EasyOCR) có thể pull batch để tối ưu model loading.

Phase 2+: Worker sẽ support pull **nhiều requests** cùng lúc (batch pull) để tối ưu GPU model loading — load model 1 lần, process nhiều files. Interface được thiết kế sẵn để support batch pull:

```
# Phase 1: single pull
job = queue.pull(filter="ocr.text_raw.tier0", max_messages=1)

# Phase 2+: batch pull
jobs = queue.pull(filter="ocr.table.tier1", max_messages=10, max_bytes=200MB)
```

---

## SECTION 3: TECHNOLOGY STACK

### 3.1. Tech Stack Table

| Technology | Vai trò | Layer | Lý do sử dụng |
|---|---|---|---|
| **React + TypeScript** | Frontend SPA | Edge | React được chọn cho frontend vì ecosystem mature, component-based architecture phù hợp cho UI có nhiều states (upload progress, job status). TypeScript thêm type safety giúp catch errors sớm. Team đã quen với React nên giảm learning curve. Vite làm build tool cho hot reload nhanh trong development. |
| **Python + FastAPI** | Backend API Server + File Proxy | Edge (API) + Orchestration (modules) | FastAPI được chọn vì: (1) Auto-generated OpenAPI/Swagger docs, (2) Native async/await support cho I/O operations (file upload, MinIO, queue, file proxy streaming), (3) Pydantic cho request/response validation, (4) Cùng language với Worker giúp share models. API Server nằm ở Edge layer, các modules (Auth, Upload, Job, File Proxy) nằm ở Orchestration layer nhưng chạy trong cùng process ở Phase 1. |
| **MinIO** | Object Storage (S3-compatible) | **Edge** | MinIO là thành phần lưu trữ file, thuộc Edge layer theo requirement: "Edge layer nhận request từ client, lưu trữ file (object storage)." S3-compatible API đảm bảo cùng code chạy được với AWS S3, Cloudflare R2 ở Phase 2. Soft delete với versioning. Web console (port 9001) để debug. **Chỉ** Edge layer (API Server) và File Proxy (Orchestration, via credentials) access trực tiếp. Worker KHÔNG access. |
| **SQLite + WAL mode** | Relational Database | Orchestration | SQLite cho metadata storage. Zero configuration. **WAL mode** enable concurrent writes (~100 writes/sec, đủ cho 5+ workers). SQL-compatible nên migrate sang PostgreSQL ở Phase 2 dễ dàng. Database thuộc Orchestration layer vì lưu trữ metadata nghiệp vụ (jobs, requests, users). |
| **NATS JetStream** | Message Queue + DLQ | Orchestration | NATS JetStream cho job dispatching. Native subject-based routing (`ocr.text_raw.tier0`). Lightweight (~50MB RAM). Message persistence. Dead letter queue support. Thuộc Orchestration layer vì chức năng điều phối jobs. |
| **OCR Engine** | Text Extraction & Structured Extract | Processing | Pluggable OCR engine chạy trong Worker container. Phase 1 hỗ trợ nhiều options: Tesseract (CPU, default), PaddleOCR (GPU), PaddleOCR-VL/PP-Structure (GPU, structured), EasyOCR (GPU). Xem chi tiết tại Section 3.2. |
| **bcrypt** | Password Hashing | Orchestration | bcrypt standard cho password hashing. Cost factor = 10. |
| **Docker + Docker Compose** | Container Orchestration | All | Docker Compose chạy toàn bộ stack. Mỗi component là container riêng. Volume mounts cho development. |

**Environment-specific Notes:**

- Phase 1 (Local Demo): MinIO (Edge, Docker) + SQLite + NATS JetStream (Orchestration, Docker) + File Proxy (module in Backend)
- Phase 2 (Cloud): Cloudflare R2/AWS S3 (Edge) + PostgreSQL + NATS JetStream Cluster (Orchestration) + File Proxy (separate service)

### 3.2. OCR Engine Options

Phase 1 hỗ trợ nhiều OCR engines, cho phép chọn engine phù hợp với use case và hardware availability.

| Engine | Hardware | Accuracy | Speed | Vietnamese | Docker Image Size | Use Case |
|--------|----------|----------|-------|------------|-------------------|----------|
| **Tesseract 5.x** | CPU only | Medium | Slow | ✅ Good | ~500MB | Default. Low cost, simple deployment. |
| **PaddleOCR** | GPU (CUDA) / CPU fallback | High | Fast | ✅ Excellent | ~3GB | High accuracy, text extraction, batch processing. |
| **PaddleOCR-VL (PP-Structure)** | GPU (CUDA) | High | Medium | ✅ Excellent | ~4GB | Structured data extraction: layout analysis, table recognition, form parsing. Output: json, md. |
| **EasyOCR** | GPU (CUDA) / CPU fallback | High | Medium | ✅ Good | ~2GB | Easy setup, 80+ languages. |

**Engine Selection:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OCR ENGINE SELECTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Environment Variable: OCR_ENGINE = tesseract | paddleocr | easyocr        │
│                                                                              │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│   │   TESSERACT     │     │   PADDLEOCR     │     │    EASYOCR      │       │
│   │   (Default)     │     │                 │     │                 │       │
│   ├─────────────────┤     ├─────────────────┤     ├─────────────────┤       │
│   │ • CPU only      │     │ • GPU preferred │     │ • GPU preferred │       │
│   │ • ~1GB RAM      │     │ • ~4GB VRAM     │     │ • ~2GB VRAM     │       │
│   │ • Single file   │     │ • Batch: 8-16   │     │ • Batch: 4-8    │       │
│   │ • Basic text    │     │ • Text + Table  │     │ • Text only     │       │
│   └─────────────────┘     └─────────────────┘     └─────────────────┘       │
│                                                                              │
│   Docker Compose Profiles:                                                   │
│   • docker compose --profile cpu up        → Tesseract worker               │
│   • docker compose --profile gpu up        → PaddleOCR worker (default GPU) │
│   • docker compose --profile gpu-easy up   → EasyOCR worker                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Worker Docker Images:**

| Image | Base | Size | Hardware |
|-------|------|------|----------|
| `ocr-worker-tesseract:latest` | `python:3.11-slim` | ~500MB | CPU |
| `ocr-worker-paddleocr:latest` | `paddlepaddle/paddle:2.5.1-gpu-cuda11.7-cudnn8.4-trt8.4` | ~3GB | NVIDIA GPU (CUDA 11.7+) |
| `ocr-worker-easyocr:latest` | `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime` | ~2GB | NVIDIA GPU (CUDA 11.7+) |

**Engine Interface (Pluggable):**

```python
# Tất cả engines implement cùng interface
class OCREngine(Protocol):
    def process(self, image_path: str, output_format: str) -> OCRResult:
        """Process single image, return extracted text."""
        ...

    def process_batch(self, image_paths: list[str], output_format: str) -> list[OCRResult]:
        """Process multiple images (GPU engines optimize this)."""
        ...

    def get_capabilities(self) -> EngineCapabilities:
        """Return engine capabilities (table detection, languages, etc.)."""
        ...
```

**Recommendation:**

| Scenario | Recommended Engine |
|----------|-------------------|
| Local development, no GPU | Tesseract |
| Production với GPU, tiếng Việt | PaddleOCR |
| Quick setup, multi-language | EasyOCR |
| Table/document structure extraction | PaddleOCR-VL (PP-Structure) |

---

## SECTION 4: DATA ARCHITECTURE

### 4.1. Domain Model Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOMAIN MODEL                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────┐                                                              │
│   │   USER   │                                                              │
│   └────┬─────┘                                                              │
│        │                                                                     │
│        ├── 1:N ──▶ ┌──────────┐                                             │
│        │           │ SESSION  │                                             │
│        │           └──────────┘                                             │
│        │                                                                     │
│        └── 1:N ──▶ ┌──────────┐          1:N           ┌──────────┐         │
│                    │ REQUEST  │────────────────────────▶│   JOB    │         │
│                    │          │                         │          │         │
│                    └──────────┘                         └────┬─────┘         │
│                                                              │               │
│                                              ┌───────────────┼───────────┐  │
│                                              │               │           │  │
│                                              │ 1:1           │ 1:1       │  │
│                                              ▼               ▼           │  │
│                                         ┌─────────┐    ┌─────────┐      │  │
│                                         │  FILE   │    │ RESULT  │      │  │
│                                         │         │    │(if done)│      │  │
│                                         └─────────┘    └─────────┘      │  │
│                                                                          │  │
│   ┌─────────────────────────────────────────────────────────────────┐    │  │
│   │ SERVICE REGISTRY (Phase 1: config-based, Phase 2: Admin UI)    │    │  │
│   │   ┌──────────────┐                                              │    │  │
│   │   │   SERVICE    │  access_key, allowed methods, allowed tiers  │    │  │
│   │   └──────────────┘                                              │    │  │
│   └─────────────────────────────────────────────────────────────────┘    │  │
│                                                                          │  │
│   ┌─────────────────────────────────────────────────────────────────┐    │  │
│   │ FUTURE MODULES (acknowledged, not implemented Phase 1)          │    │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │  │
│   │   │   BILLING    │  │NOTIFICATION  │  │  AUDIT LOG   │         │    │  │
│   │   │  (Phase 2)   │  │  (Phase 2)   │  │  (Phase 2)   │         │    │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘         │    │  │
│   └─────────────────────────────────────────────────────────────────┘    │  │
│                                                                          │  │
│   Relationships:                                                         │  │
│   • USER ──1:N──▶ SESSION (login sessions)                              │  │
│   • USER ──1:N──▶ REQUEST (batch submissions)                           │  │
│   • REQUEST ──1:N──▶ JOB (one job per file)                             │  │
│   • JOB ──1:1──▶ FILE (source file)                                     │  │
│   • JOB ──1:1──▶ RESULT (OCR output, only if completed)                 │  │
│   • SERVICE ──registered──▶ can pull jobs + access File Proxy            │  │
│                                                                          │  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Database Schema (SQLite — Orchestration Layer)

**Table: users**

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| email | TEXT | Unique, validated format |
| password_hash | TEXT | bcrypt hash |
| created_at | TIMESTAMP | Account creation time |
| deleted_at | TIMESTAMP | Soft delete (nullable) |

**Table: sessions**

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key (session token) |
| user_id | TEXT | FK → users.id |
| expires_at | TIMESTAMP | Session expiry |
| created_at | TIMESTAMP | Session creation time |

**Table: requests**

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| user_id | TEXT | FK → users.id |
| method | TEXT | OCR method (e.g., `text_raw`) |
| tier | INTEGER | Infrastructure tier (e.g., 0) |
| output_format | TEXT | Requested output format (e.g., `txt`, `json`, `md`). Available formats depend on service's `supported_output_formats`. |
| retention_hours | INTEGER | File retention (default 24) |
| status | TEXT | Request status (aggregated from jobs) |
| total_files | INTEGER | Total files in batch |
| completed_files | INTEGER | Successfully completed files |
| failed_files | INTEGER | Failed files |
| created_at | TIMESTAMP | Request creation time |
| completed_at | TIMESTAMP | All jobs finished (nullable) |
| deleted_at | TIMESTAMP | Soft delete (nullable) |

**Table: jobs**

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| request_id | TEXT | FK → requests.id |
| file_id | TEXT | FK → files.id |
| status | TEXT | Job status (see State Machine §4.5) |
| method | TEXT | OCR method |
| tier | INTEGER | Infrastructure tier |
| output_format | TEXT | Output format for this job |
| retry_count | INTEGER | Current retry count (default 0) |
| max_retries | INTEGER | Max allowed retries (default 3) |
| error_history | TEXT (JSON) | Array of `{error, retriable, timestamp}` |
| started_at | TIMESTAMP | Worker started processing (nullable) |
| completed_at | TIMESTAMP | Processing completed (nullable) |
| processing_time_ms | INTEGER | Actual processing time (nullable) |
| result_path | TEXT | Object key in results bucket (nullable) |
| worker_id | TEXT | Which worker processed this job (nullable) |
| created_at | TIMESTAMP | Job creation time |
| deleted_at | TIMESTAMP | Soft delete (nullable) |

**Table: files**

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| request_id | TEXT | FK → requests.id |
| original_name | TEXT | Original filename |
| mime_type | TEXT | Validated MIME type |
| size_bytes | INTEGER | File size |
| page_count | INTEGER | Number of pages (1 for images) |
| object_key | TEXT | MinIO object key in uploads bucket |
| created_at | TIMESTAMP | Upload time |
| deleted_at | TIMESTAMP | Soft delete (nullable) |
| purged_at | TIMESTAMP | Hard delete time (nullable) |

**Table: services**

| Column | Type | Description |
|---|---|---|
| id | TEXT | Service identifier (e.g., `worker-ocr-text-tier0`) |
| access_key | TEXT | Unique key for authentication with File Proxy |
| allowed_methods | TEXT (JSON) | Array of methods this service can handle |
| allowed_tiers | TEXT (JSON) | Array of tiers this service can handle |
| supported_output_formats | TEXT (JSON) | Array of output formats this service can produce (e.g. `["txt","json"]`, `["json","md"]`) |
| enabled | BOOLEAN | Whether service is active |
| created_at | TIMESTAMP | Registration time |

**Table: heartbeats**

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto-increment primary key |
| service_id | TEXT | FK → services.id |
| status | TEXT | idle, processing, uploading, error |
| current_job_id | TEXT | Job being processed (nullable) |
| files_completed | INTEGER | Progress: files done in current batch |
| files_total | INTEGER | Progress: total files in current batch |
| error_count | INTEGER | Errors in current batch |
| received_at | TIMESTAMP | When heartbeat was received |

**Phase 2 Tables (acknowledged, not implemented):**

Các bảng sau sẽ được thêm ở Phase 2 khi implement billing, notifications, và audit: `credit_transactions`, `notifications`, `audit_logs`. Schema hiện tại đã có các trường cần thiết cho billing hooks (`processing_time_ms`, `status`, `result_path` trong jobs table).

### 4.3. Chiến lược lưu trữ

| Storage Type | Công nghệ | Layer | Dữ liệu lưu trữ |
|---|---|---|---|
| **Object Storage** | MinIO (S3-compatible) | **Edge** | Binary files trong 3 buckets: `uploads`, `results`, `deleted`. Files referenced by object key trong database. API Server (Edge) và File Proxy (Orch) access trực tiếp. Worker (Processing) phải qua File Proxy. |
| **Relational Database** | SQLite | Orchestration | Metadata: users, sessions, requests, jobs, files, services, heartbeats. Structured data với relationships. |
| **Queue Storage** | NATS JetStream | Orchestration | Job messages đang chờ xử lý. Dead letter messages. Persistent trên disk. |

### 4.4. Data Flow

**Flow 1: Upload & Submit Flow**

```
Client          Edge Layer                    Orchestration Layer
Browser         API Server    MinIO(Storage)  Upload Module  Job Module  NATS Queue
  │                │              │               │             │            │
  │  POST /upload  │              │               │             │            │
  │ (files+config) │              │               │             │            │
  │───────────────►│              │               │             │            │
  │                │  delegate    │               │             │            │
  │                │─────────────────────────────►│             │            │
  │                │              │               │             │            │
  │                │              │    validate   │             │            │
  │                │              │    files      │             │            │
  │                │              │               │             │            │
  │                │              │  S3 PutObject │             │            │
  │                │              │◄──────────────│             │            │
  │                │              │  (Edge←Orch   │             │            │
  │                │              │   adjacent ✓) │             │            │
  │                │              │               │             │            │
  │                │              │               │  create req │            │
  │                │              │               │  + jobs     │            │
  │                │              │               │────────────►│            │
  │                │              │               │             │            │
  │                │              │               │             │  publish   │
  │                │              │               │             │  jobs      │
  │                │              │               │             │───────────►│
  │                │              │               │             │            │
  │  Response      │              │               │             │            │
  │◄───────────────│              │               │             │            │

  Upload Module accesses MinIO via Edge layer context (adjacent layers ✓)
```

**Flow 2: Worker Processing Flow (via File Proxy)**

```
Processing Layer     Orchestration Layer                       Edge Layer
Worker               File Proxy    Job Module   NATS Queue     MinIO(Storage)
  │                     │              │            │              │
  │                     │              │   pull     │              │
  │◄────────────────────────────────────────────────│              │
  │                     │              │            │              │
  │  notify: PROCESSING │              │            │              │
  │─────────────────────────────────── ►│           │              │
  │                     │              │            │              │
  │  POST /download     │              │            │              │
  │  {job_id, key}      │              │            │              │
  │────────────────────►│              │            │              │
  │                     │  verify key  │            │              │
  │                     │  check ACL   │            │              │
  │                     │              │            │              │
  │                     │  S3 GetObject│            │              │
  │                     │─────────────────────────────────────────►│
  │                     │◄────────────────────────────────────────│
  │  stream file        │              │            │              │
  │◄────────────────────│              │            │              │
  │                     │              │            │              │
  │  ┌─────────────┐    │              │            │              │
  │  │ OCR Process │    │              │            │              │
  │  │ (Engine)    │    │              │            │              │
  │  └──────┬──────┘    │              │            │              │
  │         │           │              │            │              │
  │  POST /upload       │              │            │              │
  │  {job_id, key, file}│              │            │              │
  │────────────────────►│              │            │              │
  │                     │  S3 PutObject│            │              │
  │                     │─────────────────────────────────────────►│
  │                     │◄────────────────────────────────────────│
  │  upload OK          │              │            │              │
  │◄────────────────────│              │            │              │
  │                     │              │            │              │
  │  notify: COMPLETED  │              │            │              │
  │─────────────────────────────────── ►│           │              │
  │                     │              │            │              │
  │  cleanup local files│              │            │              │
  │                     │              │            │              │

  Worker→FileProxy (Processing→Orch) ✓ adjacent layers
  FileProxy→MinIO (Orch→Edge) ✓ adjacent layers
  Worker→MinIO ✗ NEVER (would bypass Orchestration layer)
```

**Flow 3: Status Polling Flow**

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │───▶│   API    │───▶│  Query   │───▶│ Aggregate│───▶ Response
│  Refresh │    │  Server  │    │   Jobs   │    │  Status  │
│          │    │  (Edge)  │    │  (Orch)  │    │  (Orch)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
                                                      ▼
                                               Request Status:
                                               • COMPLETED if all done
                                               • PARTIAL_SUCCESS if mix
                                               • PROCESSING if any running
                                               • FAILED if all failed
```

### 4.5. Job State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB STATE MACHINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌───────────────┐                                 │
│                           │   SUBMITTED   │                                 │
│                           │  (Job created)│                                 │
│                           └───────┬───────┘                                 │
│                                   │                                          │
│                                   │ Auto (validate file)                    │
│                                   ▼                                          │
│                           ┌───────────────┐                                 │
│                           │  VALIDATING   │                                 │
│                           │ (Check format)│                                 │
│                           └───────┬───────┘                                 │
│                                   │                                          │
│                          ┌────────┼────────┐                                │
│                          │                 │                                │
│                       Valid            Invalid                              │
│                          │                 │                                │
│                          ▼                 ▼                                │
│              ┌───────────────┐     ┌───────────────┐                       │
│              │    QUEUED     │     │   REJECTED    │                       │
│              │  (In queue)   │     │  (Terminal)   │                       │
│              └───────┬───────┘     └───────────────┘                       │
│                      │                                                      │
│                      │ Worker picks up                                      │
│                      ▼                                                      │
│              ┌───────────────┐                                              │
│              │  PROCESSING   │                                              │
│              │ (OCR running) │                                              │
│              └───────┬───────┘                                              │
│                      │                                                      │
│         ┌────────────┼────────────┐                                        │
│         │            │            │                                        │
│      Success    Retriable    Non-retriable                                 │
│         │        Error         Error                                       │
│         │            │            │                                        │
│         ▼            ▼            ▼                                        │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐                                 │
│  │ COMPLETED │ │ RETRYING │ │  FAILED   │                                 │
│  │ (Success) │ │          │ │(Terminal) │                                 │
│  └───────────┘ └────┬─────┘ └───────────┘                                 │
│                      │                                                      │
│                      │ retry < max?                                         │
│                ┌─────┼──────┐                                               │
│              Yes           No                                               │
│                │            │                                               │
│                ▼            ▼                                               │
│          ┌──────────┐ ┌───────────────┐                                    │
│          │  QUEUED  │ │  DEAD_LETTER  │                                    │
│          │(re-enter)│ │  (Terminal)   │                                    │
│          └──────────┘ └───────────────┘                                    │
│                                                                              │
│         From QUEUED only:                                                   │
│         ┌───────────┐                                                       │
│         │ CANCELLED │ (User cancel, only if not yet picked up)             │
│         │(Terminal) │                                                       │
│         └───────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

State Transition Rules:
┌────────────┬──────────────┬─────────────────────────┬──────────────────────────────┐
│ From       │ To           │ Trigger                 │ Side Effects                 │
├────────────┼──────────────┼─────────────────────────┼──────────────────────────────┤
│ SUBMITTED  │ VALIDATING   │ Auto (immediate)        │ Begin file validation        │
│ VALIDATING │ QUEUED       │ File valid              │ Publish to queue             │
│ VALIDATING │ REJECTED     │ File invalid            │ Log rejection reason         │
│ QUEUED     │ PROCESSING   │ Worker picks            │ Set started_at, worker_id    │
│ QUEUED     │ CANCELLED    │ User cancel request     │ Remove from queue            │
│ PROCESSING │ COMPLETED    │ OCR success             │ Save result, set completed_at│
│ PROCESSING │ RETRYING     │ Retriable error         │ Increment retry_count,       │
│            │              │ AND retry < max         │ append to error_history      │
│ PROCESSING │ FAILED       │ Non-retriable error     │ Set final error              │
│ RETRYING   │ QUEUED       │ Delay elapsed           │ Re-publish to queue          │
│ RETRYING   │ DEAD_LETTER  │ retry >= max            │ Move to DLQ, log            │
└────────────┴──────────────┴─────────────────────────┴──────────────────────────────┘

Request Status Aggregation:
┌──────────────────┬──────────────────────────────────────────────────────────────┐
│ Request Status   │ Condition                                                    │
├──────────────────┼──────────────────────────────────────────────────────────────┤
│ PROCESSING       │ Any job is QUEUED, PROCESSING, or RETRYING                   │
│ COMPLETED        │ All jobs are COMPLETED                                       │
│ PARTIAL_SUCCESS  │ At least 1 COMPLETED + at least 1 FAILED/DEAD_LETTER        │
│ FAILED           │ All jobs are FAILED or DEAD_LETTER (none succeeded)          │
│ CANCELLED        │ All jobs are CANCELLED                                       │
└──────────────────┴──────────────────────────────────────────────────────────────┘
```

### 4.6. Data Governance

**Data Lifecycle Management:**

- **Uploaded Files**: Lưu trong MinIO bucket `uploads` (Edge layer). Retention configurable per request (Phase 1 default: 24h). Khi retention expire hoặc user delete → move sang bucket `deleted` (soft delete).

- **Result Files**: Lưu trong MinIO bucket `results` (Edge layer). Retention configurable (Phase 1 default: 7 days). Cùng soft delete lifecycle.

- **Deleted Files**: Lưu trong MinIO bucket `deleted` (Edge layer) với prefix `{original_bucket}/{timestamp}/`. Retention 7 ngày trong deleted bucket, sau đó hard delete.

- **Job Metadata**: Giữ lại trong database (Orchestration layer) với `deleted_at` timestamp. Phase 1 giữ 90 ngày.

- **Cleanup Schedule**: Cleanup job chạy mỗi giờ (trong Backend process):
  1. Scan files quá retention → soft delete (move to `deleted` bucket via File Proxy hoặc Edge context)
  2. Scan `deleted` bucket files quá 7 ngày → hard delete

**Soft Delete Policy:**

| Action | Behavior |
|---|---|
| User delete file | Move to `deleted` bucket (Edge Storage), set `deleted_at` trong DB (Orch) |
| Retention expire | Move to `deleted` bucket (Edge Storage), set `deleted_at` trong DB (Orch) |
| User request recovery | Move back từ `deleted` bucket, clear `deleted_at` |
| 7 ngày trong `deleted` | Hard delete file, set `purged_at` trong DB, giữ metadata |

---

## SECTION 5: INTEGRATION & COMMUNICATION

### 5.1. Giao tiếp nội bộ

| Pattern | Use Case | Implementation | Layer Communication |
|---|---|---|---|
| **Sync (REST)** | Frontend ↔ API Server | HTTP/JSON | Client ↔ Edge |
| **Sync (REST)** | API Server ↔ Modules | Internal function calls (same process Phase 1) | Edge ↔ Orchestration |
| **Sync (REST)** | Worker ↔ File Proxy | HTTP/JSON with access_key | Processing ↔ Orchestration |
| **Sync (REST)** | Worker ↔ Orchestrator | HTTP/JSON (heartbeat, status update) | Processing ↔ Orchestration |
| **Sync (S3 API)** | Upload Module ↔ MinIO | S3-compatible API | Orchestration ↔ Edge (via Edge context) |
| **Sync (S3 API)** | File Proxy ↔ MinIO | S3-compatible API with storage credentials | Orchestration ↔ Edge |
| **Async (Queue)** | Job dispatch, Worker pull | NATS JetStream subject-based routing | Orchestration ↔ Processing |
| **Database** | State persistence | SQLite direct access | Within Orchestration layer |

**Quy tắc giao tiếp:**

1. **Layer Adjacency Only**: Mỗi layer chỉ giao tiếp trực tiếp với layer liền kề. Processing layer KHÔNG access Edge layer resources (Storage) trực tiếp. Luồng hợp lệ: Worker → File Proxy (Processing→Orch) → MinIO (Orch→Edge).

2. **Object Storage thuộc Edge**: MinIO là thành phần Edge layer. API Server (Edge) access trực tiếp. File Proxy (Orchestration) access bằng storage credentials — đây là giao tiếp giữa layers liền kề. Worker (Processing) KHÔNG access — phải qua File Proxy.

3. **Workers stateless**: Worker không giữ state giữa các jobs. Tất cả state lưu trong database (Orchestration). Worker cleanup local files sau mỗi job.

4. **Queue là single source of truth cho pending work**: Nếu job trong queue, nó sẽ được process. Nếu không, nó đã done hoặc failed.

5. **Database là source of truth cho job status**: Queue (Orchestration) chỉ chứa pending jobs. Database (Orchestration) chứa tất cả jobs với full history.

6. **File Proxy là gateway cho Processing layer**: Worker gọi File Proxy API (authenticate bằng access_key) để download/upload files. File Proxy là cầu nối duy nhất (ngoài Edge) cho phép access Storage.

### 5.2. Layer Communication Rules (Chi tiết)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER COMMUNICATION RULES                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐                                                  │
│   │    CLIENT    │                                                  │
│   └──────┬───────┘                                                  │
│          │ ▲                                                        │
│          ▼ │  HTTP (user auth token)                               │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                       EDGE LAYER                              │ │
│   │   API Server ←→ Object Storage (MinIO)                       │ │
│   │   (same layer — direct access ✓)                              │ │
│   └──────┬───────────────────────────────────────────────────────┘ │
│          │ ▲                                                        │
│          ▼ │  Internal calls + Storage credentials                 │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                   ORCHESTRATION LAYER                         │ │
│   │  Job Module + File Proxy + Auth + Queue + Database           │ │
│   │                                                               │ │
│   │  File Proxy has storage creds → calls Edge Storage ✓         │ │
│   │  (adjacent layers)                                            │ │
│   └──────┬───────────────────────────────────────────────────────┘ │
│          │ ▲                                                        │
│          ▼ │  Queue pull + File Proxy API (access_key)             │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                   PROCESSING LAYER                            │ │
│   │  OCR Workers                                                  │ │
│   │  NO storage creds. Files via File Proxy only.                │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│   ✗ Processing → Edge (vượt cấp, KHÔNG cho phép)                   │
│   ✓ Processing → Orchestration → Edge (qua File Proxy, hợp lệ)    │
│                                                                      │
│   Data flow:                                                         │
│     Upload:   Client → Edge(API) → Edge(MinIO)                     │
│     Process:  Worker → FileProxy(Orch) → MinIO(Edge)               │
│     Download: Client → Edge(API) → Edge(MinIO)                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3. NATS JetStream Architecture

**Job Message Format:**

| Field | Type | Description |
|---|---|---|
| job_id | string | Unique job identifier |
| request_id | string | Parent request identifier |
| file_id | string | Source file identifier |
| method | string | OCR method (`text_raw`, `table`, etc.) |
| tier | int | Processing tier (0=local, 1=cloud, etc.) |
| output_format | string | Requested output format (`txt`, `json`, etc.) |
| retry_count | int | Current retry attempt (0-based) |
| error_history | array | List of previous errors với timestamps |
| created_at | timestamp | Job creation time |

**NATS JetStream Configuration:**

| Config | Value | Description |
|---|---|---|
| Stream Name | `OCR_JOBS` | Persistent stream cho OCR jobs |
| Subjects | `ocr.>` | Wildcard capture tất cả OCR subjects |
| Storage | File | Persist messages trên disk |
| Retention | Limits (1GB) | Auto-cleanup khi đạt limit |
| Max Age | 24h | Messages expire sau 24h |
| Replicas | 1 | Single replica cho local dev |

| Config (DLQ) | Value | Description |
|---|---|---|
| Stream Name | `OCR_DLQ` | Dead letter queue stream |
| Subjects | `dlq.ocr.>` | Capture DLQ messages |
| Storage | File | Persist on disk |
| Max Age | 7d | DLQ messages kept 7 days |

**Thêm OCR Service mới (ví dụ: handwriting):**

1. Admin đăng ký service: `INSERT INTO services (id, access_key, allowed_methods, ...)`.
2. Define subject: `ocr.handwriting.tier0`.
3. Create Docker service với: `WORKER_FILTER_SUBJECT=ocr.handwriting.tier0`, `WORKER_ACCESS_KEY=sk_xxx`.
4. Update Job Module: thêm routing logic cho method=handwriting.
5. Deploy. Worker tự poll queue, authenticate với File Proxy bằng access_key.

Không cần thay đổi core queue infrastructure, File Proxy, hay Object Storage.

### 5.4. Tích hợp hệ thống

| System | Integration | Purpose | Layer | Access |
|---|---|---|---|---|
| **MinIO** | boto3/aioboto3 (S3 SDK) | Object storage | Edge | API Server (Edge) ✅, File Proxy (Orch) ✅, Worker (Processing) ❌ |
| **NATS JetStream** | nats-py | Message queue | Orchestration | Backend (Orch) ✅, Worker (Processing) ✅ |
| **OCR Engines** | pytesseract / paddleocr / easyocr | Text extraction | Processing | Worker only (pluggable) |

### 5.5. API Design Principles

| Principle | Implementation |
|---|---|
| **API Style** | REST với JSON payloads |
| **Versioning** | URL-based: `/api/v1/...` |
| **Documentation** | OpenAPI 3.0 auto-generated bởi FastAPI. Swagger UI tại `/docs`, ReDoc tại `/redoc`. |
| **Validation** | Pydantic models cho request/response validation. |
| **Authentication** | User: Session token. Worker: access_key. |
| **Async** | Async endpoints cho I/O operations. |
| **Error Format** | `{ "error": "ERROR_CODE", "message": "Human readable" }` |

**Endpoint Categories:**

| Category | Endpoints | Auth | Description |
|---|---|---|---|
| Auth | `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me` | Public / Session | User authentication |
| Upload | `/upload` | Session | Batch file upload |
| Requests | `/requests`, `/requests/:id`, `/requests/:id/cancel` | Session | Request management |
| Jobs | `/jobs/:id`, `/jobs/:id/result`, `/jobs/:id/download` | Session | Job details và results |
| Files | `/files/:id/recover`, `/files?deleted=true` | Session | File recovery |
| Internal | `/internal/file-proxy/download`, `/internal/file-proxy/upload` | access_key | Worker ↔ File Proxy |
| Internal | `/internal/heartbeat` | access_key | Worker heartbeat |
| Internal | `/internal/jobs/:id/status` | access_key | Worker reports job status |

---

## SECTION 6: INFRASTRUCTURE & DEPLOYMENT

### 6.1. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LOCAL DEVELOPMENT DEPLOYMENT                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                      DOCKER COMPOSE STACK                              │ │
│   │                                                                        │ │
│   │  EDGE LAYER CONTAINERS:                                                │ │
│   │   ┌──────────┐ ┌──────────┐ ┌──────────┐                              │ │
│   │   │ FRONTEND │ │ BACKEND  │ │  MinIO   │                              │ │
│   │   │Container │ │Container │ │Container │  ← Object Storage            │ │
│   │   │          │ │          │ │          │    thuộc Edge layer           │ │
│   │   │React+Vite│ │ FastAPI  │ │S3-compat │                              │ │
│   │   │          │ │ +Uvicorn │ │          │                              │ │
│   │   │          │ │ +Modules │ │          │                              │ │
│   │   │Port:3000 │ │Port:8080 │ │Port:9000 │                              │ │
│   │   │          │ │          │ │UI: 9001  │                              │ │
│   │   └──────────┘ └────┬─────┘ └─────┬────┘                              │ │
│   │                      │ has MinIO   │                                    │ │
│   │                      │ creds ✓     │                                    │ │
│   │                      │             │                                    │ │
│   │  ORCHESTRATION LAYER CONTAINERS:   │                                    │ │
│   │   ┌──────────┐                     │                                    │ │
│   │   │   NATS   │  Backend container also hosts Orchestration modules:    │ │
│   │   │Container │  Auth, Upload, Job, File Proxy (same process Phase 1)  │ │
│   │   │          │  File Proxy has storage creds → accesses MinIO (Edge)  │ │
│   │   │JetStream │                                                         │ │
│   │   │Port:4222 │  SQLite DB: ./data/ocr_platform.db                     │ │
│   │   └──────────┘                                                         │ │
│   │                                                                        │ │
│   │  PROCESSING LAYER CONTAINERS:                                          │ │
│   │   ┌──────────┐                                                         │ │
│   │   │  WORKER  │  ← NO MinIO creds ✗                                    │ │
│   │   │Container │    Has access_key for File Proxy                        │ │
│   │   │          │    Calls Backend /internal/file-proxy/* endpoints       │ │
│   │   │Python +  │                                                         │ │
│   │   │OCR Engine│                                                         │ │
│   │   │(no port) │                                                         │ │
│   │   └──────────┘                                                         │ │
│   │                                                                        │ │
│   │   ┌────────────────────────────────────────────────────────────────┐   │ │
│   │   │                     SHARED VOLUMES                              │   │ │
│   │   │   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐     │   │ │
│   │   │   │  ./data   │ │./data/nats│ │./data/minio│ │   ./src   │     │   │ │
│   │   │   │ (SQLite)  │ │ (streams) │ │ (objects) │ │(hot reload)│     │   │ │
│   │   │   └───────────┘ └───────────┘ └───────────┘ └───────────┘     │   │ │
│   │   └────────────────────────────────────────────────────────────────┘   │ │
│   │                                                                        │ │
│   └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│   Access:                                                                    │
│   • Frontend: http://localhost:3000                                         │
│   • API: http://localhost:8080                                              │
│   • NATS: nats://localhost:4222 (client), http://localhost:8222 (monitor)  │
│   • MinIO API: http://localhost:9000 (S3-compatible)                        │
│   • MinIO Console: http://localhost:9001 (Web UI)                          │
│                                                                              │
│   NOTE: Backend container hosts both Edge (API Server) and Orchestration    │
│   (modules) in Phase 1 for simplicity. MinIO is a separate container       │
│   belonging to Edge layer. Worker container has NO MINIO_* env vars.       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Lưu ý về Phase 1 container mapping:**

Trong Phase 1, Backend container chứa cả API Server (Edge) và các modules (Orchestration) trong cùng một process. Điều này chấp nhận được vì:
- Layer separation được enforce ở **code level** (module boundaries, interface contracts), không chỉ ở container level.
- File Proxy module trong Backend có storage credentials, nhưng Worker container thì không — credential isolation vẫn được maintain.
- Phase 2 có thể tách Backend thành nhiều services nếu cần, mà không thay đổi interfaces.

### 6.2. Container Orchestration

| Component | Layer | Deployment Strategy | Resources | MinIO Access |
|---|---|---|---|---|
| **Frontend** | Edge | Single container, Vite dev server | 256MB RAM | ❌ |
| **Backend** | Edge + Orchestration | Single container, FastAPI + all modules | 512MB RAM | ✅ (has credentials) |
| **MinIO** | Edge | Single container, S3-compatible storage | 256MB RAM | N/A (is storage) |
| **NATS** | Orchestration | Single container, JetStream enabled | 64MB RAM | ❌ |
| **Worker** | Processing | Single container per service | 1GB RAM (Tesseract) / 4GB VRAM (PaddleOCR) / 2GB VRAM (EasyOCR) | ❌ (via File Proxy) |

**Dependencies:**

- MinIO và NATS start first (no dependencies)
- Backend depends on NATS + MinIO + SQLite
- Worker depends on NATS + Backend (File Proxy API)
- Frontend depends on Backend (API calls)

**Worker Environment Variables:**

```yaml
# docker-compose.yml — worker service
worker-ocr-text-tier0:
  environment:
    - WORKER_SERVICE_ID=worker-ocr-text-tier0
    - WORKER_ACCESS_KEY=sk_local_text_tier0    # For File Proxy auth
    - WORKER_FILTER_SUBJECT=ocr.text_raw.tier0 # NATS subject to subscribe
    - NATS_URL=nats://nats:4222
    - FILE_PROXY_URL=http://backend:8080/internal/file-proxy
    - ORCHESTRATOR_URL=http://backend:8080/internal
    - HEARTBEAT_INTERVAL_MS=30000
    - JOB_TIMEOUT_SECONDS=300
    # NOTE: No MINIO_* variables — Worker CANNOT access MinIO (Edge layer)
```

### 6.3. Environments

| Environment | Purpose | Layer Deployment |
|---|---|---|
| **Development (Local)** | Active development | All layers in Docker Compose. Backend = Edge + Orch combined. MinIO = Edge storage. |
| **Testing** | CI/CD pipeline | Same stack, ephemeral. Clean DB + NATS + MinIO mỗi run. |
| **(Phase 2) Staging** | Pre-production | Cloud storage (Edge). Backend tách Edge/Orch nếu cần. File Proxy separate. |
| **(Phase 2) Production** | Live system | Full cloud. Managed storage (Edge). Orch services separate. Workers auto-scale. |

### 6.4. CI/CD Pipeline Overview

Phase 1 tập trung vào local development, CI/CD đơn giản:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   Code   │───▶│   Lint   │───▶│   Unit   │───▶│  Build   │
│   Push   │    │  Check   │    │  Tests   │    │  Docker  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

Phase 2 sẽ thêm: Integration tests (File Proxy flow, layer isolation verification), Deploy to staging/production.

---

## SECTION 7: SECURITY

### 7.1. Authentication & Authorization

**User Authentication:**

| Aspect | Implementation |
|---|---|
| **Strategy** | Session-based với token |
| **Password Storage** | bcrypt hash với cost factor 10 |
| **Session Storage** | SQLite database (Orchestration layer) |
| **Token Delivery** | Cookie (preferred) hoặc Authorization header |
| **Session Duration** | Configurable via `SESSION_EXPIRES_HOURS` (default 24h) |
| **Phase 2** | Thêm OAuth (Google, GitHub) |

**Service Authentication (Worker → File Proxy):**

| Aspect | Implementation |
|---|---|
| **Strategy** | Static access_key per service |
| **Key Storage** | `services` table trong SQLite (Orchestration layer) |
| **Key Delivery** | Environment variable trong Docker Compose |
| **Validation** | File Proxy validates access_key trước mọi file operation |
| **Phase 2** | Dynamic key management qua Admin dashboard, key rotation |

**Authorization:**

| Context | Permissions |
|---|---|
| **User** | Full access to own resources (requests, jobs, files). Cannot access other users' data. |
| **Service** | Access files belonging to jobs assigned to this service. File Proxy checks job→file→service mapping. |

### 7.2. Data Protection

| Aspect | Implementation |
|---|---|
| **Encryption at Rest** | Không (Phase 1 local dev). Phase 2 thêm encryption. |
| **Encryption in Transit** | HTTP only (localhost). Phase 2 thêm TLS/HTTPS. |
| **Secrets Management** | `.env` file. Không commit secrets vào git. |
| **Password Hashing** | bcrypt với automatic salting |
| **Worker File Cleanup** | Worker PHẢI xoá local files sau khi xử lý xong. |
| **Storage Credential Isolation** | MinIO credentials chỉ trong Backend container (Edge+Orch). Worker container KHÔNG có. Layer separation enforce credential boundaries. |

### 7.3. Security Controls

| Control | Description |
|---|---|
| **Layer Isolation** | Processing layer không có storage credentials. Mọi file access từ Worker phải qua File Proxy (Orchestration layer). File Proxy validate identity + ACL trước khi proxy request sang Storage (Edge layer). |
| **Input Validation** | Validate tất cả inputs: email, password, file types, file sizes, output_format, retention values. |
| **File Validation** | Check MIME type, magic bytes, file size. Reject executable files. Invalid → REJECTED status. |
| **Path Traversal Prevention** | Sanitize file paths. Store files với generated IDs. |
| **SQL Injection Prevention** | Parameterized queries. |
| **Session Security** | Regenerate token after login. Expiry enforcement. |
| **Service Identity Verification** | File Proxy validates access_key. Invalid → 401. |
| **File Access Control** | File Proxy checks service→job→file mapping. |

---

## SECTION 8: NON-FUNCTIONAL REQUIREMENTS

### 8.1. Performance Targets

| Metric | Target | Notes |
|---|---|---|
| **API Response Time** | < 200ms | Cho non-file-upload endpoints |
| **File Upload Response** | < 5s per file | Phụ thuộc file size |
| **Job Queue Latency** | < 2s | Submit đến worker pick up |
| **OCR Processing Time** | < 60s per file | File < 1MB, single page |
| **Status Polling** | < 100ms | Database query |
| **File Proxy Latency** | < 500ms | Additional proxy overhead (security trade-off) |
| **Heartbeat Round-trip** | < 200ms | Worker → Orchestrator |

### 8.2. Scalability Strategy

| Component | Layer | Horizontal | Vertical |
|---|---|---|---|
| **Frontend** | Edge | N/A | N/A |
| **Backend** | Edge+Orch | ❌ Phase 1 | ✅ |
| **MinIO** | Edge | ❌ Phase 1 | ✅ |
| **Worker** | Processing | ✅ Phase 2 | ✅ |
| **Database** | Orchestration | ❌ | ✅ |
| **Queue** | Orchestration | ❌ Phase 1 | ✅ |

### 8.3. Monitoring & Alerting

**Phase 1 Monitoring (Basic):**

| Layer | Approach |
|---|---|
| **Application Logs** | Console output, structured JSON format |
| **Job Metrics** | Database queries: count by status, processing time avg |
| **Error Tracking** | Error history stored in job metadata |
| **Heartbeat Monitoring** | Heartbeats table — detect dead/stalled workers |
| **File Proxy Audit** | Log all file access requests |

**Key Metrics:**

| Metric | How to Calculate |
|---|---|
| Job Success Rate | `COUNT(COMPLETED) / COUNT(*)` |
| Avg Processing Time | `AVG(completed_at - started_at)` |
| Retry Rate | `COUNT(retry_count > 0) / COUNT(*)` |
| Dead Letter Rate | `COUNT(DEAD_LETTER) / COUNT(*)` |
| Queue Depth | NATS monitoring endpoint |
| Worker Health | Last heartbeat timestamp per service |

**Metrics Collection Strategy (per Requirements §3.5.5):**

| Phase | Metrics | Usage |
|-------|---------|-------|
| Phase 1 | Queue depth, heartbeat (status + progress + errors) | ON/OFF manual |
| Phase 2 | + Growth rate, processing rate, error rate | ON/OFF thông minh |
| Phase 3 | + Utilization, consumer lag, workload estimation | Auto-scale 0→N |

---

## SECTION 9: RISKS & TRADE-OFFS

### 9.1. Kiến trúc Trade-offs

| Decision | Trade-off | Rationale |
|---|---|---|
| **MinIO ở Edge layer** | Backend (Orchestration modules) phải gọi qua Edge context hoặc shared credentials để access Storage. Phức tạp hơn so với đặt chung layer. | Requirement mandate rõ: "Edge layer lưu trữ file (object storage)." Giữ đúng layer separation. File Proxy (Orch) có credentials để gọi sang Edge Storage — giao tiếp giữa layers liền kề. |
| **File Proxy Pattern** | Thêm latency (~200-500ms) cho mỗi file operation. Thêm complexity. | Requirement mandate: Worker không access Storage trực tiếp. Security: worker không cần storage credentials. Audit: centralized file access logging. Production parity. |
| **NATS JetStream Local** | Thêm container. | Lightweight (~50MB RAM), persistence, subject filtering, DLQ. Cùng config cho Phase 2. |
| **SQLite Database** | Limited concurrent writes (~100 writes/sec). | Zero config, đủ cho demo, SQL-compatible cho migration. |
| **Static access_key** | Không rotation, trong env vars. | Đủ cho local dev. Interface đúng. Phase 2 thêm dynamic management. |
| **Single Job Pull (Tesseract)** | Không batch optimization cho CPU engine. | Tesseract CPU-based không cần batch. GPU engines (PaddleOCR, EasyOCR) hỗ trợ batch pull. |
| **Polling-based Status** | Không real-time. | Đơn giản. Phase 2 thêm SSE/WebSocket. |
| **No Billing** | Mọi request miễn phí. | Phase 1 scope. Data model ready cho billing hooks. |

### 9.2. Rủi ro chính

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **OCR accuracy thấp** | OCR không chính xác | Low-Medium | Tesseract (default) có accuracy medium. Switch sang PaddleOCR/EasyOCR nếu cần accuracy cao hơn. |
| **Worker crash** | Jobs stuck PROCESSING | Medium | Heartbeat detection → jobs back to queue. |
| **File Proxy bottleneck** | All file ops qua 1 module | Low (Phase 1) | Phase 1 chỉ 1 worker. Phase 2 tách service, scale. |
| **SQLite corruption** | Mất data | Low | Backups. Ephemeral data cho testing. |
| **Storage full** | Upload fails | Low | Cleanup hourly. Warn at 80%. |
| **NATS crash** | Queue unavailable | Low | Auto-restart. JetStream persistence. Reconnect logic. |

### 9.3. Technical Debt

| Item | Priority | Resolution |
|---|---|---|
| No Rate Limiting | P1 | Phase 2 |
| No Billing Module | P1 | Phase 2 |
| No Notification System | P1 | Phase 2 |
| Static access_keys | P2 | Phase 2 — Admin dashboard |
| No Circuit Breaker | P2 | Phase 2 |
| Basic Retry (no jitter) | P3 | Phase 2 |
| Single Job Pull (Tesseract only) | P3 | GPU engines already support batch. Tesseract remains single pull. |
| No Admin Dashboard | P2 | Phase 2 |

### 9.4. Phase 1 → Phase 2 Migration Notes

| Component | Phase 1 | Phase 2 | Effort |
|---|---|---|---|
| **Object Storage** | MinIO Docker (Edge) | Cloudflare R2 / AWS S3 (Edge) | Đổi endpoint + credentials, S3-compatible. |
| **Database** | SQLite (Orchestration) | PostgreSQL (Orchestration) | SQL-compatible. Thêm billing + notification tables. |
| **Queue** | NATS single (Orchestration) | NATS cluster (Orchestration) | Đổi config, cùng client code. |
| **File Proxy** | Module trong Backend | Separate service (Orchestration) | Extract module, deploy riêng. |
| **Auth** | Email/password | + OAuth | Thêm providers, giữ session model. |
| **Billing** | None | Pre-paid credit | Thêm tables, hooks vào Job Module. |
| **Notifications** | None | In-app real-time | Thêm table, SSE/WebSocket. |
| **Service Keys** | Static env vars | Dynamic Admin dashboard | Key rotation API. |

---

## Appendix A: Quick Reference

### A.1. Ports & URLs

| Service | Layer | Port | URL |
|---|---|---|---|
| Frontend | Edge | 3000 | http://localhost:3000 |
| Backend API | Edge + Orch | 8080 | http://localhost:8080/api/v1 |
| File Proxy (internal) | Orch | 8080 | http://backend:8080/internal/file-proxy |
| MinIO API | Edge | 9000 | http://localhost:9000 |
| MinIO Console | Edge | 9001 | http://localhost:9001 |
| NATS Client | Orch | 4222 | nats://localhost:4222 |
| NATS Monitor | Orch | 8222 | http://localhost:8222 |

### A.2. Default Configuration

| Parameter | Default | Description |
|---|---|---|
| `MAX_FILE_SIZE_MB` | 10 | Max size per file |
| `MAX_BATCH_SIZE_MB` | 50 | Max total batch size |
| `MAX_FILES_PER_BATCH` | 20 | Max files per upload |
| `MAX_RETRIES` | 3 | Max retry attempts |
| `RETRY_BASE_DELAY_MS` | 1000 | Base delay for backoff |
| `JOB_TIMEOUT_SECONDS` | 300 | Max job processing time |
| `FILE_RETENTION_HOURS` | 24 | Default file retention (overridable per request) |
| `RESULT_RETENTION_DAYS` | 7 | Default result retention |
| `WORKER_POLL_INTERVAL_MS` | 1000 | Worker queue poll interval |
| `HEARTBEAT_INTERVAL_MS` | 30000 | Worker heartbeat interval |
| `HEARTBEAT_TIMEOUT_SECONDS` | 90 | Time before worker considered dead |
| `SESSION_EXPIRES_HOURS` | 24 | Session expiry time |
| `NATS_URL` | nats://localhost:4222 | NATS server URL |
| `NATS_STREAM_NAME` | OCR_JOBS | JetStream stream name |
| `NATS_DLQ_STREAM_NAME` | OCR_DLQ | Dead letter queue stream |
| `MINIO_ENDPOINT` | localhost:9000 | MinIO endpoint (Edge layer) |
| `MINIO_ACCESS_KEY` | minioadmin | MinIO access key |
| `MINIO_SECRET_KEY` | minioadmin | MinIO secret key |
| `MINIO_BUCKET_UPLOADS` | uploads | Bucket for uploaded files |
| `MINIO_BUCKET_RESULTS` | results | Bucket for OCR results |
| `MINIO_BUCKET_DELETED` | deleted | Bucket for soft-deleted files |
| `SOFT_DELETE_RETENTION_DAYS` | 7 | Days to keep deleted files |
| `DEFAULT_OUTPUT_FORMAT` | txt | Default output format |

### A.3. Job Statuses

| Status | Description | Terminal? |
|---|---|---|
| SUBMITTED | Job just created | No |
| VALIDATING | File being validated | No |
| QUEUED | In queue, waiting for worker | No |
| PROCESSING | Worker processing | No |
| RETRYING | Waiting for retry | No |
| COMPLETED | Successfully done | Yes |
| PARTIAL_SUCCESS | (Request-level) Mix of success and failure | Yes |
| FAILED | Failed permanently (non-retriable) | Yes |
| REJECTED | File validation failed | Yes |
| CANCELLED | User cancelled (only from QUEUED) | Yes |
| DEAD_LETTER | Exceeded max retries, in DLQ | Yes |

### A.4. Queue Subject Pattern

| Pattern | Example |
|---|---|
| `{task}.{method}.tier{tier}` | `ocr.text_raw.tier0` |
| `dlq.{task}.{method}.tier{tier}` | `dlq.ocr.text_raw.tier0` |

### A.5. MinIO Buckets & Access Control (Edge Layer)

| Bucket | Purpose | Who Writes | Who Reads |
|---|---|---|---|
| `uploads` | Source files | API Server (Edge) | File Proxy (Orch) → Worker |
| `results` | OCR output | File Proxy (Orch) ← Worker | API Server (Edge) → Client |
| `deleted` | Soft-deleted | File Proxy (Orch) | File Proxy (recovery) |

**Worker containers have NO MinIO credentials. All worker file operations go through File Proxy (Orchestration layer).**

### A.6. Service Authentication & Layer Access

| Entity | Layer | Storage Creds? | access_key? | File Access |
|---|---|---|---|---|
| Client | External | ❌ | ❌ | ✅ via API (session auth) |
| API Server | Edge | ✅ | N/A | ✅ direct MinIO (same layer) |
| File Proxy | Orchestration | ✅ | N/A | ✅ calls Edge Storage (adjacent layer) |
| OCR Worker | Processing | ❌ | ✅ | ✅ via File Proxy only (adjacent layer) |
| Unregistered | Processing | ❌ | ❌ | ❌ Rejected by File Proxy |

---

*Lưu ý: Tài liệu này cung cấp cái nhìn high-level về kiến trúc hệ thống. Chi tiết implementation trong DDD và Infrastructure Plan.*

*Changelog v3.0 → v3.1:*
- *Sửa vị trí Object Storage (MinIO): chuyển từ Orchestration layer sang **Edge layer** theo đúng Requirement §3.1: "Edge layer nhận request từ client, lưu trữ file (object storage)".*
- *Cập nhật toàn bộ architecture diagram, layer responsibilities, data flow, deployment diagram để phản ánh MinIO thuộc Edge layer.*
- *Thêm Section 2.3 Layer Responsibilities Summary — giải thích rõ ràng ranh giới trách nhiệm giữa 3 layers.*
- *Clarify File Proxy gọi sang Edge layer (Object Storage) là giao tiếp giữa layers liền kề (Orchestration → Edge), hoàn toàn hợp lệ.*
- *Thêm cột Layer trong Tech Stack table và Storage Strategy table để thể hiện rõ mỗi component thuộc layer nào.*
- *Cập nhật MinIO Buckets table: thể hiện who writes / who reads theo layer.*
- *Thêm giải thích vì sao Backend container (Phase 1) chứa cả Edge và Orchestration — layer separation enforce ở code level, không chỉ container level.*

*Changelog v2.0 → v3.0:*
- *Thêm File Proxy Module (align Requirement §3.1)*
- *Thêm Service Registration & access_key (align Requirement §3.1, §3.4)*
- *Mở rộng Job State Machine: VALIDATING, REJECTED, CANCELLED, DEAD_LETTER, PARTIAL_SUCCESS (align §3.3)*
- *Thêm Dead Letter Queue (align §2.6, §3.3)*
- *Thêm Heartbeat Protocol (align §3.5.4)*
- *Thêm output_format và retention per-request (align §2.3, §2.2)*
- *Thống nhất subject naming: `ocr.text_raw.tier0` (không prefix `ocr_`)*
- *Sửa filter contradiction: workers subscribe specific subjects, không wildcard*
- *Thêm Database Schema chi tiết (services, heartbeats tables)*
- *Acknowledge Phase 2 modules: billing, notifications, audit*
- *Thêm Phase 1 → Phase 2 Migration Notes*