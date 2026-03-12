# Architecture Review Report
**Date:** 2026-03-10
**Reviewer Role:** Solution Architect
**Project:** OCR/IDP Platform (Self-Hosted, Vietnam Market)
**Phase:** Phase 1 Complete — Production Hardening

---

## 1. Tổng quan

- **Kiến trúc:** Modular Monolith Backend (FastAPI) + Distributed Workers (NATS JetStream) + S3 Storage (MinIO) + SPA Frontend (React)
- **Pattern:** Controller → Service → Repository (3-layer), Event-Driven Worker Pool
- **Đánh giá chung:** **ACCEPTABLE → GOOD**

Hệ thống được thiết kế với nền tảng vững chắc, cấu trúc rõ ràng, tuân thủ tốt nguyên tắc separation of concerns. Một số vấn đề kỹ thuật cần quan tâm trước khi scale lên multi-tenant hoặc high-traffic.

---

## 2. Điểm mạnh

### Kiến trúc & Tổ chức
- **3-layer pattern nhất quán:** Controller → Service → Repository được tuân thủ chặt chẽ toàn bộ backend. Không có endpoint nào gọi thẳng Repository, không có Repository nào chứa business logic.
- **Module boundary rõ ràng:** Mỗi module (`auth`, `upload`, `job`, `file_proxy`, `health`, `cleanup`) có `service.py`, `exceptions.py` riêng biệt, dễ test độc lập.
- **Infrastructure abstraction:** `IStorageService`, `IQueueService` interface cho phép swap MinIO/NATS bằng implementation khác mà không thay đổi business logic.
- **Worker isolation tốt:** Worker không access trực tiếp MinIO — mọi file operation đều qua `FileProxyClient` → backend ACL. Giảm attack surface đáng kể.

### Operational Readiness
- **NATS JetStream + DLQ:** Tin nhắn durable, retry có kiểm soát (exponential backoff), Dead Letter Queue cho job không thể recover.
- **APScheduler in-process:** Phù hợp cho single-instance Phase 1, tránh overhead Celery/Redis.
- **Health check thực sự:** Endpoint `/health` kiểm tra kết nối DB, NATS, MinIO thực tế — không hardcode `"ok"`.
- **Correlation ID xuyên suốt:** `X-Request-ID` được tạo ở middleware, gắn vào tất cả log entries — trace request dễ dàng.
- **Soft delete + Retention policy:** Xóa theo 2 bước (soft delete → `deleted` bucket → purge sau 7 ngày), tránh mất dữ liệu do thao tác nhầm.

### Developer Experience
- **CLAUDE.md + DEVELOPMENT_WORKFLOW.md:** Rules được tài liệu hóa tốt, giảm onboarding time.
- **Test coverage đầy đủ:** 14+ backend test modules, infra tests (DB/NATS/MinIO), worker integration tests.
- **Makefile automation:** `make up/down/build/create-admin` giảm manual setup.
- **Pydantic BaseSettings:** Config type-safe, fail-fast khi thiếu env var.

### Security Baseline
- **Magic bytes + MIME validation:** File upload không chỉ check extension — validate nội dung thực.
- **bcrypt password hashing:** Không lưu plain text hoặc MD5/SHA1.
- **Access key per worker:** Mỗi service type có access key riêng, admin approve trước khi worker hoạt động.
- **Rate limiting middleware:** Chống brute force cơ bản.

---

## 3. Vấn đề phát hiện

---

### VẤN ĐỀ 1: SQLite là Single Point of Failure

- **Vấn đề:** Toàn bộ platform dùng SQLite — single file, không hỗ trợ write concurrency thực sự (WAL cho phép concurrent reads, nhưng writes vẫn serialize). Không có replica hay failover.
- **Mức độ:** HIGH
- **Vị trí:** `02_backend/app/infrastructure/database/connection.py`
- **Tác động:** Khi file DB corrupt (disk failure, ungraceful shutdown), toàn bộ platform mất dữ liệu. Write throughput bị giới hạn ~1000 TPS. Không thể horizontal scale backend.
- **Đề xuất:**
  - **Ngắn hạn:** Thêm automated SQLite backup (daily snapshot lên MinIO bucket `backups`).
  - **Trung hạn:** Migration sang PostgreSQL trước Phase 3 (multi-tenant cần row-level security, better concurrency). Config đã abstract qua `DATABASE_URL` — swap vendor là feasible.
  - **Dài hạn:** Read replicas cho reporting/admin dashboard queries.

---

### VẤN ĐỀ 2: Migration Strategy Fragile

- **Vấn đề:** Database migrations được implement bằng `ALTER TABLE` statements hardcoded trong `connection.py._run_migrations()` chạy mỗi lần startup. Không có version tracking, không có rollback, không có tool như Alembic.
- **Mức độ:** HIGH
- **Vị trí:** `02_backend/app/infrastructure/database/connection.py` — `_run_migrations()`
- **Tác động:** Khi có nhiều migration, khó biết DB đang ở version nào. ALTER TABLE lặp lại mỗi startup gây chậm boot. Không rollback được khi migration lỗi ở production.
- **Đề xuất:**
  - Integrate **Alembic** với migration version table.
  - Hoặc implement lightweight migration runner với version tracking table (`schema_migrations`).
  - Tách migration ra file riêng (`migrations/`), không đặt trong `connection.py`.

---

### VẤN ĐỀ 3: Secret Management Không An Toàn

- **Vấn đề:** `config.py` có `secret_key: str = "your-secret-key-change-in-production"` làm default. Worker `access_key` cũng được lưu plaintext trong DB. Không có secret rotation mechanism.
- **Mức độ:** HIGH
- **Vị trí:** `02_backend/app/config.py`, `02_backend/app/infrastructure/database/models.py` (ServiceType)
- **Tác động:** Nếu deploy mà quên đổi secret key, session tokens có thể bị forge. DB leak → access keys lộ.
- **Đề xuất:**
  - Thêm validation trong config: raise error nếu `secret_key` == default value khi `ENV=production`.
  - Hash access keys trước khi lưu DB (verify bằng hash comparison, không lưu plaintext).
  - Document rõ trong deployment guide: các secrets cần rotate.

---

### VẤN ĐỀ 4: Không Có Observability Stack

- **Vấn đề:** Không có Prometheus metrics, không có distributed tracing (OpenTelemetry), không có alerting. Chỉ có JSON logs.
- **Mức độ:** HIGH
- **Vị trí:** `02_backend/app/core/logging.py`, `02_backend/app/core/middleware.py`
- **Tác động:** Khi production incident xảy ra, không biết: queue depth, job processing latency, error rate, worker utilization. Không có SLA visibility.
- **Đề xuất:**
  - **Ngắn hạn:** Thêm `prometheus-fastapi-instrumentator` — 5 lines code, có ngay HTTP metrics.
  - **Ngắn hạn:** Expose NATS JetStream metrics (queue depth, consumer lag).
  - **Trung hạn:** OpenTelemetry tracing từ API request → NATS publish → worker process.
  - `04_docs/04-Observability/` đã có kế hoạch — cần prioritize trước Phase 2 go-live.

---

### VẤN ĐỀ 5: APScheduler In-Process Không Scale Được

- **Vấn đề:** `APScheduler` chạy trong cùng process với FastAPI. Khi scale backend lên nhiều instance (horizontal), mỗi instance đều chạy heartbeat check và cleanup → duplicate execution, race conditions.
- **Mức độ:** MEDIUM
- **Vị trí:** `02_backend/app/core/scheduler.py`, `02_backend/app/core/lifespan.py`
- **Tác động:** Khi scale lên 2+ backend instances: `heartbeat_check` chạy 2 lần/interval, có thể mark worker DEAD 2 lần; cleanup job có thể delete file đang được processed.
- **Đề xuất:**
  - **Ngắn hạn (single-instance):** Document rõ đây là single-instance deployment. Thêm env var `SCHEDULER_ENABLED=true/false`.
  - **Trung hạn:** Dùng distributed lock (Redis `SET NX EX` hoặc DB advisory lock) để chỉ 1 instance chạy scheduler tại một thời điểm.
  - **Dài hạn:** Tách scheduler ra dedicated process/service.

---

### VẤN ĐỀ 6: CORS Configuration Quá Rộng Trong Development

- **Vấn đề:** `cors_origins: str = "http://localhost:5173"` là default. Không có validation tự động restrict khi deploy production.
- **Mức độ:** MEDIUM
- **Vị trí:** `02_backend/app/config.py`
- **Tác động:** Nếu production config chưa được set đúng, CORS có thể allow requests từ localhost trên production server (ít rủi ro) hoặc ngược lại — production origin bị block (user impact).
- **Đề xuất:**
  - Validate CORS origins là HTTPS khi `ENV=production`.
  - Support list format: `cors_origins: list[str]` thay vì comma-separated string.

---

### VẤN ĐỀ 7: Audit Log Chưa Đầy Đủ

- **Vấn đề:** `AuditLog` model tồn tại và `AuditLogRepository` implemented, nhưng chỉ admin actions (approve/reject service type) được log. User actions quan trọng (upload, cancel, download result) không có audit trail.
- **Mức độ:** MEDIUM
- **Vị trí:** `02_backend/app/infrastructure/database/repositories/audit_log.py`, `02_backend/app/modules/upload/service.py`
- **Tác động:** Không forensic được khi có data breach hoặc user dispute ("tôi không upload file này"). Vi phạm compliance requirements cho enterprise.
- **Đề xuất:**
  - Log ít nhất: upload (user, files, request_id), download result, cancel request/job.
  - Tạo helper `audit_service.log_user_action()` để dễ gọi từ endpoint handlers.
  - Cân nhắc async audit logging để không impact request latency.

---

### VẤN ĐỀ 8: Thiếu Request Timeout và Circuit Breaker

- **Vấn đề:** Worker → Backend HTTP calls (`FileProxyClient`, `OrchestratorClient`) không có circuit breaker. Nếu backend slow/down, workers block indefinitely.
- **Mức độ:** MEDIUM
- **Vị trí:** `03_worker/app/clients/file_proxy_client.py`, `03_worker/app/clients/orchestrator_client.py`
- **Tác động:** Network partition → workers đứng, không process job mới, NATS messages accumulate. Recovery sau khi backend lên lại: sudden burst load.
- **Đề xuất:**
  - Thêm explicit timeout cho tất cả HTTP calls: `httpx.AsyncClient(timeout=30.0)`.
  - Implement simple circuit breaker (count consecutive failures → stop retrying → periodic probe).
  - Hoặc dùng thư viện `tenacity` cho retry với backoff + circuit breaker pattern.

---

### VẤN ĐỀ 9: File Preview Không Có Size Limit

- **Vấn đề:** `GET /api/v1/files/{id}/preview` stream file về client. Không rõ có giới hạn file size cho preview không. PDF/image lớn (50MB) → memory spike trong backend.
- **Mức độ:** MEDIUM
- **Vị trí:** `02_backend/app/api/v1/endpoints/files.py`
- **Tác động:** Malicious user upload 50MB file rồi liên tục request preview → DoS backend memory.
- **Đề xuất:**
  - Cap preview size (e.g., 10MB). Files lớn hơn → return presigned MinIO URL thay vì stream qua backend.
  - Dùng `StreamingResponse` với chunk size limit.
  - Apply rate limit riêng cho `/files/*/preview` endpoint.

---

### VẤN ĐỀ 10: Worker Registration Không Có Auto-Deregistration

- **Vấn đề:** Worker register khi start, nhưng nếu crash (not graceful shutdown), instance record vẫn tồn tại trong DB với status ACTIVE. `HeartbeatMonitor` sẽ detect sau N phút, nhưng trong khoảng thời gian đó instance có thể nhận job từ NATS mà không có worker handle.
- **Mức độ:** LOW
- **Vị trí:** `02_backend/app/modules/job/heartbeat_monitor.py`, `03_worker/app/core/worker.py`
- **Tác động:** Jobs có thể bị delay N phút (heartbeat check interval) trước khi được requeue.
- **Đề xuất:**
  - Giảm heartbeat timeout threshold cho tier0 workers (đang xử lý time-sensitive jobs).
  - Expose config `stalled_threshold_minutes` per service type.
  - Hiện tại đây là acceptable behavior — document rõ trong runbook.

---

### VẤN ĐỀ 11: Frontend API Client Thiếu Interceptor Cho Token Expiry

- **Vấn đề:** Nếu session token expire trong khi user đang dùng app, API calls trả về 401. Frontend cần xử lý gracefully (redirect login, clear session).
- **Mức độ:** LOW
- **Vị trí:** `01_frontend/src/api/`
- **Tác động:** UX xấu — user thấy error toast thay vì được redirect login.
- **Đề xuất:**
  - Thêm Axios response interceptor: nếu 401 → clear local session → redirect `/login`.
  - Đây là common pattern, implementation đơn giản.

---

## 4. Architecture Decision Records (Đề xuất Xem Lại)

| ADR | Quyết định hiện tại | Nên xem xét lại khi |
|-----|---------------------|---------------------|
| ADR-005 | SQLite WAL | Trước Phase 3 (multi-tenant) — migrate sang PostgreSQL |
| ADR-003 | APScheduler in-process | Trước scale lên 2+ backend instances — distributed lock hoặc dedicated scheduler |
| ADR-004 | Session token (DB lookup mỗi request) | Khi cần performance scale — xem xét JWT signed (không cần DB lookup), hoặc Redis session cache |
| — | Không có migration tool | Ngay bây giờ — adopt Alembic trước khi schema phức tạp hơn |
| — | Worker access key plaintext trong DB | Ngay bây giờ — hash trước khi lưu |

---

## 5. Recommendations

### Ngắn hạn (Quick wins — có thể làm trong sprint tiếp theo)

1. **Thêm Prometheus metrics** — `prometheus-fastapi-instrumentator`, ~10 lines. Metrics: request rate, latency, error rate, queue depth.
2. **SQLite automated backup** — Scheduled task (đã có scheduler), copy file DB lên MinIO bucket `backups` mỗi ngày.
3. **Hardcode secret_key protection** — Raise `ValueError` trong `config.py` nếu `secret_key` == default và `ENV=production`.
4. **HTTP timeout cho worker clients** — Thêm `timeout=30.0` vào tất cả `httpx.AsyncClient()` trong `03_worker/app/clients/`.
5. **Axios 401 interceptor** — Frontend redirect to login on session expire.
6. **Hash worker access keys** — Lưu hash, verify bằng comparison.

### Trung hạn (Cần planning — 2-4 tuần)

1. **Database migration tool** — Adopt Alembic, tạo initial migration từ models hiện tại, version tracking table.
2. **Distributed scheduler lock** — Redis hoặc DB advisory lock để prevent duplicate scheduler execution khi multi-instance.
3. **Audit log mở rộng** — Log user actions quan trọng: upload, download, cancel. Async write để không block request.
4. **File preview size cap** — Giới hạn preview size, redirect lớn sang presigned URL.
5. **CORS config validation** — Strict HTTPS check cho production environment.
6. **OpenTelemetry tracing** — Request → NATS → Worker trace, integrate với Jaeger hoặc Zipkin.

### Dài hạn (Cần roadmap — Phase 3+)

1. **PostgreSQL migration** — Trước Phase 3 (multi-tenant). Connection pooling với PgBouncer, read replicas cho analytics.
2. **Dedicated scheduler service** — Tách APScheduler ra, dùng APScheduler JobStore với PostgreSQL hoặc switch sang Temporal/Celery Beat.
3. **Kubernetes deployment** — Horizontal scaling workers, Backend autoscaling, NATS cluster mode.
4. **Secret management system** — HashiCorp Vault hoặc cloud provider secrets manager. Secret rotation automation.
5. **RBAC** — Thay thế `is_admin` boolean flag bằng role-based permissions (cần cho Phase 4 enterprise).
6. **Multi-tenancy isolation** — Row-level security ở DB, bucket isolation ở MinIO, subject namespacing ở NATS.

---

## 6. Tổng kết điểm đánh giá

| Khía cạnh | Điểm (1-5) | Ghi chú |
|-----------|-----------|---------|
| High-level Architecture | 4/5 | 3-layer rõ ràng, phù hợp quy mô |
| Module & Separation of Concerns | 4/5 | Clean, nhất quán |
| Dependency & Coupling | 4/5 | Loose coupling qua interfaces |
| Data Flow & Communication | 4/5 | NATS routing tốt, FileProxy đúng |
| Database & Data Architecture | 2/5 | SQLite OK cho Phase 1, fragile migration |
| Scalability & Extensibility | 3/5 | Architecture OK, SQLite/Scheduler giới hạn |
| Error Handling & Resilience | 3/5 | Retry/DLQ tốt, thiếu circuit breaker |
| API Design | 4/5 | Nhất quán, versioned, internal/public separation |
| Security | 3/5 | Baseline tốt, cần hardening ở production |
| Observability | 2/5 | Logs OK, thiếu metrics & tracing |
| **Tổng** | **33/50** | **ACCEPTABLE → GOOD** |

---

*Review này được tạo dựa trên phân tích toàn bộ codebase tại thời điểm 2026-03-10 — Phase 1 Complete.*
*Tham khảo thêm: `04_docs/project-management/PROJECT_CONTEXT.md`, `04_docs/07-roadmap/next-action.md`*
