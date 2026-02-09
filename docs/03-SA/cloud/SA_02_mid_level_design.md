# OCR Platform — Detailed Component Design

> Tài liệu thiết kế chi tiết các component cho OCR Platform
> Version: 1.0 | Status: Draft
> References: `03-SA/SA_01_high_level_architecture.md`

---

## Table of Contents

1. [Component Interaction](#1-component-interaction)
2. [API Contracts](#2-api-contracts)
3. [Data Model Detail](#3-data-model-detail)
4. [Message Specifications](#4-message-specifications)
5. [Error Handling](#5-error-handling)

---

## 1. Component Interaction

### 1.1. Sequence Diagrams

#### Job Submission Flow

```
┌────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│ Client │     │   API   │     │   Job    │     │ Billing │     │Firestore │     │ Pub/Sub │
│        │     │ Gateway │     │ Service  │     │ Service │     │          │     │         │
└───┬────┘     └────┬────┘     └────┬─────┘     └────┬────┘     └────┬─────┘     └────┬────┘
    │               │               │               │               │               │
    │  POST /jobs   │               │               │               │               │
    │──────────────▶│               │               │               │               │
    │               │  forward      │               │               │               │
    │               │──────────────▶│               │               │               │
    │               │               │               │               │               │
    │               │               │ get file info │               │               │
    │               │               │───────────────────────────────▶               │
    │               │               │◀──────────────────────────────│               │
    │               │               │               │               │               │
    │               │               │ calculate cost│               │               │
    │               │               │──────────────▶│               │               │
    │               │               │               │               │               │
    │               │               │               │  check balance│               │
    │               │               │               │───────────────▶               │
    │               │               │               │◀──────────────│               │
    │               │               │               │               │               │
    │               │               │               │  hold credit  │               │
    │               │               │  START TXN    │───────────────▶               │
    │               │               │─ ─ ─ ─ ─ ─ ─ ─│               │               │
    │               │               │               │               │               │
    │               │               │  create job   │               │               │
    │               │               │───────────────────────────────▶               │
    │               │               │               │               │               │
    │               │               │  COMMIT TXN   │               │               │
    │               │               │─ ─ ─ ─ ─ ─ ─ ─│               │               │
    │               │               │               │               │               │
    │               │               │  publish job  │               │               │
    │               │               │──────────────────────────────────────────────▶│
    │               │               │               │               │               │
    │               │ job_id        │               │               │               │
    │◀──────────────│◀──────────────│               │               │               │
    │               │               │               │               │               │
```

#### Worker Processing Flow

```
┌─────────┐     ┌─────────┐     ┌────────┐     ┌──────────┐     ┌─────────┐
│ Worker  │     │ Pub/Sub │     │   R2   │     │Firestore │     │  Notif  │
│         │     │         │     │        │     │          │     │ Service │
└────┬────┘     └────┬────┘     └───┬────┘     └────┬─────┘     └────┬────┘
     │               │              │               │               │
     │  pull job     │              │               │               │
     │──────────────▶│              │               │               │
     │◀──────────────│              │               │               │
     │  job payload  │              │               │               │
     │               │              │               │               │
     │  update status: DISPATCHED   │               │               │
     │──────────────────────────────────────────────▶               │
     │               │              │               │               │
     │  download file│              │               │               │
     │─────────────────────────────▶│               │               │
     │◀────────────────────────────│               │               │
     │  file content │              │               │               │
     │               │              │               │               │
     │  update status: PROCESSING   │               │               │
     │──────────────────────────────────────────────▶               │
     │               │              │               │               │
     │  ┌───────────────────────┐   │               │               │
     │  │    OCR Processing     │   │               │               │
     │  │  (Tesseract, etc.)    │   │               │               │
     │  └───────────────────────┘   │               │               │
     │               │              │               │               │
     │  upload result│              │               │               │
     │─────────────────────────────▶│               │               │
     │◀────────────────────────────│               │               │
     │  result path  │              │               │               │
     │               │              │               │               │
     │  update status: COMPLETED    │               │               │
     │──────────────────────────────────────────────▶               │
     │               │              │               │               │
     │               │              │       trigger │               │
     │               │              │               │──────────────▶│
     │               │              │               │  notify user  │
     │               │              │               │               │
     │  ack message  │              │               │               │
     │──────────────▶│              │               │               │
     │               │              │               │               │
     │  delete local files          │               │               │
     │               │              │               │               │
```

### 1.2. Component Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT DEPENDENCY GRAPH                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────────┐                                                           │
│   │  API Gateway │                                                           │
│   └──────┬───────┘                                                           │
│          │                                                                    │
│          ├──────────────────┬──────────────────┬──────────────────┐          │
│          ▼                  ▼                  ▼                  ▼          │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│   │ Auth Service │   │ Job Service  │   │Upload Service│   │Billing Svc   │ │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
│          │                  │                  │                  │          │
│          │                  │                  │                  │          │
│          └──────────┬───────┴──────────────────┴──────────────────┘          │
│                     │                                                         │
│                     ▼                                                         │
│              ┌──────────────┐                                                │
│              │  Firestore   │                                                │
│              └──────────────┘                                                │
│                                                                               │
│   Job Service ───▶ Pub/Sub ───▶ OCR Worker ───▶ R2                          │
│                                      │                                       │
│                                      └────▶ Firestore                        │
│                                                                               │
│   Notification Service ◀─── Firestore (trigger)                             │
│                                                                               │
│   Worker Manager ───▶ Vast.ai API / RunPod API                               │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. API Contracts

### 2.1. API Design Principles

| Aspect | Standard |
|---|---|
| **Style** | REST (JSON over HTTPS) |
| **Base URL** | `https://api.ocr-platform.com/v1` |
| **Versioning** | URI-based (`/v1/...`) |
| **Authentication** | Bearer token in `Authorization` header |
| **Content-Type** | `application/json` |
| **Date Format** | ISO 8601 (`2024-01-15T10:30:00Z`) |
| **Pagination** | Cursor-based (`?cursor=xxx&limit=20`) |
| **Rate Limiting** | 100 req/min, `X-RateLimit-*` headers |

### 2.2. API Endpoints

#### Authentication

```yaml
# Register
Endpoint: POST /v1/auth/register
Description: Đăng ký tài khoản mới
Authentication: None
Authorization: Public

Request:
  Body:
    {
      "email": "string (required, email format)",
      "password": "string (required, min 8 chars, 1 upper, 1 number)"
    }

Response (201 Created):
    {
      "user": {
        "id": "usr_abc123",
        "email": "user@example.com",
        "created_at": "2024-01-15T10:30:00Z"
      },
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
      "expires_in": 3600
    }

Error Responses:
  400: { "error": "VALIDATION_ERROR", "message": "Invalid email format", "field": "email" }
  409: { "error": "EMAIL_EXISTS", "message": "Email already registered" }
```

```yaml
# Login
Endpoint: POST /v1/auth/login
Description: Đăng nhập với email/password
Authentication: None

Request:
  Body:
    {
      "email": "string (required)",
      "password": "string (required)"
    }

Response (200 OK):
    {
      "user": { "id": "usr_abc123", "email": "..." },
      "access_token": "...",
      "refresh_token": "...",
      "expires_in": 3600
    }

Error Responses:
  401: { "error": "INVALID_CREDENTIALS", "message": "Invalid email or password" }
  429: { "error": "TOO_MANY_ATTEMPTS", "message": "Account locked", "retry_after": 1800 }
```

```yaml
# OAuth Callback
Endpoint: POST /v1/auth/oauth/{provider}/callback
Description: Handle OAuth callback
Authentication: None
Path Parameters:
  - provider: "google" | "github"

Request:
  Body:
    {
      "code": "string (OAuth authorization code)"
    }

Response (200 OK):
    {
      "user": { ... },
      "access_token": "...",
      "refresh_token": "...",
      "is_new_user": true
    }
```

#### File Upload

```yaml
# Request Upload URL
Endpoint: POST /v1/uploads/presign
Description: Get presigned URL for direct upload to R2
Authentication: Bearer Token
Authorization: Authenticated users

Request:
  Body:
    {
      "filename": "string (required)",
      "content_type": "string (required, MIME type)",
      "content_length": "integer (required, bytes)"
    }

Response (200 OK):
    {
      "upload_id": "upl_xyz789",
      "upload_url": "https://r2.example.com/...",
      "expires_at": "2024-01-15T10:45:00Z"
    }

Error Responses:
  400: { "error": "UNSUPPORTED_FORMAT", "message": "Supported: PNG, JPEG, TIFF, BMP, WEBP, PDF" }
  400: { "error": "FILE_TOO_LARGE", "message": "Maximum file size is 50MB" }
```

```yaml
# Confirm Upload
Endpoint: POST /v1/uploads/{upload_id}/confirm
Description: Confirm upload and trigger validation
Authentication: Bearer Token

Path Parameters:
  - upload_id: string

Response (200 OK):
    {
      "file_id": "file_abc123",
      "filename": "invoice.pdf",
      "content_type": "application/pdf",
      "size": 1048576,
      "page_count": 10,
      "thumbnail_url": "https://...",
      "status": "ready"
    }

Error Responses:
  404: { "error": "UPLOAD_NOT_FOUND", "message": "Upload ID not found or expired" }
  422: { "error": "VALIDATION_FAILED", "message": "File corrupted or unreadable" }
  422: { "error": "TOO_MANY_PAGES", "message": "PDF exceeds 100 pages" }
```

#### Jobs

```yaml
# Create Job
Endpoint: POST /v1/jobs
Description: Submit OCR processing job
Authentication: Bearer Token

Request:
  Body:
    {
      "file_id": "string (required)",
      "method": "string (required, enum: ocr_simple, ocr_table, ocr_code)",
      "tier": "integer (required, 0-4)",
      "retention_days": "integer (optional, 1-30, default: 7)"
    }

Response (201 Created):
    {
      "job_id": "job_xyz789",
      "status": "SUBMITTED",
      "estimated_seconds": 120,
      "credit_held": 4000,
      "created_at": "2024-01-15T10:30:00Z"
    }

Error Responses:
  400: { "error": "INVALID_METHOD", "message": "Method must be ocr_simple, ocr_table, or ocr_code" }
  400: { "error": "INVALID_TIER", "message": "Tier must be 0-4" }
  402: { "error": "INSUFFICIENT_CREDIT", "message": "Not enough credit", "required": 4000, "balance": 3000 }
  404: { "error": "FILE_NOT_FOUND", "message": "File ID not found" }
  503: { "error": "TIER_UNAVAILABLE", "message": "Selected tier is temporarily unavailable" }
```

```yaml
# Get Job Status
Endpoint: GET /v1/jobs/{job_id}
Description: Get job status and details
Authentication: Bearer Token

Path Parameters:
  - job_id: string

Response (200 OK):
    {
      "job_id": "job_xyz789",
      "file_id": "file_abc123",
      "filename": "invoice.pdf",
      "method": "ocr_table",
      "tier": 2,
      "status": "COMPLETED",
      "page_count": 10,
      "credit_amount": 4000,
      "confidence": 0.95,
      "result_url": "https://presigned-url-to-result...",
      "created_at": "2024-01-15T10:30:00Z",
      "started_at": "2024-01-15T10:31:00Z",
      "completed_at": "2024-01-15T10:32:00Z"
    }

Error Responses:
  404: { "error": "JOB_NOT_FOUND", "message": "Job not found" }
```

```yaml
# List Jobs (History)
Endpoint: GET /v1/jobs
Description: List user's jobs with filtering
Authentication: Bearer Token

Query Parameters:
  - status: string (optional, filter by status)
  - method: string (optional, filter by method)
  - from_date: string (optional, ISO 8601)
  - to_date: string (optional, ISO 8601)
  - cursor: string (optional, pagination cursor)
  - limit: integer (optional, 1-50, default: 20)

Response (200 OK):
    {
      "jobs": [
        { "job_id": "...", "status": "COMPLETED", ... }
      ],
      "next_cursor": "eyJpZCI6Impv...",
      "total_count": 150
    }
```

```yaml
# Cancel Job
Endpoint: POST /v1/jobs/{job_id}/cancel
Description: Cancel a queued job
Authentication: Bearer Token

Path Parameters:
  - job_id: string

Response (200 OK):
    {
      "job_id": "job_xyz789",
      "status": "CANCELLED",
      "credit_refunded": 4000
    }

Error Responses:
  400: { "error": "CANNOT_CANCEL", "message": "Job is already processing" }
  404: { "error": "JOB_NOT_FOUND", "message": "Job not found" }
```

#### Billing

```yaml
# Get Balance
Endpoint: GET /v1/billing/balance
Description: Get current credit balance
Authentication: Bearer Token

Response (200 OK):
    {
      "balance": 500000,
      "currency": "VND"
    }
```

```yaml
# Create Checkout Session
Endpoint: POST /v1/billing/checkout
Description: Create Stripe checkout session for top-up
Authentication: Bearer Token

Request:
  Body:
    {
      "amount": "integer (required, min 50000)"
    }

Response (200 OK):
    {
      "checkout_url": "https://checkout.stripe.com/...",
      "session_id": "cs_xxx"
    }
```

```yaml
# List Transactions
Endpoint: GET /v1/billing/transactions
Description: List billing transactions
Authentication: Bearer Token

Query Parameters:
  - type: string (optional: topup, hold, deduct, refund)
  - from_date: string (optional)
  - to_date: string (optional)
  - cursor: string (optional)
  - limit: integer (optional)

Response (200 OK):
    {
      "transactions": [
        {
          "id": "txn_abc123",
          "type": "DEDUCT",
          "amount": -4000,
          "balance_after": 496000,
          "job_id": "job_xyz789",
          "description": "OCR job: invoice.pdf",
          "created_at": "2024-01-15T10:32:00Z"
        }
      ],
      "next_cursor": "..."
    }
```

#### Notifications

```yaml
# SSE Stream
Endpoint: GET /v1/notifications/stream
Description: Server-Sent Events stream for real-time notifications
Authentication: Bearer Token (in query param for SSE)

Query Parameters:
  - token: string (JWT token)

Response: SSE Stream
    event: notification
    data: {"type": "job_completed", "job_id": "job_xyz789", "message": "..."}

    event: notification
    data: {"type": "credit_low", "balance": 10000}
```

```yaml
# List Notifications
Endpoint: GET /v1/notifications
Description: List notifications with pagination
Authentication: Bearer Token

Response (200 OK):
    {
      "notifications": [
        {
          "id": "notif_abc123",
          "type": "job_completed",
          "message": "Job completed: invoice.pdf",
          "read": false,
          "data": { "job_id": "job_xyz789" },
          "created_at": "2024-01-15T10:32:00Z"
        }
      ],
      "unread_count": 5
    }
```

```yaml
# Mark as Read
Endpoint: POST /v1/notifications/{notification_id}/read
Description: Mark notification as read
Authentication: Bearer Token

Response (200 OK):
    { "success": true }
```

---

## 3. Data Model Detail

### 3.1. Firestore Collections

#### Users Collection

```javascript
// Collection: users
// Document ID: usr_<random>

{
  id: "usr_abc123",
  email: "user@example.com",
  password_hash: "$2b$12$...", // null if OAuth-only
  oauth_providers: [
    { provider: "google", provider_id: "123456789" }
  ],
  email_verified: true,
  created_at: Timestamp,
  updated_at: Timestamp
}

// Indexes:
// - email (unique)
// - oauth_providers.provider + oauth_providers.provider_id
```

#### Jobs Collection

```javascript
// Collection: jobs
// Document ID: job_<random>

{
  id: "job_xyz789",
  user_id: "usr_abc123",
  batch_id: "bat_def456", // optional
  file_id: "file_ghi789",
  file_name: "invoice.pdf",
  file_path: "sources/usr_abc123/file_ghi789/invoice.pdf",
  page_count: 10,
  method: "ocr_table", // ocr_simple | ocr_table | ocr_code
  tier: 2,
  status: "COMPLETED", // SUBMITTED | VALIDATING | QUEUED | DISPATCHED | PROCESSING | COMPLETED | REJECTED | CANCELLED | FAILED | RETRYING | DEAD_LETTER
  credit_amount: 4000,
  retention_days: 7,
  result_path: "results/job_xyz789/output.json",
  result_format: "json",
  confidence: 0.95,
  error_reason: null,
  retry_count: 0,
  worker_id: "wrk_123",
  created_at: Timestamp,
  started_at: Timestamp,
  completed_at: Timestamp,
  expires_at: Timestamp // result expiration
}

// Indexes:
// - user_id + created_at (descending) - for history
// - user_id + status - for filtering
// - status + tier - for queue management
// - expires_at - for cleanup
```

#### BillingAccounts Collection

```javascript
// Collection: billingAccounts
// Document ID: acc_<random>

{
  id: "acc_mno123",
  user_id: "usr_abc123",
  balance: 500000, // VND
  total_topup: 1000000,
  total_spent: 500000,
  low_credit_threshold: 100000, // user configurable
  created_at: Timestamp,
  updated_at: Timestamp
}

// Indexes:
// - user_id (unique)
```

#### Transactions Collection

```javascript
// Collection: transactions
// Document ID: txn_<random>

{
  id: "txn_pqr456",
  account_id: "acc_mno123",
  type: "DEDUCT", // TOPUP | HOLD | DEDUCT | REFUND
  amount: 4000, // positive for all types
  balance_after: 496000,
  job_id: "job_xyz789", // optional
  stripe_payment_id: "pi_xxx", // for TOPUP
  description: "OCR job: invoice.pdf",
  created_at: Timestamp
}

// Indexes:
// - account_id + created_at (descending)
// - account_id + type
// - job_id - for finding holds
```

#### Notifications Collection

```javascript
// Collection: notifications
// Document ID: notif_<random>

{
  id: "notif_abc123",
  user_id: "usr_abc123",
  type: "job_completed", // job_completed | job_failed | credit_low | file_expiring | etc.
  title: "Job Completed",
  message: "Your OCR job for invoice.pdf has completed.",
  data: {
    job_id: "job_xyz789",
    filename: "invoice.pdf"
  },
  read: false,
  created_at: Timestamp,
  expires_at: Timestamp // 30 days TTL
}

// Indexes:
// - user_id + created_at (descending)
// - user_id + read
// - expires_at - for TTL cleanup
```

### 3.2. R2 Object Structure

```
sources/
├── {user_id}/
│   └── {file_id}/
│       ├── original.pdf          # Original uploaded file
│       └── thumbnail.png         # Generated thumbnail

results/
└── {job_id}/
    ├── output.txt               # For ocr_simple
    ├── output.json              # For ocr_table (structured)
    ├── output.csv               # For ocr_table (tabular)
    ├── output.md                # For ocr_code
    └── metadata.json            # Processing metadata
```

---

## 4. Message Specifications

### 4.1. Pub/Sub Message Format

```json
// Topic: tier-{n}-jobs (n = 0, 1, 2, 3, 4)
// Job message
{
  "job_id": "job_xyz789",
  "user_id": "usr_abc123",
  "file_url": "https://presigned-url-to-source...",
  "method": "ocr_table",
  "tier": 2,
  "page_count": 10,
  "config": {
    "language": "eng+vie",
    "output_format": "json",
    "retention_days": 7
  },
  "retry_count": 0,
  "created_at": "2024-01-15T10:30:00Z",
  "message_id": "msg_abc123"
}
```

### 4.2. SSE Event Format

```
// Notification event
event: notification
data: {
  "id": "notif_abc123",
  "type": "job_completed",
  "title": "Job Completed",
  "message": "Your OCR job for invoice.pdf has completed.",
  "data": {
    "job_id": "job_xyz789"
  },
  "created_at": "2024-01-15T10:32:00Z"
}

// Job status update event
event: job_update
data: {
  "job_id": "job_xyz789",
  "status": "PROCESSING",
  "progress": 50,
  "updated_at": "2024-01-15T10:31:30Z"
}

// Heartbeat (every 30s)
event: heartbeat
data: {}
```

---

## 5. Error Handling

### 5.1. Error Code Catalog

| Code | HTTP Status | Description |
|---|---|---|
| VALIDATION_ERROR | 400 | Request validation failed |
| INVALID_METHOD | 400 | Invalid OCR method |
| INVALID_TIER | 400 | Invalid tier number |
| UNSUPPORTED_FORMAT | 400 | File format not supported |
| FILE_TOO_LARGE | 400 | File exceeds size limit |
| TOO_MANY_PAGES | 400 | PDF exceeds page limit |
| CANNOT_CANCEL | 400 | Job cannot be cancelled |
| UNAUTHORIZED | 401 | Authentication required |
| INVALID_CREDENTIALS | 401 | Wrong email/password |
| TOKEN_EXPIRED | 401 | JWT token expired |
| FORBIDDEN | 403 | Access denied |
| NOT_FOUND | 404 | Resource not found |
| FILE_NOT_FOUND | 404 | File ID not found |
| JOB_NOT_FOUND | 404 | Job ID not found |
| UPLOAD_NOT_FOUND | 404 | Upload ID not found |
| EMAIL_EXISTS | 409 | Email already registered |
| INSUFFICIENT_CREDIT | 402 | Not enough credit |
| VALIDATION_FAILED | 422 | File validation failed |
| TOO_MANY_ATTEMPTS | 429 | Rate limit exceeded |
| TIER_UNAVAILABLE | 503 | Tier temporarily unavailable |
| INTERNAL_ERROR | 500 | Unexpected server error |

### 5.2. Retry Strategy

| Component | Max Retries | Backoff | Notes |
|---|---|---|---|
| API calls to Stripe | 3 | Exponential (1s, 2s, 4s) | With jitter |
| Worker job processing | 1 | Immediate (re-queue) | At orchestrator level |
| Pub/Sub message | Automatic | Pub/Sub handles | With dead letter |
| Firestore operations | 3 | Exponential | Transient errors only |

### 5.3. Circuit Breaker (Phase 2+)

```javascript
// Circuit breaker config for external services
const circuitBreakerConfig = {
  stripe: {
    failureThreshold: 5,      // Open after 5 failures
    successThreshold: 3,      // Close after 3 successes
    timeout: 30000,           // Half-open after 30s
  },
  gpuProviders: {
    failureThreshold: 3,
    successThreshold: 2,
    timeout: 60000,
  }
};
```

---

## Traceability

| API Endpoint | BA Use Case | PO Feature |
|---|---|---|
| POST /auth/register | UC-001 | F-001 |
| POST /auth/login | UC-001 | F-001 |
| POST /uploads/presign | UC-002 | F-002 |
| POST /jobs | UC-003 | F-003 |
| GET /jobs/{id} | UC-004 | F-004 |
| POST /jobs/{id}/cancel | UC-007 | F-010 |
| GET /v1/notifications/stream | UC-004 | F-008 |
| POST /billing/checkout | UC-006 | F-006 |
| GET /billing/transactions | UC-006 | F-006 |

---

*Tài liệu này mô tả chi tiết các component interaction và API contracts. Implementation details được mô tả trong SA_03_low_level_design.md.*
