# 02 — Metrics & Instrumentation

> Thiết kế hệ thống metrics sử dụng Prometheus client, bao gồm auto HTTP metrics và custom business metrics.

---

## 1. Tổng quan

### 1.1. Kiến trúc metrics

```
Backend Application
┌─────────────────────────────────────────────────────┐
│                                                     │
│  prometheus_fastapi_instrumentator                  │
│  ├─ http_requests_total (auto)                      │
│  ├─ http_request_duration_seconds (auto)            │
│  └─ http_requests_in_progress (auto)                │
│                                                     │
│  Custom business metrics (prometheus_client)         │
│  ├─ Counters: jobs, uploads, auth attempts           │
│  ├─ Histograms: processing time, file size           │
│  └─ Gauges: active workers, queue depth, sessions    │
│                                                     │
│  /metrics endpoint ◄──── Prometheus scrape (15s)     │
│                                                     │
│  Background metrics collector (30s loop)             │
│  └─ Poll DB/NATS for gauge values                    │
└─────────────────────────────────────────────────────┘
```

### 1.2. Python packages

Thêm vào `02_backend/requirements.txt`:
```
prometheus-fastapi-instrumentator>=6.1.0
prometheus-client>=0.20.0
```

---

## 2. Auto HTTP Metrics

`prometheus-fastapi-instrumentator` tự động instrument mọi HTTP request:

### 2.1. Metrics tự động có sẵn

| Metric | Type | Labels | Mô tả |
|--------|------|--------|--------|
| `http_requests_total` | Counter | method, handler, status | Tổng số HTTP requests |
| `http_request_duration_seconds` | Histogram | method, handler | Thời gian xử lý request |
| `http_requests_in_progress` | Gauge | method, handler | Số request đang xử lý |
| `http_request_size_bytes` | Histogram | handler | Kích thước request body |
| `http_response_size_bytes` | Histogram | handler | Kích thước response body |

### 2.2. Setup code

```python
# File: 02_backend/app/core/metrics.py

from prometheus_fastapi_instrumentator import Instrumentator

def setup_metrics(app):
    """Setup auto HTTP metrics + expose /metrics endpoint."""
    instrumentator = Instrumentator(
        should_group_status_codes=True,        # 2xx, 3xx, 4xx, 5xx
        should_ignore_untemplated=True,        # Ignore 404 on unknown paths
        should_respect_env_var=False,           # Always enabled
        excluded_handlers=["/health", "/metrics"],  # Exclude from metrics
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
```

### 2.3. Tích hợp

```python
# File: 02_backend/app/main.py (thêm vào sau setup_middleware)

from app.core.metrics import setup_metrics

# Trong lifespan hoặc sau khi tạo app:
setup_metrics(app)
```

---

## 3. Custom Business Metrics

### 3.1. Definitions

```python
# File: 02_backend/app/core/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# ================================================================
# COUNTERS — Đếm tổng số events (chỉ tăng, không giảm)
# ================================================================

jobs_submitted_total = Counter(
    "ocr_jobs_submitted_total",
    "Total OCR jobs submitted to queue",
    ["method", "tier"],
)

jobs_completed_total = Counter(
    "ocr_jobs_completed_total",
    "Total OCR jobs completed successfully",
    ["method", "tier"],
)

jobs_failed_total = Counter(
    "ocr_jobs_failed_total",
    "Total OCR jobs that failed (terminal)",
    ["method", "tier"],
)

uploads_total = Counter(
    "ocr_uploads_total",
    "Total upload requests (batches)",
    ["method", "tier"],
)

auth_attempts_total = Counter(
    "ocr_auth_attempts_total",
    "Authentication attempts",
    ["result"],  # "success" | "failure"
)

rate_limit_hits_total = Counter(
    "ocr_rate_limit_hits_total",
    "Number of requests rejected by rate limiter",
    ["endpoint"],
)

quota_exceeded_total = Counter(
    "ocr_quota_exceeded_total",
    "Number of requests rejected by quota check",
    ["reason"],  # "daily_limit" | "file_size" | "batch_size"
)

# ================================================================
# HISTOGRAMS — Đo phân phối giá trị
# ================================================================

job_processing_duration = Histogram(
    "ocr_job_processing_duration_seconds",
    "OCR job processing duration in seconds",
    ["method", "tier"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
)

upload_size_bytes = Histogram(
    "ocr_upload_size_bytes",
    "Individual file size in uploaded batch",
    ["mime_type"],
    buckets=[
        1024,        # 1 KB
        10240,       # 10 KB
        102400,      # 100 KB
        1048576,     # 1 MB
        5242880,     # 5 MB
        10485760,    # 10 MB
        52428800,    # 50 MB
    ],
)

upload_batch_size = Histogram(
    "ocr_upload_batch_size",
    "Number of files per upload batch",
    buckets=[1, 2, 5, 10, 20, 50],
)

# ================================================================
# GAUGES — Giá trị hiện tại (tăng/giảm)
# ================================================================

active_workers = Gauge(
    "ocr_active_workers",
    "Number of active (non-DEAD) worker instances",
    ["service_type"],
)

processing_jobs = Gauge(
    "ocr_processing_jobs",
    "Number of jobs currently in PROCESSING state",
)

active_sessions = Gauge(
    "ocr_active_sessions",
    "Number of non-expired user sessions",
)

queue_depth = Gauge(
    "ocr_queue_depth",
    "Approximate number of pending messages in job queue",
    ["subject"],
)
```

### 3.2. Metric naming conventions

Tuân thủ Prometheus naming best practices:

| Rule | Example | Giải thích |
|------|---------|-----------|
| Prefix = app name | `ocr_` | Namespace tránh conflict |
| Unit suffix | `_seconds`, `_bytes` | Rõ ràng đơn vị |
| `_total` suffix cho counter | `jobs_completed_total` | Convention bắt buộc |
| Snake_case | `job_processing_duration` | Prometheus standard |
| Labels cho dimensions | `["method", "tier"]` | Filter/group by |

### 3.3. Label cardinality

> **Quan trọng:** Giữ label cardinality thấp để tránh metrics explosion.

| Label | Possible values | Cardinality |
|-------|----------------|-------------|
| `method` | text_raw, table, form, ... | ~5 (thấp) |
| `tier` | 0, 1, 2, 3, 4 | 5 (thấp) |
| `result` | success, failure | 2 (thấp) |
| `service_type` | ocr-text-tier0, ... | ~10 (OK) |
| `mime_type` | image/png, image/jpeg, application/pdf | ~5 (thấp) |

**KHÔNG BAO GIỜ** dùng high-cardinality labels: user_id, job_id, file_name, IP address → dùng logs/traces thay thế.

---

## 4. Instrumentation Points

### 4.1. Upload flow

```python
# File: 02_backend/app/modules/upload/service.py
# Trong method process_upload():

from app.core.metrics import (
    uploads_total, upload_size_bytes, upload_batch_size,
    jobs_submitted_total,
)

# Sau khi tạo request thành công:
uploads_total.labels(method=method, tier=str(tier)).inc()
upload_batch_size.observe(len(validated_files))

# Cho mỗi file trong batch:
for file in validated_files:
    upload_size_bytes.labels(mime_type=file.mime_type).observe(file.size_bytes)

# Cho mỗi job published vào NATS:
for job in created_jobs:
    jobs_submitted_total.labels(method=method, tier=str(tier)).inc()
```

### 4.2. Job completion

```python
# File: 02_backend/app/api/v1/internal/job_status.py
# Trong endpoint update_job_status():

from app.core.metrics import (
    jobs_completed_total, jobs_failed_total,
    job_processing_duration,
)

if new_status == "COMPLETED":
    jobs_completed_total.labels(
        method=job.method, tier=str(job.tier)
    ).inc()

    if job.processing_time_ms:
        job_processing_duration.labels(
            method=job.method, tier=str(job.tier)
        ).observe(job.processing_time_ms / 1000)  # Convert ms → seconds

elif new_status == "FAILED":
    jobs_failed_total.labels(
        method=job.method, tier=str(job.tier)
    ).inc()
```

### 4.3. Authentication

```python
# File: 02_backend/app/api/v1/endpoints/auth.py

from app.core.metrics import auth_attempts_total

# Trong login():
try:
    user = auth_service.login(email, password)
    auth_attempts_total.labels(result="success").inc()
except UnauthorizedError:
    auth_attempts_total.labels(result="failure").inc()
    raise
```

### 4.4. Heartbeat (worker gauge)

```python
# File: 02_backend/app/api/v1/internal/heartbeat.py

from app.core.metrics import active_workers

# Khi instance chuyển sang ACTIVE:
active_workers.labels(service_type=instance.service_type_id).inc()

# Khi instance chuyển sang DEAD:
active_workers.labels(service_type=instance.service_type_id).dec()
```

---

## 5. Background Metrics Collector

Một số gauges cần polling từ DB/NATS vì không có event-driven trigger:

```python
# File: 02_backend/app/core/metrics_collector.py

import asyncio
import logging
from datetime import datetime, timezone

from app.core.metrics import active_sessions, processing_jobs, queue_depth
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Session as SessionModel, Job

logger = logging.getLogger(__name__)

COLLECTOR_INTERVAL = 30  # seconds

async def metrics_collector_loop():
    """Periodically update gauge metrics by polling DB."""
    while True:
        try:
            _collect_db_gauges()
        except Exception as e:
            logger.warning(f"Metrics collector error: {e}")
        await asyncio.sleep(COLLECTOR_INTERVAL)


def _collect_db_gauges():
    """Sync DB queries for gauge metrics."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Active sessions (non-expired)
        session_count = db.query(SessionModel).filter(
            SessionModel.expires_at > now
        ).count()
        active_sessions.set(session_count)

        # Processing jobs
        processing_count = db.query(Job).filter(
            Job.status == "PROCESSING",
            Job.deleted_at.is_(None),
        ).count()
        processing_jobs.set(processing_count)

    finally:
        db.close()
```

### Khởi động trong lifespan

```python
# File: 02_backend/app/core/lifespan.py (thêm vào startup)

from app.core.metrics_collector import metrics_collector_loop

async def startup():
    # ... existing startup code ...

    # Start background metrics collector
    asyncio.create_task(metrics_collector_loop())
    logger.info("Metrics collector started")
```

---

## 6. Prometheus Configuration

```yaml
# File: infra/prometheus/prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alert_rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  # Backend metrics
  - job_name: 'backend'
    metrics_path: /metrics
    static_configs:
      - targets: ['backend:8000']
        labels:
          service: 'ocr-backend'

  # NATS monitoring
  - job_name: 'nats'
    metrics_path: /varz
    static_configs:
      - targets: ['nats:8222']
        labels:
          service: 'nats'
```

---

## 7. PromQL Query Examples

### 7.1. Dashboard queries

| Panel | PromQL |
|-------|--------|
| Request rate (req/s) | `rate(http_requests_total{handler!="/health"}[5m])` |
| Error rate (%) | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100` |
| Latency p95 | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| Jobs submitted/min | `rate(ocr_jobs_submitted_total[5m]) * 60` |
| Job success rate | `rate(ocr_jobs_completed_total[5m]) / (rate(ocr_jobs_completed_total[5m]) + rate(ocr_jobs_failed_total[5m])) * 100` |
| Avg processing time | `rate(ocr_job_processing_duration_seconds_sum[5m]) / rate(ocr_job_processing_duration_seconds_count[5m])` |
| Active workers | `ocr_active_workers` |
| Queue depth | `ocr_queue_depth` |
| Failed auth rate | `rate(ocr_auth_attempts_total{result="failure"}[5m])` |
| Upload size p50 | `histogram_quantile(0.5, rate(ocr_upload_size_bytes_bucket[1h]))` |

### 7.2. Alert queries

Chi tiết trong [05_alerting_and_dashboards.md](./05_alerting_and_dashboards.md).

---

## 8. Verification

### 8.1. Kiểm tra /metrics endpoint

```bash
# Sau khi deploy:
curl http://localhost:8000/metrics | head -50

# Expected output (trích):
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{handler="/api/v1/upload",method="POST",status="2xx"} 42.0

# HELP ocr_jobs_submitted_total Total OCR jobs submitted to queue
# TYPE ocr_jobs_submitted_total counter
ocr_jobs_submitted_total{method="text_raw",tier="0"} 156.0

# HELP ocr_active_workers Number of active worker instances
# TYPE ocr_active_workers gauge
ocr_active_workers{service_type="ocr-text-tier0"} 2.0
```

### 8.2. Kiểm tra Prometheus targets

Truy cập `http://localhost:9090/targets`:
- `backend` target → State: UP
- `nats` target → State: UP
