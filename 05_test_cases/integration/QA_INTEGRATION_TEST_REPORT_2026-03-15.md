# QA Integration Test Report — 2026-03-15

## Overview

**68 integration tests** written and all passing. Tests cover the full OCR Platform backend stack using **real SQLite (in-memory)** and **FastAPI TestClient** with mocked external services (MinIO, NATS).

## Test Suites

### 1. Repository Integration Tests (`test_repo_integration.py`) — 35 tests

| ID | Test | Status |
|---|---|:---:|
| RP-001 | Create user and retrieve by email | PASS |
| RP-002 | Email exists check | PASS |
| RP-003 | Soft delete hides from queries | PASS |
| RP-004 | Count active users with admin exclusion | PASS |
| RP-005 | Paginated user listing | PASS |
| RP-006 | Create session and get valid | PASS |
| RP-007 | Expired session not returned | PASS |
| RP-008 | Delete sessions by user | PASS |
| RP-009 | Create request and get active | PASS |
| RP-010 | Filter requests by status/method | PASS |
| RP-011 | Paginated request listing | PASS |
| RP-012 | Update status sets completed_at | PASS |
| RP-013 | Soft delete request | PASS |
| RP-014 | Increment completed/failed counters | PASS |
| RP-015 | New job default SUBMITTED status | PASS |
| RP-016 | PROCESSING sets started_at | PASS |
| RP-017 | COMPLETED calculates processing_time_ms | PASS |
| RP-018 | Error history JSON appended | PASS |
| RP-019 | Get jobs by request | PASS |
| RP-020 | Cancel only QUEUED jobs | PASS |
| RP-021 | Get processing jobs by worker | PASS |
| RP-022 | Increment retry count | PASS |
| RP-023 | Create files and get by request | PASS |
| RP-024 | Soft delete file | PASS |
| RP-025 | Total size by request | PASS |
| RP-026 | Register service type (PENDING) | PASS |
| RP-027 | Approve generates access key | PASS |
| RP-028 | Reject marks instances DEAD | PASS |
| RP-029 | Disable/enable cycle | PASS |
| RP-030 | can_handle method+tier check | PASS |
| RP-031 | Instance for APPROVED type → ACTIVE | PASS |
| RP-032 | Instance for PENDING type → WAITING | PASS |
| RP-033 | Stale instance detection | PASS |
| RP-034 | Cascade delete request → files → jobs | PASS |
| RP-035 | Audit log record and query | PASS |

### 2. Auth API Integration Tests (`test_api_auth_integration.py`) — 10 tests

| ID | Test | Status |
|---|---|:---:|
| IA-001 | Register new user returns token | PASS |
| IA-002 | Register duplicate email → 400 | PASS |
| IA-003 | Login valid credentials | PASS |
| IA-004 | Login wrong password → 401 | PASS |
| IA-005 | Login non-existent email → 401 | PASS |
| IA-006 | GET /me with valid token | PASS |
| IA-007 | GET /me without token → 401 | PASS |
| IA-008 | GET /me with invalid token → 401 | PASS |
| IA-009 | Logout invalidates session | PASS |
| IA-010 | Full flow: register → login → me → logout | PASS |

### 3. Internal API Integration Tests (`test_api_internal_integration.py`) — 15 tests

| ID | Test | Status |
|---|---|:---:|
| II-001 | Worker registration new type → PENDING/WAITING | PASS |
| II-002 | Worker registration approved type → ACTIVE + key | PASS |
| II-003 | Worker registration rejected type → 403 | PASS |
| II-004 | Re-register existing instance | PASS |
| II-005 | Heartbeat approved instance → continue | PASS |
| II-006 | Heartbeat waiting → approved + key | PASS |
| II-007 | Heartbeat disabled type → drain | PASS |
| II-008 | Heartbeat rejected type → shutdown | PASS |
| II-009 | Heartbeat unknown instance → 404 | PASS |
| II-010 | Job status QUEUED → PROCESSING | PASS |
| II-011 | Job status PROCESSING → COMPLETED | PASS |
| II-012 | Job status PROCESSING → FAILED | PASS |
| II-013 | Invalid access key → 403 | PASS |
| II-014 | Invalid status transition → 404 | PASS |
| II-015 | Deregister marks instance DEAD | PASS |

### 4. Lifecycle Integration Tests (`test_lifecycle_integration.py`) — 8 tests

| ID | Test | Status |
|---|---|:---:|
| LF-001 | Single job → COMPLETED → request COMPLETED | PASS |
| LF-002 | Multi-job partial failure → PARTIAL_SUCCESS | PASS |
| LF-003 | All jobs failed → request FAILED | PASS |
| LF-004 | Cancel request cancels QUEUED jobs | PASS |
| LF-005 | Retriable failure requeues job | PASS |
| LF-006 | Max retries → DEAD_LETTER | PASS |
| LF-007 | Worker register → approve → heartbeat lifecycle | PASS |
| LF-008 | Full E2E: user → request → worker → completed | PASS |

## Architecture

```
00_test/integration/
├── conftest.py       # In-memory SQLite, FastAPI TestClient, fixtures
├── helpers.py        # Shared helper functions (create_user, etc.)
├── test_repo_integration.py          # 35 repository CRUD tests
├── test_api_auth_integration.py      # 10 auth endpoint tests
├── test_api_internal_integration.py  # 15 internal endpoint tests
└── test_lifecycle_integration.py     #  8 lifecycle flow tests
```

**Key approach:**
- In-memory SQLite with `StaticPool` (shared connection)
- FastAPI `TestClient` with dependency overrides
- MinIO and NATS mocked (`AsyncMock`)
- Real bcrypt password hashing
- Real SQLAlchemy ORM + state machine logic
- Tables cleaned between tests for isolation

## Full Test Suite Summary

| Suite | Tests | Status |
|---|:---:|:---:|
| Backend Unit | 170 | ALL PASS |
| Worker Unit | 223 | ALL PASS |
| Contract & Flow | 122 | ALL PASS |
| **Integration** | **68** | **ALL PASS** |
| **TOTAL** | **583** | **ALL PASS** |
