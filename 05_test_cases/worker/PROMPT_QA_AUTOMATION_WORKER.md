# Prompt: QA Automation — Unit Test Suite cho OCR Worker

> Bạn là QA Automation Engineer. Nhiệm vụ: viết **unit tests** bằng Python/Pytest để verify toàn bộ logic xử lý của OCR Worker. Tests đặt trong `00_test/ocr_worker/` (white-box, import code trực tiếp, mock external services).

---

## 1. Mục Tiêu

Verify rằng mỗi component trong worker hoạt động **đúng** theo thiết kế:
- Mỗi public method của mỗi class đều có test
- Cover **happy path → edge case → error case** (theo thứ tự)
- Worker logic phải test được **KHÔNG CẦN** NATS, MinIO, backend running
- Engine logic test với mock OCR engines (PaddleOCR, Tesseract) khi có thể, real engine khi cần verify output

---

## 2. Ranh Giới & Phạm Vi

### Bạn CHỈ làm việc trong:
```
00_test/ocr_worker/         ← Unit tests cho worker (white-box)
```

### KHÔNG modify:
```
02_backend/                 ← Backend code
03_worker/                  ← Worker production code — không sửa
```

### Phân biệt test types:
- `00_test/ocr_worker/test_ocr_processor.py` — Existing: test real OCR engine (cần PaddleOCR installed)
- `00_test/ocr_worker/test_queue_client.py` — Existing: test real NATS (cần NATS running)
- `00_test/ocr_worker/test_e2e_flow.py` — Existing: E2E flow (cần full stack)
- **MỚI**: Unit tests mock external deps → chạy được offline, nhanh

---

## 3. Tài Liệu Tham Chiếu

| Tài liệu | Mục đích |
|---|---|
| `03_worker/app/core/worker.py` | Main worker lifecycle + job processing |
| `03_worker/app/core/processor.py` | Engine factory + OCR dispatch |
| `03_worker/app/core/state.py` | Worker state tracking |
| `03_worker/app/core/shutdown.py` | Graceful shutdown handler |
| `03_worker/app/engines/base.py` | Base handler interface |
| `03_worker/app/engines/paddle_text/` | PaddleOCR text engine (3 files) |
| `03_worker/app/engines/tesseract/` | Tesseract engine (3 files) |
| `03_worker/app/engines/paddle_vl/` | PaddleOCR-VL structured engine (3 files) |
| `03_worker/app/clients/*.py` | HTTP + NATS clients (4 files) |
| `03_worker/app/utils/errors.py` | Error classification |
| `03_worker/app/config.py` | Worker settings |
| `00_test/ocr_worker/conftest.py` | Existing fixtures — reuse |

---

## 4. Tech Stack & Import Pattern

### Dependencies:
```
pytest >= 7.0
pytest-asyncio >= 0.21
Pillow (cho image fixtures)
numpy (cho engine preprocessing tests)
```

### Import Pattern (BẮT BUỘC):
Worker code dùng relative imports từ `app.*`, cần thêm path:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from types import SimpleNamespace

# Add worker source to path
worker_path = Path(__file__).parent.parent.parent / "03_worker"
sys.path.insert(0, str(worker_path))
```

### Mock Pattern cho Worker:
```python
# Mock NATS / HTTP clients
def make_queue_mock():
    queue = MagicMock()
    queue.connect = AsyncMock()
    queue.disconnect = AsyncMock()
    queue.pull_job = AsyncMock(return_value=None)
    queue.ack = AsyncMock()
    queue.nak = AsyncMock()
    queue.term = AsyncMock()
    return queue

def make_file_proxy_mock():
    proxy = MagicMock()
    proxy.download = AsyncMock(return_value=(b"fake_image", "image/png", "test.png"))
    proxy.upload = AsyncMock(return_value="results/key.txt")
    proxy.set_access_key = MagicMock()
    proxy.has_access_key = True
    return proxy

def make_orchestrator_mock():
    orch = MagicMock()
    orch.register = AsyncMock(return_value={
        "type_status": "APPROVED",
        "instance_status": "ACTIVE",
        "access_key": "sk_test_key",
    })
    orch.deregister = AsyncMock()
    orch.update_status = AsyncMock()
    orch.set_access_key = MagicMock()
    return orch

def make_heartbeat_mock():
    hb = MagicMock()
    hb.start = AsyncMock()
    hb.stop = AsyncMock()
    hb.set_state = MagicMock()
    hb.set_action_callback = MagicMock()
    hb.set_access_key = MagicMock()
    return hb

# Standard job dict
def make_job_dict(job_id="job-1", file_id="file-1", method="ocr_text_raw"):
    return {
        "job_id": job_id,
        "file_id": file_id,
        "request_id": "req-1",
        "method": method,
        "tier": 0,
        "output_format": "txt",
        "object_key": "user1/req1/file1/test.png",
        "_msg_id": "msg-1",
    }
```

### Naming Convention:
```
test_worker_{component}.py      ← File name
class Test{Feature}:            ← Group by feature
    def test_{action}_{condition}:  ← Test name
```

---

## 5. Fixtures (thêm vào `conftest.py` hoặc file-local)

### Existing fixtures (reuse):
| Fixture | Mô tả |
|---|---|
| `event_loop` | Session-scoped async loop |
| `sample_png` | Minimal valid 1x1 PNG bytes |
| `test_image_with_text` | PIL Image "Hello OCR 123" |

### Fixtures MỚI cần thêm:
```python
@pytest.fixture
def shutdown_handler():
    """GracefulShutdown mock."""
    handler = MagicMock()
    handler.is_shutting_down = False
    return handler

@pytest.fixture
def job_dict():
    """Standard job message dict."""
    return make_job_dict()

@pytest.fixture
def sample_pdf():
    """Minimal valid PDF bytes."""
    return b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"

@pytest.fixture
def rgb_image_array():
    """Simple 100x100 RGB numpy array."""
    import numpy as np
    return np.zeros((100, 100, 3), dtype=np.uint8)

@pytest.fixture
def grayscale_image_array():
    """Simple 100x100 grayscale numpy array."""
    import numpy as np
    return np.zeros((100, 100), dtype=np.uint8)
```

---

## 6. Test Matrix — TẤT CẢ Worker Components

---

### 6.1. WorkerState (`core/state.py`)
**File test:** `test_worker_state.py` (MỚI)
**Loại:** Pure logic, KHÔNG cần mock

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WS-001 | `__init__` | Initial state | happy | status="idle", current_job_id=None, counters=0 |
| WS-002 | `start_job` | Start processing job | happy | status="processing", current_job_id set, job_started_at set |
| WS-003 | `end_job` | End processing job | happy | status="idle", current_job_id=None, files_completed += 1 |
| WS-004 | `end_job` | Multiple end_job calls increment counter | happy | files_completed tracks correctly |
| WS-005 | `record_error` | Record error | happy | error_count += 1, status="error" |
| WS-006 | `record_error` | Multiple errors increment counter | happy | error_count = N |
| WS-007 | `to_heartbeat` | Serialize idle state | happy | Dict with all fields, status="idle" |
| WS-008 | `to_heartbeat` | Serialize processing state | happy | Dict with current_job_id, status="processing" |
| WS-009 | lifecycle | start_job → end_job → start_job | edge | State resets correctly between jobs |
| WS-010 | lifecycle | start_job → record_error → end_job | edge | error_count persists, status back to idle |

---

### 6.2. GracefulShutdown (`core/shutdown.py`)
**File test:** `test_worker_shutdown.py` (MỚI)
**Loại:** Pure logic + asyncio

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| GS-001 | `__init__` | Initial state | happy | is_shutting_down=False |
| GS-002 | `handle_signal` | First signal received | happy | is_shutting_down=True, event set |
| GS-003 | `handle_signal` | Second signal (already shutting down) | edge | No crash, log warning |
| GS-004 | `wait_for_shutdown` | Wait then signal | happy | Returns after signal received |
| GS-005 | `wait_for_shutdown` | Already signaled before wait | edge | Returns immediately |

---

### 6.3. Error Classification (`utils/errors.py`)
**File test:** `test_worker_errors.py` (MỚI)
**Loại:** Pure logic, KHÔNG cần mock

| Test ID | Method/Class | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WE-001 | `RetriableError` | Is subclass of WorkerError | happy | `isinstance(err, WorkerError)` |
| WE-002 | `PermanentError` | Is subclass of WorkerError | happy | `isinstance(err, WorkerError)` |
| WE-003 | `DownloadError` | Is subclass of RetriableError | happy | `isinstance(err, RetriableError)` |
| WE-004 | `UploadError` | Is subclass of RetriableError | happy | `isinstance(err, RetriableError)` |
| WE-005 | `InvalidImageError` | Is subclass of PermanentError | happy | `isinstance(err, PermanentError)` |
| WE-006 | `classify_error` | PermanentError → (msg, False) | happy | retriable=False |
| WE-007 | `classify_error` | RetriableError → (msg, True) | happy | retriable=True |
| WE-008 | `classify_error` | DownloadError → (msg, True) | happy | retriable=True (inherits) |
| WE-009 | `classify_error` | InvalidImageError → (msg, False) | happy | retriable=False (inherits) |
| WE-010 | `classify_error` | ConnectionError → (msg, True) | happy | In RETRIABLE_ERRORS list |
| WE-011 | `classify_error` | TimeoutError → (msg, True) | happy | In RETRIABLE_ERRORS list |
| WE-012 | `classify_error` | ValueError → (msg, False) | happy | In NON_RETRIABLE_ERRORS list |
| WE-013 | `classify_error` | Unknown exception → (msg, True) | edge | Default: retriable=True |
| WE-014 | `classify_error` | Error message preserved | happy | msg contains original error text |
| WE-015 | `OCRError` | Is subclass of WorkerError | happy | `isinstance(err, WorkerError)` |

---

### 6.4. Settings / Config (`config.py`)
**File test:** `test_worker_config.py` (MỚI)
**Loại:** Pure logic + env var parsing

| Test ID | Property | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WC-001 | `worker_allowed_methods` | Default value | happy | `["ocr_text_raw"]` |
| WC-002 | `worker_allowed_methods` | Comma-separated env | happy | Correct list parsing |
| WC-003 | `worker_allowed_tiers` | Default value | happy | `[0]` |
| WC-004 | `worker_allowed_tiers` | Comma-separated env | happy | Correct int list |
| WC-005 | `worker_supported_formats` | Default value | happy | `["txt", "json"]` |
| WC-006 | `get_worker_instance_id` | Format check | happy | `"{service_type}-{hostname[:12]}"` |
| WC-007 | `worker_access_key` | Empty string → None | edge | Returns None, not "" |
| WC-008 | `worker_access_key` | Valid key | happy | Returns key string |

---

### 6.5. OCRProcessor (`core/processor.py`)
**File test:** `test_worker_processor.py` (MỚI)
**Loại:** Unit test, mock engine handlers

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WP-001 | `__init__` | Paddle engine loads handler | happy | `"ocr_text_raw"` in handlers |
| WP-002 | `__init__` | Tesseract engine loads handler | happy | `"ocr_text_raw"` in handlers |
| WP-003 | `__init__` | Paddle-VL engine loads handler | happy | `"structured_extract"` in handlers |
| WP-004 | `process` | Valid method dispatches to handler | happy | Handler.process() called |
| WP-005 | `process` | Unknown method raises ValueError | error | `ValueError("Unsupported method")` |
| WP-006 | `process` | Result bytes returned from handler | happy | Return handler output |
| WP-007 | `get_engine_info` | Returns engine info dict | happy | Dict with engine, lang, use_gpu |
| WP-008 | `create_handler` | Paddle → TextRawHandler | happy | Correct class returned |
| WP-009 | `create_handler` | Tesseract → TextRawTesseractHandler | happy | Correct class returned |
| WP-010 | `create_handler` | Paddle-VL → StructuredExtractHandler | happy | Correct class returned |
| WP-011 | `create_handler` | Unknown engine → raise | error | ValueError or appropriate error |

---

### 6.6. OCRWorker — Lifecycle (`core/worker.py`)
**File test:** `test_worker_lifecycle.py` (MỚI)
**Loại:** Service test, mock ALL clients

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WL-001 | `start` | Register + approved + connect queue | happy | access_key set, queue.connect called |
| WL-002 | `start` | Register + PENDING (no access_key) | happy | is_approved=False, still connects |
| WL-003 | `start` | Register + REJECTED | error | Raise or exit (log error) |
| WL-004 | `_set_access_key` | Sets key on all clients | happy | file_proxy, orchestrator, heartbeat, queue all have key |
| WL-005 | `stop` | Cleanup sequence | happy | heartbeat.stop + queue.disconnect + orchestrator.deregister called |
| WL-006 | `stop` | Deregister fails gracefully | edge | No crash on deregister error |
| WL-007 | `_handle_heartbeat_action` | action="continue" | happy | No state change |
| WL-008 | `_handle_heartbeat_action` | action="approved" + access_key | happy | _set_access_key called, is_approved=True |
| WL-009 | `_handle_heartbeat_action` | action="drain" | happy | is_draining=True |
| WL-010 | `_handle_heartbeat_action` | action="shutdown" | happy | shutdown triggered |
| WL-011 | `_graceful_shutdown` | Deregister + shutdown flag | happy | shutdown.is_shutting_down=True |

---

### 6.7. OCRWorker — Job Processing (`core/worker.py`)
**File test:** `test_worker_job_processing.py` (MỚI)
**Loại:** Service test, mock ALL external calls

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| WJ-001 | `process_job` | Happy path: download → process → upload → complete → ack | happy | All steps called in order |
| WJ-002 | `process_job` | Status update to PROCESSING first | happy | orchestrator.update_status("PROCESSING") called first |
| WJ-003 | `process_job` | Status update to COMPLETED with engine_version | happy | engine_version in update call |
| WJ-004 | `process_job` | Output format txt → content_type text/plain | happy | upload called with text/plain |
| WJ-005 | `process_job` | Output format json → content_type application/json | happy | upload called with application/json |
| WJ-006 | `process_job` | Output format md → content_type text/markdown | happy | upload called with text/markdown |
| WJ-007 | `process_job` | state.start_job called at start | happy | state.start_job(job_id) called |
| WJ-008 | `process_job` | state.end_job called in finally | happy | Always called, even on error |
| WJ-009 | `process_job` | Download fails with RetriableError | error | _handle_failure(retriable=True) |
| WJ-010 | `process_job` | OCR fails with PermanentError | error | _handle_failure(retriable=False) |
| WJ-011 | `process_job` | Upload fails with UploadError | error | _handle_failure(retriable=True) |
| WJ-012 | `process_job` | Unknown exception | error | _handle_failure(retriable=True) |
| WJ-013 | `_handle_failure` | Retriable error → NAK with delay | happy | queue.nak(msg_id, delay=5) |
| WJ-014 | `_handle_failure` | Non-retriable error → TERM | happy | queue.term(msg_id) |
| WJ-015 | `_handle_failure` | Job not found (404) → TERM | edge | queue.term(msg_id) |
| WJ-016 | `_handle_failure` | Update status to FAILED with error msg | happy | orchestrator.update_status("FAILED", error=...) |
| WJ-017 | `run` | Not approved → wait loop (sleep) | edge | No pull_job call while not approved |
| WJ-018 | `run` | Draining → wait loop (sleep) | edge | No pull_job call while draining |
| WJ-019 | `run` | Shutdown flag → exit loop | happy | Loop terminates |
| WJ-020 | `run` | Pull job returns None (timeout) → continue | happy | No process_job call |
| WJ-021 | `run` | Pull job returns job → process_job called | happy | process_job called once |

---

### 6.8. QueueClient (`clients/queue_client.py`)
**File test:** `test_worker_queue_client.py` (MỚI)
**Loại:** Unit test, mock NATS

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| QC-001 | `connect` | Connect to NATS + create subscription | happy | nc.connect called, pull_subscribe called |
| QC-002 | `disconnect` | Drain NATS connection | happy | nc.drain called |
| QC-003 | `pull_job` | Valid message → return job dict | happy | Dict with job_id, file_id, _msg_id |
| QC-004 | `pull_job` | Timeout → return None | edge | Return None, no error |
| QC-005 | `pull_job` | Parse error → return None | error | Invalid JSON handled, return None |
| QC-006 | `pull_job` | Message stored for ack/nak | happy | _pending_messages[msg_id] = msg |
| QC-007 | `ack` | Valid msg_id → message acked | happy | msg.ack() called, removed from pending |
| QC-008 | `ack` | Unknown msg_id | edge | No crash (log warning) |
| QC-009 | `nak` | Valid msg_id + delay → message nakked | happy | msg.nak(delay=N) called |
| QC-010 | `nak` | No delay → default nak | happy | msg.nak() called without delay |
| QC-011 | `term` | Valid msg_id → message terminated | happy | msg.term() called |

---

### 6.9. FileProxyClient (`clients/file_proxy_client.py`)
**File test:** `test_worker_file_proxy.py` (MỚI)
**Loại:** Unit test, mock httpx

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| FPC-001 | `__init__` | Initialized with config values | happy | base_url, timeout set |
| FPC-002 | `set_access_key` | Key stored | happy | _access_key = key |
| FPC-003 | `has_access_key` | No key → False | happy | Return False |
| FPC-004 | `has_access_key` | Key set → True | happy | Return True |
| FPC-005 | `download` | Valid response → (bytes, content_type, filename) | happy | Return tuple |
| FPC-006 | `download` | No access key → RuntimeError | error | Raise RuntimeError |
| FPC-007 | `download` | HTTP error → raise | error | httpx.HTTPStatusError raised |
| FPC-008 | `download` | X-Access-Key header sent | happy | Header present in request |
| FPC-009 | `upload` | Valid response → result_key | happy | Return string |
| FPC-010 | `upload` | Content base64 encoded | happy | Payload contains base64 string |
| FPC-011 | `upload` | No access key → RuntimeError | error | Raise RuntimeError |
| FPC-012 | `upload` | X-Access-Key header sent | happy | Header present in request |

---

### 6.10. OrchestratorClient (`clients/orchestrator_client.py`)
**File test:** `test_worker_orchestrator.py` (MỚI)
**Loại:** Unit test, mock httpx

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| OC-001 | `register` | APPROVED response with access_key | happy | Return dict with access_key |
| OC-002 | `register` | PENDING response (no access_key) | happy | Return dict without access_key |
| OC-003 | `register` | Payload includes all fields | happy | service_type, instance_id, methods, tiers in body |
| OC-004 | `register` | Engine info included | happy | engine_info in payload |
| OC-005 | `deregister` | Success | happy | POST called |
| OC-006 | `deregister` | Error ignored (best-effort) | edge | No exception raised |
| OC-007 | `update_status` | PROCESSING status | happy | PATCH with {status: "PROCESSING"} |
| OC-008 | `update_status` | COMPLETED with engine_version | happy | PATCH with engine_version field |
| OC-009 | `update_status` | FAILED with error message | happy | PATCH with {status: "FAILED", error: "..."} |
| OC-010 | `update_status` | No access key → RuntimeError | error | Raise RuntimeError |
| OC-011 | `update_status` | HTTP error → raise | error | httpx.HTTPStatusError raised |
| OC-012 | `update_status` | X-Access-Key header sent | happy | Header present in request |

---

### 6.11. HeartbeatClient (`clients/heartbeat_client.py`)
**File test:** `test_worker_heartbeat.py` (MỚI)
**Loại:** Unit test, mock httpx + asyncio

| Test ID | Method | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| HC-001 | `set_state` | State reference stored | happy | _state set |
| HC-002 | `set_action_callback` | Callback stored | happy | _action_callback set |
| HC-003 | `set_access_key` | Key stored | happy | _access_key set |
| HC-004 | `start` | Creates asyncio task | happy | _task is not None |
| HC-005 | `stop` | Cancels task | happy | _task cancelled |
| HC-006 | `stop` | No task → no error | edge | No crash |
| HC-007 | `_send_heartbeat` | Payload includes state info | happy | Body has status, current_job_id, etc. |
| HC-008 | `_send_heartbeat` | X-Access-Key header if set | happy | Header present |
| HC-009 | `_send_heartbeat` | No access key → no header | edge | Request still sent |
| HC-010 | `_send_heartbeat` | Response with action → callback called | happy | action_callback invoked |
| HC-011 | `_send_heartbeat` | Response without action → no callback | happy | callback not called |
| HC-012 | `_send_heartbeat` | HTTP error → caught, no crash | error | Exception logged, loop continues |
| HC-013 | `_heartbeat_loop` | Loops at correct interval | happy | Sleep with interval_ms/1000 |

---

### 6.12. PaddleOCR Text — Preprocessing (`engines/paddle_text/preprocessing.py`)
**File test:** `test_engine_paddle_preprocessing.py` (MỚI)
**Loại:** Pure logic, cần PIL + numpy

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| PP-001 | `load_image` | Valid PNG bytes → (np.array, size) | happy | Array shape matches image, size tuple |
| PP-002 | `load_image` | RGBA image → RGB conversion | edge | Array shape (H, W, 3) |
| PP-003 | `load_image` | Grayscale image → RGB conversion | edge | Array shape (H, W, 3) |
| PP-004 | `load_image` | Invalid bytes → raise | error | PIL.UnidentifiedImageError |
| PP-005 | `load_image` | Empty bytes → raise | error | Exception raised |

---

### 6.13. PaddleOCR Text — Postprocessing (`engines/paddle_text/postprocessing.py`)
**File test:** `test_engine_paddle_postprocessing.py` (MỚI)
**Loại:** Pure logic

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| PO-001 | `extract_results` | Valid PaddleOCR output | happy | (full_text, text_lines, boxes_data) |
| PO-002 | `extract_results` | Empty OCR result | edge | ("", [], []) |
| PO-003 | `extract_results` | None OCR result | edge | ("", [], []) |
| PO-004 | `extract_results` | Single line result | happy | 1 text_line, 1 box_data |
| PO-005 | `extract_results` | Confidence extracted correctly | happy | 0.0-1.0 range |
| PO-006 | `extract_results` | Bounding box extracted | happy | bbox with 4 points |
| PO-007 | `format_output` | format="txt" → plain text bytes | happy | UTF-8 text bytes |
| PO-008 | `format_output` | format="json" → JSON with metadata | happy | JSON parseable, has text/lines/details |
| PO-009 | `format_output` | JSON includes line count | happy | `lines_count` field |
| PO-010 | `format_output` | JSON includes confidence | happy | `details[].confidence` |
| PO-011 | `format_output` | Empty text → valid output | edge | Empty string/JSON |

---

### 6.14. Tesseract — Preprocessing (`engines/tesseract/preprocessing.py`)
**File test:** `test_engine_tesseract_preprocessing.py` (MỚI)
**Loại:** Pure logic, cần PIL

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| TP-001 | `is_pdf` | PDF magic bytes → True | happy | Return True |
| TP-002 | `is_pdf` | PNG bytes → False | happy | Return False |
| TP-003 | `is_pdf` | Empty bytes → False | edge | Return False |
| TP-004 | `load_images` | PNG bytes → List[Image] with 1 image | happy | len=1, valid Image |
| TP-005 | `load_images` | JPEG bytes → List[Image] with 1 image | happy | len=1, valid Image |
| TP-006 | `load_images` | Invalid bytes → raise | error | Exception raised |
| TP-007 | `prepare_image` | RGBA → RGB | happy | mode="RGB" |
| TP-008 | `prepare_image` | Grayscale → L mode kept | happy | mode="L" |
| TP-009 | `prepare_image` | RGB stays RGB | happy | No conversion |
| TP-010 | `load_images` | PDF bytes → List[Image] (mock pdf2image) | happy | Multiple images returned |

---

### 6.15. Tesseract — Postprocessing (`engines/tesseract/postprocessing.py`)
**File test:** `test_engine_tesseract_postprocessing.py` (MỚI)
**Loại:** Pure logic (mock pytesseract)

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| TO-001 | `extract_plain` | Normal text → text_lines | happy | List of non-empty strings |
| TO-002 | `extract_plain` | Empty image → empty list | edge | [] |
| TO-003 | `extract_detailed` | Normal text → (text_lines, boxes_data) | happy | Lines + boxes with bbox, confidence |
| TO-004 | `extract_detailed` | Confidence normalized (0-100 → 0-1) | happy | Values in 0.0-1.0 |
| TO-005 | `extract_detailed` | Low confidence words filtered | edge | conf < 0 filtered out |
| TO-006 | `format_output` | format="txt" → plain text | happy | UTF-8 bytes |
| TO-007 | `format_output` | format="json" → JSON with pages | happy | JSON with pages, lines, details |
| TO-008 | `format_output` | page_count in JSON | happy | `pages` field correct |
| TO-009 | `_flush_line` | Accumulated words flushed | happy | Line text joined, confidence averaged |

---

### 6.16. PaddleOCR-VL — Preprocessing (`engines/paddle_vl/preprocessing.py`)
**File test:** `test_engine_paddlevl_preprocessing.py` (MỚI)
**Loại:** Pure logic, cần PIL + numpy

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| VP-001 | `detect_file_type` | PDF bytes → "pdf" | happy | Return "pdf" |
| VP-002 | `detect_file_type` | PNG bytes → "image" | happy | Return "image" |
| VP-003 | `detect_file_type` | Empty bytes → "image" | edge | Return "image" |
| VP-004 | `load_images` | PNG bytes → List[np.ndarray] | happy | len=1, RGB array |
| VP-005 | `load_images` | RGBA image → RGB conversion | edge | Shape (H, W, 3) |
| VP-006 | `prepare_image` | Small image → upscaled | happy | Short side >= MIN_SHORT_SIDE |
| VP-007 | `prepare_image` | Large image → not upscaled | happy | No size change |
| VP-008 | `prepare_image` | Very large image → capped at MAX_LONG_SIDE | edge | Long side <= MAX_LONG_SIDE |

---

### 6.17. PaddleOCR-VL — Postprocessing (`engines/paddle_vl/postprocessing.py`)
**File test:** `test_engine_paddlevl_postprocessing.py` (MỚI)
**Loại:** Pure logic

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| VO-001 | `extract_regions` | Text region extracted | happy | Region type="text", content set |
| VO-002 | `extract_regions` | Table region with valid HTML | happy | Region type="table", html + markdown set |
| VO-003 | `extract_regions` | Table with invalid HTML → fallback to text | edge | Region type="table", content extracted from rec_res |
| VO-004 | `extract_regions` | Title region | happy | Region type="title" |
| VO-005 | `extract_regions` | Figure region → placeholder | happy | Region type="figure" |
| VO-006 | `extract_regions` | Regions sorted by reading order | happy | Top-to-bottom, left-to-right |
| VO-007 | `extract_regions` | Confidence values extracted | happy | 0.0-1.0 range |
| VO-008 | `extract_regions_from_raw_ocr` | PaddleOCR output → regions | happy | Regions with bbox + content |
| VO-009 | `extract_regions_from_raw_ocr` | Empty OCR result → empty regions | edge | regions=[] |
| VO-010 | `assess_result_quality` | Good quality → True | happy | Has text blocks with content |
| VO-011 | `assess_result_quality` | Empty pages → False | edge | No valid content |
| VO-012 | `assess_result_quality` | Only tables → True | happy | Valid tables count |
| VO-013 | `html_table_to_markdown` | Simple HTML table → markdown | happy | Pipe-formatted table |
| VO-014 | `html_table_to_markdown` | Table with header → markdown with separator | happy | `|---|` separator row |
| VO-015 | `html_table_to_markdown` | Empty table → empty string | edge | No crash |
| VO-016 | `format_structured_output` | format="json" → full structure | happy | JSON with pages, summary |
| VO-017 | `format_structured_output` | format="md" → markdown with pages | happy | Markdown with page breaks |
| VO-018 | `format_structured_output` | format="txt" → plain text | happy | Extracted text only |
| VO-019 | `_strip_html_wrapper` | Remove html/body tags | happy | Clean content |
| VO-020 | `_is_valid_table_html` | Valid tr/td → True | happy | Return True |
| VO-021 | `_is_valid_table_html` | No table structure → False | edge | Return False |
| VO-022 | `_extract_text_from_table_res` | Extract text from rec_res | happy | Combined text string |

---

### 6.18. Engine Handlers — Integration (mock OCR engine)
**File test:** `test_engine_handlers.py` (MỚI)
**Loại:** Service test, mock PaddleOCR/Tesseract/PPStructure

| Test ID | Handler | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| EH-001 | `TextRawHandler` | process() → valid text bytes | happy | Non-empty bytes returned |
| EH-002 | `TextRawHandler` | get_engine_info() | happy | Dict with engine, version, lang |
| EH-003 | `TextRawHandler` | GPU fallback to CPU | edge | No crash on GPU unavailable |
| EH-004 | `TextRawTesseractHandler` | process() → valid text bytes | happy | Non-empty bytes returned |
| EH-005 | `TextRawTesseractHandler` | get_engine_info() | happy | engine="tesseract", version set |
| EH-006 | `TextRawTesseractHandler` | Language mapping en→eng | happy | self.lang="eng" |
| EH-007 | `TextRawTesseractHandler` | Language mapping vi→vie | happy | self.lang="vie" |
| EH-008 | `TextRawTesseractHandler` | Unknown lang → fallback | edge | No crash |
| EH-009 | `StructuredExtractHandler` | process() → valid bytes | happy | Non-empty bytes returned |
| EH-010 | `StructuredExtractHandler` | get_engine_info() with capabilities | happy | capabilities list present |
| EH-011 | `StructuredExtractHandler` | Fallback chain: table=True → table=False | edge | Falls back on table matcher error |
| EH-012 | `StructuredExtractHandler` | Fallback chain: PPStructure → pure OCR GPU | edge | Falls back to PaddleOCR |
| EH-013 | `StructuredExtractHandler` | Fallback chain: OCR GPU → OCR CPU | edge | Final fallback |
| EH-014 | `StructuredExtractHandler` | Empty result quality → retry fallback | edge | assess_result_quality triggers next step |

---

### 6.19. Cleanup Utility (`utils/cleanup.py`)
**File test:** `test_worker_cleanup.py` (MỚI)
**Loại:** Pure logic, mock filesystem

| Test ID | Function | Scenario | Loại | Kỳ vọng |
|---|---|---|---|---|
| CU-001 | `ensure_temp_dir` | Create temp dir | happy | Directory exists after call |
| CU-002 | `ensure_temp_dir` | Already exists → no error | edge | Idempotent |
| CU-003 | `cleanup_local_files` | With job_id → remove job dir | happy | Job dir removed |
| CU-004 | `cleanup_local_files` | Without job_id → remove all temp | happy | Entire temp dir cleaned |
| CU-005 | `cleanup_local_files` | Dir not exists → no error | edge | No crash |

---

## 7. Thứ Tự Thực Hiện (Priority)

> **LƯU Ý QUAN TRỌNG — Xuất báo cáo sau MỖI phase:**
> Sau khi hoàn thành mỗi phase (A, B, C, D, E), **BẮT BUỘC** xuất báo cáo trung gian ngay lập tức theo format ở mục 13 (Section 13).
> Lý do: Context window có giới hạn — nếu tràn token giữa chừng, toàn bộ kết quả các phase trước sẽ bị mất.
> Báo cáo trung gian phải ghi vào file `05_test_cases/worker/QA_UNIT_TEST_REPORT_WORKER_YYYY-MM-DD.md` (append mỗi phase).
> Nếu session bị ngắt, session mới đọc file report này để biết phase nào đã xong và tiếp tục từ phase tiếp theo.

### Phase A — Pure Logic (không cần external deps, chạy nhanh nhất)
1. `test_worker_state.py` — WorkerState (10 tests)
2. `test_worker_errors.py` — Error classification (15 tests)
3. `test_worker_shutdown.py` — GracefulShutdown (5 tests)
4. `test_worker_config.py` — Settings parsing (8 tests)
5. `test_worker_cleanup.py` — Cleanup utility (5 tests)

### Phase B — Preprocessing & Postprocessing (cần PIL/numpy, không cần OCR engine)
6. `test_engine_paddle_preprocessing.py` — PaddleOCR preprocessing (5 tests)
7. `test_engine_paddle_postprocessing.py` — PaddleOCR postprocessing (11 tests)
8. `test_engine_tesseract_preprocessing.py` — Tesseract preprocessing (10 tests)
9. `test_engine_tesseract_postprocessing.py` — Tesseract postprocessing (9 tests)
10. `test_engine_paddlevl_preprocessing.py` — Paddle-VL preprocessing (8 tests)
11. `test_engine_paddlevl_postprocessing.py` — Paddle-VL postprocessing (22 tests)

### Phase C — Client Layer (mock httpx/NATS)
12. `test_worker_file_proxy.py` — FileProxyClient (12 tests)
13. `test_worker_orchestrator.py` — OrchestratorClient (12 tests)
14. `test_worker_heartbeat.py` — HeartbeatClient (13 tests)
15. `test_worker_queue_client.py` — QueueClient (11 tests)

### Phase D — Worker Core (mock all clients)
16. `test_worker_processor.py` — OCRProcessor (11 tests)
17. `test_worker_lifecycle.py` — OCRWorker lifecycle (11 tests)
18. `test_worker_job_processing.py` — OCRWorker job processing (21 tests)

### Phase E — Engine Handler Integration (mock OCR engines)
19. `test_engine_handlers.py` — All handlers end-to-end (14 tests)

---

## 8. Quy Trình Chạy Test

### Chạy toàn bộ worker unit tests:
```bash
cd 00_test && python -m pytest ocr_worker/ -v --tb=short
```

### Chạy chỉ pure logic (Phase A — nhanh, offline):
```bash
python -m pytest ocr_worker/test_worker_state.py ocr_worker/test_worker_errors.py ocr_worker/test_worker_shutdown.py ocr_worker/test_worker_config.py -v
```

### Chạy preprocessing/postprocessing (Phase B):
```bash
python -m pytest ocr_worker/test_engine_*preprocessing*.py ocr_worker/test_engine_*postprocessing*.py -v
```

### Chạy client layer (Phase C):
```bash
python -m pytest ocr_worker/test_worker_file_proxy.py ocr_worker/test_worker_orchestrator.py ocr_worker/test_worker_heartbeat.py ocr_worker/test_worker_queue_client.py -v
```

### Chạy worker core (Phase D+E):
```bash
python -m pytest ocr_worker/test_worker_processor.py ocr_worker/test_worker_lifecycle.py ocr_worker/test_worker_job_processing.py ocr_worker/test_engine_handlers.py -v
```

### Chạy với coverage:
```bash
python -m pytest ocr_worker/ -v --cov=../03_worker/app --cov-report=term-missing
```

### Phân biệt với E2E tests (cần services running):
```bash
# Chỉ unit tests (offline)
python -m pytest ocr_worker/ -v -k "not (e2e or queue_client or ocr_processor)" --ignore=ocr_worker/test_e2e_flow.py

# Chỉ E2E (cần full stack)
python -m pytest ocr_worker/test_e2e_flow.py -v
```

---

## 9. Quy Tắc BẮT BUỘC

1. **KHÔNG sửa code production** (`03_worker/`) — nếu test fail vì bug, report bug
2. **Mỗi test function = 1 scenario**
3. **Sắp xếp:** Happy → Edge → Error trong mỗi class
4. **Mock external services:** NATS, HTTP, PaddleOCR, Tesseract, PPStructure — KHÔNG mock business logic
5. **Test phải chạy offline** — không depend vào NATS, MinIO, backend running (trừ file đã mark E2E)
6. **Assert cụ thể:** Kiểm tra giá trị cụ thể, call arguments, call order
7. **Không depend thứ tự** giữa test functions
8. **Cleanup:** Nếu tạo temp files, cleanup trong teardown
9. **Import pattern:** Thêm worker path vào sys.path (xem mục 4)
10. **OCR engine tests:** Mock PaddleOCR/Tesseract cho unit tests, dùng real engine chỉ trong `test_ocr_processor.py` (existing)

---

## 10. Report Format

Sau khi chạy xong, report theo format:

```markdown
# QA Worker Unit Test Report — YYYY-MM-DD

## Summary
| Metric | Value |
|---|---|
| Total test cases | N |
| Passed | N |
| Failed | N |
| Skipped | N |
| Coverage | X% |

## Results by Component
| Component | File | Tests | Pass | Fail | Skip |
|---|---|---|---|---|---|
| WorkerState | test_worker_state.py | 10 | 10 | 0 | 0 |
| ... | ... | ... | ... | ... | ... |

## Failed Tests
| Test ID | File:Line | Expected | Actual | Root Cause |
|---|---|---|---|---|
| WJ-009 | test_worker_job_processing.py:80 | ... | ... | ... |

## Bugs Found
| Bug ID | Severity | Component | Description |
|---|---|---|---|
| WBUG-001 | HIGH | OCRWorker | ... |

## Recommendations
- ...
```

---

## 11. Checklist Trước Khi Submit

- [ ] Tất cả test cases từ Test Matrix (mục 6) đã implement
- [ ] Tất cả tests pass (hoặc xfail với reason)
- [ ] Không có test depend vào external services (trừ file marked E2E)
- [ ] Mock pattern đúng (mock clients, KHÔNG mock logic)
- [ ] Mỗi test file có docstring mô tả component + coverage
- [ ] Report đã viết theo format mục 10
- [ ] File tracking cập nhật (`04_docs/06-OCR_update_progress/`)

---

## 12. Tóm Tắt Test Count

| Phase | Files | Tests |
|---|---|---|
| A: Pure Logic | 5 | 43 |
| B: Pre/Postprocessing | 6 | 65 |
| C: Client Layer | 4 | 48 |
| D: Worker Core | 3 | 43 |
| E: Engine Handlers | 1 | 14 |
| **TỔNG** | **19** | **213** |

### So sánh với existing:
| | Existing | Planned | Gap |
|---|---|---|---|
| Test files | 4 (3 E2E/integration + 1 manual) | 19 unit test files | +15 files |
| Test cases | 20 pytest + 5 manual | 213 unit tests | +188 tests |
| Coverage | ~15-20% | Target ~90% | +70% |

---

## 13. Quy Trình Tạo Report Sau Khi Chạy Unit Tests

### Bước 1: Chạy Tests & Thu Thập Kết Quả

```bash
# Chạy toàn bộ worker unit tests với verbose + JUnit XML output
cd 00_test && python -m pytest ocr_worker/ -v --tb=short --junitxml=ocr_worker/report.xml 2>&1 | tee ocr_worker/test_output.txt

# Chạy với coverage
python -m pytest ocr_worker/ -v --cov=../03_worker/app --cov-report=term-missing --cov-report=html:ocr_worker/htmlcov 2>&1 | tee ocr_worker/coverage_output.txt
```

### Bước 2: Phân Tích Kết Quả

Từ output, thu thập các metric:
1. **Total / Passed / Failed / Skipped** — từ pytest summary line
2. **Coverage %** — từ `--cov` output (line cuối)
3. **Failed test details** — từ `--tb=short` output
4. **Per-file breakdown** — đếm tests per file từ verbose output

### Bước 3: Viết Report

Tạo file report tại:
```
05_test_cases/worker/QA_UNIT_TEST_REPORT_WORKER_YYYY-MM-DD.md
```

Theo format đầy đủ dưới đây:

---

### Report Template

````markdown
# QA Worker Unit Test Report — YYYY-MM-DD

## 1. Summary

| Metric | Value |
|---|---|
| Total test cases | N |
| Passed | N |
| Failed | N |
| Skipped | N |
| Errors | N |
| Coverage (line) | X% |
| Coverage (branch) | X% |
| Execution time | Xs |
| Offline tests | N / N total |

## 2. Results by Component

| Component | File | Tests | Pass | Fail | Skip | Coverage |
|---|---|---|---|---|---|---|
| WorkerState | test_worker_state.py | 10 | 10 | 0 | 0 | 95% |
| GracefulShutdown | test_worker_shutdown.py | 5 | 5 | 0 | 0 | 100% |
| Error Classification | test_worker_errors.py | 15 | 15 | 0 | 0 | 100% |
| Settings/Config | test_worker_config.py | 8 | 8 | 0 | 0 | 90% |
| Cleanup Utility | test_worker_cleanup.py | 5 | 5 | 0 | 0 | 100% |
| PaddleOCR Preprocessing | test_engine_paddle_preprocessing.py | 5 | 5 | 0 | 0 | 95% |
| PaddleOCR Postprocessing | test_engine_paddle_postprocessing.py | 11 | 11 | 0 | 0 | 90% |
| Tesseract Preprocessing | test_engine_tesseract_preprocessing.py | 10 | 10 | 0 | 0 | 85% |
| Tesseract Postprocessing | test_engine_tesseract_postprocessing.py | 9 | 9 | 0 | 0 | 90% |
| Paddle-VL Preprocessing | test_engine_paddlevl_preprocessing.py | 8 | 8 | 0 | 0 | 95% |
| Paddle-VL Postprocessing | test_engine_paddlevl_postprocessing.py | 22 | 22 | 0 | 0 | 85% |
| FileProxyClient | test_worker_file_proxy.py | 12 | 12 | 0 | 0 | 90% |
| OrchestratorClient | test_worker_orchestrator.py | 12 | 12 | 0 | 0 | 90% |
| HeartbeatClient | test_worker_heartbeat.py | 13 | 13 | 0 | 0 | 85% |
| QueueClient | test_worker_queue_client.py | 11 | 11 | 0 | 0 | 80% |
| OCRProcessor | test_worker_processor.py | 11 | 11 | 0 | 0 | 90% |
| OCRWorker Lifecycle | test_worker_lifecycle.py | 11 | 11 | 0 | 0 | 85% |
| OCRWorker Job Processing | test_worker_job_processing.py | 21 | 21 | 0 | 0 | 90% |
| Engine Handlers | test_engine_handlers.py | 14 | 14 | 0 | 0 | 80% |
| **TỔNG** | **19 files** | **213** | **213** | **0** | **0** | **~90%** |

## 3. Failed Tests (nếu có)

| Test ID | File:Line | Expected | Actual | Root Cause | Severity |
|---|---|---|---|---|---|
| WJ-009 | test_worker_job_processing.py:80 | _handle_failure(retriable=True) | Not called | Bug: DownloadError not caught | HIGH |
| VO-003 | test_engine_paddlevl_postprocessing.py:42 | Fallback to text | KeyError | Bug: missing rec_res check | MEDIUM |

## 4. Bugs Found

| Bug ID | Severity | Component | Description | File:Line | Steps to Reproduce |
|---|---|---|---|---|---|
| WBUG-001 | HIGH | OCRWorker | DownloadError trong process_job không trigger _handle_failure với retriable=True | core/worker.py:135 | 1. Mock file_proxy.download raise DownloadError. 2. Call process_job(job). 3. Assert _handle_failure called |
| WBUG-002 | MEDIUM | Paddle-VL Post | extract_regions crash khi table result không có rec_res field | engines/paddle_vl/postprocessing.py:88 | 1. Call extract_regions với result thiếu rec_res. 2. Expect graceful fallback |

## 5. Test Cases Chưa Cover (Gaps)

| Test ID | Component | Reason | Priority |
|---|---|---|---|
| WJ-XXX | OCRWorker | Concurrent job processing chưa test | LOW |
| EH-XXX | StructuredExtractHandler | 4-level fallback với real PPStructure output | MEDIUM |

## 6. Coverage Analysis

### Per-Module Coverage:
```
Name                                        Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------
app/core/worker.py                           120     12    90%    135-140, 180-185
app/core/processor.py                         45      2    96%    38-39
app/core/state.py                             25      0   100%
app/core/shutdown.py                          15      0   100%
app/engines/paddle_text/handler.py            35      3    91%
app/engines/paddle_text/preprocessing.py      12      0   100%
app/engines/paddle_text/postprocessing.py     40      4    90%
app/engines/tesseract/handler.py              55      8    85%
app/engines/tesseract/preprocessing.py        30      4    87%
app/engines/tesseract/postprocessing.py       45      5    89%
app/engines/paddle_vl/handler.py              80     12    85%
app/engines/paddle_vl/preprocessing.py        25      1    96%
app/engines/paddle_vl/postprocessing.py       95     14    85%
app/clients/queue_client.py                   50     10    80%
app/clients/file_proxy_client.py              40      4    90%
app/clients/orchestrator_client.py            45      5    89%
app/clients/heartbeat_client.py               55      8    85%
app/utils/errors.py                           35      0   100%
app/config.py                                 30      3    90%
app/utils/cleanup.py                          15      0   100%
-------------------------------------------------------------------------
TOTAL                                        892     95    89%
```

### Uncovered Lines Analysis:
- `core/worker.py:135-140` — Exception handler branch khi orchestrator.update_status raise HTTPError 404 + 500
- `engines/paddle_vl/handler.py:95-106` — Deep fallback chain (OCR CPU path) — khó mock toàn bộ chain

## 7. So Sánh Với Baseline

| Metric | Before (baseline) | After | Delta |
|---|---|---|---|
| Total tests | 20 | 233 | +213 |
| Offline tests | 0 | 213 | +213 |
| Coverage | ~15% | ~89% | +74% |
| Components tested | 3/19 | 19/19 | +16 |
| Bugs found | 0 | N | +N |

## 8. Recommendations

### Immediate:
1. Fix BUG-001 (nếu tìm thấy): [mô tả fix]
2. Fix BUG-002 (nếu tìm thấy): [mô tả fix]

### Follow-up:
3. Thêm tests cho concurrent job processing scenarios
4. Thêm tests cho NATS reconnection logic
5. Thêm integration tests chạy real PaddleOCR cho Tesseract và Paddle-VL handlers (hiện chỉ có PaddleOCR text)
6. Set up CI pipeline chạy offline tests (Phase A+B+C+D) trên mỗi PR
7. Set coverage threshold ≥ 85% trong CI

### Test Debt:
- [ ] Concurrent processing tests (multi-job scenario)
- [ ] NATS reconnection / disconnect mid-processing
- [ ] File proxy timeout handling (long-running downloads)
- [ ] Large file processing (>50MB image)
````

### Bước 4: Cập Nhật Tracking

Sau khi viết report, **bắt buộc** cập nhật file tracking:

```
04_docs/06-OCR_update_progress/YYYY-MM-DD.md
```

Append entry mới:
```markdown
======

## time: HH:MM

### Mục tiêu
QA/QC: Chạy và report unit tests cho OCR Worker.

### Files thay đổi
- `00_test/ocr_worker/test_worker_*.py` — Unit tests cho worker components
- `00_test/ocr_worker/test_engine_*.py` — Unit tests cho engine pre/postprocessing
- `05_test_cases/worker/QA_UNIT_TEST_REPORT_WORKER_YYYY-MM-DD.md` — Test report

### Lý do
Verify toàn bộ worker logic trước khi chuyển Phase 2. Phát hiện N bugs, coverage đạt X%.
```

### Bước 5: Nếu Phát Hiện Bugs

Mỗi bug cần report riêng, KHÔNG sửa code production:

```markdown
# Bug Report: WBUG-NNN

**Severity:** CRITICAL / HIGH / MEDIUM / LOW
**Component:** [tên component]
**File:** [path/to/file.py:line]

## Description
[Mô tả ngắn gọn bug]

## Steps to Reproduce
1. ...
2. ...
3. ...

## Expected
[Kết quả mong đợi]

## Actual
[Kết quả thực tế]

## Test Case
[Test ID] trong [test file] — có thể chạy lại để verify fix

## Suggested Fix
[Gợi ý fix nếu rõ nguyên nhân, nhưng KHÔNG tự sửa code production]
```

Lưu bug report tại:
```
05_test_cases/worker/bugs/WBUG-NNN.md
```
