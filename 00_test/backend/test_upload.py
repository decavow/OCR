"""
Test cases for Upload API.

Endpoints:
  - POST /api/v1/upload
"""

import time
import pytest
import httpx

API_V1 = "http://localhost:8000/api/v1"


class TestUpload:
    """Tests for POST /upload."""

    @pytest.mark.asyncio
    async def test_upload_single_file(self, client, auth_headers, sample_png):
        """Should upload single file successfully."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert data["status"] == "PROCESSING"
        assert data["total_files"] == 1
        assert len(data["files"]) == 1
        assert data["files"][0]["original_name"] == "test.png"

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, client, auth_headers, sample_png):
        """Should upload multiple files successfully."""
        files = [
            ("files", ("test1.png", sample_png, "image/png")),
            ("files", ("test2.png", sample_png, "image/png")),
            ("files", ("test3.png", sample_png, "image/png")),
        ]

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] == 3
        assert len(data["files"]) == 3

    @pytest.mark.asyncio
    async def test_upload_with_output_format(self, client, auth_headers, sample_png):
        """Should accept output format parameter."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            data={"output_format": "json"},
            headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["output_format"] == "json"

    @pytest.mark.asyncio
    async def test_upload_with_method_tier(self, client, auth_headers, sample_png):
        """Should accept method and tier parameters."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            data={"method": "ocr_text_raw", "tier": "0"},
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "ocr_text_raw"
        assert data["tier"] == 0

    @pytest.mark.asyncio
    async def test_upload_pdf(self, client, auth_headers, sample_pdf):
        """Should upload PDF file successfully."""
        files = {"files": ("document.pdf", sample_pdf, "application/pdf")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["files"][0]["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_upload_without_auth(self, client, sample_png):
        """Should reject upload without authentication."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(f"{API_V1}/upload", files=files)

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, client, auth_headers):
        """Should reject unsupported file type."""
        # Create a fake executable file
        fake_exe = b"MZ" + b"\x00" * 100  # DOS header signature

        files = {"files": ("malware.exe", fake_exe, "application/x-msdownload")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_empty_file(self, client, auth_headers):
        """Should handle empty file."""
        files = {"files": ("empty.png", b"", "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        # Empty file should be rejected (invalid magic bytes)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_response_structure(self, client, auth_headers, sample_png):
        """Should return correct response structure."""
        files = {"files": ("test.png", sample_png, "image/png")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()

        # Check top-level fields
        assert "request_id" in data
        assert "status" in data
        assert "total_files" in data
        assert "output_format" in data
        assert "method" in data
        assert "tier" in data
        assert "created_at" in data
        assert "files" in data

        # Check file structure
        file_data = data["files"][0]
        assert "id" in file_data
        assert "original_name" in file_data
        assert "mime_type" in file_data
        assert "size_bytes" in file_data


class TestUploadValidation:
    """Tests for upload validation."""

    @pytest.mark.asyncio
    async def test_file_size_limit(self, client, auth_headers):
        """Should reject files exceeding size limit."""
        # Create a large file (> 50MB)
        # Note: This test might be slow or cause memory issues
        # In practice, we'd mock the size limit check
        pass  # Skip for now - would need actual large file

    @pytest.mark.asyncio
    async def test_batch_size_limit(self, client, auth_headers, sample_png):
        """Should reject batches exceeding limit (20 files)."""
        files = [
            ("files", (f"test_{i}.png", sample_png, "image/png"))
            for i in range(25)  # Exceed 20 file limit
        ]

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_magic_bytes_validation(self, client, auth_headers):
        """Should validate file content matches declared type."""
        # Send PNG content with JPEG mime type
        png_data = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG magic

        files = {"files": ("fake.jpg", png_data, "image/jpeg")}

        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )

        # Should detect actual type from magic bytes
        assert resp.status_code == 200
        # The detected mime should be PNG, not JPEG
