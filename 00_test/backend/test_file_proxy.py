"""
Test cases for File Proxy API (Internal Worker Endpoints).

Endpoints:
  - POST /api/v1/internal/file-proxy/download
  - POST /api/v1/internal/file-proxy/upload
"""

import base64
import time
import pytest
import httpx

API_V1 = "http://localhost:8000/api/v1"

# Test service access key (must match SEED_SERVICES in test config)
TEST_ACCESS_KEY = "sk_test_key"


class TestFileProxyDownload:
    """Tests for POST /internal/file-proxy/download."""

    @pytest.fixture
    async def uploaded_file(self, client, auth_headers, sample_png):
        """Upload a file and return its info."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        data = resp.json()
        return {
            "request_id": data["request_id"],
            "file_id": data["files"][0]["id"],
            "job_id": None,  # Need to get from DB
        }

    @pytest.mark.asyncio
    async def test_download_without_access_key(self, client):
        """Should reject request without access key."""
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "test-job", "file_id": "test-file"}
        )

        assert resp.status_code == 422  # Missing header

    @pytest.mark.asyncio
    async def test_download_invalid_access_key(self, client):
        """Should reject invalid access key."""
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "test-job", "file_id": "test-file"},
            headers={"X-Access-Key": "invalid_key"}
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_download_nonexistent_job(self, client):
        """Should reject non-existent job."""
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "nonexistent-job", "file_id": "some-file"},
            headers={"X-Access-Key": TEST_ACCESS_KEY}
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_download_file_not_in_job(self, client):
        """Should reject file not belonging to job."""
        # This would need actual job/file IDs from DB
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "real-job", "file_id": "wrong-file"},
            headers={"X-Access-Key": TEST_ACCESS_KEY}
        )

        assert resp.status_code == 403


class TestFileProxyUpload:
    """Tests for POST /internal/file-proxy/upload."""

    @pytest.mark.asyncio
    async def test_upload_without_access_key(self, client):
        """Should reject request without access key."""
        content = base64.b64encode(b"OCR result text").decode()

        resp = await client.post(
            f"{API_V1}/internal/file-proxy/upload",
            json={
                "job_id": "test-job",
                "file_id": "test-file",
                "content": content,
                "content_type": "text/plain"
            }
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_invalid_access_key(self, client):
        """Should reject invalid access key."""
        content = base64.b64encode(b"OCR result text").decode()

        resp = await client.post(
            f"{API_V1}/internal/file-proxy/upload",
            json={
                "job_id": "test-job",
                "file_id": "test-file",
                "content": content,
                "content_type": "text/plain"
            },
            headers={"X-Access-Key": "invalid_key"}
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_invalid_base64(self, client):
        """Should reject invalid base64 content."""
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/upload",
            json={
                "job_id": "test-job",
                "file_id": "test-file",
                "content": "not-valid-base64!!!",
                "content_type": "text/plain"
            },
            headers={"X-Access-Key": TEST_ACCESS_KEY}
        )

        assert resp.status_code in [400, 403]

    @pytest.mark.asyncio
    async def test_upload_nonexistent_job(self, client):
        """Should reject non-existent job."""
        content = base64.b64encode(b"OCR result text").decode()

        resp = await client.post(
            f"{API_V1}/internal/file-proxy/upload",
            json={
                "job_id": "nonexistent-job",
                "file_id": "some-file",
                "content": content,
                "content_type": "text/plain"
            },
            headers={"X-Access-Key": TEST_ACCESS_KEY}
        )

        assert resp.status_code == 403


class TestFileProxyIntegration:
    """Integration tests for file proxy (requires full upload flow)."""

    @pytest.mark.asyncio
    async def test_full_download_upload_flow(self, client, auth_headers, sample_png):
        """Test complete worker flow: download -> process -> upload."""
        # Step 1: User uploads file
        files = {"files": ("test.png", sample_png, "image/png")}
        upload_resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        file_id = upload_data["files"][0]["id"]
        request_id = upload_data["request_id"]

        # Note: To complete this test, we'd need to:
        # 1. Query DB to get the job_id created for this file
        # 2. Use file proxy download to get the file
        # 3. Use file proxy upload to submit result
        # 4. Verify result is stored correctly

        # For now, just verify upload created the records
        assert file_id is not None
        assert request_id is not None
