# 06 — Implementation Plan

> Kế hoạch triển khai theo phases, danh sách files cần tạo/modify, và verification checklist.

---

## 1. Phase Overview

```
Week 1                    Week 2                    Week 3              Week 4
┌───────────────────┐    ┌───────────────────┐    ┌──────────────┐    ┌──────────────┐
│ Phase 1: Infra    │    │ Phase 5: Audit    │    │ Phase 4:     │    │ Phase 8:     │
│ (Docker Compose)  │    │ (DB + API)        │    │ Distributed  │    │ Alert Rules  │
│                   │    │                   │    │ Tracing      │    │              │
│ Phase 2: Metrics  │    │ Phase 6: Rate     │    │ (OTel)       │    │ Phase 9:     │
│ (Prometheus)      │    │ Limit & Quotas    │    │              │    │ Dashboards   │
│                   │    │                   │    │              │    │ (Grafana)    │
│ Phase 3: Logging  │    │ Phase 7: Data     │    │              │    │              │
│ (Correlation IDs) │    │ Retention         │    │              │    │              │
└───────────────────┘    └───────────────────┘    └──────────────┘    └──────────────┘
 ~6h                      ~8h                      ~5h                 ~4h
```

**Tổng estimated effort:** ~23 giờ

---

## 2. Phase 1: Observability Infrastructure

**Effort:** ~2h | **Dependency:** None | **Risk:** Low

### Mục tiêu
Docker Compose chạy đủ 6 services mới, Grafana accessible.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `infra/prometheus/prometheus.yml` | Scrape targets: backend:8000, nats:8222 |
| 2 | `infra/prometheus/alert_rules.yml` | Placeholder (populated in Phase 8) |
| 3 | `infra/grafana/provisioning/datasources/datasources.yaml` | Prometheus, Loki, Tempo datasources |
| 4 | `infra/grafana/provisioning/dashboards/dashboards.yaml` | Dashboard file provisioning |
| 5 | `infra/loki/loki-config.yaml` | Filesystem storage, 30d retention |
| 6 | `infra/promtail/promtail-config.yaml` | Docker SD, JSON pipeline stages |
| 7 | `infra/tempo/tempo-config.yaml` | OTLP receiver, local storage |
| 8 | `infra/alertmanager/alertmanager.yml` | Default routing, placeholder receivers |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `docker-compose.yml` | +6 services (prometheus, grafana, loki, promtail, tempo, alertmanager) |
| 2 | `.gitignore` | +data/prometheus, data/grafana, data/loki, data/tempo |

### Verification
- [ ] `docker compose up -d` → tất cả services healthy
- [ ] `http://localhost:9090/targets` → Prometheus UI accessible
- [ ] `http://localhost:3000` → Grafana login (admin/admin)
- [ ] `http://localhost:3100/ready` → Loki ready
- [ ] `http://localhost:9093` → AlertManager UI

---

## 3. Phase 2: Prometheus Metrics

**Effort:** ~3h | **Dependency:** Phase 1 | **Risk:** Low

### Mục tiêu
Backend expose `/metrics`, Prometheus scrape thành công, custom business metrics hoạt động.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/metrics.py` | Metric definitions + `setup_metrics()` |
| 2 | `02_backend/app/core/metrics_collector.py` | Background gauge collector (30s loop) |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/requirements.txt` | +prometheus-fastapi-instrumentator, +prometheus-client |
| 2 | `02_backend/app/main.py` | `setup_metrics(app)` |
| 3 | `02_backend/app/core/lifespan.py` | Start `metrics_collector_loop` task |
| 4 | `02_backend/app/modules/upload/service.py` | +uploads_total, +upload_size_bytes, +jobs_submitted_total |
| 5 | `02_backend/app/api/v1/internal/job_status.py` | +jobs_completed_total, +jobs_failed_total, +job_processing_duration |
| 6 | `02_backend/app/api/v1/endpoints/auth.py` | +auth_attempts_total |
| 7 | `02_backend/app/api/v1/internal/heartbeat.py` | +active_workers gauge updates |

### Verification
- [ ] `curl localhost:8000/metrics` → returns Prometheus format
- [ ] Upload 1 file → `ocr_jobs_submitted_total` tăng 1
- [ ] Job complete → `ocr_jobs_completed_total` tăng 1
- [ ] Prometheus targets page → backend target UP
- [ ] PromQL query: `rate(http_requests_total[5m])` → returns data

---

## 4. Phase 3: Structured Logging + Correlation IDs

**Effort:** ~1.5h | **Dependency:** Phase 1 | **Risk:** Low

### Mục tiêu
Mọi log entry có trace_id, request_id, user_id. Loki search hoạt động.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/context.py` | ContextVars: trace_id, request_id, user_id |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/app/core/logging.py` | JSONFormatter thêm trace_id, request_id, user_id |
| 2 | `02_backend/app/core/middleware.py` | +CorrelationMiddleware class + register |
| 3 | `02_backend/app/api/deps.py` | +set_user_id() trong get_current_user |

### Verification
- [ ] Login → upload → check docker logs backend → JSON có trace_id, user_id
- [ ] Grafana Explore → Loki → `{container="ocr-backend"} | json` → fields visible
- [ ] Filter by trace_id: `| trace_id="abc-123"` → chỉ logs cùng request

---

## 5. Phase 4: Distributed Tracing (OpenTelemetry)

**Effort:** ~5h | **Dependency:** Phase 1, 3 | **Risk:** Medium

### Mục tiêu
Full trace từ upload request → NATS → worker → result. Visible trong Grafana Tempo.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/tracing.py` | Backend OTel setup (FastAPI + SQLAlchemy auto-instrument) |
| 2 | `03_worker/app/core/tracing.py` | Worker OTel setup (httpx auto-instrument) |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/requirements.txt` | +opentelemetry-* packages (5 packages) |
| 2 | `03_worker/requirements.txt` | +opentelemetry-* packages (4 packages) |
| 3 | `02_backend/app/main.py` | `setup_tracing(app, engine)` |
| 4 | `02_backend/app/infrastructure/queue/messages.py` | +trace_parent, +trace_state fields |
| 5 | `02_backend/app/infrastructure/queue/nats_client.py` | Inject trace context before publish |
| 6 | `03_worker/app/main.py` | `setup_tracing(instance_id)` |
| 7 | `03_worker/app/core/worker.py` | Extract trace context, wrap process_job in span |
| 8 | `03_worker/app/clients/queue_client.py` | Pass trace fields through |
| 9 | `docker-compose.yml` | +OTEL_EXPORTER_OTLP_ENDPOINT env var |

### Verification
- [ ] Upload file → Job completes
- [ ] Grafana Explore → Tempo → Search by service "ocr-backend" → trace visible
- [ ] Trace has spans from both `ocr-backend` AND `ocr-worker`
- [ ] Click trace_id in Loki → jumps to Tempo trace view
- [ ] Processing time visible in span duration

---

## 6. Phase 5: Audit Logging

**Effort:** ~3h | **Dependency:** Phase 3 (context) | **Risk:** Low

### Mục tiêu
Mọi admin action và auth event được ghi lại, queryable qua API.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/audit.py` | `audit()` helper function |
| 2 | `02_backend/app/infrastructure/database/repositories/audit_log.py` | AuditLogRepository |
| 3 | `02_backend/app/api/v1/endpoints/admin/audit.py` | GET /admin/audit endpoint |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/app/infrastructure/database/models.py` | +AuditLog model |
| 2 | `02_backend/app/infrastructure/database/repositories/__init__.py` | Export AuditLogRepository |
| 3 | `02_backend/app/api/v1/router.py` | Register audit router |
| 4 | `02_backend/app/api/v1/endpoints/auth.py` | +audit() calls (login, login_failed, logout, register) |
| 5 | `02_backend/app/api/v1/endpoints/admin/service_types.py` | +audit() calls (approve, reject, disable, enable, delete) |
| 6 | `02_backend/app/api/v1/endpoints/upload.py` | +audit() call (upload.create) |
| 7 | `02_backend/app/api/v1/internal/job_status.py` | +audit() calls (job.completed, job.failed) |

### Verification
- [ ] Login → `GET /admin/audit?action=auth.login` → returns entry
- [ ] Approve service → `GET /admin/audit?action=service.approve` → returns entry
- [ ] Upload file → `GET /admin/audit?action=upload.create` → returns entry
- [ ] Entry has actor_email, ip_address, trace_id

---

## 7. Phase 6: Rate Limiting & User Quotas

**Effort:** ~3h | **Dependency:** Phase 2 (metrics) | **Risk:** Low

### Mục tiêu
Excessive requests bị 429, uploads bị reject khi vượt quota.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/rate_limit.py` | slowapi Limiter setup |
| 2 | `02_backend/app/modules/upload/quota.py` | check_quota() logic |
| 3 | `02_backend/app/infrastructure/database/repositories/quota.py` | UserQuotaRepository |
| 4 | `02_backend/app/api/v1/endpoints/admin/quotas.py` | Admin quota CRUD API |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/requirements.txt` | +slowapi |
| 2 | `02_backend/app/infrastructure/database/models.py` | +UserQuota model |
| 3 | `02_backend/app/main.py` | `setup_rate_limit(app)` |
| 4 | `02_backend/app/api/v1/endpoints/auth.py` | +@limiter.limit("10/minute") on login |
| 5 | `02_backend/app/api/v1/endpoints/upload.py` | +@limiter.limit("30/minute"), catch QuotaExceeded |
| 6 | `02_backend/app/modules/upload/service.py` | +check_quota() call |
| 7 | `02_backend/app/api/v1/router.py` | Register quotas router |

### Verification
- [ ] Login 11 times in 1 minute → 11th returns HTTP 429
- [ ] Set quota daily_limit=1 → upload twice → 2nd rejected
- [ ] `ocr_rate_limit_hits_total` metric increments on 429
- [ ] `ocr_quota_exceeded_total` metric increments on quota exceeded

---

## 8. Phase 7: Data Retention Enforcement

**Effort:** ~2h | **Dependency:** None (independent) | **Risk:** Medium

### Mục tiêu
Expired requests tự động soft-delete, files di chuyển sang deleted bucket.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `02_backend/app/core/retention.py` | retention_enforcement_loop() |

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `02_backend/app/core/lifespan.py` | Start retention loop in startup() |
| 2 | `02_backend/app/config.py` | +retention_enabled, +retention_interval_seconds |

### Verification
- [ ] Upload với retention_hours=1 → wait 1h (hoặc set interval thấp hơn để test)
- [ ] Request record has deleted_at set
- [ ] File moved from uploads → deleted bucket in MinIO
- [ ] Result moved from results → deleted bucket in MinIO
- [ ] Logs show "Retention cleanup: N requests cleaned"

---

## 9. Phase 8: Alert Rules

**Effort:** ~1h | **Dependency:** Phase 2 (metrics) | **Risk:** Low

### Mục tiêu
Prometheus evaluate alert rules, AlertManager receives alerts.

### Modify

| # | File | Thay đổi |
|---|------|----------|
| 1 | `infra/prometheus/alert_rules.yml` | Full alert rules (7 rules in 4 groups) |
| 2 | `infra/alertmanager/alertmanager.yml` | Configure webhook/email receivers |

### Verification
- [ ] Stop all workers → `NoActiveWorkers` alert fires within 2m
- [ ] `http://localhost:9093` → AlertManager shows active alert
- [ ] `http://localhost:9090/alerts` → Prometheus shows alert state
- [ ] Start workers back → alert resolves

---

## 10. Phase 9: Grafana Dashboards

**Effort:** ~3h | **Dependency:** Phase 2, 3, 5 | **Risk:** Low

### Mục tiêu
5 dashboards provisioned tự động, render data thực.

### Tạo mới

| # | File | Nội dung |
|---|------|----------|
| 1 | `infra/grafana/dashboards/system-overview.json` | Request rate, error rate, latency, workers, queue |
| 2 | `infra/grafana/dashboards/worker-fleet.json` | Workers by type, processing time, instance table |
| 3 | `infra/grafana/dashboards/job-pipeline.json` | Job flow, queue depth, success rate, retry rate |
| 4 | `infra/grafana/dashboards/user-activity.json` | Auth attempts, uploads, quota usage |
| 5 | `infra/grafana/dashboards/audit-log.json` | Audit events timeline, admin actions |

### Verification
- [ ] Grafana → OCR Platform folder → 5 dashboards listed
- [ ] System Overview → all stat panels show values (not "No data")
- [ ] Upload files → Job Pipeline dashboard updates
- [ ] Login → User Activity shows auth events
- [ ] Audit Log shows recent entries

---

## 11. Complete File Summary

### Tất cả files mới (25 files)

```
# Infrastructure configs (8)
infra/prometheus/prometheus.yml
infra/prometheus/alert_rules.yml
infra/grafana/provisioning/datasources/datasources.yaml
infra/grafana/provisioning/dashboards/dashboards.yaml
infra/loki/loki-config.yaml
infra/promtail/promtail-config.yaml
infra/tempo/tempo-config.yaml
infra/alertmanager/alertmanager.yml

# Grafana dashboards (5)
infra/grafana/dashboards/system-overview.json
infra/grafana/dashboards/worker-fleet.json
infra/grafana/dashboards/job-pipeline.json
infra/grafana/dashboards/user-activity.json
infra/grafana/dashboards/audit-log.json

# Backend code (8)
02_backend/app/core/context.py
02_backend/app/core/metrics.py
02_backend/app/core/metrics_collector.py
02_backend/app/core/tracing.py
02_backend/app/core/audit.py
02_backend/app/core/rate_limit.py
02_backend/app/core/retention.py
02_backend/app/modules/upload/quota.py

# Backend repositories + endpoints (4)
02_backend/app/infrastructure/database/repositories/audit_log.py
02_backend/app/infrastructure/database/repositories/quota.py
02_backend/app/api/v1/endpoints/admin/audit.py
02_backend/app/api/v1/endpoints/admin/quotas.py

# Worker code (1 - minus existing)
03_worker/app/core/tracing.py
```

### Tất cả files modify (15 files)

```
# Root
docker-compose.yml
.gitignore

# Backend
02_backend/requirements.txt
02_backend/app/main.py
02_backend/app/config.py
02_backend/app/core/logging.py
02_backend/app/core/middleware.py
02_backend/app/core/lifespan.py
02_backend/app/api/deps.py
02_backend/app/api/v1/router.py
02_backend/app/api/v1/endpoints/auth.py
02_backend/app/api/v1/endpoints/upload.py
02_backend/app/api/v1/internal/job_status.py
02_backend/app/api/v1/internal/heartbeat.py
02_backend/app/modules/upload/service.py
02_backend/app/infrastructure/database/models.py
02_backend/app/infrastructure/database/repositories/__init__.py
02_backend/app/infrastructure/queue/messages.py
02_backend/app/infrastructure/queue/nats_client.py

# Worker
03_worker/requirements.txt
03_worker/app/main.py
03_worker/app/core/worker.py
03_worker/app/clients/queue_client.py
```

---

## 12. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| OTel instrumentation gây slowdown | API latency tăng | BatchSpanProcessor (async export), benchmark trước/sau |
| Promtail chiếm Docker socket | Security concern | Read-only mount, container filter by network |
| SQLite lock contention (audit writes) | Upload latency tăng | WAL mode đã có, audit writes nhỏ (~1ms) |
| Grafana dashboard JSON phức tạp | Maintenance khó | Export từ Grafana UI → save JSON, không edit thủ công |
| Rate limiter in-memory mất state khi restart | Brief window without limits | Chấp nhận được cho single-instance. Document migration path to Redis |
| Tempo storage tăng nhanh | Disk full | Set retention trong Tempo config, monitor disk usage |

---

## 13. Post-Implementation Checklist

Sau khi hoàn thành tất cả 9 phases:

- [ ] **Metrics**: `/metrics` endpoint returns all custom metrics
- [ ] **Logging**: Tất cả logs có trace_id, structured JSON
- [ ] **Tracing**: End-to-end trace visible in Tempo (backend → NATS → worker)
- [ ] **Correlation**: Click trace_id trong Loki → nhảy sang Tempo (và ngược lại)
- [ ] **Audit**: Admin actions + auth events logged, queryable via API
- [ ] **Rate Limit**: Login brute-force blocked, upload spam blocked
- [ ] **Quotas**: User cannot exceed daily/batch limits
- [ ] **Retention**: Expired data cleaned automatically
- [ ] **Alerts**: Worker down → alert fires → notification sent
- [ ] **Dashboards**: All 5 dashboards render real data
- [ ] **Documentation**: Tất cả 6 docs trong `04_docs/06-Observability/` updated
