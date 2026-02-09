# OCR Platform Local MVP1 - Planning Index

> Version: 2.0 | Phase: Local MVP 1
> Aligned with: SA v3.1
> Last Updated: 2024-01-15

---

## Overview

Tài liệu planning cho việc implement OCR Platform Local MVP Phase 1.

**Reference:** [SA v3.1 - System Architecture](../../03-SA/local/SA_local_mvp1_architecture.md)

---

## Documents

| # | Document | Description | Link |
|---|----------|-------------|------|
| 01 | **Code Structure** | Cấu trúc thư mục, files, layer mapping | [01_code_structure.md](./01_code_structure.md) |
| 02 | **Layer Processing Logic** | Logic xử lý, diagrams, sequence diagrams | [02_layer_processing_logic.md](./02_layer_processing_logic.md) |
| 03 | **API Design** | Chi tiết API endpoints (user + internal) | [03_api_design.md](./03_api_design.md) |
| 04 | **Component Constraints** | Ràng buộc cho output của từng component | [04_component_constraints.md](./04_component_constraints.md) |

---

## Key Changes from SA v2.0 to v3.1

| Aspect | Old (v2.0) | New (v3.1) |
|--------|------------|------------|
| **MinIO Location** | Unclear | **Edge Layer** |
| **Retry Logic** | Worker retries | **Orchestrator retries** |
| **Job States** | Basic | Full: SUBMITTED, VALIDATING, QUEUED, PROCESSING, RETRYING, COMPLETED, FAILED, REJECTED, CANCELLED, DEAD_LETTER |
| **Heartbeat** | Basic | Full protocol with progress, error_count |
| **Dead Letter Queue** | Not defined | `dlq.ocr.{method}.tier{tier}` |
| **File Proxy API** | GET endpoints | **POST endpoints** with job_id in body |
| **Per-request config** | Not supported | `output_format`, `retention_hours` |

---

## Architecture Summary

```
┌────────────────────────────────────────────────────────────────┐
│                      LAYER ARCHITECTURE                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EDGE LAYER                                                     │
│  ├── Frontend (React)                                          │
│  ├── API Server (FastAPI)                                      │
│  └── MinIO (Object Storage) ← Storage lives here               │
│                                                                 │
│  ORCHESTRATION LAYER                                            │
│  ├── Auth Module                                                │
│  ├── Upload Module                                              │
│  ├── Job Module (includes Retry Orchestrator)                  │
│  ├── File Proxy Module ← Bridge to Edge Storage                │
│  ├── NATS JetStream (OCR_JOBS, OCR_DLQ)                        │
│  └── SQLite Database                                            │
│                                                                 │
│  PROCESSING LAYER                                               │
│  └── OCR Worker ← NO storage credentials                       │
│      ├── Pulls from NATS                                       │
│      ├── Downloads via File Proxy                              │
│      ├── Processes with Tesseract                              │
│      ├── Uploads via File Proxy                                │
│      ├── Reports status to Orchestrator                        │
│      └── Sends heartbeat every 30s                             │
│                                                                 │
│  KEY RULE: Worker → File Proxy → MinIO (no direct access)      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Quick Navigation

### 1. Code Structure
- [Root Directory](./01_code_structure.md#1-root-directory-structure)
- [Frontend Structure](./01_code_structure.md#2-frontend-structure-react--typescript--vite)
- [Backend Structure](./01_code_structure.md#3-backend-structure-fastapi--python)
- [Worker Structure](./01_code_structure.md#4-worker-structure-python---processing-layer)
- [Database Models](./01_code_structure.md#5-database-models-sqlite---orchestration-layer)
- [Docker Compose](./01_code_structure.md#7-docker-compose-services)

### 2. Layer Processing Logic
- [Architecture Overview](./02_layer_processing_logic.md#1-architecture-overview)
- [Edge Layer](./02_layer_processing_logic.md#2-edge-layer-processing)
- [Orchestration Layer](./02_layer_processing_logic.md#3-orchestration-layer-processing)
- [Retry Orchestrator](./02_layer_processing_logic.md#34-retry-orchestrator-flow-new---retry-at-orchestration-layer)
- [Heartbeat Monitor](./02_layer_processing_logic.md#35-heartbeat-monitor-flow-new)
- [Processing Layer](./02_layer_processing_logic.md#4-processing-layer)
- [Job State Machine](./02_layer_processing_logic.md#6-job-state-machine-complete)

### 3. API Design
- [User Authentication](./03_api_design.md#3-authentication-endpoints)
- [Upload Endpoint](./03_api_design.md#4-upload-endpoints)
- [Request Endpoints](./03_api_design.md#5-request-endpoints)
- [Job Endpoints](./03_api_design.md#6-job-endpoints)
- [Internal: File Proxy](./03_api_design.md#81-file-proxy---download-file)
- [Internal: Heartbeat](./03_api_design.md#84-heartbeat)
- [Job Status Enum](./03_api_design.md#10-job-status-enum)

### 4. Component Constraints
- [Layer Constraints](./04_component_constraints.md#2-layer-constraints-critical)
- [Worker Constraints](./04_component_constraints.md#9-ocr-worker-constraints)
- [Retry Behavior](./04_component_constraints.md#93-retry-behavior-critical)
- [State Machine](./04_component_constraints.md#61-state-machine-transitions-critical)
- [MinIO Access Control](./04_component_constraints.md#102-access-control)

---

## Implementation Checklist

### Infrastructure
- [ ] Docker Compose with layer separation
- [ ] NATS JetStream (OCR_JOBS + OCR_DLQ streams)
- [ ] MinIO (uploads, results, deleted buckets)
- [ ] SQLite with WAL mode
- [ ] Worker container WITHOUT MinIO credentials

### Backend - Auth Module
- [ ] User registration (bcrypt)
- [ ] User login (session token)
- [ ] Session validation
- [ ] Logout

### Backend - Upload Module
- [ ] File validation (MIME, magic bytes, size)
- [ ] Batch validation (count, total size)
- [ ] MinIO upload (Edge layer access)
- [ ] Request + Job creation
- [ ] output_format + retention_hours support

### Backend - Job Module
- [ ] Full state machine (all states)
- [ ] SUBMITTED → VALIDATING → QUEUED transition
- [ ] Status aggregation (including PARTIAL_SUCCESS)
- [ ] Cancel request (QUEUED jobs only)
- [ ] **Retry Orchestrator** (retry logic here, not Worker)
- [ ] Dead Letter Queue handling

### Backend - File Proxy Module
- [ ] access_key validation
- [ ] ACL check (method, tier)
- [ ] POST /internal/file-proxy/download
- [ ] POST /internal/file-proxy/upload
- [ ] Audit logging

### Backend - Heartbeat
- [ ] POST /internal/heartbeat endpoint
- [ ] Heartbeat table storage
- [ ] Heartbeat monitor (detect dead/stalled workers)

### Worker (Processing Layer)
- [ ] **NO MinIO credentials** (enforced)
- [ ] NATS consumer (specific subject)
- [ ] File download via File Proxy
- [ ] Tesseract OCR processing
- [ ] Result upload via File Proxy
- [ ] Status reporting to Orchestrator
- [ ] **Error reporting (NOT retry)**
- [ ] Heartbeat every 30s
- [ ] Local file cleanup (mandatory)

### Frontend
- [ ] Login/Register pages
- [ ] Dashboard with request list
- [ ] Upload page (files + output_format + retention)
- [ ] Request detail with all job states
- [ ] Cancel button (for QUEUED jobs)
- [ ] Polling (stop on terminal status)
- [ ] Result download

---

## Critical Design Decisions

| Decision | Rationale |
|----------|-----------|
| **MinIO in Edge Layer** | SA v3.1: "Edge layer lưu trữ file" |
| **Retry at Orchestrator** | Worker stateless, Orchestrator has full context |
| **Worker no storage creds** | Layer separation, security, audit |
| **File Proxy POST methods** | Body contains job_id for proper ACL |
| **Heartbeat table** | Track worker health, detect issues |
| **Full state machine** | Handle all edge cases properly |
| **Dead Letter Queue** | Don't lose failed jobs, admin review |

---

## Configuration Defaults

| Parameter | Value |
|-----------|-------|
| MAX_FILE_SIZE_MB | 10 |
| MAX_BATCH_SIZE_MB | 50 |
| MAX_FILES_PER_BATCH | 20 |
| MAX_RETRIES | 3 |
| RETRY_DELAYS | 1s, 2s, 4s |
| JOB_TIMEOUT_SECONDS | 300 |
| HEARTBEAT_INTERVAL_MS | 30000 |
| HEARTBEAT_TIMEOUT_SECONDS | 90 |
| SESSION_EXPIRES_HOURS | 24 |
| DEFAULT_OUTPUT_FORMAT | txt |
| DEFAULT_RETENTION_HOURS | 24 |

---

## References

- [System Architecture v3.1](../../03-SA/local/SA_local_mvp1_architecture.md)
- [Product Owner Document](../../01-PO/local/PO_phase1_local.md)
- [Business Analysis Document](../../02-BA/local/BA_business_analysis.md)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-15 | Initial planning documents |
| 2.0 | 2024-01-15 | Aligned with SA v3.1: MinIO in Edge, Retry at Orchestrator, Full state machine, Heartbeat protocol, Dead Letter Queue |
