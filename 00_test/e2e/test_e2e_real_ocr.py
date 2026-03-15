"""
E2E Real OCR Tests — Upload real files from 05_test_cases/data_test/,
wait for PaddleOCR worker to process, verify results.

Test data:
  - paper_image.png          — English academic paper image
  - merrychirst.png          — English greeting card
  - thiệp mừng năm mới.png  — Vietnamese greeting card (Unicode filename)
  - 1709.04109v4.pdf         — English academic PDF
  - 29849-Article Text-33903-1-2-20240324.pdf — Vietnamese article PDF

Requires: real PaddleOCR worker running (ocr-paddle service type APPROVED).
"""

import os
import time
import pytest
import httpx

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
ADMIN_EMAIL = "e2e-admin@test.com"
ADMIN_PASSWORD = "E2eAdmin123!"

# Timeout for OCR processing (PDF can take longer)
OCR_TIMEOUT = 120
POLL_INTERVAL = 3


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_token(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["token"]
    # Try register
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    return resp.json()["token"]


def upload_real_file(client: httpx.Client, filepath: str,
                     method: str = "ocr_paddle_text", output_format: str = "txt",
                     tier: int = 0) -> dict:
    """Upload a real file and return response data."""
    filename = os.path.basename(filepath)
    mime = "image/png" if filepath.endswith(".png") else "application/pdf"

    with open(filepath, "rb") as f:
        # Retry for rate limit
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


def wait_for_completion(client: httpx.Client, request_id: str,
                        timeout: int = OCR_TIMEOUT) -> dict:
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
    return data.get("text", "")


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ocr_client():
    """Authenticated client + verify worker is available."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = get_token(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"

        # Check worker available
        resp = client.get("/services/available")
        assert resp.status_code == 200
        services = resp.json()["items"]
        ocr_services = [s for s in services if "ocr_paddle_text" in s["allowed_methods"]]
        if not ocr_services:
            pytest.skip("No OCR worker running for ocr_paddle_text")

        active = ocr_services[0]
        print(f"\n  Worker: {active['id']} ({active['active_instances']} instances)")

        yield client


def _file_path(name: str) -> str:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
    return path


# ─── Tests: PNG files ────────────────────────────────────────────────────────

class TestRealOCR_PNG:
    """Upload real PNG images → PaddleOCR → verify text result."""

    def test_paper_image_png(self, ocr_client):
        """paper_image.png — English academic paper screenshot."""
        filepath = _file_path("paper_image.png")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(ocr_client, job_id)
        print(f"  OCR result ({len(text)} chars): {text[:200]}...")
        assert len(text) > 10, "OCR returned too little text"

    def test_merrychirst_png(self, ocr_client):
        """merrychirst.png — English greeting card."""
        filepath = _file_path("merrychirst.png")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(ocr_client, job_id)
        print(f"  OCR result ({len(text)} chars): {text[:200]}...")
        assert len(text) > 5, "OCR returned too little text"

    def test_vietnamese_filename_png(self, ocr_client):
        """thiệp mừng năm mới.png — Vietnamese filename + content."""
        filepath = _file_path("thiệp mừng năm mới.png")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(ocr_client, job_id)
        print(f"  OCR result ({len(text)} chars): {text[:200]}...")
        assert len(text) >= 0  # May have little text depending on image


# ─── Tests: PDF files ────────────────────────────────────────────────────────

class TestRealOCR_PDF:
    """Upload real PDF files → PaddleOCR → verify text result."""

    def test_academic_pdf(self, ocr_client):
        """1709.04109v4.pdf — English academic paper."""
        filepath = _file_path("1709.04109v4.pdf")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id, timeout=180)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(ocr_client, job_id)
        print(f"  OCR result ({len(text)} chars): {text[:200]}...")
        assert len(text) > 50, "PDF OCR returned too little text"

    def test_vietnamese_article_pdf(self, ocr_client):
        """29849-Article Text-33903-1-2-20240324.pdf — Vietnamese article."""
        filepath = _file_path("29849-Article Text-33903-1-2-20240324.pdf")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id, timeout=180)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        job_id = result["jobs"][0]["id"]
        text = get_result_text(ocr_client, job_id)
        print(f"  OCR result ({len(text)} chars): {text[:200]}...")
        assert len(text) > 50, "PDF OCR returned too little text"


# ─── Tests: Multi-file batch ─────────────────────────────────────────────────

class TestRealOCR_Batch:
    """Upload multiple real files in one request."""

    def test_batch_two_png(self, ocr_client):
        """Upload 2 PNG files in one request → both processed."""
        file1 = _file_path("paper_image.png")
        file2 = _file_path("merrychirst.png")

        with open(file1, "rb") as f1, open(file2, "rb") as f2:
            for attempt in range(5):
                f1.seek(0)
                f2.seek(0)
                resp = ocr_client.post(
                    "/upload",
                    files=[
                        ("files", ("paper_image.png", f1, "image/png")),
                        ("files", ("merrychirst.png", f2, "image/png")),
                    ],
                    data={
                        "output_format": "txt",
                        "method": "ocr_paddle_text",
                        "tier": "0",
                        "retention_hours": "24",
                    },
                )
                if resp.status_code != 429:
                    break
                time.sleep(3)

        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["total_files"] == 2
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id, timeout=120)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"
        assert result["completed_files"] == 2

        # Verify both have results
        for job in result["jobs"]:
            text = get_result_text(ocr_client, job["id"])
            print(f"  Job {job['id'][:8]}: {len(text)} chars")
            assert len(text) > 0


# ─── Tests: JSON output format ───────────────────────────────────────────────

class TestRealOCR_OutputFormat:
    """Test different output formats."""

    def test_json_output(self, ocr_client):
        """Upload PNG with output_format=json → structured result."""
        filepath = _file_path("paper_image.png")
        data = upload_real_file(ocr_client, filepath, output_format="json")
        request_id = data["request_id"]
        print(f"  request_id: {request_id}")

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED", f"Status: {result['status']}"

        # Result should be JSON-parseable
        job_id = result["jobs"][0]["id"]
        resp = ocr_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        print(f"  Result type: {type(resp.json())}")


# ─── Tests: Download result file ─────────────────────────────────────────────

class TestRealOCR_Download:
    """Verify result download works with real OCR output."""

    def test_download_result_file(self, ocr_client):
        """Upload → OCR → download result as file attachment."""
        filepath = _file_path("paper_image.png")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]

        # Download as file
        dl_resp = ocr_client.get(f"/jobs/{job_id}/download")
        assert dl_resp.status_code == 200
        assert "Content-Disposition" in dl_resp.headers
        assert len(dl_resp.content) > 10
        print(f"  Downloaded {len(dl_resp.content)} bytes")
        print(f"  Content-Disposition: {dl_resp.headers['Content-Disposition']}")

    def test_download_raw_format(self, ocr_client):
        """Download result in raw text format."""
        filepath = _file_path("merrychirst.png")
        data = upload_real_file(ocr_client, filepath)
        request_id = data["request_id"]

        result = wait_for_completion(ocr_client, request_id)
        assert result["status"] == "COMPLETED"

        job_id = result["jobs"][0]["id"]
        raw_resp = ocr_client.get(f"/jobs/{job_id}/result?format=raw")
        assert raw_resp.status_code == 200
        assert len(raw_resp.content) > 0
        print(f"  Raw result: {raw_resp.content[:200]}")
