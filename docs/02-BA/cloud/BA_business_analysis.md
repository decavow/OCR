# OCR Platform — Business Analysis Document

> Tài liệu phân tích nghiệp vụ cho OCR Platform
> Version: 1.0 | Status: Draft
> References: `01-PO/PO_product_spec.md`

---

## Table of Contents

1. [Product Brief](#1-product-brief)
2. [User & Problem Analysis](#2-user--problem-analysis)
3. [Product Requirements](#3-product-requirements)
4. [Lean Business Case](#4-lean-business-case)
5. [Core Use Cases](#5-core-use-cases)
6. [Glossary & Domain Model](#6-glossary--domain-model)

---

## 1. Product Brief

### 1.1. Product Vision & Elevator Pitch

**One-liner:**
> OCR Platform giúp doanh nghiệp nhỏ và cá nhân chuyển đổi tài liệu giấy/scan thành văn bản số có cấu trúc, bằng cách cung cấp dịch vụ OCR pay-per-page với 3 phương pháp chuyên biệt và 5 mức hạ tầng bảo mật.

**Elevator Pitch (30 giây):**

> Mỗi ngày, hàng triệu doanh nghiệp nhỏ mất hàng giờ nhập liệu thủ công từ hoá đơn, hợp đồng, bảng biểu. Các giải pháp OCR miễn phí không đủ chất lượng, trong khi enterprise OCR quá đắt cho SMB.
>
> OCR Platform là dịch vụ web cho phép bạn upload tài liệu, chọn phương pháp xử lý phù hợp (text thuần, bảng biểu, hoặc mã nguồn), và nhận kết quả có cấu trúc trong vài phút.
>
> Khác biệt: Trả theo lượng sử dụng (không subscription), output structured cho bảng biểu (CSV/JSON), và 5 mức bảo mật từ tiết kiệm đến enterprise-grade.
>
> Mục tiêu: 50,000 trang xử lý thành công mỗi tháng trong 6 tháng đầu.

**Product Vision (2-3 năm):**

OCR Platform sẽ trở thành nền tảng xử lý tài liệu hàng đầu cho SMB tại Việt Nam và Đông Nam Á, với:
- 100,000+ người dùng active
- 1 triệu+ trang xử lý mỗi tháng
- Public API cho developers tích hợp
- Các phương pháp OCR chuyên biệt cho từng ngành (invoice, receipt, form, legal documents)
- White-label solution cho enterprise

### 1.2. Market & Opportunity Analysis

**Target Market:**

| Segment | TAM | SAM | SOM (Year 1) |
|---|---|---|---|
| Global OCR Market | $13.5B (2025) [Grand View Research] | - | - |
| Asia Pacific OCR Market | $2.8B (2025) | - | - |
| Vietnam + SEA SMB OCR | - | ~$50M (estimated) | $500K |
| Vietnam SMB cần OCR casual | - | - | $100K |

> **[ASSUMPTION]** SAM và SOM là ước tính dựa trên:
> - Số SMB tại Việt Nam: ~800,000 (GSO)
> - % cần OCR: 10% = 80,000
> - Spending/năm: $50-100 = $4-8M market

**Target Users:**

| User Type | Số lượng ước tính | Trả tiền? | Sử dụng? | Volume/tháng |
|---|---|---|---|---|
| SMB Kế toán | 50,000 | ✅ Decision maker là Manager/Owner | ✅ Daily user | 50-200 pages |
| Freelancer | 100,000 | ✅ Self-pay | ✅ Occasional | 5-50 pages |
| Developer/Tech | 20,000 | ✅ Self-pay or company | ✅ Project-based | 20-100 pages |

**Competitive Landscape:**

| Competitor | Pricing Model | Accuracy | Table Support | Code Support | Target |
|---|---|---|---|---|---|
| **Google Cloud Vision** | Pay-per-API-call (~$1.5/1000 pages) | High | Basic | No | Developers |
| **ABBYY FineReader** | Subscription ($199+/year) | Very High | Good | No | Enterprise |
| **Adobe Acrobat** | Subscription ($15+/month) | Medium | Basic | No | General |
| **Tesseract (DIY)** | Free (self-hosted) | Medium | No | No | Technical |
| **Online OCR tools** | Free/Ads | Low-Medium | No | No | Casual |
| **OCR Platform (Ours)** | Pay-per-page | High | Structured | Yes | SMB |

**Market Timing:**

1. **Post-COVID digitalization:** Nhu cầu số hoá tài liệu tăng mạnh
2. **SMB growth in Vietnam:** Số SMB tăng trưởng 10%+/năm
3. **AI/ML cost reduction:** Chi phí xử lý OCR giảm, margin tốt hơn
4. **No strong local player:** Chưa có giải pháp OCR local mạnh cho Vietnamese documents

### 1.3. Problem Statement

```
[SMB và cá nhân tại Việt Nam] đang gặp vấn đề [chuyển đổi tài liệu scan/ảnh sang văn bản số có cấu trúc]
khi [xử lý hoá đơn, hợp đồng, bảng biểu, hoặc tài liệu kỹ thuật hàng ngày].

Hậu quả:
- Mất 5-30 phút/trang khi nhập thủ công
- Sai sót dữ liệu 5-10% khi nhập tay
- Không thể import dữ liệu bảng biểu vào Excel/phần mềm
- Chi phí $200-2000/tháng cho enterprise solutions quá cao

Hiện tại họ đang giải quyết bằng:
- Nhập liệu thủ công (tốn thời gian, dễ sai)
- Google Drive OCR (miễn phí nhưng không structured output)
- Free online tools (giới hạn, quảng cáo, privacy concerns)

Hạn chế của cách này:
- Không có output structured cho bảng biểu
- Accuracy không ổn định
- Không phù hợp cho volume cao
```

**Problem Validation Signals:**

| Signal | Evidence | Confidence |
|---|---|---|
| Search volume "OCR online free" | 10K+ searches/month (Vietnam) | High |
| Complaints on forums về nhập liệu thủ công | Multiple threads on Tinhte, VOZ | Medium |
| SMB survey (informal) | 7/10 SMB owners mention manual data entry pain | Medium |
| Existing market (ABBYY, Adobe) | Proves willingness to pay | High |

### 1.4. Product Scope — MVP vs. Full Vision

**🎯 MVP (v1.0):**

| # | Capability | Rationale |
|---|---|---|
| 1 | 3 OCR methods (simple, table, code) | Core differentiation |
| 2 | 5 infrastructure tiers | Flexibility in price/security |
| 3 | Pre-paid credit billing | Pay-per-use model |
| 4 | Batch upload (up to 50 files) | Efficiency for power users |
| 5 | Real-time notifications | User experience |
| 6 | Job history & management | User control |
| 7 | OAuth + email auth | Reduce friction |

**🔮 Full Vision (v2.0+):**

| Phase | Capabilities |
|---|---|
| v2 | Processing presets, email notifications, API (limited) |
| v3 | Admin dashboard, full multi-tier scale, enhanced monitoring |
| v4 | Public API, handwriting OCR, specialized verticals (invoice, receipt) |
| v5 | White-label, enterprise on-premise, multi-language (CN, JP, KR) |

**🚫 Explicit Out of Scope:**

- Mobile app (web responsive is sufficient)
- Public API (Phase 4+)
- Multi-tenant/organization (individual workspaces only)
- Document storage/management (not a cloud drive)
- Real-time collaborative editing
- Handwriting recognition (Phase 4+)

---

## 2. User & Problem Analysis

### 2.1. User Personas (Lean Format)

#### Persona 1: Minh — Kế toán SMB (Primary)

| Trường | Nội dung |
|---|---|
| **Persona Name** | Minh — Kế toán doanh nghiệp nhỏ |
| **Demographics** | Nữ, 28-35 tuổi, thu nhập 12-20 triệu/tháng, tech-savvy cơ bản (Excel, web apps), laptop Windows |
| **Goal** | Số hoá hoá đơn/bảng biểu nhanh để import vào phần mềm kế toán |
| **Pain Point** | Nhập thủ công 5-10 phút/hoá đơn, bảng biểu scan không copy-paste được |
| **Current Solution** | Nhập tay + Google Drive OCR (không hài lòng với bảng) |
| **Why Switch?** | Khi volume tăng (cuối năm), deadline gấp, hoặc được đồng nghiệp giới thiệu |
| **Willingness to Pay** | 200-500k/tháng cho 100-200 pages, prefer pay-per-use over subscription |

#### Persona 2: Hùng — Developer (Secondary)

| Trường | Nội dung |
|---|---|
| **Persona Name** | Hùng — Developer / Tech Lead |
| **Demographics** | Nam, 26-38 tuổi, thu nhập 25-50 triệu/tháng, tech-savvy cao, đa platform |
| **Goal** | Chuyển đổi code từ tài liệu cũ sang text có thể compile |
| **Pain Point** | OCR thông thường không giữ indentation, syntax errors |
| **Current Solution** | Manual transcription, tự setup Tesseract |
| **Why Switch?** | Dự án migration, nhiều tài liệu kỹ thuật cần digitize |
| **Willingness to Pay** | 500k-1M/project, company có thể chi trả |

#### Persona 3: Lan — Freelancer (Secondary)

| Trường | Nội dung |
|---|---|
| **Persona Name** | Lan — Freelancer / Cá nhân |
| **Demographics** | 24-40 tuổi, đa dạng thu nhập, tech-savvy cơ bản |
| **Goal** | OCR nhanh các tài liệu rải rác mà không cần subscription |
| **Pain Point** | Subscription quá đắt cho nhu cầu ít, free tools có quảng cáo/limit |
| **Current Solution** | Free tools online, chấp nhận limit |
| **Why Switch?** | File quan trọng cần accuracy, file lớn vượt limit free |
| **Willingness to Pay** | 50-100k/lần, chỉ trả khi cần |

### 2.2. User Journey Map (Core Flow)

```
[Awareness] → [First Touch] → [Onboarding] → [Core Action] → [Value Moment] → [Retention/Referral]
     │              │              │               │               │               │
     ▼              ▼              ▼               ▼               ▼               ▼
 "Cần OCR"    Visit website   Register +     Upload file +   See accurate    Return for
 Google       See pricing     First upload   Select method   result, save    next batch
 search,      Compare with    (< 3 min)      Submit job      time (< 5 min)  Recommend
 referral     alternatives                   (< 2 min)                       to colleague
```

**Journey Detail:**

| Stage | User Action | User Feeling | Opportunity |
|---|---|---|---|
| **Awareness** | Search "OCR online", ask colleague | Frustrated with current solution | SEO, word-of-mouth |
| **First Touch** | Visit website, read pricing | Curious, comparing | Clear value prop, simple pricing |
| **Onboarding** | Register, explore dashboard | Slightly confused or excited | Simple UX, guided first upload |
| **Core Action** | Upload, select config, submit | Hopeful, waiting | Fast processing, real-time status |
| **Value Moment** | See result, verify accuracy | Delighted or disappointed | High accuracy, easy export |
| **Retention** | Return for next batch | Satisfied, trusting | Consistent quality, fair pricing |
| **Referral** | Tell colleague | Enthusiastic | Referral program (future) |

---

## 3. Product Requirements

### 3.1. Feature Prioritization Matrix

| Feature ID | Tên feature | User Value (1-5) | Business Value (1-5) | Dev Effort | Priority | Phase |
|---|---|---|---|---|---|---|
| F-001 | User Authentication | 4 | 5 | M | Must | MVP |
| F-002 | File Upload & Validation | 5 | 5 | M | Must | MVP |
| F-003 | OCR Processing (3 methods) | 5 | 5 | L | Must | MVP |
| F-004 | Job Status Tracking | 4 | 4 | M | Must | MVP |
| F-005 | Result Viewing & Download | 5 | 4 | M | Must | MVP |
| F-006 | Credit System | 3 | 5 | L | Must | MVP |
| F-007 | Batch Upload | 4 | 3 | M | Should | MVP |
| F-008 | In-app Notifications | 3 | 3 | S | Should | MVP |
| F-009 | Job History | 3 | 3 | S | Should | MVP |
| F-010 | Job Cancellation | 2 | 3 | S | Should | MVP |
| F-011 | Processing Presets | 2 | 2 | S | Could | v2 |
| F-012 | Admin Dashboard | 1 | 4 | L | Could | v3 |

**Legend:** User/Business Value: 1 (Low) - 5 (High), Dev Effort: S (Small), M (Medium), L (Large), XL (Extra Large)

### 3.2. Product Requirements (Lean Format)

#### PR-001: User Registration (F-001)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-001 |
| **Feature** | F-001 User Authentication |
| **User Story** | Với tư cách người dùng mới, tôi muốn đăng ký tài khoản để sử dụng dịch vụ OCR |
| **Acceptance Criteria** | AC1: Đăng ký với email hợp lệ + password (min 8 chars, 1 upper, 1 number) → thành công<br>AC2: Email đã tồn tại → hiển thị lỗi "Email đã được sử dụng"<br>AC3: Password không đạt yêu cầu → hiển thị lỗi cụ thể |
| **Business Rules** | RULE-001 (Unique Email), RULE-002 (Password Policy) |
| **Priority** | Must |
| **Notes** | MVP: Không cần email verification. OAuth làm song song. |

#### PR-002: OAuth Login (F-001)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-002 |
| **Feature** | F-001 User Authentication |
| **User Story** | Với tư cách người dùng, tôi muốn đăng nhập bằng Google/GitHub để tiết kiệm thời gian |
| **Acceptance Criteria** | AC1: Click "Sign in with Google" → OAuth flow → logged in<br>AC2: Email OAuth trùng account → link accounts<br>AC3: Email OAuth mới → tạo account mới |
| **Business Rules** | RULE-005, RULE-006 |
| **Priority** | Must |
| **Notes** | Google và GitHub là 2 providers phổ biến nhất với target users |

#### PR-003: Single File Upload (F-002)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-003 |
| **Feature** | F-002 File Upload & Validation |
| **User Story** | Với tư cách người dùng, tôi muốn upload file ảnh/PDF để xử lý OCR |
| **Acceptance Criteria** | AC1: Upload file hợp lệ (PNG, JPEG, TIFF, BMP, WEBP, PDF ≤ 50MB, ≤ 100 pages) → thành công<br>AC2: File > 50MB → lỗi "File too large"<br>AC3: Format không hỗ trợ → lỗi "Unsupported format"<br>AC4: PDF > 100 pages → lỗi "Too many pages" |
| **Business Rules** | RULE-007, RULE-008, RULE-009, RULE-010 |
| **Priority** | Must |
| **Notes** | Direct upload via presigned URL. Validate MIME + magic bytes. |

#### PR-004: Batch Upload (F-007)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-004 |
| **Feature** | F-007 Batch Upload |
| **User Story** | Với tư cách người dùng, tôi muốn upload nhiều file cùng lúc để xử lý với cùng config |
| **Acceptance Criteria** | AC1: Upload ≤ 50 files, tổng ≤ 200MB → thành công<br>AC2: Tổng > 200MB → lỗi "Batch too large"<br>AC3: > 50 files → lỗi "Too many files"<br>AC4: Một số file lỗi → chỉ reject file lỗi, giữ file hợp lệ |
| **Business Rules** | RULE-011, RULE-012, RULE-013, RULE-014 |
| **Priority** | Should |
| **Notes** | Cho phép remove file trước khi submit. Hiển thị estimate cost. |

#### PR-005: OCR Method Selection (F-003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-005 |
| **Feature** | F-003 OCR Processing |
| **User Story** | Với tư cách người dùng, tôi muốn chọn phương pháp OCR phù hợp với loại tài liệu |
| **Acceptance Criteria** | AC1: Hiển thị 3 methods với mô tả rõ ràng<br>AC2: Mỗi method hiển thị ví dụ output<br>AC3: Chọn method → cập nhật estimate time và cost |
| **Business Rules** | RULE-015, RULE-016 |
| **Priority** | Must |
| **Notes** | Methods: ocr_simple (text), ocr_table (JSON+CSV), ocr_code (Markdown) |

#### PR-006: Tier Selection (F-003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-006 |
| **Feature** | F-003 OCR Processing |
| **User Story** | Với tư cách người dùng, tôi muốn chọn tier hạ tầng để cân bằng cost/speed/security |
| **Acceptance Criteria** | AC1: Hiển thị 5 tiers với price, SLA, đặc điểm<br>AC2: Tier không có worker → grayed out "Unavailable"<br>AC3: Chọn tier → cập nhật cost estimate |
| **Business Rules** | RULE-017, RULE-018 |
| **Priority** | Must |
| **Notes** | Tier 0, 4 always available. Show estimated wait time. |

#### PR-007: Job Submit (F-003)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-007 |
| **Feature** | F-003 OCR Processing |
| **User Story** | Với tư cách người dùng, tôi muốn submit file để bắt đầu xử lý OCR |
| **Acceptance Criteria** | AC1: Đủ credit → hold credit, tạo job, redirect to status page<br>AC2: Không đủ credit → lỗi "Insufficient credit" với link top-up<br>AC3: Job created → hiển thị job ID |
| **Business Rules** | RULE-019, RULE-020 |
| **Priority** | Must |
| **Notes** | Atomic operation: hold + create job. Transaction-based. |

#### PR-008: Real-time Job Status (F-004)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-008 |
| **Feature** | F-004 Job Status Tracking |
| **User Story** | Với tư cách người dùng, tôi muốn xem trạng thái job real-time để biết khi nào xong |
| **Acceptance Criteria** | AC1: Status updates tự động không cần refresh (SSE)<br>AC2: Hiển thị queue position và estimated wait<br>AC3: Completed → link to result<br>AC4: Failed → hiển thị reason và refund confirmation |
| **Business Rules** | RULE-021, RULE-022, RULE-023 |
| **Priority** | Must |
| **Notes** | SSE connection. Show timeline with timestamps. |

#### PR-009: Result Viewer (F-005)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-009 |
| **Feature** | F-005 Result Viewing & Download |
| **User Story** | Với tư cách người dùng, tôi muốn xem kết quả OCR trên web để verify trước khi download |
| **Acceptance Criteria** | AC1: ocr_simple → plain text với line breaks<br>AC2: ocr_table → HTML table rendered<br>AC3: ocr_code → syntax highlighted code<br>AC4: Multi-page → page navigation<br>AC5: Confidence < 80% → highlighted |
| **Business Rules** | RULE-024 |
| **Priority** | Must |
| **Notes** | Side-by-side view original + result. Lazy load pages. |

#### PR-010: Result Download (F-005)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-010 |
| **Feature** | F-005 Result Viewing & Download |
| **User Story** | Với tư cách người dùng, tôi muốn download kết quả trong format phù hợp workflow |
| **Acceptance Criteria** | AC1: ocr_simple → TXT, DOCX, PDF<br>AC2: ocr_table → JSON, CSV, XLSX<br>AC3: ocr_code → MD, TXT<br>AC4: Filename có suffix "_ocr" |
| **Business Rules** | RULE-025 |
| **Priority** | Must |
| **Notes** | Presigned URL valid 1 hour. Include metadata. |

#### PR-011: Credit Top-up (F-006)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-011 |
| **Feature** | F-006 Credit System |
| **User Story** | Với tư cách người dùng, tôi muốn nạp credit để sử dụng dịch vụ |
| **Acceptance Criteria** | AC1: Hiển thị balance và packages (50k, 100k, 200k, 500k, 1M)<br>AC2: Stripe payment success → credit added immediately<br>AC3: Payment fail → error message, no credit added |
| **Business Rules** | RULE-026, RULE-027, RULE-028 |
| **Priority** | Must |
| **Notes** | Stripe Elements for card input. Min 50k VND. |

#### PR-012: Billing History (F-006)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-012 |
| **Feature** | F-006 Credit System |
| **User Story** | Với tư cách người dùng, tôi muốn xem lịch sử billing để track spending |
| **Acceptance Criteria** | AC1: Hiển thị list transactions (top-up, deduct, refund)<br>AC2: Filter by date range<br>AC3: Export to CSV |
| **Business Rules** | RULE-029 |
| **Priority** | Must |
| **Notes** | 2 years retention for compliance. |

#### PR-013: Job Cancellation (F-010)

| Trường | Nội dung |
|---|---|
| **PR-ID** | PR-013 |
| **Feature** | F-010 Job Cancellation |
| **User Story** | Với tư cách người dùng, tôi muốn huỷ job đang chờ để lấy lại credit |
| **Acceptance Criteria** | AC1: Job QUEUED → "Cancel" button visible → cancel → refund<br>AC2: Job PROCESSING → "Cancel" disabled<br>AC3: Cancel success → notification "Credit refunded" |
| **Business Rules** | RULE-034, RULE-035, RULE-036 |
| **Priority** | Should |
| **Notes** | Only QUEUED jobs cancellable. |

### 3.3. Business Rules

| Rule ID | Tên quy tắc | Mô tả chi tiết | Ví dụ |
|---|---|---|---|
| **RULE-017** | Credit Calculation | `credit = base_price(method) × tier_multiplier × page_count` | ocr_simple (100đ base) × Tier 2 (4x) × 10 pages = 4,000đ |
| **RULE-019** | Hold vs Deduct | Credit được hold khi submit (reserved), deduct khi job complete (finalized). Đảm bảo không oversell. | Submit → hold 5,000đ → Processing → Complete → deduct 5,000đ |
| **RULE-021** | Job State Machine | States: SUBMITTED → VALIDATING → QUEUED → DISPATCHED → PROCESSING → COMPLETED. Error states: REJECTED, CANCELLED, FAILED, RETRYING, DEAD_LETTER | Validation fail → REJECTED (refund) |
| **RULE-023** | Auto Refund | Job vào FAILED, CANCELLED, hoặc DEAD_LETTER → credit tự động refund vào account | Timeout → FAILED → refund 100% held credit |
| **RULE-014** | Atomic Credit Hold (Batch) | Khi submit batch, hold credit cho toàn bộ. Nếu không đủ → reject cả batch. Không có partial submit. | 10 files × 500đ = 5,000đ. Balance 4,000đ → reject all 10 |

**Additional Business Rules (Derived):**

| Rule ID | Tên quy tắc | Mô tả chi tiết | Ví dụ |
|---|---|---|---|
| **RULE-037** | Retry Logic | Job fail do timeout/error → retry tối đa 1 lần ở orchestrator level. Retry cũng fail → DEAD_LETTER | Job timeout → RETRYING → re-queue → timeout lần 2 → DEAD_LETTER |
| **RULE-038** | File Retention Default | File gốc: 24h mặc định, user có thể chọn 1h-30d. Kết quả: 7d mặc định, max 30d. | User chọn 7 ngày → file tự xoá sau 7 ngày |
| **RULE-039** | Tier Pricing Multiplier | Tier 0: 1x, Tier 1: 2x, Tier 2: 4x, Tier 3: 8x, Tier 4: 20x | [NEEDS CONFIRMATION] |
| **RULE-040** | Method Pricing Base | ocr_simple: 100đ, ocr_table: 200đ, ocr_code: 150đ | [NEEDS CONFIRMATION] |
| **RULE-041** | Credit Package Bonus | 500k package: +5% bonus. 1M package: +10% bonus. | 1M VND → 1,100,000đ credit |

---

## 4. Lean Business Case

### 4.1. Revenue Model

**Cách kiếm tiền:** Pre-paid credit, pay-per-page

**Pricing Strategy:**

| Method | Base Price/page | Tier 0 | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|---|---|
| ocr_simple | 100đ | 100đ | 200đ | 400đ | 800đ | 2,000đ |
| ocr_table | 200đ | 200đ | 400đ | 800đ | 1,600đ | 4,000đ |
| ocr_code | 150đ | 150đ | 300đ | 600đ | 1,200đ | 3,000đ |

> **[NEEDS CONFIRMATION]** Pricing cần validate với market research và cost analysis.

**Competitive Comparison:**

| Service | Price/page (equivalent) | Notes |
|---|---|---|
| Google Cloud Vision | ~35đ ($1.5/1000) | API only, need coding |
| ABBYY FineReader | ~250đ ($199/year ÷ 800 pages) | Desktop, subscription |
| Adobe Acrobat | ~375đ ($15/month ÷ 40 pages) | Overkill for OCR only |
| OCR Platform (Tier 1) | 200đ | Competitive, simpler |

**Revenue Projection:**

| Timeline | Users | Pages/month | ARPU | Revenue/month |
|---|---|---|---|---|
| Month 3 (MVP) | 100 | 5,000 | $5 | $500 |
| Month 6 | 500 | 25,000 | $8 | $4,000 |
| Month 12 | 2,000 | 100,000 | $10 | $20,000 |
| Month 24 | 10,000 | 500,000 | $12 | $120,000 |

### 4.2. Cost Estimation (Lean)

| Hạng mục | Chi phí ước tính | Ghi chú |
|---|---|---|
| **Development (MVP)** | $15,000 - $25,000 | 2 fullstack × 4 months @ $1,500-2,000/month |
| **Infrastructure (monthly)** | $200 - $500 (MVP) | Cloudflare free tier, GCP free tier, minimal GPU |
| **Third-party services** | $50 - $100/month | Stripe (2.9% + $0.30/txn), Auth0/Clerk free tier |
| **GPU (variable)** | $0.50 - $2.00/1000 pages | Vast.ai/RunPod, varies by tier |
| **Design (UI/UX)** | $2,000 - $5,000 | Template-based, 1 designer × 1 month |
| **Buffer (20%)** | $3,500 - $6,500 | Contingency |
| **Tổng MVP** | **$21,000 - $37,000** | 4-6 months |
| **Monthly operating** | $300 - $800 | Post-launch, scales with usage |

### 4.3. Cost Optimization Recommendations

| Hạng mục | Cách làm "đầy đủ" | Cách làm "lean" | Tiết kiệm |
|---|---|---|---|
| **Backend** | Custom FastAPI + complex infra | Cloudflare Workers + managed services | 40-60% |
| **Database** | PostgreSQL + Redis cluster | Firestore (scale to zero) | 60-80% |
| **File Storage** | S3 with complex CDN | Cloudflare R2 (free egress) | 70-80% |
| **Auth** | Custom auth system | Firebase Auth / Clerk free tier | 80-90% |
| **Payment** | Custom payment system | Stripe Elements | 90%+ |
| **GPU** | Dedicated GPU servers 24/7 | Vast.ai spot instances, auto on/off | 50-70% |
| **Monitoring** | Datadog/New Relic | Cloudflare Analytics + GCP free monitoring | 80-90% |

**Trade-offs:**
- Cloudflare Workers: Cold start latency, limited CPU time → acceptable for OCR orchestration
- Firestore: No SQL, limited queries → acceptable for document-based data model
- Vast.ai: Spot instances can be preempted → retry logic mitigates

### 4.4. Go / No-Go Assessment

| Tiêu chí | Đánh giá | Ghi chú |
|---|---|---|
| Vấn đề đủ lớn & urgent? | ✅ | SMB manual data entry is real pain |
| Thị trường đủ lớn? | ✅ | $50M+ SAM in SEA, growing |
| Khác biệt so với đối thủ? | ✅ | Pay-per-page + structured output + tiers |
| Ngân sách đủ cho MVP? | ⚠️ | Need to confirm $20-40k available |
| Team có đủ năng lực? | ⚠️ | Need 2 fullstack + DevOps (part-time) |
| Time-to-market hợp lý? | ✅ | 4-6 months MVP is achievable |
| Revenue model rõ ràng? | ✅ | Pre-paid credit, proven in similar services |

**Verdict:** ⚠️ **Go with conditions**
- Conditions: Confirm budget, confirm team, validate pricing with 10 user interviews

---

## 5. Core Use Cases (MVP Only)

### UC-001: Register Account

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-001 |
| **Use Case Name** | Register new account |
| **Actor(s)** | New User |
| **User Story** | PR-001, PR-002 |
| **Trigger** | User clicks "Get Started" or "Sign Up" |
| **Main Flow** | 1. User navigates to registration page<br>2. User enters email and password<br>3. System validates email format and password policy<br>4. System creates account<br>5. System redirects to dashboard |
| **Alternative Flows** | 3a. User clicks OAuth button → OAuth flow → account created/linked |
| **Exception Flows** | 3b. Email exists → error "Email already registered"<br>3c. Password weak → error with requirements |
| **Postconditions** | User has active account, logged in, on dashboard |
| **Business Rules** | RULE-001, RULE-002, RULE-005, RULE-006 |
| **MVP Notes** | Skip email verification for MVP |

### UC-002: Upload Single File

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-002 |
| **Use Case Name** | Upload single file for OCR |
| **Actor(s)** | Logged-in User |
| **User Story** | PR-003 |
| **Trigger** | User clicks "Upload" button |
| **Main Flow** | 1. User clicks upload button or drag-drops file<br>2. System requests presigned URL<br>3. Browser uploads file directly to storage<br>4. System validates file (format, size, pages)<br>5. System shows file preview |
| **Alternative Flows** | 1a. User uses file picker instead of drag-drop |
| **Exception Flows** | 4a. File > 50MB → error "File too large"<br>4b. Unsupported format → error "Unsupported format"<br>4c. PDF > 100 pages → error "Too many pages"<br>4d. File corrupted → error "Cannot read file" |
| **Postconditions** | File uploaded and validated, ready for configuration |
| **Business Rules** | RULE-007, RULE-008, RULE-009, RULE-010 |
| **MVP Notes** | Direct upload via presigned URL for performance |

### UC-003: Configure and Submit Job

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-003 |
| **Use Case Name** | Configure OCR settings and submit job |
| **Actor(s)** | Logged-in User with uploaded file |
| **User Story** | PR-005, PR-006, PR-007 |
| **Trigger** | File upload complete |
| **Main Flow** | 1. System shows method options (simple, table, code)<br>2. User selects method<br>3. System shows tier options with prices<br>4. User selects tier<br>5. System shows cost estimate and retention options<br>6. User clicks "Process"<br>7. System holds credit<br>8. System creates job, transitions to SUBMITTED<br>9. System redirects to job status page |
| **Alternative Flows** | 6a. User adjusts retention before submit |
| **Exception Flows** | 7a. Insufficient credit → error "Not enough credit" with top-up link |
| **Postconditions** | Job created, credit held, user viewing status page |
| **Business Rules** | RULE-015, RULE-016, RULE-017, RULE-019, RULE-020 |
| **MVP Notes** | Atomic transaction for hold + create |

### UC-004: Track Job Status

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-004 |
| **Use Case Name** | Track job processing status |
| **Actor(s)** | Logged-in User with submitted job |
| **User Story** | PR-008 |
| **Trigger** | Job submitted, user on status page |
| **Main Flow** | 1. System establishes SSE connection<br>2. System displays current status (SUBMITTED)<br>3. Status transitions through states (VALIDATING → QUEUED → DISPATCHED → PROCESSING)<br>4. Each transition updates UI in real-time<br>5. Job completes (COMPLETED)<br>6. System shows "View Result" button |
| **Alternative Flows** | 5a. Job fails → show error reason, refund confirmation |
| **Exception Flows** | 2a. SSE connection lost → fallback to polling<br>5b. Job DEAD_LETTER → show admin will review |
| **Postconditions** | User knows job status, can view result if complete |
| **Business Rules** | RULE-021, RULE-022, RULE-023, RULE-037 |
| **MVP Notes** | SSE preferred, polling fallback |

### UC-005: View and Download Result

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-005 |
| **Use Case Name** | View OCR result and download |
| **Actor(s)** | Logged-in User with completed job |
| **User Story** | PR-009, PR-010 |
| **Trigger** | User clicks "View Result" |
| **Main Flow** | 1. System loads result viewer<br>2. System displays original (if available) and extracted text side-by-side<br>3. User reviews result, navigates pages if multi-page<br>4. User clicks download button<br>5. User selects format (TXT/DOCX/PDF or JSON/CSV/XLSX or MD/TXT)<br>6. System generates presigned URL<br>7. Browser downloads file |
| **Alternative Flows** | 3a. User zooms/scrolls to review<br>6a. User downloads different format |
| **Exception Flows** | 2a. Result expired (past retention) → error "Result no longer available" |
| **Postconditions** | User has downloaded result file |
| **Business Rules** | RULE-024, RULE-025, RULE-038 |
| **MVP Notes** | Lazy load for large documents |

### UC-006: Top Up Credit

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-006 |
| **Use Case Name** | Add credit to account |
| **Actor(s)** | Logged-in User |
| **User Story** | PR-011 |
| **Trigger** | User navigates to Billing or sees "Insufficient credit" |
| **Main Flow** | 1. System shows current balance<br>2. System shows credit packages (50k, 100k, 200k, 500k, 1M)<br>3. User selects package<br>4. System shows Stripe payment form<br>5. User enters card details<br>6. User clicks "Pay"<br>7. Stripe processes payment<br>8. System adds credit to account<br>9. System shows confirmation with new balance |
| **Alternative Flows** | 3a. User enters custom amount (if supported) |
| **Exception Flows** | 7a. Payment declined → error "Payment failed"<br>7b. 3DS required → redirect to bank verification |
| **Postconditions** | Credit added, transaction in billing history |
| **Business Rules** | RULE-026, RULE-027, RULE-028, RULE-041 |
| **MVP Notes** | Stripe Elements, packages only (no custom amount MVP) |

### UC-007: Cancel Queued Job

| Trường | Nội dung |
|---|---|
| **UC-ID** | UC-007 |
| **Use Case Name** | Cancel job waiting in queue |
| **Actor(s)** | Logged-in User with QUEUED job |
| **User Story** | PR-013 |
| **Trigger** | User clicks "Cancel" on QUEUED job |
| **Main Flow** | 1. System shows confirmation dialog<br>2. User confirms cancel<br>3. System changes job status to CANCELLED<br>4. System refunds held credit<br>5. System shows notification "Job cancelled. Credit refunded." |
| **Alternative Flows** | 2a. User clicks "No" → stay on page |
| **Exception Flows** | 3a. Job already transitioned to PROCESSING → error "Job already started" |
| **Postconditions** | Job cancelled, credit refunded |
| **Business Rules** | RULE-034, RULE-035, RULE-036 |
| **MVP Notes** | Race condition: check state before cancel |

---

## 6. Glossary & Domain Model

### 6.1. Business Glossary

| Thuật ngữ | Định nghĩa | Ví dụ |
|---|---|---|
| **Credit** | Đơn vị tiền tệ nội bộ, dùng để thanh toán jobs. 1 credit = 1 VND. | 100,000 credit = 100,000 VND |
| **Job** | Một unit công việc xử lý OCR cho một file. | Job ID: job_abc123 |
| **Batch** | Nhóm nhiều files upload cùng lúc, share cùng config. | Batch 10 invoices, all ocr_table, Tier 2 |
| **Method** | Phương pháp xử lý OCR, quyết định algorithm và output format. | ocr_simple, ocr_table, ocr_code |
| **Tier** | Mức hạ tầng xử lý, quyết định tốc độ, bảo mật, SLA, giá. | Tier 0 (Local) đến Tier 4 (VIP) |
| **Page** | Đơn vị tính phí. 1 image = 1 page. 1 PDF page = 1 page. | 10-page PDF = 10 pages |
| **Hold** | Trạng thái credit đã reserved cho job nhưng chưa trừ. | Submit job → hold 1000 credit |
| **Deduct** | Trừ credit từ balance sau khi job complete. | Job done → deduct 1000 credit |
| **Refund** | Hoàn credit về balance khi job fail/cancel. | Job fail → refund 1000 credit |
| **Worker** | Container xử lý OCR chạy trên GPU infrastructure. | Worker trên Vast.ai |
| **Queue** | Hàng đợi jobs theo tier. FIFO ordering. | Tier 1 queue, Tier 2 queue |
| **Dead Letter Queue** | Queue chứa jobs fail sau khi retry, cần admin review. | Job fail 2x → DLQ |
| **Presigned URL** | URL tạm thời để upload/download file trực tiếp từ storage. | Valid 1 hour |
| **Retention** | Thời gian lưu trữ file trước khi tự động xoá. | 24h default for source, 7d for result |

### 6.2. Domain Model (High-Level)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN MODEL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────┐           ┌──────────┐           ┌──────────┐                │
│   │   USER   │───1:N────▶│   JOB    │───1:1────▶│  RESULT  │                │
│   └──────────┘           └──────────┘           └──────────┘                │
│        │                      │                                              │
│        │                      │                                              │
│        │                      │ N:1                                          │
│        │                      ▼                                              │
│        │                 ┌──────────┐                                        │
│        │                 │  BATCH   │                                        │
│        │                 └──────────┘                                        │
│        │                                                                     │
│        │                                                                     │
│        │ 1:N                                                                 │
│        ▼                                                                     │
│   ┌──────────┐           ┌──────────┐                                        │
│   │ BILLING  │◀──1:N─────│TRANSACTION│                                       │
│   │ ACCOUNT  │           └──────────┘                                        │
│   └──────────┘                │                                              │
│                               │ 1:1 (for job-related)                        │
│                               ▼                                              │
│                          ┌──────────┐                                        │
│                          │   JOB    │                                        │
│                          └──────────┘                                        │
│                                                                               │
│   ┌──────────┐                                                               │
│   │NOTIFICATION│◀──N:1────── USER                                            │
│   └──────────┘                                                               │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Entity Details:**

| Entity | Mô tả | Key Attributes | Relationships |
|---|---|---|---|
| **User** | Người dùng hệ thống | id, email, password_hash, oauth_providers, created_at | 1:N Jobs, 1:1 BillingAccount, 1:N Notifications |
| **Job** | Một unit xử lý OCR | id, user_id, batch_id, file_id, method, tier, status, created_at, completed_at | N:1 User, N:1 Batch, 1:1 Result, 1:N Transactions |
| **Batch** | Nhóm jobs cùng config | id, user_id, method, tier, retention, created_at | 1:N Jobs |
| **Result** | Kết quả OCR | id, job_id, output_path, format, confidence, expires_at | 1:1 Job |
| **BillingAccount** | Tài khoản credit | id, user_id, balance, created_at | 1:1 User, 1:N Transactions |
| **Transaction** | Giao dịch credit | id, account_id, type (topup/hold/deduct/refund), amount, job_id, created_at | N:1 BillingAccount, N:1 Job (optional) |
| **Notification** | Thông báo user | id, user_id, type, message, read, created_at | N:1 User |

---

## Summary

```
--- SUMMARY HANDOFF #2 (BA → SA) ---
Business Processes: UC-001 (Register), UC-002 (Upload), UC-003 (Configure & Submit), UC-004 (Track Status), UC-005 (View & Download), UC-006 (Top Up), UC-007 (Cancel Job)
Data Entities chính: User, Job, Batch, Result, BillingAccount, Transaction, Notification
Integration Points: Stripe (payment), OAuth (Google, GitHub), R2 (storage), GPU providers (Vast.ai, RunPod)
Non-functional Requirements: Job complete < 5 min (Tier 0), < 1 min (Tier 4), 95%+ accuracy, 99.5% uptime target (Phase 3)
Business Rules mới phát hiện: RULE-037 (Retry), RULE-038 (Retention), RULE-039 (Tier multiplier), RULE-040 (Method base price), RULE-041 (Package bonus)
Gaps phát hiện: Pricing matrix needs confirmation, Budget needs confirmation, Team size needs confirmation
--- ✅ PHASE 2 COMPLETE (Business Analysis) ---
```
