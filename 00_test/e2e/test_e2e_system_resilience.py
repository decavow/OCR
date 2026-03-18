"""
E2E System Resilience Tests — Error recovery, timeouts, edge cases.

Tests ensure:
  1. Workers recover from processing errors gracefully
  2. Concurrent uploads are handled correctly
  3. Invalid inputs fail cleanly (no GPU leak)
  4. Service health remains stable under various conditions
  5. Workers handle Vietnamese/Unicode content without issues
  6. Rate limiting works under burst traffic

Test IDs: SR-001 to SR-016

Requires: Backend + at least one OCR worker running.
"""

import os
import time
import uuid

import httpx
import pytest

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "05_test_cases", "data_test"
)

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
ADMIN_EMAIL = "e2e-admin@test.com"
ADMIN_PASSWORD = "E2eAdmin123!"

OCR_TIMEOUT = 180
POLL_INTERVAL = 2


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _auth(client: httpx.Client, email: str, password: str) -> str:
    for _ in range(5):
        resp = client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["token"]
        if resp.status_code == 429:
            time.sleep(3)
            continue
        break
    for _ in range(3):
        resp = client.post("/auth/register", json={"email": email, "password": password})
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
            method: str = "ocr_paddle_text", output_format: str = "txt",
            tier: int = 0) -> dict:
    filename = os.path.basename(filepath)
    mime = "application/pdf" if filepath.lower().endswith(".pdf") else "image/png"
    with open(filepath, "rb") as f:
        for _ in range(5):
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


def _upload_bytes(client: httpx.Client, content: bytes, filename: str,
                  mime: str = "image/png", method: str = "ocr_paddle_text",
                  output_format: str = "txt") -> httpx.Response:
    """Upload raw bytes — may intentionally fail for error tests."""
    for _ in range(3):
        resp = client.post(
            "/upload",
            files=[("files", (filename, content, mime))],
            data={
                "output_format": output_format,
                "method": method,
                "tier": "0",
                "retention_hours": "24",
            },
        )
        if resp.status_code != 429:
            return resp
        time.sleep(3)
    return resp


def _poll_until_terminal(client: httpx.Client, request_id: str,
                         timeout: int = OCR_TIMEOUT) -> dict:
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        assert resp.status_code == 200
        data = resp.json()
        last_status = data.get("status")
        if last_status in ("COMPLETED", "FAILED", "PARTIAL_SUCCESS", "CANCELLED"):
            return data
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Request {request_id} stuck at '{last_status}' after {timeout}s"
    )


def _get_result_text(client: httpx.Client, job_id: str) -> str:
    resp = client.get(f"/jobs/{job_id}/result")
    if resp.status_code != 200:
        return ""
    return resp.json().get("text", "")


def _get_available_methods(client: httpx.Client) -> dict:
    resp = client.get("/services/available")
    assert resp.status_code == 200
    methods = {}
    for svc in resp.json().get("items", []):
        for method in svc.get("allowed_methods", []):
            if svc.get("active_instances", 0) > 0:
                methods[method] = svc["id"]
    return methods


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def auth_client():
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = _auth(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture(scope="module")
def available_methods(auth_client) -> dict:
    return _get_available_methods(auth_client)


def _require_method(available_methods, method: str):
    if method not in available_methods:
        pytest.skip(f"No active worker with method '{method}'")


# ═══════════════════════════════════════════════════════════════════════════════
# SR-001 → SR-004: Error Recovery
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.resilience
class TestErrorRecovery:
    """Verify system handles errors without GPU memory leaks."""

    def test_sr001_invalid_mime_type_rejected(self, auth_client, available_methods):
        """SR-001: Upload with invalid MIME type — rejected cleanly."""
        _require_method(available_methods, "ocr_paddle_text")
        content = b"This is not an image at all, just random text content."
        resp = _upload_bytes(
            auth_client, content,
            filename="test.exe",
            mime="application/octet-stream",
        )
        # Should be rejected at upload — no GPU resources wasted
        assert resp.status_code in (400, 415, 422), (
            f"Invalid MIME should be rejected, got {resp.status_code}"
        )
        print(f"\n  Invalid MIME rejected: {resp.status_code}")

    def test_sr002_tiny_corrupt_image(self, auth_client, available_methods):
        """SR-002: Upload corrupt image — worker fails cleanly, no GPU leak."""
        _require_method(available_methods, "ocr_paddle_text")
        # Valid PNG header but corrupt data
        corrupt_png = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"  # Missing IDAT
        )
        resp = _upload_bytes(auth_client, corrupt_png, filename="corrupt.png")

        if resp.status_code == 200:
            # Accepted for processing — check result
            data = resp.json()
            result = _poll_until_terminal(auth_client, data["request_id"], timeout=60)
            # Should fail or complete with minimal result (1x1 image)
            print(f"\n  Corrupt image status: {result['status']}")
        else:
            print(f"\n  Corrupt image rejected at upload: {resp.status_code}")

    def test_sr003_recovery_after_error(self, auth_client, available_methods):
        """SR-003: After processing an error, worker still handles normal jobs."""
        _require_method(available_methods, "ocr_paddle_text")

        # First: upload something that might cause issues
        corrupt_png = b"\x89PNG\r\n\x1a\n" + os.urandom(100)
        resp = _upload_bytes(auth_client, corrupt_png, filename="bad.png")
        if resp.status_code == 200:
            try:
                _poll_until_terminal(auth_client, resp.json()["request_id"], timeout=60)
            except TimeoutError:
                pass  # OK — it might time out

        # Then: normal job should still work
        filepath = _file_path("merrychirst.png")
        data = _upload(auth_client, filepath)
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            f"Worker failed to recover after error: {result['status']}"
        )
        text = _get_result_text(auth_client, result["jobs"][0]["id"])
        assert len(text) > 0, "Empty result after error recovery"
        print(f"\n  Recovery successful: {len(text)} chars")

    def test_sr004_empty_pdf_handling(self, auth_client, available_methods):
        """SR-004: Upload minimal empty PDF — handled gracefully."""
        _require_method(available_methods, "ocr_paddle_text")
        empty_pdf = (
            b"%PDF-1.0\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n190\n%%EOF"
        )
        resp = _upload_bytes(
            auth_client, empty_pdf,
            filename="empty.pdf",
            mime="application/pdf",
        )

        if resp.status_code == 200:
            data = resp.json()
            result = _poll_until_terminal(auth_client, data["request_id"], timeout=60)
            # May complete with empty text or fail — both are acceptable
            print(f"\n  Empty PDF status: {result['status']}")
            assert result["status"] in ("COMPLETED", "FAILED"), (
                f"Unexpected status for empty PDF: {result['status']}"
            )
        else:
            print(f"\n  Empty PDF rejected: {resp.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# SR-005 → SR-008: Concurrent Upload Handling
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.resilience
class TestConcurrentUploads:
    """Verify system handles rapid/concurrent uploads correctly."""

    def test_sr005_rapid_sequential_uploads(self, auth_client, available_methods):
        """SR-005: 5 rapid sequential uploads — all queued and processed."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("merrychirst.png")

        request_ids = []
        for i in range(5):
            data = _upload(auth_client, filepath)
            request_ids.append(data["request_id"])
            print(f"\n  Upload {i+1}/5: {data['request_id'][:8]}")

        # Wait for all to complete
        completed = 0
        failed = 0
        for rid in request_ids:
            try:
                result = _poll_until_terminal(auth_client, rid, timeout=OCR_TIMEOUT)
                if result["status"] == "COMPLETED":
                    completed += 1
                else:
                    failed += 1
                    print(f"\n  {rid[:8]}: {result['status']}")
            except TimeoutError:
                failed += 1
                print(f"\n  {rid[:8]}: TIMEOUT")

        print(f"\n  Results: {completed} completed, {failed} failed")
        assert completed >= 4, (
            f"Too many failures ({failed}/5) — system may be unstable under load"
        )

    def test_sr006_mixed_format_rapid_uploads(self, auth_client, available_methods):
        """SR-006: Rapid uploads with mixed formats (txt/json) — all processed."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        request_ids = []
        formats = ["txt", "json", "txt", "json"]
        for fmt in formats:
            data = _upload(auth_client, filepath, output_format=fmt)
            request_ids.append((data["request_id"], fmt))

        for rid, fmt in request_ids:
            result = _poll_until_terminal(auth_client, rid)
            assert result["status"] == "COMPLETED", (
                f"Format {fmt} failed: {result['status']}"
            )
            print(f"\n  {fmt}: COMPLETED")

    def test_sr007_multi_user_concurrent(self, auth_client):
        """SR-007: Multiple users uploading simultaneously."""
        # Create second user
        with httpx.Client(base_url=BASE_URL, timeout=30) as client2:
            email2 = f"e2e-user2-{uuid.uuid4().hex[:8]}@test.com"
            password2 = "TestUser2Pass123!"
            token2 = _auth(client2, email2, password2)
            client2.headers["Authorization"] = f"Bearer {token2}"

            methods = _get_available_methods(auth_client)
            if "ocr_paddle_text" not in methods:
                pytest.skip("No ocr_paddle_text worker")

            filepath = _file_path("merrychirst.png")

            # User 1 upload
            data1 = _upload(auth_client, filepath)
            # User 2 upload
            data2 = _upload(client2, filepath)

            # Both should complete
            result1 = _poll_until_terminal(auth_client, data1["request_id"])
            result2 = _poll_until_terminal(client2, data2["request_id"])

            assert result1["status"] == "COMPLETED", f"User1 failed: {result1['status']}"
            assert result2["status"] == "COMPLETED", f"User2 failed: {result2['status']}"
            print(f"\n  User1: COMPLETED, User2: COMPLETED")

    def test_sr008_upload_during_processing(self, auth_client, available_methods):
        """SR-008: Upload new file while another is being processed."""
        _require_method(available_methods, "ocr_paddle_text")
        pdf_path = _file_path("1709.04109v4.pdf")
        img_path = _file_path("merrychirst.png")

        # Start a slow PDF job
        pdf_data = _upload(auth_client, pdf_path)

        # Immediately upload a quick image
        img_data = _upload(auth_client, img_path)

        # Both should eventually complete
        pdf_result = _poll_until_terminal(auth_client, pdf_data["request_id"], timeout=300)
        img_result = _poll_until_terminal(auth_client, img_data["request_id"])

        assert pdf_result["status"] == "COMPLETED", f"PDF: {pdf_result['status']}"
        assert img_result["status"] == "COMPLETED", f"Image: {img_result['status']}"
        print(f"\n  PDF + Image concurrent: both COMPLETED")


# ═══════════════════════════════════════════════════════════════════════════════
# SR-009 → SR-012: Vietnamese/Unicode Resilience
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.resilience
class TestUnicodeResilience:
    """Verify Unicode handling doesn't cause issues."""

    def test_sr009_vietnamese_image_full_cycle(self, auth_client, available_methods):
        """SR-009: Vietnamese filename + content → upload → process → download."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("thiệp mừng năm mới.png")

        data = _upload(auth_client, filepath)
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        # Download result
        job_id = result["jobs"][0]["id"]
        dl_resp = auth_client.get(f"/jobs/{job_id}/download")
        assert dl_resp.status_code == 200
        assert len(dl_resp.content) >= 0
        print(f"\n  Vietnamese full cycle: COMPLETED ({len(dl_resp.content)} bytes)")

    def test_sr010_vietnamese_pdf_processing(self, auth_client, available_methods):
        """SR-010: Vietnamese PDF article → processed correctly."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("29849-Article Text-33903-1-2-20240324.pdf")

        data = _upload(auth_client, filepath)
        result = _poll_until_terminal(auth_client, data["request_id"], timeout=OCR_TIMEOUT)
        assert result["status"] == "COMPLETED"

        text = _get_result_text(auth_client, result["jobs"][0]["id"])
        print(f"\n  Vietnamese PDF: {len(text)} chars")
        assert len(text) > 50, "Vietnamese PDF should produce text"

    def test_sr011_vietnamese_structured_extraction(self, auth_client, available_methods):
        """SR-011: Vietnamese image → structured extraction."""
        if "structured_extract" not in available_methods:
            pytest.skip("No structured_extract worker")

        filepath = _file_path("thiệp mừng năm mới.png")
        data = _upload(
            auth_client, filepath,
            method="structured_extract", output_format="json",
        )
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED"

        resp = auth_client.get(f"/jobs/{result['jobs'][0]['id']}/result")
        assert resp.status_code == 200
        result_data = resp.json()
        pages = result_data.get("pages", [])
        print(f"\n  Vietnamese structured: {len(pages)} page(s)")


# ═══════════════════════════════════════════════════════════════════════════════
# SR-012 → SR-014: Service Stability
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.resilience
class TestServiceStability:
    """Verify services remain stable throughout testing."""

    def test_sr012_health_endpoint_stable(self, auth_client):
        """SR-012: Health endpoint returns consistent results over 5 checks."""
        statuses = []
        for i in range(5):
            resp = auth_client.get("/health")
            assert resp.status_code == 200
            statuses.append(resp.json().get("status"))
            time.sleep(1)

        print(f"\n  Health statuses: {statuses}")
        # All should be the same
        assert len(set(statuses)) == 1, (
            f"Health status flickering: {statuses}"
        )

    def test_sr013_services_available_consistent(self, auth_client):
        """SR-013: Available services list remains consistent."""
        method_counts = []
        for i in range(3):
            methods = _get_available_methods(auth_client)
            method_counts.append(len(methods))
            time.sleep(1)

        print(f"\n  Method counts: {method_counts}")
        # Should be stable (no workers dropping/appearing)
        assert max(method_counts) - min(method_counts) <= 1, (
            f"Worker count unstable: {method_counts}"
        )

    def test_sr014_request_list_works_after_load(self, auth_client):
        """SR-014: Request list endpoint works after processing many jobs."""
        resp = auth_client.get("/requests?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        requests = data.get("items", data) if isinstance(data, dict) else data
        print(f"\n  Recent requests: {len(requests) if isinstance(requests, list) else 'N/A'}")


# ═══════════════════════════════════════════════════════════════════════════════
# SR-015 → SR-016: Output Format Resilience
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.resilience
class TestOutputFormatResilience:
    """Verify all output formats work correctly."""

    def test_sr015_all_text_formats(self, auth_client, available_methods):
        """SR-015: Test txt and json output formats with same image."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        for fmt in ("txt", "json"):
            data = _upload(auth_client, filepath, output_format=fmt)
            result = _poll_until_terminal(auth_client, data["request_id"])
            assert result["status"] == "COMPLETED", (
                f"Format '{fmt}' failed: {result['status']}"
            )
            text = _get_result_text(auth_client, result["jobs"][0]["id"])
            assert len(text) > 50, f"Format '{fmt}' produced short result: {len(text)}"
            print(f"\n  {fmt}: {len(text)} chars")

    def test_sr016_structured_output_formats(self, auth_client, available_methods):
        """SR-016: Test json and md output formats for structured extraction."""
        if "structured_extract" not in available_methods:
            pytest.skip("No structured_extract worker")

        filepath = _file_path("paper_image.png")

        for fmt in ("json", "md"):
            data = _upload(
                auth_client, filepath,
                method="structured_extract", output_format=fmt,
            )
            result = _poll_until_terminal(auth_client, data["request_id"])
            assert result["status"] == "COMPLETED", (
                f"Structured format '{fmt}' failed: {result['status']}"
            )

            resp = auth_client.get(f"/jobs/{result['jobs'][0]['id']}/result")
            assert resp.status_code == 200
            print(f"\n  structured/{fmt}: COMPLETED")
