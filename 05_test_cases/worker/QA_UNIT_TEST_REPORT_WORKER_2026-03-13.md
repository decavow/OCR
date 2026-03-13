# QA Worker Unit Test Report — 2026-03-13

> Báo cáo đánh giá mức độ coverage unit test cho toàn bộ OCR Worker (3 engines: PaddleOCR, Tesseract, PaddleOCR-VL).

---

## 1. Summary

| Metric | Value |
|---|---|
| Tổng test cases đã có (existing) | **20** pytest tests + 5 manual |
| Tổng test cases theo Test Matrix (planned) | **213** tests |
| Test files đã có | **3** pytest files + 1 manual runner |
| Test files cần thêm (NEW) | **15** files |
| Coverage hiện tại (existing/planned) | **~9%** |
| Test cases cần bổ sung | **193** tests |

---

## 2. Hiện Trạng — Tests Đã Có

### 2.1 Existing Test Files & Count

| # | File | Tests | Type | Cần Services? |
|---|---|---|---|---|
| 1 | `test_ocr_processor.py` | 11 | Integration (real PaddleOCR) | PaddleOCR installed |
| 2 | `test_queue_client.py` | 6 | Integration (real NATS) | NATS + Backend running |
| 3 | `test_e2e_flow.py` | 6 | E2E (full stack) | NATS + Backend + MinIO |
| 4 | `run_tests.py` | 5 | Manual runner (non-pytest) | Full stack |
| | **TỔNG** | **20 pytest + 5 manual** | | |

### 2.2 Chi Tiết Existing Tests

#### `test_ocr_processor.py` (11 tests)

| Class | Method | Tests What |
|---|---|---|
| `TestTextRawHandler` | `test_handler_initialization` | PaddleOCR init (GPU/CPU fallback) |
| | `test_process_minimal_png` | 1x1 PNG không crash |
| | `test_process_image_with_text` | Extract text "Hello OCR 123" |
| | `test_output_format_txt` | Return plain text bytes |
| | `test_output_format_json` | Return JSON with text/lines fields |
| | `test_json_includes_details` | JSON has confidence + bounding boxes |
| | `test_handles_rgba_image` | RGBA → RGB conversion |
| | `test_handles_grayscale_image` | Grayscale handling |
| `TestOCRProcessor` | `test_processor_initialization` | Handler registry has "ocr_text_raw" |
| | `test_processor_ocr_text_raw_method` | End-to-end process call |
| | `test_processor_unknown_method` | ValueError on bad method |

#### `test_queue_client.py` (6 tests)

| Class | Method | Tests What |
|---|---|---|
| `TestNATSConnection` | `test_connect_to_nats` | NATS server reachable |
| | `test_jetstream_available` | JetStream enabled |
| | `test_ocr_jobs_stream_exists` | OCR_JOBS stream with subjects |
| `TestQueueClient` | `test_queue_client_connect` | QueueClient connects |
| | `test_queue_client_pull_empty` | Pull timeout → None |
| | `test_queue_client_message_format` | Job dict has required fields |

#### `test_e2e_flow.py` (6 tests)

| Class | Method | Tests What |
|---|---|---|
| `TestUploadToQueue` | `test_upload_creates_job_in_nats` | Upload → message count increases |
| | `test_upload_multiple_creates_multiple_jobs` | 3 files → 3 messages |
| | `test_job_message_contains_correct_subject` | Subject = `ocr.{method}.tier{N}` |
| `TestWorkerProcessing` | `test_worker_can_download_uploaded_file` | File proxy download works |
| | `test_simulate_worker_flow` | Full: upload → pull → OCR → ack |
| `TestRequestStatus` | `test_request_status_after_upload` | Status = SUBMITTED/QUEUED/PROCESSING |

### 2.3 Test Types Distribution

| Type | Count | % | Chạy Offline? |
|---|---|---|---|
| Integration (real OCR engine) | 11 | 44% | Cần PaddleOCR |
| Integration (real NATS) | 6 | 24% | Cần NATS + Backend |
| E2E (full stack) | 6 | 24% | Cần full stack |
| Manual (non-pytest) | 5 | 8% (riêng) | Cần full stack |
| **Unit tests (offline, mock)** | **0** | **0%** | — |

---

## 3. Gap Analysis — Cần Bổ Sung

### 3.1 Phân Tích Theo Component

| Component | Source File | Existing Tests | Planned Tests | Coverage | Gap |
|---|---|---|---|---|---|
| **WorkerState** | `core/state.py` | 0 | 10 | **0%** | 10 |
| **GracefulShutdown** | `core/shutdown.py` | 0 | 5 | **0%** | 5 |
| **Error Classification** | `utils/errors.py` | 0 | 15 | **0%** | 15 |
| **Settings/Config** | `config.py` | 0 | 8 | **0%** | 8 |
| **Cleanup Utility** | `utils/cleanup.py` | 0 | 5 | **0%** | 5 |
| **PaddleOCR Preprocessing** | `engines/paddle_text/preprocessing.py` | 0 | 5 | **0%** | 5 |
| **PaddleOCR Postprocessing** | `engines/paddle_text/postprocessing.py` | 0 | 11 | **0%** | 11 |
| **Tesseract Preprocessing** | `engines/tesseract/preprocessing.py` | 0 | 10 | **0%** | 10 |
| **Tesseract Postprocessing** | `engines/tesseract/postprocessing.py` | 0 | 9 | **0%** | 9 |
| **Paddle-VL Preprocessing** | `engines/paddle_vl/preprocessing.py` | 0 | 8 | **0%** | 8 |
| **Paddle-VL Postprocessing** | `engines/paddle_vl/postprocessing.py` | 0 | 22 | **0%** | 22 |
| **QueueClient** | `clients/queue_client.py` | 3 (integration) | 11 | **~27%** | 8 |
| **FileProxyClient** | `clients/file_proxy_client.py` | 1 (E2E) | 12 | **~8%** | 11 |
| **OrchestratorClient** | `clients/orchestrator_client.py` | 0 | 12 | **0%** | 12 |
| **HeartbeatClient** | `clients/heartbeat_client.py` | 0 | 13 | **0%** | 13 |
| **OCRProcessor** | `core/processor.py` | 3 (integration) | 11 | **~27%** | 8 |
| **OCRWorker Lifecycle** | `core/worker.py` | 0 | 11 | **0%** | 11 |
| **OCRWorker Job Processing** | `core/worker.py` | 1 (E2E) | 21 | **~5%** | 20 |
| **Engine Handlers (integration)** | `engines/*/handler.py` | 8 (real OCR) | 14 | **~57%** | 6 |
| **TỔNG** | | **~20** | **213** | **~9%** | **193** |

### 3.2 Phân Loại Gap Theo Mức Độ Nghiêm Trọng

#### CRITICAL — Business Logic Không Có Test

| Component | Gap | Tại sao Critical |
|---|---|---|
| **OCRWorker Job Processing** | 20 tests | Toàn bộ luồng xử lý job: download → OCR → upload → status update → ack/nak. Nếu logic sai, job sẽ bị mất hoặc xử lý sai |
| **OCRWorker Lifecycle** | 11 tests | Register, approval flow, heartbeat action handling, graceful shutdown. Nếu sai, worker không start hoặc không dừng đúng cách |
| **Error Classification** | 15 tests | Quyết định retry hay permanent fail. Nếu sai, job retriable bị drop hoặc job permanent bị retry vô hạn |
| **OrchestratorClient** | 12 tests | Status update, register, deregister. Nếu sai, backend không biết trạng thái thật của job |

#### HIGH — Data Processing Không Có Test

| Component | Gap | Tại sao High |
|---|---|---|
| **Paddle-VL Postprocessing** | 22 tests | Phức tạp nhất: layout analysis, table HTML→markdown, region extraction, quality assessment. Nhiều edge cases |
| **Tesseract Pre/Postprocessing** | 19 tests | PDF-to-images, multi-page handling, confidence normalization, word grouping |
| **PaddleOCR Pre/Postprocessing** | 16 tests | Image conversion, OCR result parsing, JSON formatting |
| **HeartbeatClient** | 13 tests | Periodic heartbeat, action callback. Nếu sai, worker bị coi là dead |
| **FileProxyClient** | 11 tests | Download/upload with access key. Nếu sai, file không tải được |

#### MEDIUM — Infrastructure/Config

| Component | Gap | Tại sao Medium |
|---|---|---|
| **WorkerState** | 10 tests | State tracking cho heartbeat payload |
| **QueueClient (unit)** | 8 tests | Existing integration tests cover happy path, thiếu mock-based edge cases |
| **Settings/Config** | 8 tests | Env var parsing, defaults |
| **Engine Handlers (mock)** | 6 tests | Fallback chain, GPU→CPU, language mapping |

#### LOW — Utility

| Component | Gap |
|---|---|
| **GracefulShutdown** | 5 tests |
| **Cleanup Utility** | 5 tests |

---

## 4. Đánh Giá Chất Lượng Tests Hiện Có

### 4.1 Điểm Mạnh

| Aspect | Assessment |
|---|---|
| **Real OCR validation** | `test_ocr_processor.py` test thật PaddleOCR — verify output chính xác |
| **E2E coverage** | `test_e2e_flow.py` cover toàn bộ flow upload → queue → download → OCR → ack |
| **GPU/CPU fallback** | Tests handle GPU unavailable gracefully |
| **Fixture quality** | `test_image_with_text` tạo image có text thật để verify OCR |
| **Message format** | Verify job dict có đầy đủ required fields |

### 4.2 Điểm Yếu / Rủi Ro

| Issue | Severity | Details |
|---|---|---|
| **0 unit tests (offline/mock)** | **CRITICAL** | Tất cả tests đều cần external services. Không chạy được trên CI, không chạy được khi develop offline |
| **0 tests cho worker lifecycle** | **CRITICAL** | `OCRWorker.start()`, `run()`, `stop()`, `process_job()` — toàn bộ main loop chưa test |
| **0 tests cho error handling** | **CRITICAL** | `classify_error()`, `_handle_failure()` — quyết định retry/permanent hoàn toàn chưa verify |
| **0 tests cho clients (mock)** | **HIGH** | OrchestratorClient, HeartbeatClient chưa test. FileProxyClient chỉ 1 E2E test |
| **0 tests cho preprocessing/postprocessing** | **HIGH** | Toàn bộ data transformation chưa có unit test riêng |
| **Tesseract handler chưa có test** | **HIGH** | Chỉ test PaddleOCR, chưa test Tesseract handler |
| **Paddle-VL handler chưa có test** | **HIGH** | Structured extraction (phức tạp nhất) chưa test |
| **conftest.py path sai** | MEDIUM | Line 14: `WORKER_DIR = Path(...) / "worker"` — nên là `"03_worker"` |
| **Test skip nhiều** | MEDIUM | Nhiều test dùng `pytest.skip()` khi service unavailable → CI sẽ skip hết |
| **`run_tests.py` không phải pytest** | LOW | Manual runner — không chạy được qua pytest, không report coverage |

### 4.3 Test Quality Score

| Criteria | Score (1-5) | Notes |
|---|---|---|
| Consistency | 3/5 | Pattern OK nhưng mix giữa real + skip |
| Readability | 4/5 | Clear docstrings, good naming |
| Completeness | 1/5 | Chỉ cover ~9% planned tests |
| Maintainability | 2/5 | All tests depend on running services — fragile |
| Reliability | 2/5 | Many pytest.skip paths, NATS state shared between tests |
| **Offline-ability** | **0/5** | **Không có test nào chạy được offline** |

---

## 5. So Sánh Với Backend Tests

| Metric | Backend | Worker | Nhận xét |
|---|---|---|---|
| Existing tests | 149 | 20 | Worker ít hơn 7x |
| Planned tests | 196 | 213 | Worker cần nhiều hơn (3 engines) |
| Current coverage | 76% | 9% | Worker tụt hậu nghiêm trọng |
| Unit tests (mock) | 100+ | **0** | Worker hoàn toàn thiếu unit tests |
| Can run offline | ~110 | **0** | Worker không test được offline |
| Module full coverage | 8/18 (44%) | 0/19 (0%) | Không module nào đạt full coverage |

---

## 6. Kế Hoạch Bổ Sung (Action Plan)

### Phase A — Pure Logic (Priority: CRITICAL, Effort: LOW)
> Chạy được offline, không cần install PaddleOCR/Tesseract. Nên làm đầu tiên.

| # | File | Tests | Effort | Component |
|---|---|---|---|---|
| 1 | `test_worker_state.py` | 10 | LOW | WorkerState — state tracking |
| 2 | `test_worker_errors.py` | 15 | LOW | Error classification — retry vs permanent |
| 3 | `test_worker_shutdown.py` | 5 | LOW | GracefulShutdown — signal handling |
| 4 | `test_worker_config.py` | 8 | LOW | Settings — env var parsing |
| 5 | `test_worker_cleanup.py` | 5 | LOW | Cleanup — temp files |
| | **Subtotal** | **43** | | |

### Phase B — Pre/Postprocessing (Priority: HIGH, Effort: MEDIUM)
> Cần PIL + numpy nhưng KHÔNG cần PaddleOCR/Tesseract engines. Test data transformation logic.

| # | File | Tests | Effort | Component |
|---|---|---|---|---|
| 6 | `test_engine_paddle_preprocessing.py` | 5 | LOW | Image → numpy array |
| 7 | `test_engine_paddle_postprocessing.py` | 11 | MEDIUM | OCR result → text/JSON |
| 8 | `test_engine_tesseract_preprocessing.py` | 10 | MEDIUM | Image/PDF → PIL images |
| 9 | `test_engine_tesseract_postprocessing.py` | 9 | MEDIUM | Tesseract data → text/JSON |
| 10 | `test_engine_paddlevl_preprocessing.py` | 8 | LOW | Image → numpy + upscale |
| 11 | `test_engine_paddlevl_postprocessing.py` | 22 | HIGH | Regions, tables, markdown, quality |
| | **Subtotal** | **65** | | |

### Phase C — Client Layer (Priority: CRITICAL, Effort: MEDIUM)
> Mock httpx + NATS. Verify HTTP calls, headers, payloads.

| # | File | Tests | Effort | Component |
|---|---|---|---|---|
| 12 | `test_worker_file_proxy.py` | 12 | MEDIUM | Download/upload + access key |
| 13 | `test_worker_orchestrator.py` | 12 | MEDIUM | Register, status update, deregister |
| 14 | `test_worker_heartbeat.py` | 13 | MEDIUM | Periodic heartbeat + action callback |
| 15 | `test_worker_queue_client.py` | 11 | MEDIUM | Pull, ack, nak, term (mock NATS) |
| | **Subtotal** | **48** | | |

### Phase D — Worker Core (Priority: CRITICAL, Effort: HIGH)
> Mock all clients. Verify main loop, job processing, error handling.

| # | File | Tests | Effort | Component |
|---|---|---|---|---|
| 16 | `test_worker_processor.py` | 11 | MEDIUM | Engine selection, method routing |
| 17 | `test_worker_lifecycle.py` | 11 | HIGH | start/stop, approval flow, heartbeat actions |
| 18 | `test_worker_job_processing.py` | 21 | HIGH | process_job, _handle_failure, run loop |
| | **Subtotal** | **43** | | |

### Phase E — Engine Handler Integration (Priority: MEDIUM, Effort: MEDIUM)
> Mock PaddleOCR/Tesseract/PPStructure internals. Test handler classes.

| # | File | Tests | Effort | Component |
|---|---|---|---|---|
| 19 | `test_engine_handlers.py` | 14 | MEDIUM | All 3 handlers: init, process, fallback chain |
| | **Subtotal** | **14** | | |

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Error classification bug → job retry vô hạn hoặc drop sai | **HIGH** | **CRITICAL** | Phase A: `test_worker_errors.py` (15 tests) |
| Worker _handle_failure bug → message leak (không ack/nak) | **HIGH** | **CRITICAL** | Phase D: `test_worker_job_processing.py` (WJ-013→016) |
| Paddle-VL postprocessing bug → corrupt structured output | HIGH | **HIGH** | Phase B: `test_engine_paddlevl_postprocessing.py` (22 tests) |
| HeartbeatClient bug → worker marked dead by backend | HIGH | HIGH | Phase C: `test_worker_heartbeat.py` (13 tests) |
| OrchestratorClient bug → status never updated | HIGH | HIGH | Phase C: `test_worker_orchestrator.py` (12 tests) |
| Worker lifecycle bug → worker hangs on start/stop | MEDIUM | HIGH | Phase D: `test_worker_lifecycle.py` (11 tests) |
| Tesseract PDF preprocessing bug → multi-page fails | MEDIUM | MEDIUM | Phase B: `test_engine_tesseract_preprocessing.py` (TP-010) |
| Access key not forwarded → 403 on file proxy | MEDIUM | HIGH | Phase C: `test_worker_file_proxy.py` (FPC-006, FPC-011) |
| CI cannot run any worker tests | **HIGH** | MEDIUM | Phase A: 43 offline tests immediately runnable |
| Config parsing bug → wrong subject filter | LOW | MEDIUM | Phase A: `test_worker_config.py` (8 tests) |

---

## 8. Metrics Sau Khi Hoàn Thành

### Projected Coverage

| Phase | Tests Added | Cumulative | Coverage |
|---|---|---|---|
| Current (existing) | — | 20 | ~9% |
| + Phase A (pure logic) | +43 | 63 | ~30% |
| + Phase B (pre/postprocessing) | +65 | 128 | ~60% |
| + Phase C (clients) | +48 | 176 | ~83% |
| + Phase D (worker core) | +43 | 219 | ~95% |
| + Phase E (engine handlers) | +14 | 233 | ~100% |

### Offline Test Ratio (Target: >80%)

| Phase | Offline Tests | Total | Offline Ratio |
|---|---|---|---|
| Current | 0 | 20 | 0% |
| After all phases | 213 | 233 | **91%** |

---

## 9. Đặc Biệt: Paddle-VL Postprocessing — Module Phức Tạp Nhất

Module `engines/paddle_vl/postprocessing.py` là module phức tạp nhất trong worker với **22 test cases planned**, bao gồm:

### Critical Functions:
1. **`extract_regions()`** — Parse PPStructure output → structured regions
   - Text, title, list, table, figure region types
   - HTML table validation + fallback to text extraction
   - Reading order sort (top-to-bottom, left-to-right)
   - Confidence extraction

2. **`html_table_to_markdown()`** — HTML table → markdown pipe format
   - Header detection, separator row
   - Colspan/rowspan handling

3. **`assess_result_quality()`** — Quality gate cho fallback chain
   - Determines if result is good enough hoặc cần fallback
   - False → triggers next fallback level

4. **`format_structured_output()`** — 3 output formats: JSON, markdown, text
   - JSON: Full structure with summary
   - Markdown: Page breaks, region formatting
   - Text: Plain content extraction

### Tại sao cần ưu tiên:
- Fallback chain (4 levels) depend vào `assess_result_quality()` — nếu function này sai, fallback không hoạt động đúng
- Table HTML→markdown conversion dễ break với edge cases (empty table, no header, nested tables)
- Region sorting ảnh hưởng trực tiếp đến reading order của output

---

## 10. Tổng Kết

| Hạng mục | Kết quả |
|---|---|
| **Component coverage** | 0/19 components có unit test (0%) |
| **Critical gaps** | Worker lifecycle, error handling, orchestrator client, job processing |
| **Offline test capability** | 0 tests chạy được offline |
| **Highest risk** | Error classification + _handle_failure = quyết định retry/drop |
| **Most complex untested** | Paddle-VL postprocessing (22 test cases) |
| **Quality of existing** | Integration tests tốt nhưng fragile (depend services) |
| **Recommendation** | Bổ sung **193 unit tests** theo 5 phases (A→E) |

### Kết luận

Worker tests đang ở tình trạng **rất thiếu** — chỉ **9% coverage**, **0 unit tests offline**. So với backend (76%), worker tụt hậu nghiêm trọng. Toàn bộ business logic (lifecycle, job processing, error handling, data transformation) chỉ được verify gián tiếp qua E2E tests cần full stack.

**Ưu tiên tuyệt đối:**
1. **Phase A** (43 tests, effort LOW) — Có thể làm ngay, chạy offline, cover error classification + state + config
2. **Phase C** (48 tests, effort MEDIUM) — Client layer mock, verify HTTP calls + NATS operations
3. **Phase D** (43 tests, effort HIGH) — Worker core logic, job processing loop, _handle_failure

Sau 3 phases đầu (134 tests), coverage sẽ đạt **~63%** và CI sẽ chạy được **134 tests offline**.

---

*Report generated by QA Automation Engineer — 2026-03-13*
