# QA Unit Test Report — 2026-03-13

> Implementation report: Unit tests cho OCR/IDP Platform Backend.
> Session: Phase A + B + C implemented. Phase D = existing (API-level, cần backend running).

---

## Summary

| Metric | Value |
|---|---|
| Total test cases (unit + service + integration) | **176** |
| Passed | **176** |
| Failed | **0** |
| Skipped | **0** |
| API-level tests (Phase D, existing) | **51** (cần backend running) |
| Total all tests | **227** |

---

## Phase A — Core Logic (COMPLETED)

| Module | File | Tests | Pass | Fail | Skip | Status |
|---|---|---|---|---|---|---|
| M1: StateMachine | `test_state_machine.py` | 27 | 27 | 0 | 0 | EXISTING |
| M9: RateLimiter | `test_rate_limiter.py` | 9 | 9 | 0 | 0 | EXISTING |
| Core Exceptions | `test_exceptions.py` | 15 | 15 | 0 | 0 | **NEW** |
| Queue Messages | `test_queue_messages.py` | 10 | 10 | 0 | 0 | **NEW** |
| Storage Helpers | `test_storage_helpers.py` | 9 | 9 | 0 | 0 | **NEW** |
| **Phase A Total** | | **70** | **70** | **0** | **0** | |

### New Test IDs Implemented (Phase A):
- **EX-001 → EX-004**: NotFoundError, UnauthorizedError, ForbiddenError, AppException + ValidationError
- **QM-001 → QM-004**: JobMessage serialization, default retry_count, subject format, DLQ subject format + parse_subject
- **SH-001 → SH-003**: generate_object_key, generate_result_key, parse_object_key

---

## Phase B — Service Layer (COMPLETED)

| Module | File | Tests | Pass | Fail | Skip | Status |
|---|---|---|---|---|---|---|
| M2: JobService | `test_job_service.py` | 18 | 18 | 0 | 0 | EXISTING + **5 NEW** |
| M3: RetryOrchestrator | `test_retry_orchestrator.py` | 12 | 12 | 0 | 0 | EXISTING |
| M4: HeartbeatMonitor | `test_heartbeat_monitor.py` | 9 | 9 | 0 | 0 | EXISTING |
| M8: RetentionCleanup | `test_retention_cleanup.py` | 9 | 9 | 0 | 0 | EXISTING + **2 NEW** |
| M7: HealthService | `test_health_service.py` | 12 | 12 | 0 | 0 | EXISTING |
| Core Middleware | `test_middleware.py` | 7 | 7 | 0 | 0 | **NEW** |
| **Phase B Total** | | **67** | **67** | **0** | **0** | |

### New Test IDs Implemented (Phase B):
- **JS-009 → JS-011**: get_job_result (COMPLETED with result_path, non-completed, no result_path, not found)
- **JS-024**: FAILED + retriable triggers RetryOrchestrator
- **RC-007**: Jobs with result_path files moved during cleanup
- **RC-011**: Custom older_than_hours parameter
- **MW-001 → MW-004**: app_exception_handler (404, 401, 403, 400), unhandled_exception_handler (500)

---

## Phase C — Integration (COMPLETED)

| Module | File | Tests | Pass | Fail | Skip | Status |
|---|---|---|---|---|---|---|
| Repository Layer | `test_repositories.py` | 30 | 30 | 0 | 0 | **NEW** |
| M6: StatusIntegration | `test_request_status_integration.py` | 5 | 5 | 0 | 0 | EXISTING |
| AuditLog | `test_audit_log.py` | 11 | 11 | 0 | 0 | EXISTING |
| M5: Scheduler | `test_scheduler.py` | 5 | 5 | 0 | 0 | EXISTING |
| **Phase C Total** | | **51** (incl. scheduler) | **51** | **0** | **0** | |

### New Test IDs Implemented (Phase C):
- **RP-001 → RP-002**: UserRepository (create_user + get_by_email, nonexistent)
- **RP-003 → RP-004**: SessionRepository (create + get_valid, expired session)
- **RP-005 → RP-010**: RequestRepository (CRUD, pagination, expired, soft/hard delete, counters)
- **RP-011 → RP-017**: JobRepository (CRUD, get_by_request, status filter, queued filter, cancel, retry)
- **RP-018 → RP-020**: FileRepository (CRUD, soft_delete, include_deleted)
- **RP-021 → RP-022**: ServiceTypeRepository (get_approved, can_handle)
- **RP-023 → RP-024**: ServiceInstanceRepository (get_stale, mark_dead)
- **RP-025 → RP-026**: HeartbeatRepository (upsert + get_latest, cleanup_old)
- **RP-027**: AuditLogRepository (log_action)
- **RP-028**: BaseRepository (CRUD operations)

---

## Phase D — API-level (EXISTING, cần backend running)

| Module | File | Tests | Status |
|---|---|---|---|
| Auth API | `test_auth.py` | 14 | EXISTING — requires running backend |
| Upload API | `test_upload.py` | 12 | EXISTING — requires running backend |
| File Proxy API | `test_file_proxy.py` | 9 | EXISTING — requires running backend |
| Health API | `test_health.py` | 4 | EXISTING — requires running backend |
| NATS Integration | `test_health.py` (NATS tests) | 2 | EXISTING — requires running backend + NATS |
| **Phase D Total** | | **51** | NOT RUN (no backend) |

---

## Results by Module (All Phases)

| Module | File | Tests | Pass | Fail | Skip |
|---|---|---|---|---|---|
| M1: StateMachine | test_state_machine.py | 27 | 27 | 0 | 0 |
| M2: JobService | test_job_service.py | 18 | 18 | 0 | 0 |
| M3: RetryOrchestrator | test_retry_orchestrator.py | 12 | 12 | 0 | 0 |
| M4: HeartbeatMonitor | test_heartbeat_monitor.py | 9 | 9 | 0 | 0 |
| M5: Scheduler | test_scheduler.py | 5 | 5 | 0 | 0 |
| M6: StatusIntegration | test_request_status_integration.py | 5 | 5 | 0 | 0 |
| M7: HealthService | test_health_service.py | 12 | 12 | 0 | 0 |
| M8: RetentionCleanup | test_retention_cleanup.py | 9 | 9 | 0 | 0 |
| M9: RateLimiter | test_rate_limiter.py | 9 | 9 | 0 | 0 |
| Core Exceptions | test_exceptions.py | 15 | 15 | 0 | 0 |
| Queue Messages | test_queue_messages.py | 10 | 10 | 0 | 0 |
| Storage Helpers | test_storage_helpers.py | 9 | 9 | 0 | 0 |
| Middleware | test_middleware.py | 7 | 7 | 0 | 0 |
| Repository Layer | test_repositories.py | 30 | 30 | 0 | 0 |
| AuditLog | test_audit_log.py | 11 | 11 | 0 | 0 |
| **TOTAL (A+B+C)** | **15 files** | **188** | **188** | **0** | **0** |

---

## Failed Tests

Không có.

---

## Bugs Found

Không phát hiện bug trong production code. Tất cả test cases pass theo đúng expected behavior.

---

## New Files Created

| File | Type | Tests | Description |
|---|---|---|---|
| `test_exceptions.py` | Pure logic | 15 | AppException, NotFoundError, UnauthorizedError, ForbiddenError, ValidationError |
| `test_queue_messages.py` | Pure logic | 10 | JobMessage serialization, subject/DLQ format, parse_subject |
| `test_storage_helpers.py` | Pure logic | 9 | generate_object_key, generate_result_key, parse_object_key |
| `test_middleware.py` | Unit (mock) | 7 | app_exception_handler, unhandled_exception_handler |
| `test_repositories.py` | Integration (in-memory SQLite) | 30 | UserRepo, SessionRepo, RequestRepo, JobRepo, FileRepo, ServiceTypeRepo, ServiceInstanceRepo, HeartbeatRepo, AuditLogRepo, BaseRepo |

## Existing Files Modified

| File | Changes |
|---|---|
| `test_job_service.py` | +5 tests: JS-009 → JS-011 (get_job_result), JS-024 (retry orchestrator trigger) |
| `test_retention_cleanup.py` | +2 tests: RC-007 (result_path files), RC-011 (custom older_than_hours) |

---

## Gaps — Test Cases Chưa Cover

| Module | Missing Coverage | Reason |
|---|---|---|
| Phase D: Auth/Upload/FileProxy/Health | 51 API-level tests | Cần backend running — không thể chạy offline |
| `test_upload.py:test_file_size_limit` | Placeholder (pass) | Cần mock hoặc actual large file |

---

## Recommendations

1. **Chạy Phase D tests** khi backend running: `cd 00_test && python -m pytest backend/test_auth.py backend/test_upload.py backend/test_file_proxy.py backend/test_health.py -v`
2. **Thêm conditional skip** cho API tests khi server unavailable (dùng `@pytest.fixture(autouse=True)` with `httpx.get` health check)
3. **Coverage tracking**: `pytest backend/ -v --cov=../02_backend/app --cov-report=term-missing -k "not (TestAuth or TestUpload or TestFileProxy or TestHealth or TestNATS)"`
4. **CI integration**: Chạy Phases A+B+C trong CI pipeline (không cần services running)

---

*Report generated by QA Automation Engineer — 2026-03-13*
