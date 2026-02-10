# Requirements Analysis Brief

> Tài liệu phân tích requirements trước khi viết các tài liệu PO, BA, SA.
> Được tạo dựa trên: `docs/detailed_requirements.md`

---

## 1. Loại Sản Phẩm

**Domain:** SaaS / AI-ML Platform (OCR Processing as a Service)

**Đặc điểm:**
- Platform cung cấp dịch vụ OCR cho người dùng cá nhân/doanh nghiệp
- Web-only, không cung cấp public API
- Pre-paid credit model (pay-as-you-go)
- Multi-tier infrastructure với các mức bảo mật/hiệu năng/giá khác nhau
- Serverless/cloud-native architecture

**Domain-specific additions cần áp dụng:**
- **AI/ML Product:** Processing pipeline, quality metrics, fallback behavior, cost-per-inference
- **SaaS:** Pre-paid billing, user workspace, rate limiting, subscription-like model (credit-based)

---

## 2. Danh Sách Quyết Định Đã Có

Dưới đây là các quyết định thiết kế đã được khẳng định rõ ràng trong requirements — **KHÔNG ĐƯỢC THAY ĐỔI** trong quá trình viết tài liệu.

### 2.1. Architecture Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-001 | **3-layer architecture:** Edge (Cloudflare) → Orchestration (GCP) → Processing (GPU workers) | Section 3.1 |
| DEC-002 | **File binary không đi qua orchestration layer** — Worker lấy file trực tiếp từ storage qua presigned URL | Section 3.1 |
| DEC-003 | **Một orchestrator duy nhất** đảm nhận tất cả chức năng điều phối | Section 3.1 |
| DEC-004 | **Firestore là source of truth duy nhất** cho mọi dữ liệu phi file | Section 3.2 |
| DEC-005 | **Cloudflare R2** cho file storage (gốc + kết quả OCR) | Section 3.2 |
| DEC-006 | **Mỗi tier có queue riêng biệt** — FIFO ordering | Section 3.3 |
| DEC-007 | **Pull-based worker model** — worker chủ động pull job từ queue | Section 3.4 |
| DEC-008 | **Stateless workers** — container chạy trên GPU infrastructure | Section 3.4 |

### 2.2. Business Model Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-009 | **Pre-paid credit model** — nạp credit trước, trừ khi submit job | Section 2.5 |
| DEC-010 | **Tính phí theo số trang** (mỗi trang PDF hoặc mỗi file ảnh = 1 page) | Section 2.5 |
| DEC-011 | **Giá khác nhau theo tổ hợp method × tier** | Section 2.5 |
| DEC-012 | **Credit hold ngay khi submit** — reject nếu không đủ credit | Section 2.5 |

### 2.3. Functional Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-013 | **Không cung cấp public API** — chỉ tương tác qua Web UI | Section 2.1 |
| DEC-014 | **Không phân chia tổ chức (tenant)** — mỗi user có workspace cá nhân | Section 2.1 |
| DEC-015 | **3 methods OCR cố định:** ocr_simple, ocr_table, ocr_code | Section 2.3 |
| DEC-016 | **5 tiers cố định:** Tier 0-4 với đặc điểm xác định | Section 2.4 |
| DEC-017 | **Cùng method cho ra cùng kết quả bất kể tier** — chỉ khác bảo mật/tốc độ/SLA | Section 2.4 |
| DEC-018 | **Thông báo chỉ qua in-app notification** — không email, không webhook | Section 2.9 |
| DEC-019 | **Người dùng tự chọn method** — hệ thống không tự phát hiện loại tài liệu | Section 2.3 |
| DEC-020 | **Tier 0 và Tier 4 always-on** — Tier 1-3 auto on/off | Section 2.4, 3.5 |

### 2.4. Job Processing Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-021 | **Job lifecycle cố định:** SUBMITTED → VALIDATING → QUEUED → DISPATCHED → PROCESSING → COMPLETED | Section 3.3 |
| DEC-022 | **Không retry trong worker** — thất bại ở bất kỳ bước nào = fail job | Section 2.6 |
| DEC-023 | **Retry tối đa 1 lần ở orchestrator** — đẩy job vào queue lại | Section 2.6 |
| DEC-024 | **Dead letter queue + auto refund** cho job fail sau retry | Section 2.6 |
| DEC-025 | **Chỉ huỷ được job đang chờ trong queue** — job đang xử lý không thể huỷ | Section 2.7 |

### 2.5. Data Retention Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-026 | **File gốc mặc định xoá sau 24h** (min 1h, max 30 ngày — user chọn) | Section 2.2 |
| DEC-027 | **Kết quả OCR mặc định lưu 7 ngày** (max 30 ngày) | Section 2.8 |
| DEC-028 | **Lịch sử job lưu 90 ngày** | Section 2.10 |
| DEC-029 | **File trên worker xoá ngay sau khi xử lý xong** | Section 3.6 |

### 2.6. Technology Decisions

| ID | Quyết định | Reference |
|---|---|---|
| DEC-030 | **Cloudflare stack:** Workers, R2, Pages | Section 4 Phase 2 |
| DEC-031 | **GCP stack:** Cloud Run, Pub/Sub, Firestore, Scheduler, Monitoring | Section 4 Phase 2 |
| DEC-032 | **GPU providers:** Vast.ai (Tier 1), RunPod (Tier 2-3), VIP cluster (Tier 4) | Section 2.4 |
| DEC-033 | **Stripe cho billing** | Section 4 Phase 2 |
| DEC-034 | **OAuth providers:** Google, GitHub | Section 2.1 |

---

## 3. Danh Sách Câu Hỏi Mở + Assumptions

### Q-01: OCR đa ngôn ngữ
```
Câu hỏi: Hỗ trợ OCR đa ngôn ngữ?
Assumption: MVP hỗ trợ English + Vietnamese. Các ngôn ngữ khác thêm sau khi có nhu cầu.
Lý do: Requirements đề xuất English + Vietnamese (Section 5, Q1). Đây là 2 ngôn ngữ chính của thị trường mục tiêu.
Ảnh hưởng nếu sai: Cần thêm model/configuration cho ngôn ngữ khác, ảnh hưởng testing matrix.
```

### Q-02: Chữ viết tay
```
Câu hỏi: Hỗ trợ nhận dạng chữ viết tay?
Assumption: KHÔNG hỗ trợ trong MVP. Có thể xem xét Phase 3+.
Lý do: Requirements đề xuất không làm ở MVP do accuracy thấp và cần model riêng (Section 5, Q2).
Ảnh hưởng nếu sai: Cần model riêng, training data, accuracy testing riêng.
```

### Q-03: Giới hạn file size và page count
```
Câu hỏi: Giới hạn cụ thể cho file size và số trang PDF?
Assumption:
  - File đơn lẻ: max 50MB
  - Tổng batch: max 200MB
  - Số trang PDF: max 100 trang/file
Lý do: Đây là giới hạn phổ biến cho các dịch vụ OCR tương tự. Cần validate với thực tế xử lý của worker.
Ảnh hưởng nếu sai: Cần điều chỉnh infrastructure (memory, timeout), pricing model.
```

### Q-04: Rate limit cụ thể
```
Câu hỏi: Rate limit theo user như thế nào?
Assumption:
  - API calls: 100 requests/phút/user
  - Upload: 10 batches/phút/user
  - Concurrent jobs: max 20 jobs pending/user
Lý do: Cân bằng giữa trải nghiệm người dùng và bảo vệ hệ thống. Có thể điều chỉnh sau khi có usage data.
Ảnh hưởng nếu sai: Ảnh hưởng queue sizing, worker scaling, user experience.
```

### Q-05: Grace period cho timeout
```
Câu hỏi: Grace period cụ thể là bao lâu?
Assumption: Grace period = 50% của estimate time (ví dụ: estimate 2 phút → grace 1 phút → total timeout 3 phút).
Lý do: Đủ buffer cho biến động nhưng không quá lâu gây block resource.
Ảnh hưởng nếu sai: Job fail rate, user experience, refund rate.
```

### Q-06: Worker heartbeat interval
```
Câu hỏi: Heartbeat interval và timeout threshold?
Assumption:
  - Heartbeat interval: 15 giây
  - Timeout threshold: 60 giây (4 heartbeats miss)
Lý do: Đủ nhanh để phát hiện worker chết nhưng không quá tải network.
Ảnh hưởng nếu sai: Ảnh hưởng job failover speed, resource cleanup.
```

### Q-07: Worker idle timeout per tier
```
Câu hỏi: Idle timeout cho Tier 1-3 là bao lâu?
Assumption:
  - Tier 1 (Standard): 5 phút idle → shutdown
  - Tier 2 (Enhanced): 10 phút idle → shutdown
  - Tier 3 (Dedicated): 15 phút idle → shutdown
Lý do: Tier cao hơn = startup cost cao hơn = nên giữ worker lâu hơn.
Ảnh hưởng nếu sai: Infrastructure cost, cold start latency.
```

### Q-08: OCR Engine cụ thể
```
Câu hỏi: Engine OCR cụ thể cho mỗi method?
Assumption:
  - ocr_simple: Tesseract 5.x (open-source, proven)
  - ocr_table: Table Transformer hoặc Camelot (chuyên biệt cho bảng)
  - ocr_code: Custom pipeline dựa trên Tesseract + code-aware post-processing
Lý do: Requirements đề xuất Tesseract cho ocr_simple (Section 5, Q8). Các method khác cần research thêm.
Ảnh hưởng nếu sai: Model accuracy, processing time, licensing cost.
```

### Q-09: Pricing cụ thể
```
Câu hỏi: Giá credit cụ thể cho mỗi tổ hợp method × tier?
Assumption: [NEEDS CONFIRMATION] — Cần PO/Business xác định pricing strategy.
Đề xuất mức giá baseline (VND/page):
  - ocr_simple: Tier 0 (100đ) → Tier 1 (200đ) → Tier 2 (400đ) → Tier 3 (800đ) → Tier 4 (2000đ)
  - ocr_table: x2 so với ocr_simple
  - ocr_code: x1.5 so với ocr_simple
Lý do: Cần tham khảo đối thủ và cost structure thực tế.
Ảnh hưởng nếu sai: Revenue, competitive positioning.
```

### Q-10: Credit low threshold notification
```
Câu hỏi: Ngưỡng mặc định cho thông báo credit thấp?
Assumption: Mặc định thông báo khi credit còn dưới 100 pages equivalent. User có thể tự điều chỉnh.
Lý do: Đủ để user có thời gian nạp thêm trước khi hết.
Ảnh hưởng nếu sai: User experience, churn rate.
```

### Q-11: Throughput cao điểm
```
Câu hỏi: Throughput cao điểm dự kiến?
Assumption:
  - MVP: 100 jobs/giờ (concurrent 10 jobs)
  - Phase 2: 500 jobs/giờ (concurrent 50 jobs)
  - Phase 3: 2000 jobs/giờ (concurrent 200 jobs)
Lý do: Cần benchmark thực tế. Giả định này dựa trên typical SMB usage.
Ảnh hưởng nếu sai: Queue sizing, worker scaling, infrastructure cost.
```

### Q-12: Budget hạ tầng
```
Câu hỏi: Budget hạ tầng hàng tháng?
Assumption: [NEEDS CONFIRMATION] — Đề xuất:
  - MVP: $200-500/tháng
  - Phase 2: $500-1500/tháng
  - Phase 3: $1500-5000/tháng (tuỳ traffic)
Lý do: Cần xác định để chọn tier nào available, instance type nào.
Ảnh hưởng nếu sai: Tier availability, scaling capacity, SLA commitments.
```

### Q-13: Real-time notification implementation
```
Câu hỏi: Real-time notification dùng công nghệ gì?
Assumption: Server-Sent Events (SSE) thay vì WebSocket.
Lý do: SSE đơn giản hơn, đủ cho one-way push notification, dễ scale với Cloudflare Workers.
Ảnh hưởng nếu sai: Client implementation, infrastructure complexity.
```

### Q-14: Admin dashboard scope (Phase 3)
```
Câu hỏi: Admin dashboard phạm vi đến đâu?
Assumption: Internal-only dashboard với các chức năng:
  - Xem system metrics (queue depth, error rate, worker status)
  - Review dead letter queue jobs
  - Manual refund
  - User management (suspend, credit adjustment)
  - Billing reconciliation
Lý do: Requirements đề xuất internal-only, Phase 3 (Section 5, Q3).
Ảnh hưởng nếu sai: Dev effort cho Phase 3.
```

### Q-15: GDPR/Compliance approach
```
Câu hỏi: Yêu cầu compliance cụ thể (GDPR, HIPAA)?
Assumption: GDPR-aware từ đầu, HIPAA không trong scope.
  - Data deletion on request
  - Data export capability
  - Consent tracking
  - No PII in logs
Lý do: Requirements đề xuất GDPR-aware từ đầu (Section 5, Q4). HIPAA quá phức tạp cho SMB target.
Ảnh hưởng nếu sai: Toàn bộ cách xử lý và lưu trữ dữ liệu.
```

---

## 4. Mâu Thuẫn / Mơ Hồ Phát Hiện Được

### 4.1. Mơ hồ: Output format cho ocr_code
```
Vấn đề: Requirements nói ocr_code output là Markdown, nhưng không rõ:
  - Markdown format cụ thể như thế nào cho code?
  - Có syntax highlighting không?
  - Metadata kèm theo gồm những gì?

Diễn giải chọn: Output là Markdown với code blocks (```) và language detection. Metadata gồm:
  - detected_language (programming language)
  - confidence_score
  - line_count
  - character_count
```

### 4.2. Mơ hồ: Batch configuration scope
```
Vấn đề: "Tất cả file trong cùng batch phải dùng chung cấu hình (method + tier)" — nhưng:
  - Retention time có phải chung không?
  - Nếu có file lỗi trong batch, các file khác xử lý như thế nào?

Diễn giải chọn:
  - Retention time: Chung cho cả batch
  - File lỗi: Mỗi file là 1 job riêng, fail không ảnh hưởng job khác trong batch
```

### 4.3. Mơ hồ: Credit hold khi batch có nhiều file
```
Vấn đề: "Nếu credit hết giữa batch: các job đã hold credit tiếp tục xử lý, các job chưa submit bị reject"
  - Nhưng "Credit được hold ngay khi submit" — vậy hold cho từng file hay cả batch?

Diễn giải chọn:
  - Khi submit batch: Estimate total credit cần
  - Hold toàn bộ estimated credit
  - Nếu không đủ hold → reject cả batch (atomic)
  - Nếu đủ hold → tạo jobs, mỗi job có credit allocation riêng
  - Refund unused credit nếu thực tế xử lý ít hơn estimate
```

### 4.4. Mơ hồ: Presigned URL expiration
```
Vấn đề: "File trên storage chỉ truy cập được qua presigned URL có thời hạn" — thời hạn là bao lâu?

Diễn giải chọn:
  - Upload URL: 15 phút (đủ để upload file lớn)
  - Download URL (result): 1 giờ (đủ để download)
  - Worker access URL: 2 giờ (đủ cho processing timeout + buffer)
```

### 4.5. Mơ hồ: Confidence score availability
```
Vấn đề: "Kết quả kèm confidence score nếu engine hỗ trợ" — engine nào hỗ trợ, nào không?

Diễn giải chọn:
  - ocr_simple (Tesseract): Có confidence score per word
  - ocr_table: Có confidence score per cell
  - ocr_code: Có confidence score cho language detection, không cho từng ký tự
```

---

## 5. MVP Scope Dự Kiến

### Phase 1 — MVP Core (Theo requirements Section 4)

**Goal:** Chứng minh luồng end-to-end hoạt động trên môi trường local.

**Scope:**
| In Scope | Out of Scope |
|---|---|
| 1 method: ocr_simple | ocr_table, ocr_code |
| 1 tier: Local (Tier 0) | Cloud tiers (1-4) |
| Upload đơn file | Batch upload |
| Status polling | Real-time notification |
| Xem/download kết quả | Advanced result viewer |
| Email/password auth | OAuth (Google, GitHub) |
| Miễn phí (chưa có billing) | Credit system, Stripe |
| In-memory/Redis queue | Pub/Sub |
| Local storage (MinIO) | R2 |
| Firestore emulator | Firestore production |
| Single process orchestrator | Distributed orchestrator |

**Features MVP Phase 1:**
1. F-001: User Authentication (email/password)
2. F-002: File Upload (single file)
3. F-003: OCR Processing (ocr_simple only)
4. F-004: Job Status Tracking (polling)
5. F-005: Result Viewing & Download
6. F-006: Job History (basic)

**Không làm trong Phase 1:**
- Batch upload
- Multiple OCR methods
- Cloud tiers
- Billing/Credit
- OAuth
- Real-time notifications
- Cancel/Refund
- Admin dashboard

### Phase 2 — Cloud Production (Theo requirements Section 4)

**Goal:** Kiến trúc production-ready trên cloud, thêm method và infra tier.

**Added Scope:**
- 3 methods (ocr_simple, ocr_table, ocr_code)
- 2 tiers (Local + Vast.ai)
- Batch upload
- OAuth login
- Full billing (pre-paid credit + Stripe)
- Cancel/refund flow
- Notification center (real-time)
- Job history đầy đủ
- Result viewer
- TLS, presigned URL, file deletion guarantee
- Logging + alerting + distributed tracing

### Phase 3 — Scale (Theo requirements Section 4)

**Goal:** Mở rộng hạ tầng, áp dụng auto-scale, production hardening.

**Added Scope:**
- 5 tiers đầy đủ (Tier 0-4)
- Auto-scale 0 → N workers
- Heartbeat + health check hoàn chỉnh
- Multi-provider failover
- Phân biệt rõ mức bảo mật theo tier
- Monitoring dashboard đầy đủ
- Alert rules hoàn chỉnh
- Audit script định kỳ
- Admin dashboard nội bộ

---

## 6. Tóm Tắt cho Các Phase Tiếp Theo

### Cho PO (Phase 1 documentation):
- Focus vào WHAT và WHY
- 6 MVP features core
- 3 personas: End User, Power User, Admin (Phase 3)
- North Star Metric: Pages Processed Successfully per Month
- Key Business Rules: Credit hold, Job lifecycle, File retention

### Cho BA (Phase 2 documentation):
- Focus vào business logic và data flow
- 6-8 core business processes
- 5-10 data entities
- Integration points: Stripe, OAuth providers
- Business rules chi tiết cho billing và job processing

### Cho SA (Phase 3 documentation):
- Focus vào technical decisions
- 3-layer architecture với rationale
- Tech stack selection với alternatives considered
- Data architecture: Firestore + R2
- Security architecture: TLS, presigned URL, RBAC
- Scaling strategy: Tier-based, auto on/off

---

--- ✅ PHASE 0 COMPLETE: Requirements Analysis Brief ---
