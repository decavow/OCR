# OCR Platform — Observability & Governance

> Tài liệu thiết kế hệ thống Observation và Governance cho OCR Platform
> Version: 1.0 | Status: Draft
> Scope: Xây dựng full observability stack cho local MVP, sẵn sàng scale lên cloud

---

## Table of Contents

| # | Document | Mô tả |
|---|----------|-------|
| 01 | [Architecture Overview](./01_architecture_overview.md) | Kiến trúc tổng quan observability stack, các thành phần và data flow |
| 02 | [Metrics & Instrumentation](./02_metrics_and_instrumentation.md) | Prometheus metrics, custom business metrics, /metrics endpoint |
| 03 | [Logging & Tracing](./03_logging_and_tracing.md) | Structured logging + Loki, distributed tracing + Tempo, correlation IDs |
| 04 | [Governance](./04_governance.md) | Audit logging, rate limiting, user quotas, data retention enforcement |
| 05 | [Alerting & Dashboards](./05_alerting_and_dashboards.md) | AlertManager rules, Grafana dashboards, notification channels |
| 06 | [Implementation Plan](./06_implementation_plan.md) | Phased rollout, file changes, verification checklist |

---

## Context

### Hiện trạng (trước observability)

Hệ thống OCR Platform hiện chỉ có các cơ chế monitoring cơ bản:

| Feature | Mức độ | Hạn chế |
|---------|--------|---------|
| JSON structured logging | Stdout only | Không aggregate, không search, mất khi container restart |
| Request timing middleware | Log method/path/status/duration | Không có metrics time-series, không percentiles |
| Admin dashboard KPIs | Query trực tiếp DB | Không real-time, tốn DB resource, không historical trend |
| Worker heartbeat | 30s interval | Không alerting khi worker chết |
| Job state machine | DB-backed transitions | Không trace xuyên suốt backend → NATS → worker |

### Mục tiêu

Xây dựng **Observability Stack (Hướng 2)** với các thành phần:

```
Metrics    → Prometheus + Grafana      (time-series, dashboards)
Logging    → Loki + Promtail           (log aggregation, search)
Tracing    → OpenTelemetry + Tempo     (distributed tracing)
Alerting   → AlertManager              (automated notifications)
Governance → Audit log, Rate limit, Quotas, Retention enforcement
```

### Nguyên tắc thiết kế

1. **Additive, not rewrite** — Thêm instrumentation vào code hiện có, không refactor lại
2. **Convention over configuration** — Dùng auto-instrumentation (FastAPI, SQLAlchemy, httpx) trước, custom sau
3. **Correlation everywhere** — Mọi log/metric/trace đều liên kết qua `trace_id`
4. **Separation of concerns** — Observability infra chạy riêng container, không ảnh hưởng business logic
5. **Progressive enhancement** — Mỗi phase hoạt động độc lập, không cần chờ phase sau

### Tech Stack bổ sung

| Component | Image | Port | Vai trò |
|-----------|-------|------|---------|
| Prometheus | `prom/prometheus:v2.51.0` | 9090 | Metrics collection & storage |
| Grafana | `grafana/grafana:10.4.0` | 3000 | Dashboard & visualization |
| Loki | `grafana/loki:2.9.5` | 3100 | Log aggregation |
| Promtail | `grafana/promtail:2.9.5` | — | Log shipper (Docker → Loki) |
| Tempo | `grafana/tempo:2.4.0` | 3200, 4317 | Trace storage (OTLP receiver) |
| AlertManager | `prom/alertmanager:v0.27.0` | 9093 | Alert routing & notification |

### Tổng quan thay đổi

| Metric | Số lượng |
|--------|----------|
| Docker services mới | 6 |
| Config files mới | ~12 |
| Python files mới (backend) | ~8 |
| Python files modify (backend) | ~12 |
| Python packages mới (backend) | 8 |
| Python packages mới (worker) | 4 |
| DB models mới | 2 (AuditLog, UserQuota) |
| Grafana dashboards | 5 |
