# PROJECT_CONTEXT.md — Kiến Trúc & Bối Cảnh Dự Án

> Tài liệu tham khảo chi tiết. Đọc khi cần hiểu sâu về hệ thống.
> Cập nhật khi có thay đổi kiến trúc hoặc quyết định thiết kế mới.

---

## 1. Product Overview

**OCR/IDP Platform** — Nền tảng xử lý tài liệu thông minh cho thị trường Việt Nam.

- **Loại hình:** Self-hosted, on-premise
- **Giai đoạn:** POC (~63%) → Production Hardening (Phase 1)
- **Mục tiêu:** Chuyển từ OCR đơn thuần sang IDP (Intelligent Document Processing) — trích xuất dữ liệu có cấu trúc (JSON, CSV) từ tài liệu

---

## 2. Architecture

### 2.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  EDGE LAYER (Upload & Storage)                       │
│  - File upload (multipart, validation)               │
│  - MinIO storage (uploads/, results/, deleted/)      │
│  - Magic bytes + MIME check                          │
│  - Batch limits: 20 files, 50MB/file, 200MB total   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  ORCHESTRATION LAYER (FastAPI Backend)               │
│  - REST API (public + admin + internal)              │
│  - Job creation → NATS publish                       │
│  - Status tracking, request aggregation              │
│  - Worker registration + approval                    │
│  - File Proxy (access control cho workers)           │
│  - Background scheduler (APScheduler)                │
└──────────────────────┬──────────────────────────────┘
                       │ NATS JetStream
┌──────────────────────▼──────────────────────────────┐
│  PROCESSING LAYER (OCR Workers)                      │
│  - Pull jobs từ NATS queue                           │
│  - Download file qua File Proxy (KHÔNG trực tiếp    │
│    access MinIO)                                     │
│  - Process OCR → Upload result qua File Proxy        │
│  - Report status về backend                          │
│  - Heartbeat loop                                    │
└─────────────────────────────────────────────────────┘
```

### 2.2 Key Design Decisions

| Quyết định | Chi tiết | Lý do |
|---|---|---|
| Workers không access MinIO | Luôn qua File Proxy | Access control, audit, security |
| NATS subject routing | `ocr.{method}.tier{tier}` | Tách queue theo loại + tier, tránh block |
| SQLite WAL mode | Single-writer, concurrent reads | Đơn giản cho self-host, đủ cho Phase 1-3 |
| Session-based auth | bcrypt + session token | Self-host, không cần OAuth/JWT |
| APScheduler in-process | FastAPI lifespan managed | Nhẹ, không cần Celery/Redis |
| Controller → Service → Repo | 3 lớp bắt buộc | Enterprise-ready, testable, maintainable |

### 2.3 Communication Flow

```
User Upload → Backend validates → Store in MinIO
           → Create Request + Files + Jobs in DB
           → Publish JobMessage to NATS (ocr.{method}.tier{tier})

Worker     → Pull from NATS subscription
           → Download file via File Proxy (X-Access-Key)
           → Process OCR
           → Upload result via File Proxy
           → PATCH /internal/jobs/{id}/status (COMPLETED/FAILED)

Backend    → Receive status update
           → Update Job in DB
           → Recalculate Request status (aggregate)
           → If FAILED + retriable → RetryOrchestrator (requeue or DLQ)
```

---

## 3. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend | React, Vite, TypeScript, Tailwind CSS, Shadcn/UI, Recharts | React 18 |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy | Python 3.12 |
| Database | SQLite (WAL mode) | — |
| Storage | MinIO (S3-compatible) | Latest |
| Queue | NATS JetStream | Latest |
| Workers | PaddleOCR (GPU), PaddleOCR-VL/PPStructure (GPU), Tesseract (CPU) | — |
| Scheduler | APScheduler (AsyncIOScheduler) | >=3.10 |
| Infra | Docker Compose, Makefile | — |
| Testing | pytest, httpx (async), Vitest (planned) | — |

---

## 4. Database Schema

### Core Models

| Table | Mô tả | Key Fields |
|---|---|---|
| `users` | Người dùng | id, email, password_hash, is_admin |
| `sessions` | Phiên đăng nhập | id, user_id, token, expires_at |
| `requests` | Batch upload request | id, user_id, method, tier, status, total_files, completed_files, failed_files, expires_at |
| `files` | File trong request | id, request_id, original_name, mime_type, size_bytes, object_key |
| `jobs` | Job xử lý OCR per file | id, request_id, file_id, status, method, tier, retry_count, max_retries, error_history, result_path, worker_id, engine_version |

### Service Models

| Table | Mô tả | Key Fields |
|---|---|---|
| `service_types` | Loại worker (admin managed) | id, status (PENDING/APPROVED/DISABLED/REJECTED), access_key, allowed_methods, allowed_tiers |
| `service_instances` | Instance đang chạy | id, service_type_id, status (WAITING/ACTIVE/PROCESSING/DRAINING/DEAD), last_heartbeat_at |
| `heartbeats` | Heartbeat records | id, instance_id, status, current_job_id, received_at |

### Job Status Flow

```
SUBMITTED → VALIDATING → QUEUED → PROCESSING → COMPLETED
                │            │          │
                → REJECTED   → CANCELLED → FAILED → QUEUED (retry)
                                                  → DEAD_LETTER
```

### Request Status Aggregation (M1)

```
Nếu có job đang PROCESSING/QUEUED/SUBMITTED → "PROCESSING"
Tất cả COMPLETED                            → "COMPLETED"
Tất cả FAILED/DEAD_LETTER                   → "FAILED"
Tất cả CANCELLED                            → "CANCELLED"
Mix terminal states                          → "PARTIAL_SUCCESS"
```

---

## 5. API Structure

### Public Endpoints (Session auth required)
| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/v1/auth/register` | Đăng ký |
| POST | `/api/v1/auth/login` | Đăng nhập |
| POST | `/api/v1/auth/logout` | Đăng xuất |
| GET | `/api/v1/auth/me` | Thông tin user |
| POST | `/api/v1/upload` | Upload files |
| GET | `/api/v1/requests` | Danh sách requests (filters: status, method, date) |
| GET | `/api/v1/requests/{id}` | Chi tiết request + jobs |
| POST | `/api/v1/requests/{id}/cancel` | Cancel request |
| GET | `/api/v1/jobs/{id}` | Chi tiết job |
| GET | `/api/v1/jobs/{id}/result` | Kết quả OCR (text) |
| GET | `/api/v1/jobs/{id}/download` | Download kết quả |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel single job |
| GET | `/api/v1/services/available` | Dịch vụ khả dụng |

### Admin Endpoints (is_admin required)
| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/v1/admin/dashboard/stats` | KPIs |
| GET | `/api/v1/admin/dashboard/job-volume` | Charts data |
| GET/PATCH | `/api/v1/admin/service-types/*` | Quản lý service types |
| GET | `/api/v1/admin/service-instances/*` | Quản lý instances |

### Internal Endpoints (X-Access-Key, worker only)
| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/v1/internal/register` | Worker đăng ký |
| POST | `/api/v1/internal/heartbeat` | Worker heartbeat |
| PATCH | `/api/v1/internal/jobs/{id}/status` | Worker report status |
| GET | `/api/v1/internal/file-proxy/download` | Worker download file |
| POST | `/api/v1/internal/file-proxy/upload` | Worker upload result |

### Health
| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | Health check (DB, NATS, MinIO) |

---

## 6. MinIO Buckets

| Bucket | Mục đích | Lifecycle |
|---|---|---|
| `uploads` | File gốc user upload | Giữ theo retention_hours |
| `results` | Kết quả OCR | Giữ theo retention_hours |
| `deleted` | File đã soft-delete | Purge sau 7 ngày (grace period) |

**Object key format:** `{user_id}/{request_id}/{file_id}/{filename}`

---

## 7. NATS Streams

| Stream | Subjects | Mục đích |
|---|---|---|
| `OCR_JOBS` | `ocr.>` | Main job queue |
| `OCR_DLQ` | `dlq.>` | Dead Letter Queue |

**Subject format:** `ocr.{method}.tier{tier}` (e.g., `ocr.ocr_text_raw.tier0`)
**DLQ format:** `dlq.{method}.tier{tier}`

---

## 8. Market Context — Service Tiers

| Tier | Đối tượng | Hạ tầng | Tính năng | Phase |
|---|---|---|---|:---:|
| Tier 1 Standard | Freelancer, SMEs | Shared Cloud | OCR/IDP cơ bản, Web app, Pay-as-you-go | 1-2 |
| Tier 2 Professional | DN vừa | Shared (phân vùng) | IDP templates, Workflow, RBAC cơ bản | 2-3 |
| Tier 3 Enterprise | Ngân hàng, BH, Chính phủ | Dedicated/On-premise | SSO, Audit Trail, SLA, Custom AI | 4-5 |

---

## 9. Architecture Decision Log

| # | Ngày | Quyết định | Lý do | Phase |
|---|---|---|---|---|
| ADR-001 | 2026-03-07 | Self-host only, no external API | Bảo mật dữ liệu, target enterprise VN | 1 |
| ADR-002 | 2026-03-07 | Controller → Service → Repo pattern | Enterprise-ready, testable | 1 |
| ADR-003 | 2026-03-07 | APScheduler in-process (not Celery) | Đủ nhẹ cho single-instance | 1 |
| ADR-004 | 2026-03-07 | Frontend: Error UX trước mobile | Production cần toast/skeleton/retry states | 1 |
| ADR-005 | 2026-03-07 | API Key auth OUT OF SCOPE Phase 1 | Self-host, chỉ cần session auth | 1 |

> Thêm ADR mới khi có quyết định kiến trúc quan trọng.

---

## 10. Docker & Deployment

```bash
# Infrastructure + Backend
make up                    # docker compose up -d
make down                  # docker compose down
make build                 # docker compose build

# Workers (separate containers)
make worker-paddle         # PaddleOCR GPU
make worker-paddle-vl      # PaddleOCR-VL GPU
make worker-tesseract      # Tesseract CPU

# Admin
make create-admin EMAIL=admin@gmail.com PASS=admin123
make promote EMAIL=user@gmail.com

# All
make all                   # up + workers
make all-down              # workers-down + down
```

---

*Cập nhật lần cuối: 2026-03-07*
