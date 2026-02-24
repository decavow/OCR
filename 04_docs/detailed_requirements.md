# OCR Platform — Scope & Requirements (High-Level)

> Tài liệu xác định scope hệ thống trước khi PO viết tài liệu chi tiết.
> Mỗi mục mô tả **"hệ thống cần làm gì"**, không mô tả cách implement.

---

## 1. Tổng quan hệ thống

Hệ thống cho phép người dùng upload tài liệu (ảnh, PDF) lên web, chọn phương pháp và mức hạ tầng xử lý OCR, nhận kết quả sau khi xử lý xong, và trả phí theo lượng sử dụng thực tế.

---

## 2. Business Requirements

### 2.1. Người dùng & Xác thực

- Người dùng chỉ tương tác qua Web UI, không cung cấp public API.
- Hỗ trợ đăng nhập bằng OAuth (Google, GitHub) hoặc email/password.
- Không phân chia tổ chức (tenant). Mỗi người dùng có workspace cá nhân, mọi dữ liệu lưu trữ và phân quyền theo user.
- Giới hạn tần suất sử dụng (rate limit) theo user để chống lạm dụng.

### 2.2. Upload & Đầu vào

- Hỗ trợ upload file ảnh (PNG, JPEG, TIFF, BMP, WEBP, GIF) và PDF.
- Giới hạn cho input size là 200MB dữ liệu đầu vào, nếu vượt qua hệ thống sẽ báo lỗi và yêu cầu người dùng bỏ bớt tài liệu. Hệ thống xử lý theo batch và tính phí theo thực tế.
- File được validate ngay khi upload (format, integrity). File không hợp lệ bị reject ngay, không vào queue.
- Người dùng chọn thời gian lưu trữ file gốc từ các mức có sẵn (1h, 6h, 12h, 24h, 7d, 30d). Mặc định: 24h.

**Batch Upload & Request Model:**

- Hỗ trợ upload theo batch. Tất cả file trong cùng batch phải dùng chung cấu hình (method + tier).
- Một **request** = một batch chứa nhiều file + cấu hình chung (method, tier, retention).
- Khi submit, hệ thống tạo một request duy nhất chứa toàn bộ files, gán tag dựa trên cấu hình, và đẩy vào queue.

**Cấu hình khi Submit (UI):**

UI hiển thị các lựa chọn dưới dạng dropdown:

| Field | Type | Options |
|-------|------|---------|
| **OCR Service** | Dropdown | Danh sách services được Admin enable |
| **Security Tier** | Dropdown | Các tier available cho service đã chọn |
| **Output Format** | Dropdown | Các format available cho service đã chọn |
| **Retention** | Dropdown | Các mức có sẵn: 1h, 6h, 12h, 24h (default), 7d, 30d |

**Price Estimation:**

- Khi người dùng chọn service + tier + files → hiển thị **estimated price** ngay trên UI.
- Công thức: `price = sum(pages) × unit_price(service, tier)`
- Unit price được config bởi Admin cho mỗi combo service × tier.

> **Phân phase:** Phase 1 không có billing (mọi request miễn phí), pricing hiển thị từ config hardcoded phía frontend. Phase 2 khi implement billing → build pricing API + admin config backend.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SUBMIT REQUEST UI                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  Files: invoice1.pdf, invoice2.pdf (12 pages total)    │       │
│   │                                                          │       │
│   │  OCR Service:    [▼ ocr_table                    ]      │       │
│   │  Security Tier:  [▼ Enhanced (SLA 99.5%)         ]      │       │
│   │  Output Format:  [▼ JSON                          ]      │       │
│   │  Retention:      [▼ 7 days                        ]      │       │
│   │                                                          │       │
│   │  ─────────────────────────────────────────────────────  │       │
│   │  Estimated Price: 48,000 VND                            │       │
│   │  (12 pages × 4,000 VND/page)                            │       │
│   │  ─────────────────────────────────────────────────────  │       │
│   │                                                          │       │
│   │  Your balance: 500,000 VND  ✓ Sufficient                │       │
│   │                                                          │       │
│   │                              [Submit Request]            │       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

- Hệ thống tự động gán **tag** dựa trên service + tier để định tuyến request.

### 2.3. OCR Services

- Mỗi **OCR Service** = Data Processing Pipeline + OCR Model, được đóng gói và deploy độc lập.
- Người dùng tự chọn service, hệ thống không tự phát hiện loại tài liệu.
- Người dùng chịu trách nhiệm về chất lượng output khi chọn sai service.
- Hệ thống cung cấp các preset gợi ý để hướng dẫn người dùng chọn cấu hình phù hợp.

**Danh sách OCR Services (Initial Phase):**

*Danh sách chưa chốt, chỉ liệt kê các service phổ biến và dễ áp dụng cho giai đoạn đầu. Có thể mở rộng thêm sau.*

| Service ID | Tên | Khả năng | Available Formats | Default |
|------------|-----|----------|-------------------|---------|
| `ocr_text_raw` | Text Extract (Raw) | Extract text thuần, không format | `txt`, `json` | `txt` |
| `ocr_text_formatted` | Text Extract (Formatted) | Extract text giữ nguyên layout | `md`, `txt`, `json` | `md` |
| `ocr_table` | Table Extract | Nhận dạng bảng biểu, structured data | `json`, `csv`, `xlsx` | `json` |
| `ocr_handwriting` | Handwriting | Nhận dạng chữ viết tay | `txt`, `json` | `txt` |

> **Phân phase:** Phase 1 chỉ implement `ocr_text_raw` với format `txt`, `json`. Các service và format khác (md, csv, xlsx) thêm cùng lúc khi implement service tương ứng ở Phase 2+.

**Output Format Configuration:**

- Người dùng có thể chọn định dạng output khi submit request.
- Nếu không chọn, hệ thống sử dụng **default format** của service đó.
- OCR Service (worker) chịu trách nhiệm trả về đúng format được yêu cầu. Orchestrator chỉ đóng vai trò vận chuyển kết quả, không chuyển đổi format.

**Service Registration (Admin):**

- Admin khai báo danh sách **available services** trong hệ thống.
- Mỗi service được khai báo sẽ được cấp **access key** để truy cập File Proxy.
- Service không được khai báo → không thể pull jobs, không thể access files.
- Admin có thể enable/disable service mà không cần redeploy.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICE REGISTRATION MODEL                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Admin Dashboard:                                                   │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  Available Services:                                     │       │
│   │  ┌─────────────────────────────────────────────────────┐│       │
│   │  │ ☑ ocr_text_raw     | Tier: 0,1,2 | Key: sk_xxx     ││       │
│   │  │ ☑ ocr_table        | Tier: 1,2,3 | Key: sk_yyy     ││       │
│   │  │ ☐ ocr_handwriting  | Disabled    | -               ││       │
│   │  │ ☑ ocr_text_formatted | Tier: 0,1 | Key: sk_zzz     ││       │
│   │  └─────────────────────────────────────────────────────┘│       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                      │
│   Service được enable → Nhận access key → Có thể pull jobs          │
│   Service bị disable → Không hiển thị trên UI                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Processing Time Expectation:**

- Người dùng thường upload nhiều tài liệu, sẵn sàng **trade-off latency cao**.
- Expected processing time: **lên đến 24 giờ** cho batch lớn.
- Hệ thống tối ưu cho throughput, không phải real-time processing.

### 2.4. Phân tầng hạ tầng (Infrastructure Tiers)

- 5 mức hạ tầng (Tier 0–4), tăng dần về bảo mật, tốc độ, và chi phí.
- Cùng method cho ra cùng kết quả bất kể tier. Sự khác biệt nằm ở mức bảo mật, tốc độ xử lý, và cam kết SLA.

| Tier | Tên | Đặc điểm chính |
|---|---|---|
| 0 | Local | Self-hosted, data không rời nội bộ, không có SLA, chi phí thấp nhất. |
| 1 | Standard | GPU cloud (shared), best-effort SLA, giá rẻ. |
| 2 | Enhanced | GPU cloud (shared) với mã hoá tăng cường, SLA 99.5%. |
| 3 | Dedicated | GPU riêng (dedicated), zero-retention trên worker, SLA 99.9%. |
| 4 | VIP | Cluster riêng biệt, isolated network, end-to-end encryption, SLA 99.95%. |

- **Mặc định tất cả services đều tắt** để tiết kiệm chi phí host mô hình. Chỉ khi có request phù hợp, hệ thống mới trigger bật service.
- Tier 0 (Local) có thể luôn chạy do cost thấp. Tier 1–3 bật khi có job và tắt khi idle. Tier 4 (VIP) tuỳ cam kết SLA với khách hàng.

**Service & Tier Availability trên UI:**

- UI chỉ hiển thị các **OCR Services** được Admin enable.
- Cho mỗi service, UI chỉ hiển thị các **tiers** mà service đó support (theo Admin config).
- Nếu một tier không có service nào available → tier đó bị ẩn khỏi dropdown.
- Tooltip giải thích lý do unavailable (ví dụ: "Service đang bảo trì", "Tier không khả dụng").

*Ma trận Service × Tier (ví dụ):*

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICE × TIER AVAILABILITY MATRIX                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                    Tier 0    Tier 1    Tier 2    Tier 3    Tier 4   │
│                    (Local)   (Std)     (Enhanced)(Dedicated)(VIP)   │
│                 ┌─────────┬─────────┬─────────┬─────────┬─────────┐ │
│  ocr_text_raw   │    ✓    │    ✓    │    ✓    │    -    │    -    │ │
│                 ├─────────┼─────────┼─────────┼─────────┼─────────┤ │
│  ocr_text_fmt   │    ✓    │    ✓    │    -    │    -    │    -    │ │
│                 ├─────────┼─────────┼─────────┼─────────┼─────────┤ │
│  ocr_table      │    -    │    ✓    │    ✓    │    ✓    │    ✓    │ │
│                 ├─────────┼─────────┼─────────┼─────────┼─────────┤ │
│  ocr_handwriting│    -    │    -    │    ✓    │    ✓    │    ✓    │ │
│                 └─────────┴─────────┴─────────┴─────────┴─────────┘ │
│                                                                      │
│   ✓ = Available (Admin enabled)                                     │
│   - = Not available (not configured or not supported)               │
│                                                                      │
│   Cùng service → Cùng kết quả (bất kể tier)                         │
│   Khác tier → Khác bảo mật, khác tốc độ, khác giá                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```            

### 2.5. Thanh toán

- Mô hình pre-paid: người dùng nạp credit trước, trừ credit khi job hoàn thành.
- Tính phí theo số trang (mỗi trang PDF hoặc mỗi file ảnh = 1 page).
- Giá khác nhau theo tổ hợp service × tier (tier cao + service phức tạp = đắt hơn).

**Credit Check & Deduction Flow:**

- **Trước khi submit**: Hệ thống kiểm tra credit có đủ cho toàn bộ request không.
- Nếu không đủ credit → **reject ngay**, không vào queue.
- Nếu đủ credit → **trừ credit ngay** (deduct) và **hold khoản tiền đó** trong hệ thống (chờ xác nhận kết quả), sau đó mới đẩy vào queue.
- Không có trường hợp "credit hết giữa batch" vì đã trừ và hold trước khi submit.

**Billing Settlement (sau khi xử lý):**

- Khi job hoàn thành, module billing xác nhận kết quả thực tế.
- Files thành công → **finalize** (xác nhận trừ tiền vĩnh viễn)
- Files failed → **refund** (hoàn lại khoản đã trừ vào balance)
- Credit flow: `DEDUCT & HOLD (submit) → FINALIZE (success) / REFUND (failed)`

- Cung cấp billing dashboard: lịch sử nạp tiền, lịch sử trừ credit, chi tiết từng job.
- Thông báo khi credit còn dưới ngưỡng do người dùng tự cấu hình.

### 2.6. Xử lý job & Timeout

- Mỗi job có thời gian ước tính (estimate time) dựa trên method và số trang.
- Nếu job vượt quá estimate time + một khoảng grace period mà chưa hoàn thành → đánh dấu thất bại.
- Trong một worker, không retry: thất bại ở bất kỳ bước nào là thất bại cả request đó.
- Tại tầng điều phối (orchestrator), retry tối đa **3 lần** bằng cách đẩy request vào queue lại. Nếu vượt quá 3 lần retry → request vào **dead letter queue**.
- Request vào dead letter queue sẽ được **refund credit tự động**. Admin có thể review và xử lý thủ công.

### 2.7. Huỷ job & Hoàn tiền

- Người dùng có thể huỷ job khi job chưa bắt đầu xử lý (đang chờ trong queue). Credit được hoàn 100%.
- Job đang xử lý thì không thể huỷ.
- Batch cancel: huỷ toàn bộ batch hoặc từng file. Chỉ huỷ được các job còn đang chờ.
- Job thất bại (timeout hoặc lỗi worker): credit tự động hoàn trả.

### 2.8. Kết quả đầu ra

- Định dạng output do **OCR Service (worker) quyết định** dựa trên cấu hình request. Orchestrator chỉ vận chuyển kết quả nguyên vẹn, không chuyển đổi.
- Mỗi service có **default format** và **available formats** riêng (xem bảng mục 2.3).
- Kết quả luôn kèm **metadata** (file info, processing time, service version, confidence score nếu có). Tuy nhiên về phía người dùng chỉ nên trả lại kết quả (metadata được lưu trong db)
- Kết quả lưu trữ với lifecycle riêng so với file gốc. Người dùng chọn thời gian lưu từ các mức có sẵn (mặc định 7 ngày, tối đa 30 ngày).
- Người dùng có thể xem kết quả trực tiếp trên web (Result Viewer) hoặc download về.

**Output Structure (ví dụ JSON):**

```json
{
  "request_id": "req_abc123",
  "file_id": "file_xyz789",
  "service": "ocr_table",
  "format": "json",
  "created_at": "2024-01-15T10:30:00Z",
  "processing_time_ms": 2340,
  "metadata": {
    "service_version": "1.2.0",
    "confidence": 0.95,
    "pages_processed": 3
  },
  "result": { ... }
}
```

### 2.9. Thông báo

- Kênh duy nhất: thông báo trong web (in-app notification). Không email, không webhook.
- Giao diện notification center (bell icon) với đánh dấu đã đọc/chưa đọc.
- Thông báo được đẩy real-time về browser khi người dùng đang online.

**Các sự kiện cần thông báo:**

| Sự kiện | Thời điểm | Nội dung thông báo |
|---------|-----------|-------------------|
| Request submitted | Ngay khi submit thành công | "Request đã được gửi, đang chờ xử lý" |
| Processing started | Khi worker bắt đầu xử lý | "Đang xử lý, ước tính hoàn thành trong ~X phút" |
| Job completed | Khi hoàn thành | "Hoàn thành! Xem kết quả tại đây" |
| Job failed | Khi thất bại | "Thất bại: [lý do]. Credit đã được hoàn trả" |
| Job retrying | Khi đang retry | "Đang thử lại lần 1..." |
| Partial success | Khi batch có file lỗi | "Hoàn thành 8/10 files. 2 files lỗi" |
| Credit low | Khi dưới ngưỡng | "Credit còn thấp (X VND), nạp thêm để tiếp tục sử dụng" |
| Credit refunded | Khi hoàn tiền | "Đã hoàn X VND do job thất bại" |
| File expiring | 24h trước khi xoá | "File sẽ bị xoá trong 24h, download ngay nếu cần" |

### 2.10. Lịch sử & Quản lý

- Mọi lịch sử lưu theo user, không có khái niệm tổ chức.
- Người dùng xem lịch sử với bộ lọc: thời gian, trạng thái, method, tier, tên file, job ID.
- Lịch sử lưu 90 ngày.
- Mỗi job có trang chi tiết: thông tin file, cấu hình đã chọn, timeline xử lý, thời gian thực tế, credit đã trừ, link xem/download kết quả.

---

## 3. Technical Requirements

### 3.1. Phân tách service

- Ba lớp service hoạt động độc lập, giao tiếp qua API:
  - **Edge layer:** Nhận request từ client, lưu trữ file (object storage), phục vụ giao diện web. Không xử lý logic nghiệp vụ.
  - **Orchestration layer:** Xử lý logic nghiệp vụ, điều phối job, quản lý thanh toán, gửi thông báo, quản lý OCR services, lưu log. Một orchestrator duy nhất đảm nhận tất cả chức năng điều phối.
  - **Processing layer (OCR Services):** Mỗi OCR Service = Data Processing + OCR Model. Chỉ xử lý OCR, không có business logic. Có thể chạy trên nhiều loại hạ tầng (self-hosted, cloud GPU) tuỳ tier.

- **Nguyên tắc giao tiếp giữa các layer:**
  - Mỗi layer chỉ được giao tiếp trực tiếp với layer liền kề, **không được vượt cấp**.
  - Worker (Processing layer) **KHÔNG** truy cập trực tiếp vào Object Storage (Edge layer).
  - Orchestration layer chứa **File Proxy Service** — điểm duy nhất (ngoài Edge) có credentials truy cập storage.
  - File Proxy Service kiểm soát chặt chẽ: ai được lấy file nào, khi nào, với quyền gì.

**File Proxy Service:**

- Là service trung gian nằm trong Orchestration layer, đóng vai trò proxy file giữa Object Storage và OCR Services.
- Chỉ File Proxy Service có storage credentials, OCR Services không có.
- OCR Services gọi File Proxy để download/upload file, sử dụng **access_key** được Admin cấp.
- File Proxy xác thực service identity (via access_key) và kiểm tra quyền truy cập file trước khi cho phép.

**Access Control:**

| Entity | Có Storage credentials? | Có access_key? | Có thể access files? |
|--------|------------------------|----------------|----------------------|
| Client | ❌ | ❌ | ✅ via presigned URL (upload/download) |
| Orchestrator | ❌ | N/A (internal) | ✅ via File Proxy (internal network) |
| File Proxy | ✅ | N/A | ✅ trực tiếp Storage |
| OCR Service | ❌ | ✅ (Admin cấp) | ✅ via File Proxy |
| Unregistered Service | ❌ | ❌ | ❌ Bị reject |

**Authentication giữa các thành phần:**

- **Client → Edge**: Sử dụng user authentication (OAuth/session token).
- **Orchestrator → File Proxy**: Internal service authentication (cùng nằm trong private network, dùng service account hoặc internal token).
- **OCR Service → File Proxy**: Sử dụng **access_key** được Admin cấp khi đăng ký service.
- **File Proxy → Storage**: Sử dụng storage credentials (chỉ File Proxy có).

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER COMMUNICATION RULES                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐                                                  │
│   │    CLIENT    │                                                  │
│   └──────┬───────┘                                                  │
│          │ ▲                                                        │
│          ▼ │                                                        │
│   ┌──────────────┐                                                  │
│   │  EDGE LAYER  │  Object Storage                                 │
│   └──────┬───────┘                                                  │
│          │ ▲                                                        │
│          ▼ │  ✓ Allowed (storage credentials)                      │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                   ORCHESTRATION LAYER                         │ │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │ │
│   │  │ Orchestrator │    │  File Proxy  │    │    Queue     │    │ │
│   │  │   Service    │◄──►│   Service    │    │   Service    │    │ │
│   │  │              │    │              │    │              │    │ │
│   │  │ • Job mgmt   │    │ • Storage    │    │ • Single Q   │    │ │
│   │  │ • Auth       │    │   creds      │    │ • Tag filter │    │ │
│   │  │ • Billing    │    │ • ACL check  │    │              │    │ │
│   │  └──────────────┘    └──────┬───────┘    └──────────────┘    │ │
│   └─────────────────────────────┼────────────────────────────────┘ │
│                                 │ ▲                                 │
│                                 ▼ │  ✓ Allowed (via access_key)    │
│   ┌──────────────┐                                                  │
│   │  PROCESSING  │  OCR Services gọi File Proxy (dùng access_key) │
│   │    LAYER     │  KHÔNG có storage credentials                   │
│   │(OCR Services)│  KHÔNG truy cập trực tiếp Storage               │
│   └──────────────┘                                                  │
│                                                                      │
│   ✗ NOT Allowed: OCR Service → Storage (vượt cấp)                  │
│   ✓ Allowed: OCR Service → File Proxy → Storage                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Luồng dữ liệu file (đúng chuẩn):**

```
Upload:   Client → Edge (Storage)
Process:  OCR Service → File Proxy (access_key) → Storage (download)
          OCR Service → File Proxy (access_key) → Storage (upload result)
Download: Client → Edge (Storage)
```

### 3.2. Lưu trữ dữ liệu

- **Object Storage**: File gốc và kết quả OCR lưu trên object storage, có lifecycle rules tự động xoá khi hết hạn.
- **Metadata Database**: Toàn bộ metadata (users, jobs, files, billing, notifications, workers, audit logs) lưu trên database. Database là source of truth duy nhất cho mọi dữ liệu phi file.
- Yêu cầu database:
  - Hỗ trợ **scale to zero** (không tốn chi phí khi không có traffic) — quan trọng cho giai đoạn đầu.
  - Hỗ trợ **transactions** — cần thiết cho các thao tác credit (deduct, hold, refund).
  - Data model phù hợp với pattern: lookup by ID + filter by user.
- Các thao tác liên quan đến credit (deduct, hold, refund) phải dùng database transaction để đảm bảo tính toàn vẹn.

### 3.3. Queue & Job lifecycle

- Job đi qua các trạng thái: SUBMITTED → VALIDATING → QUEUED → PROCESSING → COMPLETED/PARTIAL_SUCCESS. Các nhánh lỗi: REJECTED, CANCELLED, FAILED, RETRYING, DEAD_LETTER.
  - *Ghi chú phân phase: Phase 1 bỏ qua DISPATCHED vì worker pull 1 job/lần. Phase 2+ khi implement batch pull, thêm DISPATCHED giữa QUEUED và PROCESSING để phân biệt "đã pull nhưng chưa xử lý".*
- **PARTIAL_SUCCESS**: Request có ít nhất 1 file thành công và 1 file thất bại. Credit chỉ trừ cho files thành công.

**Request Tagging:**

- Khi người dùng chọn cấu hình (service + tier), hệ thống tự động gán **tag** cho request.
- Tag format: `{service}_{tier}` (ví dụ: `ocr_text_raw_local`, `ocr_table_enhanced`, `ocr_handwriting_standard`).
- Tag được gắn vào message khi đẩy vào queue.
- Service (worker) đăng ký danh sách tags mà mình có thể xử lý, khi pull sẽ filter chỉ lấy requests có tag khớp.

**Queue Architecture:**

Hệ thống cần message queue hỗ trợ:
- **Tag-based filtering**: Service có thể pull đúng loại request dựa trên tag.
- **Priority support** (optional): Phân biệt mức ưu tiên giữa các tiers.
- **Durability**: Messages không bị mất khi service restart.
- **ACK/NACK mechanism**: Đảm bảo message được xử lý hoặc retry.

**Priority-based Queuing (Optional):**

- Có thể chia queue theo priority levels nếu cần (VIP > Dedicated > Enhanced > Standard > Local).
- Trade-off: nhiều queue = phức tạp hơn, cost cao hơn.
- Recommendation: bắt đầu với single queue + tag filtering, tách queue nếu cần priority.

```
┌─────────────────────────────────────────────────────────────────────┐
│                   QUEUE WITH SERVICE + TIER FILTERING                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User chọn: Service=ocr_table, Tier=Enhanced                       │
│                           │                                          │
│                           ▼                                          │
│   Orchestrator gán tag:  "ocr_table_enhanced"                       │
│                           │                                          │
│                           ▼                                          │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │                    MESSAGE QUEUE                         │       │
│   │                                                          │       │
│   │  Topics/Subjects:                                        │       │
│   │  • ocr.text_raw.local      • ocr.table.enhanced         │       │
│   │  • ocr.text_raw.standard   • ocr.table.standard         │       │
│   │  • ocr.handwriting.enhanced                              │       │
│   │                                                          │       │
│   └─────────────────────────────────────────────────────────┘       │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│   │ Service:    │   │ Service:    │   │ Service:    │              │
│   │ ocr_table   │   │ ocr_text_raw│   │ocr_handwrite│              │
│   │             │   │             │   │             │              │
│   │ Subscribe:  │   │ Subscribe:  │   │ Subscribe:  │              │
│   │ ocr.table.* │   │ocr.text_raw │   │ocr.handwrite│              │
│   │             │   │    .*       │   │    .*       │              │
│   │ Pull: all   │   │             │   │             │              │
│   │ ocr_table   │   │             │   │             │              │
│   │ requests    │   │             │   │             │              │
│   └─────────────┘   └─────────────┘   └─────────────┘              │
│                                                                      │
│   Mỗi service subscribe theo pattern: ocr.{service_id}.*           │
│   Nhận được requests từ tất cả tiers mà service đó handle          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Ưu điểm kiến trúc này:**
- Filter theo **cả service lẫn tier**, không chỉ tier
- Service A có thể handle tier 1,2,3 trong khi Service B chỉ handle tier 0,1
- Dễ dàng thêm service mới mà không cần thay đổi queue infrastructure
- Visibility tốt: xem được tất cả pending requests ở một nơi

**ACK Timing Strategy:**

Khi service pull nhiều requests, việc ACK (acknowledge) message cần được xử lý cẩn thận:

| Strategy | Mô tả | Ưu điểm | Nhược điểm |
|----------|-------|---------|------------|
| **ACK trước xử lý** | ACK ngay khi pull | Đơn giản | Mất message nếu service crash |
| **ACK sau xử lý** | ACK sau khi hoàn thành từng request | An toàn | Timeout nếu xử lý lâu |
| **Visibility timeout** | Message ẩn trong thời gian xử lý | Cân bằng | Cần estimate thời gian chính xác |

**Đề xuất**: Sử dụng **visibility timeout** kết hợp với **heartbeat extension**:
- Khi pull, message chuyển sang trạng thái "invisible" trong N phút.
- Trong quá trình xử lý, service gửi heartbeat để extend timeout.
- Nếu service crash (không heartbeat), message tự động visible lại sau timeout.
- ACK chỉ gửi sau khi xử lý hoàn tất thành công.

**Dead Letter Queue & Retry:**

- Mỗi request có **retry counter** được track trong metadata.
- Nếu request fail (service crash, timeout, lỗi xử lý):
  - Retry counter tăng 1
  - Nếu retry < **max retries (3 lần)** → đẩy lại vào queue chính
  - Nếu retry >= 3 → **cancel task** và trả về failed cho người dùng -> Credit được **refund tự động** khi task bị báo failed

**Service Batch Pull:**

- Một **request** có thể chứa nhiều file bên trong (batch upload từ user).
- Service có thể **pull nhiều requests cùng lúc** để xử lý batch, nhưng đảm bảo size của các request không vượt quá limit (200MB).
- Service pull requests cho đến khi đạt **internal batch limit** (số files hoặc total size), sau đó xử lý tập trung.
- Các limit này là **config của service**, không phải limit của user.

> **Phân phase:** Phase 1 worker pull 1 job/lần (sequential processing). Batch pull là optimization cho Phase 2+ khi có cloud GPU — load model 1 lần, xử lý nhiều requests.

| Service Batch Limit | Giá trị mẫu | Ghi chú |
|---------------------|-------------|---------|
| Max total size per batch | 200 MB | Có thể config theo service |
| Max requests per pull | 10 requests | Tránh pull quá nhiều cùng lúc |

**Multi-Request Processing & Result Return:**

Khi service pull nhiều requests (từ nhiều users), kết quả được trả về như sau:

```
┌─────────────────────────────────────────────────────────────────────┐
│                  MULTI-REQUEST PROCESSING FLOW                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Service pull 4 requests (11 files total):                         │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  Req1: user_A, [file1, file2]           → 2 files       │       │
│   │  Req2: user_B, [file3]                  → 1 file        │       │
│   │  Req3: user_A, [file4, file5, file6]    → 3 files       │       │
│   │  Req4: user_C, [file7..file11]          → 5 files       │       │
│   └─────────────────────────────────────────────────────────┘       │
│                           │                                          │
│                           ▼                                          │
│   Service xử lý batch (load model 1 lần):                           │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  Process file1  → result1   (Req1)                      │       │
│   │  Process file2  → result2   (Req1)                      │       │
│   │  Process file3  → result3   (Req2)                      │       │
│   │  Process file4  → result4   (Req3)                      │       │
│   │  Process file5  → ✗ FAILED  (Req3) → flag, continue    │       │
│   │  Process file6  → result6   (Req3)                      │       │
│   │  Process file7  → result7   (Req4)                      │       │
│   │  ...                                                     │       │
│   └─────────────────────────────────────────────────────────┘       │
│                           │                                          │
│                           ▼                                          │
│   Kết quả trả về **per request** (không sort):                      │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  Req1 → COMPLETED:                                       │       │
│   │         Upload [result1, result2] → File Proxy          │       │
│   │         Update status → Orchestrator                     │       │
│   │         Billing: 2 pages charged                         │       │
│   │                                                          │       │
│   │  Req2 → COMPLETED:                                       │       │
│   │         Upload [result3] → File Proxy                    │       │
│   │         Update status → Orchestrator                     │       │
│   │         Billing: 1 page charged                          │       │
│   │                                                          │       │
│   │  Req3 → PARTIAL_SUCCESS:                                 │       │
│   │         Upload [result4, result6] → File Proxy          │       │
│   │         Update status → Orchestrator                     │       │
│   │         Billing: 2 pages charged, 1 page refunded       │       │
│   │                                                          │       │
│   │  Req4 → COMPLETED:                                       │       │
│   │         Upload [result7..result11] → File Proxy         │       │
│   │         Update status → Orchestrator                     │       │
│   │         Billing: 5 pages charged                         │       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Key points:**
- Mỗi request được track riêng biệt, có status và billing riêng.
- Kết quả upload theo request, không gộp chung.
- Nếu 1 file failed → flag failed, tiếp tục xử lý file tiếp theo trong batch.
- Billing module tính toán dựa trên kết quả thực tế của từng request.

**Failure Handling (Partial Success):**

- Nếu một file trong request bị lỗi, service **gán flag FAILED** cho file đó và tiếp tục xử lý file tiếp theo.
- Khi trả kết quả về Orchestrator, module billing tự động tính toán:
  - Files thành công → trừ credit
  - Files failed → refund credit đã hold
- Request status = PARTIAL_SUCCESS nếu có ít nhất 1 file thành công và 1 file thất bại.

### 3.4. OCR Service Management

- Mỗi **OCR Service** = Data Processing Pipeline + OCR Model, được deploy như stateless container.
- Service chủ động pull **nhiều requests** từ queue cho đến khi đạt batch limit (pull-based, không phải push).
- Service xử lý batch requests từ **nhiều users khác nhau** trong cùng một lần processing (nếu chúng không vượt quá limit size) để tối ưu tài nguyên.
- Service gửi heartbeat định kỳ về orchestrator. Nếu mất heartbeat quá ngưỡng → service coi như dead, jobs chuyển trạng thái thất bại.
- Hệ thống có khả năng scale theo chiều ngang (horizontal scaling).

**Luồng xử lý của OCR Service:**

Service không truy cập trực tiếp vào Object Storage. Mọi tương tác với file phải thông qua **File Proxy Service** (nằm trong Orchestration layer):

1. Service pull **nhiều requests** từ queue (filter by registered tags) cho đến khi đạt batch limit.
2. Service gọi **File Proxy Service** để download files (sử dụng access key được Admin cấp).
3. File Proxy xác thực service identity, kiểm tra quyền, stream files từ Storage về Service.
4. Service xử lý OCR cho toàn bộ batch (load model 1 lần, process nhiều files). Nếu file lỗi → flag FAILED, tiếp tục.
5. Service gọi **File Proxy Service** để upload results (per request, không gộp).
6. Service gọi Orchestrator để cập nhật trạng thái **cho từng request** (COMPLETED / PARTIAL_SUCCESS).
7. Orchestrator trigger Billing module để tính toán và finalize/refund credit.
8. **Service cleanup** — xoá tất cả downloaded files và generated results khỏi local disk.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OCR SERVICE PROCESSING FLOW                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌───────────┐   ┌──────────────┐   ┌────────────┐   ┌────────┐   │
│   │OCR SERVICE│   │ FILE PROXY   │   │ORCHESTRATOR│   │STORAGE │   │
│   └─────┬─────┘   └──────┬───────┘   └─────┬──────┘   └───┬────┘   │
│         │                │                 │              │         │
│         │ 1. Pull requests (filter by tags)│              │         │
│         │◄─────────────────────────────────│              │         │
│         │                │                 │              │         │
│         │ 2. Download files (access_key)   │              │         │
│         │───────────────►│                 │              │         │
│         │                │ verify key      │              │         │
│         │                │ check ACL       │              │         │
│         │                │─────────────────────────────────►        │
│         │                │◄────────────────────────────────│        │
│         │ 3. Stream files│                 │              │         │
│         │◄───────────────│                 │              │         │
│         │                │                 │              │         │
│         │ ┌────────────────────────────────────────────────┐        │
│         │ │  4. OCR Processing (batch mode)                │        │
│         │ │  • Load model 1x                               │        │
│         │ │  • Process files sequentially                  │        │
│         │ │  • If file error → flag FAILED, continue next  │        │
│         │ │  • Track success/failure per file              │        │
│         │ └────────────────────────────────────────────────┘        │
│         │                │                 │              │         │
│         │ 5. Upload results (per request)  │              │         │
│         │───────────────►│                 │              │         │
│         │                │─────────────────────────────────►        │
│         │                │◄────────────────────────────────│        │
│         │ Upload OK      │                 │              │         │
│         │◄───────────────│                 │              │         │
│         │                │                 │              │         │
│         │ 6. Update status (per request)   │              │         │
│         │    + file results metadata       │              │         │
│         │──────────────────────────────────►              │         │
│         │                │                 │              │         │
│         │                │    7. Trigger Billing module   │         │
│         │                │       Finalize success / Refund failed   │
│         │                │                 │              │         │
│         │ ┌────────────────────────────────────────────────┐        │
│         │ │  8. Service Cleanup                            │        │
│         │ │  • Delete all downloaded files from local disk │        │
│         │ │  • Delete all generated results from local disk│        │
│         │ │  • Ready for next batch                        │        │
│         │ └────────────────────────────────────────────────┘        │
│         │                │                 │              │         │
└─────────────────────────────────────────────────────────────────────┘

OCR Service có access_key (được Admin cấp khi register)
OCR Service KHÔNG có storage credentials
Mọi file access đều qua File Proxy Service
```

### 3.5. Service Scaling

Orchestrator chịu trách nhiệm quản lý vòng đời của OCR Services: bật, tắt, restart, và scale dựa trên tình trạng thực tế của hệ thống.

**Service Availability:**

| Service Type | Default State | Trigger | Notes |
|--------------|---------------|---------|-------|
| Local (Tier 0) | OFF (có thể ON) | On-demand | Cost thấp, có thể để always-on |
| Cloud Standard | OFF | On-demand | Bật khi có request phù hợp |
| Cloud Enhanced | OFF | On-demand | Bật khi có request phù hợp |
| Cloud Dedicated | OFF | On-demand | Bật khi có request phù hợp |
| VIP (Tier 4) | Tuỳ SLA | Cam kết | Có thể always-on theo hợp đồng |

#### 3.5.1. Vòng đời bật/tắt Service

Mặc định tất cả services đều ở trạng thái **OFF** để tiết kiệm chi phí. Orchestrator chịu trách nhiệm bật/tắt service dựa trên nhu cầu thực tế.

**Trạng thái của Service:**

Mỗi service instance có một trong các trạng thái sau:

| Trạng thái | Mô tả | Hành vi |
|------------|-------|---------|
| **OFF** | Service chưa được khởi động | Không poll queue, không tiêu tốn tài nguyên |
| **STARTING** | Đang khởi động (cold start) | Load model, khởi tạo pipeline, chưa nhận request |
| **READY** | Đã sẵn sàng xử lý | Bắt đầu poll queue, gửi heartbeat |
| **PROCESSING** | Đang xử lý batch | Poll queue tạm dừng, gửi heartbeat kèm progress |
| **IDLE** | Đã sẵn sàng nhưng không có request | Tiếp tục poll queue, đếm thời gian idle |
| **STOPPING** | Đang dừng (chờ hoàn thành request cuối) | Không nhận request mới, hoàn thành batch hiện tại |
| **ERROR** | Gặp lỗi không thể tự phục hồi | Ngừng xử lý, chờ Orchestrator quyết định restart hoặc kill |

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SERVICE LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                     Orchestrator trigger                             │
│                           │                                          │
│   ┌─────┐   start    ┌──────────┐   ready    ┌─────────┐           │
│   │ OFF │────────────►│ STARTING │───────────►│  READY  │           │
│   └─────┘             └──────────┘            └────┬────┘           │
│      ▲                     │                       │ ▲               │
│      │                     │ fail                   │ │               │
│      │                     ▼                       ▼ │               │
│      │               ┌─────────┐            ┌────────────┐          │
│      │               │  ERROR  │◄───────────│ PROCESSING │          │
│      │               └────┬────┘   error    └────┬───────┘          │
│      │                    │                      │                   │
│      │              restart│               done  │                   │
│      │                    ▼                      ▼                   │
│      │               ┌──────────┐          ┌──────────┐             │
│      │               │ STARTING │          │   IDLE   │             │
│      │               └──────────┘          └────┬─────┘             │
│      │                                          │                    │
│      │                              idle timeout│                    │
│      │                                          ▼                    │
│      │                                   ┌──────────┐               │
│      └───────────────────────────────────│ STOPPING │               │
│                    shutdown complete      └──────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Quy trình bật Service (Start):**

Khi Orchestrator phát hiện có pending requests mà không có service phù hợp đang chạy:

1. Orchestrator xác định loại service cần bật dựa trên **tag** của request (service + tier).
2. Orchestrator kiểm tra service đó đã được **Admin enable** chưa (theo Service Registration). Nếu chưa enable → không bật, request chờ trong queue.
3. Orchestrator gửi lệnh start tới hạ tầng tương ứng (tuỳ tier: local server, cloud provider, GPU provider).
4. Service chuyển sang trạng thái **STARTING** — quá trình này bao gồm khởi động container, load OCR model vào memory, khởi tạo data processing pipeline.
5. Khi sẵn sàng, service gửi **heartbeat đầu tiên** về Orchestrator → chuyển sang **READY**.
6. Service bắt đầu poll queue theo registered tags.

**Cold start time** (thời gian từ OFF → READY) phụ thuộc vào tier và model size, có thể từ vài giây đến vài phút. Hệ thống cần track cold start time thực tế để cung cấp estimated wait time chính xác cho user khi submit request vào service đang OFF.

**Quy trình tắt Service (Stop):**

Khi service idle quá ngưỡng thời gian configurable:

1. Orchestrator gửi lệnh **graceful shutdown** cho service.
2. Service chuyển sang trạng thái **STOPPING** — ngừng poll queue mới, nhưng **hoàn thành batch đang xử lý** (nếu có).
3. Sau khi batch hiện tại hoàn tất (upload results, update status, cleanup), service xác nhận đã dừng.
4. Service chuyển sang **OFF**, giải phóng tài nguyên.

Hệ thống **không bao giờ kill service đang xử lý** trừ khi worker bị phát hiện là dead hoặc stalled. Nếu cần tắt gấp (ví dụ: spot instance bị thu hồi), các requests đang xử lý sẽ được coi như failed và quay lại queue để retry.

**Quy trình restart Service:**

Khi Orchestrator phát hiện worker có vấn đề (error rate cao, stall, consecutive failures):

1. Orchestrator gửi lệnh graceful shutdown (nếu service còn responsive) hoặc force kill (nếu service không responsive).
2. Các requests đang xử lý bởi worker đó sẽ được đánh dấu **failed** và quay lại queue (nếu chưa vượt retry limit).
3. Orchestrator khởi động instance mới thay thế.
4. Nếu instance mới cũng gặp lỗi tương tự → Orchestrator **không tiếp tục restart**, mà chuyển sang alert admin.

#### 3.5.2. Scaling Signals

Để ra quyết định scaling chính xác, Orchestrator cần thu thập và đánh giá ba nhóm tín hiệu: **Demand** (khối lượng công việc), **Capacity** (năng lực xử lý), và **Health** (tình trạng sức khoẻ của workers).

**Demand Signals — "Có bao nhiêu việc cần làm?"**

Hệ thống phải theo dõi không chỉ số lượng requests đang chờ, mà còn **xu hướng thay đổi** của workload theo thời gian:

| Signal | Mô tả | Tại sao cần |
|--------|-------|-------------|
| Queue depth | Số requests đang chờ xử lý (theo tag) | Biết khối lượng tồn đọng hiện tại |
| Queue growth rate | Tốc độ queue tăng/giảm theo thời gian | Phân biệt "queue đầy nhưng đang vơi" vs "queue đầy và tiếp tục tăng" |
| Estimated workload | Tổng số pages/tổng file size trong queue | Đánh giá khối lượng xử lý thực tế — 10 requests × 100 pages khác hoàn toàn 10 requests × 2 pages |

Queue depth đơn thuần không đủ để ra quyết định. Ví dụ: queue depth = 50 nhưng tốc độ xử lý nhanh hơn tốc độ nạp vào → queue đang giảm dần → không cần scale. Ngược lại, queue depth = 50 và tốc độ nạp liên tục vượt tốc độ xử lý (consumer lag dương) → cần thêm capacity.

**Capacity Signals — "Workers đang hoạt động thế nào?"**

Heartbeat hiện tại chỉ cho biết "worker còn sống." Điều này không đủ — hệ thống cần biết worker đang xử lý hiệu quả hay không:

| Signal | Mô tả | Tại sao cần |
|--------|-------|-------------|
| Processing rate | Số files/pages worker xử lý được per unit time | Tính toán capacity thực tế để so sánh với demand |
| Worker utilization | Tỷ lệ thời gian worker thực sự đang xử lý vs idle | Phát hiện worker bị bottleneck ở download/upload thay vì OCR |
| Processing progress | Request đang xử lý, số files đã xong / tổng files | Detect worker stuck (alive nhưng không tiến triển) |

Do đó, **heartbeat từ worker phải mang đủ thông tin progress**, không chỉ alive signal. Payload tối thiểu bao gồm: trạng thái hiện tại (idle / processing / uploading), request đang xử lý (nếu có), số files đã hoàn thành / tổng files trong batch, và thời điểm bắt đầu xử lý request hiện tại.

Từ heartbeat data này, Orchestrator có thể tính toán processing rate và utilization mà không cần worker tự report metrics phức tạp.

**Health Signals — "Có gì đang sai không?"**

Nhóm tín hiệu này giúp phân biệt giữa "cần thêm worker" (scale) và "worker hiện tại đang lỗi" (remediation):

| Signal | Mô tả | Tại sao cần |
|--------|-------|-------------|
| Error rate | Tỷ lệ files failed / tổng files đã xử lý | Phát hiện worker đang gặp lỗi hệ thống |
| Consecutive failures | Số requests fail liên tiếp | Phân biệt lỗi data (1 file lỗi) vs lỗi hệ thống (tất cả đều lỗi) |
| Processing stall | Worker gửi heartbeat nhưng progress không đổi trong thời gian dài | Phát hiện worker bị treo (alive nhưng không làm việc) |

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SCALING SIGNALS OVERVIEW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌───────────────────┐                                             │
│   │  DEMAND SIGNALS   │  "Có bao nhiêu việc?"                      │
│   │  • Queue depth    │                                             │
│   │  • Growth rate    │──────┐                                      │
│   │  • Est. workload  │      │                                      │
│   └───────────────────┘      │                                      │
│                              ▼                                      │
│                    ┌───────────────────┐                             │
│                    │   ORCHESTRATOR    │                             │
│                    │                   │──► Scale UP / DOWN / OFF    │
│                    │   Evaluate &      │──► Restart unhealthy worker │
│                    │   Decide          │──► Alert admin              │
│                    │                   │──► Do nothing               │
│                    └───────────────────┘                             │
│                              ▲                                      │
│   ┌───────────────────┐      │      ┌───────────────────┐          │
│   │ CAPACITY SIGNALS  │      │      │  HEALTH SIGNALS   │          │
│   │ • Processing rate │──────┘──────│ • Error rate      │          │
│   │ • Utilization     │             │ • Consec. failures│          │
│   │ • Progress info   │             │ • Stall detection │          │
│   └───────────────────┘             └───────────────────┘          │
│                                                                      │
│   Ba nhóm tín hiệu kết hợp → Orchestrator ra quyết định            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 3.5.3. Scaling Decision Requirements

Hệ thống phải có khả năng phân biệt và phản ứng đúng với các tình huống sau:

**Tình huống 1 — Demand tăng, capacity đủ:**
Queue depth tăng nhưng tốc độ xử lý vẫn kịp (queue đang giảm dần). Workers healthy và hoạt động bình thường. Hệ thống không cần hành động — capacity hiện tại đang đáp ứng được.

**Tình huống 2 — Demand tăng, capacity không đủ:**
Queue tăng liên tục, tốc độ nạp vượt tốc độ xử lý (consumer lag dương). Workers healthy nhưng không kịp xử lý. Hệ thống cần **bật thêm worker instances** (hoặc chuyển từ OFF → ON ở giai đoạn đầu).

**Tình huống 3 — Worker có vấn đề:**
Queue tăng không phải vì demand mới, mà vì workers đang lỗi hoặc xử lý chậm bất thường. Error rate tăng, processing rate giảm, hoặc worker bị stall. Hệ thống cần **restart worker có vấn đề** (xem quy trình restart tại 3.5.1), không phải scale thêm. Nếu restart không giải quyết → alert admin.

**Tình huống 4 — Demand giảm, workers idle:**
Queue gần trống, workers không có requests để xử lý, đã idle quá ngưỡng thời gian configurable. Hệ thống cần **tắt workers** theo quy trình graceful shutdown (xem 3.5.1) để tiết kiệm chi phí.

**Tình huống 5 — Cold start:**
Không có workers đang chạy, một request mới vào queue. Hệ thống cần **bật đúng loại worker** dựa trên tag của request (xem quy trình bật tại 3.5.1) và **thông báo cho user** estimated startup time.

```
┌─────────────────────────────────────────────────────────────────────┐
│                   SCALING DECISION REQUIREMENTS                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Demand ↑ + Capacity OK + Health OK                                │
│   → Không hành động (hệ thống đang xử lý kịp)                      │
│                                                                      │
│   Demand ↑ + Capacity thiếu + Health OK                             │
│   → Bật thêm workers (scale up)                                     │
│                                                                      │
│   Demand bất kỳ + Health có vấn đề                                  │
│   → Restart worker lỗi (remediation, không phải scaling)            │
│   → Nếu restart không giải quyết → Alert admin                      │
│                                                                      │
│   Demand ↓ + Workers idle quá ngưỡng                                │
│   → Graceful shutdown → OFF                                         │
│                                                                      │
│   Demand mới + Không có worker nào ON                               │
│   → Bật worker phù hợp (cold start)                                │
│   → Thông báo estimated startup time cho user                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 3.5.4. Yêu cầu cho Heartbeat

Heartbeat là nguồn dữ liệu chính để Orchestrator đánh giá capacity và health. Hệ thống yêu cầu heartbeat phải đáp ứng các tiêu chí sau:

**Tần suất:** Heartbeat gửi định kỳ theo khoảng thời gian configurable. Ngưỡng mất heartbeat (coi worker là dead) cũng phải configurable.

**Nội dung:** Heartbeat phải chứa đủ thông tin để Orchestrator đánh giá cả capacity lẫn health, bao gồm:

| Thông tin | Mô tả | Phục vụ |
|-----------|-------|---------|
| Service ID | Định danh worker | Tracking |
| Trạng thái | idle / processing / uploading / error | Capacity + Health |
| Request đang xử lý | request_id (nếu đang processing) | Progress tracking |
| Tiến độ batch | Số files đã xong / tổng files | Progress + Stall detection |
| Thời điểm bắt đầu | Timestamp bắt đầu xử lý request hiện tại | Stall detection (so sánh với thời gian hiện tại) |
| Error count | Số lỗi gặp phải trong batch hiện tại | Health assessment |

**Phát hiện bất thường:** Orchestrator phải có khả năng phát hiện worker bất thường dựa trên heartbeat data:

| Bất thường | Dấu hiệu | Hành động |
|-----------|----------|-----------|
| Worker dead | Mất heartbeat quá ngưỡng | Requests đang xử lý → failed, quay lại queue |
| Worker stalled | Heartbeat đều đặn nhưng progress không đổi | Trigger restart (xem 3.5.1) |
| Worker unhealthy | Error count tăng liên tục qua nhiều heartbeat | Trigger restart hoặc alert admin |

#### 3.5.5. Metrics Collection Xuyên Suốt Các Phase

Mặc dù giai đoạn đầu chỉ sử dụng mô hình on/off đơn giản (0 hoặc 1 instance), hệ thống vẫn cần **thu thập đầy đủ metrics từ Phase 1** để phục vụ auto-scaling ở Phase 3. Sự khác biệt giữa các phase chỉ nằm ở cách sử dụng metrics, không phải ở việc thu thập:

| Phase | Metrics thu thập | Cách sử dụng |
|-------|-----------------|--------------|
| Phase 1 | Queue depth, heartbeat (basic) | ON/OFF đơn giản: có request → bật, idle → tắt |
| Phase 2 | + Growth rate, processing rate, error rate | ON/OFF thông minh hơn: phân biệt scale vs restart |
| Phase 3 | + Utilization, consumer lag, workload estimation | Auto-scale 0→N: tính toán số instances cần thiết |

Yêu cầu: metrics collection infrastructure được thiết kế từ Phase 1 với khả năng mở rộng, để khi chuyển sang Phase 2-3 chỉ cần thêm metrics mới và thay đổi logic quyết định, không cần thay đổi kiến trúc thu thập.

### 3.6. Bảo mật

- Mã hoá in-transit (TLS) trên mọi kết nối giữa các thành phần.
- Mã hoá at-rest cho file storage và database (mặc định của provider).
- File trên worker bị xoá ngay sau khi xử lý xong, không cache lên disk.
- File trên storage chỉ truy cập được qua presigned URL có thời hạn.
- Đảm bảo xoá file đúng hạn bằng nhiều lớp cơ chế: lifecycle rules tự động, cron job backup, audit định kỳ.
- Mức bảo mật tăng dần theo tier (xem bảng 2.4).

### 3.7. Observability

- Logging: request logs, processing logs, audit logs (lưu theo thời hạn khác nhau, tối thiểu 30 ngày đến tối đa 2 năm tuỳ loại).
- Monitoring & alerting: giám sát queue depth, tỷ lệ lỗi, heartbeat worker, chi phí worker idle, dung lượng storage, tần suất refund. Alert khi vượt ngưỡng.
- Distributed tracing: mỗi request gắn trace ID, truyền xuyên suốt qua tất cả service để debug end-to-end.

---

## 4. MVP Phasing

### Phase 1 — Khung hệ thống + Local OCR

Chứng minh luồng end-to-end hoạt động trên môi trường local.

- 1 method (ocr_simple), 1 tier (Local).
- Upload đơn file, xem status bằng polling, xem/download kết quả.
- Auth đơn giản (email/password), chưa có billing (mọi request miễn phí).
- Queue vẫn đảm bảo transfer data với filtered data, storage local, database emulator.
- Orchestrator là single process chạy cùng server.
- Khoá các quyết định kiến trúc cốt lõi: job lifecycle, data flow pattern, data model, scale controller interface.

### Phase 2 — Lên Cloud + Mở rộng service

Kiến trúc production-ready trên cloud, thêm method và infra tier, chưa auto-scale.

- 3 methods, 2 tiers (Local + Cloud).
- Deploy đầy đủ lên cloud infrastructure (edge layer + orchestration layer + processing layer).
- Worker on/off đơn giản (0 hoặc 1 worker per tier).
- Web UI hoàn thiện: batch upload, chọn method + tier, notification center (real-time), job history, result viewer.
- OAuth login, billing (pre-paid credit), cancel/refund flow.
- Bảo mật cơ bản: TLS, presigned URL, file deletion guarantee.
- Logging + alerting + distributed tracing.
- Chuyển từ database emulator sang production mà không cần migration.

### Phase 3 — Scale & Thêm hạ tầng

Mở rộng hạ tầng, áp dụng auto-scale, production hardening.

- 5 tiers đầy đủ (Tier 0–4).
- Auto-scale 0 → N workers dựa trên queue depth, thời gian chờ, GPU utilization.
- Heartbeat + health check hoàn chỉnh, multi-provider failover.
- Phân biệt rõ mức bảo mật theo tier.
- Monitoring dashboard đầy đủ, alert rules hoàn chỉnh, audit script định kỳ.
- Admin dashboard nội bộ.

---

## 5. Câu hỏi mở

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| 1 | Hỗ trợ OCR đa ngôn ngữ? | Chọn model, ma trận kiểm thử. Đề xuất bắt đầu với English + Vietnamese. |
| 2 | Hỗ trợ nhận dạng chữ viết tay? | Cần model riêng, accuracy thấp. Đề xuất không làm ở MVP. |
| 3 | Admin dashboard phạm vi đến đâu? | Effort phát triển UI. Đề xuất internal-only, Phase 3. |
| 4 | Yêu cầu compliance (GDPR, HIPAA)? | Ảnh hưởng toàn bộ cách xử lý và lưu trữ dữ liệu. Đề xuất GDPR-aware từ đầu. |
| 5 | Throughput cao điểm dự kiến? | Ảnh hưởng thiết kế queue và scaling. Cần benchmark. |
| 6 | Budget hạ tầng hàng tháng? | Quyết định tier nào available, có dùng reserved instance không. Cần xác định. |
| 7 | Rủi ro spot/preemptible instance bị thu hồi? | Chiến lược failover. Chấp nhận rủi ro ở MVP 2, failover ở MVP 3. |
| 8 | Engine OCR cụ thể cho mỗi method? | Effort đánh giá model. Đánh giá các options phù hợp cho từng method. |
| 9 | Ngưỡng chuyển đổi database (document → relational)? | Chi phí ở quy mô lớn. Monitor ở MVP 3, cân nhắc migrate nếu DB cost vượt ngưỡng. |
| 10 | ACK timing strategy cụ thể? | Ảnh hưởng reliability và latency. Xem đề xuất tại mục 3.3. |