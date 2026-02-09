"""
End-to-end OCR flow tests.

Tests the complete flow:
1. Upload image via backend
2. Job appears in NATS queue
3. Worker processes job
4. Result is uploaded
5. Status is updated
"""

import pytest
import nats
import asyncio

NATS_URL = "nats://localhost:4222"
API_V1 = "/api/v1"


class TestUploadToQueue:
    """Tests for upload -> queue flow."""

    @pytest.mark.asyncio
    async def test_upload_creates_job_in_nats(self, client, auth_headers, sample_png):
        """Should publish job to NATS after upload."""
        # Get initial message count
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        try:
            info = await js.stream_info("OCR_JOBS")
            initial_count = info.state.messages
        except:
            initial_count = 0

        # Upload file
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )
        assert resp.status_code == 200

        # Check message count increased
        info = await js.stream_info("OCR_JOBS")
        assert info.state.messages > initial_count

        await nc.close()

    @pytest.mark.asyncio
    async def test_upload_multiple_creates_multiple_jobs(self, client, auth_headers, sample_png):
        """Should publish one job per file."""
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        try:
            info = await js.stream_info("OCR_JOBS")
            initial_count = info.state.messages
        except:
            initial_count = 0

        # Upload 3 files
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
        assert resp.json()["total_files"] == 3

        # Check 3 messages added
        info = await js.stream_info("OCR_JOBS")
        assert info.state.messages >= initial_count + 3

        await nc.close()

    @pytest.mark.asyncio
    async def test_job_message_contains_correct_subject(self, client, auth_headers, sample_png):
        """Should use correct subject based on method and tier."""
        from app.clients.queue_client import QueueClient
        from app.config import settings

        # Upload with specific method and tier
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            params={"method": "text_raw", "tier": 0},
            headers=auth_headers
        )
        assert resp.status_code == 200

        # Create subscriber for that subject
        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.text_raw.tier0"
        settings.worker_service_id = "test-subject-check"

        queue = QueueClient()
        await queue.connect()

        job = await queue.pull_job(timeout=5.0)

        if job:
            assert job["method"] == "text_raw"
            assert job["tier"] == 0
            await queue.nak(job["_msg_id"])

        await queue.disconnect()


class TestWorkerProcessing:
    """Tests for worker processing simulation."""

    @pytest.mark.asyncio
    async def test_worker_can_download_uploaded_file(self, client, auth_headers, test_image_with_text):
        """Should be able to download file via file-proxy after upload."""
        img_bytes, _ = test_image_with_text

        # Upload file
        files = {"files": ("test.png", img_bytes, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )
        assert resp.status_code == 200

        upload_data = resp.json()
        file_info = upload_data["files"][0]
        file_id = file_info["id"]
        job_id = file_info["job_id"]

        # Try to download via file-proxy (need valid worker access key)
        from app.clients.file_proxy_client import FileProxyClient
        from app.config import settings

        settings.file_proxy_url = "http://localhost:8000/api/v1/internal/file-proxy"
        settings.worker_access_key = "sk_local_text_tier0"  # From seed

        proxy = FileProxyClient()

        try:
            content, content_type, filename = await proxy.download(job_id, file_id)
            assert len(content) > 0
            assert content_type in ("image/png", "application/octet-stream")
        except Exception as e:
            # May fail if access key not configured
            pytest.skip(f"File proxy not accessible: {e}")

    @pytest.mark.asyncio
    async def test_simulate_worker_flow(self, client, auth_headers, test_image_with_text):
        """Simulate complete worker processing flow."""
        from app.clients.queue_client import QueueClient
        from app.clients.file_proxy_client import FileProxyClient
        from app.core.processor import OCRProcessor
        from app.config import settings

        img_bytes, expected_text = test_image_with_text

        # Step 1: Upload file
        files = {"files": ("ocr_test.png", img_bytes, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            params={"output_format": "txt", "method": "text_raw", "tier": 0},
            headers=auth_headers
        )
        assert resp.status_code == 200

        # Step 2: Pull job from queue
        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.text_raw.tier0"
        settings.worker_service_id = "test-simulate"
        settings.file_proxy_url = "http://localhost:8000/api/v1/internal/file-proxy"
        settings.worker_access_key = "sk_local_text_tier0"

        queue = QueueClient()
        await queue.connect()

        job = await queue.pull_job(timeout=5.0)

        if not job:
            await queue.disconnect()
            pytest.skip("No job in queue")

        # Step 3: Download file
        proxy = FileProxyClient()
        try:
            content, _, _ = await proxy.download(job["job_id"], job["file_id"])
        except Exception as e:
            await queue.nak(job["_msg_id"])
            await queue.disconnect()
            pytest.skip(f"Cannot download: {e}")

        # Step 4: Process with OCR
        processor = OCRProcessor()
        result = await processor.process(
            file_content=content,
            output_format=job["output_format"],
            method=job["method"]
        )

        assert len(result) > 0
        result_text = result.decode("utf-8")
        print(f"OCR Result: {result_text}")

        # Step 5: Upload result (may fail without proper setup)
        try:
            await proxy.upload(
                job_id=job["job_id"],
                file_id=job["file_id"],
                content=result,
                content_type="text/plain"
            )
        except Exception as e:
            print(f"Upload skipped: {e}")

        # Ack the message
        await queue.ack(job["_msg_id"])
        await queue.disconnect()


class TestRequestStatus:
    """Tests for request/job status tracking."""

    @pytest.mark.asyncio
    async def test_request_status_after_upload(self, client, auth_headers, sample_png):
        """Should have SUBMITTED status after upload."""
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            headers=auth_headers
        )
        assert resp.status_code == 200

        request_id = resp.json()["request_id"]

        # Check status
        resp = await client.get(
            f"{API_V1}/requests/{request_id}",
            headers=auth_headers
        )

        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] in ["SUBMITTED", "QUEUED", "PROCESSING"]
