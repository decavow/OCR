# OCR Platform — SAD Review Questionnaire

> Bộ câu hỏi đánh giá tài liệu System Architecture Document (SAD) cho Phase 1 Local MVP.
> Mục đích: Đảm bảo tài liệu kiến trúc phản ánh đúng và đủ ý định thiết kế của team.

---

## Cách sử dụng

Mỗi câu hỏi đi kèm với phần "Tham chiếu SAD" — chỉ ra section nào trong tài liệu hiện tại đang (hoặc nên) trả lời câu hỏi đó. Nếu câu trả lời chưa có hoặc chưa rõ ràng trong tài liệu, đó là tín hiệu cần bổ sung hoặc làm rõ.

Đánh dấu mỗi câu hỏi theo một trong ba trạng thái:
- **✅ Đã trả lời rõ ràng trong SAD** — không cần chỉnh sửa
- **⚠️ Có đề cập nhưng chưa đủ rõ** — cần bổ sung hoặc làm rõ
- **❌ Chưa có trong SAD** — cần thêm vào tài liệu

---

## PHẦN 1: KIẾN TRÚC TỔNG THỂ VÀ LAYER SEPARATION

Nhóm câu hỏi này kiểm tra xem tài liệu đã mô tả đúng cách hệ thống được chia tách và các layers tương tác với nhau hay chưa. Đây là nền tảng quan trọng nhất vì mọi quyết định thiết kế khác đều dựa trên cách phân layer.

**1.1.** Hệ thống chia thành bao nhiêu layers, mỗi layer chứa những components nào, và ranh giới giữa các layers là gì (logical boundary trong cùng process hay physical boundary giữa các processes khác nhau)?

**1.2.** Giữa Edge Layer và Orchestration Layer, ranh giới tương tác là function call (in-process) hay network call (HTTP/gRPC)? Tài liệu có thể hiện rõ rằng API Server và các Modules chạy cùng một process (modular monolith) hay không?

**1.3.** Giữa Orchestration Layer và Processing Layer (Worker), giao tiếp duy nhất có phải chỉ qua Queue hay Worker cũng gọi trực tiếp đến API Server hoặc database? Nếu Worker truy cập database trực tiếp, đó có phải là thiết kế có chủ đích hay chỉ là shortcut cho Phase 1?

**1.4.** Nếu cần thêm một layer mới (ví dụ: một API Gateway phía trước API Server), kiến trúc hiện tại có cho phép mà không cần refactor lớn không? Tài liệu có đề cập đến extensibility path không?


---

## PHẦN 2: LUỒNG XỬ LÝ CHÍNH (SYSTEM FLOWS)

Nhóm câu hỏi này kiểm tra xem tài liệu đã mô tả đủ các luồng xử lý end-to-end hay chưa. Mỗi luồng chính cần thể hiện rõ thứ tự tương tác giữa các components, đâu là sync và đâu là async.

**2.1.** Luồng Upload-to-Result: Khi user upload files rồi bấm "Process All", tài liệu có mô tả rõ từng bước từ frontend → API → modules → queue → worker → result → user poll status không? Có sequence diagram thể hiện chiều thời gian của các tương tác không?


**2.2.** Tại điểm nào trong luồng upload, HTTP response được trả về cho user? User nhận response ngay sau khi files được lưu (sync), hay phải chờ đến khi jobs được tạo xong (vẫn sync nhưng lâu hơn)? Ranh giới giữa phần sync và async có được thể hiện rõ không?


**2.3.** Luồng Retry: Khi job fail với retriable error, tài liệu có mô tả đầy đủ flow từ lúc worker detect error → classify error → check retry count → schedule delay → re-enter queue → worker pick up lại không? State transitions trong quá trình này có nhất quán với Job State Machine không?

**2.4.** Luồng Partial Success: Khi một batch có 10 files, 7 thành công, 3 thất bại — Request status là gì? User có thể download 7 kết quả thành công mà không cần chờ 3 files còn lại không? Tài liệu có mô tả logic aggregate status không?

**2.5.** Có tồn tại trạng thái trung gian giữa "files uploaded" và "processing started" không? Nếu user upload files rồi đóng browser trước khi click "Process All", chuyện gì xảy ra với những files đã upload? Cleanup job có handle orphaned files không?


---

## PHẦN 3: SUBJECT-BASED QUEUE VÀ WORKER ROUTING

Nhóm câu hỏi này kiểm tra tính đúng đắn và đầy đủ của thiết kế Queue — một trong những components cốt lõi quyết định khả năng mở rộng của hệ thống.

**3.1.** Subject pattern `ocr.{method}.tier{tier}` có đủ expressive cho các use cases Phase 2+ không? Ví dụ nếu cần route theo priority (urgent vs normal), hoặc theo file type (image vs PDF), pattern hiện tại có support không hay cần mở rộng?


**3.2.** Trong Phase 1, chỉ có một worker với filter `method=*, tier=*`. Khi chuyển Phase 2 với nhiều workers, cơ chế nào đảm bảo một job không bị hai workers cùng pick up (at-most-once delivery)? Tài liệu có đề cập đến message acknowledgment hay locking mechanism không?

**3.3.** Queue hiện tại là in-memory, data mất khi restart. Tài liệu có mô tả rõ recovery strategy không — ví dụ khi restart, jobs đang ở trạng thái QUEUED trong database nhưng không còn trong queue, cơ chế nào để re-populate queue từ database?

**3.4.** Interface của Queue service (publish, pull, schedule) có được define đủ rõ ràng để Phase 2 swap sang NATS JetStream mà không đổi business logic không? Tài liệu có liệt kê method signatures của IQueueService không?


---

## PHẦN 4: DATA ARCHITECTURE VÀ STORAGE

Nhóm câu hỏi này kiểm tra xem chiến lược lưu trữ đã hợp lý và đầy đủ chưa, bao gồm cả việc phân chia trách nhiệm giữa Database và Filesystem.

**4.1.** Database và Filesystem phục vụ mục đích khác nhau (metadata vs binary content). Tài liệu có giải thích rõ tại sao cần cả hai và chúng liên kết với nhau qua gì (file_path reference) không?

**4.2.** SQLite được access bởi cả Backend container và Worker container qua shared Docker volume. Tài liệu có address strategy cho concurrent access không (WAL mode, retry on SQLITE_BUSY, serialized writes)?

**4.3.** Data lifecycle: Khi files bị cleanup sau 24h, job metadata vẫn giữ lại. Tài liệu có mô tả rõ trạng thái của job record sau khi files bị xóa không? Job record có field nào indicate "files đã bị xóa" không? User gọi API download result cho job đã hết retention sẽ nhận response gì?

**4.4.** File storage path convention `./storage/uploads/{user_id}/{request_id}/{file_id}.{ext}` — nếu Phase 2 chuyển sang cloud storage (R2/S3), path convention này có map được sang object key structure không? Hay cần transform?

---

## PHẦN 5: ERROR HANDLING VÀ RESILIENCE

Nhóm câu hỏi này kiểm tra xem hệ thống đã xử lý các failure scenarios đầy đủ chưa — đặc biệt quan trọng vì OCR processing là async và có nhiều điểm có thể fail.

**5.1.** Tài liệu phân loại errors thành retriable vs non-retriable. Danh sách ví dụ cho mỗi loại đã đủ chưa? Team có thống nhất được tiêu chí phân loại (ví dụ: "nếu retry có thể cho kết quả khác thì là retriable") không?


**5.2.** Khi worker crash giữa chừng xử lý (job đang ở PROCESSING), cơ chế nào detect job bị stuck? Có component nào chạy periodic check để tìm jobs ở PROCESSING quá lâu (stale job detection) không? Component nào chịu trách nhiệm: Backend hay một watchdog riêng?

**5.3.** Retry mechanism có exponential backoff (1s, 2s, 4s) nhưng không có jitter. Tài liệu có acknowledge đây là known limitation không? Trong Phase 1 với single worker thì jitter không quan trọng, nhưng Phase 2 với multiple workers có thể gây thundering herd.


**5.4.** Nếu Tesseract process bị hang (không crash, không timeout, chỉ chạy rất chậm), `JOB_TIMEOUT_SECONDS` (300s) có được enforce ở level nào? Worker tự đặt timeout cho subprocess call, hay có external mechanism? 

---

## PHẦN 6: INTERFACE CONTRACTS VÀ ABSTRACTION

Nhóm câu hỏi này kiểm tra xem các interfaces đã được define đủ rõ để đảm bảo Phase 2 có thể swap implementation mà không đổi business logic — đây là một trong những design principles chính của tài liệu.

**6.1.** Tài liệu nhắc đến IStorageService, IQueueService nhưng có define interface methods cụ thể không? Ví dụ IStorageService cần ít nhất: `save(path, data)`, `read(path)`, `delete(path)`, `exists(path)`. Thiếu interface definition sẽ dẫn đến mỗi dev interpret khác nhau.

**6.2.** API endpoint contracts: Mỗi endpoint chính có request/response schema overview không? Ví dụ `POST /upload` nhận multipart hay base64? `GET /requests/:id` trả về full job list hay summary? Đây là tầng SAD nên không cần chi tiết như DDD, nhưng cần đủ để frontend và backend team align.


**6.3.** Error response format `{ "error": "ERROR_CODE", "message": "..." }` — có danh sách các error codes chính không? Ít nhất cần categories: auth errors, validation errors, resource errors, processing errors.

---

## PHẦN 7: DEPLOYMENT VÀ INFRASTRUCTURE CONSTRAINTS

Nhóm câu hỏi này kiểm tra xem tài liệu đã mô tả đủ các constraints và configuration cần thiết để team có thể setup và chạy hệ thống đúng cách.

**7.1.** Docker Compose stack có 3 containers (frontend, backend, worker) chia sẻ volumes. Tài liệu có mô tả rõ dependency order không? Worker cần đợi Backend ready trước khi start (database và storage phải sẵn sàng). Compose file có healthcheck cho backend không?

**7.2.** Frontend (port 3000) gọi Backend (port 8080) là cross-origin request. Tài liệu có đề cập CORS configuration không? Đây là blocker ngay Phase 1, không phải Phase 2 concern.


**7.3.** Environment variables được list trong Appendix A.2 (MAX_FILE_SIZE_MB, MAX_RETRIES, v.v.). Danh sách này đã đủ chưa? Có thiếu biến nào quan trọng (ví dụ: DATABASE_PATH, STORAGE_PATH, API_PORT, FRONTEND_URL cho CORS)?


**7.4.** Tài liệu nói "chạy được với một lệnh `docker compose up`". Có mô tả rõ prerequisites không (Docker version, disk space tối thiểu, Tesseract language packs cần cài)? Developer mới join team có đủ thông tin để setup từ tài liệu không?


---

## PHẦN 8: MIGRATION PATH (PHASE 1 → PHASE 2)

Nhóm câu hỏi này kiểm tra xem tài liệu đã vạch ra đường đi rõ ràng từ Local MVP sang Cloud hay chưa — vì toàn bộ thiết kế interface-driven chỉ có giá trị nếu migration path khả thi.

**8.1.** Khi swap SQLite → PostgreSQL, tài liệu có identify những thay đổi cần thiết không? Schema migration strategy? Có SQLite-specific features nào đang dùng mà PostgreSQL không hỗ trợ (hoặc ngược lại)?


**8.2.** Khi swap In-memory Queue → NATS JetStream, interface hiện tại có đủ để cover NATS features không? NATS có concepts như streams, consumers, ack/nack mà in-memory queue không có. Tài liệu có address gap này không?


**8.3.** Khi swap Local Filesystem → R2/S3, file operations nào cần thay đổi? `read` từ local path vs S3 `getObject` có cùng interface không? Worker hiện tại đọc file bằng local path — trên cloud, worker cần download file từ S3 trước, đây là thay đổi behavior không chỉ implementation.


**8.4.** Trigger conditions cho migration ("queue depth > 100 jobs", "processing latency không đáp ứng SLA") — đã có cách đo chưa? Phase 1 monitoring có đủ để detect những trigger này không?

---

## PHẦN 9: SECURITY BASELINE

Nhóm câu hỏi này kiểm tra xem security controls cho Phase 1 đã đủ cho môi trường local development chưa, và có identify rõ những gì cần thêm cho Phase 2 production.

**9.1.** Authentication flow: User register → login → nhận token → dùng token cho mỗi request. Token được deliver qua cookie hay Authorization header? Tài liệu nói "cookie (preferred) hoặc Authorization header" — team đã quyết định chưa? Hai cách này ảnh hưởng đến CORS configuration khác nhau.

**9.2.** Resource-level authorization: "User chỉ có thể truy cập requests/jobs/files mà user đó tạo ra". Check này xảy ra ở đâu — middleware level, service level, hay database query level? Nếu check ở database query (WHERE user_id = ?), có đảm bảo consistent across tất cả endpoints không?


**9.3.** File validation: Check MIME type + magic bytes + file size. Nếu attacker upload file có magic bytes của PNG nhưng nội dung thực sự là executable, hệ thống có detect được không? Tesseract sẽ handle file không hợp lệ như thế nào — crash, return error, hay silent failure?


---

## PHẦN 10: CONSISTENCY VÀ COMPLETENESS CHECK

Nhóm câu hỏi cuối cùng kiểm tra tính nhất quán nội bộ của tài liệu — tức là các sections khác nhau không mâu thuẫn với nhau.

**10.1.** Batch limits: Section 1.3 nói "max 20 files", Section 2.3.4 nói "max 20 files, max 50MB total", Appendix A.2 confirm "MAX_FILES_PER_BATCH = 20, MAX_BATCH_SIZE_MB = 50". Các con số này có nhất quán ở mọi nơi trong tài liệu không?


**10.2.** Job statuses: Section 4.4 (State Machine) define 6 statuses (SUBMITTED, QUEUED, PROCESSING, RETRYING, COMPLETED, FAILED). Appendix A.3 có list đầy đủ 6 statuses này không? Section 2.3.5 khi mô tả aggregate status logic có sử dụng đúng các status names này không?


**10.3.** Backend technology: Tài liệu liệt kê "Node.js + Express hoặc Python + FastAPI" nhưng chưa quyết định. Các sections khác (Docker setup, Worker implementation) có phụ thuộc vào quyết định này không? Ví dụ nếu chọn Node.js cho backend, Worker vẫn chạy Python (Tesseract) — lúc đó in-memory queue chia sẻ giữa hai processes viết bằng hai ngôn ngữ khác nhau hoạt động như thế nào?

> Rà soát: Section 3.1 vs Section 6.1 (Docker Compose)

**10.4.** Tài liệu reference "Detailed Design Document (DDD)" và "Infrastructure & Deployment Plan" ở cuối. Những tài liệu này đã tồn tại chưa, hay SAD đang reference documents chưa được viết? Nếu chưa 

---

## TÓM TẮT ĐÁNH GIÁ

Sau khi trả lời tất cả câu hỏi, tổng hợp kết quả vào bảng sau:

| Phần | Số câu ✅ | Số câu ⚠️ | Số câu ❌ | Ưu tiên fix |
|------|-----------|-----------|-----------|-------------|
| 1. Kiến trúc tổng thể | | | | |
| 2. Luồng xử lý chính | | | | |
| 3. Queue & Routing | | | | |
| 4. Data Architecture | | | | |
| 5. Error Handling | | | | |
| 6. Interface Contracts | | | | |
| 7. Deployment | | | | |
| 8. Migration Path | | | | |
| 9. Security | | | | |
| 10. Consistency | | | | |
| **Tổng** | | | | |

Quy tắc ưu tiên:
- Nếu ❌ ở Phần 1, 2, 3 → fix ngay vì ảnh hưởng đến toàn bộ kiến trúc
- Nếu ❌ ở Phần 5, 6 → fix trước khi bắt đầu implement
- Nếu ❌ ở Phần 7, 8, 9 → có thể fix song song với implementation
- Nếu ⚠️ → review lại và bổ sung khi convenient