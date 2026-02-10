# Ma trận yêu cầu kỹ thuật theo Năng lực OCR

---

## Sheet 1 — Chi tiết theo Capability

### NHÓM A — TEXT EXTRACTION

#### A1. Raw Text Extraction | Độ khó: ★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Binarization (Otsu, adaptive threshold) · • Deskew (Hough Transform, projection profile) · • Denoise (Gaussian, median filter) · • DPI normalization (→ 300 DPI) · • PDF text layer check (digital → skip OCR) |
| **Model / Engine** | • Traditional OCR: Tesseract, PaddleOCR, EasyOCR · • Cloud: Google Vision, AWS Textract (DetectText) · • Digital PDF: extract trực tiếp bằng parser, không cần model |
| **Post-processing** | • Spell-check (symspellpy) · • Language detection · • Unicode normalization · • Confidence filtering |

> **Năng lực tổ chức:** CV cơ bản, Systems Engineering

---

#### A2. Layout-Preserved Text | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Tất cả preprocessing của A1 · • Page segmentation (tách vùng text, hình, bảng) · • Column detection (projection profile theo trục X) · • Reading order analysis |
| **Model / Engine** | • Document Layout Analysis: LayoutParser, Surya, DiT, PubLayNet-Detectron2 · • OCR + layout: DocTR, Google Document AI · • Layout model: LayoutLMv3, YOLOv8 fine-tuned cho document zones |
| **Post-processing** | • Reading order reconstruction · • Zone merging (header/footer removal) · • Markdown/HTML generation · • Multi-column text stitching |

> **Năng lực tổ chức:** CV trung bình, ML Engineering (layout model), Systems Engineering

---

#### A3. Font & Style Preservation | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Tất cả preprocessing của A2 · • Font classification (serif/sans-serif detection) · • Bold detection (stroke width analysis) · • Italic detection (slant angle) · • Character height → font size estimation |
| **Model / Engine** | • Enterprise OCR: ABBYY FineReader SDK, Adobe Acrobat SDK · • Cloud: Azure Document Intelligence (rich formatting) · • Custom: CNN font classifier + OCR engine · • Style attribute detection model |
| **Post-processing** | • Style mapping → DOCX/rich HTML · • Font family matching (nearest system font) · • Color extraction & mapping · • Superscript/subscript baseline detection |

> **Năng lực tổ chức:** CV nâng cao, ML Engineering cao, Systems Engineering

---

### NHÓM B — STRUCTURE EXTRACTION

#### B1. Table Extraction | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Bordered: line detection (HoughLinesP), morphological ops (erode/dilate → grid) · • Borderless: text alignment clustering, column gap analysis · • Cell boundary detection (contour → bounding box) · • Table region isolation từ full page |
| **Model / Engine** | • Bordered: OpenCV line intersection (rule-based, không cần DL) · • Borderless: Table Transformer (DETR), CascadeTabNet, TableNet · • Tích hợp: PaddleOCR ppstructure, AWS Textract (Tables) · • Per-cell OCR sau khi detect cells |
| **Post-processing** | • Cell content OCR · • Spanning cell reconstruction (rowspan/colspan) · • Header row detection · • Data type inference per column · • Output: DataFrame → CSV/Excel/JSON |

> **Năng lực tổ chức:** CV trung bình–cao, ML Engineering (borderless), Domain Knowledge (hiểu cấu trúc bảng)

---

#### B2. Form / Key-Value Extraction | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Checkbox detection (template matching, contour + aspect ratio filter) · • Radio button detection · • Text field boundary detection · • Form region segmentation · • Checked/unchecked classification (pixel count trong ROI) |
| **Model / Engine** | • LayoutLMv2/v3 fine-tuned (SOTA cho form understanding) · • BROS (BERT for document structure) · • Cloud: AWS Textract (Forms), Azure Form Recognizer · • End-to-end: Donut · • Spatial proximity matching (rule-based fallback) |
| **Post-processing** | • Label-value pairing (spatial proximity + direction heuristic) · • Key normalization (fuzzy matching tên field) · • Checkbox state → boolean · • JSON schema validation (Pydantic) · • Confidence scoring per field |

> **Năng lực tổ chức:** CV trung bình, ML Engineering cao (fine-tune LayoutLM), Domain Knowledge (hiểu form schema), Data Annotation (key-value pairs)

---

#### B3. List & Hierarchy Detection | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Indent-level measurement (left-edge bbox → cluster thành levels) · • Bullet/number pattern detection · • Vertical spacing analysis (gap between items) · • Nesting depth estimation |
| **Model / Engine** | • Rule-based: Regex pattern matching cho numbering (Điều X, Khoản Y, Điểm Z, 1., a), •, –) · • LayoutLMv3 sequence labeling (list item classification) · • Surya layout detection · • Hybrid: regex + ML confidence |
| **Post-processing** | • Tree construction algorithm · • Numbering pattern normalization · • TOC linking (page number → section) · • Parent-child relationship inference · • Output: nested JSON/XML tree |

> **Năng lực tổ chức:** NLP (pattern matching), Domain Knowledge cao (cấu trúc VB pháp luật), ML Engineering nhẹ

---

### NHÓM C — SEMANTIC EXTRACTION

#### C1. Named Entity Extraction | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • OCR pipeline (A1/A2) là preprocessing · • Word segmentation (quan trọng cho tiếng Việt) · • Sentence segmentation · • Text normalization (Unicode, dấu thanh) |
| **Model / Engine** | • NER: PhoBERT + NER head, spaCy vi_core_news, Underthesea · • Regex cho structured entity (CMND, phone, email, MST) · • dateparser cho ngày tháng đa format · • Hybrid: ML NER + regex post-pass · • Cloud: Google NLP, AWS Comprehend |
| **Post-processing** | • Entity normalization (date format, phone format) · • Entity linking & deduplication · • Confidence scoring · • Cross-reference resolution · • Output: labeled entities + positions |

> **Năng lực tổ chức:** NLP cao (word segmentation VN), ML Engineering trung bình, Domain Knowledge (entity types)

---

#### C2. Domain-Specific Field Extraction | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Document classification (xác định loại tài liệu → chọn schema) · • Image classifier: ResNet/EfficientNet fine-tuned · • Keyword-based routing (rule-based fallback) · • Template matching cho tài liệu có layout cố định |
| **Model / Engine** | • LayoutLMv3 fine-tuned per document type · • Donut end-to-end (image → JSON, không cần OCR riêng) · • Pix2Struct · • VLM: GPT-4o, Claude Vision (zero/few-shot, linh hoạt nhất) · • Cloud: Azure Custom Models, Google Custom Extractor |
| **Post-processing** | • JSON schema validation (Pydantic) · • Business rule validation (cross-field check) · • Confidence thresholding · • Human-in-the-loop routing (low confidence → review) · • Output: structured JSON theo schema định sẵn |

> **Năng lực tổ chức:** ML Engineering cao (fine-tune per doc type), Domain Knowledge rất cao, Data Annotation nhiều, QA & Evaluation

---

#### C3. Relationship Extraction | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Entity extraction pipeline (C1/C2) là preprocessing · • Coreference detection (Bên A = Bên A ở điều khác) · • Section/paragraph segmentation · • Cross-reference detection (xem Điều X, theo Phụ lục Y) |
| **Model / Engine** | • Relation extraction: REBEL, SpERT · • LayoutLMv3 + relation classification head · • LLM prompting (few-shot) — phổ biến nhất hiện tại · • Graph Neural Network cho document graph · • Rule-based: regex cho cross-reference patterns |
| **Post-processing** | • Knowledge graph construction (NetworkX, Neo4j) · • Relation type classification · • Confidence scoring · • Coreference chain resolution · • Output: entity-relation graph / triples |

> **Năng lực tổ chức:** NLP rất cao, ML Engineering cao, Domain Knowledge rất cao, Data Annotation phức tạp

---

### NHÓM D — SPECIAL CONTENT

#### D1. Handwriting Recognition | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Sauvola binarization (tốt hơn Otsu cho chữ viết tay) · • Slant correction (stroke angle detection → warpAffine) · • Baseline detection (horizontal projection) · • Line segmentation (seam carving) · • Word segmentation (connected component + gap) · • Stroke width normalization |
| **Model / Engine** | • TrOCR (Transformer, Microsoft) — SOTA, cần fine-tune · • Kraken · • Cloud: Google Vision (DOCUMENT_TEXT_DETECTION), AWS Textract · • CTC-based models (CRNN + CTC decoder) · • LM-augmented beam search decoding |
| **Post-processing** | • Language model re-ranking (CTC + LM beam search) · • Heavy spell correction · • Confidence-based rejection (loại kết quả confidence thấp) · • Dấu thanh tiếng Việt correction · • Output: text + per-word confidence |

> **Năng lực tổ chức:** CV nâng cao (preprocessing đặc thù), ML Engineering rất cao (train/fine-tune HTR), Data Annotation rất nhiều (transcript chữ viết tay), QA & Evaluation (accuracy thấp hơn printed)

---

#### D2. Stamp / Seal / Signature Detection | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Color space conversion (BGR → HSV/Lab) · • Color-based segmentation (đỏ: H∈[0,10]∪[170,180]) · • Edge detection (Canny) · • Morphological cleanup · • ROI extraction cho vùng stamp/signature |
| **Model / Engine** | • Object detection: YOLOv8/v5 fine-tuned, Faster R-CNN · • Instance segmentation: Mask R-CNN · • Signature verification: Siamese Network · • Stamp text OCR: polar transform → straighten → OCR · • Binary classifier: có stamp/signature hay không |
| **Post-processing** | • Position mapping (page, coordinates) · • Presence/absence classification · • Signature similarity scoring · • Stamp text extraction (circular text) · • Output: detection + classification + position |

> **Năng lực tổ chức:** CV cao (color segmentation, object detection), ML Engineering cao (fine-tune detector), Data Annotation (bounding box), Domain Knowledge (vị trí stamp/sig trong tài liệu VN)

---

#### D3. Barcode / QR Code | Độ khó: ★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • ROI detection (locate barcode/QR region) · • Contrast enhancement · • Perspective correction (cho mã bị nghiêng/cong) · • Resolution upscaling nếu mã quá nhỏ |
| **Model / Engine** | • Dedicated readers: ZBar (pyzbar), OpenCV BarcodeDetector · • Mobile: Google ML Kit, Apple Vision · • 1D: EAN-13, Code 128, Code 39, UPC-A · • 2D: QR Code, Data Matrix, PDF417, Aztec |
| **Post-processing** | • Payload decoding · • URL/data validation · • Format-specific parsing · • Error detection (mã bị hỏng 1 phần) · • Output: type + decoded data + position |

> **Năng lực tổ chức:** CV cơ bản, Systems Engineering (Mature libraries, ít cần ML)

---

#### D4. Mathematical Formula / Equation | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Formula region detection (tách formula khỏi text) · • Inline vs display formula classification · • Symbol isolation · • Binarization (formula thường có ký tự nhỏ, nét mảnh) |
| **Model / Engine** | • pix2tex (LaTeX-OCR): ViT encoder + autoregressive decoder · • Nougat (Meta): PDF → Markdown bao gồm LaTeX · • Mathpix API (accuracy cao nhất, thương mại) · • InftyReader (STEM documents) · • im2latex models |
| **Post-processing** | • LaTeX validation & cleanup · • MathML conversion (latex2mathml) · • Rendering verification (KaTeX/MathJax) · • Multi-line equation stitching · • Output: LaTeX string hoặc MathML |

> **Năng lực tổ chức:** ML Engineering cao (specialized models), Domain Knowledge (toán, hóa, vật lý), QA & Evaluation (formula accuracy)

---

#### D5. Diagram / Chart Understanding | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Chart region detection (YOLO/Faster R-CNN) · • Chart type classification (bar/line/pie/flow) · • Axis detection & scale extraction · • Legend detection · • Color-based series separation |
| **Model / Engine** | • Chart → data: DePlot (Google), MatCha, ChartOCR, UniChart · • VLM: GPT-4o, Claude Vision (describe/summarize) · • Flowchart: node detection + edge detection → graph · • Bar/Line: element detection → value mapping · • Pie: segment angle measurement |
| **Post-processing** | • Data table reconstruction (CSV/JSON) · • Axis label → data mapping · • Chart summarization (text description) · • Flowchart → Mermaid/DOT conversion · • Output: data table hoặc structured description |

> **Năng lực tổ chức:** CV cao (chart element detection), ML Engineering cao, Domain Knowledge (hiểu chart types), NLP (cho chart summarization via VLM)

---

## Sheet 2 — Ma trận Capability × Kỹ thuật yêu cầu

> ● = Bắt buộc (core) · ◐ = Quan trọng · ○ = Tùy trường hợp · (trống) = Không cần

### Preprocessing

|     | Capability       | Binarization | Deskew | Denoise | DPI Norm | Color Seg. | Page/Zone Seg. | Line/Word Seg. | Contour/Edge | Template/ROI | Perspective Corr. |
|-----|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A1  | Raw Text         | ●  | ●  | ●  | ●  |    |    |    |    |    |    |
| A2  | Layout Text      | ●  | ●  | ●  | ●  |    | ●  |    |    |    |    |
| A3  | Font/Style       | ●  | ●  | ●  | ●  |    | ●  |    |    |    |    |
| B1  | Table            | ●  | ◐  | ◐  | ◐  |    | ●  |    | ●  |    |    |
| B2  | Form/KV          | ●  | ◐  | ◐  | ◐  |    | ●  |    | ●  | ●  |    |
| B3  | List/Hierarchy   | ◐  | ◐  | ○  | ◐  |    | ◐  |    |    |    |    |
| C1  | NER              | ◐  | ○  | ○  | ○  |    | ○  | ●  |    |    |    |
| C2  | Domain Fields    | ◐  | ○  | ○  | ○  |    | ◐  | ◐  |    | ●  |    |
| C3  | Relations        | ○  | ○  | ○  | ○  |    | ◐  | ◐  |    |    |    |
| D1  | Handwriting      | ●  | ●  | ●  | ●  |    | ◐  | ●  |    |    |    |
| D2  | Stamp/Seal/Sig   | ◐  | ○  | ○  | ○  | ●  | ◐  |    | ●  | ◐  |    |
| D3  | Barcode/QR       | ○  |    | ○  | ○  |    | ○  |    |    | ◐  | ●  |
| D4  | Math Formula     | ●  | ○  | ◐  | ◐  |    | ◐  |    |    | ○  |    |
| D5  | Diagram/Chart    | ◐  | ○  | ○  | ◐  | ●  | ●  |    | ◐  |    |    |

### Model / Engine

|     | Capability       | Traditional OCR | Doc Layout (DLA) | Table Detection | Object Detection | Sequence Labeling | LayoutLM Family | End-to-end (Donut) | VLM/LLM | Specialized Reader | Siamese/Verify |
|-----|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A1  | Raw Text         | ●  |    |    |    |    |    |    |    |    |    |
| A2  | Layout Text      | ●  | ●  |    |    |    | ◐  |    | ○  |    |    |
| A3  | Font/Style       | ●  | ●  |    |    |    | ◐  |    | ○  | ○  |    |
| B1  | Table            | ●  | ◐  | ●  | ○  |    | ◐  | ○  | ◐  |    |    |
| B2  | Form/KV          | ●  | ○  |    | ○  | ○  | ●  | ●  | ●  |    |    |
| B3  | List/Hierarchy   | ●  | ◐  |    |    | ◐  | ●  |    | ◐  |    |    |
| C1  | NER              | ●  |    |    |    | ●  | ◐  |    | ◐  |    |    |
| C2  | Domain Fields    | ◐  | ○  | ○  |    | ◐  | ●  | ●  | ●  |    |    |
| C3  | Relations        | ◐  |    |    |    | ●  | ●  |    | ●  |    |    |
| D1  | Handwriting      | ○  |    |    |    |    |    |    | ○  | ●  |    |
| D2  | Stamp/Seal/Sig   | ○  |    |    | ●  |    |    |    | ◐  |    | ●  |
| D3  | Barcode/QR       |    |    |    |    |    |    |    |    | ●  |    |
| D4  | Math Formula     |    | ○  |    |    |    |    | ○  | ◐  | ●  |    |
| D5  | Diagram/Chart    | ○  | ○  |    | ●  |    |    | ○  | ●  | ○  |    |

### Post-processing

|     | Capability       | Spell Check | Reading Order | Schema Validation | Entity Norm. | Tree/Graph | Confidence Score | HITL Routing | Format Convert | Biz Rule Valid. | Cross-ref |
|-----|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A1  | Raw Text         | ●  |    |    |    |    | ○  |    |    |    |    |
| A2  | Layout Text      | ◐  | ●  |    |    |    | ○  |    | ●  |    |    |
| A3  | Font/Style       | ○  | ●  |    |    |    | ◐  |    | ●  |    |    |
| B1  | Table            |    |    | ○  |    |    | ●  | ○  | ●  |    |    |
| B2  | Form/KV          |    |    | ●  | ◐  |    | ●  | ●  |    | ●  |    |
| B3  | List/Hierarchy   |    | ◐  | ○  |    | ●  | ◐  |    | ○  |    | ○  |
| C1  | NER              | ◐  |    | ○  | ●  |    | ●  | ○  |    | ○  | ○  |
| C2  | Domain Fields    |    |    | ●  | ●  |    | ●  | ●  |    | ●  | ○  |
| C3  | Relations        |    |    | ○  | ●  | ●  | ●  | ◐  |    | ◐  | ●  |
| D1  | Handwriting      | ●  |    |    |    |    | ●  | ●  | ○  |    |    |
| D2  | Stamp/Seal/Sig   |    |    |    |    |    | ●  | ◐  |    | ○  |    |
| D3  | Barcode/QR       |    |    | ○  |    |    | ○  |    |    | ○  |    |
| D4  | Math Formula     |    |    | ○  |    |    | ◐  | ○  | ◐  |    |    |
| D5  | Diagram/Chart    |    |    | ○  |    | ◐  | ◐  | ○  | ●  |    |    |

---

## Sheet 3 — Năng lực tổ chức × Capability

> ● = Rất cao (critical) · ◐ = Trung bình · ○ = Thấp / cơ bản · (trống) = Không cần

|     | Capability       | CV & Image Processing | NLP & Language | ML/DL Engineering | Domain Knowledge | Data Annotation | Systems Engineering | QA & Evaluation |
|-----|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A1  | Raw Text         | ◐  |    | ○  |    |    | ◐  | ○  |
| A2  | Layout Text      | ●  | ○  | ◐  | ○  | ○  | ◐  | ○  |
| A3  | Font/Style       | ●  | ○  | ●  | ○  | ○  | ◐  | ◐  |
| B1  | Table            | ●  | ○  | ●  | ◐  | ◐  | ◐  | ◐  |
| B2  | Form/KV          | ◐  | ○  | ●  | ●  | ●  | ◐  | ●  |
| B3  | List/Hierarchy   | ○  | ●  | ◐  | ●  | ○  | ○  | ◐  |
| C1  | NER              | ○  | ●  | ◐  | ◐  | ◐  | ◐  | ◐  |
| C2  | Domain Fields    | ○  | ◐  | ●  | ●  | ●  | ●  | ●  |
| C3  | Relations        | ○  | ●  | ●  | ●  | ●  | ◐  | ●  |
| D1  | Handwriting      | ●  | ◐  | ●  | ○  | ●  | ◐  | ●  |
| D2  | Stamp/Seal/Sig   | ●  |    | ●  | ◐  | ●  | ◐  | ◐  |
| D3  | Barcode/QR       | ○  |    |    | ○  |    | ◐  | ○  |
| D4  | Math Formula     | ◐  | ○  | ●  | ●  | ◐  | ○  | ●  |
| D5  | Diagram/Chart    | ●  | ◐  | ●  | ◐  | ◐  | ◐  | ●  |