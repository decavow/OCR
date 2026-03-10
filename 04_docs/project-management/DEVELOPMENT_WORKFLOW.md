# DEVELOPMENT_WORKFLOW.md — Quy Trình Phát Triển

> Hướng dẫn thực hành cho Claude Code và developer.
> Tuân thủ quy trình này khi implement, test, và tracking tiến độ.

---

## 1. Module Development Lifecycle

Mỗi module đi qua 6 bước. **KHÔNG skip bước nào.**

```
[1] PREPARE  →  [2] IMPLEMENT  →  [3] TEST  →  [4] VERIFY  →  [5] TRACK  →  [6] DONE
```

### [1] PREPARE — Đọc hiểu trước khi code

- [ ] Đọc spec của module trong `phase1-implementation-plan.md`
- [ ] Đọc tất cả file liên quan (files sẽ sửa/tạo)
- [ ] Xác nhận dependencies đã hoàn thành (check Sprint dependency graph)
- [ ] Hiểu rõ acceptance criteria

### [2] IMPLEMENT — Code theo pattern

- [ ] Tuân theo pattern hiện có (xem `CLAUDE.md` → Coding Conventions)
- [ ] Endpoint → Service → Repository (không gọi repo từ endpoint)
- [ ] Tạo file mới theo module pattern (`service.py`, `exceptions.py`)
- [ ] Config mới thêm vào `config.py`, không sửa `.env`
- [ ] DB model/column mới thêm migration vào `connection.py._run_migrations()`

### [3] TEST — Viết test trước khi verify

- [ ] Test file đặt trong `00_test/backend/` hoặc `00_test/` tương ứng
- [ ] Dùng pytest + httpx AsyncClient cho API tests
- [ ] Cover happy path + edge cases + error cases
- [ ] Mock external dependencies (NATS, MinIO) nếu cần
- [ ] Chạy test pass local

### [4] VERIFY — Kiểm tra tích hợp

- [ ] Chạy full test suite: `python 00_test/run_all_tests.py`
- [ ] Verify không break existing tests
- [ ] Verify API contract không thay đổi (trừ khi có spec mới)
- [ ] Docker build thành công (nếu sửa Dockerfile/requirements)

### [5] TRACK — Cập nhật tiến độ

- [ ] Cập nhật `04_docs/06-OCR_update_progress/YYYY-MM-DD.md`
- [ ] Cập nhật status trong `phase1-implementation-plan.md` (Checklist Tổng Thể)
- [ ] Nếu phát hiện vấn đề mới → ghi vào tracking

### [6] DONE — Module hoàn thành khi

- [ ] Tất cả acceptance criteria đạt
- [ ] Tests pass
- [ ] Tracking đã cập nhật
- [ ] Không còn TODO/stub trong code của module

---

## 2. Quy Tắc Commit

### Format

```
<type>: <mô tả ngắn gọn>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### Types

| Type | Khi nào dùng |
|---|---|
| `feat` | Thêm tính năng mới |
| `fix` | Sửa bug |
| `refactor` | Tái cấu trúc code, không thay đổi behavior |
| `test` | Thêm/sửa test |
| `docs` | Cập nhật tài liệu |
| `chore` | Config, build, dependencies |

### Quy tắc

- Commit khi được yêu cầu, không tự ý commit
- Một commit = một module hoặc một nhóm thay đổi liên quan
- Không commit: `.env`, `*.db`, `__pycache__/`, `node_modules/`
- Không dùng `--amend` trừ khi được yêu cầu rõ ràng
- Không force push

### Ví dụ

```
feat: implement JobStateMachine.get_request_status()
feat: add APScheduler background task infrastructure
fix: real health check for DB, NATS, MinIO connections
refactor: move job logic from endpoints to JobService
test: add retry orchestrator unit tests
```

---

## 3. Quy Tắc Test

### Cấu trúc

```
00_test/
├── backend/
│   ├── conftest.py           # Shared fixtures
│   ├── test_state_machine.py # M1
│   ├── test_job_service.py   # M2
│   └── ...
├── infras/
│   ├── test_minio.py
│   ├── test_nats.py
│   └── test_database.py
├── ocr_worker/
│   └── ...
└── run_all_tests.py
```

### Naming convention

```python
# File: test_{module_name}.py
# Function: test_{method}_{scenario}_{expected_result}

def test_get_request_status_all_completed_returns_completed():
    ...

def test_get_request_status_mixed_returns_partial_success():
    ...

def test_handle_failure_retriable_requeues_job():
    ...

def test_handle_failure_max_retries_moves_to_dlq():
    ...
```

### Fixtures

```python
# Dùng conftest.py cho shared fixtures
# Mock NATS, MinIO khi test unit
# Dùng real DB (in-memory SQLite) cho integration tests
```

### Chạy test

```bash
# Tất cả tests
python 00_test/run_all_tests.py

# Một module
pytest 00_test/backend/test_state_machine.py -v

# Một test cụ thể
pytest 00_test/backend/test_state_machine.py::test_get_request_status_all_completed -v
```

---

## 4. Progress Tracking

### Khi nào cập nhật

| Sự kiện | Cập nhật ở đâu |
|---|---|
| Bắt đầu module | Tracking file: `NOT STARTED → IN PROGRESS` |
| Hoàn thành module | Tracking file: `IN PROGRESS → DONE` + chi tiết |
| Phát hiện vấn đề | Tracking file: ghi bug/blocker |
| Hoàn thành sprint | Tracking file: tổng kết sprint |
| Quyết định kiến trúc mới | `PROJECT_CONTEXT.md` → ADR table |

### Format tracking file

File: `04_docs/06-OCR_update_progress/YYYY-MM-DD.md`

```markdown
date: YYYY-MM-DD
time: HH:MM
======

**[MODULE_ID] STATUS — Tên module**

Thay đổi:
- File A: mô tả thay đổi
- File B: mô tả thay đổi

Test: pass/fail (X tests)
Ghi chú: (nếu có)
```

### Ví dụ

```markdown
date: 2026-03-10
time: 14:00
======

**[M1] DONE — JobStateMachine.get_request_status()**

Thay đổi:
- `02_backend/app/modules/job/state_machine.py`: Implement get_request_status()
  - 7 rules: empty, all completed, all failed, all cancelled, mixed, processing, partial

Test: pass (8 tests)
- `00_test/backend/test_state_machine.py`: 8 test cases covering all status combinations

Acceptance criteria: ALL MET
```

### Quy tắc đánh status

| Status | Ý nghĩa | Điều kiện |
|---|---|---|
| `NOT STARTED` | Chưa bắt đầu | Chưa có code nào |
| `IN PROGRESS` | Đang làm | Có code nhưng chưa xong |
| `DONE` | Hoàn thành | Code xong + tests pass + acceptance met |
| `BLOCKED` | Bị chặn | Ghi rõ blocker |
| `OUT OF SCOPE` | Loại khỏi scope | Ghi lý do |

---

## 5. Sprint Workflow

### Bắt đầu Sprint

1. Xác nhận dependencies của sprint trước đã DONE
2. Đọc lại scope các modules trong sprint
3. Với sprint có modules song song: implement theo thứ tự dễ → khó

### Trong Sprint

1. Implement từng module hoàn chỉnh trước khi chuyển module tiếp
2. Không implement nhiều module cùng lúc (trừ khi hoàn toàn độc lập)
3. Nếu bị block → ghi tracking → chuyển module khác (nếu có thể)

### Kết thúc Sprint

1. Tất cả modules DONE
2. Full test suite pass
3. Tracking file tổng kết sprint
4. Review: có vấn đề gì cần carry over?

---

## 6. Quy Trình Khi Có Thay Đổi Scope

Khi nhận thông tin mới từ user (thay đổi yêu cầu, thêm/bớt module):

1. Cập nhật `phase1-implementation-plan.md`
2. Cập nhật `CLAUDE.md` (Phase 1 Status table)
3. Cập nhật `project-management/PROJECT_CONTEXT.md` nếu ảnh hưởng kiến trúc (thêm ADR)
4. Ghi lại trong tracking file
5. KHÔNG cập nhật trùng lặp ở nhiều file — mỗi thông tin chỉ ở MỘT nơi chính

### Nguyên tắc Single Source of Truth

| Thông tin | File chính | Các file khác chỉ THAM CHIẾU |
|---|---|---|
| Coding rules & instructions | `CLAUDE.md` | — |
| Architecture & design decisions | `04_docs/project-management/PROJECT_CONTEXT.md` | CLAUDE.md tóm tắt |
| Phase plan & module details | `04_docs/07-roadmap/phase1-implementation-plan.md` | CLAUDE.md summary table |
| Daily progress | `04_docs/06-OCR_update_progress/YYYY-MM-DD.md` | — |
| Development workflow | `04_docs/project-management/DEVELOPMENT_WORKFLOW.md` | CLAUDE.md tham chiếu |

---

## 7. File Governance Map

```
CLAUDE.md (root, auto-loaded)
├── Coding conventions (SOURCE OF TRUTH)
├── Instructions for Claude Code (SOURCE OF TRUTH)
├── Phase status summary (REFERENCES → plan)
└── Quick reference links

04_docs/project-management/PROJECT_CONTEXT.md
├── Architecture (SOURCE OF TRUTH)
├── Tech stack (SOURCE OF TRUTH)
├── DB schema reference (SOURCE OF TRUTH)
├── API reference (SOURCE OF TRUTH)
├── ADR log (SOURCE OF TRUTH)
└── Market context (SOURCE OF TRUTH)

04_docs/project-management/DEVELOPMENT_WORKFLOW.md (this file)
├── Module lifecycle checklist (SOURCE OF TRUTH)
├── Commit rules (SOURCE OF TRUTH)
├── Test rules (SOURCE OF TRUTH)
├── Tracking rules (SOURCE OF TRUTH)
└── Sprint workflow (SOURCE OF TRUTH)

04_docs/07-roadmap/phase1-implementation-plan.md
├── Module specs & file details (SOURCE OF TRUTH)
├── Dependency graph (SOURCE OF TRUTH)
└── Overall checklist (SOURCE OF TRUTH)

04_docs/06-OCR_update_progress/YYYY-MM-DD.md
└── Daily progress entries (SOURCE OF TRUTH)
```

---

*Cập nhật lần cuối: 2026-03-07*
