# QA Unit Test Report — 2026-03-12

> Báo cáo đánh giá mức độ coverage unit test cho toàn bộ backend OCR/IDP Platform (Phase 1).

---

## 1. Summary

| Metric | Value |
|---|---|
| Tổng test cases đã có (existing) | **149** tests |
| Tổng test cases theo Test Matrix (planned) | **196** tests |
| Test files đã có | **14** files |
| Test files cần thêm (NEW) | **4** files |
| Coverage hiện tại (existing/planned) | **76%** |
| Test cases cần bổ sung | **47** tests |

---

## 2. Hiện Trạng — Tests Đã Có

### 2.1 Existing Test Files & Count

| # | Module | File | Tests | Status |
|---|---|---|---|---|
| 1 | M1: StateMachine | `test_state_machine.py` | 27 | FULL COVERAGE |
| 2 | M2: JobService | `test_job_service.py` | 13 | PARTIAL (50%) |
| 3 | M3: RetryOrchestrator | `test_retry_orchestrator.py` | 12 | PARTIAL (80%) |
| 4 | M4: HeartbeatMonitor | `test_heartbeat_monitor.py` | 9 | PARTIAL (90%) |
| 5 | M5: Scheduler | `test_scheduler.py` | 5 | PARTIAL (83%) |
| 6 | M7: HealthService | `test_health_service.py` | 12 | FULL COVERAGE |
| 7 | M8: RetentionCleanup | `test_retention_cleanup.py` | 7 | PARTIAL (64%) |
| 8 | M9: RateLimiter | `test_rate_limiter.py` | 9 | PARTIAL (90%) |
| 9 | Auth | `test_auth.py` | 14 | FULL COVERAGE |
| 10 | Upload | `test_upload.py` | 12 | FULL COVERAGE |
| 11 | FileProxy | `test_file_proxy.py` | 9 | FULL COVERAGE |
| 12 | StatusIntegration | `test_request_status_integration.py` | 5 | FULL COVERAGE |
| 13 | AuditLog | `test_audit_log.py` | 11 | FULL COVERAGE |
| 14 | Health API | `test_health.py` | 4 | FULL COVERAGE |
| | **TỔNG** | **14 files** | **149** | **76%** |

### 2.2 Test Types Distribution

| Type | Count | % |
|---|---|---|
| Pure logic (no mock) | 36 | 24% |
| Service test (mock repos) | 64 | 43% |
| API-level (cần backend running) | 39 | 26% |
| Integration (in-memory DB) | 10 | 7% |

---

## 3. Gap Analysis — Cần Bổ Sung

### 3.1 Files MỚI cần tạo (4 files, 39 tests)

| File | Module | Tests Needed | Priority |
|---|---|---|---|
| `test_repositories.py` | Repository Layer | **28** | HIGH |
| `test_queue_messages.py` | NATS Messages/Subjects | **4** | MEDIUM |
| `test_storage_helpers.py` | Storage Helpers | **3** | MEDIUM |
| `test_exceptions.py` | Core Exceptions | **4** | LOW |

### 3.2 Files CẦN BỔ SUNG test cases (5 files, 8 tests)

| File | Module | Existing | Planned | Gap | Missing Test IDs |
|---|---|---|---|---|---|
| `test_job_service.py` | M2: JobService | 13 | 26 | **13** | JS-009→011 (get_job_result), JS-014 (wrong owner cancel_request), JS-015 (no queued cancel), JS-018 (cancel completed job), JS-024 (failed+retriable triggers retry), JS-025/026 (recalculate) |
| `test_retention_cleanup.py` | M8: Cleanup | 7 | 11 | **4** | RC-005 (storage copy verify), RC-006 (storage None edge), RC-007 (result_path files), RC-011 (custom older_than) |
| `test_retry_orchestrator.py` | M3: Retry | 12 | 15 | **3** | RO-011 (subject format verify), RO-013 (DLQ subject format), RO-015 (_build_message) |
| `test_heartbeat_monitor.py` | M4: Heartbeat | 9 | 10 | **1** | HB-005 (dead worker, no PROCESSING jobs) |
| `test_scheduler.py` | M5: Scheduler | 5 | 6 | **1** | SC-003 (double init idempotent) |

### 3.3 Chi Tiết — Repository Tests (`test_repositories.py` — MỚI, 28 tests)

Đây là **gap lớn nhất**. Repository layer hiện tại KHÔNG có unit test riêng. Tất cả repository logic chỉ được test gián tiếp qua service tests (mock repos).

| Repository | Tests Needed | Critical Methods |
|---|---|---|
| `BaseRepository` | 4 | get, get_all, create, update, delete |
| `UserRepository` | 2 | create_user, get_by_email |
| `SessionRepository` | 2 | create_session, get_valid (expired check) |
| `RequestRepository` | 6 | create_request, get_active, get_by_user, get_expired, soft/hard_delete, increment counters |
| `JobRepository` | 5 | create_job, get_by_request, get_by_status, cancel_jobs, increment_retry |
| `FileRepository` | 3 | create_file, soft_delete, get_by_request_include_deleted |
| `ServiceTypeRepository` | 2 | get_approved, can_handle |
| `ServiceInstanceRepository` | 2 | get_stale_instances, mark_dead |
| `HeartbeatRepository` | 2 | create_heartbeat + get_latest, cleanup_old |

**Approach:** Dùng in-memory SQLite (giống pattern `test_audit_log.py`) — tạo DB thật, test CRUD trực tiếp.

---

## 4. Coverage By Module

| Module | Planned Tests | Existing Tests | Coverage | Status |
|---|---|---|---|---|
| M1: StateMachine | 27 | 27 | **100%** | DONE |
| M2: JobService | 26 | 13 | **50%** | PARTIAL |
| M3: RetryOrchestrator | 15 | 12 | **80%** | PARTIAL |
| M4: HeartbeatMonitor | 10 | 9 | **90%** | PARTIAL |
| M5: Scheduler | 6 | 5 | **83%** | PARTIAL |
| M6: StatusIntegration | 5 | 5 | **100%** | DONE |
| M7: HealthService | 9 | 12 | **100%** | DONE |
| M8: RetentionCleanup | 11 | 7 | **64%** | PARTIAL |
| M9: RateLimiter | 10 | 9 | **90%** | PARTIAL |
| Auth Service | 14 | 14 | **100%** | DONE |
| Upload Service | 11 | 12 | **100%** | DONE |
| File Proxy | 6 | 9 | **100%** | DONE |
| AuditLog | 3 | 11 | **100%** | DONE |
| Repository Layer | 28 | 0 | **0%** | NOT STARTED |
| Queue Messages | 4 | 0 | **0%** | NOT STARTED |
| Storage Helpers | 3 | 0 | **0%** | NOT STARTED |
| Core Exceptions | 4 | 0 | **0%** | NOT STARTED |
| Middleware | 4 | 0 | **0%** | NOT STARTED |
| **TOTAL** | **196** | **149** | **76%** | |

---

## 5. Đánh Giá Chất Lượng Tests Hiện Có

### 5.1 Điểm Mạnh

| Aspect | Assessment |
|---|---|
| **Import pattern** | Consistent — dùng `importlib.util` tránh full app import. Tất cả files follow cùng pattern |
| **Mock strategy** | Đúng layer — service tests mock repos (không mock service logic) |
| **Test naming** | Rõ ràng — `test_{action}_{condition}` |
| **Test isolation** | Mỗi test độc lập, không depend thứ tự |
| **Fixture reuse** | `conftest.py` shared fixtures (client, auth, sample files) |
| **Edge cases** | Có cover: empty lists, None values, wrong owner |
| **Error paths** | Có cover: not found, unauthorized, invalid transitions |

### 5.2 Điểm Yếu / Rủi Ro

| Issue | Severity | Details |
|---|---|---|
| **Repository layer = 0% coverage** | HIGH | Tất cả data access logic chỉ test gián tiếp qua mock. Nếu repository có bug (wrong query, missing filter), service tests vẫn PASS |
| **`test_upload.py:test_file_size_limit` = pass** | MEDIUM | Test case placeholder, không thực sự chạy assertion. Line 184: `pass  # Skip for now` |
| **API tests cần backend running** | MEDIUM | `test_auth.py`, `test_upload.py`, `test_file_proxy.py`, `test_health.py` fail nếu server không chạy. Cần marker riêng hoặc skip điều kiện |
| **Missing coverage: `get_job_result`** | HIGH | `JobService.get_job_result()` chưa có test nào. Đây là method quan trọng (user download OCR result) |
| **Missing coverage: Middleware** | MEDIUM | Request logging, error handling, CORS — chưa test |
| **Không có test cho worker** | LOW | Worker tests nằm ở `00_test/ocr_worker/` — ngoài scope backend tests nhưng cần lưu ý |

### 5.3 Test Pattern Quality Score

| Criteria | Score (1-5) | Notes |
|---|---|---|
| Consistency | 5/5 | Tất cả files follow cùng pattern |
| Readability | 4/5 | Class grouping + clear names. Có thể thêm docstring cho edge cases |
| Completeness | 3/5 | 76% coverage, thiếu repository layer |
| Maintainability | 4/5 | Module-based organization, easy to extend |
| Reliability | 4/5 | Tests deterministic, không depend external state (trừ API tests) |

---

## 6. Kế Hoạch Bổ Sung (Action Plan)

### Phase A — Priority HIGH (repository layer)

| Task | Tests | Effort | Impact |
|---|---|---|---|
| Tạo `test_repositories.py` | 28 | MEDIUM | Verify toàn bộ data access layer |
| Bổ sung `test_job_service.py` | 13 | MEDIUM | Cover `get_job_result` + cancel edge cases |
| Bổ sung `test_retention_cleanup.py` | 4 | LOW | Cover storage interactions |

### Phase B — Priority MEDIUM (pure logic + edge cases)

| Task | Tests | Effort | Impact |
|---|---|---|---|
| Tạo `test_queue_messages.py` | 4 | LOW | Verify message format |
| Tạo `test_storage_helpers.py` | 3 | LOW | Verify key generation |
| Bổ sung `test_retry_orchestrator.py` | 3 | LOW | Subject format verification |
| Bổ sung `test_heartbeat_monitor.py` | 1 | LOW | Edge case |
| Bổ sung `test_scheduler.py` | 1 | LOW | Idempotent init |

### Phase C — Priority LOW (infrastructure + cosmetic)

| Task | Tests | Effort | Impact |
|---|---|---|---|
| Tạo `test_exceptions.py` | 4 | LOW | Verify exception attributes |
| Tạo `test_middleware.py` | 4 | MEDIUM | Verify request handling |
| Fix `test_upload.py:test_file_size_limit` | 1 | LOW | Remove placeholder |

---

## 7. Recommendations

### Immediate Actions (nên làm ngay)

1. **Tạo `test_repositories.py`** — Đây là gap lớn nhất. Repository layer xử lý toàn bộ database queries (filtering, pagination, soft-delete, counter increment). Mock ở service layer không đảm bảo queries chạy đúng trên DB thật.

2. **Bổ sung tests cho `JobService.get_job_result()`** — Method này là luồng chính để user lấy kết quả OCR. Hiện chưa có test nào cover.

3. **Thêm conditional skip cho API tests** — Các file `test_auth.py`, `test_upload.py`, `test_health.py` sẽ fail nếu backend không running. Thêm:
   ```python
   @pytest.fixture(autouse=True)
   def check_server():
       try:
           httpx.get("http://localhost:8000/health", timeout=2)
       except httpx.ConnectError:
           pytest.skip("Backend not running")
   ```

### Process Improvements

4. **Tách API tests thành marker riêng:**
   ```bash
   # Chỉ chạy unit tests (không cần services)
   pytest backend/ -m "not api_test" -v

   # Chạy full (cần services running)
   pytest backend/ -v
   ```

5. **CI/CD integration:** Thêm pytest vào CI pipeline, chạy unit tests (Phase A+B) trước mỗi merge.

6. **Coverage tracking:** Thêm `pytest-cov` vào requirements, set threshold 80% để ngăn regression.

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Repository bug missed do chỉ test qua mock | **HIGH** | HIGH | Tạo `test_repositories.py` với in-memory SQLite |
| `get_job_result` bug (user nhận sai kết quả) | MEDIUM | **HIGH** | Thêm tests JS-009→011 |
| API tests fail trên CI (no backend) | **HIGH** | MEDIUM | Conditional skip + marker separation |
| Retention cleanup bỏ sót files | LOW | MEDIUM | Thêm RC-005→007 |
| Rate limiter misconfigured | LOW | LOW | Tests đã cover 90% |

---

## 9. Tổng Kết

| Hạng mục | Kết quả |
|---|---|
| **Module coverage** | 13/18 modules có test (72%) |
| **Full coverage modules** | 8/18 (44%) — SM, RI, HS, Auth, Upload, FP, AL, Health |
| **Critical gap** | Repository layer (0%), JobService.get_job_result (0%) |
| **Quality** | Tests hiện tại chất lượng TỐT (pattern consistent, isolation đúng) |
| **Recommendation** | Bổ sung **47 test cases** theo 3 phases (A→B→C) |

### Kết luận

Phase 1 unit tests đang ở mức **76% coverage** — đủ cho business logic core (StateMachine, Retry, Heartbeat). Tuy nhiên **Repository layer chưa có test trực tiếp** là rủi ro lớn nhất — bất kỳ bug nào trong SQL queries, filtering, pagination sẽ không bị phát hiện bởi unit tests hiện tại.

**Ưu tiên #1:** Tạo `test_repositories.py` (28 tests) + bổ sung `get_job_result` tests.
**Ưu tiên #2:** Hoàn thiện edge cases cho RetryOrchestrator, RetentionCleanup.
**Ưu tiên #3:** Tạo tests cho infrastructure helpers (messages, storage, exceptions).

---

*Report generated by QA Automation Engineer — 2026-03-12*
