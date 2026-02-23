# 01 — Observability Architecture Overview

> Kiến trúc tổng quan của observability stack và cách tích hợp vào hệ thống OCR Platform hiện có.

---

## 1. High-Level Architecture

```
                         ┌─────────────────────────┐
                         │       GRAFANA :3000      │
                         │  ┌───────┬───────┬─────┐ │
                         │  │Metrics│ Logs  │Trace│ │
                         │  │Panels │Search │View │ │
                         │  └───┬───┴───┬───┴──┬──┘ │
                         └─────┼───────┼──────┼────┘
                               │       │      │
                  ┌────────────┘       │      └────────────┐
                  ▼                    ▼                   ▼
          ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
          │  PROMETHEUS  │    │     LOKI     │    │    TEMPO     │
          │    :9090     │    │    :3100     │    │    :3200     │
          │              │    │              │    │    :4317     │
          │  Metrics DB  │    │   Log Store  │    │ Trace Store  │
          └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
                 │                   │                   │
            scrape /metrics     Promtail tail       OTLP gRPC
            (pull, 15s)         Docker logs         (push)
                 │                   │                   │
     ┌───────────┼───────────────────┼───────────────────┼──────────┐
     │           ▼                   ▼                   ▼          │
     │  ┌─────────────────────────────────────────────────────────┐ │
     │  │                    BACKEND :8000                        │ │
     │  │                                                         │ │
     │  │  /metrics ──────────────────────────► Prometheus scrape │ │
     │  │  stdout JSON logs ──────────────────► Promtail → Loki  │ │
     │  │  OTel SDK spans ────────OTLP────────► Tempo            │ │
     │  │                                                         │ │
     │  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ │ │
     │  │  │ Metrics  │ │ Logging  │ │  Tracing  │ │  Audit   │ │ │
     │  │  │prometheus│ │ JSON +   │ │ OTel SDK  │ │  SQLite  │ │ │
     │  │  │_client   │ │contextvar│ │ + spans   │ │  table   │ │ │
     │  │  └──────────┘ └──────────┘ └───────────┘ └──────────┘ │ │
     │  └─────────────────────┬───────────────────────────────────┘ │
     │                        │                                     │
     │                   NATS :4222                                 │
     │              (traceparent in msg)                             │
     │                        │                                     │
     │  ┌─────────────────────▼───────────────────────────────────┐ │
     │  │                    WORKER                               │ │
     │  │                                                         │ │
     │  │  stdout JSON logs ──────────────────► Promtail → Loki  │ │
     │  │  OTel SDK spans ────────OTLP────────► Tempo            │ │
     │  │  (extract traceparent from NATS msg)                    │ │
     │  └─────────────────────────────────────────────────────────┘ │
     │                                                              │
     │                    ALERTMANAGER :9093                         │
     │                         ▲                                    │
     │                         │ fire alerts                        │
     │                    Prometheus rules                           │
     │                         │                                    │
     │                    ┌────┴─────┐                              │
     │                    │ Telegram │                              │
     │                    │ Slack    │                              │
     │                    │ Email    │                              │
     │                    └──────────┘                              │
     │                                                              │
     │                    ocr-network (bridge)                      │
     └──────────────────────────────────────────────────────────────┘
```

---

## 2. Thành phần và vai trò

### 2.1. Metrics Pipeline (Prometheus → Grafana)

```
Backend code                  Prometheus               Grafana
┌─────────────────┐          ┌─────────────┐          ┌──────────┐
│ prometheus_client│  scrape  │ Time-series │  query   │Dashboard │
│ Counter/Histogram│◄─────────│   Storage   │◄─────────│  Panels  │
│ Gauge            │  /metrics│  (30 days)  │  PromQL  │          │
│                  │  (15s)   │             │          │          │
└─────────────────┘          └──────┬──────┘          └──────────┘
                                    │
                                    ▼
                             AlertManager
                             (rule eval)
```

**Cách hoạt động:**
1. Backend expose `/metrics` endpoint bằng `prometheus_client`
2. Prometheus scrape endpoint mỗi 15 giây
3. Data lưu dưới dạng time-series (retention 30 ngày)
4. Grafana query Prometheus bằng PromQL để render dashboard
5. Prometheus evaluate alert rules, fire tới AlertManager

### 2.2. Logging Pipeline (Stdout → Promtail → Loki → Grafana)

```
Backend/Worker               Promtail                  Loki              Grafana
┌─────────────┐             ┌───────────┐             ┌──────────┐     ┌──────────┐
│ JSON log    │  Docker     │ Docker SD │  push API   │Log chunks│ LogQL│ Explore  │
│ → stdout    │──stdout────►│ Pipeline  │────────────►│ + Index  │◄─────│  View    │
│ {trace_id,  │             │ Extract   │             │          │      │          │
│  request_id,│             │ labels    │             │          │      │          │
│  user_id}   │             └───────────┘             └──────────┘      └──────────┘
└─────────────┘
```

**Cách hoạt động:**
1. Backend/Worker log JSON có sẵn ra stdout (pattern hiện tại, không đổi)
2. Promtail discover containers qua Docker socket
3. Pipeline stages parse JSON, extract `level`, `logger`, `trace_id` làm labels
4. Push log entries tới Loki API
5. Grafana query Loki bằng LogQL

**Điểm mạnh:** Backend code **không cần thay đổi output** — chỉ cần enrich JSON fields.

### 2.3. Tracing Pipeline (OTel SDK → Tempo → Grafana)

```
Backend                      NATS                     Worker               Tempo
┌──────────────┐            ┌──────────┐            ┌──────────────┐     ┌───────┐
│ OTel SDK     │            │JobMessage│            │ OTel SDK     │     │ OTLP  │
│              │  publish   │{         │  consume   │              │     │Receiver│
│ Span:        │───────────►│ trace_   │───────────►│ Span:        │     │       │
│ "upload_file"│            │ parent   │            │ "process_job"│     │       │
│   ├─ DB query│            │ trace_   │            │   ├─ download│     │       │
│   ├─ MinIO   │            │ state    │            │   ├─ OCR     │     │       │
│   └─ NATS pub│            │}         │            │   └─ upload  │     │       │
│              │────OTLP───►│          │            │              │──OTLP──►    │
└──────────────┘            └──────────┘            └──────────────┘     └───┬───┘
                                                                            │
                                                                        Grafana
                                                                        Trace View
```

**Cách hoạt động:**
1. Backend OTel SDK tạo spans cho mỗi operation (DB, MinIO, NATS publish)
2. Trước khi publish NATS message, inject W3C `traceparent` + `tracestate` vào `JobMessage`
3. Worker extract trace context từ message, tạo child span `process_job`
4. Cả backend và worker push spans tới Tempo qua OTLP gRPC
5. Grafana Tempo datasource hiển thị full trace end-to-end

**End-to-end trace example:**
```
Trace: abc123
├─ [backend] POST /api/v1/upload (250ms)
│  ├─ [backend] validate_files (5ms)
│  ├─ [backend] MinIO.upload (50ms)
│  ├─ [backend] DB.create_job (3ms)
│  └─ [backend] NATS.publish (2ms)
│
└─ [worker] process_job (3500ms)
   ├─ [worker] FileProxy.download (100ms)
   ├─ [worker] OCR.process (3200ms)
   ├─ [worker] FileProxy.upload (150ms)
   └─ [worker] Orchestrator.update_status (50ms)
```

### 2.4. Governance Layer (Application-level)

```
┌────────────────────────────────────────────────────────────┐
│                    Backend Application                      │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  Audit Log   │  │ Rate Limiter │  │ Data Retention   │ │
│  │              │  │              │  │                  │ │
│  │ SQLite table │  │ slowapi      │  │ asyncio bg task  │ │
│  │ audit_logs   │  │ in-memory    │  │ hourly cleanup   │ │
│  │              │  │ sliding win  │  │                  │ │
│  │ WHO did WHAT │  │ per-user/IP  │  │ expire → move    │ │
│  │ WHEN WHERE   │  │ rate limits  │  │ to deleted bucket│ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
│         │                 │                    │           │
│         ▼                 ▼                    ▼           │
│  Admin API:        HTTP 429 response    MinIO soft-delete  │
│  GET /admin/audit  on excess requests   + DB soft-delete   │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   User Quotas                        │  │
│  │  SQLite table user_quotas                            │  │
│  │  daily_upload_limit | monthly_job_limit              │  │
│  │  max_file_size_mb   | max_batch_size                 │  │
│  │  Check before upload → reject if exceeded            │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Docker Compose — Services mới

### 3.1. Service definitions

Thêm vào `docker-compose.yml`, tất cả join `ocr-network`:

```yaml
  # === OBSERVABILITY STACK ===

  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: ocr-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./infra/prometheus/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro
      - ./data/prometheus:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/healthy"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - ocr-network

  grafana:
    image: grafana/grafana:10.4.0
    container_name: ocr-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - ./data/grafana:/var/lib/grafana
    depends_on:
      prometheus:
        condition: service_healthy
    networks:
      - ocr-network

  loki:
    image: grafana/loki:2.9.5
    container_name: ocr-loki
    ports:
      - "3100:3100"
    volumes:
      - ./infra/loki/loki-config.yaml:/etc/loki/local-config.yaml:ro
      - ./data/loki:/loki
    command: -config.file=/etc/loki/local-config.yaml
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3100/ready"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - ocr-network

  promtail:
    image: grafana/promtail:2.9.5
    container_name: ocr-promtail
    volumes:
      - ./infra/promtail/promtail-config.yaml:/etc/promtail/config.yaml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yaml
    depends_on:
      loki:
        condition: service_healthy
    networks:
      - ocr-network

  tempo:
    image: grafana/tempo:2.4.0
    container_name: ocr-tempo
    ports:
      - "3200:3200"
      - "4317:4317"
      - "4318:4318"
    volumes:
      - ./infra/tempo/tempo-config.yaml:/etc/tempo/config.yaml:ro
      - ./data/tempo:/var/tempo
    command: -config.file=/etc/tempo/config.yaml
    networks:
      - ocr-network

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: ocr-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./infra/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    networks:
      - ocr-network
```

### 3.2. Port Map tổng hợp

| Service | Port | UI/API | Mục đích |
|---------|------|--------|----------|
| Backend | 8000 | API + /metrics | OCR Platform API |
| MinIO | 9000, 9001 | Console :9001 | Object storage |
| NATS | 4222, 8222 | Monitor :8222 | Message queue |
| Prometheus | 9090 | Web UI | Metrics query |
| Grafana | 3000 | Web UI | Dashboards |
| Loki | 3100 | API | Log query |
| Tempo | 3200, 4317 | API + OTLP | Trace query |
| AlertManager | 9093 | Web UI | Alert management |

### 3.3. Config files directory structure

```
infra/
├── prometheus/
│   ├── prometheus.yml              # Scrape targets
│   └── alert_rules.yml             # Alert rule definitions
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yaml    # Prometheus, Loki, Tempo
│   │   └── dashboards/
│   │       └── dashboards.yaml     # Dashboard provisioning config
│   └── dashboards/
│       ├── system-overview.json    # System health dashboard
│       ├── worker-fleet.json       # Worker monitoring dashboard
│       ├── job-pipeline.json       # Job flow dashboard
│       ├── user-activity.json      # User behavior dashboard
│       └── audit-log.json          # Audit trail dashboard
├── loki/
│   └── loki-config.yaml           # Storage, retention, schema
├── promtail/
│   └── promtail-config.yaml       # Docker SD, pipeline stages
├── tempo/
│   └── tempo-config.yaml          # OTLP receiver, local storage
└── alertmanager/
    └── alertmanager.yml            # Routing, receivers (placeholder)
```

---

## 4. Data Flow Summary

### 4.1. Request lifecycle với observability

```
User upload file
    │
    ▼
┌─ Backend receives POST /api/v1/upload ─────────────────────────────┐
│                                                                     │
│  1. CorrelationMiddleware                                           │
│     → Generate trace_id, request_id                                 │
│     → Set contextvars                                               │
│                                                                     │
│  2. RequestLoggingMiddleware                                        │
│     → Start timer                                                   │
│     → Log: {method, path, status, duration, trace_id, request_id}  │
│                                                                     │
│  3. Auth dependency                                                 │
│     → Validate token                                                │
│     → Set user_id contextvar                                        │
│     → Metric: auth_attempts_total                                   │
│                                                                     │
│  4. Rate limit check (slowapi)                                      │
│     → Check per-user rate                                           │
│     → 429 if exceeded                                               │
│                                                                     │
│  5. Quota check                                                     │
│     → Check daily_upload_limit, max_file_size                       │
│     → Reject if exceeded                                            │
│                                                                     │
│  6. Upload service (OTel span: "upload_files")                      │
│     ├─ Validate files                                               │
│     ├─ MinIO upload (OTel span: "minio.upload")                     │
│     ├─ DB create records (OTel span: "db.create_job")               │
│     ├─ NATS publish + inject traceparent (OTel span: "nats.publish")│
│     ├─ Metric: uploads_total.inc()                                  │
│     ├─ Metric: upload_size_bytes.observe()                          │
│     ├─ Metric: jobs_submitted_total.inc()                           │
│     └─ Audit: log("upload.create", user, request_id)               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
    │
    │  NATS message {job_id, ..., trace_parent, trace_state}
    ▼
┌─ Worker consumes job ──────────────────────────────────────────────┐
│                                                                     │
│  1. Extract traceparent → continue OTel trace                       │
│  2. OTel span: "process_job"                                        │
│     ├─ FileProxy.download (OTel span: "file_proxy.download")        │
│     ├─ OCR.process (OTel span: "ocr.process")                       │
│     ├─ FileProxy.upload (OTel span: "file_proxy.upload")            │
│     └─ Orchestrator.update_status                                   │
│  3. Stdout log: {trace_id, job_id, duration, status}               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
    │
    │  POST /internal/job-status {status: COMPLETED}
    ▼
┌─ Backend updates job ──────────────────────────────────────────────┐
│  Metric: jobs_completed_total.inc()                                 │
│  Metric: job_processing_duration.observe()                          │
│  Audit: log("job.completed", system, job_id)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2. Correlation ID propagation

```
                    trace_id: "abc-123"
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
Prometheus           Loki logs            Tempo traces
(label trên          (field trong         (trace ID)
 exemplar)            JSON log)

→ Click trace_id trong Loki → nhảy sang Tempo trace view
→ Click trace_id trong Tempo → nhảy sang Loki logs cùng trace
→ Grafana dashboard → drill down từ metric → logs → traces
```

---

## 5. Quyết định thiết kế quan trọng

### 5.1. Tại sao Tempo thay vì Jaeger?

| Tiêu chí | Tempo | Jaeger |
|-----------|-------|--------|
| Grafana integration | Native (cùng ecosystem) | Cần plugin |
| Storage dependency | Local filesystem | Cần Elasticsearch hoặc Cassandra |
| Docker complexity | 1 container | 3-4 containers (collector, query, storage) |
| Trace-Log correlation | Built-in với Loki | Manual config |
| Resource usage | Nhẹ | Nặng hơn |

**Kết luận:** Tempo phù hợp hơn cho single-developer deployment.

### 5.2. Tại sao in-memory rate limiting thay vì Redis?

| Tiêu chí | In-memory (slowapi) | Redis |
|-----------|---------------------|-------|
| Thêm dependency | Không | Cần Redis container |
| Hoạt động khi single backend | Tốt | Overkill |
| Mất state khi restart | Có (chấp nhận được) | Không |
| Scale multi-instance | Không | Có |

**Kết luận:** Hiện tại single backend → in-memory đủ. Migrate sang Redis khi cần multi-instance.

### 5.3. Tại sao audit log trong SQLite thay vì chỉ Loki?

| Tiêu chí | SQLite table | Chỉ Loki |
|-----------|-------------|----------|
| Query chính xác (filter by actor, action, date) | SQL WHERE clause | LogQL (kém linh hoạt hơn) |
| API endpoint cho admin UI | Dễ (SELECT từ table) | Phức tạp (proxy Loki query) |
| Data integrity | ACID transactions | Eventual consistency |
| Retention control | Application-managed | Loki retention policy |

**Kết luận:** Audit log cần structured query → SQLite là primary store. Loki là secondary (search + dashboard).

### 5.4. Tại sao contextvars thay vì truyền request object?

```python
# KHÔNG LÀM: Truyền request qua mọi function
async def upload_service(request: Request, db, files):
    await create_job(request, db, ...)
    await publish_nats(request, ...)

# LÀM: contextvars tự propagate qua async chain
# Middleware set 1 lần → toàn bộ call chain đều access được
from app.core.context import get_trace_id
logger.info("job created", extra={"trace_id": get_trace_id()})
```

**Lý do:** Không cần thay đổi function signature của code hiện tại. `contextvars` propagate tự nhiên qua `async`/`await`.
