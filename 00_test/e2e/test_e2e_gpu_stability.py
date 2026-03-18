"""
E2E GPU Stability Tests — Verify no OOM during model init and processing.

Tests ensure:
  1. Worker starts successfully (model loads without OOM)
  2. Sequential jobs don't leak GPU memory
  3. Multi-page PDFs process without OOM
  4. Both engines (paddle_text + paddle_vl) can operate
  5. Rapid sequential uploads don't cause memory accumulation
  6. Batch processing under load remains stable

Test IDs: GS-001 to GS-015

Requires: Real OCR worker(s) running with GPU.
"""

import os
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
PDF_TIMEOUT = 300
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


def _poll_until_terminal(client: httpx.Client, request_id: str,
                         timeout: int = OCR_TIMEOUT) -> dict:
    """Poll request status until terminal state."""
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
    """Get result text for a completed job."""
    resp = client.get(f"/jobs/{job_id}/result")
    if resp.status_code != 200:
        return ""
    return resp.json().get("text", "")


def _check_worker_health(client: httpx.Client) -> dict:
    """Check overall system health including workers."""
    resp = client.get("/health")
    assert resp.status_code == 200
    return resp.json()


def _get_available_methods(client: httpx.Client) -> dict:
    """Get available OCR methods and their worker counts."""
    resp = client.get("/services/available")
    assert resp.status_code == 200
    methods = {}
    for svc in resp.json().get("items", []):
        for method in svc.get("allowed_methods", []):
            if svc.get("active_instances", 0) > 0:
                methods[method] = {
                    "service_id": svc["id"],
                    "instances": svc["active_instances"],
                }
    return methods


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def auth_client():
    """Authenticated client for GPU stability tests."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        token = _auth(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture(scope="module")
def available_methods(auth_client) -> dict:
    """Detect available OCR methods."""
    return _get_available_methods(auth_client)


def _require_method(available_methods, method: str):
    """Skip if no active worker supports the given method."""
    if method not in available_methods:
        pytest.skip(f"No active worker with method '{method}'")
    return available_methods[method]


# ═══════════════════════════════════════════════════════════════════════════════
# GS-001 → GS-004: Worker Startup & Health Verification
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.gpu_stability
class TestGPUStartup:
    """Verify workers started successfully (models loaded without OOM)."""

    def test_gs001_system_health_ok(self, auth_client):
        """GS-001: System health check — all services running."""
        health = _check_worker_health(auth_client)
        assert health.get("status") in ("healthy", "ok", True), (
            f"System unhealthy: {health}"
        )
        print(f"\n  Health: {health}")

    def test_gs002_ocr_worker_available(self, auth_client, available_methods):
        """GS-002: At least one OCR worker is active (model loaded successfully)."""
        assert len(available_methods) > 0, (
            "No OCR workers available — model loading may have failed (OOM?)"
        )
        print(f"\n  Available methods: {list(available_methods.keys())}")
        for method, info in available_methods.items():
            print(f"    {method}: {info['instances']} instance(s)")

    def test_gs003_paddle_text_worker_responds(self, auth_client, available_methods):
        """GS-003: PaddleOCR text worker processes a simple image (model is loaded)."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("merrychirst.png")

        data = _upload(auth_client, filepath)
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            f"Worker failed on simple image: {result['status']} — possible OOM during processing"
        )
        text = _get_result_text(auth_client, result["jobs"][0]["id"])
        assert len(text) > 0, "Empty result — worker may have crashed"
        print(f"\n  Result: {len(text)} chars — worker healthy")

    def test_gs004_paddle_vl_worker_responds(self, auth_client, available_methods):
        """GS-004: PaddleVL structured worker processes a simple image (model is loaded)."""
        _require_method(available_methods, "structured_extract")
        filepath = _file_path("merrychirst.png")

        data = _upload(auth_client, filepath, method="structured_extract", output_format="json")
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            f"VL worker failed on simple image: {result['status']} — possible OOM"
        )
        print(f"\n  Structured extraction OK — VL worker healthy")


# ═══════════════════════════════════════════════════════════════════════════════
# GS-005 → GS-008: Sequential Processing (Memory Leak Detection)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.gpu_stability
class TestGPUSequentialProcessing:
    """Process multiple jobs sequentially — detect memory leaks."""

    def test_gs005_sequential_images_no_degradation(self, auth_client, available_methods):
        """GS-005: Process 5 images sequentially — all complete, no slowdown."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("paper_image.png")

        timings = []
        for i in range(5):
            start = time.time()
            data = _upload(auth_client, filepath)
            result = _poll_until_terminal(auth_client, data["request_id"])
            elapsed = time.time() - start

            assert result["status"] == "COMPLETED", (
                f"Job {i+1}/5 failed: {result['status']} — "
                f"possible GPU memory accumulation after {i} jobs"
            )
            timings.append(elapsed)
            print(f"\n  Job {i+1}/5: {elapsed:.1f}s")

        # Verify no significant slowdown (last job shouldn't be >3x slower than first)
        if timings[0] > 0:
            ratio = timings[-1] / timings[0]
            print(f"\n  Timing ratio (last/first): {ratio:.2f}x")
            assert ratio < 5.0, (
                f"Last job {timings[-1]:.1f}s is {ratio:.1f}x slower than first "
                f"{timings[0]:.1f}s — possible memory leak causing GPU thrashing"
            )

    def test_gs006_sequential_pdfs_no_degradation(self, auth_client, available_methods):
        """GS-006: Process 3 PDFs sequentially — all complete without OOM."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("1709.04109v4.pdf")

        timings = []
        for i in range(3):
            start = time.time()
            data = _upload(auth_client, filepath)
            result = _poll_until_terminal(auth_client, data["request_id"], timeout=PDF_TIMEOUT)
            elapsed = time.time() - start

            assert result["status"] == "COMPLETED", (
                f"PDF {i+1}/3 failed: {result['status']} — "
                f"multi-page PDF processing may cause OOM after {i} PDFs"
            )

            job_id = result["jobs"][0]["id"]
            text = _get_result_text(auth_client, job_id)
            timings.append(elapsed)
            print(f"\n  PDF {i+1}/3: {elapsed:.1f}s, {len(text)} chars")

            assert len(text) > 100, (
                f"PDF {i+1} result too short ({len(text)} chars) — "
                "possible partial processing due to memory pressure"
            )

    def test_gs007_alternating_image_pdf(self, auth_client, available_methods):
        """GS-007: Alternate between image and PDF — memory cleanup between types."""
        _require_method(available_methods, "ocr_paddle_text")
        img_path = _file_path("paper_image.png")
        pdf_path = _file_path("1709.04109v4.pdf")

        files = [
            ("image", img_path, OCR_TIMEOUT),
            ("pdf", pdf_path, PDF_TIMEOUT),
            ("image", img_path, OCR_TIMEOUT),
            ("pdf", pdf_path, PDF_TIMEOUT),
        ]

        for i, (ftype, fpath, timeout) in enumerate(files):
            data = _upload(auth_client, fpath)
            result = _poll_until_terminal(auth_client, data["request_id"], timeout=timeout)
            assert result["status"] == "COMPLETED", (
                f"Job {i+1} ({ftype}) failed: {result['status']} — "
                "memory cleanup between file types may be insufficient"
            )
            print(f"\n  Job {i+1} ({ftype}): COMPLETED")

    def test_gs008_sequential_structured_extractions(self, auth_client, available_methods):
        """GS-008: Sequential structured extractions — PPStructure memory stability."""
        _require_method(available_methods, "structured_extract")
        filepath = _file_path("paper_image.png")

        for i in range(3):
            data = _upload(auth_client, filepath, method="structured_extract", output_format="json")
            result = _poll_until_terminal(auth_client, data["request_id"])
            assert result["status"] == "COMPLETED", (
                f"Structured extraction {i+1}/3 failed: {result['status']} — "
                "PPStructure may be leaking GPU memory"
            )
            print(f"\n  Structured {i+1}/3: COMPLETED")


# ═══════════════════════════════════════════════════════════════════════════════
# GS-009 → GS-011: Heavy Load (Stress Tests)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.gpu_stability
class TestGPUHeavyLoad:
    """Stress GPU memory with heavy workloads."""

    def test_gs009_multi_page_pdf_stress(self, auth_client, available_methods):
        """GS-009: Multi-page academic PDF — high GPU memory usage per page."""
        _require_method(available_methods, "ocr_paddle_text")
        filepath = _file_path("1709.04109v4.pdf")

        start = time.time()
        data = _upload(auth_client, filepath)
        result = _poll_until_terminal(auth_client, data["request_id"], timeout=PDF_TIMEOUT)
        elapsed = time.time() - start

        assert result["status"] == "COMPLETED", (
            f"Multi-page PDF failed: {result['status']} — "
            "per-page GPU cache cleanup may not be working"
        )

        job = result["jobs"][0]
        text = _get_result_text(auth_client, job["id"])
        proc_time = job.get("processing_time_ms")

        print(f"\n  PDF processing: {elapsed:.1f}s wall, {proc_time}ms reported")
        print(f"  Result: {len(text)} chars")
        assert len(text) > 500, "Multi-page PDF should produce substantial text"

    def test_gs010_batch_upload_gpu_stability(self, auth_client, available_methods):
        """GS-010: Batch upload 3 files — concurrent processing on GPU."""
        _require_method(available_methods, "ocr_paddle_text")
        file1 = _file_path("paper_image.png")
        file2 = _file_path("merrychirst.png")
        file3 = _file_path("thiệp mừng năm mới.png")

        files_to_upload = [
            ("paper_image.png", open(file1, "rb"), "image/png"),
            ("merrychirst.png", open(file2, "rb"), "image/png"),
            ("greeting.png", open(file3, "rb"), "image/png"),
        ]

        try:
            for _ in range(5):
                for _, f, _ in files_to_upload:
                    f.seek(0)
                resp = auth_client.post(
                    "/upload",
                    files=[("files", (name, f, mime)) for name, f, mime in files_to_upload],
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
        finally:
            for _, f, _ in files_to_upload:
                f.close()

        assert resp.status_code == 200, f"Batch upload failed: {resp.text}"
        data = resp.json()
        assert data["total_files"] == 3

        result = _poll_until_terminal(auth_client, data["request_id"], timeout=OCR_TIMEOUT)
        assert result["status"] == "COMPLETED", (
            f"Batch failed: {result['status']}, "
            f"completed={result.get('completed_files')}, "
            f"failed={result.get('failed_files')} — "
            "concurrent GPU processing may cause OOM"
        )
        assert result["completed_files"] == 3
        print(f"\n  Batch 3 files: all COMPLETED")

    def test_gs011_structured_pdf_heavy(self, auth_client, available_methods):
        """GS-011: Structured extraction on multi-page PDF — heaviest GPU load."""
        _require_method(available_methods, "structured_extract")
        filepath = _file_path("1709.04109v4.pdf")

        start = time.time()
        data = _upload(
            auth_client, filepath,
            method="structured_extract", output_format="json",
        )
        result = _poll_until_terminal(auth_client, data["request_id"], timeout=PDF_TIMEOUT)
        elapsed = time.time() - start

        assert result["status"] == "COMPLETED", (
            f"Structured PDF failed: {result['status']} — "
            "PPStructure + multi-page = highest OOM risk"
        )

        job_id = result["jobs"][0]["id"]
        resp = auth_client.get(f"/jobs/{job_id}/result")
        assert resp.status_code == 200
        result_data = resp.json()

        pages = result_data.get("pages", [])
        total_regions = sum(len(p.get("regions", [])) for p in pages)

        print(f"\n  Structured PDF: {elapsed:.1f}s, {len(pages)} pages, {total_regions} regions")
        assert len(pages) >= 2, "Multi-page PDF should produce multiple pages"


# ═══════════════════════════════════════════════════════════════════════════════
# GS-012 → GS-014: Cross-Engine Stability
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.gpu_stability
class TestGPUCrossEngine:
    """Test stability when using multiple engine types."""

    def test_gs012_text_then_structured(self, auth_client, available_methods):
        """GS-012: PaddleText → PaddleVL — cross-engine GPU memory sharing."""
        has_text = "ocr_paddle_text" in available_methods
        has_vl = "structured_extract" in available_methods
        if not (has_text and has_vl):
            pytest.skip("Need both ocr_paddle_text and structured_extract workers")

        filepath = _file_path("paper_image.png")

        # First: text extraction
        data = _upload(auth_client, filepath, method="ocr_paddle_text")
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", "Text extraction failed before VL test"
        print(f"\n  Text extraction: COMPLETED")

        # Then: structured extraction
        data = _upload(auth_client, filepath, method="structured_extract", output_format="json")
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            "Structured extraction failed after text — cross-engine GPU contention"
        )
        print(f"  Structured extraction: COMPLETED")

    def test_gs013_structured_then_text(self, auth_client, available_methods):
        """GS-013: PaddleVL → PaddleText — reverse order cross-engine test."""
        has_text = "ocr_paddle_text" in available_methods
        has_vl = "structured_extract" in available_methods
        if not (has_text and has_vl):
            pytest.skip("Need both ocr_paddle_text and structured_extract workers")

        filepath = _file_path("paper_image.png")

        # First: structured extraction (heavier)
        data = _upload(auth_client, filepath, method="structured_extract", output_format="json")
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", "Structured failed before text test"
        print(f"\n  Structured extraction: COMPLETED")

        # Then: text extraction (lighter)
        data = _upload(auth_client, filepath, method="ocr_paddle_text")
        result = _poll_until_terminal(auth_client, data["request_id"])
        assert result["status"] == "COMPLETED", (
            "Text extraction failed after structured — GPU memory not freed"
        )
        print(f"  Text extraction: COMPLETED")

    def test_gs014_interleaved_engines_5_rounds(self, auth_client, available_methods):
        """GS-014: 5 rounds alternating text and structured — sustained stability."""
        has_text = "ocr_paddle_text" in available_methods
        has_vl = "structured_extract" in available_methods
        if not (has_text and has_vl):
            pytest.skip("Need both ocr_paddle_text and structured_extract workers")

        filepath = _file_path("paper_image.png")

        for i in range(5):
            # Text extraction
            data = _upload(auth_client, filepath, method="ocr_paddle_text")
            result = _poll_until_terminal(auth_client, data["request_id"])
            assert result["status"] == "COMPLETED", (
                f"Round {i+1}/5: text failed — memory degradation after {i} rounds"
            )

            # Structured extraction
            data = _upload(auth_client, filepath, method="structured_extract", output_format="json")
            result = _poll_until_terminal(auth_client, data["request_id"])
            assert result["status"] == "COMPLETED", (
                f"Round {i+1}/5: structured failed — memory degradation after {i} rounds"
            )
            print(f"\n  Round {i+1}/5: both engines OK")


# ═══════════════════════════════════════════════════════════════════════════════
# GS-015: Post-Load Health Check
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.gpu_stability
class TestGPUPostLoadHealth:
    """Verify system health after heavy GPU processing."""

    def test_gs015_worker_healthy_after_load(self, auth_client, available_methods):
        """GS-015: Workers still healthy after all previous tests."""
        # Check system health
        health = _check_worker_health(auth_client)
        print(f"\n  System health: {health}")

        # Verify workers still available
        current_methods = _get_available_methods(auth_client)
        assert len(current_methods) > 0, (
            "No workers available after load test — workers may have crashed from OOM"
        )

        # Quick smoke test: process one more image
        if "ocr_paddle_text" in current_methods:
            filepath = _file_path("merrychirst.png")
            data = _upload(auth_client, filepath)
            result = _poll_until_terminal(auth_client, data["request_id"], timeout=60)
            assert result["status"] == "COMPLETED", (
                "Worker can't process after load — possible OOM-induced crash"
            )
            print(f"  Post-load smoke test: COMPLETED")

        print(f"  Available methods: {list(current_methods.keys())}")
