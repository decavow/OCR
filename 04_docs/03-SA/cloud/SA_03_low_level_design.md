# OCR Platform — Infrastructure & Deployment Plan

> Tài liệu chi tiết về hạ tầng và quy trình triển khai cho OCR Platform
> Version: 1.0 | Status: Draft
> References: `03-SA/SA_01_high_level_architecture.md`, `03-SA/SA_02_mid_level_design.md`

---

## Table of Contents

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Network & Security](#2-network--security)
3. [CI/CD Pipeline](#3-cicd-pipeline)
4. [Database Operations](#4-database-operations)
5. [Monitoring, Logging & Alerting](#5-monitoring-logging--alerting)
6. [Scaling Plan](#6-scaling-plan)
7. [Disaster Recovery](#7-disaster-recovery)
8. [Operational Runbook](#8-operational-runbook)

---

## 1. Infrastructure Overview

### 1.1. Infrastructure Strategy

| Trường | Nội dung |
|---|---|
| **Hosting Approach** | **Hybrid PaaS + Serverless:** Cloudflare (edge) + GCP managed services (orchestration) + GPU providers (processing) |
| **Cloud Provider** | Primary: **Cloudflare** (edge, storage) + **GCP** (compute, database, queue). GPU: **Vast.ai**, **RunPod** |
| **Container Strategy** | Docker containers cho workers. Serverless cho edge (Workers) và orchestration (Cloud Run). |
| **Khi nào evolve?** | Migrate to Kubernetes khi cần multi-worker orchestration phức tạp (> 5 workers per tier) hoặc custom networking requirements. |

**Sizing Guideline:**

| Scenario | Recommended |
|---|---|
| MVP (< 1,000 users) | Current setup: Cloudflare free tier, GCP free tier, 1 worker per tier |
| Growth (1K-10K users) | Upgrade Cloudflare (Pro), GCP (standard), 2-3 workers per tier |
| Scale (10K+ users) | Cloudflare Enterprise, GCP committed use, Kubernetes cho workers |

### 1.2. Infrastructure Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              INFRASTRUCTURE TOPOLOGY                                          │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                         CLOUDFLARE (Global Edge Network)                             │   │
│   │                                                                                       │   │
│   │  ┌───────────────────────────────────────────────────────────────────────────────┐  │   │
│   │  │                            DNS + CDN + WAF                                     │  │   │
│   │  │  • DDoS protection      • SSL termination     • Rate limiting                 │  │   │
│   │  └───────────────────────────────────────────────────────────────────────────────┘  │   │
│   │                                      │                                               │   │
│   │         ┌────────────────────────────┼────────────────────────────┐                 │   │
│   │         ▼                            ▼                            ▼                 │   │
│   │  ┌──────────────┐           ┌──────────────┐           ┌──────────────┐            │   │
│   │  │   Pages      │           │   Workers    │           │     R2       │            │   │
│   │  │   (Static)   │           │  (Functions) │           │  (Storage)   │            │   │
│   │  │              │           │              │           │              │            │   │
│   │  │ • SPA build  │           │ • API Gateway│           │ • Sources    │            │   │
│   │  │ • Assets     │           │ • Auth check │           │ • Results    │            │   │
│   │  │ • Bundled JS │           │ • Rate limit │           │ • Lifecycle  │            │   │
│   │  └──────────────┘           └──────┬───────┘           └──────────────┘            │   │
│   │                                     │                                               │   │
│   └─────────────────────────────────────┼───────────────────────────────────────────────┘   │
│                                         │                                                    │
│                                         │ HTTPS (via Cloudflare Tunnel or public endpoint)  │
│                                         ▼                                                    │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          GCP (asia-southeast1 - Singapore)                           │   │
│   │                                                                                       │   │
│   │  ┌───────────────────────────────────────────────────────────────────────────────┐  │   │
│   │  │                         VPC Network (10.0.0.0/16)                              │  │   │
│   │  │                                                                                │  │   │
│   │  │  ┌──────────────────────────────────────────────────────────────────────────┐ │  │   │
│   │  │  │                    Cloud Run (Serverless Container)                       │ │  │   │
│   │  │  │                                                                           │ │  │   │
│   │  │  │  Orchestrator Service                                                     │ │  │   │
│   │  │  │  • Min instances: 0                                                       │ │  │   │
│   │  │  │  • Max instances: 10                                                      │ │  │   │
│   │  │  │  • CPU: 1, Memory: 512MB                                                  │ │  │   │
│   │  │  │  • Concurrency: 80                                                        │ │  │   │
│   │  │  │  • Timeout: 300s                                                          │ │  │   │
│   │  │  └──────────────────────────────────────────────────────────────────────────┘ │  │   │
│   │  │                                                                                │  │   │
│   │  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                  │  │   │
│   │  │  │   Firestore    │  │    Pub/Sub     │  │   Scheduler    │                  │  │   │
│   │  │  │   (Native)     │  │   (Queues)     │  │    (Cron)      │                  │  │   │
│   │  │  │                │  │                │  │                │                  │  │   │
│   │  │  │ • Users        │  │ • tier-0-jobs  │  │ • Cleanup      │                  │  │   │
│   │  │  │ • Jobs         │  │ • tier-1-jobs  │  │ • Health check │                  │  │   │
│   │  │  │ • Billing      │  │ • tier-2-jobs  │  │ • Billing sync │                  │  │   │
│   │  │  │ • Notifs       │  │ • tier-3-jobs  │  │                │                  │  │   │
│   │  │  │                │  │ • tier-4-jobs  │  │                │                  │  │   │
│   │  │  │                │  │ • dead-letter  │  │                │                  │  │   │
│   │  │  └────────────────┘  └────────────────┘  └────────────────┘                  │  │   │
│   │  │                                                                                │  │   │
│   │  │  ┌────────────────┐  ┌────────────────┐                                       │  │   │
│   │  │  │ Secret Manager │  │ Cloud Logging  │                                       │  │   │
│   │  │  │                │  │ + Monitoring   │                                       │  │   │
│   │  │  │ • API keys     │  │                │                                       │  │   │
│   │  │  │ • Stripe keys  │  │ • Logs         │                                       │  │   │
│   │  │  │ • JWT secrets  │  │ • Metrics      │                                       │  │   │
│   │  │  │                │  │ • Alerts       │                                       │  │   │
│   │  │  └────────────────┘  └────────────────┘                                       │  │   │
│   │  └───────────────────────────────────────────────────────────────────────────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              GPU PROVIDERS                                            │   │
│   │                                                                                       │   │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                   │   │
│   │  │    Self-hosted   │  │     Vast.ai      │  │     RunPod       │                   │   │
│   │  │    (Tier 0)      │  │    (Tier 1)      │  │   (Tier 2-3)     │                   │   │
│   │  │                  │  │                  │  │                  │                   │   │
│   │  │ • Local server   │  │ • Spot instances │  │ • On-demand GPU  │                   │   │
│   │  │ • Always on      │  │ • RTX 3090/4090  │  │ • A100/A10       │                   │   │
│   │  │ • No SLA         │  │ • Auto on/off    │  │ • SLA 99.5-99.9% │                   │   │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘                   │   │
│   │                                                                                       │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                         VIP Cluster (Tier 4)                                  │   │   │
│   │  │                                                                               │   │   │
│   │  │  • Dedicated infrastructure      • Isolated network                          │   │   │
│   │  │  • Always on                     • E2E encryption                            │   │   │
│   │  │  • SLA 99.95%                    • Zero data retention                       │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3. Environment Strategy

| Environment | Purpose | Infrastructure | Access |
|---|---|---|---|
| **Local** | Development | Docker Compose (MinIO, Firestore Emulator, Redis) | Developer |
| **Staging** | Pre-production testing | Cloudflare (free), GCP (minimal), Tier 0 only | Dev + QA + PO |
| **Production** | Live system | Full Cloudflare + GCP + All tiers | End users |

**Environment Parity:**
- Same Docker images across environments
- Environment-specific config via environment variables
- Staging mirrors production structure (smaller scale)

---

## 2. Network & Security

### 2.1. Network Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK TOPOLOGY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   [Internet Users]                                                           │
│          │                                                                    │
│          │ HTTPS (443)                                                       │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                 CLOUDFLARE (Edge Security)                            │   │
│   │                                                                       │   │
│   │  • DDoS Protection (Always On)                                       │   │
│   │  • WAF Rules (OWASP Top 10)                                          │   │
│   │  • Rate Limiting (100 req/min/IP)                                    │   │
│   │  • Bot Protection                                                     │   │
│   │  • SSL/TLS 1.3 Termination                                           │   │
│   │  • Geographic Blocking (if needed)                                    │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│          │                                                                    │
│          │ HTTPS (via Cloudflare Tunnel)                                     │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    GCP VPC (10.0.0.0/16)                              │   │
│   │                                                                       │   │
│   │  ┌────────────────────────────────────────────────────────────────┐  │   │
│   │  │                Public Subnet (10.0.1.0/24)                      │  │   │
│   │  │                                                                 │  │   │
│   │  │  Cloud Run (Orchestrator)                                      │  │   │
│   │  │  • Ingress: All (via Cloud Run URL or custom domain)          │  │   │
│   │  │  • Egress: Allow all (to Firestore, Pub/Sub, R2)              │  │   │
│   │  └────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                       │   │
│   │  ┌────────────────────────────────────────────────────────────────┐  │   │
│   │  │                Private Services                                 │  │   │
│   │  │                                                                 │  │   │
│   │  │  Firestore: VPC Service Controls (optional, Phase 3)          │  │   │
│   │  │  Pub/Sub: VPC Service Controls (optional, Phase 3)            │  │   │
│   │  └────────────────────────────────────────────────────────────────┘  │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│          │                                                                    │
│          │ HTTPS (outbound to GPU providers)                                 │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    GPU Workers                                        │   │
│   │                                                                       │   │
│   │  • Pull from Pub/Sub (authenticated)                                 │   │
│   │  • Access R2 via presigned URLs                                      │   │
│   │  • Update Firestore via API                                          │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Network Access Rules

| Component | Accessible From | Port | Protocol | Notes |
|---|---|---|---|---|
| Cloudflare CDN | Internet | 443 | HTTPS | DDoS protected |
| Cloudflare Workers | Internet (via CDN) | 443 | HTTPS | Edge functions |
| Cloudflare R2 | Workers, Orchestrator, Workers | 443 | HTTPS (S3 API) | Via presigned URLs |
| Cloud Run | Cloudflare (via URL/Tunnel) | 443 | HTTPS | Serverless, no direct internet access preferred |
| Firestore | Cloud Run, Workers (via API) | 443 | HTTPS | IAM authenticated |
| Pub/Sub | Cloud Run, Workers (via API) | 443 | HTTPS | IAM authenticated |
| GPU Workers | Outbound only | 443 | HTTPS | Pull-based, no inbound |

### 2.3. Security Configuration

| Concern | Implementation |
|---|---|
| **SSL/TLS** | TLS 1.3 everywhere. Cloudflare handles edge SSL. HTTPS between all components. |
| **Firewall** | Cloudflare WAF enabled. GCP: deny all by default, allow specific egress. |
| **Secrets** | GCP Secret Manager for production. Cloudflare Secrets for edge. Never in code/git. |
| **SSH** | No SSH to serverless. Workers accessed via logs only. VIP cluster: SSH key + bastion. |
| **DB Access** | Firestore: IAM-based. No public endpoint. Service account per component. |
| **DDoS** | Cloudflare DDoS protection (free tier sufficient for MVP). |
| **Dependency Scan** | Dependabot enabled. npm audit in CI. Trivy for container images. |
| **Container Scan** | Trivy scan on every build. Block deploy if critical vulnerabilities. |
| **IAM** | Principle of least privilege. Separate service accounts per service. |

### 2.4. DNS Configuration

| Record | Type | Value | Purpose |
|---|---|---|---|
| ocr-platform.com | A | Cloudflare Proxy | Main domain |
| www.ocr-platform.com | CNAME | ocr-platform.com | WWW redirect |
| api.ocr-platform.com | CNAME | Cloudflare Proxy → Cloud Run | API endpoint |
| staging.ocr-platform.com | CNAME | Cloudflare Proxy | Staging env |

---

## 3. CI/CD Pipeline

### 3.1. Pipeline Strategy

| Trường | Decision | Lý do |
|---|---|---|
| **CI/CD Tool** | GitHub Actions | Native to GitHub, free for public repos, sufficient for MVP |
| **Branching** | GitHub Flow | Simple: main + feature branches. No complex release branches. |
| **Deploy Strategy** | Rolling (Cloud Run), Direct (Cloudflare) | Cloud Run handles rolling updates automatically |
| **Release Process** | Auto to staging on merge, Manual approval for production | Fast iteration while maintaining production stability |

### 3.2. Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CI/CD PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   [Developer Push / PR]                                                       │
│          │                                                                    │
│          ▼                                                                    │
│   ┌──────────────┐                                                           │
│   │  CI Pipeline │                                                           │
│   │              │                                                           │
│   │  1. Checkout                                                             │
│   │  2. Install dependencies                                                 │
│   │  3. Lint (ESLint, Prettier)                                             │
│   │  4. Type check (TypeScript)                                             │
│   │  5. Unit tests                                                          │
│   │  6. Integration tests (with emulators)                                  │
│   │  7. Security scan (npm audit, Trivy)                                    │
│   │  8. Build Docker images                                                 │
│   │  9. Push to Container Registry                                          │
│   └──────┬───────┘                                                           │
│          │                                                                    │
│          │ On merge to main                                                  │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    CD Pipeline (Staging)                              │   │
│   │                                                                       │   │
│   │  1. Deploy Cloudflare Workers                                        │   │
│   │  2. Deploy Cloudflare Pages                                          │   │
│   │  3. Deploy Cloud Run (staging)                                       │   │
│   │  4. Run smoke tests                                                  │   │
│   │  5. Notify team (Slack)                                              │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│          │                                                                    │
│          │ Manual approval (GitHub Environment)                              │
│          ▼                                                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    CD Pipeline (Production)                           │   │
│   │                                                                       │   │
│   │  1. Deploy Cloudflare Workers (production)                           │   │
│   │  2. Deploy Cloudflare Pages (production)                             │   │
│   │  3. Deploy Cloud Run (production, gradual rollout)                   │   │
│   │  4. Health check (wait 5 min)                                        │   │
│   │  5. Monitor error rate                                               │   │
│   │  6. Auto-rollback if error > 5%                                      │   │
│   │  7. Notify team                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3. Trigger Rules

| Branch / Event | Action | Target |
|---|---|---|
| Push to `feature/*` | CI only (lint, test, build) | — |
| PR to `main` | CI + preview deploy (Cloudflare preview) | Preview URL |
| Merge to `main` | CI + CD to staging | staging.ocr-platform.com |
| Manual trigger / Tag `v*` | CD to production (after approval) | ocr-platform.com |

### 3.4. Environment Variables & Secrets

| Variable | Staging | Production | Source |
|---|---|---|---|
| `DATABASE_PROJECT` | staging-project-id | production-project-id | GitHub Secret |
| `R2_BUCKET` | ocr-staging | ocr-production | GitHub Secret |
| `STRIPE_SECRET_KEY` | sk_test_xxx | sk_live_xxx | GCP Secret Manager |
| `JWT_SECRET` | (random) | (random) | GCP Secret Manager |
| `GOOGLE_CLIENT_ID` | (same) | (same) | GitHub Secret |
| `GITHUB_CLIENT_ID` | (same) | (same) | GitHub Secret |
| `ENVIRONMENT` | staging | production | CI variable |
| `LOG_LEVEL` | debug | info | CI variable |

### 3.5. Rollback Strategy

| Scenario | Detection | Method | Recovery Time |
|---|---|---|---|
| Deploy crash | Health check fail | Cloud Run auto-rollback | < 2 min |
| Error rate spike | Monitoring alert (> 5%) | Manual: `gcloud run deploy --revision` | < 5 min |
| Feature bug | User report | Manual: redeploy previous image | < 10 min |
| Data corruption | Manual detection | Restore from backup + redeploy | < 1 hour |

---

## 4. Database Operations

### 4.1. Database Hosting

| Trường | Decision | Lý do |
|---|---|---|
| **Service** | Firestore (Native mode) | Serverless, scale-to-zero, document model fits |
| **Region** | asia-southeast1 (Singapore) | Low latency for SEA users |
| **Multi-region** | No (MVP) | Cost. Consider asia-south1 for DR in Phase 3 |

### 4.2. Backup & Recovery

| Aspect | Configuration |
|---|---|
| **Auto Backup** | Daily (Firestore built-in) |
| **Retention** | 7 days (free tier) |
| **Point-in-Time Recovery** | Enabled (Firestore native) |
| **Manual Backup** | Before major migrations, stored in GCS |
| **Backup Verification** | Monthly: restore to staging and verify |
| **RTO** | 4 hours |
| **RPO** | 24 hours (daily backup) |

### 4.3. Migration Strategy

| Aspect | Approach |
|---|---|
| **Tool** | Custom scripts (Firestore Admin SDK) |
| **Workflow** | Write script → Test local (emulator) → Test staging → Apply production |
| **Rollback** | Each migration has reverse script |
| **Zero-Downtime** | Additive changes only. Avoid renaming/deleting fields in production. |
| **Large Data** | Batch operations with exponential backoff |

**Migration Script Example:**

```javascript
// migrations/001_add_retention_days.js
async function up(db) {
  const jobs = await db.collection('jobs').where('retention_days', '==', null).get();
  const batch = db.batch();
  jobs.forEach(doc => {
    batch.update(doc.ref, { retention_days: 7 });
  });
  await batch.commit();
}

async function down(db) {
  // No-op: field can remain
}
```

---

## 5. Monitoring, Logging & Alerting

### 5.1. Monitoring Stack

| Layer | Tool | Purpose |
|---|---|---|
| **Uptime** | GCP Uptime Checks | Health check endpoints every 1 min |
| **Error Tracking** | GCP Error Reporting | Exception capture with stack traces |
| **APM** | Cloud Run metrics | Request latency, throughput |
| **Infrastructure** | GCP Cloud Monitoring | CPU, memory, network |
| **Log Management** | GCP Cloud Logging | Centralized logs, searchable |
| **Alerting** | GCP Alerting + Slack | Route alerts to team |

### 5.2. Logging Strategy

| Aspect | Configuration |
|---|---|
| **Format** | Structured JSON: `{timestamp, level, message, trace_id, user_id, ...}` |
| **Levels** | ERROR (alert), WARN (investigate), INFO (events), DEBUG (dev only) |
| **Storage** | Cloud Logging (30 days production, 7 days staging) |
| **PII** | NEVER log: passwords, tokens, card numbers, full phone. Mask sensitive. |
| **Tracing** | Unique `trace_id` per request, propagated via header `X-Trace-ID` |

**Log Format Example:**

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "message": "Job submitted",
  "trace_id": "abc123",
  "user_id": "usr_xyz789",
  "job_id": "job_abc123",
  "method": "ocr_table",
  "tier": 2,
  "page_count": 10
}
```

### 5.3. Alert Rules

| Alert | Condition | Severity | Action |
|---|---|---|---|
| **App Down** | Health check fail × 2 | 🔴 Critical | Page on-call, auto-restart |
| **High Error Rate** | > 5% errors / 5 min | 🔴 Critical | Page on-call |
| **Slow Response** | P95 > 2s / 10 min | 🟡 Warning | Slack notification |
| **Queue Backlog** | > 100 pending / 10 min | 🟡 Warning | Slack, consider scaling |
| **Worker Missing** | Heartbeat missing > 60s | 🔴 Critical | Auto-mark job failed, page |
| **High Refund Rate** | > 10% / 1 hour | 🟡 Warning | Investigate quality issues |
| **Storage High** | R2 > 80% quota | 🟡 Warning | Plan cleanup or upgrade |
| **Billing Error** | Stripe webhook 4xx/5xx | 🔴 Critical | Manual review |

### 5.4. Health Check Endpoints

| Endpoint | Check | Response | Interval |
|---|---|---|---|
| `GET /health` | App running | `{"status": "ok"}` | 30s |
| `GET /health/ready` | App + Firestore + Pub/Sub | `{"status": "ok", "db": "ok", "queue": "ok"}` | 60s |

---

## 6. Scaling Plan

### 6.1. Scaling Tiers

| Tier | Users | Traffic | Infrastructure | Trigger Next |
|---|---|---|---|---|
| **Tier 0 — MVP** | 0-500 | < 100 req/min | Cloud Run (0-2), 1 worker/tier | CPU > 70% sustained |
| **Tier 1 — Growth** | 500-5K | 100-500 req/min | Cloud Run (2-5), 2 workers/tier | P95 > 1s, queue > 50 |
| **Tier 2 — Scale** | 5K-50K | 500-2K req/min | Cloud Run (5-10), auto-scale workers | Multi-region demand |
| **Tier 3 — Large** | 50K+ | 2K+ req/min | Kubernetes, dedicated DB | — |

### 6.2. Auto-Scaling Configuration

**Cloud Run:**

| Parameter | MVP | Growth |
|---|---|---|
| Min instances | 0 | 1 |
| Max instances | 2 | 10 |
| Scale up trigger | Concurrent > 50 | Concurrent > 60 |
| Scale down | 5 min idle | 10 min idle |
| CPU allocation | 1 | 2 |
| Memory | 512MB | 1GB |

**Workers (Phase 3):**

| Parameter | Value |
|---|---|
| Min workers per tier | 0 (tier 1-3), 1 (tier 0,4) |
| Max workers per tier | 5 |
| Scale up trigger | Queue depth > 10 OR wait time > 5 min |
| Scale down trigger | Queue empty for 10 min |

### 6.3. Performance Optimization Checklist

| Phase | Optimization | Effort | Impact |
|---|---|---|---|
| **MVP** | CDN for static assets (Cloudflare auto) | Low | High |
| **MVP** | Firestore indexes for common queries | Low | High |
| **MVP** | Gzip/Brotli compression (Cloudflare auto) | Low | Medium |
| **Growth** | Connection pooling (Firestore handles) | Low | Medium |
| **Growth** | Image optimization (thumbnails) | Medium | Medium |
| **Scale** | Redis cache for frequent queries | Medium | High |
| **Scale** | Read replicas (Firestore multi-region) | High | High |

---

## 7. Disaster Recovery

### 7.1. DR Strategy

| Aspect | MVP | Scale |
|---|---|---|
| **Strategy** | Backup & Restore | Pilot Light |
| **RPO** | 24h (daily backup) | 1h (continuous) |
| **RTO** | 4h | 1h |
| **Backup Location** | Same region, Firestore native | Cross-region (GCS) |
| **DR Test** | Quarterly | Monthly |

### 7.2. Disaster Scenarios

| Scenario | Detection | Response | Recovery Time |
|---|---|---|---|
| **Cloud Run crash** | Health check fail | Auto-restart by Cloud Run | < 2 min |
| **Region outage** | GCP status page | Activate DR region (Phase 3) | 2-4h |
| **Firestore corruption** | Data inconsistency | Point-in-time recovery | 1-2h |
| **R2 outage** | Cloudflare status | Wait for recovery (no local backup) | Dependent on Cloudflare |
| **Security breach** | Alert / anomaly | Rotate secrets, isolate, investigate | Hours-days |
| **Accidental deletion** | User report | Restore from Firestore backup | 30min-2h |

### 7.3. Incident Response

```
1. DETECT
   • Alert fires (monitoring) OR user report
   • On-call receives notification

2. ASSESS
   • Severity: Critical / Major / Minor
   • Scope: Single user / All users / Partial
   • Impact: Data loss? Revenue impact?

3. COMMUNICATE
   • Internal: Slack channel, stakeholders
   • External: Status page (if major), user notification

4. MITIGATE
   • Quick fix if possible (rollback, restart)
   • Failover if needed

5. RESOLVE
   • Root cause fix
   • Deploy fix

6. POST-MORTEM
   • Timeline of events
   • Root cause analysis
   • Action items to prevent recurrence
   • Update runbook if needed
```

---

## 8. Operational Runbook

### 8.1. Common Operations

| Operation | Method | Frequency | Who |
|---|---|---|---|
| Deploy staging | Auto on merge to main | Multiple/day | CI/CD |
| Deploy production | Manual approval after staging | Weekly | Tech Lead |
| Rollback | `gcloud run deploy --revision` or GitHub Actions | As needed | DevOps/Tech Lead |
| View logs | GCP Console or `gcloud logging read` | Daily | Dev |
| Restart service | Cloud Run: redeploy same image | As needed | DevOps |
| Manual backup | Firestore export to GCS | Before migrations | DevOps |
| Restore backup | Firestore import from GCS | Emergency | DevOps |
| Rotate secrets | Update Secret Manager + redeploy | Quarterly / on breach | DevOps |
| Scale workers | Update Worker Manager config | As needed | DevOps |

### 8.2. Access Management

| Resource | Who | Method | Rotation |
|---|---|---|---|
| GCP Console | CTO, Tech Lead, DevOps | IAM + MFA | Quarterly review |
| Cloudflare Dashboard | CTO, Tech Lead, DevOps | Account + MFA | Quarterly review |
| Production logs | Dev (read-only), DevOps (full) | IAM roles | On team change |
| Firestore (prod) | DevOps (via console), App (service account) | IAM | On team change |
| CI/CD secrets | DevOps, Tech Lead | GitHub Secrets | On team change |
| GPU providers | DevOps | API keys in Secret Manager | Quarterly |

### 8.3. Maintenance Windows

| Activity | Schedule | Duration | User Impact | Notification |
|---|---|---|---|---|
| Routine deploy | Business hours | < 5 min | None (rolling) | Internal only |
| Minor migration | Business hours | < 15 min | None | Internal only |
| Major migration | Off-peak (weekend night) | 30min-1h | Possible brief downtime | 24h before |
| Infrastructure upgrade | Off-peak | 1-2h | Possible downtime | 48h before |
| Critical security patch | ASAP | < 30 min | Possible brief | Post-fix |

---

## Summary

```
--- FEEDBACK APPENDIX (SA → PO/BA) ---

Đề xuất cập nhật PO:
  - Thêm RULE: File validation includes virus scan (future, not MVP)
  - Clarify: Tier 4 VIP cluster details cần spec riêng (Phase 3)

Đề xuất cập nhật BA:
  - Add UC: Admin review dead letter queue
  - Add BR: Grace period = 50% of estimated time (derived from Q-05)

Technical Risks phát hiện:
  - Risk: Vast.ai spot preemption → Mitigation: Retry logic, Phase 3 multi-provider
  - Risk: Firestore cost spike at scale → Mitigation: Monitor, migration trigger at $500/month
  - Risk: No circuit breaker MVP → Mitigation: P1 before production

Câu hỏi kỹ thuật cần stakeholder quyết định:
  - Q1: Tier 4 VIP cluster specifics? Recommendation: Define Phase 3, placeholder for now
  - Q2: Multi-region DR priority? Recommendation: Phase 3, single region sufficient for MVP
  - Q3: Log retention requirements for compliance? Recommendation: 2 years for audit, 30 days for app logs

--- ✅ PHASE 3 COMPLETE ---
```

---

*Tài liệu này mô tả chi tiết về infrastructure và deployment. Đây là tài liệu cuối cùng trong bộ SA, cung cấp hướng dẫn cho DevOps và team vận hành.*
