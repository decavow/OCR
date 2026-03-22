"""
E2E Integration Tests — Marker Worker (ocr_marker method)

Verifies the full pipeline with a REAL Marker worker:
  1. Service registration   → marker type APPROVED, instance ACTIVE
  2. Upload → NATS → Worker → Result for each output format (md, html, json)
  3. State transitions      → QUEUED → PROCESSING → COMPLETED
  4. Result content quality → structure preservation, confidence scoring
  5. Multi-format output    → md/html/json all produce valid output
  6. PDF + Image support    → both file types processed correctly
  7. Vietnamese text        → Vietnamese content preserved

Test IDs: MK-001 to MK-012

Requires:
  - Backend running at localhost:8080
  - NATS running at localhost:4222
  - MinIO running at localhost:9000
  - Marker worker running with OCR_ENGINE=marker
"""

import json
import os
import time

import httpx
import pytest

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
TEST_EMAIL = "marker-test@test.com"
TEST_PASSWORD = "MarkerTest123!"

OCR_TIMEOUT = 180  # Marker model loading can be slow first time
POLL_INTERVAL = 3


# ─── Helpers ────────────────────────────────────────────────────────────────


def _auth(client: httpx.Client) -> str:
    """Login or register, return token."""
    for _ in range(5):
        resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    for _ in range(3):
        resp = client.post("/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    raise AssertionError(f"Auth failed: {resp.status_code} {resp.text}")


def _file_path(name: str) -> str:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


def _upload(client: httpx.Client, filepath: str,
            output_format: str = "md", tier: int = 0) -> dict:
    """Upload file with method=ocr_marker."""
    filename = os.path.basename(filepath)
    mime = "application/pdf" if filepath.lower().endswith(".pdf") else "image/png"

    for attempt in range(3):
        with open(filepath, "rb") as f:
            resp = client.post(
                "/upload",
                files=[("files", (filename, f, mime))],
                data={
                    "output_format": output_format,
                    "method": "ocr_marker",
                    "tier": str(tier),
                    "retention_hours": "24",
                },
            )
        if resp.status_code != 429:
            break
        time.sleep(3)

    assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text}"
    return resp.json()


def _wait_completed(client: httpx.Client, request_id: str,
                    timeout: int = OCR_TIMEOUT) -> dict:
    """Poll until request reaches terminal state."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        assert resp.status_code == 200
        data = resp.json()
        last_status = data.get("status")
        if last_status in ("COMPLETED", "FAILED", "PARTIAL"):
            return data
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Request {request_id} stuck at '{last_status}' after {timeout}s"
    )


def _get_job_id(data: dict) -> str:
    """Extract first job_id from request response."""
    jobs = data.get("jobs", [])
    if jobs:
        return jobs[0].get("id", "")
    return ""


def _download_result(client: httpx.Client, request_id: str, job_id: str) -> bytes:
    """Download result file via job endpoint."""
    resp = client.get(f"/jobs/{job_id}/download")
    assert resp.status_code == 200, f"Download failed: {resp.status_code} {resp.text}"
    return resp.content


# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        token = _auth(c)
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ─── MK-001: Service Registration ──────────────────────────────────────────


class TestMarkerServiceRegistration:
    """MK-001 to MK-002: Marker worker registered and active."""

    def test_mk001_marker_service_type_exists(self, client):
        """MK-001: Backend has 'marker' service type seeded and APPROVED."""
        resp = client.get("/services/available")
        assert resp.status_code == 200
        body = resp.json()
        services = body.get("items", body) if isinstance(body, dict) else body

        marker_svc = None
        for svc in services:
            if svc.get("id") == "marker" or svc.get("service_type") == "marker":
                marker_svc = svc
                break

        assert marker_svc is not None, (
            f"Marker service not found in available services: "
            f"{[s.get('id', s.get('service_type')) for s in services]}"
        )
        assert "ocr_marker" in marker_svc.get("allowed_methods", [])

    def test_mk002_marker_worker_instance_active(self, client):
        """MK-002: At least one Marker worker instance is ACTIVE."""
        resp = client.get("/services/available")
        body = resp.json()
        services = body.get("items", body) if isinstance(body, dict) else body

        marker_svc = None
        for svc in services:
            if svc.get("id") == "marker" or svc.get("service_type") == "marker":
                marker_svc = svc
                break

        assert marker_svc is not None, "Marker service not found"
        active_count = marker_svc.get("active_instances", 0)
        assert active_count >= 1, (
            f"No active Marker worker instances (active_instances={active_count})"
        )


# ─── MK-003 to MK-006: Full OCR Pipeline ───────────────────────────────────


class TestMarkerOCRPipeline:
    """MK-003 to MK-006: Upload image → Marker OCR → Verify result."""

    def test_mk003_upload_accepted(self, client):
        """MK-003: Image upload with method=ocr_marker is accepted."""
        filepath = _file_path("paper_image.png")
        result = _upload(client, filepath, output_format="md")

        assert "request_id" in result
        assert result.get("total_files", 0) >= 1
        assert result.get("method") == "ocr_marker"

    def test_mk004_ocr_completes(self, client):
        """MK-004: Marker processes image and reaches COMPLETED."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="md")

        request_id = upload["request_id"]
        result = _wait_completed(client, request_id)

        assert result["status"] == "COMPLETED", (
            f"Expected COMPLETED, got {result['status']}"
        )

    def test_mk005_result_has_content(self, client):
        """MK-005: Marker result contains meaningful markdown text."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="md")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        assert job_id, "No file_id found in response"

        content = _download_result(client, request_id, job_id)
        text = content.decode("utf-8")
        assert len(text) > 100, f"Result too short: {len(text)} chars"

    def test_mk006_result_has_structure(self, client):
        """MK-006: Marker preserves document structure (headings or paragraphs)."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="json")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        parsed = json.loads(content)

        # Should have parsed blocks
        assert parsed["blocks_count"] > 0, "No blocks parsed from image"
        block_types = {b["type"] for b in parsed["blocks"]}
        assert len(block_types) >= 1, "Expected at least 1 block type"


# ─── MK-007 to MK-009: Multi-Format Output ─────────────────────────────────


class TestMarkerOutputFormats:
    """MK-007 to MK-009: Verify md, html, json output formats."""

    def test_mk007_html_output(self, client):
        """MK-007: HTML output contains valid HTML structure."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="html")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        html = content.decode("utf-8")

        assert "<!DOCTYPE html>" in html
        assert "<body>" in html
        assert len(html) > 200

    def test_mk008_json_output(self, client):
        """MK-008: JSON output has confidence and blocks structure."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="json")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        parsed = json.loads(content)

        assert "confidence" in parsed
        assert "blocks" in parsed
        assert "blocks_count" in parsed
        assert isinstance(parsed["blocks"], list)
        assert parsed["confidence"] > 0
        assert parsed["blocks_count"] == len(parsed["blocks"])

    def test_mk009_md_output(self, client):
        """MK-009: Markdown output is valid UTF-8 text."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="md")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        text = content.decode("utf-8")

        assert len(text) > 50, f"MD output too short: {len(text)} chars"


# ─── MK-010 to MK-011: Image + Vietnamese ──────────────────────────────────


class TestMarkerImageAndVietnamese:
    """MK-010 to MK-011: Image input and Vietnamese text."""

    def test_mk010_image_input_works(self, client):
        """MK-010: PNG image is processed successfully by Marker."""
        filepath = _file_path("merrychirst.png")
        upload = _upload(client, filepath, output_format="md")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        text = content.decode("utf-8")
        assert len(text) > 10

    def test_mk011_vietnamese_image(self, client):
        """MK-011: Vietnamese text image is processed correctly."""
        filepath = _file_path("thiệp mừng năm mới.png")
        upload = _upload(client, filepath, output_format="md")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        job_id = _get_job_id(data)
        content = _download_result(client, request_id, job_id)
        text = content.decode("utf-8")
        assert len(text) > 10


# ─── MK-012: Job Metadata ──────────────────────────────────────────────────


class TestMarkerJobMetadata:
    """MK-012: Job metadata includes correct engine info."""

    def test_mk012_job_has_engine_info(self, client):
        """MK-012: Completed job reports marker engine metadata."""
        filepath = _file_path("paper_image.png")
        upload = _upload(client, filepath, output_format="md")
        request_id = upload["request_id"]

        data = _wait_completed(client, request_id)
        assert data["status"] == "COMPLETED"

        jobs = data.get("jobs", [])
        assert len(jobs) >= 1

        job = jobs[0]
        # Job should have processing metadata
        assert job.get("status") == "COMPLETED"
        assert job.get("method") == "ocr_marker"
        assert job.get("processing_time_ms", 0) > 0
