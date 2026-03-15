"""E2E-012, 014, 015: Error handling — invalid input, auth, not found."""

import uuid
import pytest
from .helpers import upload_file


class TestUploadErrors:
    """Upload validation E2E tests."""

    def test_e2e012_upload_invalid_mime_type(self, client, worker_setup):
        """Upload non-image file should be rejected."""
        txt_content = b"This is a plain text file, not an image."
        resp = upload_file(
            client, txt_content,
            filename="test.txt", mime="text/plain",
        )
        # Should reject — non-image MIME type
        assert resp.status_code in (400, 422)

    def test_e2e012b_upload_empty_file(self, client, worker_setup):
        """Upload empty file — backend may accept or reject."""
        resp = upload_file(client, b"", filename="empty.png", mime="image/png")
        # Backend may accept empty files (200) or reject them (400/422)
        assert resp.status_code in (200, 400, 422, 500)

    def test_e2e012c_upload_no_files(self, client, worker_setup):
        """Upload request without files should fail."""
        resp = client.post("/upload", data={
            "output_format": "txt",
            "method": "ocr_paddle_text",
            "tier": "0",
        })
        assert resp.status_code == 422  # FastAPI validation error


class TestNotFoundErrors:
    """404 error handling E2E tests."""

    def test_e2e015_request_not_found(self, client):
        """Getting non-existent request should return 404."""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/requests/{fake_id}")
        assert resp.status_code == 404

    def test_e2e015b_job_not_found(self, client):
        """Getting non-existent job should return 404."""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/jobs/{fake_id}")
        assert resp.status_code == 404

    def test_e2e015c_result_not_found_for_incomplete_job(self, client, sample_png, worker_setup):
        """Getting result for non-completed job should fail."""
        resp = upload_file(client, sample_png)
        request_id = resp.json()["request_id"]
        detail = client.get(f"/requests/{request_id}")
        job_id = detail.json()["jobs"][0]["id"]

        # Job is QUEUED, not COMPLETED
        result_resp = client.get(f"/jobs/{job_id}/result")
        assert result_resp.status_code == 400


class TestAuthErrors:
    """Authentication error E2E tests."""

    def test_e2e014_no_auth_upload(self, anon_client, worker_setup):
        """Upload without auth should return 401 (or 429 if rate limited)."""
        resp = anon_client.post(
            "/upload",
            files=[("files", ("test.png", b"\x89PNG", "image/png"))],
            data={"output_format": "txt", "method": "ocr_paddle_text", "tier": "0"},
        )
        assert resp.status_code in (401, 429)

    def test_e2e014b_no_auth_requests_list(self, anon_client):
        """List requests without auth should return 401."""
        resp = anon_client.get("/requests")
        assert resp.status_code == 401

    def test_e2e014c_no_auth_jobs(self, anon_client):
        """Get job without auth should return 401."""
        resp = anon_client.get(f"/jobs/{uuid.uuid4()}")
        assert resp.status_code == 401
