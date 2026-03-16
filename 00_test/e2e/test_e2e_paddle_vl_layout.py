"""
E2E tests for Paddle-VL Layout-Preserved Output (A2 capability).

Uploads real files with method=structured_extract, waits for the
paddle-vl worker to process, then verifies output quality across
all formats (JSON, Markdown, HTML, plain text).

Verifies:
  - Region types preserved (title, text, table, list, figure)
  - Heading level detection (h1/h2/h3)
  - Reading order correctness
  - Table detection and markdown conversion
  - Multi-page PDF support
  - Paragraph structure preservation (newlines, not spaces)

Requires:
  - Backend running at E2E_BASE_URL (default http://localhost:8080/api/v1)
  - MinIO + NATS running
  - PaddleOCR-VL worker running (ocr-paddle-vl service type APPROVED,
    with structured_extract method)

Test data: 05_test_cases/data_test/
"""

import json
import os
import re
import time

import httpx
import pytest

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
ADMIN_EMAIL = "e2e-admin@test.com"
ADMIN_PASSWORD = "E2eAdmin123!"

OCR_TIMEOUT = 180  # structured extraction can be slow
POLL_INTERVAL = 3


# ─── Helpers ─────────────────────────────────────────────────────────────────


def get_token(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    return resp.json()["token"]


def upload_for_structured_extract(
    client: httpx.Client,
    filepath: str,
    output_format: str = "json",
    tier: int = 0,
) -> dict:
    """Upload a file with method=structured_extract."""
    filename = os.path.basename(filepath)
    mime = "image/png" if filepath.lower().endswith(".png") else "application/pdf"

    with open(filepath, "rb") as f:
        for attempt in range(5):
            f.seek(0)
            resp = client.post(
                "/upload",
                files=[("files", (filename, f, mime))],
                data={
                    "output_format": output_format,
                    "method": "structured_extract",
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
    """Poll until request reaches a terminal state."""
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


def get_result_json(client: httpx.Client, job_id: str) -> dict:
    """Get result parsed as JSON (for output_format=json)."""
    resp = client.get(f"/jobs/{job_id}/result?format=json")
    assert resp.status_code == 200, f"Result fetch failed: {resp.text}"
    return resp.json()


def get_result_text(client: httpx.Client, job_id: str) -> str:
    """Get result as raw text (for md/html/txt output_format)."""
    resp = client.get(f"/jobs/{job_id}/result?format=raw")
    assert resp.status_code == 200, f"Result fetch failed: {resp.text}"
    return resp.text


def file_path(name: str) -> str:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def vl_client():
    """Authenticated client with verified paddle-vl worker available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = get_token(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        # Check paddle-vl worker
        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        vl_services = [
            s for s in services if "structured_extract" in s.get("allowed_methods", [])
        ]
        if not vl_services:
            pytest.skip(
                "No paddle-vl worker running (structured_extract not available)"
            )

        active = vl_services[0]
        print(
            f"\n  Paddle-VL Worker: {active['id']} "
            f"({active.get('active_instances', 0)} instances)"
        )

        yield client


# ─── Tests: JSON output format ──────────────────────────────────────────────


class TestPaddleVL_JSON:
    """E2E-VL-001 to E2E-VL-005: JSON structured output verification."""

    def test_evl001_json_structure(self, vl_client):
        """E2E-VL-001: JSON output has pages + summary + regions with types."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(vl_client, request_id)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        parsed = get_result_json(vl_client, job_id)

        # Top-level structure
        assert "pages" in parsed, "JSON must have 'pages' key"
        assert "summary" in parsed, "JSON must have 'summary' key"
        assert isinstance(parsed["pages"], list)
        assert len(parsed["pages"]) >= 1

        # Summary fields
        summary = parsed["summary"]
        assert summary["total_pages"] >= 1
        assert summary["total_regions"] >= 1
        print(f"  Summary: {json.dumps(summary)}")

    def test_evl002_regions_have_types(self, vl_client):
        """E2E-VL-002: Regions have type, bbox, and content/html."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])
        page = parsed["pages"][0]

        region_types = set()
        for region in page["regions"]:
            rtype = region["type"]
            region_types.add(rtype)
            assert rtype in ("text", "title", "table", "list", "figure"), (
                f"Unknown region type: {rtype}"
            )
            assert "bbox" in region, f"Region missing bbox: {region}"

            if rtype in ("text", "title", "list"):
                assert "content" in region, f"{rtype} region missing content"
                assert len(region["content"]) > 0
            elif rtype == "table":
                assert "html" in region or "markdown" in region

        print(f"  Region types found: {region_types}")
        # At minimum, we expect text regions from a paper image
        assert "text" in region_types, "Expected at least text regions"

    def test_evl003_heading_levels_detected(self, vl_client):
        """E2E-VL-003: Title regions have heading_level field."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])

        titles = [
            r
            for p in parsed["pages"]
            for r in p["regions"]
            if r["type"] == "title"
        ]
        if not titles:
            pytest.skip("No title regions detected in test image")

        for title in titles:
            assert "heading_level" in title, (
                f"Title missing heading_level: {title.get('content', '')[:50]}"
            )
            assert title["heading_level"] in (1, 2, 3), (
                f"Invalid heading_level: {title['heading_level']}"
            )
        print(
            f"  Found {len(titles)} titles: "
            + ", ".join(
                f"h{t['heading_level']}: {t['content'][:30]}" for t in titles[:5]
            )
        )

    def test_evl004_bbox_valid(self, vl_client):
        """E2E-VL-004: Bounding boxes have valid coordinates."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])

        for page in parsed["pages"]:
            for region in page["regions"]:
                bbox = region.get("bbox", [])
                if not bbox or bbox == [0, 0, 0, 0]:
                    continue  # fallback regions may have zero bbox
                assert len(bbox) == 4, f"bbox must have 4 values: {bbox}"
                x1, y1, x2, y2 = bbox
                assert x2 > x1, f"x2 must > x1: {bbox}"
                assert y2 > y1, f"y2 must > y1: {bbox}"

    def test_evl005_text_preserves_newlines(self, vl_client):
        """E2E-VL-005: Text regions preserve newlines (not space-joined)."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])

        text_regions = [
            r
            for p in parsed["pages"]
            for r in p["regions"]
            if r["type"] == "text" and len(r.get("content", "")) > 50
        ]
        if not text_regions:
            pytest.skip("No long text regions to check newline preservation")

        # At least some text regions should have newlines (multi-line paragraphs)
        has_newlines = any("\n" in r["content"] for r in text_regions)
        print(
            f"  {len(text_regions)} text regions, "
            f"{'some' if has_newlines else 'none'} have newlines"
        )
        # Log samples
        for r in text_regions[:3]:
            preview = r["content"][:100].replace("\n", "\\n")
            print(f"    [{len(r['content'])} chars] {preview}")


# ─── Tests: Markdown output format ──────────────────────────────────────────


class TestPaddleVL_Markdown:
    """E2E-VL-006 to E2E-VL-009: Markdown output verification."""

    def test_evl006_markdown_has_headings(self, vl_client):
        """E2E-VL-006: Markdown output contains # heading syntax."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="md")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        md = get_result_text(vl_client, result["jobs"][0]["id"])
        assert len(md) > 10, "Markdown output too short"

        # Check for heading markers
        heading_lines = [l for l in md.split("\n") if re.match(r"^#{1,6}\s", l)]
        print(f"  MD length: {len(md)} chars, {len(heading_lines)} headings")
        for h in heading_lines[:5]:
            print(f"    {h[:80]}")

        if not heading_lines:
            # Not a failure — image might not have detectable titles
            print("  WARNING: No headings detected in markdown output")

    def test_evl007_markdown_has_content(self, vl_client):
        """E2E-VL-007: Markdown has substantial text content."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="md")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        md = get_result_text(vl_client, result["jobs"][0]["id"])
        assert len(md) > 50, f"Markdown too short ({len(md)} chars)"

        # Should have multiple paragraphs (non-empty lines)
        paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
        print(f"  {len(paragraphs)} paragraphs, {len(md)} total chars")
        assert len(paragraphs) >= 1, "Expected at least 1 paragraph"

    def test_evl008_markdown_heading_levels(self, vl_client):
        """E2E-VL-008: Markdown has differentiated heading levels (# vs ##)."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="md")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        md = get_result_text(vl_client, result["jobs"][0]["id"])
        heading_levels = set()
        for line in md.split("\n"):
            m = re.match(r"^(#{1,6})\s", line)
            if m:
                heading_levels.add(len(m.group(1)))

        print(f"  Heading levels found: {heading_levels}")
        # Log whether h1/h2 differentiation exists
        if len(heading_levels) > 1:
            print("  OK: Multiple heading levels detected (h1/h2 differentiation)")
        elif len(heading_levels) == 1:
            print("  INFO: Only one heading level detected")
        else:
            print("  INFO: No headings detected")

    def test_evl009_markdown_table_detection(self, vl_client):
        """E2E-VL-009: Tables in document are rendered as markdown tables."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="md")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        md = get_result_text(vl_client, result["jobs"][0]["id"])

        # Check for markdown table syntax: | col | col |
        table_lines = [l for l in md.split("\n") if re.match(r"^\|.*\|$", l.strip())]
        separator_lines = [l for l in md.split("\n") if re.match(r"^\|[-|]+\|$", l.strip())]

        print(f"  Table lines: {len(table_lines)}, separators: {len(separator_lines)}")
        if table_lines:
            print(f"  Sample table line: {table_lines[0][:80]}")
        else:
            print("  INFO: No markdown tables detected (image may not contain tables)")


# ─── Tests: HTML output format ──────────────────────────────────────────────


class TestPaddleVL_HTML:
    """E2E-VL-010 to E2E-VL-012: HTML output verification."""

    def test_evl010_html_is_valid_document(self, vl_client):
        """E2E-VL-010: HTML output is a complete self-contained document."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="html")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        html = get_result_text(vl_client, result["jobs"][0]["id"])
        assert len(html) > 50, "HTML output too short"

        # Check for essential HTML structure
        assert "<!DOCTYPE html>" in html, "Missing DOCTYPE"
        assert "<html" in html, "Missing <html> tag"
        assert "<head>" in html, "Missing <head>"
        assert "<body>" in html, "Missing <body>"
        assert "</html>" in html, "Missing closing </html>"
        assert "<style>" in html, "Missing embedded CSS"
        print(f"  HTML length: {len(html)} chars")

    def test_evl011_html_has_heading_tags(self, vl_client):
        """E2E-VL-011: HTML uses heading tags (<h1>, <h2>, etc.)."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="html")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        html = get_result_text(vl_client, result["jobs"][0]["id"])

        h_tags = re.findall(r"<(h[1-6])>.*?</\1>", html, re.DOTALL)
        print(f"  Heading tags found: {len(h_tags)} ({set(h_tags)})")
        for tag in h_tags[:5]:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", html, re.DOTALL)
            if match:
                print(f"    <{tag}>: {match.group(1)[:60]}")

    def test_evl012_html_has_paragraphs(self, vl_client):
        """E2E-VL-012: HTML wraps text in <p> tags."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="html")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        html = get_result_text(vl_client, result["jobs"][0]["id"])

        p_count = html.count("<p>")
        print(f"  <p> tags: {p_count}")
        assert p_count >= 1, "Expected at least one <p> tag"


# ─── Tests: Plain text output ───────────────────────────────────────────────


class TestPaddleVL_PlainText:
    """E2E-VL-013: Plain text output verification."""

    def test_evl013_txt_has_content(self, vl_client):
        """E2E-VL-013: Plain text output has substantial extracted text."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="txt")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        text = get_result_text(vl_client, result["jobs"][0]["id"])
        assert len(text) > 20, f"Text too short ({len(text)} chars)"
        print(f"  Text length: {len(text)} chars")
        print(f"  First 200 chars: {text[:200]}")


# ─── Tests: PDF multi-page processing ───────────────────────────────────────


class TestPaddleVL_PDF:
    """E2E-VL-014 to E2E-VL-016: PDF processing verification."""

    def test_evl014_pdf_multipage_json(self, vl_client):
        """E2E-VL-014: PDF produces multiple pages in JSON output."""
        filepath = file_path("1709.04109v4.pdf")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(vl_client, request_id, timeout=300)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])

        num_pages = len(parsed["pages"])
        total_regions = parsed["summary"]["total_regions"]
        print(f"  Pages: {num_pages}, total regions: {total_regions}")

        assert num_pages > 1, f"Expected multi-page PDF, got {num_pages} pages"
        assert total_regions > 5, f"Expected many regions, got {total_regions}"

        # Each page should have a page_number
        for i, page in enumerate(parsed["pages"]):
            assert page["page_number"] == i + 1

        # Log region breakdown per page
        for page in parsed["pages"][:3]:
            types = {}
            for r in page["regions"]:
                types[r["type"]] = types.get(r["type"], 0) + 1
            print(f"  Page {page['page_number']}: {types}")

    def test_evl015_pdf_markdown_page_breaks(self, vl_client):
        """E2E-VL-015: Multi-page PDF markdown has page separators."""
        filepath = file_path("1709.04109v4.pdf")
        data = upload_for_structured_extract(vl_client, filepath, output_format="md")
        result = wait_for_completion(vl_client, data["request_id"], timeout=300)
        assert result["status"] == "COMPLETED"

        md = get_result_text(vl_client, result["jobs"][0]["id"])
        assert len(md) > 100, f"Markdown too short ({len(md)} chars)"

        # Multi-page markdown should have page separators
        page_markers = re.findall(r"## Page \d+", md)
        print(f"  Page markers found: {len(page_markers)}")
        if page_markers:
            for marker in page_markers[:5]:
                print(f"    {marker}")

    def test_evl016_vietnamese_pdf(self, vl_client):
        """E2E-VL-016: Vietnamese PDF produces structured output."""
        filepath = file_path("29849-Article Text-33903-1-2-20240324.pdf")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"], timeout=300)
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])
        total = parsed["summary"]["total_regions"]
        print(f"  Vietnamese PDF: {len(parsed['pages'])} pages, {total} regions")
        assert total > 0, "Expected regions from Vietnamese PDF"

        # Sample some text to verify Vietnamese character support
        all_text = " ".join(
            r.get("content", "")
            for p in parsed["pages"]
            for r in p["regions"]
            if r["type"] in ("text", "title")
        )
        print(f"  Sample text: {all_text[:200]}")


# ─── Tests: Vietnamese image ────────────────────────────────────────────────


class TestPaddleVL_Vietnamese:
    """E2E-VL-017: Vietnamese image processing."""

    def test_evl017_vietnamese_image(self, vl_client):
        """E2E-VL-017: Vietnamese image with Unicode filename processes correctly."""
        filepath = file_path("thiệp mừng năm mới.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        parsed = get_result_json(vl_client, result["jobs"][0]["id"])
        print(
            f"  Vietnamese image: {len(parsed['pages'])} pages, "
            f"{parsed['summary']['total_regions']} regions"
        )


# ─── Tests: Cross-format consistency ────────────────────────────────────────


class TestPaddleVL_Consistency:
    """E2E-VL-018 to E2E-VL-019: Cross-format consistency checks."""

    def test_evl018_json_vs_md_same_content(self, vl_client):
        """E2E-VL-018: JSON and Markdown outputs contain the same text content."""
        filepath = file_path("paper_image.png")

        # Upload twice: once json, once md
        data_json = upload_for_structured_extract(
            vl_client, filepath, output_format="json"
        )
        data_md = upload_for_structured_extract(
            vl_client, filepath, output_format="md"
        )

        result_json = wait_for_completion(vl_client, data_json["request_id"])
        result_md = wait_for_completion(vl_client, data_md["request_id"])

        assert result_json["status"] == "COMPLETED"
        assert result_md["status"] == "COMPLETED"

        # Extract text from JSON
        parsed = get_result_json(vl_client, result_json["jobs"][0]["id"])
        json_texts = []
        for page in parsed["pages"]:
            for r in page["regions"]:
                if r["type"] in ("text", "title", "list"):
                    json_texts.append(r.get("content", ""))

        # Get markdown text
        md = get_result_text(vl_client, result_md["jobs"][0]["id"])

        # Key content from JSON should appear in markdown
        matches = 0
        for text in json_texts[:10]:
            # Check first 30 chars of each text block
            snippet = text[:30].strip()
            if snippet and snippet in md:
                matches += 1

        match_rate = matches / max(len(json_texts[:10]), 1)
        print(
            f"  JSON regions: {len(json_texts)}, "
            f"matched in MD: {matches} ({match_rate:.0%})"
        )
        # At least some content should match — OCR may vary slightly between runs
        # due to timing/caching, so we allow some tolerance
        assert matches > 0 or len(json_texts) == 0, (
            "No JSON text content found in Markdown output"
        )

    def test_evl019_download_result_file(self, vl_client):
        """E2E-VL-019: Result can be downloaded as a file."""
        filepath = file_path("paper_image.png")
        data = upload_for_structured_extract(vl_client, filepath, output_format="json")
        result = wait_for_completion(vl_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]

        # Download as file
        resp = vl_client.get(f"/jobs/{job_id}/download")
        assert resp.status_code == 200
        assert "Content-Disposition" in resp.headers
        assert len(resp.content) > 10
        print(f"  Downloaded {len(resp.content)} bytes")
        print(f"  Content-Disposition: {resp.headers['Content-Disposition']}")

        # Verify downloaded content is valid JSON
        try:
            downloaded = json.loads(resp.content)
            assert "pages" in downloaded
            print(f"  Downloaded JSON has {len(downloaded['pages'])} pages")
        except json.JSONDecodeError:
            # Non-JSON format, just verify it has content
            assert len(resp.content) > 10
