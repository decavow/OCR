# Prompt: QA Automation — Unit Test Suite cho OCR/IDP Platform

> Nhiệm vụ: viết **unit tests** bằng Python/Pytest để verify toàn bộ business logic của hệ thống OCR/IDP. Tests đặt trong `00_test/backend/` (white-box, import code trực tiếp).

---

## 1. Mục Tiêu

Verify rằng mỗi module trong hệ thống hoạt động **đúng** theo tài liệu yêu cầu:
- Mỗi public method của service/module đều có test
- Cover **happy path → edge case → error case** (theo thứ tự)
- Đảm bảo **regression** — test phải FAIL nếu logic thay đổi sai

---

## 2. Ranh Giới & Phạm Vi

### Bạn CHỈ làm việc trong:
```
00_test/backend/          ← Unit tests (white-box)
```

### KHÔNG modify:
```
01_frontend/
02_backend/               ← Code production — không sửa
03_worker/
```

### Phân biệt với `05_test_cases/`:
- `00_test/backend/` = **white-box unit tests** (import code, mock dependencies) — domain của bạn
- `05_test_cases/` = **black-box E2E** (chỉ HTTP) — domain riêng, không chạm vào

---

## 3. Tài Liệu Tham Chiếu (ĐỌC TRƯỚC KHI VIẾT TEST)

| Tài liệu | Mục đích |
|---|---|
| `CLAUDE.md` | Coding conventions, module pattern, project rules |
| `04_docs/project-management/PROJECT_CONTEXT.md` | Architecture, DB schema, ADR log |
| `04_docs/project-management/DEVELOPMENT_WORKFLOW.md` | Module lifecycle, test conventions |
| `04_docs/07-roadmap/phase1-implementation-plan.md` | Module specs chi tiết (requirements) |
| `00_test/backend/conftest.py` | Existing fixtures — **reuse, không duplicate** |
| `00_test/backend/test_state_machine.py` | Tham khảo pattern unit test thuần (không mock) |
| `00_test/backend/test_job_service.py` | Tham khảo pattern service test (mock repos) |

---

## 4. Tech Stack & Import Pattern

### Dependencies:
```
pytest >= 7.0
pytest-asyncio >= 0.21
httpx (cho API-level tests)
```

### Import Pattern (BẮT BUỘC):
Dùng `importlib.util` để load module trực tiếp, tránh trigger full app import chain:

```python
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Load module cần test
def load_module(relative_path: str, module_name: str):
    """Load một module từ 02_backend/ mà không cần import cả app."""
    mod_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)

    # Mock các dependencies nếu cần
    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock()),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod
```

### Naming Convention:
```
test_{module}_{feature}.py          ← File name
class Test{Feature}:                ← Group by feature
    def test_{action}_{condition}:  ← Test name
```

### Mock Pattern:
```python
# Mock object dùng SimpleNamespace
from types import SimpleNamespace

def make_job(job_id="job-1", status="PROCESSING", retry_count=0):
    return SimpleNamespace(
        id=job_id, status=status, retry_count=retry_count,
        error_history="[]", method="ocr_text_raw", tier=0,
    )
```

---

## 5. Fixtures (dùng từ `conftest.py`)

| Fixture | Scope | Mô tả |
|---|---|---|
| `event_loop` | session | Async event loop |
| `client` | session | httpx.AsyncClient (base_url=localhost:8000) |
| `auth_headers` | function | Bearer token cho mỗi test |
| `sample_png` | function | Minimal valid PNG bytes |
| `sample_pdf` | function | Minimal valid PDF bytes |

---

## 6. Test Matrix — TẤT CẢ Modules

### 6.1. M1: JobStateMachine (`modules/job/state_machine.py`)
**File test:** `test_state_machine.py`
**Loại:** Pure logic, KHÔNG cần mock

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| SM-001 | `get_request_status` | Empty jobs list | happy | Return `"PROCESSING"` |
| SM-002 | `get_request_status` | All COMPLETED | happy | Return `"COMPLETED"` |
| SM-003 | `get_request_status` | All FAILED | happy | Return `"FAILED"` |
| SM-004 | `get_request_status` | All DEAD_LETTER | happy | Return `"FAILED"` |
| SM-005 | `get_request_status` | All CANCELLED | happy | Return `"CANCELLED"` |
| SM-006 | `get_request_status` | Mixed FAILED + DEAD_LETTER | edge | Return `"FAILED"` |
| SM-007 | `get_request_status` | COMPLETED + FAILED | edge | Return `"PARTIAL_SUCCESS"` |
| SM-008 | `get_request_status` | COMPLETED + CANCELLED | edge | Return `"PARTIAL_SUCCESS"` |
| SM-009 | `get_request_status` | COMPLETED + DEAD_LETTER | edge | Return `"PARTIAL_SUCCESS"` |
| SM-010 | `get_request_status` | FAILED + CANCELLED | edge | Return `"PARTIAL_SUCCESS"` |
| SM-011 | `get_request_status` | All terminal mixed | edge | Return `"PARTIAL_SUCCESS"` |
| SM-012 | `get_request_status` | Any PROCESSING in mix | edge | Return `"PROCESSING"` |
| SM-013 | `get_request_status` | Any QUEUED in mix | edge | Return `"PROCESSING"` |
| SM-014 | `get_request_status` | Any SUBMITTED in mix | edge | Return `"PROCESSING"` |
| SM-015 | `get_request_status` | Any VALIDATING in mix | edge | Return `"PROCESSING"` |
| SM-016 | `get_request_status` | Single COMPLETED | edge | Return `"COMPLETED"` |
| SM-017 | `validate_transition` | SUBMITTED → VALIDATING | happy | Return `True` |
| SM-018 | `validate_transition` | PROCESSING → COMPLETED | happy | Return `True` |
| SM-019 | `validate_transition` | FAILED → QUEUED (retry) | happy | Return `True` |
| SM-020 | `validate_transition` | COMPLETED → PROCESSING | error | Return `False` |
| SM-021 | `validate_transition` | CANCELLED → QUEUED | error | Return `False` |
| SM-022 | `validate_transition` | Unknown status | error | Return `False` |
| SM-023 | `is_terminal` | COMPLETED | happy | Return `True` |
| SM-024 | `is_terminal` | FAILED | edge | Return `False` (can retry) |
| SM-025 | `is_terminal` | DEAD_LETTER | happy | Return `True` |
| SM-026 | `is_terminal` | CANCELLED | happy | Return `True` |
| SM-027 | `is_terminal` | PROCESSING | happy | Return `False` |

---

### 6.2. M2: JobService (`modules/job/service.py`)
**File test:** `test_job_service.py`
**Loại:** Service test, mock repositories

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| JS-001 | `get_request` | Request found, correct owner | happy | Return request object |
| JS-002 | `get_request` | Request found, wrong owner | error | Return `None` |
| JS-003 | `get_request` | Request not found | error | Return `None` |
| JS-004 | `get_request_with_jobs` | Found request + 2 jobs | happy | Return (request, [job, job]) |
| JS-005 | `get_request_with_jobs` | Wrong owner | error | Return `None` |
| JS-006 | `get_job` | Job found, owner verified | happy | Return job object |
| JS-007 | `get_job` | Job found, wrong owner | error | Return `None` |
| JS-008 | `get_job` | Job not found | error | Return `None` |
| JS-009 | `get_job_result` | Job COMPLETED with result_path | happy | Return (job, bytes) |
| JS-010 | `get_job_result` | Job not COMPLETED | error | Return `None` hoặc raise |
| JS-011 | `get_job_result` | No result_path | error | Return `None` hoặc raise |
| JS-012 | `cancel_request` | Request with QUEUED jobs | happy | Return `{success: True, cancelled_jobs: N}` |
| JS-013 | `cancel_request` | Request not found | error | Return `{success: False}` |
| JS-014 | `cancel_request` | Request wrong owner | error | Return `{success: False}` |
| JS-015 | `cancel_request` | No QUEUED jobs | edge | Return `{success: True, cancelled_jobs: 0}` |
| JS-016 | `cancel_job` | QUEUED job | happy | Return `{success: True, cancelled: True}` |
| JS-017 | `cancel_job` | PROCESSING job (not QUEUED) | error | Return `{success: False}` |
| JS-018 | `cancel_job` | COMPLETED job (terminal) | error | Return `{success: False}` |
| JS-019 | `update_job_status` | PROCESSING → COMPLETED | happy | Return updated job, increment completed_files |
| JS-020 | `update_job_status` | PROCESSING → FAILED | happy | Return updated job, increment failed_files |
| JS-021 | `update_job_status` | Invalid transition (COMPLETED → PROCESSING) | error | Return `None` |
| JS-022 | `update_job_status` | Job not found | error | Return `None` |
| JS-023 | `update_job_status` | COMPLETED triggers request status recalc | happy | `update_status` called on request |
| JS-024 | `update_job_status` | FAILED + retriable triggers RetryOrchestrator | happy | `handle_failure` called |
| JS-025 | `_recalculate_request_status` | All jobs COMPLETED → request COMPLETED | happy | Request status = COMPLETED |
| JS-026 | `_recalculate_request_status` | Mixed → PARTIAL_SUCCESS | edge | Request status = PARTIAL_SUCCESS |

---

### 6.3. M3: RetryOrchestrator (`modules/job/orchestrator.py`)
**File test:** `test_retry_orchestrator.py`
**Loại:** Service test, mock queue + repos

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| RO-001 | `decide_retry_or_dlq` | retry_count < max, retriable | happy | Return `"retry"` |
| RO-002 | `decide_retry_or_dlq` | retry_count = max | edge | Return `"dlq"` |
| RO-003 | `decide_retry_or_dlq` | retry_count > max | edge | Return `"dlq"` |
| RO-004 | `decide_retry_or_dlq` | Non-retriable error | error | Return `"dlq"` |
| RO-005 | `decide_retry_or_dlq` | Last error_history non-retriable | edge | Return `"dlq"` |
| RO-006 | `handle_failure` | Retriable + under limit | happy | Calls `requeue_job` |
| RO-007 | `handle_failure` | Non-retriable | happy | Calls `move_to_dlq` |
| RO-008 | `handle_failure` | Max retries exceeded | edge | Calls `move_to_dlq` |
| RO-009 | `requeue_job` | Normal | happy | increment_retry + status QUEUED + publish to NATS |
| RO-010 | `requeue_job` | Queue is None | edge | No error, status updated only |
| RO-011 | `requeue_job` | Verify NATS subject = `ocr.{method}.tier{tier}` | happy | Correct subject format |
| RO-012 | `move_to_dlq` | Normal | happy | status DEAD_LETTER + publish to DLQ subject |
| RO-013 | `move_to_dlq` | Verify DLQ subject = `dlq.{method}.tier{tier}` | happy | Correct DLQ subject |
| RO-014 | `move_to_dlq` | Verify message contains job info | happy | job_id, request_id, retry_count in message |
| RO-015 | `_build_message` | Build from job + file | happy | JobMessage fields correct |

---

### 6.4. M4: HeartbeatMonitor (`modules/job/heartbeat_monitor.py`)
**File test:** `test_heartbeat_monitor.py`
**Loại:** Service test, mock repos + orchestrator

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| HB-001 | `check_workers` | 2 stale workers found | happy | Return `["w1", "w2"]`, mark_dead called 2x |
| HB-002 | `check_workers` | No stale workers | happy | Return `[]` |
| HB-003 | `detect_stalled` | Dead worker with 2 PROCESSING jobs | happy | Return 2 jobs |
| HB-004 | `detect_stalled` | No dead workers | happy | Return `[]` |
| HB-005 | `detect_stalled` | Dead worker but no PROCESSING jobs | edge | Return `[]` |
| HB-006 | `recover_stalled_jobs` | 2 jobs recovered via orchestrator | happy | `handle_failure` called 2x with `retriable=True` |
| HB-007 | `recover_stalled_jobs` | No orchestrator | edge | No error raised |
| HB-008 | `recover_stalled_jobs` | One job recovery fails | edge | Continue processing others, no crash |
| HB-009 | `run_check` | Full cycle with stalled jobs | happy | `{stalled_recovered: N, heartbeats_cleaned: M}` |
| HB-010 | `run_check` | No issues | happy | `{stalled_recovered: 0, heartbeats_cleaned: 0}` |

---

### 6.5. M5: Scheduler (`core/scheduler.py`)
**File test:** `test_scheduler.py`
**Loại:** Integration light, verify init/shutdown

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| SC-001 | `init_scheduler` | Start scheduler | happy | Scheduler running |
| SC-002 | `shutdown_scheduler` | Stop scheduler | happy | Scheduler stopped |
| SC-003 | `init_scheduler` | Double init | edge | No error (idempotent) |
| SC-004 | periodic tasks | Heartbeat registered at 60s | happy | Job exists in scheduler |
| SC-005 | periodic tasks | Cleanup registered at 1h | happy | Job exists in scheduler |
| SC-006 | periodic tasks | Purge registered at 24h | happy | Job exists in scheduler |

---

### 6.6. M7: HealthService (`modules/health/service.py`)
**File test:** `test_health_service.py`
**Loại:** Service test, mock DB/NATS/MinIO

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| HS-001 | `check_database` | DB healthy | happy | `{status: "healthy", latency_ms: N}` |
| HS-002 | `check_database` | DB connection error | error | `{status: "unhealthy", error: "..."}` |
| HS-003 | `check_nats` | NATS connected | happy | `{status: "healthy"}` |
| HS-004 | `check_nats` | NATS disconnected | error | `{status: "unhealthy"}` |
| HS-005 | `check_minio` | MinIO healthy | happy | `{status: "healthy"}` |
| HS-006 | `check_minio` | MinIO connection error | error | `{status: "unhealthy"}` |
| HS-007 | `check_all` | All healthy | happy | `{status: "healthy", services: {...}}` |
| HS-008 | `check_all` | One unhealthy | edge | `{status: "degraded"}` |
| HS-009 | `check_all` | All unhealthy | error | `{status: "unhealthy"}` |

---

### 6.7. M8: RetentionCleanupService (`modules/cleanup/service.py`)
**File test:** `test_retention_cleanup.py`
**Loại:** Service test, mock storage + repos

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| RC-001 | `cleanup_expired` | No expired requests | happy | `{expired_requests: 0, files_moved: 0}` |
| RC-002 | `cleanup_expired` | 1 expired request with 1 file | happy | `{expired_requests: 1, files_moved: 1}` |
| RC-003 | `cleanup_expired` | 1 expired request with 2 files | edge | `{files_moved: 2}` |
| RC-004 | `cleanup_expired` | 3 expired requests | edge | `{expired_requests: 3}` |
| RC-005 | `cleanup_expired` | Storage present → files moved | happy | `copy_object` + `remove_object` called |
| RC-006 | `cleanup_expired` | Storage None → only DB soft-delete | edge | No storage error, soft_delete called |
| RC-007 | `cleanup_expired` | Jobs with result_path also moved | happy | Result files moved too |
| RC-008 | `purge_deleted` | No soft-deleted records | happy | `{purged_requests: 0}` |
| RC-009 | `purge_deleted` | 1 soft-deleted request | happy | `hard_delete` called once |
| RC-010 | `purge_deleted` | Request with files → storage removed | happy | `remove_object` called per file |
| RC-011 | `purge_deleted` | Custom `older_than_hours` param | edge | Correct cutoff passed to repo |

---

### 6.8. M9: RateLimiter (`core/rate_limiter.py`)
**File test:** `test_rate_limiter.py`
**Loại:** Pure logic + config verification

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| RL-001 | `TokenBucket.consume` | Within limit (5/60) | happy | `allowed=True`, remaining decreases |
| RL-002 | `TokenBucket.consume` | Over limit | error | `allowed=False`, `remaining=0` |
| RL-003 | `TokenBucket.consume` | Remaining count tracks correctly | happy | Each consume decreases by 1 |
| RL-004 | `RateLimiter.check` | Different keys independent | happy | Key A exhausted, Key B still allowed |
| RL-005 | config | `/upload` limit = 10 req/min | happy | Assert from `RATE_LIMITS` |
| RL-006 | config | `/auth/login` limit = 5 req/min | happy | Assert `(5, 60)` |
| RL-007 | config | `/auth/register` limit = 3 req/min | happy | Assert `(3, 60)` |
| RL-008 | config | Default limit = 60 req/min | happy | Assert `DEFAULT_RATE_LIMIT` |
| RL-009 | config | Internal endpoints excluded | happy | `/api/v1/internal/` in `EXCLUDED_PREFIXES` |
| RL-010 | config | Health endpoint excluded | happy | `/health` in `EXCLUDED_PREFIXES` |

---

### 6.9. Auth Service (`modules/auth/service.py`)
**File test:** `test_auth.py`
**Loại:** API-level test (cần backend running) HOẶC service-level unit test

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| AU-001 | `POST /auth/register` | Valid email + password | happy | 200, token + user returned |
| AU-002 | `POST /auth/register` | Duplicate email | error | 400 |
| AU-003 | `POST /auth/register` | Invalid email format | error | 422 |
| AU-004 | `POST /auth/register` | Missing password | error | 422 |
| AU-005 | `POST /auth/login` | Valid credentials | happy | 200, token returned |
| AU-006 | `POST /auth/login` | Wrong password | error | 401 |
| AU-007 | `POST /auth/login` | Non-existent user | error | 401 |
| AU-008 | `POST /auth/logout` | Valid token | happy | 200, session invalidated |
| AU-009 | `POST /auth/logout` | Token invalidated after logout | happy | Subsequent /me returns 401 |
| AU-010 | `POST /auth/logout` | No token | edge | 200 (graceful) |
| AU-011 | `GET /auth/me` | Valid token | happy | 200, user info |
| AU-012 | `GET /auth/me` | No token | error | 401 |
| AU-013 | `GET /auth/me` | Invalid token | error | 401 |
| AU-014 | `GET /auth/me` | Malformed header | error | 401 |

---

### 6.10. Upload Service (`modules/upload/service.py`)
**File test:** `test_upload.py`
**Loại:** API-level test (cần backend running)

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| UP-001 | `POST /upload` | Single valid PNG | happy | 200, request_id + 1 file |
| UP-002 | `POST /upload` | Multiple files (3 PNGs) | happy | 200, total_files=3 |
| UP-003 | `POST /upload` | With output_format=json | happy | 200, output_format="json" |
| UP-004 | `POST /upload` | With method + tier | happy | 200, correct method/tier |
| UP-005 | `POST /upload` | PDF file | happy | 200, mime=application/pdf |
| UP-006 | `POST /upload` | No auth | error | 401 |
| UP-007 | `POST /upload` | Invalid file type (exe) | error | 400 |
| UP-008 | `POST /upload` | Empty file | error | 400 |
| UP-009 | `POST /upload` | Batch > 20 files | error | 400 |
| UP-010 | `POST /upload` | Response structure complete | happy | All required fields present |
| UP-011 | `POST /upload` | Magic bytes validation | edge | Detects actual type from content |

---

### 6.11. File Proxy Service (`modules/file_proxy/service.py`)
**File test:** `test_file_proxy.py`
**Loại:** Service test, mock storage + repos

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| FP-001 | `download_for_worker` | Valid access_key + job_id + file_id | happy | Return (bytes, content_type, filename) |
| FP-002 | `download_for_worker` | Invalid access_key | error | Raise UnauthorizedError |
| FP-003 | `download_for_worker` | Job-file ACL mismatch | error | Raise ForbiddenError |
| FP-004 | `upload_from_worker` | Valid upload | happy | Return result_key, job.result_path updated |
| FP-005 | `upload_from_worker` | Invalid access_key | error | Raise UnauthorizedError |
| FP-006 | `upload_from_worker` | ACL mismatch | error | Raise ForbiddenError |

---

### 6.12. Repository Layer (`infrastructure/database/repositories/`)
**File test:** `test_repositories.py` (MỚI)
**Loại:** Integration test với in-memory SQLite

| Test ID | Repository | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| RP-001 | `UserRepository` | create_user + get_by_email | happy | User created, findable by email |
| RP-002 | `UserRepository` | get_by_email không tồn tại | edge | Return `None` |
| RP-003 | `SessionRepository` | create_session + get_valid | happy | Session found with valid token |
| RP-004 | `SessionRepository` | get_valid với expired session | edge | Return `None` |
| RP-005 | `RequestRepository` | create_request + get_active | happy | Request created and findable |
| RP-006 | `RequestRepository` | get_by_user với pagination | happy | Correct slice returned |
| RP-007 | `RequestRepository` | get_expired finds only expired | edge | Only expired requests returned |
| RP-008 | `RequestRepository` | soft_delete + get_soft_deleted_before | happy | Soft-deleted found by cutoff |
| RP-009 | `RequestRepository` | hard_delete removes from DB | happy | Not findable after hard_delete |
| RP-010 | `RequestRepository` | increment_completed / increment_failed | happy | Counters update correctly |
| RP-011 | `JobRepository` | create_job + get_active | happy | Job created and findable |
| RP-012 | `JobRepository` | get_by_request returns all jobs | happy | Correct count |
| RP-013 | `JobRepository` | get_by_status filters correctly | edge | Only matching status |
| RP-014 | `JobRepository` | get_queued_by_request | happy | Only QUEUED jobs |
| RP-015 | `JobRepository` | update_status changes status | happy | Status updated |
| RP-016 | `JobRepository` | cancel_jobs returns cancelled count | happy | Count matches |
| RP-017 | `JobRepository` | increment_retry updates retry_count | happy | retry_count += 1 |
| RP-018 | `FileRepository` | create_file + get_active | happy | File created and findable |
| RP-019 | `FileRepository` | soft_delete makes get_active return None | happy | Not found after soft_delete |
| RP-020 | `FileRepository` | get_by_request_include_deleted | edge | Returns even deleted files |
| RP-021 | `ServiceTypeRepository` | get_approved filters by status | happy | Only APPROVED returned |
| RP-022 | `ServiceTypeRepository` | can_handle checks method + tier | happy | True/False based on config |
| RP-023 | `ServiceInstanceRepository` | get_stale_instances by timeout | happy | Returns stale instances |
| RP-024 | `ServiceInstanceRepository` | mark_dead changes status | happy | Status = DEAD |
| RP-025 | `HeartbeatRepository` | create_heartbeat + get_latest | happy | Latest heartbeat returned |
| RP-026 | `HeartbeatRepository` | cleanup_old removes old records | happy | Returns count deleted |
| RP-027 | `AuditLogRepository` | log_action creates entry | happy | Entry created with all fields |
| RP-028 | `BaseRepository` | get, get_all, create, update, delete | happy | CRUD operations work |

---

### 6.13. Infrastructure — Queue (`infrastructure/queue/`)
**File test:** `test_queue_messages.py` (MỚI)
**Loại:** Pure logic test

| Test ID | Component | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| QM-001 | `JobMessage` | to_dict() serialization | happy | All fields present |
| QM-002 | `JobMessage` | Default retry_count = 0 | happy | `retry_count=0` |
| QM-003 | `subjects` | Subject format `ocr.{method}.tier{tier}` | happy | Correct format |
| QM-004 | `subjects` | DLQ subject format `dlq.{method}.tier{tier}` | happy | Correct format |

---

### 6.14. Infrastructure — Storage (`infrastructure/storage/`)
**File test:** `test_storage_helpers.py` (MỚI)
**Loại:** Pure logic test (helpers only, không test MinIO connection)

| Test ID | Component | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| SH-001 | `generate_object_key` | Standard path | happy | `{user_id}/{request_id}/{file_id}/{filename}` |
| SH-002 | `generate_result_key` | Standard path | happy | Correct result path format |
| SH-003 | `ObjectInfo` | Dataclass fields | happy | All fields accessible |

---

### 6.15. Core — Middleware (`core/middleware.py`)
**File test:** `test_middleware.py` (MỚI)
**Loại:** Unit test, mock request/response

| Test ID | Component | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| MW-001 | `RequestLoggingMiddleware` | Normal request logged | happy | Log contains method, path, status |
| MW-002 | `app_exception_handler` | AppException → correct status code | happy | Status matches exception |
| MW-003 | `app_exception_handler` | NotFoundError → 404 | happy | 404 response |
| MW-004 | `unhandled_exception_handler` | Unknown exception → 500 | error | 500 response |

---

### 6.16. Core — Exceptions (`core/exceptions.py`)
**File test:** `test_exceptions.py` (MỚI)
**Loại:** Pure logic test

| Test ID | Component | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| EX-001 | `NotFoundError` | status_code = 404 | happy | Assert attribute |
| EX-002 | `UnauthorizedError` | status_code = 401 | happy | Assert attribute |
| EX-003 | `ForbiddenError` | status_code = 403 | happy | Assert attribute |
| EX-004 | `AppException` | Message preserved | happy | `str(exc)` contains message |

---

### 6.17. Request Status Integration (`modules/job/` cross-module)
**File test:** `test_request_status_integration.py`
**Loại:** Integration test

| Test ID | Scenario | Loại | Kỳ vọng |
|---|---|---|---|
| RI-001 | Create request + 3 jobs, complete all → COMPLETED | happy | Request status = COMPLETED |
| RI-002 | Complete 2/3, fail 1 → PARTIAL_SUCCESS | edge | Request status = PARTIAL_SUCCESS |
| RI-003 | Fail all jobs → FAILED | happy | Request status = FAILED |
| RI-004 | Cancel all QUEUED → CANCELLED | happy | Request status = CANCELLED |
| RI-005 | Complete 1, cancel 2 → PARTIAL_SUCCESS | edge | Request status = PARTIAL_SUCCESS |

---

### 6.18. Audit Log (`infrastructure/database/repositories/audit_log.py`)
**File test:** `test_audit_log.py`
**Loại:** Integration test

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| AL-001 | `log_action` | Create audit entry | happy | Entry persisted with all fields |
| AL-002 | `log_action` | Details as dict | happy | JSON serializable |
| AL-003 | `log_action` | Null details | edge | Entry created without details |

---

## 7. Thứ Tự Thực Hiện (Priority)

> **LƯU Ý QUAN TRỌNG — Xuất báo cáo sau MỖI phase:**
> Sau khi hoàn thành mỗi phase (A, B, C, D), **BẮT BUỘC** xuất báo cáo trung gian ngay lập tức theo format ở mục 10.
> Lý do: Context window có giới hạn — nếu tràn token giữa chừng, toàn bộ kết quả các phase trước sẽ bị mất.
> Báo cáo trung gian phải ghi vào file `05_test_cases/backend/QA_UNIT_TEST_REPORT_BACKEND_YYYY-MM-DD.md` (append mỗi phase).
> Nếu session bị ngắt, session mới đọc file report này để biết phase nào đã xong và tiếp tục từ phase tiếp theo.

### Phase A — Core Logic (không cần external deps, chạy nhanh)
1. `test_state_machine.py` — Pure logic, nền tảng cho mọi module khác
2. `test_rate_limiter.py` — Pure logic
3. `test_exceptions.py` — Pure logic (MỚI)
4. `test_queue_messages.py` — Pure logic (MỚI)
5. `test_storage_helpers.py` — Pure logic (MỚI)

### Phase B — Service Layer (mock repos, verify business logic)
6. `test_job_service.py` — Core orchestration
7. `test_retry_orchestrator.py` — Retry + DLQ
8. `test_heartbeat_monitor.py` — Worker monitoring
9. `test_retention_cleanup.py` — File cleanup
10. `test_health_service.py` — Health checks
11. `test_file_proxy.py` — File proxy

### Phase C — Integration (cần DB hoặc running services)
12. `test_repositories.py` — Repository CRUD (MỚI, in-memory SQLite)
13. `test_request_status_integration.py` — Cross-module integration
14. `test_audit_log.py` — Audit trail

### Phase D — API-level (cần backend running)
15. `test_auth.py` — Auth endpoints
16. `test_upload.py` — Upload endpoint
17. `test_health.py` — Health endpoint

---

## 8. Quy Trình Chạy Test

### Chạy toàn bộ unit tests:
```bash
cd 00_test && python -m pytest backend/ -v --tb=short
```

### Chạy theo module:
```bash
python -m pytest backend/test_state_machine.py -v
python -m pytest backend/test_job_service.py -v
python -m pytest backend/test_retry_orchestrator.py -v
```

### Chạy theo loại (chỉ pure logic, không cần services):
```bash
python -m pytest backend/test_state_machine.py backend/test_rate_limiter.py backend/test_exceptions.py -v
```

### Chạy với coverage:
```bash
python -m pytest backend/ -v --cov=../02_backend/app --cov-report=term-missing
```

### Chạy tests theo marker:
```bash
# Chỉ async tests
python -m pytest backend/ -v -m asyncio

# Chỉ tests không cần services running
python -m pytest backend/ -v -k "not (auth or upload or health)"
```

---

## 9. Quy Tắc BẮT BUỘC

1. **KHÔNG sửa code production** — nếu test fail vì bug, report bug (ghi test ID, expected vs actual, file + line)
2. **Mỗi test function = 1 scenario** — không gom nhiều assertions không liên quan
3. **Sắp xếp:** Happy → Edge → Error trong mỗi class
4. **Mock đúng layer:** Service test mock repos, KHÔNG mock service logic
5. **Assert cụ thể:** Kiểm tra giá trị cụ thể, không chỉ `assert result is not None`
6. **Không depend thứ tự** giữa test functions — mỗi test độc lập
7. **Không assert giá trị không ổn định** (timestamp, UUID) — assert format/existence
8. **Khi phát hiện test case thiếu** từ Test Matrix → thêm ngay, đánh ID tiếp nối
9. **Test file mới** phải follow import pattern ở mục 4
10. **Cleanup sau test** — nếu tạo data, phải cleanup (dùng fixture teardown)

---

## 10. Report Format

Sau khi chạy xong, report theo format:

```markdown
# QA Unit Test Report — YYYY-MM-DD

## Summary
| Metric | Value |
|---|---|
| Total test cases | N |
| Passed | N |
| Failed | N |
| Skipped | N |
| Coverage | X% |

## Results by Module
| Module | File | Tests | Pass | Fail | Skip |
|---|---|---|---|---|---|
| M1: StateMachine | test_state_machine.py | 27 | 27 | 0 | 0 |
| ... | ... | ... | ... | ... | ... |

## Failed Tests (nếu có)
| Test ID | File:Line | Expected | Actual | Root Cause |
|---|---|---|---|---|
| JS-024 | test_job_service.py:180 | handle_failure called | Not called | Bug: missing delegation |

## Bugs Found
| Bug ID | Severity | Module | Description | Steps to Reproduce |
|---|---|---|---|---|
| BUG-001 | HIGH | JobService | ... | ... |

## Gaps — Test Cases Chưa Cover
| Module | Missing Coverage | Reason |
|---|---|---|
| ... | ... | ... |

## Recommendations
- ...
```

---

## 11. Checklist Trước Khi Submit

- [ ] Tất cả test cases từ Test Matrix (mục 6) đã được implement
- [ ] Tất cả tests pass (hoặc xfail với reason)
- [ ] Không có test depend vào external services (NATS, MinIO) trừ khi marked
- [ ] Import pattern đúng (importlib, không import app trực tiếp)
- [ ] Mỗi test file có docstring mô tả module + coverage
- [ ] Report đã được viết theo format mục 10
- [ ] File tracking đã được cập nhật (`04_docs/06-OCR_update_progress/`)
