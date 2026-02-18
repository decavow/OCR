# 03 — Logging & Distributed Tracing

> Nâng cấp structured logging với correlation IDs, tích hợp Loki cho log aggregation, và OpenTelemetry + Tempo cho distributed tracing end-to-end.

---

## PART 1: STRUCTURED LOGGING + LOKI

### 1.1. Hiện trạng logging

Hệ thống đã có structured JSON logging:

```python
# File hiện tại: 02_backend/app/core/logging.py
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)
```

**Output hiện tại:**
```json
{"timestamp": "2026-02-16T10:30:00", "level": "INFO", "message": "POST /api/v1/upload - 200 - 250ms", "logger": "middleware"}
```

**Hạn chế:**
- Không có `trace_id` → không thể correlate logs của cùng 1 request
- Không có `user_id` → không biết ai gây ra log entry
- Không có `request_id` → không phân biệt được concurrent requests
- Logs chỉ ở stdout → mất khi container restart, không search được

### 1.2. Thiết kế mới: Context-aware logging

#### 1.2.1. Context variables

```python
# File mới: 02_backend/app/core/context.py

import uuid
from contextvars import ContextVar

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")

def set_trace_id(val: str):
    _trace_id.set(val)

def get_trace_id() -> str:
    return _trace_id.get()

def set_request_id(val: str):
    _request_id.set(val)

def get_request_id() -> str:
    return _request_id.get()

def set_user_id(val: str):
    _user_id.set(val)

def get_user_id() -> str:
    return _user_id.get()

def generate_id() -> str:
    return str(uuid.uuid4())
```

**Tại sao `contextvars`?**
- Python 3.7+ native — không cần dependency
- Propagate tự động qua `async`/`await` chain
- Thread-safe cho concurrent requests
- Không cần thay đổi function signatures của code hiện tại

#### 1.2.2. Correlation Middleware

```python
# File: 02_backend/app/core/middleware.py (thêm class mới)

class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Inject trace_id và request_id vào context cho mọi request.
    - trace_id: Dùng incoming X-Trace-Id header hoặc generate mới
    - request_id: Luôn generate mới (unique per request)
    """

    async def dispatch(self, request: Request, call_next):
        from app.core.context import (
            set_trace_id, set_request_id, generate_id,
        )

        # Trace ID: reuse from header (cho cross-service) hoặc generate
        trace_id = request.headers.get("X-Trace-Id", generate_id())
        request_id = generate_id()

        set_trace_id(trace_id)
        set_request_id(request_id)

        response = await call_next(request)

        # Propagate back in response headers
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Request-Id"] = request_id

        return response
```

**Middleware registration order** (quan trọng):
```python
def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(CorrelationMiddleware)   # 1st: Set context (outermost)
    app.add_middleware(RequestLoggingMiddleware) # 2nd: Log with context
    app.add_exception_handler(AppException, app_exception_handler)
```

#### 1.2.3. Enhanced JSONFormatter

```python
# File: 02_backend/app/core/logging.py (modify)

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # === NEW: Correlation fields from context ===
        from app.core.context import get_trace_id, get_request_id, get_user_id
        trace_id = get_trace_id()
        if trace_id:
            log_data["trace_id"] = trace_id
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id
        user_id = get_user_id()
        if user_id:
            log_data["user_id"] = user_id

        # Extra fields (existing behavior)
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)
```

**Output mới:**
```json
{
  "timestamp": "2026-02-16T10:30:00",
  "level": "INFO",
  "message": "POST /api/v1/upload - 200 - 250ms",
  "logger": "middleware",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "request_id": "f9e8d7c6-b5a4-3210-fedc-ba0987654321",
  "user_id": "usr-abc123"
}
```

#### 1.2.4. Set user_id sau authentication

```python
# File: 02_backend/app/api/deps.py (modify get_current_user)

from app.core.context import set_user_id

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(get_token),
) -> User:
    user = auth_service.validate_token(db, token)
    set_user_id(user.id)  # ← NEW: Set context cho logging
    return user
```

### 1.3. Loki Integration

#### 1.3.1. Promtail config

```yaml
# File: infra/promtail/promtail-config.yaml

server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
        filters:
          - name: network
            values: ["ocr-network"]

    relabel_configs:
      # Container name as label
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      # Log stream (stdout/stderr)
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'stream'

    pipeline_stages:
      # Parse Docker log wrapper
      - docker: {}

      # Parse JSON log body
      - json:
          expressions:
            level: level
            logger: logger
            trace_id: trace_id
            request_id: request_id
            user_id: user_id

      # Promote to Loki labels (chỉ low-cardinality fields)
      - labels:
          level:
          logger:
          # KHÔNG promote trace_id, user_id vì high cardinality
          # → Dùng filter expressions thay vì labels

      # Parse timestamp from JSON
      - timestamp:
          source: timestamp
          format: '2006-01-02T15:04:05.999999999Z07:00'
```

#### 1.3.2. Loki config

```yaml
# File: infra/loki/loki-config.yaml

auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 30d
  allow_structured_metadata: true

compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
```

#### 1.3.3. LogQL query examples

| Mục đích | Query |
|----------|-------|
| Tất cả logs của backend | `{container="ocr-backend"}` |
| Chỉ ERROR logs | `{container="ocr-backend"} \| json \| level="ERROR"` |
| Logs theo trace_id | `{container=~"ocr-.*"} \| json \| trace_id="abc-123"` |
| Logs theo user_id | `{container="ocr-backend"} \| json \| user_id="usr-456"` |
| Upload errors | `{container="ocr-backend", logger="upload"} \| json \| level="ERROR"` |
| Worker processing logs | `{container=~"ocr-worker.*"} \| json \| message=~".*process.*"` |
| Log rate by level | `sum by (level) (rate({container="ocr-backend"} \| json [5m]))` |
| Error spike detection | `sum(rate({container="ocr-backend"} \| json \| level="ERROR" [1m])) > 5` |

---

## PART 2: DISTRIBUTED TRACING (OpenTelemetry + Tempo)

### 2.1. Tại sao cần distributed tracing?

Hiện tại khi 1 job fail, phải:
1. Check backend log → tìm job_id
2. Check NATS monitoring → message có deliver không?
3. Check worker log → tìm job_id trong worker nào?
4. Ghép timeline thủ công

Với tracing, chỉ cần 1 trace_id → thấy toàn bộ lifecycle:

```
Trace: abc-123 (total: 4200ms)
│
├─ [ocr-backend] POST /api/v1/upload          350ms
│  ├─ [ocr-backend] validate_files              10ms
│  ├─ [ocr-backend] minio.upload                80ms
│  ├─ [ocr-backend] db.create_records           15ms
│  ├─ [ocr-backend] nats.publish                 5ms
│  └─ [ocr-backend] response                     2ms
│
│  ~~~ async gap: job sits in NATS queue ~~~     200ms
│
├─ [ocr-worker] process_job                    3500ms
│  ├─ [ocr-worker] file_proxy.download          120ms
│  │  └─ [ocr-backend] GET /internal/file-proxy  80ms
│  ├─ [ocr-worker] ocr.process                 3000ms
│  ├─ [ocr-worker] file_proxy.upload             180ms
│  │  └─ [ocr-backend] POST /internal/file-proxy 150ms
│  └─ [ocr-worker] orchestrator.update_status     50ms
│     └─ [ocr-backend] PATCH /internal/job-status 30ms
│
└─ [ocr-backend] job_status_update               50ms
   ├─ [ocr-backend] db.update_job                 5ms
   └─ [ocr-backend] db.update_request             5ms
```

### 2.2. Python packages

**Backend** (`02_backend/requirements.txt`):
```
opentelemetry-api>=1.23.0
opentelemetry-sdk>=1.23.0
opentelemetry-exporter-otlp-proto-grpc>=1.23.0
opentelemetry-instrumentation-fastapi>=0.44b0
opentelemetry-instrumentation-sqlalchemy>=0.44b0
```

**Worker** (`03_worker/requirements.txt`):
```
opentelemetry-api>=1.23.0
opentelemetry-sdk>=1.23.0
opentelemetry-exporter-otlp-proto-grpc>=1.23.0
opentelemetry-instrumentation-httpx>=0.44b0
```

### 2.3. Backend OTel setup

```python
# File mới: 02_backend/app/core/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

_provider = None

def setup_tracing(app, engine, endpoint: str = "http://tempo:4317"):
    """Initialize OpenTelemetry tracing for backend."""
    global _provider

    resource = Resource.create({
        SERVICE_NAME: "ocr-backend",
    })

    _provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,
    )
    _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)

    # Auto-instrument FastAPI (creates spans for all HTTP handlers)
    FastAPIInstrumentor.instrument_app(app)

    # Auto-instrument SQLAlchemy (creates spans for all DB queries)
    SQLAlchemyInstrumentor().instrument(engine=engine)

    return _provider


def shutdown_tracing():
    """Flush and shutdown tracer."""
    global _provider
    if _provider:
        _provider.shutdown()
```

### 2.4. Worker OTel setup

```python
# File mới: 03_worker/app/core/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

_provider = None

def setup_tracing(instance_id: str, endpoint: str = "http://tempo:4317"):
    """Initialize OpenTelemetry tracing for worker."""
    global _provider

    resource = Resource.create({
        SERVICE_NAME: "ocr-worker",
        "service.instance.id": instance_id,
    })

    _provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,
    )
    _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)

    # Auto-instrument httpx (all HTTP calls from worker)
    HTTPXClientInstrumentor().instrument()

    return _provider
```

### 2.5. Trace propagation qua NATS

Đây là phần quan trọng nhất — NATS không hỗ trợ trace context natively, nên cần serialize vào message.

#### 2.5.1. Mở rộng JobMessage

```python
# File: 02_backend/app/infrastructure/queue/messages.py (modify)

@dataclass
class JobMessage:
    job_id: str
    file_id: str
    request_id: str
    method: str
    tier: int
    output_format: str
    object_key: str
    retry_count: int = 0
    # === NEW: W3C Trace Context ===
    trace_parent: str = ""    # W3C traceparent header value
    trace_state: str = ""     # W3C tracestate header value
```

#### 2.5.2. Backend: Inject trace context khi publish

```python
# File: 02_backend/app/infrastructure/queue/nats_client.py (modify publish)

from opentelemetry import trace, context
from opentelemetry.propagate import inject

async def publish(self, subject: str, message: JobMessage) -> None:
    # Inject current trace context into message
    carrier = {}
    inject(carrier)
    message.trace_parent = carrier.get("traceparent", "")
    message.trace_state = carrier.get("tracestate", "")

    data = json.dumps(message.to_dict()).encode()
    ack = await self.js.publish(subject, data)
```

#### 2.5.3. Worker: Extract trace context khi consume

```python
# File: 03_worker/app/core/worker.py (modify process_job)

from opentelemetry import trace
from opentelemetry.propagate import extract

async def process_job(self, job: dict) -> None:
    job_id = job["job_id"]

    # Extract trace context from NATS message
    carrier = {
        "traceparent": job.get("trace_parent", ""),
        "tracestate": job.get("trace_state", ""),
    }
    ctx = extract(carrier)

    tracer = trace.get_tracer("ocr-worker")

    with tracer.start_as_current_span(
        "process_job",
        context=ctx,
        kind=trace.SpanKind.CONSUMER,
    ) as span:
        span.set_attribute("job.id", job_id)
        span.set_attribute("job.method", job["method"])
        span.set_attribute("job.tier", job["tier"])
        span.set_attribute("job.file_id", job["file_id"])

        try:
            # ... existing processing logic ...
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
```

### 2.6. Tempo Configuration

```yaml
# File: infra/tempo/tempo-config.yaml

server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal

metrics_generator:
  storage:
    path: /var/tempo/generator/wal
```

### 2.7. Trace-Log Correlation trong Grafana

Cấu hình Grafana datasources để link Tempo ↔ Loki:

```yaml
# File: infra/grafana/provisioning/datasources/datasources.yaml

apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      derivedFields:
        # Click trace_id trong log → mở Tempo trace
        - datasourceUid: tempo
          matcherRegex: '"trace_id":"([a-f0-9-]+)"'
          name: TraceID
          url: '$${__value.raw}'

  - name: Tempo
    type: tempo
    uid: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      tracesToLogs:
        datasourceUid: loki
        filterByTraceID: true
        filterBySpanID: false
        tags: ['container']
      nodeGraph:
        enabled: true
      serviceMap:
        datasourceUid: prometheus
```

**Workflow trong Grafana:**
```
Grafana Explore → Loki tab
  → Query: {container="ocr-backend"} | json | level="ERROR"
  → Thấy log entry với trace_id
  → Click "TraceID" link
  → Tự động mở Tempo tab với full trace
  → Thấy tất cả spans từ backend + worker
  → Click span → "Logs for this span" → quay lại Loki
```

---

## 3. Tóm tắt files thay đổi

### Files mới

| File | Mục đích |
|------|----------|
| `02_backend/app/core/context.py` | ContextVars cho trace_id, request_id, user_id |
| `02_backend/app/core/tracing.py` | OTel setup cho backend |
| `03_worker/app/core/tracing.py` | OTel setup cho worker |
| `infra/loki/loki-config.yaml` | Loki storage config |
| `infra/promtail/promtail-config.yaml` | Log scraping pipeline |
| `infra/tempo/tempo-config.yaml` | Trace storage config |
| `infra/grafana/provisioning/datasources/datasources.yaml` | Datasource connections |

### Files modify

| File | Thay đổi |
|------|----------|
| `02_backend/app/core/logging.py` | Thêm trace_id/request_id/user_id vào JSON |
| `02_backend/app/core/middleware.py` | Thêm CorrelationMiddleware |
| `02_backend/app/api/deps.py` | set_user_id() sau auth |
| `02_backend/app/main.py` | setup_tracing() |
| `02_backend/app/infrastructure/queue/messages.py` | trace_parent, trace_state fields |
| `02_backend/app/infrastructure/queue/nats_client.py` | Inject trace context |
| `03_worker/app/main.py` | setup_tracing() |
| `03_worker/app/core/worker.py` | Extract trace context, create spans |
| `02_backend/requirements.txt` | OTel packages |
| `03_worker/requirements.txt` | OTel packages |
