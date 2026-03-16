# Plan: Nâng cấp Paddle Worker — Layout-Preserved Output (A2)

> **Mục tiêu:** Đáp ứng capability A2 — Layout-Preserved Text: giữ đúng thứ tự đọc, phân biệt cột, header/footer, reading order. Output: Markdown, HTML chất lượng cao.
>
> **Cập nhật:** 2026-03-16
>
> **Status:** DONE — Sprint 1/2/3 hoàn thành. 69/69 tests pass.

---

## 1. Phân Tích Hiện Trạng & Vấn Đề

### 1.1 Tổng quan kiến trúc worker hiện tại

```
03_worker/app/engines/
├── paddle_text/     → Raw text extraction (A1) — KHÔNG thuộc scope
├── paddle_vl/       → Structured extraction (A2 target) — SCOPE CHÍNH
│   ├── handler.py           → StructuredExtractHandler (PPStructure v2/v3)
│   ├── preprocessing.py     → Load image/PDF, upscale
│   ├── postprocessing.py    → Region extraction + format MD/HTML/JSON
│   └── debug.py             → Debug pipeline
└── tesseract/       → CPU OCR — KHÔNG thuộc scope
```

### 1.2 Các vấn đề cụ thể

#### P1 — CRITICAL: V3 path mất toàn bộ structure

**File:** `handler.py:155-177` — `_extract_v3_structured()`

```python
# Hiện tại: flatten mọi thứ thành "text", mất layout info
for r in results:
    if hasattr(r, 'get'):
        rec_texts = r.get("rec_texts", [])
        if rec_texts:
            text = "\n".join(rec_texts)
            regions.append({"type": "text", "text": text, "bbox": []})
```

**Hậu quả:**
- Mọi region (title, table, list, figure) → đều thành `type: "text"`
- `bbox` luôn `[]` → mất reading order, không sort được
- Table HTML hoàn toàn bị bỏ qua
- Khi format sang MD/HTML → chỉ ra thuần text

#### P2 — HIGH: Text joining phá vỡ cấu trúc đoạn văn

**File:** `postprocessing.py:143`

```python
content = " ".join(text_parts)  # Nối mọi dòng trong region bằng space
```

**Hậu quả:** Một đoạn văn nhiều dòng bị nối thành 1 dòng dài, mất line break tự nhiên.

#### P3 — HIGH: Không phát hiện heading level

**File:** `postprocessing.py:470-471`

```python
if rtype == "title":
    parts.append(f"\n# {region['content']}\n")  # Luôn h1
```

**Hậu quả:** Mọi title đều thành `#` (h1). Tài liệu nhiều section không có h2/h3.

#### P4 — HIGH: Không detect multi-column layout

**File:** `postprocessing.py:161`

```python
regions.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))  # y rồi x
```

**Hậu quả:** Tài liệu 2 cột (báo cáo, paper) bị đọc ngang thay vì theo cột.

#### P5 — MEDIUM: List handling quá đơn giản

```python
elif rtype == "list":
    parts.append(f"- {region['content']}")  # 1 region = 1 bullet
```

**Hậu quả:** Không phân biệt bullet/numbered list, không nested, không multi-item.

#### P6 — MEDIUM: Không lọc header/footer lặp lại

Running header/footer (số trang, tên tài liệu lặp mỗi trang) lẫn vào content, gây nhiễu output.

#### P7 — LOW: HTML table-to-markdown không xử lý colspan/rowspan

```python
cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
```

Regex đơn giản bỏ qua `colspan`, `rowspan` → table phức tạp bị lệch cột.

---

## 2. Giải Pháp Đề Xuất

### Phân chia thành 3 Sprint

| Sprint | Tên | Mục tiêu | Vấn đề giải quyết |
|:---:|---|---|---|
| S1 | Fix V3 + Core Structure | Có output MD/HTML đúng cấu trúc | P1, P2 |
| S2 | Layout Intelligence | Reading order thông minh, heading levels | P3, P4, P5 |
| S3 | Polish & Edge Cases | Header/footer, table nâng cao, quality | P6, P7 |

---

## 3. Sprint 1 — Fix V3 + Core Structure

> **Mục tiêu:** PPStructureV3 output tương đương chất lượng v2. MD/HTML có đúng title/text/table/list.

### Task 1.1: Reverse-engineer PPStructureV3 output format

**Vấn đề:** Hiện tại code đoán format v3 nhưng sai. Cần chạy thật để biết chính xác output schema.

**Hành động:**
1. Tạo script debug chạy `PPStructureV3.predict()` với 3-5 file mẫu đa dạng (text-only, table, mixed layout)
2. Dump raw output sang JSON để phân tích
3. Document chính xác schema v3: field names, nesting, region types

**File tạo:** `03_worker/scripts/debug_v3_output.py`

### Task 1.2: Rewrite `_extract_v3_structured()`

**File sửa:** `handler.py`

**Yêu cầu:**
- Parse đúng PPStructureV3 output theo schema từ Task 1.1
- Trích xuất chính xác: `type` (title/text/table/list/figure), `bbox`, `content`/`html`
- Với table: lấy HTML table → gọi `html_table_to_markdown()`
- Output phải match interface `{"page_number": N, "regions": [...]}`  giống v2 path

**Kết quả mong đợi:** V3 path ra output giống v2, format_structured_output() xử lý đúng.

### Task 1.3: Fix text joining trong region

**File sửa:** `postprocessing.py:132-144`

**Thay đổi:**
```python
# Trước:
content = " ".join(text_parts)

# Sau — giữ line break tự nhiên:
content = "\n".join(text_parts)
```

**Lưu ý:** Kiểm tra ảnh hưởng đến JSON output (field `content` giờ có `\n`).

### Task 1.4: Bổ sung `content` field cho v3 regions

Hiện tại v3 dùng key `"text"` thay vì `"content"` → `_format_markdown()` và `_format_html()` không đọc được.

**File sửa:** `handler.py:_extract_v3_structured()` — dùng `"content"` thống nhất.

### Tiêu chí Done Sprint 1:
- [x] Chạy 5 file mẫu qua v3 path → output MD có đúng title/text/table
- [x] V3 output JSON có đầy đủ region types + bbox
- [x] Text regions giữ line break tự nhiên
- [x] Test so sánh: v2 vs v3 output cho cùng file → chênh lệch < 10%

---

## 4. Sprint 2 — Layout Intelligence

> **Mục tiêu:** Reading order thông minh, heading levels, list nâng cao.

### Task 2.1: Heading level detection dựa trên font size/bbox

**File tạo:** `postprocessing.py` — thêm hàm `_detect_heading_level()`

**Thuật toán:**
1. Thu thập bbox height của tất cả title regions trong page
2. Cluster thành 2-3 nhóm dựa trên height (lớn → h1, vừa → h2, nhỏ → h3)
3. Nếu chỉ có 1 title → h1
4. Fallback: title đầu tiên = h1, còn lại = h2

**Cách tính:**
```python
def _detect_heading_level(title_region, all_title_heights):
    region_height = bbox[3] - bbox[1]  # y2 - y1
    if region_height >= percentile_75(all_title_heights):
        return 1  # h1
    elif region_height >= percentile_25(all_title_heights):
        return 2  # h2
    else:
        return 3  # h3
```

**Ảnh hưởng format:**
- MD: `#` → `##` → `###`
- HTML: `<h1>` → `<h2>` → `<h3>`

### Task 2.2: Multi-column layout detection

**File tạo:** `postprocessing.py` — thêm hàm `_detect_columns()` và `_reorder_by_columns()`

**Thuật toán:**
1. Lấy tất cả bbox x-coordinates (x1, x2) của regions trong page
2. Tìm "khoảng trống dọc" (vertical gap) — vùng x mà không có region nào cover
3. Nếu tìm thấy gap rõ ràng (width > 5% page width) → chia thành 2+ cột
4. Sort: cột trái trước (top-to-bottom), rồi cột phải (top-to-bottom)
5. Full-width regions (spanning > 80% page) → giữ nguyên vị trí

**Pseudo-code:**
```python
def _reorder_by_columns(regions, page_width):
    # 1. Phân loại: full-width vs column
    full_width = [r for r in regions if (r.bbox[2] - r.bbox[0]) > 0.8 * page_width]
    narrow = [r for r in regions if r not in full_width]

    # 2. Detect column boundaries từ narrow regions
    x_centers = [(r.bbox[0] + r.bbox[2]) / 2 for r in narrow]
    columns = cluster_into_columns(x_centers)  # k-means hoặc gap detection

    # 3. Sort: full-width by y, then each column by y
    ordered = []
    for r in sorted(full_width + narrow, key=sort_key):
        ordered.append(r)
    return ordered
```

**Lưu ý:** Page width lấy từ image shape (đã có trong preprocessing).

### Task 2.3: Nâng cấp list detection

**File sửa:** `postprocessing.py` — cải thiện `_format_markdown()` và `_format_html()`

**Thay đổi:**
1. Parse list content để tách multi-item: split theo `\n` hoặc detect pattern `1.`, `2.`, `•`, `-`
2. Detect numbered vs bullet:
   - Bắt đầu bằng `\d+[.)]` → numbered (`1.`, `2.`)
   - Còn lại → bullet (`-`)
3. MD output:
```markdown
1. First item
2. Second item
- Bullet item
- Another bullet
```
4. HTML output:
```html
<ol><li>First</li><li>Second</li></ol>
<ul><li>Bullet</li><li>Another</li></ul>
```

### Task 2.4: Truyền page dimensions qua pipeline

**File sửa:** `handler.py`, `postprocessing.py`

Để column detection hoạt động, cần truyền `page_width` từ preprocessing → postprocessing.

**Thay đổi:**
- `extract_regions()` thêm param `page_width: int`
- `handler.py` truyền `image.shape[1]` (width) vào
- `_reorder_by_columns()` dùng page_width để xác định full-width threshold

### Tiêu chí Done Sprint 2:
- [x] Tài liệu có h1/h2/h3 → MD output có `#`/`##`/`###` phù hợp
- [x] Tài liệu 2 cột (paper, báo cáo) → reading order đúng (cột trái trước, cột phải sau)
- [x] List region có nhiều item → MD output mỗi item 1 dòng `- ` hoặc `1. `
- [x] Full-width title + 2-column body → output giữ đúng thứ tự

---

## 5. Sprint 3 — Polish & Edge Cases

> **Mục tiêu:** Header/footer filtering, table nâng cao, quality assurance.

### Task 3.1: Header/footer detection & filtering

**File tạo:** `postprocessing.py` — thêm hàm `_filter_headers_footers()`

**Thuật toán:**
1. Chỉ áp dụng khi document có ≥ 3 trang
2. Với mỗi page, lấy regions ở top 8% và bottom 8% (theo bbox y)
3. So sánh text content giữa các trang:
   - Nếu text xuất hiện ở cùng vị trí (y-coordinate tương tự) trên ≥ 60% số trang → đánh dấu là header/footer
   - Dùng fuzzy match (similarity > 0.8) vì OCR có thể nhận diện hơi khác giữa các trang
4. Loại bỏ regions được đánh dấu, hoặc đưa vào metadata

**Xử lý số trang:**
- Detect pattern: `\d+`, `Page \d+`, `Trang \d+`
- Nếu ở bottom 5% + match pattern → loại

### Task 3.2: Cải thiện HTML table-to-markdown với colspan/rowspan

**File sửa:** `postprocessing.py` — nâng cấp `html_table_to_markdown()`

**Thay đổi:**
1. Parse `colspan="N"` → repeat cell N lần trong markdown
2. Parse `rowspan="N"` → merge info (markdown không hỗ trợ rowspan natively, dùng repeated text)
3. Dùng thư viện `html.parser` (stdlib) thay regex cho robustness:

```python
from html.parser import HTMLParser

class TableParser(HTMLParser):
    # Parse table structure properly
    # Handle colspan, rowspan, nested tags
```

4. Fallback: nếu parse lỗi → giữ nguyên logic regex hiện tại

### Task 3.3: Paragraph merging cho adjacent text regions

**File sửa:** `postprocessing.py`

**Thuật toán:**
1. Sau khi sort regions, kiểm tra text regions liên tiếp
2. Nếu 2 text regions có:
   - Cùng cột (x overlap > 50%)
   - Khoảng cách y nhỏ (< 1.5x line height trung bình)
   - Cả hai không phải title/list
3. → Merge thành 1 paragraph

**Lợi ích:** Giảm fragment, output MD/HTML gọn hơn.

### Task 3.4: Figure caption extraction

**File sửa:** `postprocessing.py`

**Thuật toán:**
1. Khi gặp `type: "figure"`, tìm text region liền kề phía dưới
2. Nếu text bắt đầu bằng "Figure", "Hình", "Fig." → gán làm caption
3. Output:
   - MD: `*[Figure: caption text]*`
   - HTML: `<figure><figcaption>caption text</figcaption></figure>`

### Task 3.5: Test suite cho layout-preserved output

**File tạo:** `00_test/ocr_worker/test_layout_output.py`

**Test cases:**
1. Single-column text document → MD có paragraphs, headings đúng level
2. Two-column document → reading order cột trái trước
3. Document với table → MD có valid markdown table
4. Document với numbered list → `1. 2. 3.` format
5. Multi-page document → header/footer filtered
6. Mixed layout (title + 2-col + table + figure) → all elements preserved
7. V3 vs V2 output comparison test

### Tiêu chí Done Sprint 3:
- [x] Multi-page PDF → header/footer không lẫn vào content
- [x] Table có colspan → markdown table đúng số cột
- [x] Adjacent text fragments → merged thành paragraph
- [x] Figure có caption → hiển thị trong MD/HTML
- [x] Test suite pass 100% (69/69)

---

## 6. Tổng kết thay đổi theo file

| File | Sprint | Thay đổi |
|---|:---:|---|
| `handler.py` | S1 | Rewrite `_extract_v3_structured()`, `_extract_v3_ocr_fallback()`, truyền page_width |
| `postprocessing.py` | S1-S3 | Fix text join, heading levels, column detection, header/footer filter, paragraph merge, table parser, list upgrade, figure caption |
| `preprocessing.py` | S2 | Return page dimensions cùng image |
| `debug.py` | S1 | Dump v3 raw output cho debug |
| `scripts/debug_v3_output.py` | S1 | Script test v3 schema |
| `00_test/.../test_layout_output.py` | S3 | Test suite |

---

## 7. Dependencies & Risks

| Risk | Impact | Mitigation |
|---|---|---|
| PPStructureV3 API thay đổi giữa patch versions | Cao | Pin version trong requirements, viết adapter layer |
| Column detection sai trên layout phức tạp (3+ cột, nested columns) | Trung bình | Giới hạn hỗ trợ 1-2 cột, fallback về simple sort |
| Heading level detection sai khi font size đồng đều | Thấp | Fallback: title đầu = h1, còn lại h2 |
| Performance giảm do thêm post-processing | Thấp | Tất cả logic O(n) với n = số regions, không đáng kể |

### Không cần thêm dependencies:
- `html.parser` → stdlib Python
- Column detection → pure Python, dùng statistics module
- Tất cả logic nằm trong postprocessing, không ảnh hưởng engine

---

## 8. Ưu tiên nếu chỉ có thời gian cho 1 Sprint

**Chọn Sprint 1** — vì:
1. V3 path hiện tại **hoàn toàn broken** cho structured output
2. Fix xong S1 → MD/HTML đã có title/table/list thay vì plain text
3. S2/S3 là enhancement, S1 là must-fix

---

*— Hết tài liệu —*
