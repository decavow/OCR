# 04 — Governance: Audit, Rate Limiting, Quotas & Retention

> Các cơ chế governance để kiểm soát ai làm gì, giới hạn sử dụng, và quản lý vòng đời dữ liệu.

---

## PART 1: AUDIT LOGGING

### 1.1. Mục tiêu

Ghi lại **ai đã làm gì, khi nào, từ đâu** cho mọi hành động quan trọng trong hệ thống. Phục vụ:
- Security investigation (ai login fail? ai approve service?)
- Compliance (lịch sử thao tác admin)
- Debugging (user report lỗi → trace lại hành động)

### 1.2. Data Model

```python
# File: 02_backend/app/infrastructure/database/models.py (thêm)

class AuditLog(Base):
    """Audit log for tracking security and administrative actions."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    actor_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )  # user.id hoặc None cho system actions
    actor_email: Mapped[str] = mapped_column(
        String(255)
    )  # email hoặc "system"
    action: Mapped[str] = mapped_column(
        String(50)
    )  # e.g. "auth.login", "service.approve"
    resource_type: Mapped[str] = mapped_column(
        String(50)
    )  # e.g. "user", "service_type", "job"
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # ID của resource bị tác động
    details: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON chi tiết bổ sung
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )  # IPv4 hoặc IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )  # Link tới trace
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
```

### 1.3. Audit Actions

#### 1.3.1. Authentication actions

| Action | Resource Type | Khi nào | Details |
|--------|--------------|---------|---------|
| `auth.register` | `user` | User đăng ký thành công | `{"email": "..."}` |
| `auth.login` | `session` | Login thành công | `{"email": "..."}` |
| `auth.login_failed` | `session` | Login thất bại | `{"email": "...", "reason": "invalid_password"}` |
| `auth.logout` | `session` | Logout | `{"email": "..."}` |

#### 1.3.2. Admin - Service governance

| Action | Resource Type | Khi nào | Details |
|--------|--------------|---------|---------|
| `service.approve` | `service_type` | Admin approve service type | `{"type_id": "...", "access_key_generated": true}` |
| `service.reject` | `service_type` | Admin reject service type | `{"type_id": "...", "reason": "..."}` |
| `service.disable` | `service_type` | Admin disable service type | `{"type_id": "...", "active_instances": 3}` |
| `service.enable` | `service_type` | Admin enable service type | `{"type_id": "..."}` |
| `service.delete` | `service_type` | Admin xóa service type | `{"type_id": "...", "instances_removed": 2}` |

#### 1.3.3. User actions

| Action | Resource Type | Khi nào | Details |
|--------|--------------|---------|---------|
| `upload.create` | `request` | Upload batch thành công | `{"request_id": "...", "file_count": 5, "method": "text_raw"}` |
| `request.delete` | `request` | User xóa request | `{"request_id": "..."}` |

#### 1.3.4. System actions

| Action | Resource Type | Khi nào | Details |
|--------|--------------|---------|---------|
| `job.completed` | `job` | Job hoàn thành | `{"job_id": "...", "processing_time_ms": 3500}` |
| `job.failed` | `job` | Job fail terminal | `{"job_id": "...", "error": "...", "retry_count": 3}` |
| `retention.cleanup` | `request` | Retention enforcement xóa data | `{"requests_cleaned": 5, "files_moved": 12}` |

### 1.4. Audit Helper

```python
# File mới: 02_backend/app/core/audit.py

import json
from fastapi import Request
from sqlalchemy.orm import Session
from app.infrastructure.database.models import User, AuditLog
from app.core.context import get_trace_id

def audit(
    db: Session,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str = None,
    details: dict = None,
    request: Request = None,
):
    """
    Log an audit event.

    Gọi explicit sau khi action thành công.
    KHÔNG dùng middleware vì middleware log cả actions thất bại.
    """
    ip = None
    user_agent = None
    if request:
        ip = request.client.host if request.client else None
        user_agent = (request.headers.get("User-Agent") or "")[:500]

    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else "system",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details) if details else None,
        ip_address=ip,
        user_agent=user_agent,
        trace_id=get_trace_id() or None,
    )
    db.add(entry)
    db.commit()
```

**Tại sao explicit calls thay vì middleware/decorator?**

| Approach | Ưu điểm | Nhược điểm |
|----------|---------|-----------|
| Middleware (auto) | Không quên log | Log cả actions thất bại, không biết action semantics |
| Decorator | Gọn hơn explicit | Khó truyền details, khó biết action thành công hay chưa |
| **Explicit (chọn)** | Chính xác, có context | Phải gọi thủ công (dễ quên) |

**Kết luận:** Explicit calls đặt **sau khi action thành công** cho audit entries chính xác và có ngữ nghĩa.

### 1.5. Audit integration points

```python
# === auth.py ===

# Login thành công
auth_attempts_total.labels(result="success").inc()
audit(db, user, "auth.login", "session", request=request)

# Login thất bại
auth_attempts_total.labels(result="failure").inc()
audit(db, None, "auth.login_failed", "session",
      details={"email": body.email, "reason": "invalid_credentials"},
      request=request)

# === admin/service_types.py ===

# Approve
audit(db, admin, "service.approve", "service_type",
      resource_id=type_id,
      details={"access_key_generated": True},
      request=request)

# === upload.py ===

# Upload thành công
audit(db, user, "upload.create", "request",
      resource_id=request_record.id,
      details={"file_count": len(files), "method": method, "tier": tier},
      request=request)
```

### 1.6. Admin Audit API

```python
# File mới: 02_backend/app/api/v1/endpoints/admin/audit.py

@router.get("")
async def query_audit_logs(
    actor_id: str = Query(None),
    action: str = Query(None),
    resource_type: str = Query(None),
    from_date: str = Query(None),      # ISO format
    to_date: str = Query(None),        # ISO format
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Query audit logs with filters.
    Only accessible by admin users.

    Examples:
    - GET /admin/audit?action=auth.login_failed&page_size=100
    - GET /admin/audit?actor_id=usr-123&from_date=2026-02-01
    - GET /admin/audit?resource_type=service_type
    """
```

**Response schema:**
```json
{
  "items": [
    {
      "id": 42,
      "actor_id": "usr-abc123",
      "actor_email": "admin@example.com",
      "action": "service.approve",
      "resource_type": "service_type",
      "resource_id": "ocr-text-tier0",
      "details": {"access_key_generated": true},
      "ip_address": "192.168.1.10",
      "trace_id": "a1b2c3d4-...",
      "created_at": "2026-02-16T10:30:00Z"
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 50
}
```

---

## PART 2: RATE LIMITING

### 2.1. Mục tiêu

Bảo vệ hệ thống khỏi:
- Brute-force login attempts
- Upload abuse (spam uploads)
- API abuse (excessive polling)

### 2.2. Approach: slowapi (in-memory)

```python
# File mới: 02_backend/app/core/rate_limit.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def get_user_identifier(request):
    """
    Identify user for rate limiting.
    Authenticated → use token prefix (per-user limit)
    Anonymous → use IP address (per-IP limit)
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"user:{auth[7:][:16]}"
    return get_remote_address(request)

limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["100/minute"],     # Global default
    storage_uri="memory://",           # In-memory (single instance)
)

def setup_rate_limit(app):
    """Register rate limiter with FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,
    )
```

### 2.3. Rate limit rules

| Endpoint | Limit | Lý do |
|----------|-------|-------|
| `POST /auth/login` | 10/minute | Chống brute-force |
| `POST /auth/register` | 5/minute | Chống spam account |
| `POST /upload` | 30/minute | Chống upload abuse |
| `GET /requests` | 60/minute | Chống excessive polling |
| Global default | 100/minute | Baseline protection |

### 2.4. Integration

```python
# File: 02_backend/app/api/v1/endpoints/auth.py

from app.core.rate_limit import limiter

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, ...):
    ...

@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, ...):
    ...
```

```python
# File: 02_backend/app/api/v1/endpoints/upload.py

@router.post("")
@limiter.limit("30/minute")
async def upload_files(request: Request, ...):
    ...
```

### 2.5. Response khi bị rate limited

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
Content-Type: application/json

{
  "error": "Rate limit exceeded: 10 per 1 minute"
}
```

### 2.6. Metric tracking

```python
# Khi rate limit triggered, increment counter:
from app.core.metrics import rate_limit_hits_total
rate_limit_hits_total.labels(endpoint="/auth/login").inc()
```

### 2.7. Migration path sang Redis

Khi scale lên multi-backend instance:
```python
# Chỉ cần đổi storage_uri:
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["100/minute"],
    storage_uri="redis://redis:6379",   # ← Chỉ thay dòng này
)
```

---

## PART 3: USER QUOTAS

### 3.1. Mục tiêu

Giới hạn **resource usage** per user:
- Bao nhiêu uploads/ngày
- Bao nhiêu jobs/tháng
- File size tối đa
- Batch size tối đa

**Khác với rate limiting:**
- Rate limiting = requests/time (bảo vệ API)
- Quota = total usage/period (bảo vệ resources)

### 3.2. Data Model

```python
# File: 02_backend/app/infrastructure/database/models.py (thêm)

class UserQuota(Base):
    """Per-user resource quota limits."""
    __tablename__ = "user_quotas"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    daily_upload_limit: Mapped[int] = mapped_column(
        Integer, default=50
    )  # Upload batches per day
    monthly_job_limit: Mapped[int] = mapped_column(
        Integer, default=1000
    )  # Total jobs per month
    max_file_size_mb: Mapped[int] = mapped_column(
        Integer, default=10
    )  # Max single file size (MB)
    max_batch_size: Mapped[int] = mapped_column(
        Integer, default=20
    )  # Max files per batch
    max_retention_hours: Mapped[int] = mapped_column(
        Integer, default=720
    )  # Max retention (30 days)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ix_user_quotas_user_id", "user_id"),
    )
```

### 3.3. Default quotas

Khi user chưa có record trong `user_quotas`:

```python
DEFAULT_QUOTAS = {
    "daily_upload_limit": 50,      # 50 batches/day
    "monthly_job_limit": 1000,     # 1000 jobs/month
    "max_file_size_mb": 10,        # 10 MB per file
    "max_batch_size": 20,          # 20 files per batch
    "max_retention_hours": 720,    # 30 days
}
```

### 3.4. Quota enforcement

```python
# File mới: 02_backend/app/modules/upload/quota.py

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.infrastructure.database.models import UserQuota, Request
from app.core.metrics import quota_exceeded_total

class QuotaExceeded(Exception):
    def __init__(self, message: str, reason: str):
        self.message = message
        self.reason = reason
        super().__init__(message)

def check_quota(
    db: Session,
    user_id: str,
    file_count: int,
    file_sizes: list[int],
):
    """
    Check if upload would exceed user quota.
    Raises QuotaExceeded if any limit is exceeded.
    Call this BEFORE processing the upload.
    """
    quota = db.query(UserQuota).filter(
        UserQuota.user_id == user_id
    ).first()

    # Use defaults if no quota record
    daily_limit = quota.daily_upload_limit if quota else DEFAULT_QUOTAS["daily_upload_limit"]
    max_file_mb = quota.max_file_size_mb if quota else DEFAULT_QUOTAS["max_file_size_mb"]
    max_batch = quota.max_batch_size if quota else DEFAULT_QUOTAS["max_batch_size"]

    # 1. Batch size check
    if file_count > max_batch:
        quota_exceeded_total.labels(reason="batch_size").inc()
        raise QuotaExceeded(
            f"Batch size {file_count} exceeds limit of {max_batch}",
            reason="batch_size",
        )

    # 2. Individual file size check
    max_bytes = max_file_mb * 1024 * 1024
    for size in file_sizes:
        if size > max_bytes:
            quota_exceeded_total.labels(reason="file_size").inc()
            raise QuotaExceeded(
                f"File size {size} bytes exceeds limit of {max_file_mb}MB",
                reason="file_size",
            )

    # 3. Daily upload count check
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_count = db.query(Request).filter(
        Request.user_id == user_id,
        Request.created_at >= today_start,
        Request.deleted_at.is_(None),
    ).count()

    if today_count + 1 > daily_limit:
        quota_exceeded_total.labels(reason="daily_limit").inc()
        raise QuotaExceeded(
            f"Daily upload limit of {daily_limit} exceeded ({today_count} used today)",
            reason="daily_limit",
        )
```

### 3.5. Integration vào upload service

```python
# File: 02_backend/app/modules/upload/service.py (modify)

from app.modules.upload.quota import check_quota, QuotaExceeded

async def process_upload(self, user_id, files, method, tier, ...):
    # Step 1: Validate files (existing)
    validated_files = self._validate_files(files)

    # Step 2: Check quota (NEW)
    file_sizes = [f.size_bytes for f in validated_files]
    check_quota(self.db, user_id, len(validated_files), file_sizes)

    # Step 3: Create records (existing)
    ...
```

### 3.6. Admin quota management

```python
# File mới: 02_backend/app/api/v1/endpoints/admin/quotas.py

@router.get("/{user_id}")
async def get_user_quota(user_id: str, ...):
    """Get quota for a user (returns defaults if no custom quota)."""

@router.put("/{user_id}")
async def update_user_quota(user_id: str, body: UpdateQuotaRequest, ...):
    """Set custom quota for a user."""

@router.delete("/{user_id}")
async def reset_user_quota(user_id: str, ...):
    """Delete custom quota (user falls back to defaults)."""
```

---

## PART 4: DATA RETENTION ENFORCEMENT

### 4.1. Hiện trạng

Model `Request` đã có:
- `retention_hours: int` — user chọn khi upload (default: 168 = 7 days)
- `expires_at: datetime` — tính từ `created_at + retention_hours`

**Nhưng chưa có code enforce** → Data tồn tại vĩnh viễn dù đã hết hạn.

### 4.2. Thiết kế

Background asyncio task chạy mỗi giờ:

```
┌─ Retention Enforcement Loop (hourly) ─────────────────────┐
│                                                            │
│  1. Query: requests WHERE expires_at <= NOW                │
│            AND deleted_at IS NULL                           │
│            LIMIT 100 (batch)                               │
│                                                            │
│  2. For each expired request:                              │
│     a. Move uploads/* → deleted/* bucket (MinIO)           │
│     b. Move results/* → deleted/* bucket (MinIO)           │
│     c. Soft-delete File records (set deleted_at)           │
│     d. Soft-delete Job records (set deleted_at)            │
│     e. Soft-delete Request record (set deleted_at)         │
│                                                            │
│  3. Audit: log("retention.cleanup", system, details)       │
│  4. Metric: retention_cleaned_total.inc(count)             │
│                                                            │
│  Sleep 1 hour → repeat                                     │
└────────────────────────────────────────────────────────────┘
```

### 4.3. Implementation

```python
# File mới: 02_backend/app/core/retention.py

import asyncio
import logging
from datetime import datetime, timezone

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Request, File, Job
from app.config import settings

logger = logging.getLogger(__name__)

async def retention_enforcement_loop(storage):
    """Periodically enforce data retention policies."""
    while True:
        try:
            if settings.retention_enabled:
                cleaned = await _cleanup_expired_requests(storage)
                if cleaned > 0:
                    logger.info(f"Retention cleanup: {cleaned} requests cleaned")
        except Exception as e:
            logger.error(f"Retention cleanup error: {e}", exc_info=True)

        await asyncio.sleep(settings.retention_interval_seconds)


async def _cleanup_expired_requests(storage) -> int:
    """Find and clean up expired requests. Returns count cleaned."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        expired = db.query(Request).filter(
            Request.expires_at <= now,
            Request.deleted_at.is_(None),
        ).limit(100).all()

        if not expired:
            return 0

        for req in expired:
            await _cleanup_single_request(db, storage, req)

        db.commit()
        return len(expired)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _cleanup_single_request(db, storage, request):
    """Clean up a single expired request."""
    now = datetime.now(timezone.utc)

    for file_rec in request.files:
        if file_rec.deleted_at:
            continue

        # Move original upload to deleted bucket
        try:
            await storage.move_to_deleted(
                settings.minio_bucket_uploads,
                file_rec.object_key,
            )
        except Exception as e:
            logger.warning(f"Failed to move upload {file_rec.object_key}: {e}")

        file_rec.deleted_at = now

    # Move results and soft-delete jobs
    for job in request.jobs:
        if job.deleted_at:
            continue

        if job.result_path:
            try:
                await storage.move_to_deleted(
                    settings.minio_bucket_results,
                    job.result_path,
                )
            except Exception as e:
                logger.warning(f"Failed to move result {job.result_path}: {e}")

        job.deleted_at = now

    # Soft-delete the request itself
    request.deleted_at = now
```

### 4.4. Configuration

```python
# File: 02_backend/app/config.py (thêm)

class Settings(BaseSettings):
    # ... existing ...

    # Retention enforcement
    retention_enabled: bool = True
    retention_interval_seconds: int = 3600    # 1 hour
```

### 4.5. Lifecycle

```python
# File: 02_backend/app/core/lifespan.py (thêm vào startup)

from app.core.retention import retention_enforcement_loop

async def startup():
    # ... existing startup ...

    # Start retention enforcement
    if settings.retention_enabled:
        asyncio.create_task(retention_enforcement_loop(storage_service))
        logger.info("Retention enforcement started "
                     f"(interval: {settings.retention_interval_seconds}s)")
```

### 4.6. Deleted bucket cleanup

Files di chuyển sang `deleted` bucket vẫn tồn tại (soft delete ở storage level).
Admin có thể:
- Recover files nếu cần (move lại từ deleted → uploads/results)
- Hard delete bằng MinIO lifecycle policy hoặc manual cleanup

Recommend thêm MinIO lifecycle rule cho deleted bucket:
```json
{
  "Rules": [{
    "Status": "Enabled",
    "Expiration": { "Days": 30 },
    "Filter": { "Prefix": "" }
  }]
}
```
→ Auto hard-delete files trong deleted bucket sau 30 ngày.

---

## Tóm tắt files

### Files mới

| File | Module |
|------|--------|
| `02_backend/app/core/audit.py` | Audit helper function |
| `02_backend/app/core/rate_limit.py` | slowapi setup |
| `02_backend/app/core/retention.py` | Background retention task |
| `02_backend/app/modules/upload/quota.py` | Quota checking logic |
| `02_backend/app/infrastructure/database/repositories/audit_log.py` | AuditLog repository |
| `02_backend/app/infrastructure/database/repositories/quota.py` | UserQuota repository |
| `02_backend/app/api/v1/endpoints/admin/audit.py` | Admin audit query API |
| `02_backend/app/api/v1/endpoints/admin/quotas.py` | Admin quota management API |

### Files modify

| File | Thay đổi |
|------|----------|
| `02_backend/app/infrastructure/database/models.py` | +AuditLog, +UserQuota models |
| `02_backend/app/main.py` | setup_rate_limit(app) |
| `02_backend/app/core/lifespan.py` | Start retention loop |
| `02_backend/app/config.py` | +retention_enabled, +retention_interval_seconds |
| `02_backend/app/api/v1/endpoints/auth.py` | +audit calls, +@limiter.limit |
| `02_backend/app/api/v1/endpoints/upload.py` | +@limiter.limit |
| `02_backend/app/api/v1/endpoints/admin/service_types.py` | +audit calls |
| `02_backend/app/modules/upload/service.py` | +check_quota() call |
| `02_backend/app/api/v1/router.py` | Register audit + quotas routers |
| `02_backend/requirements.txt` | +slowapi |
