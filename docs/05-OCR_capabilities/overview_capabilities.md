Danh sách các capability dạng tổng quát:

---

### Nhóm A — Text Extraction

**A1. Raw Text Extraction**
Chỉ lấy text, không quan tâm layout. Output: plain string.
Best for: indexing, search, feeding LLM.

**A2. Layout-Preserved Text**
Giữ đúng thứ tự đọc, phân biệt cột, header/footer, reading order. Output: Markdown, HTML.
Best for: tái tạo tài liệu, convert PDF → editable doc.

**A3. Font & Style Preservation**
Giữ bold, italic, font size, color, superscript/subscript. Output: DOCX, rich HTML.
Best for: người dùng cần bản sao gần như y hệt bản gốc.

---

### Nhóm B — Structure Extraction

**B1. Table Extraction**
Nhận diện bảng, merge cell, spanning, nested table. Output: CSV, Excel, JSON array.
Best for: báo cáo tài chính, bảng giá, data entry.

**B2. Form / Key-Value Extraction**
Nhận diện cặp label-value trong form (ô tick, checkbox, text field). Output: key-value JSON.
Best for: form đăng ký, phiếu khảo sát, đơn xin.

**B3. List & Hierarchy Detection**
Nhận diện bullet list, numbered list, nested list, mục lục. Output: structured tree.
Best for: tài liệu pháp lý (điều khoản lồng nhau), sách có mục lục.

---

### Nhóm C — Semantic Extraction

**C1. Named Entity Extraction**
Trích xuất entity có ngữ nghĩa: tên người, ngày tháng, số tiền, địa chỉ, mã số… Output: labeled entities.
Best for: hợp đồng, CMND/CCCD, invoice.

**C2. Domain-Specific Field Extraction**
Trích xuất theo template cụ thể của loại tài liệu. Ví dụ invoice → `{invoice_no, date, vendor, line_items, total}`. Output: structured JSON theo schema định sẵn.
Best for: automation pipeline, RPA.

**C3. Relationship Extraction**
Hiểu mối quan hệ giữa các entity — ai ký với ai, điều khoản nào áp dụng cho mục nào, dòng item nào thuộc subtotal nào.
Best for: hợp đồng phức tạp, báo cáo tài chính multi-section.

---

### Nhóm D — Special Content

**D1. Handwriting Recognition**
Nhận diện chữ viết tay — cả block letter lẫn cursive. Cần tách riêng vì accuracy gap rất lớn so với printed text.
Best for: đơn viết tay, phiếu khám bệnh, ghi chú.

**D2. Stamp / Seal / Signature Detection**
Nhận diện và trích xuất con dấu, chữ ký, watermark. Không chỉ OCR mà còn detect vị trí, phân loại có/không.
Best for: xác thực tài liệu, kiểm tra hợp đồng đã ký chưa.

**D3. Barcode / QR Code**
Đọc mã vạch, QR code nhúng trong tài liệu.
Best for: chứng từ logistics, vé, tem nhãn.

**D4. Mathematical Formula / Equation**
Nhận diện công thức toán, hóa học. Output: LaTeX, MathML.
Best for: tài liệu học thuật, sách giáo khoa, paper.

**D5. Diagram / Chart Understanding**
Hiểu biểu đồ, sơ đồ, flowchart — trích xuất data points hoặc mô tả.
Best for: báo cáo có chart, tài liệu kỹ thuật có sơ đồ.

---

### Dimension bổ sung (cross-cutting)

Ngoài các capability trên, có vài dimension nên tag thêm cho mỗi giải pháp:

- **Ngôn ngữ**: tiếng Việt, CJK, mixed-language, RTL…
- **Chất lượng đầu vào**: scan sạch, ảnh chụp nghiêng/mờ, fax chất lượng thấp
---

Với cách tách này, khi người dùng nói "tôi muốn extract bảng từ báo cáo tài chính PDF scan" → biết họ cần **A1 hoặc A2 + B1**, và có thể recommend giải pháp tối ưu nhất cho đúng combo đó thay vì ép họ vào một "level" chung.
