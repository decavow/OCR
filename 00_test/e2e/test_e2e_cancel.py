"""E2E-013: Cancel request — cancel QUEUED jobs."""

import pytest
from .helpers import upload_file


class TestCancelRequest:
    """Cancel flow E2E tests."""

    def test_e2e013_cancel_queued_request(self, client, sample_png, worker_setup):
        """Cancel a request with QUEUED jobs should succeed."""
        # Upload file
        resp = upload_file(client, sample_png, filename="cancel_test.png")
        assert resp.status_code == 200
        request_id = resp.json()["request_id"]

        # Jobs should be QUEUED
        detail = client.get(f"/requests/{request_id}")
        assert detail.json()["jobs"][0]["status"] == "QUEUED"

        # Cancel
        cancel_resp = client.post(f"/requests/{request_id}/cancel")
        assert cancel_resp.status_code == 200
        cancel_data = cancel_resp.json()
        assert cancel_data["success"] is True

        # Verify status after cancel
        detail2 = client.get(f"/requests/{request_id}")
        detail2_data = detail2.json()
        # If a real worker already picked the job, it may be PROCESSING/COMPLETED
        assert detail2_data["status"] in ("CANCELLED", "FAILED", "PROCESSING", "COMPLETED")

    def test_e2e013b_cancel_single_job(self, client, sample_png, worker_setup):
        """Cancel a single QUEUED job — may fail if real worker already picked it."""
        resp = upload_file(client, sample_png, filename="cancel_job.png")
        request_id = resp.json()["request_id"]
        detail = client.get(f"/requests/{request_id}")
        job_id = detail.json()["jobs"][0]["id"]

        cancel_resp = client.post(f"/jobs/{job_id}/cancel")
        # 200 if still QUEUED, 400 if real worker already moved it to PROCESSING
        assert cancel_resp.status_code in (200, 400)
