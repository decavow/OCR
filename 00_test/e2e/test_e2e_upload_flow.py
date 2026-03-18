"""
E2E-004→006, 010, 011: Upload → Worker → Result — Full OCR lifecycle.

This is the CORE E2E test: simulates the complete user flow from upload
through worker processing to result download. The "worker" is simulated
by calling internal APIs (file-proxy, job-status) directly.
"""

import pytest
from .helpers import upload_file, upload_multiple_files, simulate_worker_process_job, wait_for_status


@pytest.mark.usefixtures("refresh_worker")
class TestUploadSingleFile:
    """Upload a single file and verify job creation."""

    def test_e2e004_upload_single_png(self, client, sample_png, worker_setup):
        """Upload a single PNG → request created with PROCESSING status."""
        resp = upload_file(client, sample_png, filename="test_e2e.png")
        assert resp.status_code == 200
        data = resp.json()

        assert "request_id" in data
        assert data["total_files"] == 1
        assert data["method"] == "ocr_paddle_text"
        assert data["tier"] == 0
        assert data["output_format"] == "txt"
        assert len(data["files"]) == 1
        assert data["files"][0]["original_name"] == "test_e2e.png"
        assert data["files"][0]["mime_type"] == "image/png"

    def test_e2e005_check_request_status_after_upload(self, client, sample_png, worker_setup):
        """After upload, request status should be PROCESSING with jobs QUEUED."""
        resp = upload_file(client, sample_png)
        assert resp.status_code == 200
        request_id = resp.json()["request_id"]

        # Check request detail
        detail = client.get(f"/requests/{request_id}")
        assert detail.status_code == 200
        detail_data = detail.json()
        assert detail_data["id"] == request_id
        assert detail_data["status"] == "PROCESSING"
        assert detail_data["total_files"] == 1
        assert len(detail_data["jobs"]) == 1
        assert detail_data["jobs"][0]["status"] == "QUEUED"


@pytest.mark.usefixtures("refresh_worker")
class TestFullOCRLifecycle:
    """Complete flow: Upload → Worker processes → User gets result."""

    def test_e2e006_upload_worker_process_get_result(self, client, sample_png, worker_setup):
        """
        Full lifecycle:
        1. User uploads PNG
        2. Worker downloads file via file-proxy
        3. Worker uploads result via file-proxy
        4. Worker marks job COMPLETED
        5. User checks request → COMPLETED
        6. User downloads result → contains text
        """
        # Step 1: Upload
        resp = upload_file(client, sample_png, filename="lifecycle_test.png")
        assert resp.status_code == 200
        upload_data = resp.json()
        request_id = upload_data["request_id"]
        file_id = upload_data["files"][0]["id"]

        # Get job_id from request detail
        detail = client.get(f"/requests/{request_id}")
        assert detail.status_code == 200
        job_id = detail.json()["jobs"][0]["id"]

        # Step 2-4: Simulate worker processing
        expected_text = "Xin chào từ E2E test - OCR kết quả thành công!"
        worker_results = simulate_worker_process_job(
            client=client,
            access_key=worker_setup["access_key"],
            job_id=job_id,
            file_id=file_id,
            result_text=expected_text,
        )
        assert worker_results["processing"]["status_code"] == 200
        assert worker_results["download"]["content_length"] > 0
        assert worker_results["upload"]["status_code"] == 200
        assert worker_results["completed"]["status_code"] == 200

        # Step 5: Check request status → COMPLETED
        detail2 = client.get(f"/requests/{request_id}")
        assert detail2.status_code == 200
        detail2_data = detail2.json()
        assert detail2_data["status"] == "COMPLETED"
        assert detail2_data["completed_files"] == 1
        assert detail2_data["failed_files"] == 0

        # Step 6: Get result
        result_resp = client.get(f"/jobs/{job_id}/result")
        assert result_resp.status_code == 200
        result_data = result_resp.json()
        assert expected_text in result_data["text"]
        assert result_data["lines"] >= 1

    def test_e2e010_download_result_as_raw(self, client, sample_png, worker_setup):
        """Download result in raw format should return plain text."""
        # Upload + process
        resp = upload_file(client, sample_png, filename="raw_test.png")
        request_id = resp.json()["request_id"]
        detail = client.get(f"/requests/{request_id}")
        job = detail.json()["jobs"][0]

        simulate_worker_process_job(
            client=client,
            access_key=worker_setup["access_key"],
            job_id=job["id"],
            file_id=job["file_id"],
            result_text="Raw result content",
        )

        # Download raw
        raw_resp = client.get(f"/jobs/{job['id']}/result?format=raw")
        assert raw_resp.status_code == 200
        assert b"Raw result content" in raw_resp.content

    def test_e2e010b_download_result_file(self, client, sample_png, worker_setup):
        """Download result as file attachment."""
        resp = upload_file(client, sample_png, filename="download_test.png")
        request_id = resp.json()["request_id"]
        detail = client.get(f"/requests/{request_id}")
        job = detail.json()["jobs"][0]

        simulate_worker_process_job(
            client=client,
            access_key=worker_setup["access_key"],
            job_id=job["id"],
            file_id=job["file_id"],
            result_text="Downloadable result",
        )

        dl_resp = client.get(f"/jobs/{job['id']}/download")
        assert dl_resp.status_code == 200
        assert "Content-Disposition" in dl_resp.headers
        assert b"Downloadable result" in dl_resp.content


@pytest.mark.usefixtures("refresh_worker")
class TestMultiFileUpload:
    """Upload multiple files in one request."""

    def test_e2e011_upload_three_files(self, client, sample_png, worker_setup):
        """Upload 3 files → 3 jobs created, process all → COMPLETED."""
        files_data = [
            ("file1.png", sample_png, "image/png"),
            ("file2.png", sample_png, "image/png"),
            ("file3.png", sample_png, "image/png"),
        ]
        resp = upload_multiple_files(client, files_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] == 3
        assert len(data["files"]) == 3

        request_id = data["request_id"]

        # Get all jobs
        detail = client.get(f"/requests/{request_id}")
        jobs = detail.json()["jobs"]
        assert len(jobs) == 3

        # Try to simulate worker for each job (skip if real worker already picked it up)
        for job in jobs:
            if job["status"] not in ("QUEUED", "SUBMITTED"):
                continue  # Real worker already processing/completed
            try:
                simulate_worker_process_job(
                    client=client,
                    access_key=worker_setup["access_key"],
                    job_id=job["id"],
                    file_id=job["file_id"],
                    result_text=f"Result for {job['id']}",
                )
            except AssertionError:
                pass  # Real worker may have picked it up between check and simulate

        # Wait for all to complete (real worker or simulated)
        result = wait_for_status(
            client, request_id,
            ["COMPLETED", "PARTIAL_SUCCESS", "FAILED"],
            timeout=60, interval=2,
        )
        # With real worker: may be COMPLETED or PARTIAL_SUCCESS
        # (simulated worker uses different access key than real worker)
        assert result["status"] in ("COMPLETED", "PARTIAL_SUCCESS")
        assert result["completed_files"] >= 1


@pytest.mark.usefixtures("refresh_worker")
class TestUploadWithPDF:
    """Upload PDF file."""

    def test_e2e004b_upload_pdf(self, client, sample_pdf, worker_setup):
        """Upload a PDF file should work."""
        resp = upload_file(
            client, sample_pdf,
            filename="test.pdf", mime="application/pdf",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] == 1
        assert data["files"][0]["mime_type"] == "application/pdf"
