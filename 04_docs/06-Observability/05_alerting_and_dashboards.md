# 05 — Alerting & Grafana Dashboards

> Prometheus alert rules, AlertManager routing, và thiết kế 5 Grafana dashboards cho OCR Platform.

---

## PART 1: ALERTING

### 1.1. Alert Architecture

```
Prometheus                  AlertManager               Receivers
┌──────────────┐           ┌──────────────┐           ┌──────────┐
│ Evaluate     │  fire     │ Group        │  route    │ Telegram │
│ alert rules  │──────────►│ Deduplicate  │──────────►│ Slack    │
│ every 15s    │           │ Route        │           │ Email    │
│              │           │ Silence      │           │ Webhook  │
└──────────────┘           └──────────────┘           └──────────┘
```

### 1.2. Alert Rules

```yaml
# File: infra/prometheus/alert_rules.yml

groups:
  # ============================================================
  # GROUP 1: System Health
  # ============================================================
  - name: system_health
    rules:
      - alert: BackendDown
        expr: up{job="backend"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OCR Backend is down"
          description: "Backend service has been unreachable for 1 minute."

      - alert: HighApiLatency
        expr: |
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket{
              handler!~"/health|/metrics"
            }[5m])
          ) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency (p95 > 5s)"
          description: "95th percentile latency is {{ $value | humanizeDuration }}."

      - alert: HighErrorRate
        expr: |
          (
            rate(http_requests_total{status=~"5.."}[5m])
            / rate(http_requests_total[5m])
          ) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High HTTP error rate (>5%)"
          description: "{{ $value | humanizePercentage }} of requests returning 5xx."

  # ============================================================
  # GROUP 2: Worker Fleet
  # ============================================================
  - name: worker_fleet
    rules:
      - alert: NoActiveWorkers
        expr: sum(ocr_active_workers) == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "No active OCR workers"
          description: "All worker instances are down. Jobs cannot be processed."

      - alert: WorkerFleetDegraded
        expr: |
          sum(ocr_active_workers) < 2
          and sum(ocr_active_workers) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Worker fleet degraded"
          description: "Only {{ $value }} worker(s) active. Processing may be slow."

  # ============================================================
  # GROUP 3: Job Pipeline
  # ============================================================
  - name: job_pipeline
    rules:
      - alert: HighJobErrorRate
        expr: |
          (
            rate(ocr_jobs_failed_total[5m])
            / (
              rate(ocr_jobs_completed_total[5m])
              + rate(ocr_jobs_failed_total[5m])
            )
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High OCR job error rate (>10%)"
          description: "{{ $value | humanizePercentage }} of jobs failing."

      - alert: QueueBacklog
        expr: sum(ocr_queue_depth) > 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Queue backlog building up"
          description: "{{ $value }} messages pending in queue for >10 minutes."

      - alert: HighProcessingTime
        expr: |
          histogram_quantile(0.95,
            rate(ocr_job_processing_duration_seconds_bucket[15m])
          ) > 120
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "OCR processing time p95 > 2 minutes"
          description: "95th percentile processing time is {{ $value | humanizeDuration }}."

      - alert: StuckJobs
        expr: ocr_processing_jobs > 0
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Jobs stuck in PROCESSING state"
          description: "{{ $value }} jobs in PROCESSING for >30 minutes."

  # ============================================================
  # GROUP 4: Security
  # ============================================================
  - name: security
    rules:
      - alert: AuthBruteForce
        expr: rate(ocr_auth_attempts_total{result="failure"}[5m]) > 0.5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Possible brute-force attack detected"
          description: "{{ $value }} failed login attempts/sec over 2 minutes."

      - alert: HighRateLimitHits
        expr: sum(rate(ocr_rate_limit_hits_total[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Sustained rate limiting activity"
          description: "Rate limiter rejecting >1 req/sec for 5 minutes."
```

### 1.3. AlertManager Configuration

```yaml
# File: infra/alertmanager/alertmanager.yml

global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s          # Wait before sending first notification
  group_interval: 10s       # Wait before sending updated notification
  repeat_interval: 4h       # Resend after this if still firing
  receiver: 'default'

  # Route critical alerts to separate channel
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      repeat_interval: 1h

receivers:
  - name: 'default'
    # Placeholder — configure when notification channel is ready
    webhook_configs: []
    # Example Telegram:
    # webhook_configs:
    #   - url: 'http://telegram-bot:8080/alert'
    #     send_resolved: true

  - name: 'critical'
    webhook_configs: []
    # Same as default but with shorter repeat_interval

# Silence rules (optional)
# inhibit_rules:
#   - source_match:
#       severity: 'critical'
#     target_match:
#       severity: 'warning'
#     equal: ['alertname']
```

### 1.4. Alert severity matrix

| Severity | Response Time | Notification | Example |
|----------|--------------|-------------|---------|
| **critical** | Ngay lập tức | Telegram + Email | BackendDown, NoActiveWorkers, AuthBruteForce |
| **warning** | Trong giờ làm việc | Slack/Email | HighErrorRate, QueueBacklog, HighLatency |
| **info** | Review hàng ngày | Dashboard only | Không alert, chỉ hiển thị trên Grafana |

---

## PART 2: GRAFANA DASHBOARDS

### 2.1. Dashboard provisioning

```yaml
# File: infra/grafana/provisioning/dashboards/dashboards.yaml

apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'OCR Platform'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

### 2.2. Dashboard 1: System Overview

**File:** `infra/grafana/dashboards/system-overview.json`
**Mục đích:** Health check nhanh toàn hệ thống — xem trong 10 giây biết hệ thống OK hay không.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM OVERVIEW                               │
├────────────┬────────────┬────────────┬────────────┬─────────────┤
│  Req/sec   │ Error Rate │ Latency p95│  Active    │  Queue      │
│   12.5     │   0.5%     │   250ms    │  Workers:3 │  Depth: 5   │
│  (stat)    │  (stat)    │  (stat)    │  (stat)    │  (stat)     │
├────────────┴────────────┴────────────┴────────────┴─────────────┤
│                                                                  │
│  Request Rate (time-series graph)                                │
│  ──── total  ──── 2xx  ──── 4xx  ──── 5xx                      │
│                                                                  │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│  Latency Percentiles (graph)     │  Error Breakdown (pie)        │
│  ──── p50  ──── p95  ──── p99   │  ■ 400  ■ 401  ■ 404  ■ 500 │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                                                                  │
│  Active Sessions (time-series)                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key PromQL queries:**

| Panel | Query |
|-------|-------|
| Req/sec (stat) | `sum(rate(http_requests_total{handler!~"/health\|/metrics"}[5m]))` |
| Error Rate (stat) | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100` |
| Latency p95 (stat) | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` |
| Active Workers (stat) | `sum(ocr_active_workers)` |
| Queue Depth (stat) | `sum(ocr_queue_depth)` |
| Request Rate (graph) | `sum by (status) (rate(http_requests_total[5m]))` |
| Latency percentiles | `histogram_quantile(0.50\|0.95\|0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` |

---

### 2.3. Dashboard 2: Worker Fleet

**File:** `infra/grafana/dashboards/worker-fleet.json`
**Mục đích:** Giám sát health và performance của tất cả worker instances.

```
┌─────────────────────────────────────────────────────────────────┐
│                     WORKER FLEET                                 │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│ Total Active│ Processing  │ Draining    │ Dead                  │
│     3       │     1       │     0       │     0                 │
├─────────────┴─────────────┴─────────────┴───────────────────────┤
│                                                                  │
│  Active Workers Over Time (by service_type)                      │
│  ──── ocr-text-tier0  ──── ocr-table-tier0                      │
│                                                                  │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│  Processing Time Distribution    │  Jobs Completed per Worker    │
│  (histogram heatmap)             │  (bar chart by service_type)  │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                                                                  │
│  Worker Instance Table                                           │
│  ┌──────────────┬────────┬──────────────┬────────────────┐      │
│  │ Instance ID  │ Status │ Last Beat    │ Current Job    │      │
│  │ ocr-text-a1  │ ACTIVE │ 5s ago       │ —              │      │
│  │ ocr-text-b2  │ PROC.. │ 3s ago       │ job-xyz-456    │      │
│  └──────────────┴────────┴──────────────┴────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key queries:**

| Panel | Query |
|-------|-------|
| Active count | `sum(ocr_active_workers)` |
| Workers by type | `ocr_active_workers` |
| Processing time heatmap | `sum(rate(ocr_job_processing_duration_seconds_bucket[5m])) by (le, method)` |
| Instance table | Loki query: `{container=~"ocr-backend"} \| json \| message=~"Heartbeat.*"` |

---

### 2.4. Dashboard 3: Job Pipeline

**File:** `infra/grafana/dashboards/job-pipeline.json`
**Mục đích:** Theo dõi flow của jobs từ submit → complete, phát hiện bottleneck.

```
┌─────────────────────────────────────────────────────────────────┐
│                     JOB PIPELINE                                 │
├────────────┬────────────┬────────────┬────────────┬─────────────┤
│ Submitted  │ Completed  │  Failed    │ Success    │ Avg Process │
│  156/h     │  148/h     │   8/h      │  Rate: 95% │  Time: 3.2s │
├────────────┴────────────┴────────────┴────────────┴─────────────┤
│                                                                  │
│  Job Flow (stacked area chart)                                   │
│  ■ Submitted  ■ Completed  ■ Failed                             │
│                                                                  │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│  Queue Depth Over Time           │  Processing Time by Method    │
│  (time-series)                   │  (box plot / histogram)       │
│                                  │  ── text_raw  ── table        │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                                                                  │
│  Retry & DLQ Rates                                               │
│  ──── retry_count > 0  ──── dead_letter                         │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Job Status Breakdown (by method x tier)                         │
│  ┌──────────┬───────┬──────────┬────────┬──────────┐            │
│  │ Method   │ Tier  │Completed │ Failed │ Success% │            │
│  │ text_raw │   0   │   142    │   6    │  95.9%   │            │
│  │ table    │   0   │    6     │   2    │  75.0%   │            │
│  └──────────┴───────┴──────────┴────────┴──────────┘            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key queries:**

| Panel | Query |
|-------|-------|
| Submitted rate | `sum(rate(ocr_jobs_submitted_total[1h])) * 3600` |
| Success rate | `sum(rate(ocr_jobs_completed_total[1h])) / (sum(rate(ocr_jobs_completed_total[1h])) + sum(rate(ocr_jobs_failed_total[1h]))) * 100` |
| Job flow stacked | `sum by (status) (rate(ocr_jobs_submitted_total[5m]))` + completed + failed |
| Queue depth | `sum(ocr_queue_depth)` |
| Processing time by method | `histogram_quantile(0.95, sum(rate(ocr_job_processing_duration_seconds_bucket[5m])) by (le, method))` |
| Avg processing time | `sum(rate(ocr_job_processing_duration_seconds_sum[1h])) / sum(rate(ocr_job_processing_duration_seconds_count[1h]))` |

---

### 2.5. Dashboard 4: User Activity

**File:** `infra/grafana/dashboards/user-activity.json`
**Mục đích:** Theo dõi hành vi người dùng, quota usage, auth patterns.

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER ACTIVITY                                │
├────────────┬────────────┬────────────┬──────────────────────────┤
│ Total Users│ Active     │ Auth Fail  │ Rate Limit Hits          │
│    25      │ Today: 8   │  /5m: 0    │    /5m: 0               │
├────────────┴────────────┴────────────┴──────────────────────────┤
│                                                                  │
│  Auth Attempts Over Time                                         │
│  ──── success (green)  ──── failure (red)                       │
│                                                                  │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│  Uploads Over Time               │  File Size Distribution       │
│  (bar chart, per hour)           │  (histogram)                  │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                                                                  │
│  Top Users by Upload Count (table)                               │
│  ┌──────────────────┬──────────┬──────────┬────────────────┐    │
│  │ Email            │ Uploads  │ Jobs     │ Quota Used (%) │    │
│  │ user1@email.com  │   42     │  210     │  84%           │    │
│  │ user2@email.com  │   15     │   60     │  30%           │    │
│  └──────────────────┴──────────┴──────────┴────────────────┘    │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Quota Exceeded Events                                           │
│  ──── daily_limit  ──── file_size  ──── batch_size              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key queries:**

| Panel | Query |
|-------|-------|
| Active sessions | `ocr_active_sessions` |
| Auth success rate | `sum(rate(ocr_auth_attempts_total{result="success"}[5m]))` |
| Auth failure rate | `sum(rate(ocr_auth_attempts_total{result="failure"}[5m]))` |
| Uploads over time | `sum(rate(ocr_uploads_total[1h])) * 3600` |
| File size distribution | `sum(rate(ocr_upload_size_bytes_bucket[1h])) by (le)` |
| Rate limit hits | `sum(rate(ocr_rate_limit_hits_total[5m]))` |
| Quota exceeded | `sum by (reason) (rate(ocr_quota_exceeded_total[1h]))` |

---

### 2.6. Dashboard 5: Audit Log

**File:** `infra/grafana/dashboards/audit-log.json`
**Mục đích:** Audit trail — ai làm gì, khi nào. Sử dụng Loki datasource.

```
┌─────────────────────────────────────────────────────────────────┐
│                      AUDIT LOG                                   │
├────────────┬────────────┬────────────┬──────────────────────────┤
│ Total      │ Admin      │ Auth       │ Security Events          │
│ Events/24h │ Actions/24h│ Events/24h │  /24h                    │
│    234     │    12      │   180      │    3                     │
├────────────┴────────────┴────────────┴──────────────────────────┤
│                                                                  │
│  Audit Events Over Time (by action category)                     │
│  ■ auth.*  ■ service.*  ■ upload.*  ■ retention.*               │
│                                                                  │
├──────────────────────────────────┬───────────────────────────────┤
│                                  │                               │
│  Admin Actions Breakdown (pie)   │  Login Activity (time-series) │
│  ■ approve  ■ reject             │  ──── success  ──── failure  │
│  ■ disable  ■ enable             │                               │
│                                  │                               │
├──────────────────────────────────┴───────────────────────────────┤
│                                                                  │
│  Recent Audit Entries (Loki log panel)                           │
│  ┌──────────────────┬──────────┬───────────┬──────────────────┐ │
│  │ Timestamp        │ Actor    │ Action    │ Resource         │ │
│  │ 10:30:05         │ admin@.. │ svc.appr  │ ocr-text-tier0   │ │
│  │ 10:29:42         │ user1@.. │ upload    │ req-abc-123      │ │
│  │ 10:28:15         │ user2@.. │ login     │ session          │ │
│  └──────────────────┴──────────┴───────────┴──────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Data source:** Loki (audit entries logged as structured JSON)

**LogQL queries:**

| Panel | Query |
|-------|-------|
| Total events | `count_over_time({container="ocr-backend"} \| json \| message=~"AUDIT:.*" [24h])` |
| Auth events | `{container="ocr-backend"} \| json \| message=~"AUDIT:auth.*"` |
| Admin actions | `{container="ocr-backend"} \| json \| message=~"AUDIT:service.*"` |
| Recent entries | `{container="ocr-backend"} \| json \| message=~"AUDIT:.*"` |

**Alternative:** Nếu audit log ở SQLite, dùng Grafana JSON API datasource hoặc backend API proxy.

---

## 3. Dashboard Access Control

| Role | Dashboards | Actions |
|------|-----------|---------|
| Admin | All 5 dashboards | View + Edit |
| Viewer | System Overview, Job Pipeline | View only |
| Anonymous | None | Disabled (`GF_AUTH_ANONYMOUS_ENABLED=false`) |

Grafana default credentials: `admin/admin` (đổi sau khi deploy).
