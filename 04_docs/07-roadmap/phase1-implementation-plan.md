# Phase 1: Production Hardening — Implementation Plan

> **Scope:** Biến POC thành sản phẩm self-host vận hành thực tế. Không bao gồm external API integration.
> **Nguyên tắc:** Hoàn thiện từng module độc lập, test riêng, sau đó tích hợp.
> **Cập nhật:** 2026-03-07 (rev.1 — loại bỏ M10 API Key, hệ thống self-host thuần)

---

## Tổng Quan Dependency Graph

```
Sprint 1 (Foundation — Song song, không phụ thuộc nhau)
├── M1: JobStateMachine.get_request_status()     [pure logic]
├── M5: Background Scheduler (APScheduler)        [infrastructure]
├── M7: Real Health Check                         [independent]
└── M9: Rate Limiting Middleware                   [independent]

Sprint 2 (Core Orchestration — Tuần tự)
├── M2: JobService Refactor                       [depends: M1]
├── M3: RetryOrchestrator + DLQ                   [depends: M2]
└── M6: Request Status Auto-Update                [depends: M2, M3]

Sprint 3 (Monitoring & Cleanup — Sau Sprint 1+2)
├── M4: HeartbeatMonitor + Stalled Recovery       [depends: M2, M3, M5]
└── M8: Retention Cleanup                         [depends: M5]

Sprint 4 (Frontend & CI/CD — Song song với Sprint 2-3)
├── M11: Frontend Error Handling UX               [independent]
└── M12: CI/CD Pipeline                           [independent]

> **Note:** M10 (API Key Authentication) đã loại khỏi Phase 1.
> Hệ thống self-host thuần, chỉ dùng session-based auth cho Web UI.
> API Key cho external integration sẽ xem xét ở phase sau nếu cần.
```

---

## Sprint 1: Foundation (Song song)

### M1: JobStateMachine — Request Status Aggregation

**Mục tiêu:** Implement `get_request_status()` để tính toán status của Request từ danh sách Job statuses.

**File:** `02_backend/app/modules/job/state_machine.py`

**Logic cần implement:**

```python
@staticmethod
def get_request_status(jobs: list) -> str:
    """
    Rules:
    1. Nếu không có jobs → "PROCESSING"
    2. Nếu có bất kỳ job PROCESSING/QUEUED/SUBMITTED → "PROCESSING"
    3. Nếu tất cả COMPLETED → "COMPLETED"
    4. Nếu tất cả FAILED/DEAD_LETTER → "FAILED"
    5. Nếu tất cả CANCELLED → "CANCELLED"
    6. Nếu mix (có COMPLETED + FAILED/CANCELLED) → "PARTIAL_SUCCESS"
    7. Nếu tất cả terminal nhưng không cùng loại → "PARTIAL_SUCCESS"
    """
```

**Test:** `00_test/backend/test_state_machine.py`
- Test empty jobs list
- Test all COMPLETED
- Test all FAILED
- Test mixed statuses
- Test with PROCESSING jobs
- Test CANCELLED scenarios

**Acceptance criteria:**
- [x] Pure logic, no DB dependency
- [x] Unit tests cover all status combinations
- [x] No changes to other files

---

### M5: Background Scheduler (APScheduler)

**Mục tiêu:** Thiết lập APScheduler chạy in-process, quản lý bởi FastAPI lifespan.

**Files cần tạo/sửa:**

1. **Tạo mới:** `02_backend/app/core/scheduler.py`
   ```python
   # APScheduler setup
   from apscheduler.schedulers.asyncio import AsyncIOScheduler

   scheduler = AsyncIOScheduler()

   def init_scheduler():
       """Register all periodic jobs. Called during startup."""
       # Placeholder — các module khác sẽ register task ở đây
       # scheduler.add_job(func, 'interval', seconds=60, id='heartbeat_check')
       scheduler.start()

   def shutdown_scheduler():
       """Graceful shutdown."""
       scheduler.shutdown(wait=False)
   ```

2. **Sửa:** `02_backend/app/core/lifespan.py`
   - Import `init_scheduler`, `shutdown_scheduler`
   - Gọi `init_scheduler()` trong `startup()`
   - Gọi `shutdown_scheduler()` trong `shutdown()`

3. **Sửa:** `02_backend/requirements.txt`
   - Thêm `APScheduler>=3.10`

**Test:** `00_test/backend/test_scheduler.py`
- Verify scheduler starts/stops without errors
- Verify job registration works

**Acceptance criteria:**
- [x] Scheduler start/stop trong lifespan
- [x] Không ảnh hưởng startup time
- [x] Ready để M4, M8 register periodic tasks

---

### M7: Real Health Check

**Mục tiêu:** Health check endpoint thực sự verify DB, NATS, MinIO connections.

**Files cần sửa:**

1. **Tạo mới:** `02_backend/app/modules/health/service.py`
   ```python
   class HealthService:
       async def check_database(self) -> dict:
           """Execute SELECT 1 on SQLite."""
           # Return {"status": "healthy"/"unhealthy", "latency_ms": float}

       async def check_nats(self) -> dict:
           """Check NATS connection status."""
           # Return {"status": "healthy"/"unhealthy", "connected": bool}

       async def check_minio(self) -> dict:
           """List buckets to verify MinIO."""
           # Return {"status": "healthy"/"unhealthy", "buckets": int}

       async def check_all(self) -> dict:
           """Run all checks, return aggregate status."""
           # Return {"status": "healthy"/"degraded"/"unhealthy", "checks": {...}}
   ```

2. **Sửa:** `02_backend/app/main.py` — endpoint `/health`
   ```python
   @app.get("/health")
   async def health_check():
       service = HealthService(db, storage_service, queue_service)
       result = await service.check_all()
       status_code = 200 if result["status"] != "unhealthy" else 503
       return JSONResponse(content=result, status_code=status_code)
   ```

3. **Tạo mới:** `02_backend/app/modules/health/__init__.py`

**Test:** `00_test/backend/test_health.py`
- Test healthy response
- Test degraded (one service down)
- Test unhealthy (DB down)

**Acceptance criteria:**
- [x] Returns 200 khi healthy, 503 khi unhealthy
- [x] Bao gồm latency cho mỗi service
- [x] Docker healthcheck hoạt động đúng

---

### M9: Rate Limiting Middleware

**Mục tiêu:** Giới hạn request rate để chống abuse.

**Files cần tạo/sửa:**

1. **Tạo mới:** `02_backend/app/core/rate_limiter.py`
   ```python
   # In-memory rate limiter (đủ cho single-instance Phase 1)
   # Có thể chuyển sang Redis ở Phase 5

   class RateLimiter:
       """Token bucket rate limiter."""
       def __init__(self):
           self._buckets: dict[str, TokenBucket] = {}

       async def check(self, key: str, limit: int, window_seconds: int) -> bool:
           """Return True if request is allowed."""

   class RateLimitMiddleware(BaseHTTPMiddleware):
       """Apply rate limiting per IP or per user."""
       RATE_LIMITS = {
           "/api/v1/upload": (10, 60),    # 10 req/min
           "/api/v1/auth/login": (5, 60),  # 5 req/min
           "/api/v1/auth/register": (3, 60), # 3 req/min
           "default": (60, 60),            # 60 req/min
       }
   ```

2. **Sửa:** `02_backend/app/core/middleware.py`
   - Import `RateLimitMiddleware`
   - Add vào `setup_middleware()`

3. **Sửa:** `02_backend/app/config.py`
   - Thêm `rate_limit_enabled: bool = True`

**Test:** `00_test/backend/test_rate_limiter.py`
- Test under limit → allowed
- Test over limit → 429
- Test different endpoints have different limits
- Test limit resets after window

**Acceptance criteria:**
- [x] 429 Too Many Requests khi vượt limit
- [x] Header `X-RateLimit-Remaining` và `X-RateLimit-Reset`
- [x] Configurable qua settings
- [x] Không block internal endpoints (`/api/v1/internal/*`)

---

### ~~M10: API Key Authentication~~ — LOẠI KHỎI SCOPE

> Hệ thống self-host thuần, chỉ dùng session-based auth cho Web UI.
> API Key cho external integration sẽ xem xét ở phase sau nếu mở rộng ra SaaS/API public.

---

## Sprint 2: Core Orchestration (Tuần tự)

### M2: JobService Refactor

**Mục tiêu:** Centralize tất cả job logic vào `JobService`. Endpoints gọi qua service, không gọi repo trực tiếp.

**Files cần sửa:**

1. **Sửa:** `02_backend/app/modules/job/service.py` — Implement đầy đủ
   ```python
   class JobService:
       def __init__(self, db: Session, queue: NATSQueueService = None):
           self.db = db
           self.queue = queue
           self.job_repo = JobRepository(db)
           self.request_repo = RequestRepository(db)
           self.file_repo = FileRepository(db)
           self.state_machine = JobStateMachine()

       async def get_request(self, request_id: str, user_id: str) -> Request | None:
           """Get request, verify ownership."""
           request = self.request_repo.get_active(request_id)
           if request and request.user_id != user_id:
               return None
           return request

       async def get_request_with_jobs(self, request_id: str, user_id: str) -> tuple[Request, list[Job]] | None:
           """Get request with its jobs."""

       async def get_job(self, job_id: str, user_id: str) -> Job | None:
           """Get job, verify ownership via request."""

       async def get_job_result(self, job_id: str, user_id: str, storage) -> tuple[Job, bytes]:
           """Get job result content."""

       async def cancel_request(self, request_id: str, user_id: str) -> dict:
           """Cancel all QUEUED jobs in request."""

       async def cancel_job(self, job_id: str, user_id: str) -> dict:
           """Cancel single QUEUED job."""

       async def update_job_status(
           self, job_id: str, status: str, worker_id: str,
           error: str = None, retriable: bool = True, engine_version: str = None,
       ) -> Job:
           """Update job status + trigger request status recalculation.
           Called by internal endpoint (worker callback).
           """
           job = self.job_repo.get_active(job_id)
           # 1. Validate transition via state_machine
           # 2. Update job status via repo
           # 3. Update request counters (completed_files, failed_files)
           # 4. Recalculate request status via get_request_status()
           # 5. If FAILED + retriable → delegate to RetryOrchestrator (M3)
           # 6. Return updated job

       def _recalculate_request_status(self, request: Request) -> None:
           """Fetch all jobs for request, compute aggregate status, update request."""
           jobs = self.job_repo.get_by_request(request.id)
           new_status = self.state_machine.get_request_status(jobs)
           if new_status != request.status:
               self.request_repo.update_status(request, new_status)
   ```

2. **Sửa:** `02_backend/app/api/v1/endpoints/requests.py`
   - Import `JobService`
   - Refactor `get_requests()` — keep as-is (listing uses repo directly, OK for read-only)
   - Refactor `get_request()` → dùng `job_service.get_request_with_jobs()`
   - Refactor `cancel_request()` → dùng `job_service.cancel_request()`

3. **Sửa:** `02_backend/app/api/v1/endpoints/jobs.py`
   - Refactor `get_job()` → dùng `job_service.get_job()`
   - Refactor `get_job_result()` → dùng `job_service.get_job_result()`
   - Refactor `cancel_job()` → dùng `job_service.cancel_job()`

4. **Sửa:** `02_backend/app/api/v1/internal/job_status.py`
   - Refactor `update_job_status()` → dùng `job_service.update_job_status()`
   - Đây là điểm tích hợp quan trọng nhất: khi worker report status, service tự động:
     - Update job
     - Update request counters
     - Recalculate request status
     - Trigger retry nếu cần (M3)

5. **Tạo mới:** `02_backend/app/api/deps.py` — thêm dependency
   ```python
   def get_job_service(db=Depends(get_db), queue=Depends(get_queue)) -> JobService:
       return JobService(db, queue)
   ```

**Test:** `00_test/backend/test_job_service.py`
- Test update_job_status triggers request status recalculation
- Test cancel_request only cancels QUEUED jobs
- Test ownership verification
- Test state transition validation

**Acceptance criteria:**
- [x] Endpoints chỉ gọi JobService, không gọi repo trực tiếp (trừ read-only listing)
- [x] Request status tự động cập nhật khi job status thay đổi
- [x] Request counters (completed_files, failed_files) chính xác
- [x] Không break existing API contracts

---

### M3: RetryOrchestrator + DLQ

**Mục tiêu:** Implement retry logic và Dead Letter Queue.

**Files cần sửa:**

1. **Sửa:** `02_backend/app/modules/job/orchestrator.py`
   ```python
   class RetryOrchestrator:
       MAX_RETRIES = 3

       def __init__(self, db: Session, queue: NATSQueueService):
           self.db = db
           self.queue = queue
           self.job_repo = JobRepository(db)

       async def handle_failure(self, job: Job, error: str, retriable: bool) -> None:
           """Handle job failure. Called by JobService.update_job_status()."""
           if retriable and job.retry_count < self.MAX_RETRIES:
               await self.requeue_job(job)
           else:
               await self.move_to_dlq(job)

       async def decide_retry_or_dlq(self, job: Job) -> str:
           """Decide action based on error history and retry count."""
           if job.retry_count >= self.MAX_RETRIES:
               return "dlq"
           history = json.loads(job.error_history or "[]")
           if history and not history[-1].get("retriable", True):
               return "dlq"
           return "retry"

       async def requeue_job(self, job: Job) -> None:
           """Requeue job for retry."""
           # 1. Increment retry count
           self.job_repo.increment_retry(job)
           # 2. Reset status to QUEUED
           self.job_repo.update_status(job, status="QUEUED")
           # 3. Publish to NATS with retry_count
           subject = get_subject(job.method, job.tier)
           message = JobMessage(
               job_id=job.id,
               file_id=job.file_id,
               request_id=job.request_id,
               method=job.method,
               tier=job.tier,
               output_format=job.request.output_format,
               object_key=...,  # Get from file record
               retry_count=job.retry_count,
           )
           await self.queue.publish(subject, message)

       async def move_to_dlq(self, job: Job) -> None:
           """Move job to Dead Letter Queue."""
           # 1. Update status to DEAD_LETTER
           self.job_repo.update_status(job, status="DEAD_LETTER")
           # 2. Publish to DLQ stream
           dlq_subject = f"dlq.{job.method}.tier{job.tier}"
           message = JobMessage(
               job_id=job.id,
               file_id=job.file_id,
               request_id=job.request_id,
               method=job.method,
               tier=job.tier,
               output_format=job.request.output_format,
               object_key=...,
               retry_count=job.retry_count,
           )
           await self.queue.publish(dlq_subject, message)
   ```

2. **Sửa:** `02_backend/app/modules/job/service.py`
   - `update_job_status()` gọi `RetryOrchestrator.handle_failure()` khi status == FAILED

3. **Sửa:** `02_backend/app/config.py`
   - Thêm `max_job_retries: int = 3`

**Test:** `00_test/backend/test_retry_orchestrator.py`
- Test retriable failure → requeue
- Test non-retriable failure → DLQ
- Test max retries exceeded → DLQ
- Test retry count increment
- Test DLQ message published to correct subject
- Test NATS publish called with correct message

**Acceptance criteria:**
- [x] Job retry tự động khi worker report FAILED + retriable
- [x] Max 3 retries, sau đó vào DLQ
- [x] DLQ message chứa đủ thông tin để debug
- [x] retry_count chính xác trong DB và message

---

### M6: Request Status Auto-Update (Integration)

**Mục tiêu:** Đảm bảo Request status luôn phản ánh đúng trạng thái tổng hợp từ các Jobs.

**Đây là integration module** — đã được implement bên trong M2 (`JobService._recalculate_request_status()`). Module này chỉ cần verify qua integration test.

**Test:** `00_test/backend/test_request_status_integration.py`
- Upload batch 3 files
- Complete 1 job → request vẫn PROCESSING
- Complete 2 jobs → request vẫn PROCESSING
- Complete 3 jobs → request chuyển COMPLETED
- Scenario: 2 completed + 1 failed → PARTIAL_SUCCESS
- Scenario: All failed → FAILED
- Scenario: Cancel 1 + complete 2 → PARTIAL_SUCCESS

**Acceptance criteria:**
- [x] Request status chuyển đổi chính xác theo tất cả scenarios
- [x] `completed_files` và `failed_files` counters đúng
- [x] `completed_at` được set khi request reach terminal state

---

## Sprint 3: Monitoring & Cleanup

### M4: HeartbeatMonitor + Stalled Job Recovery

**Mục tiêu:** Detect worker chết và recover các job đang PROCESSING trên worker đó.

**Files cần sửa:**

1. **Sửa:** `02_backend/app/modules/job/heartbeat_monitor.py`
   ```python
   class HeartbeatMonitor:
       HEARTBEAT_TIMEOUT_SECONDS = 90   # 3 missed heartbeats
       STALLED_JOB_TIMEOUT_SECONDS = 600  # 10 minutes

       def __init__(self, db: Session, retry_orchestrator: RetryOrchestrator = None):
           self.db = db
           self.instance_repo = ServiceInstanceRepository(db)
           self.heartbeat_repo = HeartbeatRepository(db)
           self.job_repo = JobRepository(db)
           self.retry_orchestrator = retry_orchestrator

       async def check_workers(self) -> list[str]:
           """Find dead workers (no heartbeat in timeout period)."""
           stale = self.instance_repo.get_stale_instances(self.HEARTBEAT_TIMEOUT_SECONDS)
           dead_ids = []
           for instance in stale:
               self.instance_repo.mark_dead(instance)
               dead_ids.append(instance.id)
           return dead_ids

       async def detect_stalled(self) -> list[Job]:
           """Find PROCESSING jobs on dead workers."""
           dead_workers = await self.check_workers()
           stalled_jobs = []
           for worker_id in dead_workers:
               jobs = self.job_repo.get_processing_by_worker(worker_id)
               stalled_jobs.extend(jobs)
           return stalled_jobs

       async def recover_stalled_jobs(self, jobs: list[Job]) -> None:
           """Requeue stalled jobs via RetryOrchestrator."""
           for job in jobs:
               await self.retry_orchestrator.handle_failure(
                   job, error="Worker died (heartbeat timeout)", retriable=True
               )

       async def run_check(self) -> dict:
           """Full check cycle — called by scheduler."""
           stalled = await self.detect_stalled()
           if stalled:
               await self.recover_stalled_jobs(stalled)
           # Cleanup old heartbeat records
           cleaned = self.heartbeat_repo.cleanup_old(keep_hours=24)
           return {"stalled_recovered": len(stalled), "heartbeats_cleaned": cleaned}
   ```

2. **Sửa:** `02_backend/app/core/scheduler.py`
   - Register `heartbeat_monitor.run_check()` interval=60s

3. **Sửa:** `02_backend/app/core/lifespan.py`
   - Initialize HeartbeatMonitor + register in scheduler during startup

**Test:** `00_test/backend/test_heartbeat_monitor.py`
- Test detect stale workers
- Test detect stalled jobs on dead workers
- Test recovery requeues jobs
- Test cleanup old heartbeats
- Test no false positives (active workers not flagged)

**Acceptance criteria:**
- [x] Stalled jobs auto-recovered within 90s of worker death
- [x] Recovery goes through RetryOrchestrator (respects max retries)
- [x] Old heartbeat records cleaned up daily
- [x] Runs every 60s via scheduler

---

### M8: Retention Cleanup

**Mục tiêu:** Tự động xóa files hết hạn retention.

**Files cần tạo/sửa:**

1. **Tạo mới:** `02_backend/app/modules/cleanup/service.py`
   ```python
   class RetentionCleanupService:
       def __init__(self, db: Session, storage: MinIOStorageService):
           self.db = db
           self.storage = storage
           self.request_repo = RequestRepository(db)
           self.file_repo = FileRepository(db)
           self.job_repo = JobRepository(db)

       async def cleanup_expired(self) -> dict:
           """Find and delete expired requests + their files."""
           # 1. Query requests where expires_at < now AND deleted_at IS NULL
           # 2. For each expired request:
           #    a. Move files from uploads/ and results/ to deleted/ bucket
           #    b. Soft-delete request, files, jobs in DB
           # 3. Return summary

       async def purge_deleted(self, older_than_hours: int = 168) -> dict:
           """Permanently delete files from deleted/ bucket older than threshold."""
           # 1. Query soft-deleted requests where deleted_at < now - older_than_hours
           # 2. Permanently remove from MinIO deleted/ bucket
           # 3. Hard-delete from DB
           # 4. Return summary
   ```

2. **Tạo mới:** `02_backend/app/modules/cleanup/__init__.py`

3. **Sửa:** `02_backend/app/infrastructure/database/repositories/request.py`
   - Thêm `get_expired()` method
   ```python
   def get_expired(self, limit: int = 100) -> list[Request]:
       """Get expired requests (expires_at < now, not deleted)."""
       return self.db.query(Request).filter(
           Request.expires_at < datetime.now(timezone.utc),
           Request.deleted_at.is_(None)
       ).limit(limit).all()
   ```

4. **Sửa:** `02_backend/app/core/scheduler.py`
   - Register `cleanup_service.cleanup_expired()` interval=1 hour
   - Register `cleanup_service.purge_deleted()` interval=24 hours

**Test:** `00_test/backend/test_retention_cleanup.py`
- Test expired request detected
- Test files moved to deleted bucket
- Test DB records soft-deleted
- Test purge removes from storage permanently
- Test non-expired requests not affected

**Acceptance criteria:**
- [x] Expired files moved (not deleted) first
- [x] Permanent delete after additional grace period (7 days default)
- [x] DB records cleaned up
- [x] Runs hourly via scheduler

---

## Sprint 4: Frontend & CI/CD (Song song)

### M11: Frontend Error Handling UX

**Mục tiêu:** Toast notifications, error states, skeleton loading.

**Files cần tạo/sửa:**

1. **Tạo mới:** `01_frontend/src/components/common/Toast.tsx`
   ```typescript
   // Toast notification system
   // Types: success, error, warning, info
   // Auto-dismiss after 5s (configurable)
   // Stack multiple toasts
   ```

2. **Tạo mới:** `01_frontend/src/context/ToastContext.tsx`
   ```typescript
   // React context + provider for global toast management
   // useToast() hook: { showSuccess, showError, showWarning, showInfo }
   ```

3. **Tạo mới:** `01_frontend/src/components/common/Skeleton.tsx`
   ```typescript
   // Skeleton loading components
   // SkeletonText, SkeletonCard, SkeletonTable
   ```

4. **Sửa:** `01_frontend/src/api/client.ts`
   ```typescript
   // Response interceptor — trigger toast on error
   client.interceptors.response.use(
     (response) => response,
     (error) => {
       // 429: "Too many requests, please slow down"
       // 500: "Server error, please try again"
       // Network error: "Connection lost, checking..."
       // Emit event for toast system
     }
   )
   ```

5. **Sửa:** `01_frontend/src/components/upload/UploadProgress.tsx`
   - Hiển thị retry state: "Retrying (2/3)..."
   - Hiển thị error với message rõ ràng

6. **Sửa:** `01_frontend/src/components/batch/BatchStatus.tsx`
   - Thêm PARTIAL_SUCCESS, DEAD_LETTER status badges
   - Thêm retry count indicator

7. **Sửa:** `01_frontend/src/components/result/ResultViewer.tsx` (hoặc tương đương)
   - Skeleton loading khi đang fetch result
   - Error state khi fetch thất bại

8. **Sửa:** `01_frontend/src/pages/BatchesPage.tsx`
   - Skeleton loading cho table
   - Empty state khi không có data

9. **Sửa:** `01_frontend/src/App.tsx`
   - Wrap với `ToastProvider`

**Test:** Manual testing + Vitest unit tests nếu có setup
- Toast hiển thị khi API error
- Toast hiển thị khi upload thành công
- Skeleton loading khi data đang fetch
- Status badges hiển thị đúng cho mọi trạng thái

**Acceptance criteria:**
- [x] Mọi API error có toast notification
- [x] Upload success/failure có toast
- [x] Skeleton loading cho tất cả data-fetching pages
- [x] Retry status visible trên UI
- [x] PARTIAL_SUCCESS, DEAD_LETTER có badge phù hợp

---

### M12: CI/CD Pipeline

**Mục tiêu:** GitHub Actions pipeline chạy test tự động.

**Files cần tạo:**

1. **Tạo mới:** `.github/workflows/ci.yml`
   ```yaml
   name: CI
   on: [push, pull_request]
   jobs:
     backend-test:
       runs-on: ubuntu-latest
       services:
         minio: ...
         nats: ...
       steps:
         - checkout
         - setup python 3.12
         - pip install -r 02_backend/requirements.txt
         - pytest 00_test/ --tb=short

     frontend-lint:
       runs-on: ubuntu-latest
       steps:
         - checkout
         - setup node 20
         - cd 01_frontend && npm ci
         - npm run lint
         - npm run type-check

     docker-build:
       runs-on: ubuntu-latest
       steps:
         - checkout
         - docker compose build
   ```

2. **Sửa:** `01_frontend/package.json`
   - Thêm script `type-check`: `tsc --noEmit`

**Acceptance criteria:**
- [x] CI chạy trên mỗi push/PR
- [x] Backend tests pass
- [x] Frontend lint + type-check pass
- [x] Docker build success

---

## Tổng Hợp Files Thay Đổi

### Files mới tạo (9 files)
| File | Module |
|---|---|
| `02_backend/app/core/scheduler.py` | M5 |
| `02_backend/app/core/rate_limiter.py` | M9 |
| `02_backend/app/modules/health/__init__.py` | M7 |
| `02_backend/app/modules/health/service.py` | M7 |
| `02_backend/app/modules/cleanup/__init__.py` | M8 |
| `02_backend/app/modules/cleanup/service.py` | M8 |
| `01_frontend/src/components/common/Toast.tsx` | M11 |
| `01_frontend/src/context/ToastContext.tsx` | M11 |
| `01_frontend/src/components/common/Skeleton.tsx` | M11 |

### Files sửa (14 files)
| File | Modules |
|---|---|
| `02_backend/app/modules/job/state_machine.py` | M1 |
| `02_backend/app/modules/job/service.py` | M2 |
| `02_backend/app/modules/job/orchestrator.py` | M3 |
| `02_backend/app/modules/job/heartbeat_monitor.py` | M4 |
| `02_backend/app/core/lifespan.py` | M5, M4, M8 |
| `02_backend/app/core/middleware.py` | M9 |
| `02_backend/app/main.py` | M7 |
| `02_backend/app/config.py` | M9 |
| `02_backend/app/api/deps.py` | M2 |
| `02_backend/app/api/v1/endpoints/requests.py` | M2 |
| `02_backend/app/api/v1/endpoints/jobs.py` | M2 |
| `02_backend/app/api/v1/internal/job_status.py` | M2 |
| `02_backend/app/infrastructure/database/repositories/request.py` | M8 |
| `02_backend/requirements.txt` | M5 |

### Test files mới (8 files)
| File | Module |
|---|---|
| `00_test/backend/test_state_machine.py` | M1 |
| `00_test/backend/test_scheduler.py` | M5 |
| `00_test/backend/test_health.py` | M7 |
| `00_test/backend/test_rate_limiter.py` | M9 |
| `00_test/backend/test_job_service.py` | M2 |
| `00_test/backend/test_retry_orchestrator.py` | M3 |
| `00_test/backend/test_request_status_integration.py` | M6 |
| `00_test/backend/test_heartbeat_monitor.py` | M4 |
| `00_test/backend/test_retention_cleanup.py` | M8 |

---

## Checklist Tổng Thể

| Sprint | Module | Status | Ngày hoàn thành |
|:---:|---|:---:|---|
| 1 | M1: JobStateMachine.get_request_status() | DONE | 2026-03-07 |
| 1 | M5: Background Scheduler | DONE | 2026-03-07 |
| 1 | M7: Real Health Check | DONE | 2026-03-07 |
| 1 | M9: Rate Limiting | DONE | 2026-03-07 |
| 2 | M2: JobService Refactor | DONE | 2026-03-07 |
| 2 | M3: RetryOrchestrator + DLQ | DONE | 2026-03-07 |
| 2 | M6: Request Status Integration | DONE | 2026-03-07 |
| 3 | M4: HeartbeatMonitor | DONE | 2026-03-07 |
| 3 | M8: Retention Cleanup | DONE | 2026-03-07 |
| 4 | M11: Frontend Error UX | DONE | 2026-03-07 |
| 4 | M12: CI/CD Pipeline | DONE | 2026-03-07 |
| — | ~~M10: API Key Auth~~ | OUT OF SCOPE | Self-host, không cần |

---

*— Hết tài liệu —*
