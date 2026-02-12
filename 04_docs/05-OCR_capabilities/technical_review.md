# Ma trận yêu cầu kỹ thuật theo Năng lực OCR

---

## Sheet 1 — Chi tiết theo Capability

### NHÓM A — TEXT EXTRACTION

#### A1. Raw Text Extraction | Độ khó: ★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Binarization (Otsu, adaptive threshold) <br> • Deskew (Hough Transform, projection profile) <br> • Denoise (Gaussian, median filter) <br> • DPI normalization (→ 300 DPI) <br> • PDF text layer check (digital → skip OCR) |
| **Model / Engine** | • Traditional OCR: Tesseract, PaddleOCR, EasyOCR <br> • Cloud: Google Vision, AWS Textract (DetectText) <br> • Digital PDF: extract trực tiếp bằng parser, không cần model |
| **Post-processing** | • Spell-check (symspellpy) <br> • Language detection <br> • Unicode normalization <br> • Confidence filtering |

> **Năng lực tổ chức:** CV cơ bản, Systems Engineering

---

#### A2. Layout-Preserved Text | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Tất cả preprocessing của A1 <br> • Page segmentation (tách vùng text, hình, bảng) <br> • Column detection (projection profile theo trục X) <br> • Reading order analysis |
| **Model / Engine** | • Document Layout Analysis: LayoutParser, Surya, DiT, PubLayNet-Detectron2 <br> • OCR + layout: DocTR, Google Document AI <br> • Layout model: LayoutLMv3, YOLOv8 fine-tuned cho document zones |
| **Post-processing** | • Reading order reconstruction <br> • Zone merging (header/footer removal) <br> • Markdown/HTML generation <br> • Multi-column text stitching |

> **Năng lực tổ chức:** CV trung bình, ML Engineering (layout model), Systems Engineering

---

#### A3. Font & Style Preservation | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Tất cả preprocessing của A2 <br> • Font classification (serif/sans-serif detection) <br> • Bold detection (stroke width analysis) <br> • Italic detection (slant angle) <br> • Character height → font size estimation |
| **Model / Engine** | • Enterprise OCR: ABBYY FineReader SDK, Adobe Acrobat SDK <br> • Cloud: Azure Document Intelligence (rich formatting) <br> • Custom: CNN font classifier + OCR engine <br> • Style attribute detection model |
| **Post-processing** | • Style mapping → DOCX/rich HTML <br> • Font family matching (nearest system font) <br> • Color extraction & mapping <br> • Superscript/subscript baseline detection |

> **Năng lực tổ chức:** CV nâng cao, ML Engineering cao, Systems Engineering

---

### NHÓM B — STRUCTURE EXTRACTION

#### B1. Table Extraction | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Bordered: line detection (HoughLinesP), morphological ops (erode/dilate → grid) <br> • Borderless: text alignment clustering, column gap analysis <br> • Cell boundary detection (contour → bounding box) <br> • Table region isolation từ full page |
| **Model / Engine** | • Bordered: OpenCV line intersection (rule-based, không cần DL) <br> • Borderless: Table Transformer (DETR), CascadeTabNet, TableNet <br> • Tích hợp: PaddleOCR ppstructure, AWS Textract (Tables) <br> • Per-cell OCR sau khi detect cells |
| **Post-processing** | • Cell content OCR <br> • Spanning cell reconstruction (rowspan/colspan) <br> • Header row detection <br> • Data type inference per column <br> • Output: DataFrame → CSV/Excel/JSON |

> **Năng lực tổ chức:** CV trung bình–cao, ML Engineering (borderless), Domain Knowledge (hiểu cấu trúc bảng)

---

#### B2. Form / Key-Value Extraction | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Checkbox detection (template matching, contour + aspect ratio filter) <br> • Radio button detection <br> • Text field boundary detection <br> • Form region segmentation <br> • Checked/unchecked classification (pixel count trong ROI) |
| **Model / Engine** | • LayoutLMv2/v3 fine-tuned (SOTA cho form understanding) <br> • BROS (BERT for document structure) <br> • Cloud: AWS Textract (Forms), Azure Form Recognizer <br> • End-to-end: Donut <br> • Spatial proximity matching (rule-based fallback) |
| **Post-processing** | • Label-value pairing (spatial proximity + direction heuristic) <br> • Key normalization (fuzzy matching tên field) <br> • Checkbox state → boolean <br> • JSON schema validation (Pydantic) <br> • Confidence scoring per field |

> **Năng lực tổ chức:** CV trung bình, ML Engineering cao (fine-tune LayoutLM), Domain Knowledge (hiểu form schema), Data Annotation (key-value pairs)

---

#### B3. List & Hierarchy Detection | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Indent-level measurement (left-edge bbox → cluster thành levels) <br> • Bullet/number pattern detection <br> • Vertical spacing analysis (gap between items) <br> • Nesting depth estimation |
| **Model / Engine** | • Rule-based: Regex pattern matching cho numbering (Điều X, Khoản Y, Điểm Z, 1., a), •, –) <br> • LayoutLMv3 sequence labeling (list item classification) <br> • Surya layout detection <br> • Hybrid: regex + ML confidence |
| **Post-processing** | • Tree construction algorithm <br> • Numbering pattern normalization <br> • TOC linking (page number → section) <br> • Parent-child relationship inference <br> • Output: nested JSON/XML tree |

> **Năng lực tổ chức:** NLP (pattern matching), Domain Knowledge cao (cấu trúc VB pháp luật), ML Engineering nhẹ

---

### NHÓM C — SEMANTIC EXTRACTION

#### C1. Named Entity Extraction | Độ khó: ★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • OCR pipeline (A1/A2) là preprocessing <br> • Word segmentation (quan trọng cho tiếng Việt) <br> • Sentence segmentation <br> • Text normalization (Unicode, dấu thanh) |
| **Model / Engine** | • NER: PhoBERT + NER head, spaCy vi_core_news, Underthesea <br> • Regex cho structured entity (CMND, phone, email, MST) <br> • dateparser cho ngày tháng đa format <br> • Hybrid: ML NER + regex post-pass <br> • Cloud: Google NLP, AWS Comprehend |
| **Post-processing** | • Entity normalization (date format, phone format) <br> • Entity linking & deduplication <br> • Confidence scoring <br> • Cross-reference resolution <br> • Output: labeled entities + positions |

> **Năng lực tổ chức:** NLP cao (word segmentation VN), ML Engineering trung bình, Domain Knowledge (entity types)

---

#### C2. Domain-Specific Field Extraction | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Document classification (xác định loại tài liệu → chọn schema) <br> • Image classifier: ResNet/EfficientNet fine-tuned <br> • Keyword-based routing (rule-based fallback) <br> • Template matching cho tài liệu có layout cố định |
| **Model / Engine** | • LayoutLMv3 fine-tuned per document type <br> • Donut end-to-end (image → JSON, không cần OCR riêng) <br> • Pix2Struct <br> • VLM: GPT-4o, Claude Vision (zero/few-shot, linh hoạt nhất) <br> • Cloud: Azure Custom Models, Google Custom Extractor |
| **Post-processing** | • JSON schema validation (Pydantic) <br> • Business rule validation (cross-field check) <br> • Confidence thresholding <br> • Human-in-the-loop routing (low confidence → review) <br> • Output: structured JSON theo schema định sẵn |

> **Năng lực tổ chức:** ML Engineering cao (fine-tune per doc type), Domain Knowledge rất cao, Data Annotation nhiều, QA & Evaluation

---

#### C3. Relationship Extraction | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Entity extraction pipeline (C1/C2) là preprocessing <br> • Coreference detection (Bên A = Bên A ở điều khác) <br> • Section/paragraph segmentation <br> • Cross-reference detection (xem Điều X, theo Phụ lục Y) |
| **Model / Engine** | • Relation extraction: REBEL, SpERT <br> • LayoutLMv3 + relation classification head <br> • LLM prompting (few-shot) — phổ biến nhất hiện tại <br> • Graph Neural Network cho document graph <br> • Rule-based: regex cho cross-reference patterns |
| **Post-processing** | • Knowledge graph construction (NetworkX, Neo4j) <br> • Relation type classification <br> • Confidence scoring <br> • Coreference chain resolution <br> • Output: entity-relation graph / triples |

> **Năng lực tổ chức:** NLP rất cao, ML Engineering cao, Domain Knowledge rất cao, Data Annotation phức tạp

---

### NHÓM D — SPECIAL CONTENT

#### D1. Handwriting Recognition | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Sauvola binarization (tốt hơn Otsu cho chữ viết tay) <br> • Slant correction (stroke angle detection → warpAffine) <br> • Baseline detection (horizontal projection) <br> • Line segmentation (seam carving) <br> • Word segmentation (connected component + gap) <br> • Stroke width normalization |
| **Model / Engine** | • TrOCR (Transformer, Microsoft) — SOTA, cần fine-tune <br> • Kraken <br> • Cloud: Google Vision (DOCUMENT_TEXT_DETECTION), AWS Textract <br> • CTC-based models (CRNN + CTC decoder) <br> • LM-augmented beam search decoding |
| **Post-processing** | • Language model re-ranking (CTC + LM beam search) <br> • Heavy spell correction <br> • Confidence-based rejection (loại kết quả confidence thấp) <br> • Dấu thanh tiếng Việt correction <br> • Output: text + per-word confidence |

> **Năng lực tổ chức:** CV nâng cao (preprocessing đặc thù), ML Engineering rất cao (train/fine-tune HTR), Data Annotation rất nhiều (transcript chữ viết tay), QA & Evaluation (accuracy thấp hơn printed)

---

#### D2. Stamp / Seal / Signature Detection | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Color space conversion (BGR → HSV/Lab) <br> • Color-based segmentation (đỏ: H∈[0,10]∪[170,180]) <br> • Edge detection (Canny) <br> • Morphological cleanup <br> • ROI extraction cho vùng stamp/signature |
| **Model / Engine** | • Object detection: YOLOv8/v5 fine-tuned, Faster R-CNN <br> • Instance segmentation: Mask R-CNN <br> • Signature verification: Siamese Network <br> • Stamp text OCR: polar transform → straighten → OCR <br> • Binary classifier: có stamp/signature hay không |
| **Post-processing** | • Position mapping (page, coordinates) <br> • Presence/absence classification <br> • Signature similarity scoring <br> • Stamp text extraction (circular text) <br> • Output: detection + classification + position |

> **Năng lực tổ chức:** CV cao (color segmentation, object detection), ML Engineering cao (fine-tune detector), Data Annotation (bounding box), Domain Knowledge (vị trí stamp/sig trong tài liệu VN)

---

#### D3. Barcode / QR Code | Độ khó: ★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • ROI detection (locate barcode/QR region) <br> • Contrast enhancement <br> • Perspective correction (cho mã bị nghiêng/cong) <br> • Resolution upscaling nếu mã quá nhỏ |
| **Model / Engine** | • Dedicated readers: ZBar (pyzbar), OpenCV BarcodeDetector <br> • Mobile: Google ML Kit, Apple Vision <br> • 1D: EAN-13, Code 128, Code 39, UPC-A <br> • 2D: QR Code, Data Matrix, PDF417, Aztec |
| **Post-processing** | • Payload decoding <br> • URL/data validation <br> • Format-specific parsing <br> • Error detection (mã bị hỏng 1 phần) <br> • Output: type + decoded data + position |

> **Năng lực tổ chức:** CV cơ bản, Systems Engineering (Mature libraries, ít cần ML)

---

#### D4. Mathematical Formula / Equation | Độ khó: ★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Formula region detection (tách formula khỏi text) <br> • Inline vs display formula classification <br> • Symbol isolation <br> • Binarization (formula thường có ký tự nhỏ, nét mảnh) |
| **Model / Engine** | • pix2tex (LaTeX-OCR): ViT encoder + autoregressive decoder <br> • Nougat (Meta): PDF → Markdown bao gồm LaTeX <br> • Mathpix API (accuracy cao nhất, thương mại) <br> • InftyReader (STEM documents) <br> • im2latex models |
| **Post-processing** | • LaTeX validation & cleanup <br> • MathML conversion (latex2mathml) <br> • Rendering verification (KaTeX/MathJax) <br> • Multi-line equation stitching <br> • Output: LaTeX string hoặc MathML |

> **Năng lực tổ chức:** ML Engineering cao (specialized models), Domain Knowledge (toán, hóa, vật lý), QA & Evaluation (formula accuracy)

---

#### D5. Diagram / Chart Understanding | Độ khó: ★★★★★

| Bước | Kỹ thuật |
|------|----------|
| **Preprocessing** | • Chart region detection (YOLO/Faster R-CNN) <br> • Chart type classification (bar/line/pie/flow) <br> • Axis detection & scale extraction <br> • Legend detection <br> • Color-based series separation |
| **Model / Engine** | • Chart → data: DePlot (Google), MatCha, ChartOCR, UniChart <br> • VLM: GPT-4o, Claude Vision (describe/summarize) <br> • Flowchart: node detection + edge detection → graph <br> • Bar/Line: element detection → value mapping <br> • Pie: segment angle measurement |
| **Post-processing** | • Data table reconstruction (CSV/JSON) <br> • Axis label → data mapping <br> • Chart summarization (text description) <br> • Flowchart → Mermaid/DOT conversion <br> • Output: data table hoặc structured description |

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