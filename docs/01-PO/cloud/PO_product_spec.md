# OCR Platform — Product Specification

> Tài liệu Product Specification cho OCR Platform
> Version: 1.0 | Status: Draft
> Created based on: `docs/detailed_requirements.md`

---

## Table of Contents

1. [Context & Objective](#part-1-context--objective)
2. [Target Audience](#part-2-target-audience)
3. [Functional Requirements](#part-3-functional-requirements)
4. [User Experience](#part-4-user-experience)
5. [Success Metrics](#part-5-success-metrics)
6. [Roadmap](#part-6-roadmap)
7. [Constraints](#part-7-constraints)

---

## PART 1: CONTEXT & OBJECTIVE

### 1.1. Problem Statement

**Doanh nghiệp nhỏ và cá nhân** đang gặp vấn đề **chuyển đổi tài liệu giấy/scan sang văn bản số** khi **cần xử lý hoá đơn, hợp đồng, báo cáo, hoặc mã nguồn in ấn**.

**Hậu quả:**
- Mất thời gian nhập liệu thủ công (trung bình 15-30 phút/trang cho bảng biểu phức tạp)
- Chi phí cao nếu thuê dịch vụ OCR enterprise ($500-2000/tháng)
- Rủi ro sai sót khi nhập thủ công
- Không có giải pháp phù hợp cho tài liệu chuyên biệt (bảng biểu, mã nguồn)

**Hiện tại họ đang xử lý bằng:**
- Nhập liệu thủ công (tốn thời gian, dễ sai)
- Dùng các tool OCR miễn phí (Google Drive, Adobe) — chất lượng không ổn định, không hỗ trợ bảng biểu/code
- Dùng enterprise OCR (ABBYY, Kofax) — quá đắt cho SMB

**Hạn chế của các giải pháp hiện tại:**
- Tool miễn phí: Không hỗ trợ bảng biểu cấu trúc, output không structured, không API cho automation
- Enterprise: Chi phí subscription cao, over-featured cho nhu cầu đơn giản, setup phức tạp

> **[ASSUMPTION: A-01]** Thị trường SMB và cá nhân có nhu cầu OCR định kỳ (ước tính 10-100 trang/tháng) nhưng không đủ volume để justify subscription enterprise. Cần validate qua user research.

### 1.2. Product Objective

| Trường | Nội dung |
|---|---|
| **What** | OCR Platform là một nền tảng web giúp người dùng chuyển đổi tài liệu (ảnh, PDF) thành văn bản số với độ chính xác cao, hỗ trợ đa dạng loại tài liệu (text thuần, bảng biểu, mã nguồn). |
| **Why** | Thị trường đang thiếu giải pháp OCR pay-as-you-go với mức giá phải chăng cho SMB. Các giải pháp miễn phí không đủ chất lượng, trong khi enterprise quá đắt. Xu hướng số hoá tài liệu hậu COVID tạo nhu cầu lớn. |
| **How (high-level)** | Cung cấp platform web đơn giản với mô hình trả theo lượng sử dụng (credit-based), cho phép người dùng chọn phương pháp OCR phù hợp với loại tài liệu, và mức hạ tầng phù hợp với yêu cầu bảo mật/tốc độ. |

### 1.3. Project Scope

| Phạm vi | Nội dung |
|---|---|
| **In Scope (MVP)** | • Upload file ảnh (PNG, JPEG, TIFF, BMP, WEBP) và PDF<br>• 3 phương pháp OCR: ocr_simple, ocr_table, ocr_code<br>• 5 tiers hạ tầng với các mức bảo mật/giá khác nhau<br>• Mô hình pre-paid credit<br>• Web UI hoàn chỉnh (upload, tracking, result viewer, history)<br>• OAuth login (Google, GitHub) + email/password<br>• In-app notifications (real-time)<br>• Batch upload |
| **Out of Scope** | • Public API (chỉ Web UI)<br>• Multi-tenant / Organization management<br>• Email / Webhook notifications<br>• Handwriting recognition<br>• Realtime document editing<br>• Document storage / management (không phải cloud drive)<br>• Mobile app |
| **Future Scope** | 1. Admin dashboard (Phase 3)<br>2. Multi-language expansion beyond EN/VI (Phase 3+)<br>3. Handwriting recognition (Phase 4+)<br>4. Public API (Phase 4+)<br>5. White-label solution (Phase 5+) |

### 1.4. Competitive Landscape

| Đối thủ / Giải pháp thay thế | Điểm mạnh | Điểm yếu | Sản phẩm của ta khác ở đâu? |
|---|---|---|---|
| **Google Cloud Vision** | Accuracy cao, scalable, đa ngôn ngữ | Phức tạp setup, pricing theo API call khó dự đoán, cần dev knowledge | Web UI đơn giản, pricing rõ ràng theo page, không cần coding |
| **ABBYY FineReader** | Accuracy tốt nhất, full-featured | Rất đắt ($199+/năm), desktop-based, overkill cho SMB | Pay-as-you-go, web-based, phù hợp low volume |
| **Adobe Acrobat OCR** | Integrated với PDF workflow | Accuracy trung bình, không structured output cho bảng, subscription-based | Specialized methods cho bảng/code, structured output |
| **Tesseract (open-source)** | Miễn phí, customizable | Cần technical knowledge, self-hosted, accuracy thấp cho bảng | No setup required, pre-configured for accuracy, managed service |
| **Online OCR tools (OnlineOCR.net, etc.)** | Miễn phí/rẻ, không cần setup | Privacy concerns, limit file size, quality thấp, no batch | Security tiers, larger files, batch support, better quality |

**Competitive Advantage:**
1. **Pay-per-page pricing** — Không subscription, trả theo lượng sử dụng thực
2. **Specialized methods** — ocr_table và ocr_code cho output structured
3. **Tiered security/speed** — Từ free tier đến enterprise-grade bảo mật
4. **Simple UX** — Không cần technical knowledge, upload và nhận kết quả

---

## PART 2: TARGET AUDIENCE

### 2.1. User Personas

#### Persona 1: Minh — Kế toán SMB

| Trường | Nội dung |
|---|---|
| **Persona Name** | Minh — Kế toán doanh nghiệp nhỏ |
| **Role / Bối cảnh** | Kế toán cho công ty thương mại 20-50 nhân viên. Xử lý 50-200 hoá đơn/tháng. |
| **Demographics** | 28-35 tuổi, nữ chiếm đa số, tech-savvy ở mức basic (thành thạo Excel, web apps), sử dụng laptop Windows |
| **Goals** | 1. Số hoá hoá đơn để nhập vào phần mềm kế toán nhanh hơn<br>2. Trích xuất data từ bảng biểu để import vào Excel |
| **Pain Points** | 1. Nhập thủ công hoá đơn tốn 5-10 phút/tờ<br>2. Bảng biểu scan không copy-paste được vào Excel |
| **Current Solution** | Nhập thủ công + đôi khi dùng Google Drive OCR (không hài lòng với bảng biểu) |
| **Trigger to Switch** | Khi volume hoá đơn tăng (cuối năm, audit), hoặc khi có deadline gấp |
| **Key Expectation** | Trích xuất được bảng biểu thành CSV/Excel với độ chính xác cao (>95%) |

#### Persona 2: Hùng — Developer/Tech Lead

| Trường | Nội dung |
|---|---|
| **Persona Name** | Hùng — Developer / Tech Lead |
| **Role / Bối cảnh** | Technical lead tại startup, cần digitize legacy code từ tài liệu in ấn cũ, documentation |
| **Demographics** | 26-38 tuổi, nam chiếm đa số, tech-savvy, sử dụng đa platform (Mac, Linux, Windows) |
| **Goals** | 1. Chuyển đổi code từ sách/tài liệu cũ sang text có thể compile<br>2. Trích xuất code snippets từ screenshots |
| **Pain Points** | 1. OCR thông thường không giữ đúng format code (indentation, special chars)<br>2. Phải manually fix syntax errors sau OCR |
| **Current Solution** | Manual transcription, hoặc dùng Tesseract tự setup (tốn thời gian config) |
| **Trigger to Switch** | Khi có dự án migration legacy codebase, hoặc cần digitize nhiều tài liệu kỹ thuật |
| **Key Expectation** | Output giữ đúng indentation, detect được programming language, syntax-aware |

#### Persona 3: Lan — Freelancer / Cá nhân

| Trường | Nội dung |
|---|---|
| **Persona Name** | Lan — Freelancer / Cá nhân |
| **Role / Bối cảnh** | Freelance content writer, đôi khi cần OCR tài liệu cho khách hàng hoặc bản thân |
| **Demographics** | 24-40 tuổi, tech-savvy cơ bản, sử dụng laptop cá nhân |
| **Goals** | 1. OCR nhanh các tài liệu rải rác (5-20 trang/tháng)<br>2. Không muốn trả subscription cho nhu cầu ít |
| **Pain Points** | 1. Subscription OCR quá đắt cho nhu cầu ít<br>2. Free tools có quá nhiều quảng cáo và limit |
| **Current Solution** | Free tools online (chấp nhận limit và quảng cáo) hoặc skip OCR |
| **Trigger to Switch** | Khi có tài liệu quan trọng cần accuracy cao, hoặc file quá lớn cho free tools |
| **Key Expectation** | Dễ dùng, pay-per-use, không cần đăng ký subscription |

### 2.2. Primary vs. Secondary Users

| Loại | Persona | Vai trò trong sản phẩm | Ghi chú |
|---|---|---|---|
| **Primary User** | Minh (Kế toán SMB) | End user sử dụng hàng ngày, volume cao nhất | Focus UX chính, ocr_table là key feature |
| **Primary User** | Lan (Freelancer) | End user casual, volume thấp nhưng số lượng user lớn | Focus acquisition, free tier / low-cost tier |
| **Secondary User** | Hùng (Developer) | End user với nhu cầu chuyên biệt (ocr_code) | Niche nhưng high-value, technical marketing |
| **Buyer** | Owner/Manager của Minh | Quyết định ngân sách cho team kế toán | Ảnh hưởng pricing perception, cần ROI story |

---

## PART 3: FUNCTIONAL REQUIREMENTS

### 3.1. Feature List

| Feature ID | Module | Tên feature | Mô tả ngắn | Priority | Phase |
|---|---|---|---|---|---|
| **F-001** | Auth | User Authentication | Đăng ký, đăng nhập, quản lý profile | Must | MVP |
| **F-002** | Upload | File Upload & Validation | Upload file ảnh/PDF, validate format/size | Must | MVP |
| **F-003** | Processing | OCR Processing | Xử lý OCR với 3 methods | Must | MVP |
| **F-004** | Tracking | Job Status Tracking | Theo dõi trạng thái job real-time | Must | MVP |
| **F-005** | Output | Result Viewing & Download | Xem và download kết quả OCR | Must | MVP |
| **F-006** | Billing | Credit System | Nạp credit, hold, deduct, refund | Must | MVP |
| **F-007** | Upload | Batch Upload | Upload nhiều file cùng lúc | Should | MVP |
| **F-008** | Notification | In-app Notifications | Thông báo real-time trong web | Should | MVP |
| **F-009** | History | Job History | Xem lịch sử job với filter | Should | MVP |
| **F-010** | Job Mgmt | Job Cancellation | Huỷ job đang chờ trong queue | Should | MVP |
| **F-011** | Config | Processing Presets | Cấu hình đề xuất cho từng loại tài liệu | Could | v2 |
| **F-012** | Admin | Admin Dashboard | Dashboard quản trị nội bộ | Could | v3 |

### 3.2. User Stories & Acceptance Criteria

---

#### Module: Authentication (F-001)

```
[STORY-001] (Priority: Must | Phase: MVP)

As a new user,
I want to register an account using my email,
So that I can access the OCR platform.

Acceptance Criteria:
  AC1: Given I am on the registration page, When I enter valid email, password (min 8 chars, 1 uppercase, 1 number), and confirm password, Then account is created and I receive confirmation.
  AC2: Given I enter an email already registered, When I submit, Then I see error "Email already exists".
  AC3: Given I enter invalid email format, When I submit, Then I see error "Invalid email format".
  AC4: Given passwords don't match, When I submit, Then I see error "Passwords do not match".

Business Rules:
  - RULE-001: Email must be unique across all users
  - RULE-002: Password minimum requirements: 8 characters, 1 uppercase, 1 number

Notes:
  - MVP: Email verification optional (defer to v2)
  - Store password hashed (bcrypt)
```

```
[STORY-002] (Priority: Must | Phase: MVP)

As a registered user,
I want to log in with email and password,
So that I can access my workspace.

Acceptance Criteria:
  AC1: Given valid credentials, When I submit, Then I am redirected to dashboard.
  AC2: Given invalid credentials, When I submit, Then I see error "Invalid email or password" (không tiết lộ field nào sai).
  AC3: Given 5 failed attempts within 15 minutes, When I try again, Then account is temporarily locked for 30 minutes.
  AC4: Given I check "Remember me", When I close browser and return, Then I remain logged in (up to 30 days).

Business Rules:
  - RULE-003: Rate limit login attempts: max 5 per 15 minutes per IP/email
  - RULE-004: Session expires after 24 hours of inactivity, or 30 days if "Remember me"

Notes:
  - Implement CSRF protection
```

```
[STORY-003] (Priority: Must | Phase: MVP)

As a user,
I want to log in using Google or GitHub,
So that I can access faster without creating a new password.

Acceptance Criteria:
  AC1: Given I click "Sign in with Google", When OAuth flow completes, Then I am logged in and redirected to dashboard.
  AC2: Given I click "Sign in with GitHub", When OAuth flow completes, Then I am logged in and redirected to dashboard.
  AC3: Given OAuth email matches existing account, When I complete OAuth, Then accounts are linked.
  AC4: Given OAuth email is new, When I complete OAuth, Then new account is created automatically.

Business Rules:
  - RULE-005: OAuth accounts inherit email from provider, cannot change email
  - RULE-006: OAuth-only accounts can add password later for email login

Notes:
  - Use OAuth 2.0 standard flow
  - Store only email and OAuth provider ID, not tokens
```

---

#### Module: File Upload (F-002)

```
[STORY-004] (Priority: Must | Phase: MVP)

As a user,
I want to upload a single image or PDF file,
So that I can convert it to text.

Acceptance Criteria:
  AC1: Given I select a valid file (PNG, JPEG, TIFF, BMP, WEBP, PDF), When upload completes, Then I see the file listed with preview thumbnail.
  AC2: Given file size exceeds 50MB, When I try to upload, Then I see error "File too large. Maximum 50MB."
  AC3: Given file format is not supported, When I try to upload, Then I see error "Unsupported format. Supported: PNG, JPEG, TIFF, BMP, WEBP, PDF."
  AC4: Given PDF has more than 100 pages, When I try to upload, Then I see error "PDF too long. Maximum 100 pages."
  AC5: Given file is corrupted/unreadable, When I try to upload, Then I see error "File cannot be read. Please try another file."

Business Rules:
  - RULE-007: Max file size: 50MB per file
  - RULE-008: Max pages per PDF: 100
  - RULE-009: Supported formats: PNG, JPEG, TIFF, BMP, WEBP, PDF
  - RULE-010: Files are validated immediately on upload, before entering queue

Notes:
  - Use presigned URL for direct upload to storage (bypass server)
  - Validate MIME type và file signature (magic bytes), không chỉ extension
```

```
[STORY-005] (Priority: Should | Phase: MVP)

As a user,
I want to upload multiple files at once (batch),
So that I can process them together with same configuration.

Acceptance Criteria:
  AC1: Given I select multiple files, When I drag-and-drop or use file picker, Then all files are listed for upload.
  AC2: Given total batch size exceeds 200MB, When I try to upload, Then I see error "Batch too large. Maximum 200MB total."
  AC3: Given some files are invalid, When I try to upload, Then only invalid files show errors, valid files remain uploadable.
  AC4: Given batch upload is confirmed, Then all files share same method + tier + retention config.
  AC5: Given credit is insufficient for entire batch, When I try to submit, Then entire batch is rejected with "Insufficient credit" error.

Business Rules:
  - RULE-011: Max batch size: 200MB total
  - RULE-012: Max files per batch: 50
  - RULE-013: All files in batch must use same configuration (method, tier, retention)
  - RULE-014: Credit hold is atomic for batch — all or nothing

Notes:
  - Allow removing individual files from batch before submit
  - Show estimated credit cost before submit
```

---

#### Module: OCR Processing (F-003)

```
[STORY-006] (Priority: Must | Phase: MVP)

As a user,
I want to select an OCR method before processing,
So that I get the best result for my document type.

Acceptance Criteria:
  AC1: Given I have uploaded a file, When I view processing options, Then I see 3 methods: Simple Text, Table/Form, Code.
  AC2: Given I select "Simple Text" (ocr_simple), Then description shows "Best for text documents, articles, books".
  AC3: Given I select "Table/Form" (ocr_table), Then description shows "Best for spreadsheets, invoices, forms with tables".
  AC4: Given I select "Code" (ocr_code), Then description shows "Best for source code, technical documentation".
  AC5: Given I select a method, Then estimated processing time is displayed.

Business Rules:
  - RULE-015: Method selection is required before processing
  - RULE-016: Method determines output format (text, JSON+CSV, Markdown)

Notes:
  - Show example output for each method
  - [ASSUMPTION: A-02] Estimate time formula: base_time(method) × page_count × tier_factor
```

```
[STORY-007] (Priority: Must | Phase: MVP)

As a user,
I want to select an infrastructure tier before processing,
So that I can balance between cost, speed, and security.

Acceptance Criteria:
  AC1: Given I view tier options, Then I see 5 tiers with name, description, price, and SLA.
  AC2: Given I select Tier 0 (Local), Then I understand: cheapest, slowest, no SLA, data stays local.
  AC3: Given I select Tier 4 (VIP), Then I understand: most expensive, fastest, 99.95% SLA, highest security.
  AC4: Given a tier is unavailable (no workers), Then tier is grayed out with "Temporarily unavailable".
  AC5: Given I select a tier, Then credit cost is recalculated and displayed.

Business Rules:
  - RULE-017: Credit cost = base_price(method) × tier_multiplier × page_count
  - RULE-018: Tier availability depends on worker status

Notes:
  - Tier 0 and Tier 4 are always available
  - Show estimated wait time per tier based on queue depth
```

```
[STORY-008] (Priority: Must | Phase: MVP)

As a user,
I want to submit my file for OCR processing,
So that I can get the text extracted.

Acceptance Criteria:
  AC1: Given I have selected file, method, and tier, When I click "Process", Then job is created and I see confirmation.
  AC2: Given I click "Process", Then credit is held immediately (not yet deducted).
  AC3: Given credit is insufficient, When I click "Process", Then I see "Insufficient credit. Please top up." with link to billing.
  AC4: Given job is submitted, Then job ID is generated and displayed.
  AC5: Given job is submitted, Then I am redirected to job status page.

Business Rules:
  - RULE-019: Credit hold happens at submit time, deduction at completion
  - RULE-020: Job enters SUBMITTED state immediately, then VALIDATING

Notes:
  - Atomic operation: hold credit + create job
```

---

#### Module: Job Status Tracking (F-004)

```
[STORY-009] (Priority: Must | Phase: MVP)

As a user,
I want to see real-time status of my processing job,
So that I know when my result is ready.

Acceptance Criteria:
  AC1: Given job is submitted, When I view job status, Then I see current state (Submitted, Validating, Queued, Processing, Completed).
  AC2: Given job state changes, When I am on status page, Then status updates automatically without refresh (real-time).
  AC3: Given job is in queue, Then I see estimated wait time and position in queue.
  AC4: Given job is processing, Then I see progress indicator (if available) or spinner.
  AC5: Given job is completed, Then I see "Completed" with link to view result.
  AC6: Given job fails, Then I see "Failed" with error reason and refund confirmation.

Business Rules:
  - RULE-021: Job states: SUBMITTED → VALIDATING → QUEUED → DISPATCHED → PROCESSING → COMPLETED
  - RULE-022: Error states: REJECTED, CANCELLED, FAILED, RETRYING, DEAD_LETTER
  - RULE-023: Failed jobs are auto-refunded

Notes:
  - Use SSE (Server-Sent Events) for real-time updates
  - Show timeline of state transitions with timestamps
```

---

#### Module: Result Viewing & Download (F-005)

```
[STORY-010] (Priority: Must | Phase: MVP)

As a user,
I want to view OCR result directly on the web,
So that I can verify accuracy before downloading.

Acceptance Criteria:
  AC1: Given ocr_simple result, When I view result, Then I see plain text with line breaks preserved.
  AC2: Given ocr_table result, When I view result, Then I see table rendered as HTML table with rows/columns.
  AC3: Given ocr_code result, When I view result, Then I see code with syntax highlighting (if language detected).
  AC4: Given result has confidence score, Then confidence is displayed (per word/cell if available).
  AC5: Given multi-page document, Then I can navigate between pages.

Business Rules:
  - RULE-024: Result viewer shows original image side-by-side with extracted text (if viewport allows)

Notes:
  - Lazy load pages for large documents
  - Highlight low-confidence areas (< 80%) in yellow
```

```
[STORY-011] (Priority: Must | Phase: MVP)

As a user,
I want to download OCR result in various formats,
So that I can use the data in my workflow.

Acceptance Criteria:
  AC1: Given ocr_simple result, When I download, Then options are: TXT, DOCX, PDF.
  AC2: Given ocr_table result, When I download, Then options are: JSON, CSV, XLSX.
  AC3: Given ocr_code result, When I download, Then options are: MD (Markdown), TXT.
  AC4: Given I click download, Then file downloads with original filename + suffix (e.g., invoice_ocr.csv).
  AC5: Given result has metadata, Then metadata is included in download (JSON) or as separate file.

Business Rules:
  - RULE-025: Download links are presigned URLs, valid for 1 hour

Notes:
  - Include metadata: original filename, method, tier, processing time, confidence score, timestamp
```

---

#### Module: Credit System (F-006)

```
[STORY-012] (Priority: Must | Phase: MVP)

As a user,
I want to top up credit to my account,
So that I can use the OCR service.

Acceptance Criteria:
  AC1: Given I navigate to Billing, When I view balance, Then I see current credit balance (in VND or pages equivalent).
  AC2: Given I click "Top up", Then I see predefined packages (e.g., 100k, 200k, 500k, 1M VND).
  AC3: Given I select a package and pay via Stripe, When payment succeeds, Then credit is added immediately.
  AC4: Given payment fails, Then I see error message and credit is not added.
  AC5: Given I complete top up, Then transaction appears in billing history.

Business Rules:
  - RULE-026: Minimum top-up: 50,000 VND
  - RULE-027: Credit does not expire
  - RULE-028: Credit is non-refundable (except for failed jobs)

Notes:
  - Support Stripe payment (card)
  - [FUTURE] Support VNPay, MoMo for local payment
```

```
[STORY-013] (Priority: Must | Phase: MVP)

As a user,
I want to see detailed billing history,
So that I can track my spending.

Acceptance Criteria:
  AC1: Given I navigate to Billing > History, Then I see list of transactions (top-ups and job deductions).
  AC2: Given a job deduction, Then I see: date, job ID, method, tier, pages, amount deducted.
  AC3: Given a refund, Then I see: date, job ID, reason, amount refunded.
  AC4: Given a top-up, Then I see: date, payment method, amount added.
  AC5: Given I filter by date range, Then list is filtered accordingly.

Business Rules:
  - RULE-029: Billing history retained for 2 years (compliance)

Notes:
  - Support export to CSV
```

---

#### Module: In-app Notifications (F-008)

```
[STORY-014] (Priority: Should | Phase: MVP)

As a user,
I want to receive real-time notifications in the web app,
So that I know when important events happen.

Acceptance Criteria:
  AC1: Given job completes, Then notification appears in notification center with "Job completed: [filename]".
  AC2: Given job fails, Then notification appears with "Job failed: [filename]. Reason: [error]. Credit refunded."
  AC3: Given credit falls below configured threshold, Then notification appears with "Low credit warning: [balance] remaining."
  AC4: Given file is about to be deleted (24h before), Then notification appears with "File [filename] will be deleted in 24 hours."
  AC5: Given I click notification, Then I am taken to relevant page (job detail, billing, etc.).
  AC6: Given I mark notification as read, Then it no longer shows unread indicator.

Business Rules:
  - RULE-030: Notifications are pushed via SSE when user is online
  - RULE-031: Notifications are stored and can be viewed later (up to 30 days)

Notes:
  - Bell icon with unread count in header
  - Notification center dropdown with list
```

---

#### Module: Job History (F-009)

```
[STORY-015] (Priority: Should | Phase: MVP)

As a user,
I want to view my job history with filters,
So that I can find past jobs easily.

Acceptance Criteria:
  AC1: Given I navigate to History, Then I see list of all my jobs (newest first).
  AC2: Given I filter by date range, Then list shows only jobs in that range.
  AC3: Given I filter by status (Completed, Failed, Cancelled), Then list is filtered.
  AC4: Given I filter by method (Simple, Table, Code), Then list is filtered.
  AC5: Given I search by filename or job ID, Then matching jobs are shown.
  AC6: Given I click a job, Then I see job detail page.

Business Rules:
  - RULE-032: Job history retained for 90 days
  - RULE-033: After 90 days, job metadata is deleted (result may be deleted earlier based on retention setting)

Notes:
  - Pagination: 20 jobs per page
  - Show: filename, method, tier, status, pages, credit used, date
```

---

#### Module: Job Cancellation (F-010)

```
[STORY-016] (Priority: Should | Phase: MVP)

As a user,
I want to cancel a job that is still waiting in queue,
So that I can get my credit back if I made a mistake.

Acceptance Criteria:
  AC1: Given job is in QUEUED state, When I click "Cancel", Then job is cancelled and status shows "Cancelled".
  AC2: Given job is cancelled, Then held credit is refunded immediately.
  AC3: Given job is in PROCESSING or later, When I try to cancel, Then I see "Cannot cancel job in progress."
  AC4: Given I cancel a batch, Then only jobs still in QUEUED are cancelled, others continue.
  AC5: Given cancellation succeeds, Then notification appears "Job cancelled. Credit refunded."

Business Rules:
  - RULE-034: Only QUEUED jobs can be cancelled
  - RULE-035: PROCESSING jobs cannot be cancelled (worker already working)
  - RULE-036: Cancelled jobs refund 100% held credit

Notes:
  - Show "Cancel" button only when cancellable
```

---

### 3.3. Business Rules

| Rule ID | Tên quy tắc | Mô tả | Áp dụng cho | Ví dụ |
|---|---|---|---|---|
| **RULE-001** | Unique Email | Email phải unique trong hệ thống | STORY-001 | user@example.com chỉ dùng cho 1 account |
| **RULE-002** | Password Policy | Min 8 chars, 1 uppercase, 1 number | STORY-001 | "Password1" valid, "password" invalid |
| **RULE-003** | Login Rate Limit | Max 5 attempts / 15 min / IP or email | STORY-002 | Lock 30 phút sau 5 lần sai |
| **RULE-004** | Session Duration | 24h inactive / 30 days remember me | STORY-002 | Auto logout sau 24h không hoạt động |
| **RULE-005** | OAuth Email | OAuth account dùng email từ provider | STORY-003 | Không thể đổi email OAuth account |
| **RULE-006** | OAuth Password | OAuth account có thể add password | STORY-003 | Link thêm login method |
| **RULE-007** | Max File Size | 50MB per file | STORY-004 | File 60MB bị reject |
| **RULE-008** | Max PDF Pages | 100 pages per PDF | STORY-004 | PDF 150 trang bị reject |
| **RULE-009** | Supported Formats | PNG, JPEG, TIFF, BMP, WEBP, PDF | STORY-004 | DOC file bị reject |
| **RULE-010** | Immediate Validation | Validate ngay khi upload | STORY-004 | File lỗi không vào queue |
| **RULE-011** | Max Batch Size | 200MB total | STORY-005 | 5 file x 50MB = 250MB bị reject |
| **RULE-012** | Max Batch Files | 50 files per batch | STORY-005 | 60 files bị reject |
| **RULE-013** | Batch Config | Same config cho cả batch | STORY-005 | Không mix methods trong batch |
| **RULE-014** | Atomic Credit Hold | Hold all or nothing cho batch | STORY-005 | 1000 credit cần, 900 có → reject all |
| **RULE-015** | Method Required | Phải chọn method trước khi process | STORY-006 | Không có default method |
| **RULE-016** | Method Output Format | Method quyết định output format | STORY-006 | ocr_table → JSON+CSV |
| **RULE-017** | Credit Calculation | method_base × tier_mult × pages | STORY-007 | ocr_simple × Tier 2 × 10 pages |
| **RULE-018** | Tier Availability | Tuỳ thuộc worker status | STORY-007 | Tier 1 có thể offline |
| **RULE-019** | Credit Hold vs Deduct | Hold khi submit, deduct khi complete | STORY-008 | Không trừ tiền job đang chạy |
| **RULE-020** | Job Initial State | Job vào SUBMITTED → VALIDATING | STORY-008 | Không skip validation |
| **RULE-021** | Job Happy Path | SUBMITTED→VALIDATING→QUEUED→DISPATCHED→PROCESSING→COMPLETED | STORY-009 | Normal flow |
| **RULE-022** | Job Error States | REJECTED, CANCELLED, FAILED, RETRYING, DEAD_LETTER | STORY-009 | Error branches |
| **RULE-023** | Auto Refund Failed | Failed jobs auto refund credit | STORY-009 | Không cần manual refund |
| **RULE-024** | Side-by-side View | Original + result cạnh nhau | STORY-010 | So sánh accuracy |
| **RULE-025** | Download Link TTL | Presigned URL valid 1 hour | STORY-011 | Link hết hạn sau 1h |
| **RULE-026** | Min Top-up | 50,000 VND minimum | STORY-012 | Không nạp ít hơn 50k |
| **RULE-027** | Credit No Expire | Credit không hết hạn | STORY-012 | Dùng bất kỳ lúc nào |
| **RULE-028** | Non-refundable | Credit không hoàn (trừ failed job) | STORY-012 | Không rút tiền ra |
| **RULE-029** | Billing Retention | 2 năm lịch sử billing | STORY-013 | Compliance requirement |
| **RULE-030** | Push Notification | SSE khi user online | STORY-014 | Real-time update |
| **RULE-031** | Notification Retention | 30 ngày | STORY-014 | Xem lại notification cũ |
| **RULE-032** | Job History Retention | 90 ngày | STORY-015 | Sau 90 ngày bị xoá |
| **RULE-033** | Result Retention | 7-30 ngày tuỳ setting | STORY-015 | Kết quả xoá riêng |
| **RULE-034** | Cancel QUEUED Only | Chỉ huỷ job đang QUEUED | STORY-016 | PROCESSING không huỷ được |
| **RULE-035** | No Cancel Processing | Job đang xử lý không huỷ được | STORY-016 | Worker đã bắt đầu |
| **RULE-036** | Full Refund Cancel | Refund 100% khi cancel | STORY-016 | Không phí cancel |

---

## PART 4: USER EXPERIENCE

### 4.1. User Flows

#### Flow 1: First-time User Registration & First Job

```
Flow Name: First-time User Registration & First Job
Actor: New User (Persona: Lan - Freelancer)
Trigger: User visits platform for the first time
Precondition: None

HAPPY PATH:
  1. User lands on homepage → sees value proposition
  2. User clicks "Get Started" → redirected to registration
  3. User enters email + password → account created
  4. User is redirected to dashboard (empty state)
  5. User clicks "Upload" → file picker opens
  6. User selects file → file uploads with progress bar
  7. User sees file preview → selects method (ocr_simple)
  8. User selects tier (Tier 0 - free trial or Tier 1 - paid)
  9. User clicks "Process" → credit check
  10. If trial: proceed. If paid: redirect to top-up first
  11. Job created → user sees job status page
  12. Job completes → user sees result
  13. User downloads result → flow complete

ALTERNATIVE PATHS:
  - At step 3: User clicks "Sign in with Google" → OAuth flow → step 4
  - At step 9: User has existing credit → proceed to step 11
  - At step 12: Job fails → user sees error + refund notification

ERROR / EDGE CASES:
  - At step 6: File too large → error message, stay on upload page
  - At step 6: File format invalid → error message, stay on upload page
  - At step 9: Credit insufficient → redirect to billing with message
  - At step 12: Job timeout → auto-retry once → if still fail → DEAD_LETTER + refund

BUSINESS RULES APPLIED: RULE-001, RULE-002, RULE-007, RULE-009, RULE-019, RULE-023
```

#### Flow 2: Batch Upload & Processing

```
Flow Name: Batch Upload & Processing
Actor: Regular User (Persona: Minh - Kế toán)
Trigger: User has multiple invoices to process
Precondition: User is logged in, has sufficient credit

HAPPY PATH:
  1. User clicks "Upload" → selects multiple files (10 invoices)
  2. Files upload in parallel → progress shown for each
  3. User sees file list with preview thumbnails
  4. User removes 1 invalid file from batch
  5. User selects method: ocr_table (for invoices)
  6. User selects tier: Tier 2 (Enhanced)
  7. User sees total cost estimate → confirms
  8. User clicks "Process All"
  9. Credit hold for entire batch
  10. Jobs created (9 jobs) → batch status page
  11. Jobs complete one by one → status updates
  12. All complete → user can download all as ZIP

ALTERNATIVE PATHS:
  - At step 4: User can reorder files if needed
  - At step 11: Some jobs fail → those are refunded, others succeed
  - At step 12: User downloads individual results instead of ZIP

ERROR / EDGE CASES:
  - At step 2: Total batch > 200MB → error, remove some files
  - At step 9: Credit check fails → entire batch rejected
  - At step 11: Worker goes down mid-batch → failed jobs retry once

BUSINESS RULES APPLIED: RULE-011, RULE-012, RULE-013, RULE-014, RULE-019, RULE-023
```

#### Flow 3: Job Cancellation

```
Flow Name: Job Cancellation
Actor: User (any persona)
Trigger: User submitted job by mistake or changed mind
Precondition: Job is in QUEUED state

HAPPY PATH:
  1. User navigates to job status page
  2. User sees job is QUEUED (waiting)
  3. User clicks "Cancel"
  4. Confirmation dialog: "Cancel this job? Credit will be refunded."
  5. User confirms
  6. Job cancelled → status shows "Cancelled"
  7. Credit refunded → notification appears
  8. User sees refund in billing history

ALTERNATIVE PATHS:
  - At step 3: Job is PROCESSING → Cancel button disabled/hidden
  - At step 5: User clicks "No" → stays on job page

ERROR / EDGE CASES:
  - At step 3: Job state changed to PROCESSING between page load and click → error "Job already started"

BUSINESS RULES APPLIED: RULE-034, RULE-035, RULE-036
```

### 4.2. Screen / Page Inventory (Wireframe Brief)

| Screen ID | Tên màn hình | Mục đích | Thuộc Flow | Thành phần chính | Ghi chú UX |
|---|---|---|---|---|---|
| **SCR-001** | Landing Page | Value prop, acquisition | Flow 1 | Hero section, feature highlights, pricing preview, CTA buttons | Clear value prop in < 5 seconds |
| **SCR-002** | Registration | Create account | Flow 1 | Email input, password input, confirm password, OAuth buttons, submit button | Single page, no multi-step |
| **SCR-003** | Login | Sign in | Flow 1 | Email input, password input, remember me, OAuth buttons, forgot password link | |
| **SCR-004** | Dashboard | Home base | All flows | Credit balance, recent jobs, upload CTA, quick stats | Empty state for new users |
| **SCR-005** | Upload | File selection | Flow 1, 2 | Drag-drop zone, file picker, file list with previews, remove button, config section | Support multi-file |
| **SCR-006** | Config | Method & Tier selection | Flow 1, 2 | Method cards (3), tier cards (5), cost estimate, retention slider, submit button | Visual comparison |
| **SCR-007** | Job Status | Track single job | Flow 1 | Status indicator, progress bar, timeline, result preview (when done), cancel button | Real-time updates |
| **SCR-008** | Batch Status | Track multiple jobs | Flow 2 | List of jobs with status, overall progress, expand to individual job | Collapsible details |
| **SCR-009** | Result Viewer | View OCR output | Flow 1, 2 | Split view (original + result), page navigation, confidence highlighting, download buttons | Responsive split |
| **SCR-010** | Job History | Past jobs | - | Job list with filters, search, pagination, click to detail | Sort by date desc |
| **SCR-011** | Job Detail | Single job info | - | All job metadata, timeline, result link, credit info | From history |
| **SCR-012** | Billing | Credit management | - | Balance, top-up button, transaction history, export | |
| **SCR-013** | Top-up | Add credit | - | Package selection, Stripe payment form | Stripe Elements |
| **SCR-014** | Notification Center | View notifications | - | Notification list, mark read, clear all | Dropdown or page |
| **SCR-015** | Profile | User settings | - | Email, password change, linked accounts, delete account | |

### 4.3. Business Logic Summary

| Logic ID | Tên | Mô tả | Input | Output | Rules áp dụng |
|---|---|---|---|---|---|
| **BL-001** | Credit Calculation | Tính credit cần cho job | method, tier, page_count | credit_amount | RULE-017 |
| **BL-002** | Credit Hold | Reserve credit khi submit | user_id, credit_amount | success/fail + hold_id | RULE-019, RULE-014 |
| **BL-003** | Credit Deduct | Trừ credit khi complete | hold_id, actual_pages | deducted_amount | RULE-019 |
| **BL-004** | Credit Refund | Hoàn credit khi fail/cancel | hold_id | refunded_amount | RULE-023, RULE-036 |
| **BL-005** | File Validation | Validate file upload | file_blob | valid/invalid + reason | RULE-007, RULE-008, RULE-009 |
| **BL-006** | Estimate Processing Time | Ước tính thời gian xử lý | method, tier, page_count | estimated_seconds | Based on historical data |
| **BL-007** | Queue Position | Tính vị trí trong queue | job_id, tier | position, estimated_wait | Per-tier queue |

### 4.4. State Diagrams

#### Job State Machine

```
                                    ┌─────────────────┐
                                    │   SUBMITTED     │
                                    │ (Credit held)   │
                                    └────────┬────────┘
                                             │
                                             ▼
                            ┌────────────────────────────────┐
                            │           VALIDATING           │
                            │ (Check file integrity/format)  │
                            └────────┬───────────────┬───────┘
                                     │               │
                        Valid        │               │ Invalid
                                     ▼               ▼
                           ┌──────────────┐    ┌──────────────┐
                           │    QUEUED    │    │   REJECTED   │
                           │ (Waiting)    │    │ (Refunded)   │
                           └──────┬───────┘    └──────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
            Cancel  │             │ Worker picks │
                    ▼             ▼             │
           ┌──────────────┐  ┌──────────────┐   │
           │  CANCELLED   │  │  DISPATCHED  │   │
           │  (Refunded)  │  │  (Assigned)  │   │
           └──────────────┘  └──────┬───────┘   │
                                    │           │
                                    ▼           │
                            ┌──────────────┐    │
                            │  PROCESSING  │◄───┘
                            │  (Working)   │
                            └──────┬───────┘
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
           Success│         Timeout│          Error │
                  ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  COMPLETED   │  │   RETRYING   │  │    FAILED    │
         │ (Deducted)   │  │ (Re-queued)  │  │  (Refunded)  │
         └──────────────┘  └──────┬───────┘  └──────────────┘
                                  │
                                  │ Retry once
                                  ▼
                    ┌─────────────────────────────┐
                    │      (Back to QUEUED)       │
                    │ If retry also fails:        │
                    │  → DEAD_LETTER (Refunded)   │
                    └─────────────────────────────┘
```

**Transition Details:**

| From | To | Trigger | Guard | Side Effects |
|---|---|---|---|---|
| SUBMITTED | VALIDATING | Auto | - | - |
| VALIDATING | QUEUED | Validation pass | File valid | - |
| VALIDATING | REJECTED | Validation fail | File invalid | Refund credit |
| QUEUED | DISPATCHED | Worker picks job | Worker available | - |
| QUEUED | CANCELLED | User cancel | - | Refund credit |
| DISPATCHED | PROCESSING | Worker starts | - | - |
| PROCESSING | COMPLETED | OCR success | - | Deduct credit, store result |
| PROCESSING | RETRYING | Timeout/Error | retry_count < 1 | Re-queue |
| PROCESSING | FAILED | Error | retry_count >= 1 | Refund credit |
| RETRYING | QUEUED | Auto | - | - |
| RETRYING | DEAD_LETTER | Retry fails | - | Refund credit, alert admin |

---

## PART 5: SUCCESS METRICS

### 5.1. North Star Metric

| Trường | Nội dung |
|---|---|
| **Metric** | **Pages Processed Successfully per Month** |
| **Định nghĩa** | Tổng số trang (images + PDF pages) được xử lý OCR thành công (COMPLETED state) trong 1 tháng |
| **Target (6 tháng)** | 50,000 pages/month |
| **Tại sao metric này?** | Đây là đơn vị giá trị cốt lõi mà sản phẩm mang lại. Mỗi page processed = 1 đơn vị value delivery. Metric này gắn trực tiếp với revenue (tính phí theo page). |

### 5.2. Key Metrics Framework

| Category | Metric | Định nghĩa / Cách đo | Target MVP | Target 6 tháng | Ghi chú |
|---|---|---|---|---|---|
| **Acquisition** | New Registrations | Số user đăng ký mới / tháng | 100 | 1,000 | Track source (organic, paid, referral) |
| **Acquisition** | Registration → First Job Rate | % user hoàn thành job đầu tiên trong 7 ngày | 30% | 50% | Activation funnel |
| **Activation** | First Job Success Rate | % job đầu tiên thành công (COMPLETED) | 85% | 95% | Product quality indicator |
| **Activation** | Time to First Value | Thời gian từ register đến nhận kết quả đầu tiên | < 10 min | < 5 min | Onboarding efficiency |
| **Retention** | W1 Retention | % user return within 7 days of first job | 20% | 40% | Stickiness |
| **Retention** | M1 Retention | % user có ít nhất 1 job trong tháng tiếp theo | 15% | 30% | Monthly active |
| **Revenue** | Monthly Revenue | Tổng revenue từ credit top-up | $500 | $5,000 | Growth trajectory |
| **Revenue** | ARPU | Average Revenue Per User (active user) | $5 | $10 | Monetization efficiency |
| **Revenue** | Credit Utilization Rate | % credit nạp được sử dụng | 70% | 85% | Value perception |
| **Product** | Job Success Rate | % jobs COMPLETED / total jobs | 90% | 98% | Reliability |
| **Product** | Avg Processing Time | Trung bình thời gian từ submit đến complete | < 2 min | < 30 sec | Performance |
| **Product** | Refund Rate | % jobs refunded (failed/cancelled) | < 15% | < 5% | Quality |

### 5.3. MVP Launch Criteria

| Tiêu chí | Ngưỡng | Cách kiểm tra |
|---|---|---|
| Core features hoàn thành | 100% Must-have stories (STORY-001 đến STORY-016) pass AC | QA sign-off |
| Job Success Rate | > 85% trên test dataset 100 files đa dạng | Automated test + manual verification |
| Performance | Job complete < 5 min cho file 10 trang, Tier 0 | Load test |
| Upload reliability | < 1% upload failure rate | Monitoring |
| Security | Pass OWASP Top 10 basic checklist | Security review |
| UX | User hoàn thành first job trong < 10 min (5 test users) | Usability test |
| Billing | Credit hold/deduct/refund accurate 100% (test 50 scenarios) | Automated test |
| Data | File lifecycle works (upload, process, delete on schedule) | Integration test |

---

## PART 6: ROADMAP

### 6.1. Phase Overview

| Phase | Tên | Mục tiêu chính | Timeline | Features chính | Success Criteria |
|---|---|---|---|---|---|
| **Phase 1 — MVP Core** | Local Proof | Chứng minh end-to-end flow hoạt động | 4-6 tuần | F-001, F-002, F-003, F-004, F-005 (partial) | 100 test jobs complete successfully |
| **Phase 2 — MVP Full** | Production Ready | Full MVP features trên cloud | 8-10 tuần | All Must + Should features | 500 users, 10,000 pages/month |
| **Phase 3 — Scale** | Multi-tier Scale | 5 tiers, auto-scale | 8-12 tuần | F-012 (Admin), Full tier support | 2,000 users, 50,000 pages/month |

### 6.2. MVP Detail

**MVP Goal:** Chứng minh người dùng sẵn sàng trả tiền để xử lý OCR qua web platform với pricing pay-per-page.

**MVP Phase 1 Features (Local Proof — 4-6 tuần):**

| Feature ID | Tên | Lý do phải có trong MVP |
|---|---|---|
| F-001 (partial) | User Auth (email only) | Gate access, track usage |
| F-002 (partial) | Single File Upload | Core input |
| F-003 (partial) | OCR Processing (ocr_simple only) | Core value |
| F-004 | Job Status Tracking | User knows when done |
| F-005 (partial) | Result Download (TXT only) | Core output |

**MVP Phase 2 Features (Production — 8-10 tuần thêm):**

| Feature ID | Tên | Lý do phải có trong MVP |
|---|---|---|
| F-001 (full) | User Auth (+ OAuth) | Reduce friction |
| F-002 (full) | File Upload (+ PDF, all formats) | Cover all input types |
| F-003 (full) | OCR Processing (3 methods) | Key differentiator |
| F-005 (full) | Result Viewer + All downloads | Full output options |
| F-006 | Credit System | Monetization |
| F-007 | Batch Upload | Power user efficiency |
| F-008 | In-app Notifications | Real-time UX |
| F-009 | Job History | User management |
| F-010 | Job Cancellation | User control |

**MVP Excluded (có ý thức loại bỏ):**

| Feature | Lý do loại khỏi MVP | Khi nào sẽ làm |
|---|---|---|
| F-011 Processing Presets | Nice-to-have, users can learn | v2 |
| F-012 Admin Dashboard | Internal tool, not user-facing | Phase 3 |
| Public API | Focus web first, API later | Phase 4+ |
| Handwriting OCR | Low accuracy, niche use case | Phase 4+ |
| Email/Webhook notifications | In-app sufficient for MVP | v2 |

**MVP Timeline (high-level):**

| Tuần | Milestone | Deliverables |
|---|---|---|
| W1-W2 | Setup & Design | Infrastructure setup, UI/UX design, DB schema |
| W3-W4 | Core Backend | Auth, Upload, OCR integration (Tesseract) |
| W5-W6 | Core Frontend | Dashboard, Upload, Status, Result |
| W7-W8 | Billing & Polish | Stripe integration, notifications |
| W9-W10 | QA & Soft Launch | Testing, bug fixes, soft launch to beta users |

### 6.3. Post-MVP Direction

**Phase 3 (Scale — 8-12 tuần sau MVP):**
- Focus: Multi-tier với auto-scale, admin dashboard, monitoring
- Trigger: Khi user base > 500 và có nhu cầu tier cao hơn
- Signals: Users request faster processing, security-conscious users need higher tiers

**Phase 4+ (Future):**
- Public API nếu có nhu cầu từ developers
- Handwriting OCR nếu có significant demand
- Multi-language expansion (Chinese, Japanese, Korean)
- White-label/Enterprise offering

**Pivot Scenarios:**
- Nếu ocr_table adoption > 60% → Double down on table/form processing, consider specialized verticals (invoice, receipt)
- Nếu Tier 4 demand high → Consider on-premise deployment option for enterprise
- Nếu retention thấp < 10% M1 → Investigate pain points, consider subscription model instead of credit

---

## PART 7: CONSTRAINTS

### 7.1. Technical Constraints

| Constraint | Mô tả | Ảnh hưởng đến |
|---|---|---|
| **Tech Stack** | Cloudflare (Workers, R2, Pages) + GCP (Cloud Run, Firestore, Pub/Sub) + Stripe | Architecture đã locked |
| **Platform** | Web only, responsive design, no mobile app | Frontend development, UX |
| **OCR Engine** | Tesseract 5.x for ocr_simple (decided), others TBD | Processing accuracy, licensing |
| **Database** | Firestore (document DB) — no SQL | Data modeling, query patterns |
| **File Storage** | Cloudflare R2 (S3-compatible) | File operations, presigned URLs |
| **GPU Providers** | Vast.ai (Tier 1), RunPod (Tier 2-3), Self-hosted (Tier 0, 4) | Worker management, cost |
| **Performance** | Job complete < 5 min (Tier 0), < 1 min (Tier 4) | Processing pipeline, timeout |
| **Browser** | Chrome, Firefox, Safari, Edge (latest 2 versions) | Frontend compatibility |

### 7.2. Time & Resource Constraints

| Constraint | Chi tiết |
|---|---|
| **Timeline** | MVP Phase 1: 6 tuần. MVP Phase 2: 10 tuần thêm. Total: 16 tuần to full MVP. |
| **Budget** | [NEEDS CONFIRMATION] Ước tính: Infrastructure $200-500/tháng MVP, $1000-3000/tháng scale |
| **Team** | [NEEDS CONFIRMATION] Đề xuất: 2 fullstack dev, 1 DevOps (part-time), 1 QA (part-time) |
| **Dependencies** | Stripe account approval, OAuth app registration (Google, GitHub), GPU provider accounts |

### 7.3. Legal & Compliance Constraints

| Constraint | Mô tả | Bắt buộc cho MVP? | Ghi chú |
|---|---|---|---|
| Data Privacy (GDPR-aware) | User data deletion on request, data export, consent tracking | Có | Design từ đầu, implement Phase 2 |
| Data Retention | File gốc max 30 ngày, result max 30 ngày, job history 90 ngày | Có | Automatic deletion |
| Payment Compliance (PCI) | Stripe handles card data, we never see card numbers | Có | Use Stripe Elements |
| No PII in Logs | Không log email, file content, sensitive data | Có | Logging policy |
| Terms of Service | User agreement cho service usage | Có | Legal review needed |

### 7.4. Assumptions & Risks

**Assumptions (Giả định — cần validate):**

| # | Giả định | Nếu sai thì ảnh hưởng gì? | Cách validate |
|---|---|---|---|
| A-01 | SMB market có nhu cầu OCR pay-per-page | No product-market fit, low adoption | User interviews, landing page test |
| A-02 | Users chấp nhận accuracy 95%+ cho ocr_simple | High refund rate, negative reviews | Beta testing với real documents |
| A-03 | Tesseract đủ tốt cho MVP | Need different engine, delay | Benchmark với sample documents |
| A-04 | Credit model preferred over subscription | Revenue model fails | A/B test pricing page |
| A-05 | GPU provider costs manageable | Negative unit economics | Cost tracking từ Phase 1 |

**Key Risks:**

| Risk | Xác suất | Tác động | Mitigation |
|---|---|---|---|
| OCR accuracy thấp hơn kỳ vọng | Medium | High — user churn, refunds | Extensive testing, clear accuracy expectations, easy refund |
| GPU provider unreliable (Vast.ai spot instances) | Medium | Medium — job failures | Retry logic, multi-provider fallback (Phase 3) |
| Stripe approval delay | Low | Medium — launch delay | Apply early, have backup (VNPay) |
| Security breach / data leak | Low | High — reputation, legal | Security-first design, encryption, audit |
| Cost overrun on GPU | Medium | Medium — negative margin | Cost monitoring, tier pricing adjustment |
| Low adoption / no PMF | Medium | High — project failure | Validate early, iterate fast, pivot ready |

---

## Summary

### ✅ MVP Scope Summary
- **6 core features** (F-001 to F-006) + **4 enhancement features** (F-007 to F-010)
- **16 user stories** (STORY-001 to STORY-016)
- **15 screens** (SCR-001 to SCR-015)
- **36 business rules** (RULE-001 to RULE-036)
- **7 business logic components** (BL-001 to BL-007)

### 📊 Key Metrics
- **North Star:** Pages Processed Successfully per Month (Target: 50,000 @ 6 months)
- **Acquisition:** 1,000 new users/month
- **Activation:** 50% first job success rate
- **Retention:** 30% M1 retention
- **Revenue:** $5,000/month

### ⚠️ Top 3 Risks
1. **OCR accuracy** — May not meet user expectations for specialized documents
2. **GPU cost** — Variable cost from providers may impact unit economics
3. **Adoption** — Pay-per-page model may not resonate vs subscription alternatives

### ❓ Open Questions
1. Pricing cụ thể cho mỗi method × tier combination?
2. Budget infrastructure hàng tháng?
3. Team composition và timeline commitment?
4. Ngôn ngữ OCR ngoài EN/VI có cần không?

### 🎯 Recommended Next Steps
1. **Validate assumptions** — User interviews với 5-10 target personas
2. **Technical spike** — Tesseract benchmark với sample documents (invoice, table, code)
3. **Design sprint** — UI/UX design cho core flows (1 tuần)
4. **Dev kickoff** — Start Phase 1 sau khi có design

---

```
--- SUMMARY HANDOFF #1 (PO → BA) ---
MVP Scope: F-001 (Auth), F-002 (Upload), F-003 (OCR), F-004 (Tracking), F-005 (Result), F-006 (Billing), F-007 (Batch), F-008 (Notifications), F-009 (History), F-010 (Cancel)
Key Business Rules: RULE-017 (Credit calc), RULE-019 (Hold vs Deduct), RULE-021 (Job states), RULE-023 (Auto refund), RULE-034/35/36 (Cancel logic)
Assumptions đã đưa ra: A-01 (SMB market), A-02 (95% accuracy), A-03 (Tesseract sufficient), A-04 (Credit model), A-05 (GPU costs)
Câu hỏi chưa trả lời: Pricing matrix, Budget, Team size, Language support
Personas chính: Minh (Kế toán), Hùng (Developer), Lan (Freelancer)
North Star Metric: Pages Processed Successfully per Month
--- ✅ PHASE 1 COMPLETE ---
```
