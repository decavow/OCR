# OCR Platform Local MVP1 - Planning Index

> Version: 3.0 | Phase: Local MVP 1
> Aligned with: SA v3.1 + Actual Implementation
> Last Updated: 2025-02

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
| 03 | **API Design** | Chi tiết API endpoints (user + admin + internal) | [03_api_design.md](./03_api_design.md) |
| 04 | **Component Constraints** | Ràng buộc cho output của từng component | [04_component_constraints.md](./04_component_constraints.md) |

---

## Key Changes from v2.0 to v3.0 (Aligned with Actual Implementation)

| Aspect | Old (v2.0) | New (v3.0 - Actual) |
|--------|------------|---------------------|
| **Directory Names** | `frontend/`, `backend/`, `worker/` | `01_frontend/`, `02_backend/`, `03_worker/` |
| **Backend Port** | 8080 | **8000** |
| **Internal URL** | `/internal/*` | **`/api/v1/internal/*`** |
| **Job Status Update** | POST | **PATCH** |
| **Database File** | `ocr_platform.db` | **`ocr_fresh.db`** |
| **Service Model** | Single `Service` table | **`ServiceType` + `ServiceInstance`** two-level model |
| **Service Status** | enabled (bool) | **PENDING/APPROVED/DISABLED/REJECTED** (admin workflow) |
| **Worker Identity** | `WORKER_SERVICE_ID` | **`WORKER_SERVICE_TYPE` + auto-generated instance_id** |
| **Worker Engines** | Tesseract only | **PaddleOCR (GPU) + Tesseract (CPU) + PaddleOCR-VL (GPU, structured)** |
| **Worker Deploy** | In root docker-compose | **Separate compose per engine** in `03_worker/deploy/` |
| **Frontend in Compose** | Yes | **No** (separate deploy) |
| **Session Token** | Session.id as token | **Session.token** (separate field) |
| **User Admin** | No | **`is_admin` flag** + CLI tools |
| **Job output_format** | On Job model | **On Request only** (removed from Job) |
| **Heartbeat Reference** | `service_id` | **`instance_id`** (FK -> service_instances) |
| **Default Retention** | 24 hours | **168 hours** (7 days) |
| **Worker Registration** | Seed on startup | **Self-registration** (POST /internal/register) |
| **Admin Panel** | Not planned | **AdminServicesPage** (approve/reject/disable) |
| **DLQ Subject** | `dlq.ocr.{method}.tier{tier}` | **`dlq.{method}.tier{tier}`** |
| **Container Names** | Generic | **Prefixed:** `ocr-minio`, `ocr-nats`, `ocr-backend` |
| **Network** | Default | **Named:** `ocr-network` (bridge) |

---

## Architecture Summary

```
┌────────────────────────────────────────────────────────────────┐
│                      LAYER ARCHITECTURE                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EDGE LAYER                                                     │
│  ├── Frontend (React) — 01_frontend/ — separate deploy         │
│  ├── API Server (FastAPI:8000) — 02_backend/                   │
│  └── MinIO (Object Storage) — container: ocr-minio             │
│                                                                 │
│  ORCHESTRATION LAYER                                            │
│  ├── Auth Module (+ is_admin role)                              │
│  ├── Upload Module (validate all → then store)                  │
│  ├── Job Module (includes Retry Orchestrator)                  │
│  ├── File Proxy Module — Bridge to Edge Storage                │
│  ├── Admin Module — Service Type CRUD                          │
│  ├── NATS JetStream (OCR_JOBS, OCR_DLQ) — container: ocr-nats │
│  └── SQLite Database (ocr_fresh.db)                            │
│                                                                 │
│  PROCESSING LAYER                                               │
│  └── OCR Workers — 03_worker/ — separate deploy per engine     │
│      ├── PaddleOCR Worker (GPU) — deploy/paddle-text/          │
│      ├── Tesseract Worker (CPU) — deploy/tesseract-cpu/        │
│      └── PaddleOCR-VL Worker (GPU) — deploy/paddle-vl/        │
│      Each worker:                                               │
│      ├── Self-registers on startup                             │
│      ├── Pulls from NATS (specific subject)                    │
│      ├── Downloads via File Proxy                              │
│      ├── Processes with engine (Paddle/Tesseract)              │
│      ├── Uploads via File Proxy                                │
│      ├── Reports status (PATCH) to Orchestrator                │
│      ├── Sends heartbeat every 30s                             │
│      └── NO storage credentials (enforced)                     │
│                                                                 │
│  KEY RULES:                                                     │
│  Worker → File Proxy → MinIO (no direct access)               │
│  Admin approves ServiceType → Workers get access_key           │
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
- [Docker Compose](./01_code_structure.md#6-docker-compose-services)

### 2. Layer Processing Logic
- [Architecture Overview](./02_layer_processing_logic.md#1-architecture-overview)
- [Edge Layer](./02_layer_processing_logic.md#2-edge-layer-processing)
- [Orchestration Layer](./02_layer_processing_logic.md#3-orchestration-layer-processing)
- [Retry Orchestrator](./02_layer_processing_logic.md#34-retry-orchestrator-flow-retry-at-orchestration-layer)
- [Heartbeat Monitor](./02_layer_processing_logic.md#35-heartbeat-monitor-flow)
- [Worker Registration](./02_layer_processing_logic.md#37-worker-registration-flow-new)
- [Admin Service Management](./02_layer_processing_logic.md#38-admin-service-management-flow-new)
- [Processing Layer](./02_layer_processing_logic.md#4-processing-layer)
- [Job State Machine](./02_layer_processing_logic.md#6-job-state-machine-complete)

### 3. API Design
- [User Authentication](./03_api_design.md#3-authentication-endpoints)
- [Upload Endpoint](./03_api_design.md#4-upload-endpoints)
- [Request Endpoints](./03_api_design.md#5-request-endpoints)
- [Job Endpoints](./03_api_design.md#6-job-endpoints)
- [Admin Endpoints](./03_api_design.md#8-admin-endpoints-new)
- [Internal: Register](./03_api_design.md#101-worker-registration)
- [Internal: File Proxy](./03_api_design.md#103-file-proxy---download-file)
- [Internal: Job Status (PATCH)](./03_api_design.md#105-update-job-status)
- [Internal: Heartbeat](./03_api_design.md#106-heartbeat)
- [Job Status Enum](./03_api_design.md#12-job-status-enum)

### 4. Component Constraints
- [Layer Constraints](./04_component_constraints.md#2-layer-constraints-critical)
- [Worker Constraints](./04_component_constraints.md#9-ocr-worker-constraints)
- [Retry Behavior](./04_component_constraints.md#93-retry-behavior-critical)
- [State Machine](./04_component_constraints.md#61-state-machine-transitions-critical)
- [ServiceType/Instance](./04_component_constraints.md#12-service-type--instance-constraints-new)
- [MinIO Access Control](./04_component_constraints.md#102-access-control)

---

## Implementation Checklist

### Infrastructure
- [x] Docker Compose with layer separation (infra + backend)
- [x] NATS JetStream (OCR_JOBS + OCR_DLQ streams)
- [x] MinIO (uploads, results, deleted buckets)
- [x] SQLite with WAL mode
- [x] Worker containers WITHOUT MinIO credentials
- [x] Named network: ocr-network (bridge)
- [x] Shared .env file for all compose files

### Backend - Auth Module
- [x] User registration (bcrypt)
- [x] User login (session token — separate from session ID)
- [x] Session validation (by token field)
- [x] Logout
- [x] `is_admin` flag on User model

### Backend - Upload Module
- [x] File validation (MIME, magic bytes, size)
- [x] Batch validation (count, total size)
- [x] All-files-first validation (validate all before storing)
- [x] MinIO upload (Edge layer access)
- [x] Request + Job creation
- [x] output_format + retention_hours on Request (not Job)

### Backend - Job Module
- [x] Full state machine (all states)
- [x] SUBMITTED -> VALIDATING -> QUEUED transition
- [x] Status aggregation (including PARTIAL_SUCCESS)
- [x] Cancel request (QUEUED jobs only)
- [x] **Retry Orchestrator** (retry at Orchestration, not Worker)
- [x] Dead Letter Queue handling

### Backend - File Proxy Module
- [x] access_key validation (against ServiceType)
- [x] ACL check (method, tier from ServiceType)
- [x] POST /api/v1/internal/file-proxy/download
- [x] POST /api/v1/internal/file-proxy/upload

### Backend - Heartbeat
- [x] POST /api/v1/internal/heartbeat endpoint
- [x] Heartbeat table (references instance_id)
- [x] Heartbeat monitor (detect dead/stalled instances)

### Backend - Worker Registration (NEW)
- [x] POST /api/v1/internal/register
- [x] POST /api/v1/internal/deregister
- [x] ServiceType creation on first register
- [x] ServiceInstance lifecycle management

### Backend - Admin Module (NEW)
- [x] Admin endpoints: /api/v1/admin/service-types
- [x] Admin endpoints: /api/v1/admin/service-instances
- [x] Approve/Reject/Disable/Enable/Delete actions
- [x] CLI tools: create-admin, promote, demote

### Worker (Processing Layer)
- [x] **NO MinIO credentials** (enforced)
- [x] Self-registration on startup
- [x] Multi-engine support (PaddleOCR + Tesseract + PaddleOCR-VL)
- [x] Separate Dockerfiles (GPU + CPU)
- [x] Separate deploy configs per engine
- [x] NATS consumer (specific subject)
- [x] File download via File Proxy
- [x] Engine-specific processing (with pre/post processing)
- [x] Result upload via File Proxy
- [x] Status reporting (PATCH) to Orchestrator
- [x] **Error reporting (NOT retry)**
- [x] Heartbeat every 30s
- [x] Local file cleanup (mandatory)
- [x] Graceful shutdown (SIGTERM/SIGINT)

### Frontend
- [x] Login/Register pages
- [x] Sidebar navigation (MainLayout + Sidebar)
- [x] Dashboard with recent batches
- [x] Upload page (files + output_format + retention)
- [x] Batches list page
- [x] Batch detail with all job states
- [x] Result Viewer: split-panel, file navigation
- [x] Cancel button (for QUEUED jobs)
- [x] Polling (stop on terminal status)
- [x] Admin: Service Management page (approve/reject/disable)
- [x] Dark theme
- [x] Protected routes + AdminRoute guard

---

## Critical Design Decisions

| Decision | Rationale |
|----------|-----------|
| **MinIO in Edge Layer** | SA v3.1: "Edge layer luu tru file" |
| **ServiceType + ServiceInstance** | Two-level model: admin manages types, system manages instances |
| **Worker self-registration** | Workers register on startup, admin approves types |
| **Multi-engine workers** | PaddleOCR (GPU) + Tesseract (CPU) + PaddleOCR-VL (GPU, structured), separate deploys |
| **Retry at Orchestrator** | Worker stateless, Orchestrator has full context |
| **Worker no storage creds** | Layer separation, security |
| **File Proxy POST methods** | Body contains job_id for proper ACL |
| **Internal under /api/v1** | All routes share same prefix for consistency |
| **PATCH for job status** | Partial update semantics, not full replacement |
| **Container name networking** | Cross-compose DNS: ocr-minio, ocr-nats, ocr-backend |
| **Separate worker compose** | Each engine can be deployed/scaled independently |
| **Admin CLI tools** | create-admin, promote, demote via Makefile |
| **Shared .env** | Single source of truth for all compose files |

---

## Configuration Defaults

| Parameter | Value |
|-----------|-------|
| BACKEND_PORT | 8000 |
| MAX_FILE_SIZE_MB | 10 |
| MAX_BATCH_SIZE_MB | 50 |
| MAX_FILES_PER_BATCH | 20 |
| MAX_RETRIES | 3 |
| RETRY_DELAYS | 1s, 2s, 4s |
| JOB_TIMEOUT_SECONDS | 300 |
| HEARTBEAT_INTERVAL_MS | 30000 |
| HEARTBEAT_TIMEOUT_SECONDS | 90 |
| SESSION_EXPIRE_HOURS | 24 |
| DEFAULT_OUTPUT_FORMAT | txt (per-service: supported_output_formats) |
| DEFAULT_RETENTION_HOURS | 168 (7 days) |
| NATS_STREAM_NAME | OCR_JOBS |
| NATS_DLQ_STREAM_NAME | OCR_DLQ |

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
| 3.0 | 2025-02 | Aligned with actual implementation: Numbered dirs, port 8000, ServiceType/Instance model, multi-engine workers, admin panel, worker self-registration, PATCH for job status, internal under /api/v1, container name networking, shared .env |
