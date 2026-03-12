# Prompt: Viết Unit Test cho OCR/IDP Platform

Bạn là một Kỹ sư QA chuyên nghiệp. Nhiệm vụ: viết unit test toàn diện, ổn định, **chạy được ngay** cho đoạn mã được cung cấp trong dự án OCR/IDP Platform.

---

## 1. Ngữ cảnh Dự án

**Kiến trúc:** Self-hosted IDP Platform, 3-layer (MinIO → FastAPI → Workers via NATS JetStream)

**Pattern bắt buộc:** Controller → Service → Repository (3 lớp)

```
api/v1/endpoints/   →  modules/*/service.py  →  infrastructure/database/repositories/
(validate, route)      (business logic)          (pure data access)
```

### Tech Stack

| Layer | Ngôn ngữ | Framework | Testing |
|---|---|---|---|
| Backend | Python 3.12 (async/await) | FastAPI + Pydantic v2 + SQLAlchemy | pytest + pytest-asyncio + httpx |
| Frontend | TypeScript 5.3 | React 18 + Vite 5 | Vitest + React Testing Library |
| Worker | Python 3.12 | NATS client + OCR engines | pytest + custom async runners |

### Thư mục

```
00_test/
├── backend/             # Unit + Integration tests cho backend
│   ├── conftest.py      # Shared fixtures (client, auth, sample files)
│   └── test_*.py
├── infras/              # Infrastructure tests (MinIO, NATS, SQLite)
└── ocr_worker/          # Worker tests
    ├── conftest.py
    └── test_*.py
```

---

## 2. QUY TẮC QUAN TRỌNG — Module Loading

### ⚠️ KHÔNG BAO GIỜ import trực tiếp từ app

```python
# ❌ SAI — sẽ trigger app initialization, circular imports, crash
from app.modules.job.service import JobService

# ✅ ĐÚNG — load module isolated qua importlib
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "job_service",
    Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "service.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
JobService = mod.JobService
```

### Tại sao?

Services import từ `app.config`, `app.core.logging`, `app.infrastructure.*`. Import trực tiếp sẽ trigger toàn bộ app initialization (DB connections, NATS, MinIO). Unit test cần load module **trong môi trường đã mock sẵn dependencies**.

---

## 3. Cấu trúc File Test — Template Đầy Đủ

```python
"""
Tests for <module_name>.
Covers: <liệt kê các method/feature được test>
"""
import pytest
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from types import SimpleNamespace
from datetime import datetime


# =====================================================
# MODULE LOADING — Load source module với mocked deps
# =====================================================

# Bước 1: Load các module PURE LOGIC (không mock) nếu cần
# VD: state_machine, subjects — chứa logic thật cần cho assertions
_pure_module_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "state_machine.py"
_spec_pure = importlib.util.spec_from_file_location("state_machine", _pure_module_path)
_state_machine_mod = importlib.util.module_from_spec(_spec_pure)
_spec_pure.loader.exec_module(_state_machine_mod)

# Bước 2: Fixture load service class với mocked dependencies
@pytest.fixture
def service_class():
    logger_mock = MagicMock()
    settings_mock = MagicMock()
    # Chỉ mock các settings mà service THỰC SỰ dùng
    settings_mock.minio_bucket_results = "results"
    settings_mock.max_job_retries = 3

    mocked_modules = {
        # LUÔN mock các layer infrastructure
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        # KHÔNG mock pure logic — dùng module thật
        "app.modules.job.state_machine": _state_machine_mod,
    }
    with patch.dict("sys.modules", mocked_modules):
        svc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "<module>" / "service.py"
        spec = importlib.util.spec_from_file_location("<module>_service", svc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.ServiceClass


# =====================================================
# FACTORY HELPERS — Tạo mock objects
# =====================================================

def make_request(request_id="req-1", user_id="user-1", status="PROCESSING", **overrides):
    """Factory tạo mock Request object."""
    defaults = dict(
        id=request_id, user_id=user_id, status=status,
        total_files=3, completed_files=0, failed_files=0,
        deleted_at=None,  # Soft delete — None = active
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_job(job_id="job-1", request_id="req-1", status="PENDING", **overrides):
    """Factory tạo mock Job object."""
    defaults = dict(
        id=job_id, request_id=request_id, status=status,
        method="ocr_text_raw", tier=0, retry_count=0,
        worker_id=None, deleted_at=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# =====================================================
# TEST CLASSES — Mỗi class test 1 method/feature
# =====================================================

class TestGetRequest:
    """Tests for ServiceClass.get_request() — lấy request theo ownership."""

    @pytest.mark.asyncio
    async def test_returns_owned_request(self, service_class):
        # Arrange
        svc = service_class(db=MagicMock())
        req = make_request(user_id="user-1")
        svc.request_repo.get_active = MagicMock(return_value=req)

        # Act
        result = await svc.get_request("req-1", "user-1")

        # Assert
        assert result is not None
        assert result.user_id == "user-1"
        svc.request_repo.get_active.assert_called_once_with("req-1")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, service_class):
        # Arrange
        svc = service_class(db=MagicMock())
        svc.request_repo.get_active = MagicMock(return_value=None)

        # Act
        result = await svc.get_request("nonexistent", "user-1")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_owner(self, service_class):
        # Arrange
        svc = service_class(db=MagicMock())
        req = make_request(user_id="other-user")
        svc.request_repo.get_active = MagicMock(return_value=req)

        # Act
        result = await svc.get_request("req-1", "user-1")

        # Assert
        assert result is None
```

---

## 4. Mock Patterns — Cheat Sheet

### Pattern A: Service Layer (mock repos trên instance)

```python
# Services tạo repos trong __init__:
#   self.job_repo = JobRepository(db)
#   self.request_repo = RequestRepository(db)
# → Tạo service, rồi mock TRỰC TIẾP trên instance

svc = ServiceClass(db=MagicMock())
svc.request_repo.get_active = MagicMock(return_value=mock_request)
svc.job_repo.update_status = MagicMock(return_value=updated_job)

# ❌ SAI — patch class-level không hoạt động vì service đã tạo instance
# with patch("app.infrastructure.database.repositories.RequestRepository.get_active"):
```

### Pattern B: Async vs Sync

```python
# Repository methods là SYNC (không cần await)
svc.job_repo.get_active = MagicMock(return_value=job)

# Queue/Network methods là ASYNC (cần AsyncMock)
svc.queue = MagicMock()
svc.queue.publish = AsyncMock()

# ❌ SAI — dùng MagicMock cho async method
# svc.queue.publish = MagicMock()  # → TypeError: can't be used in 'await'
```

### Pattern C: PropertyMock cho @property

```python
# queue.is_connected là @property, không phải method
queue = MagicMock()
type(queue).is_connected = PropertyMock(return_value=True)

# ❌ SAI — set trực tiếp không hoạt động cho property
# queue.is_connected = True  # → Không raise AttributeError nhưng mock sai
```

### Pattern D: Infrastructure mocks (Health checks)

```python
def make_db_mock(healthy=True):
    db = MagicMock()
    if not healthy:
        db.execute.side_effect = Exception("DB connection failed")
    return db

def make_storage_mock(healthy=True):
    storage = MagicMock()
    if healthy:
        storage.client.list_buckets.return_value = [MagicMock()]
    else:
        storage.client.list_buckets.side_effect = Exception("MinIO down")
    return storage

def make_queue_mock(healthy=True):
    queue = MagicMock()
    type(queue).is_connected = PropertyMock(return_value=healthy)
    return queue
```

### Pattern E: API Integration Test (dùng conftest fixtures)

```python
class TestEndpoint:
    @pytest.mark.asyncio
    async def test_success(self, client, auth_headers):
        resp = await client.get("/api/v1/resource", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "expected_field" in data

    @pytest.mark.asyncio
    async def test_unauthorized_without_token(self, client):
        resp = await client.get("/api/v1/resource")
        assert resp.status_code == 401
```

---

## 5. Domain Knowledge — Cần biết khi viết test

### Soft Delete

Tất cả models dùng `deleted_at` field. Record active khi `deleted_at IS NULL`.

```python
# Repository luôn filter: .filter(Model.deleted_at.is_(None))
# → Test phải set deleted_at=None cho active records
make_request(deleted_at=None)       # Active
make_request(deleted_at=datetime.now())  # Soft-deleted
```

### State Machine

Job status transitions có quy tắc. Chỉ một số transitions hợp lệ:

```
PENDING → PROCESSING → COMPLETED
                     → FAILED → RETRYING → PROCESSING
                              → DLQ
```

`JobStateMachine` là **pure logic** — luôn import thật, KHÔNG mock:

```python
# get_request_status(jobs) — aggregate status từ list jobs
# validate_transition(current, target) — check transition hợp lệ
# is_terminal(status) — check COMPLETED/FAILED/DLQ
```

### NATS Subject Routing

```python
# Format: "ocr.{method}.tier{tier}"
# VD: "ocr.ocr_text_raw.tier0"
# DLQ: "dlq.ocr_text_raw.tier0"

# Assertion example:
queue.publish.assert_called_once()
call_args = queue.publish.call_args
assert call_args[0][0] == "ocr.ocr_text_raw.tier0"
```

### Settings (Pydantic BaseSettings)

```python
# Trong code: settings.minio_bucket_results (snake_case)
# Trong .env: MINIO_BUCKET_RESULTS (UPPER_CASE)
# Test: chỉ mock attributes mà service THỰC SỰ đọc
settings_mock = MagicMock()
settings_mock.minio_bucket_results = "results"
settings_mock.max_job_retries = 3
settings_mock.session_expire_hours = 24
```

### Service Constructor

```python
# Services tạo repos trong __init__ — pattern cố định:
class JobService:
    def __init__(self, db, queue=None):
        self.db = db
        self.queue = queue                          # Optional
        self.job_repo = JobRepository(db)           # Auto-created
        self.request_repo = RequestRepository(db)   # Auto-created
        self.file_repo = FileRepository(db)         # Auto-created

# → Sau khi tạo service, mock trên instance:
svc = JobService(db=MagicMock())
svc.job_repo.get_active = MagicMock(return_value=job)
```

---

## 6. Modules Đã/Chưa Có Test

### Đã có test (tham khảo pattern)

| File test | Module | Loại |
|---|---|---|
| `test_auth.py` | auth | API integration |
| `test_upload.py` | upload | API integration |
| `test_job_service.py` | job/service | Unit (mock repos) |
| `test_state_machine.py` | job/state_machine | Unit (pure logic) |
| `test_retry_orchestrator.py` | job/orchestrator | Unit (mock queue) |
| `test_heartbeat_monitor.py` | job/heartbeat | Unit (mock repos) |
| `test_health_service.py` | health | Unit (mock infra) |
| `test_rate_limiter.py` | rate_limit | Unit |
| `test_retention_cleanup.py` | cleanup | Unit |
| `test_file_proxy.py` | file_proxy | API integration |

### Chưa có / cần bổ sung

- `modules/upload/service.py` — upload processing logic
- `modules/cleanup/service.py` — retention + scheduler interaction
- `modules/auth/service.py` — session management logic
- `api/v1/endpoints/*.py` — endpoint-level tests cho các route mới
- `infrastructure/queue/client.py` — NATS client unit test
- `infrastructure/storage/client.py` — MinIO client unit test
- `core/middleware.py` — request middleware tests

---

## 7. Quy tắc Chất lượng

### Kịch bản bắt buộc cho MỖI hàm/method

| Loại | Mô tả | Ví dụ |
|---|---|---|
| **Happy path** | Input hợp lệ → output đúng | Tạo request thành công |
| **Edge cases** | Giá trị biên, rỗng, None | List jobs rỗng, ID không tồn tại |
| **Error handling** | Exception đúng loại | `ValueError`, `PermissionError` |
| **State transitions** | Nếu liên quan state machine | PENDING → PROCESSING hợp lệ |
| **Side effects** | Mock method được gọi đúng | `repo.update.assert_called_once()` |

### Assertions checklist

```python
# 1. Return value
assert result.status == "COMPLETED"
assert result is not None

# 2. Side effects
svc.repo.update.assert_called_once_with(expected_id, expected_data)
svc.repo.delete.assert_not_called()

# 3. Call arguments (khi cần check chi tiết)
call_args = svc.queue.publish.call_args
assert call_args[0][0] == "ocr.ocr_text_raw.tier0"  # subject
assert call_args[0][1]["job_id"] == "job-1"           # message body

# 4. Exceptions
with pytest.raises(ValueError, match="Invalid input"):
    await svc.process(bad_input)

# 5. HTTP status (integration tests)
assert resp.status_code == 200
assert resp.status_code == 401  # Unauthorized
assert resp.status_code == 404  # Not found
```

### Tính ổn định

- **KHÔNG** phụ thuộc thời gian thực → dùng `datetime(2026, 1, 1)` cố định trong factories
- **KHÔNG** phụ thuộc file system, network, database thật
- **KHÔNG** phụ thuộc thứ tự chạy giữa các test
- **KHÔNG** dùng `sleep()` trong test
- **KHÔNG** assert trên logging calls (trừ khi test logging cụ thể)
- Mỗi test tự setup và cleanup dữ liệu của mình

---

## 8. Đặt Tên

- **File:** `test_<module>.py`
- **Class:** `Test<Feature>` — mỗi class test 1 method hoặc 1 feature
- **Method:** `test_<hành_vi>_<điều_kiện>` — mô tả đủ để hiểu khi fail

```
test_get_request_returns_owned_request
test_get_request_returns_none_when_not_found
test_get_request_returns_none_when_not_owner
test_cancel_request_sets_status_cancelled
test_cancel_request_raises_when_already_terminal
test_update_job_status_triggers_request_recalculation
test_all_completed_returns_completed_status
test_mixed_statuses_returns_processing
```

---

## 9. Cách Chạy Test

```bash
# Chạy tất cả backend tests
cd 00_test && python -m pytest backend/ -v

# Chạy một file cụ thể
python -m pytest 00_test/backend/test_job_service.py -v

# Chạy một class cụ thể
python -m pytest 00_test/backend/test_job_service.py::TestGetRequest -v

# Chạy một test cụ thể
python -m pytest 00_test/backend/test_job_service.py::TestGetRequest::test_returns_owned_request -v

# Chạy với coverage
python -m pytest 00_test/backend/ --cov=02_backend/app --cov-report=term-missing

# Chạy qua custom runner (báo cáo đẹp hơn)
cd 00_test/backend && python run_tests.py
cd 00_test/backend && python run_tests.py auth     # Chỉ auth tests
cd 00_test/backend && python run_tests.py job      # Chỉ job tests
```

---

## 10. Conftest Fixtures Có Sẵn

Các fixtures sau đã define trong `00_test/backend/conftest.py`, dùng được trong mọi test file:

| Fixture | Scope | Mô tả |
|---|---|---|
| `event_loop` | session | Event loop dùng chung cho tất cả async tests |
| `client` | session | `httpx.AsyncClient` kết nối tới backend (cần server đang chạy) |
| `auth_headers` | session | Dict `{"Authorization": "Bearer <token>"}` — tự register user mới |
| `sample_png` | session | Bytes của file PNG hợp lệ tối thiểu |
| `sample_pdf` | session | Bytes của file PDF hợp lệ tối thiểu |

> **Lưu ý:** `client` và `auth_headers` chỉ dùng cho **integration tests** (cần backend server chạy). Unit tests **không dùng** — tự tạo service instance với mock db.

---

## 11. Đoạn Mã Cần Viết Test

```
<Dán code vào đây — bao gồm cả file path để biết vị trí trong project>
```

---

## 12. Output Mong Đợi

Trả về **một file test hoàn chỉnh** bao gồm:

1. Docstring mô tả module đang test
2. Imports đầy đủ (importlib, pytest, mock, SimpleNamespace, ...)
3. Module loading fixture với `sys.modules` patching
4. Factory helpers (`make_*`) cho mọi entity liên quan
5. Test classes tổ chức theo method/feature
6. Bao phủ: happy path + edge cases + error handling + side effects
7. Đảm bảo chạy được với: `python -m pytest <file> -v`

**File đặt tại:** `00_test/backend/test_<module_name>.py`
