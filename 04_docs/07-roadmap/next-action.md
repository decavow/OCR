# OCR/IDP PLATFORM — Đánh Giá Tiến Trình & Roadmap Phát Triển

> **Nền tảng Quản lý và Xử lý Tài liệu Toàn diện**
> Phiên bản: POC → Production Roadmap | Cập nhật: Tháng 3/2026

---

**Tóm tắt:** POC hiện tại đã xây dựng được pipeline OCR hoàn chỉnh (Upload → Queue → Process → Result), frontend MVP với React + Tailwind + Shadcn/UI, admin dashboard, và test suite cơ bản. Để trở thành Nền tảng IDP Toàn diện phục vụ thị trường Việt Nam, cần bổ sung khoảng 55-60% scope bao gồm: Backend orchestration completion, Document Management, IDP Intelligence, Workflow Automation và Enterprise Security.

---

## 1. Đánh Giá Hiện Trạng POC

### Tổng quan

| Hoàn thành | Một phần | Stub | Chưa bắt đầu |
|:---:|:---:|:---:|:---:|
| **31** | **4** | **5** | **16** |

### 1.1 Kiến trúc & Hạ tầng

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Phân tầng Edge / Orchestration / Processing | ✅ Done | 3 layer rõ ràng, giao tiếp qua NATS + File Proxy |
| Docker Compose (MinIO, NATS, Backend) | ✅ Done | docker-compose.yml + health check đầy đủ |
| Worker Base Image (CPU/GPU) | ✅ Done | Dockerfile.base-cpu + Dockerfile.base-gpu |
| Per-worker Dockerfile + Makefile | ✅ Done | PaddleOCR, PaddleOCR-VL, Tesseract |
| WAL mode SQLite + Migration | ✅ Done | connection.py với PRAGMA + _run_migrations() |

### 1.2 API & Authentication

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Register / Login / Logout / Me | ✅ Done | bcrypt + session token, 4 endpoint hoàn chỉnh |
| Admin CLI (create-admin, promote, demote) | ✅ Done | app/cli.py |
| Admin Dashboard API (stats, users, requests) | ✅ Done | 5 endpoint thống kê hệ thống |
| Rate Limiting | ❌ Chưa | Không có middleware giới hạn request |
| API Key cho Integration | ❌ Chưa | Chỉ có session token, chưa có API key |
| Refresh Token / Token Rotation | ❌ Chưa | Session cố định, không refresh |

### 1.3 Upload & File Processing

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Multipart Upload + Validation | ✅ Done | Magic bytes, MIME check, batch limit (20 file, 50MB/file, 200MB total) |
| MinIO Storage (uploads/results/deleted) | ✅ Done | 3 bucket, presigned URL, move/copy |
| NATS JetStream Publish | ✅ Done | Subject routing: ocr.{method}.tier{tier} |
| Job Creation + Queue | ✅ Done | Request → File → Job → NATS message |
| Chunked/Resumable Upload | ❌ Chưa | Chỉ hỗ trợ multipart đơn giản |

### 1.4 Worker & OCR Engine

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| PaddleOCR Text Extraction (GPU) | ✅ Done | handler + pre/post processing |
| PaddleOCR-VL / PPStructure (GPU) | ✅ Done | Layout analysis + table recognition |
| Tesseract OCR (CPU) | ✅ Done | Multi-language, PDF multi-page |
| Worker Registration → Approval Flow | ✅ Done | PENDING → APPROVED → heartbeat loop |
| Heartbeat + Action Response | ✅ Done | continue / approved / drain / shutdown |
| Graceful Shutdown (SIGTERM) | ✅ Done | GracefulShutdown class + deregister |
| Output: txt, json, md | ✅ Done | PaddleOCR-VL hỗ trợ cả 3 format |

### 1.5 Job Orchestration

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Job Status Update (PATCH) | ✅ Done | Worker → Backend via X-Access-Key |
| File Proxy Download/Upload | ✅ Done | Access control + ACL check |
| Retry Logic | ⚠️ Stub | RetryOrchestrator: tất cả method = `pass` |
| Stalled Job Recovery | ⚠️ Stub | HeartbeatMonitor.detect_stalled() = `pass` |
| Request Status Aggregation | ⚠️ Stub | JobStateMachine.get_request_status() = `pass` |
| Dead Letter Queue | ⚠️ Stub | DLQ stream tạo sẵn, chưa có logic đẩy vào |

### 1.6 Frontend (React + Vite + Tailwind + Shadcn/UI)

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Auth Pages (Login / Register) | ✅ Done | LoginForm, RegisterForm với validation, redirect |
| Protected Routes + Admin Routes | ✅ Done | ProtectedRoute, AdminRoute components |
| Sidebar Navigation + Layout | ✅ Done | MainLayout với Sidebar, phân quyền admin/user |
| Upload Page (Drag & Drop) | ✅ Done | DropZone, FileList, UploadConfig, UploadProgress |
| OCR Config Panel (method/tier/format/retention) | ✅ Done | Dynamic load từ /services/available, cost estimation |
| Batches List + Filters | ✅ Done | Pagination, filter theo status/method/date range |
| Batch Detail + Job List | ✅ Done | Polling auto-refresh, cancel batch, job status |
| Result Viewer (split-panel) | ✅ Done | Original preview + Extracted text, file navigation (arrow keys) |
| Admin Dashboard (KPIs + Charts) | ✅ Done | Stats cards, job volume chart (Recharts), services health, recent requests |
| Admin Service Management | ✅ Done | Approve/Reject/Disable/Enable/Delete service types |
| Admin User Management | ✅ Done | User list với role badges, request counts |
| Admin System Health | ✅ Done | Worker instances, heartbeat status, pending approvals |
| Settings Page | ◐ Một phần | Placeholder — chưa có chức năng thực |

### 1.7 Testing

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Infrastructure Tests (MinIO, NATS, SQLite) | ✅ Done | 00_test/infras/ — test connection, CRUD, streams |
| Backend API Tests (Auth, Upload, Health) | ✅ Done | 00_test/backend/ — pytest + httpx async tests |
| File Proxy Tests | ✅ Done | Access key validation, download/upload flow |
| Worker Tests (Queue, OCR processor) | ✅ Done | 00_test/ocr_worker/ — NATS, queue client, E2E flow |
| Database Model & Repository Tests | ✅ Done | 00_test/infras/test_database.py — full CRUD flow |
| Storage Client Tests | ✅ Done | 00_test/infras/test_storage.py — MinIO operations |
| Test Runner (run all) | ✅ Done | 00_test/run_all_tests.py |
| CI/CD Pipeline | ❌ Chưa | Tests chạy manual, chưa có GitHub Actions |

### 1.8 Document Management

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Folder / Workspace | ❌ Chưa | Không có model Workspace/Folder |
| Full-text Search / Indexing | ❌ Chưa | Không có search engine |
| Retention Policy Enforcement | ◐ Một phần | Trường retention_hours có nhưng không có cron job dọn dẹp |
| Version History | ❌ Chưa | — |
| Tag / Label / Category | ❌ Chưa | — |

### 1.9 IDP & Intelligence

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Template Matching | ❌ Chưa | Không có template engine |
| Key-Value Extraction | ❌ Chưa | PPStructure có layout nhưng chưa map field |
| Table Extraction → CSV/Excel | ◐ Một phần | PPStructure trả HTML table → MD, chưa có CSV export |
| Human-in-the-loop Review | ❌ Chưa | Không có correction UI hay feedback loop |
| Confidence-based Routing | ❌ Chưa | Worker trả confidence nhưng không có rule engine |

### 1.10 Enterprise & Security

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| RBAC (Role-Based Access) | ◐ Một phần | Chỉ có is_admin boolean, frontend đã phân quyền admin/user |
| SSO / SAML / OAuth2 | ❌ Chưa | — |
| Audit Trail | ❌ Chưa | Không có bảng audit_logs |
| Multi-tenant Isolation | ❌ Chưa | Tất cả dùng chung DB + bucket |
| Encryption at Rest | ❌ Chưa | MinIO không config encryption |

### 1.11 Operations & Billing

| Tính năng | Trạng thái | Chi tiết |
|---|:---:|---|
| Quota / Usage Tracking | ❌ Chưa | Không có bảng quota hay usage |
| Webhook / Event Notification | ❌ Chưa | — |
| Prometheus Metrics | ❌ Chưa | — |
| Real Health Check | ◐ Một phần | Trả hardcoded "ok", chưa check thực tế |
| Billing / Pay-as-you-go | ❌ Chưa | Frontend có cost estimation UI nhưng backend chưa có billing logic |

### Tổng kết tiến độ

**Hoàn thành: ~63%** (bao gồm Done + Partial) | **Tổng: 56 hạng mục**

So với phiên bản POC ban đầu (chỉ backend + worker), repo hiện tại đã bổ sung đáng kể: frontend MVP hoàn chỉnh với 12+ pages/components, admin dashboard với charts, và test suite bao phủ infrastructure + API + worker.

---

## 2. Phân Tích Khoảng Cách (Gap Analysis)

| Nhu cầu thị trường | Hiện trạng | Khoảng cách | Ưu tiên | Nỗ lực |
|---|---|---|:---:|:---:|
| **Core Extraction: OCR → IDP** | Có OCR text + PPStructure layout | Chưa có template engine, key-value extraction | **Cao** | Lớn |
| **Độ chính xác Tiếng Việt** | PaddleOCR + Tesseract hỗ trợ Vietnamese | Chưa fine-tune cho CCCD, hóa đơn VN, chữ viết tay | **Cao** | Rất lớn |
| **Human-in-the-loop** | Không có | Thiếu hoàn toàn: correction UI, feedback, fine-tune | Trung bình | Rất lớn |
| **Document Management** | File trong MinIO theo user/request | Không có folder, search, auto-cleanup, preview | **Cao** | Lớn |
| **Workflow Automation** | Không có | Thiếu: rule engine, webhook, integration API | Trung bình | Lớn |
| **Backend Orchestration** | 4 stub methods (pass) | Job fail không retry, request status không aggregate | **Rất cao** | Trung bình |
| **RBAC + SSO + Audit Trail** | is_admin flag + frontend phân quyền | Cần role model, SAML/OIDC, audit_logs | **Cao** | Lớn |
| **Multi-tenant + Billing** | Single tenant, FE có cost estimation | Cần tenant isolation, metering, payment | Trung bình | Rất lớn |
| **Observability** | Hardcoded health check, JSON logging | Cần Prometheus, tracing, alerting | **Cao** | Trung bình |

---

## 3. Roadmap Phát Triển

### Phase 1 — Production Hardening _(4-6 tuần)_

> Biến POC thành sản phẩm vận hành thực tế. Hoàn thiện stubs, security, polish frontend.

- **1.1 Backend Orchestration:** RetryOrchestrator, JobStateMachine.get_request_status(), HeartbeatMonitor.detect_stalled(), real health check, retention cleanup cron
- **1.2 Frontend Polish:** Settings page, mobile responsive, error handling UX, skeleton loading
- **1.3 Security:** Rate limiting, secret management, HTTPS, input sanitization
- **1.4 CI/CD:** GitHub Actions pipeline, frontend tests (Vitest), Docker build optimization

> 🎯 **Milestone:** Platform vận hành ổn định. Job fail retry tự động. Request status phản ánh đúng.

### Phase 2 — IDP Intelligence _(10-12 tuần)_

> Chuyển từ OCR sang IDP. Tạo giá trị khác biệt.

- **2.1 Template Engine:** Template model, editor UI, matching, key-value extraction pipeline
- **2.2 Vietnamese Support:** Benchmark CCCD/hóa đơn, fine-tune, pre-built templates
- **2.3 Table Enhancement:** CSV/Excel export, structure correction
- **2.4 Quality:** Confidence aggregation, low-confidence flagging, quality dashboard

> 🎯 **Milestone:** Upload hóa đơn → JSON structured data. 5-10 templates VN.

### Phase 3 — Document Management & Workflow _(8-10 tuần)_

> Quản lý tài liệu + workflow automation.

- **3.1 Doc Management:** Workspace/folder, full-text search, preview, tags, batch operations
- **3.2 Workflow:** Webhook engine, rule engine, export API, API key management
- **3.3 Human-in-the-loop (Phase 1):** Review UI, correction storage, review queue

> 🎯 **Milestone:** Folder organization, search, webhook → hệ thống kế toán.

### Phase 4 — Enterprise & Multi-tenant _(10-14 tuần)_

> Bảo mật, multi-tenant, billing. Mở Tier 2-3.

- **4.1 RBAC:** Role model (Owner/Admin/Editor/Viewer), permission system, invitation flow
- **4.2 Security:** SSO (SAML/OIDC), audit trail, encryption, IP whitelist, 2FA
- **4.3 Multi-tenant:** Tenant model, data isolation, DB isolation, tenant settings
- **4.4 Billing:** Usage metering, quota, Stripe/VNPay, usage dashboard

> 🎯 **Milestone:** SSO + audit log + data isolation. SME billing.

### Phase 5 — Scale & Intelligence _(Liên tục)_

> Hiệu năng, active learning, on-premise.

- **5.1 Active Learning:** Fine-tune từ corrections, model A/B test
- **5.2 Scale:** PostgreSQL, Redis, K8s HPA, CDN
- **5.3 On-premise:** Helm chart, air-gapped install, license server
- **5.4 Observability:** Prometheus, Grafana, OpenTelemetry, alerting

> 🎯 **Milestone:** >10K pages/ngày, on-premise, AI tự cải thiện.

---

## 4. Kiến Trúc Service Tiers

| Tier | Hạ tầng | Đối tượng | Phase | Giá |
|---|---|---|:---:|---|
| **Tier 1 — Standard** | Shared Cloud | Freelancer, SMEs | Phase 1-2 | Free + Pay-as-you-go |
| **Tier 2 — Professional** | Shared Cloud (phân vùng) | DN vừa | Phase 2-3 | Subscription |
| **Tier 3 — Enterprise** | Dedicated / On-premise | Ngân hàng, BH, Chính phủ | Phase 4-5 | Contract |

---

## 5. Top 5 Ưu Tiên Ngay Lập Tức

| # | Hành động | Lý do |
|:---:|---|---|
| **1** | Hoàn thiện Retry/Recovery/Status Aggregation | 4 stub methods là blocker cho production |
| **2** | Rate limiting & Security hardening | Cần trước khi mở cho user thực |
| **3** | Real health check + Retention cleanup | Health hardcoded "ok", file hết hạn không dọn |
| **4** | CI/CD pipeline | Test suite có nhưng không chạy tự động |
| **5** | Vietnamese OCR benchmark | Cần biết accuracy trước khi invest template engine |

---

## 6. Timeline Tổng Quan

| Phase | Thời gian | Milestone |
|---|:---:|---|
| Phase 1: Production Hardening | 4-6 tuần | Vận hành ổn định, retry/recovery |
| Phase 2: IDP Intelligence | 10-12 tuần | Structured data extraction |
| Phase 3: Doc Management & Workflow | 8-10 tuần | Folder + search + webhook |
| Phase 4: Enterprise & Multi-tenant | 10-14 tuần | SSO, audit, billing |
| Phase 5: Scale & Intelligence | Liên tục | Active learning, on-premise |

---

*— Hết tài liệu —*