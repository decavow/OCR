# CLAUDE.md — Quy Tắc Cho Claude Code

> File này auto-loaded mỗi session. Giữ gọn. Chi tiết xem `04_docs/`.

---

## Quick Reference

```
C:\Projects\OCR\
├── 00_test/          # pytest + httpx async
├── 01_frontend/      # React + Vite + Tailwind + Shadcn/UI
├── 02_backend/       # FastAPI (Python 3.12, SQLite WAL, Pydantic)
│   └── app/
│       ├── api/v1/          # endpoints/ + internal/ + schemas/
│       ├── modules/         # auth, upload, job, file_proxy, health, cleanup
│       ├── infrastructure/  # database/ (repos), storage/ (MinIO), queue/ (NATS)
│       ├── core/            # middleware, lifespan, scheduler, logging, exceptions
│       └── config.py
├── 03_worker/        # OCR Workers (PaddleOCR, Tesseract)
├── 04_docs/          # Tài liệu dự án
│   ├── project-management/       # Quản trị dự án
│   │   ├── PROJECT_CONTEXT.md    # Architecture, tech stack, design decisions
│   │   └── DEVELOPMENT_WORKFLOW.md # Quy trình phát triển, checklist
│   ├── 06-OCR_update_progress/   # Tracking tiến độ theo ngày
│   └── 07-roadmap/               # Roadmap + implementation plan
├── docker-compose.yml
├── Makefile
└── .env              # KHÔNG commit
```

**Self-host only** | Session-based auth | 3-layer: MinIO → FastAPI → Workers (NATS)

---

## Coding Conventions

### Backend (Python)

**Controller → Service → Repository** (3 lớp bắt buộc):
```
api/v1/endpoints/   →  modules/*/service.py  →  infrastructure/database/repositories/
(validate, route)      (business logic)          (pure data access)
```

**Module pattern** — mỗi module trong `app/modules/`:
```
module_name/
├── __init__.py
├── service.py        # Business logic (bắt buộc)
├── exceptions.py     # Module-specific exceptions
└── validators.py     # Input validation (nếu cần)
```

**Repository pattern** — mỗi entity trong `app/infrastructure/database/repositories/`:
- Kế thừa `BaseRepository`
- Chỉ data access, không business logic
- Trả về model objects

**Quy tắc cụ thể:**
- Schemas: Pydantic models trong `api/v1/schemas/`
- Config mới: thêm vào `app/config.py` (Pydantic BaseSettings), không sửa `.env`
- DB migration: thêm ALTER statement vào `connection.py._run_migrations()`
- Async handlers cho tất cả endpoints
- Error: raise exception cụ thể, không return error dict

### Frontend (TypeScript)
- Components: `src/components/` theo feature folder
- API calls: `src/api/` (dùng axios client)
- Types: `src/types/`
- Hooks: `src/hooks/`
- Không thêm dependencies mới nếu không cần thiết

### Chung
- **Code:** English
- **Comments/Docs:** Vietnamese hoặc English
- **Commit messages:** English, ngắn gọn, mô tả "what + why"

---

## Instructions — Quy Tắc Bắt Buộc

### Khi implement module:
1. Đọc `04_docs/project-management/DEVELOPMENT_WORKFLOW.md` để biết quy trình
2. Đọc file liên quan trước khi sửa
3. Tuân theo pattern hiện có, không phát minh pattern mới
4. Viết test cho logic mới
5. Cập nhật tracking sau khi hoàn thành

### Khi thêm endpoint:
- Đặt trong `app/api/v1/endpoints/`, đăng ký trong `router.py`
- Endpoint gọi Service, không gọi Repository trực tiếp
- Validate input qua Pydantic schema

### Khi thêm database model/column:
- Model trong `app/infrastructure/database/models.py`
- Repository trong `app/infrastructure/database/repositories/`
- Migration trong `connection.py._run_migrations()`

### Tracking bắt buộc — sau MỌI thay đổi:

Sau khi hoàn thành bất kỳ thay đổi nào (fix bug, thêm feature, refactor, config...), **bắt buộc** ghi lại vào file tracking theo ngày:

```
04_docs/06-OCR_update_progress/YYYY-MM-DD.md
```

- Nếu file ngày hôm nay chưa tồn tại → tạo mới với header `date: YYYY-MM-DD`
- Nếu đã tồn tại → append thêm entry mới với `time: HH:MM` + `======`
- Mỗi entry ghi: **mục tiêu, files thay đổi, lý do** — đủ để người khác hiểu mà không cần đọc code
- Tham khảo format tại `04_docs/06-OCR_update_progress/Tracking_guideline.md`

### Những gì KHÔNG làm:
- Không sửa `.env` — chỉ sửa `config.py`
- Không thêm feature ngoài scope Phase hiện tại
- Không refactor code không liên quan đến task đang làm
- Không commit file nhạy cảm (.env, credentials, *.db)

---

## Phase 1 Status

**11 modules, 4 sprints** — Chi tiết: `04_docs/07-roadmap/phase1-implementation-plan.md`

| Sprint | Modules | Status |
|:---:|---|:---:|
| 1 | M1: StateMachine, M5: Scheduler, M7: Health, M9: RateLimit | DONE |
| 2 | M2: JobService, M3: Retry+DLQ, M6: StatusIntegration | DONE |
| 3 | M4: HeartbeatMonitor, M8: RetentionCleanup | DONE |
| 4 | M11: Frontend Error UX, M12: CI/CD | DONE |

**Tất cả stubs đã được implement đầy đủ (2026-03-07).**

---

## Key Documents

| Tài liệu | Path |
|---|---|
| Quy trình phát triển | `04_docs/project-management/DEVELOPMENT_WORKFLOW.md` |
| Architecture & Context | `04_docs/project-management/PROJECT_CONTEXT.md` |
| Phase 1 Plan (chi tiết) | `04_docs/07-roadmap/phase1-implementation-plan.md` |
| Roadmap tổng | `04_docs/07-roadmap/next-action.md` |
| Tracking tiến độ | `04_docs/06-OCR_update_progress/` |
