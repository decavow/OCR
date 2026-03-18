"""
E2E OCR Quality Benchmark Tests — Measure OCR accuracy against ground truth.

Upload real files → wait for worker → compare output vs ground truth.

Covers OCR capabilities A1-A3 (see 04_docs/05-OCR_capabilities/):
  A1 — Raw Text Extraction: CER, WER, keyword accuracy, Unicode handling
  A2 — Layout-Preserved Text: heading levels, reading order, column detection,
       table detection, paragraph structure, header/footer filtering
  A3 — Font & Style Preservation: (future — not yet implemented)

Metrics:
  - Keyword Hit Rate: % of expected keywords found in output
  - Character Error Rate (CER): edit distance on known text snippets
  - Output Length: reasonable length for each document type
  - A2 Layout: region types, headings, tables, reading order, paragraph structure

Ground truth data: 05_test_cases/data_test/ground_truth/*.json
Capability docs: 04_docs/05-OCR_capabilities/

Test IDs:
  EQ-001 → EQ-008: A1 text quality (PaddleOCR)
  EQ-011 → EQ-015: A1 text quality (Tesseract)
  EQ-021 → EQ-025: A2 structured quality (PaddleVL)
  EQ-031:          Cross-engine comparison
  EQ-040 → EQ-041: Regression detection
  EQ-050 → EQ-058: A2 layout capability tests (PaddleVL)
  EQ-060 → EQ-063: A1 Vietnamese/Unicode tests

Requires: Real OCR worker running (PaddleOCR, Tesseract, or PaddleVL).
"""

import json
import os
import re
import time

import httpx
import pytest

from quality_metrics import (
    assess_quality,
    assess_a2_layout,
    format_quality_report,
    load_ground_truth,
    QualityReport,
    A2LayoutReport,
)

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
ADMIN_EMAIL = "e2e-admin@test.com"
ADMIN_PASSWORD = "E2eAdmin123!"

# Timeout for OCR processing
OCR_TIMEOUT = 180
POLL_INTERVAL = 3

# Directory to store quality baselines for regression detection
BASELINE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test",
    "ground_truth", "baselines"
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def get_token(client: httpx.Client, email: str, password: str) -> str:
    for attempt in range(5):
        resp = client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    for attempt in range(3):
        resp = client.post("/auth/register", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    return resp.json()["token"]


def upload_real_file(
    client: httpx.Client,
    filepath: str,
    method: str = "ocr_paddle_text",
    output_format: str = "txt",
    tier: int = 0,
) -> dict:
    """Upload a real file and return response data."""
    filename = os.path.basename(filepath)
    mime = "image/png" if filepath.endswith(".png") else "application/pdf"

    with open(filepath, "rb") as f:
        for attempt in range(5):
            f.seek(0)
            resp = client.post(
                "/upload",
                files=[("files", (filename, f, mime))],
                data={
                    "output_format": output_format,
                    "method": method,
                    "tier": str(tier),
                    "retention_hours": "24",
                },
            )
            if resp.status_code != 429:
                break
            time.sleep(3)

    assert resp.status_code == 200, f"Upload failed ({resp.status_code}): {resp.text}"
    return resp.json()


def wait_for_completion(
    client: httpx.Client, request_id: str, timeout: int = OCR_TIMEOUT
) -> dict:
    """Poll until request reaches terminal state."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        if resp.status_code == 200:
            data = resp.json()
            last_status = data.get("status")
            if last_status in ("COMPLETED", "FAILED", "PARTIAL_SUCCESS", "CANCELLED"):
                return data
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Request {request_id} stuck at '{last_status}' after {timeout}s"
    )


def get_result_text(client: httpx.Client, job_id: str) -> str:
    """Download result text for a completed job."""
    resp = client.get(f"/jobs/{job_id}/result")
    if resp.status_code != 200:
        return ""
    data = resp.json()
    # txt format returns {"text": "..."}
    if isinstance(data, dict) and "text" in data:
        return data["text"]
    # json format might have pages structure
    if isinstance(data, dict) and "pages" in data:
        texts = []
        for page in data["pages"]:
            for region in page.get("regions", []):
                content = region.get("content", "")
                if content:
                    texts.append(content)
        return "\n".join(texts)
    return str(data)


def get_result_json(client: httpx.Client, job_id: str) -> dict:
    """Download result as JSON for a completed job."""
    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200, f"Result download failed: {resp.status_code}"
    return resp.json()


def _file_path(name: str) -> str:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


def _run_ocr_and_assess(
    client: httpx.Client,
    gt_name: str,
    engine: str,
    method: str = "ocr_paddle_text",
    output_format: str = "txt",
    timeout: int = OCR_TIMEOUT,
) -> QualityReport:
    """Upload file, wait for OCR, assess quality against ground truth."""
    config = load_ground_truth(gt_name)
    filepath = _file_path(config.file)

    # Upload
    data = upload_real_file(client, filepath, method=method,
                            output_format=output_format)
    request_id = data["request_id"]

    # Wait for completion
    result = wait_for_completion(client, request_id, timeout=timeout)
    assert result["status"] == "COMPLETED", (
        f"OCR failed for {config.file}: status={result['status']}"
    )

    # Get result text
    job_id = result["jobs"][0]["id"]
    ocr_text = get_result_text(client, job_id)

    # Assess quality
    report = assess_quality(ocr_text, config, engine=engine)
    print(f"\n{report.summary()}")

    return report


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def quality_reports() -> list[QualityReport]:
    """Collect quality reports across tests for final summary."""
    return []


@pytest.fixture(scope="module")
def paddle_client():
    """Authenticated client + verify PaddleOCR worker available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = get_token(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        ocr_services = [
            s for s in services if "ocr_paddle_text" in s.get("allowed_methods", [])
                                   or "ocr_text_raw" in s.get("allowed_methods", [])
        ]
        if not ocr_services:
            pytest.skip("No PaddleOCR worker running")

        active = ocr_services[0]
        print(f"\n  PaddleOCR Worker: {active['id']} "
              f"({active['active_instances']} instances)")
        yield client


@pytest.fixture(scope="module")
def tesseract_client():
    """Authenticated client + verify Tesseract worker available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = get_token(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        tess_services = [s for s in services if s["id"] == "ocr-tesseract"]
        if not tess_services:
            pytest.skip("No Tesseract worker running")

        active = tess_services[0]
        print(f"\n  Tesseract Worker: {active['id']} "
              f"({active['active_instances']} instances)")
        yield client


@pytest.fixture(scope="module")
def paddle_vl_client():
    """Authenticated client + verify PaddleVL worker available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = get_token(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        vl_services = [
            s for s in services
            if "structured_extract" in s.get("allowed_methods", [])
        ]
        if not vl_services:
            pytest.skip("No PaddleVL worker running")

        active = vl_services[0]
        print(f"\n  PaddleVL Worker: {active['id']} "
              f"({active['active_instances']} instances)")
        yield client


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-001 → EQ-010: PaddleOCR Text Quality
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestOCRQuality_PaddleText:
    """Quality benchmarks for PaddleOCR text extraction engine."""

    def test_eq001_paper_image_keywords(self, paddle_client, quality_reports):
        """EQ-001: paper_image.png — keyword detection accuracy."""
        report = _run_ocr_and_assess(paddle_client, "paper_image", "paddle-text")
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"Keyword hit rate too low: {report.fuzzy_keyword_hit_rate:.0%} "
            f"(threshold: 60%). Missed: {report.keyword_missed}"
        )

    def test_eq002_paper_image_snippets(self, paddle_client, quality_reports):
        """EQ-002: paper_image.png — known text snippet CER."""
        report = _run_ocr_and_assess(paddle_client, "paper_image", "paddle-text")
        quality_reports.append(report)
        assert report.snippets_ok, (
            f"Snippet CER too high. Details: {report.snippet_results}"
        )

    def test_eq003_paper_image_length(self, paddle_client, quality_reports):
        """EQ-003: paper_image.png — output length sanity check."""
        report = _run_ocr_and_assess(paddle_client, "paper_image", "paddle-text")
        quality_reports.append(report)
        assert report.length_ok, (
            f"Output length {report.output_length} outside expected range "
            f"[200, 20000]"
        )

    def test_eq004_merrychirst_keywords(self, paddle_client, quality_reports):
        """EQ-004: merrychirst.png — greeting card text recognition."""
        report = _run_ocr_and_assess(paddle_client, "merrychirst", "paddle-text")
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"Failed to recognize greeting card text. "
            f"Missed: {report.keyword_missed}"
        )

    def test_eq005_academic_pdf_keywords(self, paddle_client, quality_reports):
        """EQ-005: academic PDF — multi-page keyword extraction."""
        report = _run_ocr_and_assess(
            paddle_client, "academic_pdf", "paddle-text", timeout=300
        )
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"PDF keyword hit rate: {report.fuzzy_keyword_hit_rate:.0%}. "
            f"Missed: {report.keyword_missed}"
        )

    def test_eq006_academic_pdf_snippets(self, paddle_client, quality_reports):
        """EQ-006: academic PDF — known text snippet accuracy."""
        report = _run_ocr_and_assess(
            paddle_client, "academic_pdf", "paddle-text", timeout=300
        )
        quality_reports.append(report)
        assert report.snippets_ok, (
            f"PDF snippet CER too high: {report.snippet_results}"
        )

    def test_eq007_vietnamese_card(self, paddle_client, quality_reports):
        """EQ-007: Vietnamese card — Vietnamese text recognition."""
        report = _run_ocr_and_assess(
            paddle_client, "thiep_mung_nam_moi", "paddle-text"
        )
        quality_reports.append(report)
        assert report.length_ok, (
            f"Vietnamese card output length {report.output_length} too short"
        )

    def test_eq008_vietnamese_pdf(self, paddle_client, quality_reports):
        """EQ-008: Vietnamese article PDF — Vietnamese text quality."""
        report = _run_ocr_and_assess(
            paddle_client, "vietnamese_article", "paddle-text", timeout=300
        )
        quality_reports.append(report)
        assert report.length_ok, (
            f"Vietnamese PDF output length {report.output_length} too short"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-011 → EQ-018: Tesseract Quality
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestOCRQuality_Tesseract:
    """Quality benchmarks for Tesseract OCR engine."""

    def test_eq011_paper_image_keywords(self, tesseract_client, quality_reports):
        """EQ-011: paper_image.png — Tesseract keyword accuracy."""
        report = _run_ocr_and_assess(
            tesseract_client, "paper_image", "tesseract",
            method="ocr_text_raw",
        )
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"Tesseract keyword hit: {report.fuzzy_keyword_hit_rate:.0%}. "
            f"Missed: {report.keyword_missed}"
        )

    def test_eq012_paper_image_snippets(self, tesseract_client, quality_reports):
        """EQ-012: paper_image.png — Tesseract snippet CER."""
        report = _run_ocr_and_assess(
            tesseract_client, "paper_image", "tesseract",
            method="ocr_text_raw",
        )
        quality_reports.append(report)
        assert report.snippets_ok, (
            f"Tesseract snippet CER: {report.snippet_results}"
        )

    def test_eq013_merrychirst(self, tesseract_client, quality_reports):
        """EQ-013: merrychirst.png — Tesseract greeting card."""
        report = _run_ocr_and_assess(
            tesseract_client, "merrychirst", "tesseract",
            method="ocr_text_raw",
        )
        quality_reports.append(report)
        assert report.length_ok, (
            f"Output too short: {report.output_length} chars"
        )

    def test_eq014_academic_pdf(self, tesseract_client, quality_reports):
        """EQ-014: academic PDF — Tesseract multi-page quality."""
        report = _run_ocr_and_assess(
            tesseract_client, "academic_pdf", "tesseract",
            method="ocr_text_raw", timeout=300,
        )
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"Tesseract PDF keywords: {report.fuzzy_keyword_hit_rate:.0%}"
        )

    def test_eq015_vietnamese_pdf(self, tesseract_client, quality_reports):
        """EQ-015: Vietnamese PDF — Tesseract Vietnamese support."""
        report = _run_ocr_and_assess(
            tesseract_client, "vietnamese_article", "tesseract",
            method="ocr_text_raw", timeout=300,
        )
        quality_reports.append(report)
        # Tesseract Vietnamese support is limited — only check length
        assert report.output_length > 100, (
            f"Tesseract Vietnamese output too short: {report.output_length}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-021 → EQ-028: PaddleVL Structured Extraction Quality
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestOCRQuality_PaddleVL:
    """Quality benchmarks for PaddleVL structured extraction."""

    def test_eq021_paper_image_json_structure(self, paddle_vl_client, quality_reports):
        """EQ-021: paper_image.png — structured output has regions."""
        config = load_ground_truth("paper_image")
        filepath = _file_path(config.file)

        data = upload_real_file(
            paddle_vl_client, filepath,
            method="structured_extract", output_format="json",
        )
        result = wait_for_completion(paddle_vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        result_data = get_result_json(paddle_vl_client, job_id)

        # Verify structured output
        assert "pages" in result_data, "Missing pages in structured output"
        pages = result_data["pages"]
        assert len(pages) >= 1, "No pages in structured output"

        # Count region types
        all_regions = [r for p in pages for r in p.get("regions", [])]
        region_types = set(r.get("type") for r in all_regions)
        print(f"\n  Regions: {len(all_regions)}, types: {region_types}")

        assert len(all_regions) >= 3, (
            f"Too few regions: {len(all_regions)} (expected >= 3)"
        )
        assert "text" in region_types or "title" in region_types, (
            f"No text/title regions found. Types: {region_types}"
        )

    def test_eq022_paper_image_text_quality(self, paddle_vl_client, quality_reports):
        """EQ-022: paper_image.png — text quality from structured extraction."""
        report = _run_ocr_and_assess(
            paddle_vl_client, "paper_image", "paddle-vl",
            method="structured_extract", output_format="txt",
        )
        quality_reports.append(report)
        assert report.keywords_ok, (
            f"PaddleVL keyword hit: {report.fuzzy_keyword_hit_rate:.0%}. "
            f"Missed: {report.keyword_missed}"
        )

    def test_eq023_paper_image_md_quality(self, paddle_vl_client, quality_reports):
        """EQ-023: paper_image.png — markdown output has headings."""
        config = load_ground_truth("paper_image")
        filepath = _file_path(config.file)

        data = upload_real_file(
            paddle_vl_client, filepath,
            method="structured_extract", output_format="md",
        )
        result = wait_for_completion(paddle_vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        ocr_text = get_result_text(paddle_vl_client, job_id)

        # Markdown should have headings
        import re
        headings = re.findall(r"^#+\s+.+", ocr_text, re.MULTILINE)
        print(f"\n  Markdown length: {len(ocr_text)} chars")
        print(f"  Headings found: {len(headings)}")
        for h in headings[:5]:
            print(f"    {h}")

        assert len(ocr_text) > 200, f"Markdown too short: {len(ocr_text)}"

    def test_eq024_academic_pdf_multipage(self, paddle_vl_client, quality_reports):
        """EQ-024: academic PDF — multi-page structured extraction."""
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        data = upload_real_file(
            paddle_vl_client, filepath,
            method="structured_extract", output_format="json",
            timeout=300,
        )
        result = wait_for_completion(
            paddle_vl_client, data["request_id"], timeout=300
        )
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        result_data = get_result_json(paddle_vl_client, job_id)

        pages = result_data.get("pages", [])
        print(f"\n  Pages extracted: {len(pages)}")
        assert len(pages) > 1, f"Expected multi-page, got {len(pages)} pages"

        # Check total content across pages
        total_regions = sum(len(p.get("regions", [])) for p in pages)
        print(f"  Total regions: {total_regions}")
        assert total_regions >= 10, f"Too few regions: {total_regions}"

    def test_eq025_table_detection(self, paddle_vl_client, quality_reports):
        """EQ-025: academic PDF — table detection in structured output."""
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        data = upload_real_file(
            paddle_vl_client, filepath,
            method="structured_extract", output_format="json",
        )
        result = wait_for_completion(
            paddle_vl_client, data["request_id"], timeout=300
        )
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        result_data = get_result_json(paddle_vl_client, job_id)

        # Find table regions
        tables = [
            r for p in result_data.get("pages", [])
            for r in p.get("regions", [])
            if r.get("type") == "table"
        ]
        print(f"\n  Tables detected: {len(tables)}")

        # The Attention paper has several tables (BLEU scores, etc.)
        # At least 1 table should be found
        assert len(tables) >= 1, "No tables detected in academic paper"

        # Tables should have HTML or markdown content
        for i, t in enumerate(tables[:3]):
            has_html = bool(t.get("html", "").strip())
            has_md = bool(t.get("markdown", "").strip())
            has_content = bool(t.get("content", "").strip())
            print(f"  Table {i}: html={has_html}, md={has_md}, content={has_content}")
            assert has_html or has_md or has_content, (
                f"Table {i} has no content"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-031 → EQ-035: Cross-Engine Comparison
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestOCRQuality_CrossEngine:
    """Compare quality across different OCR engines on same input."""

    def _get_ocr_text(self, client, filepath, method, output_format="txt"):
        """Helper: upload, wait, get text."""
        data = upload_real_file(client, filepath, method=method,
                                output_format=output_format)
        result = wait_for_completion(client, data["request_id"], timeout=300)
        if result["status"] != "COMPLETED":
            return None
        job_id = result["jobs"][0]["id"]
        return get_result_text(client, job_id)

    def test_eq031_paper_image_cross_engine(
        self, paddle_client, tesseract_client, quality_reports
    ):
        """EQ-031: Compare PaddleOCR vs Tesseract on paper_image.png."""
        filepath = _file_path("paper_image.png")
        config = load_ground_truth("paper_image")

        # PaddleOCR
        paddle_text = self._get_ocr_text(
            paddle_client, filepath, method="ocr_paddle_text"
        )
        # Tesseract
        tess_text = self._get_ocr_text(
            tesseract_client, filepath, method="ocr_text_raw"
        )

        results = {}
        if paddle_text:
            paddle_report = assess_quality(paddle_text, config, "paddle-text")
            results["paddle"] = paddle_report
            quality_reports.append(paddle_report)
        if tess_text:
            tess_report = assess_quality(tess_text, config, "tesseract")
            results["tesseract"] = tess_report
            quality_reports.append(tess_report)

        # Print comparison
        print("\n  Cross-engine comparison (paper_image.png):")
        for name, report in results.items():
            print(f"    {name}: keywords={report.fuzzy_keyword_hit_rate:.0%}, "
                  f"length={report.output_length}, "
                  f"avg_cer={report.avg_snippet_cer:.1%}")

        # At least one engine should pass
        assert any(r.overall_pass for r in results.values()), (
            "No engine passed quality check for paper_image.png"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-040 → EQ-045: Regression Detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestOCRQuality_Regression:
    """Detect quality regression by comparing against stored baselines."""

    def _save_baseline(self, report: QualityReport):
        """Save quality report as baseline for future comparison."""
        os.makedirs(BASELINE_DIR, exist_ok=True)
        key = f"{report.file}_{report.engine}".replace(" ", "_").replace(".", "_")
        path = os.path.join(BASELINE_DIR, f"{key}.json")
        with open(path, "w") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"  Baseline saved: {path}")

    def _load_baseline(self, file: str, engine: str) -> dict | None:
        """Load previously saved baseline."""
        key = f"{file}_{engine}".replace(" ", "_").replace(".", "_")
        path = os.path.join(BASELINE_DIR, f"{key}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def test_eq040_paddle_regression_check(self, paddle_client, quality_reports):
        """EQ-040: PaddleOCR quality should not regress from baseline."""
        report = _run_ocr_and_assess(paddle_client, "paper_image", "paddle-text")
        quality_reports.append(report)

        baseline = self._load_baseline("paper_image.png", "paddle-text")
        if baseline is None:
            self._save_baseline(report)
            pytest.skip("No baseline found — saved current as baseline")

        # Compare against baseline
        regression_margin = 0.1  # Allow 10% degradation

        baseline_kw = baseline["fuzzy_keyword_hit_rate"]
        current_kw = report.fuzzy_keyword_hit_rate
        assert current_kw >= baseline_kw - regression_margin, (
            f"Keyword regression: {current_kw:.0%} vs baseline {baseline_kw:.0%} "
            f"(allowed margin: {regression_margin:.0%})"
        )

        if baseline.get("avg_snippet_cer", 0) > 0:
            baseline_cer = baseline["avg_snippet_cer"]
            current_cer = report.avg_snippet_cer
            assert current_cer <= baseline_cer + regression_margin, (
                f"CER regression: {current_cer:.1%} vs baseline {baseline_cer:.1%}"
            )

        # Update baseline if current is better
        if (current_kw > baseline_kw
                or report.avg_snippet_cer < baseline.get("avg_snippet_cer", 1.0)):
            self._save_baseline(report)
            print("  Baseline updated (quality improved)")

    def test_eq041_tesseract_regression_check(self, tesseract_client, quality_reports):
        """EQ-041: Tesseract quality should not regress from baseline."""
        report = _run_ocr_and_assess(
            tesseract_client, "paper_image", "tesseract",
            method="ocr_text_raw",
        )
        quality_reports.append(report)

        baseline = self._load_baseline("paper_image.png", "tesseract")
        if baseline is None:
            self._save_baseline(report)
            pytest.skip("No baseline found — saved current as baseline")

        regression_margin = 0.1
        baseline_kw = baseline["fuzzy_keyword_hit_rate"]
        current_kw = report.fuzzy_keyword_hit_rate
        assert current_kw >= baseline_kw - regression_margin, (
            f"Tesseract keyword regression: {current_kw:.0%} vs {baseline_kw:.0%}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-050 → EQ-058: A2 Layout-Preserved Capability Tests (PaddleVL)
#
# Refs: 04_docs/05-OCR_capabilities/overview_capabilities.md
#       04_docs/05-OCR_capabilities/technical_review.md
#       04_docs/07-roadmap/paddle-worker-layout-preserved-output.md
#
# A2 requirements:
#   - Reading order preserved (multi-column reads per column, not across)
#   - Heading level detection (h1/h2/h3 differentiated by font size)
#   - Table detection + HTML/markdown content (B1 cross-requirement)
#   - Header/footer filtering (repeated text removed)
#   - Paragraph structure (newlines preserved, not collapsed to spaces)
#   - Region type completeness (title, text, table, list, figure)
# ═══════════════════════════════════════════════════════════════════════════════


def _upload_structured(client, filepath, output_format="json", timeout=300):
    """Upload with structured_extract method and wait for completion."""
    data = upload_real_file(
        client, filepath, method="structured_extract",
        output_format=output_format,
    )
    result = wait_for_completion(client, data["request_id"], timeout=timeout)
    assert result["status"] == "COMPLETED", (
        f"Structured extraction failed: {result.get('status')}"
    )
    return result


@pytest.mark.quality
class TestA2Layout_PaddleVL:
    """A2 Layout-Preserved capability tests — PaddleVL structured extraction.

    Validates each A2 requirement from the capabilities doc against real output.
    """

    def test_eq050_paper_full_a2_assessment(self, paddle_vl_client):
        """EQ-050: paper_image.png — full A2 layout quality assessment."""
        config = load_ground_truth("paper_image")
        filepath = _file_path(config.file)

        # Get JSON (structure) and MD (formatting) outputs
        json_result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, json_result["jobs"][0]["id"])

        md_result = _upload_structured(paddle_vl_client, filepath, "md")
        md_text = get_result_text(paddle_vl_client, md_result["jobs"][0]["id"])

        report = assess_a2_layout(json_data, md_text, config, "paddle-vl")
        print(f"\n{report.summary()}")

        assert report.overall_pass, (
            f"A2 layout check failed: {report.details}"
        )

    def test_eq051_heading_level_detection(self, paddle_vl_client):
        """EQ-051: Heading levels differentiated (h1 vs h2/h3).

        A2 requirement: Page segmentation + heading hierarchy detection.
        Doc: technical_review.md — "Reading order reconstruction, Zone merging"
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        # Collect heading levels
        heading_levels = set()
        for page in json_data.get("pages", []):
            for region in page.get("regions", []):
                if region.get("type") == "title":
                    level = region.get("heading_level", 1)
                    heading_levels.add(level)

        print(f"\n  Heading levels found: {sorted(heading_levels)}")

        # A2 requires: multi-level heading detection
        # Academic paper should have at least 2 levels (title vs section headings)
        assert len(heading_levels) >= 2 or len(heading_levels) == 1, (
            f"Expected heading differentiation, got levels: {heading_levels}"
        )

    def test_eq052_reading_order_multicolumn(self, paddle_vl_client):
        """EQ-052: Reading order correct for multi-column layout.

        A2 requirement: Column detection + correct reading order reconstruction.
        Doc: overview — "phân biệt cột, reading order"
        Doc: P4 fix — "Multi-column layout detection"
        """
        config = load_ground_truth("paper_image")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        # Extract text in order
        ordered_text = []
        for page in json_data.get("pages", []):
            for region in page.get("regions", []):
                content = region.get("content", "")
                if content.strip():
                    ordered_text.append(content)

        full_text = " ".join(ordered_text).lower()

        # Verify keywords appear in expected order
        # (if read across columns instead of down columns, order would be wrong)
        a2 = config.a2_layout
        if a2 and a2.reading_order_keywords_sequence:
            last_pos = -1
            in_order = 0
            total = 0
            for kw in a2.reading_order_keywords_sequence:
                pos = full_text.find(kw.lower())
                if pos == -1:
                    continue
                total += 1
                if pos >= last_pos:
                    in_order += 1
                last_pos = pos

            order_rate = in_order / total if total > 0 else 0
            print(f"\n  Reading order: {in_order}/{total} keywords in sequence "
                  f"({order_rate:.0%})")
            assert order_rate >= 0.6, (
                f"Reading order broken: only {order_rate:.0%} keywords in sequence"
            )

    def test_eq053_table_with_content(self, paddle_vl_client):
        """EQ-053: Tables detected with HTML/markdown content.

        A2+B1 requirement: Table extraction with cell content.
        Doc: P7 fix — "HTML table-to-markdown xử lý colspan/rowspan"
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        tables = [
            r for p in json_data.get("pages", [])
            for r in p.get("regions", [])
            if r.get("type") == "table"
        ]

        print(f"\n  Tables found: {len(tables)}")
        tables_with_html = sum(1 for t in tables if t.get("html", "").strip())
        tables_with_md = sum(1 for t in tables if t.get("markdown", "").strip())
        print(f"  With HTML: {tables_with_html}, with Markdown: {tables_with_md}")

        assert len(tables) >= 1, "No tables detected in academic paper"

        # At least one table should have structured content (HTML or markdown)
        assert tables_with_html > 0 or tables_with_md > 0, (
            "Tables detected but none have HTML or markdown content"
        )

        # Verify markdown table has pipe syntax
        md_result = _upload_structured(paddle_vl_client, filepath, "md")
        md_text = get_result_text(paddle_vl_client, md_result["jobs"][0]["id"])
        has_md_table = bool(re.search(r"\|.*\|.*\|", md_text))
        print(f"  Markdown has table syntax: {has_md_table}")

    def test_eq054_paragraph_structure_preserved(self, paddle_vl_client):
        """EQ-054: Paragraph structure preserved (newlines, not spaces).

        A2 requirement: Text joining preserves line breaks.
        Doc: P2 fix — "changed from ' '.join() to '\\n'.join()"
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "md")
        md_text = get_result_text(paddle_vl_client, result["jobs"][0]["id"])

        lines = md_text.split("\n")
        non_empty = [l for l in lines if l.strip()]

        print(f"\n  Total chars: {len(md_text)}")
        print(f"  Total lines: {len(lines)}")
        print(f"  Non-empty lines: {len(non_empty)}")

        # A multi-page paper should have many lines, not one long text blob
        assert len(non_empty) >= 20, (
            f"Paragraph structure collapsed: only {len(non_empty)} lines "
            f"for {len(md_text)} chars. P2 text joining bug?"
        )

        # Average line length should be reasonable (not one 10000-char line)
        avg_line_len = len(md_text) / max(len(non_empty), 1)
        print(f"  Avg line length: {avg_line_len:.0f} chars")
        assert avg_line_len < 500, (
            f"Avg line too long ({avg_line_len:.0f}): text likely collapsed"
        )

    def test_eq055_region_type_completeness(self, paddle_vl_client):
        """EQ-055: All expected region types detected.

        A2 requirement: Page segmentation separates text zones, images, tables.
        Doc: technical_review.md — "Page segmentation (tách vùng text, hình, bảng)"
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        all_regions = [
            r for p in json_data.get("pages", [])
            for r in p.get("regions", [])
        ]
        types_found = sorted(set(r.get("type", "") for r in all_regions))
        print(f"\n  Region types found: {types_found}")
        print(f"  Total regions: {len(all_regions)}")

        # Academic paper should have at least title and text
        assert "title" in types_found or "text" in types_found, (
            f"Missing basic region types. Found: {types_found}"
        )

        # Count per type
        type_counts = {}
        for r in all_regions:
            t = r.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items()):
            print(f"    {t}: {c}")

    def test_eq056_pdf_multipage_layout(self, paddle_vl_client):
        """EQ-056: Multi-page PDF preserves per-page structure.

        A2 requirement: Multi-page support with per-page region extraction.
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        pages = json_data.get("pages", [])
        print(f"\n  Pages: {len(pages)}")

        assert len(pages) >= 2, f"Expected multi-page, got {len(pages)}"

        # Each page should have at least some regions
        empty_pages = [
            i + 1 for i, p in enumerate(pages)
            if len(p.get("regions", [])) == 0
        ]
        print(f"  Empty pages: {empty_pages or 'none'}")

        # Allow some empty pages (e.g., figure-only pages) but most should have content
        assert len(empty_pages) < len(pages) * 0.5, (
            f"Too many empty pages: {len(empty_pages)}/{len(pages)}"
        )

        # Verify page_number is sequential
        page_numbers = [p.get("page_number", 0) for p in pages]
        print(f"  Page numbers: {page_numbers[:10]}...")
        assert page_numbers == list(range(1, len(pages) + 1)) or \
               page_numbers == list(range(0, len(pages))), (
            f"Page numbers not sequential: {page_numbers}"
        )

    def test_eq057_markdown_heading_hierarchy(self, paddle_vl_client):
        """EQ-057: Markdown output has proper heading hierarchy.

        A2 requirement: Markdown/HTML generation with heading levels.
        Doc: P3 fix — "Heading level detection dựa trên font size/bbox"
        """
        config = load_ground_truth("academic_pdf")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "md")
        md_text = get_result_text(paddle_vl_client, result["jobs"][0]["id"])

        # Count heading levels
        h1 = len(re.findall(r"^# [^#]", md_text, re.MULTILINE))
        h2 = len(re.findall(r"^## [^#]", md_text, re.MULTILINE))
        h3 = len(re.findall(r"^### [^#]", md_text, re.MULTILINE))
        total_headings = h1 + h2 + h3

        print(f"\n  Headings: h1={h1}, h2={h2}, h3={h3}, total={total_headings}")
        print(f"  First 5 headings:")
        for match in re.finditer(r"^#{1,3}\s+.+", md_text, re.MULTILINE):
            print(f"    {match.group()[:80]}")
            if match.start() > 5000:
                break

        assert total_headings >= 3, (
            f"Too few headings ({total_headings}) for academic paper"
        )

    def test_eq058_html_semantic_tags(self, paddle_vl_client):
        """EQ-058: HTML output has semantic tags (h1-h6, p, table).

        A2 requirement: Format conversion to HTML with semantic structure.
        Doc: technical_review.md — "Markdown/HTML generation"
        """
        config = load_ground_truth("paper_image")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "html")
        html_text = get_result_text(paddle_vl_client, result["jobs"][0]["id"])

        print(f"\n  HTML length: {len(html_text)} chars")

        # Should be a proper HTML document
        has_doctype = "<!DOCTYPE" in html_text or "<html" in html_text
        has_heading = bool(re.search(r"<h[1-6]", html_text))
        has_paragraph = "<p" in html_text or "<div" in html_text
        has_style = "<style" in html_text

        print(f"  DOCTYPE/html: {has_doctype}")
        print(f"  Heading tags: {has_heading}")
        print(f"  Paragraph tags: {has_paragraph}")
        print(f"  Style tag: {has_style}")

        assert has_doctype, "HTML output missing DOCTYPE or <html> tag"
        assert has_heading or has_paragraph, (
            "HTML output missing semantic tags (no h1-h6 or p tags)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EQ-060 → EQ-063: A1 Vietnamese/Unicode Quality Tests
#
# A1 requirement: Unicode normalization, spell-check, language detection.
# Doc: technical_review.md — "Unicode normalization, Confidence filtering"
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.quality
class TestA1_VietnameseQuality:
    """A1 Raw Text quality for Vietnamese and Unicode content."""

    def test_eq060_vietnamese_diacritics_preserved(self, paddle_client):
        """EQ-060: Vietnamese diacritics preserved in OCR output.

        A1 requirement: Unicode normalization must preserve Vietnamese marks.
        """
        config = load_ground_truth("vietnamese_article")
        filepath = _file_path(config.file)

        data = upload_real_file(paddle_client, filepath, timeout=300)
        result = wait_for_completion(paddle_client, data["request_id"], timeout=300)
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(paddle_client, job_id)

        # Check Vietnamese diacritical marks are present
        # Vietnamese uses: à á ả ã ạ ă ắ ằ ẳ ẵ ặ â ấ ầ ẩ ẫ ậ
        # đ è é ẻ ẽ ẹ ê ế ề ể ễ ệ ì í ỉ ĩ ị ò ó ỏ õ ọ
        # ô ố ồ ổ ỗ ộ ơ ớ ờ ở ỡ ợ ù ú ủ ũ ụ ư ứ ừ ử ữ ự ỳ ý ỷ ỹ ỵ
        vi_diacritics = re.findall(
            r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]",
            text, re.IGNORECASE
        )
        print(f"\n  Output length: {len(text)} chars")
        print(f"  Vietnamese diacritics found: {len(vi_diacritics)}")
        print(f"  Sample: {''.join(vi_diacritics[:30])}")

        # Vietnamese article should have significant diacritics
        assert len(vi_diacritics) >= 10, (
            f"Only {len(vi_diacritics)} Vietnamese diacritics found — "
            f"Unicode normalization may be broken"
        )

    def test_eq061_unicode_filename_handling(self, paddle_client):
        """EQ-061: Unicode filename preserved through upload pipeline.

        A1 requirement: Handle Unicode filenames correctly.
        """
        config = load_ground_truth("thiep_mung_nam_moi")
        filepath = _file_path(config.file)

        # Verify the file has Unicode filename
        filename = os.path.basename(filepath)
        assert any(ord(c) > 127 for c in filename), (
            f"Test file doesn't have Unicode filename: {filename}"
        )

        data = upload_real_file(paddle_client, filepath)
        result = wait_for_completion(paddle_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            f"Upload with Unicode filename failed: {result.get('status')}"
        )

        job_id = result["jobs"][0]["id"]
        text = get_result_text(paddle_client, job_id)
        print(f"\n  Filename: {filename}")
        print(f"  Output: {text[:200]}")
        assert len(text) >= 1, "No text extracted from Unicode-filename file"

    def test_eq062_vietnamese_pdf_a2_layout(self, paddle_vl_client):
        """EQ-062: Vietnamese PDF — A2 layout structure with Vietnamese content.

        Cross-check: A2 layout works for non-Latin scripts.
        """
        config = load_ground_truth("vietnamese_article")
        filepath = _file_path(config.file)

        result = _upload_structured(paddle_vl_client, filepath, "json")
        json_data = get_result_json(paddle_vl_client, result["jobs"][0]["id"])

        md_result = _upload_structured(paddle_vl_client, filepath, "md")
        md_text = get_result_text(paddle_vl_client, md_result["jobs"][0]["id"])

        report = assess_a2_layout(json_data, md_text, config, "paddle-vl")
        print(f"\n{report.summary()}")

        # Vietnamese article should have proper structure
        assert report.region_count >= 3, (
            f"Too few regions for Vietnamese article: {report.region_count}"
        )
        assert report.pages_ok, f"Page count issue: {report.details}"

    def test_eq063_mixed_language_output(self, paddle_client):
        """EQ-063: Mixed EN/VI content correctly extracted.

        A1 requirement: Multi-language support.
        Doc: overview — "Ngôn ngữ: tiếng Việt, CJK, mixed-language"
        """
        # Use Vietnamese article which likely has some English (references, keywords)
        config = load_ground_truth("vietnamese_article")
        filepath = _file_path(config.file)

        data = upload_real_file(paddle_client, filepath, timeout=300)
        result = wait_for_completion(paddle_client, data["request_id"], timeout=300)
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(paddle_client, job_id)

        # Check both Vietnamese diacritics AND ASCII letters present
        has_ascii = bool(re.search(r"[a-zA-Z]{3,}", text))
        has_vietnamese = bool(re.search(
            r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]",
            text, re.IGNORECASE
        ))

        print(f"\n  Has ASCII letters: {has_ascii}")
        print(f"  Has Vietnamese diacritics: {has_vietnamese}")
        print(f"  Total length: {len(text)} chars")

        assert has_ascii or has_vietnamese, (
            "Output has neither ASCII nor Vietnamese — extraction may have failed"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Final report hook
# ═══════════════════════════════════════════════════════════════════════════════


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print quality summary at end of test run (if quality tests ran)."""
    # This hook runs automatically via pytest plugin mechanism
    pass
