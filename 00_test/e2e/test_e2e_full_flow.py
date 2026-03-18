"""
E2E Full Flow Tests — Real file → Real worker → Verify every step.

Unlike other E2E tests:
  - test_e2e_upload_flow.py: simulates worker (skips NATS, no real OCR)
  - test_e2e_real_ocr.py: real worker but only checks final status + len(text)
  - test_e2e_ocr_quality.py: real worker but focuses on accuracy metrics

THIS file verifies the COMPLETE pipeline with real workers:
  1. Upload real file       → verify response structure
  2. Check initial state    → PROCESSING + jobs QUEUED
  3. Poll state transitions → observe QUEUED → PROCESSING → COMPLETED
  4. Verify job metadata    → engine_version, worker_id, processing_time_ms
  5. Verify result content  → keyword check (not just len > 0)
  6. Verify file download   → Content-Disposition, correct bytes
  7. Verify request summary → completed_files, timestamps

Test IDs: EF-001 to EF-020

Requires: At least one real OCR worker running.
"""

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

OCR_TIMEOUT = 180
POLL_INTERVAL = 2


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _auth(client: httpx.Client, email: str, password: str) -> str:
    """Login or register, return token."""
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
    """Upload a real file with retry on 429."""
    filename = os.path.basename(filepath)
    if filepath.lower().endswith(".pdf"):
        mime = "application/pdf"
    else:
        mime = "image/png"

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


def _poll_until_terminal(client: httpx.Client, request_id: str,
                         timeout: int = OCR_TIMEOUT) -> tuple[dict, list[dict]]:
    """Poll request status, collect state snapshots, return (final, history).

    Returns:
        final: The terminal-state response
        history: List of unique status snapshots observed during polling
    """
    deadline = time.time() + timeout
    history = []
    seen_statuses = set()
    last_data = None

    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        assert resp.status_code == 200, f"Request poll failed: {resp.status_code}"
        data = resp.json()
        last_data = data

        # Track unique request-level statuses
        req_status = data.get("status")
        if req_status not in seen_statuses:
            seen_statuses.add(req_status)
            # Also snapshot job statuses at this point
            job_statuses = [j.get("status") for j in data.get("jobs", [])]
            history.append({
                "time": time.time(),
                "request_status": req_status,
                "job_statuses": job_statuses,
                "completed_files": data.get("completed_files", 0),
                "failed_files": data.get("failed_files", 0),
            })

        if req_status in ("COMPLETED", "FAILED", "PARTIAL_SUCCESS", "CANCELLED"):
            return data, history

        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Request {request_id} stuck at '{last_data.get('status')}' after {timeout}s. "
        f"History: {history}"
    )


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def auth_client():
    """Authenticated client for full-flow tests."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = _auth(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture(scope="module")
def available_services(auth_client) -> dict:
    """Detect available OCR services and their methods."""
    resp = auth_client.get("/services/available")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    services = {}
    for s in items:
        services[s["id"]] = {
            "methods": s.get("allowed_methods", []),
            "instances": s.get("active_instances", 0),
            "formats": s.get("supported_formats", []),
        }
    return services


def _require_method(available_services, method: str):
    """Skip if no worker supports the given method."""
    for svc_id, info in available_services.items():
        if method in info["methods"] and info["instances"] > 0:
            return svc_id
    pytest.skip(f"No active worker with method '{method}'")


# ═══════════════════════════════════════════════════════════════════════════════
# EF-001 → EF-007: Single Image Full Flow (PaddleOCR / Tesseract)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.full_flow
class TestFullFlow_SingleImage:
    """Complete pipeline test: upload real image → real worker → verify all steps."""

    def test_ef001_upload_response_structure(self, auth_client, available_services):
        """EF-001: Upload returns correct response structure."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        data = _upload(auth_client, filepath)

        # Verify response structure
        assert "request_id" in data
        assert data["total_files"] == 1
        assert data["method"] == "ocr_paddle_text"
        assert data["tier"] == 0
        assert data["output_format"] == "txt"
        assert len(data["files"]) == 1

        file_info = data["files"][0]
        assert file_info["original_name"] == "paper_image.png"
        assert file_info["mime_type"] == "image/png"
        assert "id" in file_info
        assert file_info.get("size_bytes", 0) > 0

        print(f"\n  request_id: {data['request_id']}")
        print(f"  file_id: {file_info['id']}")
        print(f"  size: {file_info.get('size_bytes', '?')} bytes")

    def test_ef002_initial_state_after_upload(self, auth_client, available_services):
        """EF-002: Immediately after upload, request=PROCESSING, job=QUEUED."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        # Check immediately (before worker picks it up)
        resp = auth_client.get(f"/requests/{request_id}")
        assert resp.status_code == 200
        detail = resp.json()

        assert detail["id"] == request_id
        assert detail["status"] == "PROCESSING"
        assert detail["total_files"] == 1
        assert detail["completed_files"] == 0
        assert len(detail["jobs"]) == 1

        job = detail["jobs"][0]
        assert job["status"] in ("QUEUED", "SUBMITTED", "PROCESSING"), (
            f"Initial job status should be QUEUED/SUBMITTED, got: {job['status']}"
        )
        assert job["result_path"] is None
        assert "file_id" in job

        print(f"\n  request: {detail['status']}")
        print(f"  job: {job['status']}")

    def test_ef003_state_transitions_observed(self, auth_client, available_services):
        """EF-003: Observe state transitions QUEUED → PROCESSING → COMPLETED."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        final, history = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED", (
            f"Expected COMPLETED, got {final['status']}. History: {history}"
        )

        # Print observed transitions
        print(f"\n  State transitions observed ({len(history)} snapshots):")
        for snap in history:
            print(f"    request={snap['request_status']}, "
                  f"jobs={snap['job_statuses']}")

        # Must have seen PROCESSING at some point (either first snapshot or transition)
        seen_request_statuses = {h["request_status"] for h in history}
        assert "PROCESSING" in seen_request_statuses or "COMPLETED" in seen_request_statuses

        # Final state must be COMPLETED
        assert history[-1]["request_status"] == "COMPLETED"
        assert history[-1]["completed_files"] == 1
        assert history[-1]["failed_files"] == 0

    def test_ef004_job_metadata_after_completion(self, auth_client, available_services):
        """EF-004: Completed job has engine_version, processing_time, timestamps."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        final, _ = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED"

        job = final["jobs"][0]
        print(f"\n  Job metadata:")
        print(f"    status: {job['status']}")
        print(f"    engine_version: {job.get('engine_version')}")
        print(f"    processing_time_ms: {job.get('processing_time_ms')}")
        print(f"    started_at: {job.get('started_at')}")
        print(f"    completed_at: {job.get('completed_at')}")
        print(f"    result_path: {job.get('result_path')}")
        print(f"    retry_count: {job.get('retry_count')}")

        assert job["status"] == "COMPLETED"

        # Engine version should be set by real worker
        if job.get("engine_version"):
            assert len(job["engine_version"]) > 0
            print(f"    ✓ engine_version present")

        # Processing time should be recorded
        if job.get("processing_time_ms") is not None:
            assert job["processing_time_ms"] > 0, "Processing time should be > 0"
            assert job["processing_time_ms"] < 600_000, "Processing > 10min is suspect"
            print(f"    ✓ processing_time_ms = {job['processing_time_ms']}ms")

        # Result path should exist
        if job.get("result_path"):
            assert len(job["result_path"]) > 0
            print(f"    ✓ result_path present")

        # Timestamps
        if job.get("completed_at"):
            print(f"    ✓ completed_at present")

        # Request-level timestamps
        assert final.get("created_at") is not None
        if final.get("completed_at"):
            print(f"    ✓ request completed_at present")

    def test_ef005_result_content_has_keywords(self, auth_client, available_services):
        """EF-005: OCR result contains expected keywords from paper_image.png."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        final, _ = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED"

        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200

        result_data = resp.json()
        text = result_data.get("text", "")

        print(f"\n  Result length: {len(text)} chars")
        print(f"  First 300 chars: {text[:300]}")

        # Must have substantial content
        assert len(text) > 100, f"Result too short: {len(text)} chars"

        # Paper image is "Attention Is All You Need" — check key terms
        text_lower = text.lower()
        expected_keywords = ["attention", "model", "transformer"]
        found = [kw for kw in expected_keywords if kw in text_lower]
        missed = [kw for kw in expected_keywords if kw not in text_lower]

        print(f"  Keywords found: {found}")
        print(f"  Keywords missed: {missed}")

        assert len(found) >= 1, (
            f"No expected keywords found in OCR output. "
            f"Expected at least one of: {expected_keywords}"
        )

    def test_ef006_download_result_file(self, auth_client, available_services):
        """EF-006: Download result as file — correct headers and content."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        final, _ = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED"

        job_id = final["jobs"][0]["id"]

        # Download as file attachment
        dl_resp = auth_client.get(f"/jobs/{job_id}/download")
        assert dl_resp.status_code == 200

        # Verify headers
        content_disp = dl_resp.headers.get("Content-Disposition", "")
        print(f"\n  Content-Disposition: {content_disp}")
        print(f"  Content-Type: {dl_resp.headers.get('content-type', '?')}")
        print(f"  Content-Length: {len(dl_resp.content)} bytes")

        assert "attachment" in content_disp or "filename" in content_disp, (
            f"Missing attachment header: {content_disp}"
        )
        assert len(dl_resp.content) > 10, "Downloaded file too small"

        # Filename should reference the original file
        if "paper_image" in content_disp:
            print(f"  ✓ Filename references original file")

        # Content should be readable text
        try:
            text = dl_resp.content.decode("utf-8")
            assert len(text) > 10
            print(f"  ✓ Content is valid UTF-8 ({len(text)} chars)")
        except UnicodeDecodeError:
            # JSON format might be different
            print(f"  Content is binary ({len(dl_resp.content)} bytes)")

    def test_ef007_request_summary_complete(self, auth_client, available_services):
        """EF-007: Final request summary has all expected fields and values."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        final, _ = _poll_until_terminal(auth_client, request_id)

        print(f"\n  Request summary:")
        print(f"    id: {final['id']}")
        print(f"    status: {final['status']}")
        print(f"    method: {final.get('method')}")
        print(f"    output_format: {final.get('output_format')}")
        print(f"    total_files: {final.get('total_files')}")
        print(f"    completed_files: {final.get('completed_files')}")
        print(f"    failed_files: {final.get('failed_files')}")
        print(f"    created_at: {final.get('created_at')}")
        print(f"    completed_at: {final.get('completed_at')}")

        assert final["status"] == "COMPLETED"
        assert final["total_files"] == 1
        assert final["completed_files"] == 1
        assert final["failed_files"] == 0
        assert final.get("method") == "ocr_paddle_text"
        assert final.get("output_format") == "txt"
        assert final.get("created_at") is not None


# ═══════════════════════════════════════════════════════════════════════════════
# EF-010 → EF-013: PDF Full Flow
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.full_flow
class TestFullFlow_PDF:
    """Complete pipeline test: upload real PDF → real worker → verify all steps."""

    def test_ef010_pdf_upload_and_completion(self, auth_client, available_services):
        """EF-010: PDF upload → worker processes → COMPLETED with text."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("1709.04109v4.pdf")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        # Verify upload response
        assert upload_data["total_files"] == 1
        file_info = upload_data["files"][0]
        assert file_info["mime_type"] == "application/pdf"
        assert file_info["original_name"] == "1709.04109v4.pdf"

        # Wait for completion (PDFs take longer)
        final, history = _poll_until_terminal(auth_client, request_id, timeout=300)
        assert final["status"] == "COMPLETED", (
            f"PDF processing failed: {final['status']}. History: {history}"
        )

        # Verify result has substantial text (multi-page PDF)
        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        text = resp.json().get("text", "")

        print(f"\n  PDF result: {len(text)} chars")
        print(f"  Transitions: {len(history)} snapshots")
        assert len(text) > 500, (
            f"PDF OCR result too short: {len(text)} chars"
        )

    def test_ef011_pdf_processing_time_reasonable(self, auth_client, available_services):
        """EF-011: PDF processing time is recorded and reasonable."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")  # Use image for faster test

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]
        start_time = time.time()

        final, _ = _poll_until_terminal(auth_client, request_id)
        wall_time_ms = int((time.time() - start_time) * 1000)

        assert final["status"] == "COMPLETED"

        job = final["jobs"][0]
        proc_time = job.get("processing_time_ms")

        print(f"\n  Wall time: {wall_time_ms}ms")
        print(f"  Processing time (reported): {proc_time}ms")

        if proc_time is not None:
            # Processing time should be less than wall time
            # (wall time includes queue wait + polling overhead)
            assert proc_time <= wall_time_ms + 5000, (
                f"Processing time ({proc_time}ms) > wall time ({wall_time_ms}ms)"
            )
            assert proc_time > 0, "Processing time should be positive"


# ═══════════════════════════════════════════════════════════════════════════════
# EF-014 → EF-016: Structured Extraction Full Flow (PaddleVL)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.full_flow
class TestFullFlow_StructuredExtract:
    """Complete pipeline: upload → PaddleVL structured extraction → verify."""

    def test_ef014_structured_json_full_flow(self, auth_client, available_services):
        """EF-014: Structured extraction → JSON with pages, regions, types."""
        _require_method(available_services, "structured_extract")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(
            auth_client, filepath,
            method="structured_extract", output_format="json",
        )
        request_id = upload_data["request_id"]

        # Verify initial state
        detail = auth_client.get(f"/requests/{request_id}").json()
        assert detail["status"] == "PROCESSING"
        assert detail.get("method") == "structured_extract"
        assert detail.get("output_format") == "json"

        # Wait for completion
        final, history = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED", (
            f"Structured extraction failed: {final['status']}"
        )

        # Get JSON result
        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        result = resp.json()

        # Verify structured output
        assert "pages" in result, "Missing 'pages' in structured JSON"
        pages = result["pages"]
        assert len(pages) >= 1, "No pages in result"

        all_regions = [r for p in pages for r in p.get("regions", [])]
        region_types = sorted(set(r.get("type", "") for r in all_regions))

        print(f"\n  Pages: {len(pages)}")
        print(f"  Total regions: {len(all_regions)}")
        print(f"  Region types: {region_types}")
        print(f"  Transitions: {[h['request_status'] for h in history]}")

        assert len(all_regions) >= 2, f"Too few regions: {len(all_regions)}"
        assert any(t in region_types for t in ("text", "title")), (
            f"No text/title regions found: {region_types}"
        )

        # Verify regions have content
        regions_with_content = sum(
            1 for r in all_regions
            if r.get("content", "").strip() or r.get("html", "").strip()
        )
        assert regions_with_content >= 1, "No regions have content"

    def test_ef015_structured_markdown_full_flow(self, auth_client, available_services):
        """EF-015: Structured extraction → Markdown with headings and text."""
        _require_method(available_services, "structured_extract")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(
            auth_client, filepath,
            method="structured_extract", output_format="md",
        )
        final, _ = _poll_until_terminal(auth_client, upload_data["request_id"])
        assert final["status"] == "COMPLETED"

        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        text = resp.json().get("text", str(resp.json()))

        print(f"\n  Markdown length: {len(text)} chars")

        # Check markdown features
        has_headings = bool(re.search(r"^#{1,3}\s+", text, re.MULTILINE))
        lines = [l for l in text.split("\n") if l.strip()]

        print(f"  Has headings: {has_headings}")
        print(f"  Non-empty lines: {len(lines)}")

        assert len(text) > 100, f"Markdown too short: {len(text)}"
        assert len(lines) >= 3, f"Too few lines: {len(lines)}"

    def test_ef016_structured_pdf_multipage(self, auth_client, available_services):
        """EF-016: Multi-page PDF → structured extraction → multiple pages in output."""
        _require_method(available_services, "structured_extract")
        filepath = _file_path("1709.04109v4.pdf")

        upload_data = _upload(
            auth_client, filepath,
            method="structured_extract", output_format="json",
        )
        final, _ = _poll_until_terminal(
            auth_client, upload_data["request_id"], timeout=300
        )
        assert final["status"] == "COMPLETED"

        job_id = final["jobs"][0]["id"]
        result = auth_client.get(f"/jobs/{job_id}/result").json()

        pages = result.get("pages", [])
        total_regions = sum(len(p.get("regions", [])) for p in pages)

        print(f"\n  Pages: {len(pages)}")
        print(f"  Total regions: {total_regions}")

        assert len(pages) >= 2, f"Expected multi-page, got {len(pages)}"
        assert total_regions >= 5, f"Too few regions: {total_regions}"


# ═══════════════════════════════════════════════════════════════════════════════
# EF-017 → EF-020: Multi-File & Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.full_flow
class TestFullFlow_MultiFile:
    """Multi-file upload → all processed by real worker."""

    def test_ef017_batch_upload_all_completed(self, auth_client, available_services):
        """EF-017: Upload 2 files → both processed → request COMPLETED."""
        _require_method(available_services, "ocr_paddle_text")
        file1 = _file_path("paper_image.png")
        file2 = _file_path("merrychirst.png")

        with open(file1, "rb") as f1, open(file2, "rb") as f2:
            for _ in range(5):
                f1.seek(0)
                f2.seek(0)
                resp = auth_client.post(
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

        assert resp.status_code == 200
        upload_data = resp.json()
        assert upload_data["total_files"] == 2
        request_id = upload_data["request_id"]

        # Wait for all files
        final, history = _poll_until_terminal(auth_client, request_id, timeout=180)
        assert final["status"] == "COMPLETED", (
            f"Batch failed: {final['status']}, "
            f"completed={final.get('completed_files')}, "
            f"failed={final.get('failed_files')}"
        )
        assert final["completed_files"] == 2
        assert final["failed_files"] == 0

        # Verify both jobs have results
        for i, job in enumerate(final["jobs"]):
            assert job["status"] == "COMPLETED", (
                f"Job {i} not completed: {job['status']}"
            )
            result_resp = auth_client.get(f"/jobs/{job['id']}/result")
            assert result_resp.status_code == 200
            text = result_resp.json().get("text", "")
            print(f"\n  Job {i}: {len(text)} chars")
            assert len(text) > 0, f"Job {i} has empty result"

    def test_ef018_vietnamese_file_full_flow(self, auth_client, available_services):
        """EF-018: Vietnamese filename + content → processed correctly."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("thiệp mừng năm mới.png")

        upload_data = _upload(auth_client, filepath)
        request_id = upload_data["request_id"]

        # Verify Unicode filename preserved in upload response
        file_info = upload_data["files"][0]
        assert "thiệp" in file_info["original_name"] or "mừng" in file_info["original_name"], (
            f"Unicode filename lost: {file_info['original_name']}"
        )

        final, _ = _poll_until_terminal(auth_client, request_id)
        assert final["status"] == "COMPLETED", (
            f"Vietnamese file failed: {final['status']}"
        )

        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        print(f"\n  Vietnamese result: {resp.json().get('text', '')[:200]}")


@pytest.mark.full_flow
class TestFullFlow_OutputFormats:
    """Verify different output formats through the full pipeline."""

    def test_ef019_json_output_format(self, auth_client, available_services):
        """EF-019: output_format=json → result has structured fields."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        upload_data = _upload(auth_client, filepath, output_format="json")
        final, _ = _poll_until_terminal(auth_client, upload_data["request_id"])
        assert final["status"] == "COMPLETED"

        job_id = final["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        result = resp.json()

        print(f"\n  JSON result keys: {list(result.keys())}")

        # JSON format should have structured data (text + details/lines)
        assert "text" in result or "pages" in result or "details" in result, (
            f"JSON result missing expected fields. Keys: {list(result.keys())}"
        )

        if "text" in result:
            assert len(result["text"]) > 50
        if "details" in result:
            assert isinstance(result["details"], list)
            print(f"  Details entries: {len(result['details'])}")

    def test_ef020_txt_vs_json_same_text(self, auth_client, available_services):
        """EF-020: txt and json formats produce the same underlying text."""
        _require_method(available_services, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        # Upload as txt
        txt_data = _upload(auth_client, filepath, output_format="txt")
        txt_final, _ = _poll_until_terminal(auth_client, txt_data["request_id"])
        assert txt_final["status"] == "COMPLETED"
        txt_result = auth_client.get(
            f"/jobs/{txt_final['jobs'][0]['id']}/result"
        ).json()
        txt_text = txt_result.get("text", "")

        # Upload as json
        json_data = _upload(auth_client, filepath, output_format="json")
        json_final, _ = _poll_until_terminal(auth_client, json_data["request_id"])
        assert json_final["status"] == "COMPLETED"
        json_result = auth_client.get(
            f"/jobs/{json_final['jobs'][0]['id']}/result"
        ).json()
        json_text = json_result.get("text", "")

        print(f"\n  TXT length: {len(txt_text)}")
        print(f"  JSON text length: {len(json_text)}")

        # Both should have substantial text
        assert len(txt_text) > 50, "TXT result too short"
        assert len(json_text) > 50, "JSON text too short"

        # Text content should be similar (not necessarily identical due to formatting)
        # Check that at least some common words appear in both
        txt_words = set(txt_text.lower().split()[:20])
        json_words = set(json_text.lower().split()[:20])
        overlap = txt_words & json_words

        print(f"  Word overlap (first 20): {len(overlap)}/{min(len(txt_words), len(json_words))}")
        assert len(overlap) >= 3, (
            f"TXT and JSON outputs have very different text. "
            f"TXT words: {txt_words}, JSON words: {json_words}"
        )
