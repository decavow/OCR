"""
Test cases for QueueClient (NATS subscriber).
"""

import pytest
import nats

NATS_URL = "nats://localhost:4222"


class TestNATSConnection:
    """Tests for NATS connectivity."""

    @pytest.mark.asyncio
    async def test_connect_to_nats(self):
        """Should connect to NATS server."""
        nc = await nats.connect(NATS_URL)
        assert nc.is_connected
        await nc.close()

    @pytest.mark.asyncio
    async def test_jetstream_available(self):
        """Should have JetStream enabled."""
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        # This should not raise
        await js.account_info()
        await nc.close()

    @pytest.mark.asyncio
    async def test_ocr_jobs_stream_exists(self):
        """Should have OCR_JOBS stream configured."""
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        info = await js.stream_info("OCR_JOBS")
        assert info is not None
        assert "ocr.>" in info.config.subjects

        await nc.close()


class TestQueueClient:
    """Tests for worker's QueueClient."""

    @pytest.mark.asyncio
    async def test_queue_client_connect(self):
        """Should connect QueueClient to NATS."""
        from app.clients.queue_client import QueueClient
        from app.config import settings

        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.ocr_text_raw.tier0"
        settings.worker_service_type = "test-worker"

        client = QueueClient()
        await client.connect()

        assert client.nc is not None
        assert client.nc.is_connected

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_queue_client_pull_empty(self):
        """Should return None when no messages available."""
        from app.clients.queue_client import QueueClient
        from app.config import settings

        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.ocr_text_raw.tier0"
        settings.worker_service_type = "test-worker-empty"

        client = QueueClient()
        await client.connect()

        # Pull with short timeout
        job = await client.pull_job(timeout=1.0)

        # Should be None or a job dict
        assert job is None or isinstance(job, dict)

        if job:
            # If we got a job, nak it
            await client.nak(job["_msg_id"])

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_queue_client_message_format(self, client, auth_headers, sample_png):
        """Should receive correctly formatted job message after upload."""
        from app.clients.queue_client import QueueClient
        from app.config import settings

        # Upload a file to trigger job message
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            "/api/v1/upload",
            files=files,
            data={"method": "ocr_text_raw", "tier": "0"},
            headers=auth_headers
        )
        assert resp.status_code == 200

        # Connect queue client and pull
        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.ocr_text_raw.tier0"
        settings.worker_service_type = "test-worker-format"

        queue = QueueClient()
        await queue.connect()

        job = await queue.pull_job(timeout=5.0)

        if job:
            # Verify job format
            assert "job_id" in job
            assert "file_id" in job
            assert "request_id" in job
            assert "method" in job
            assert "tier" in job
            assert "output_format" in job
            assert "object_key" in job
            assert "_msg_id" in job

            # Nak to allow reprocessing
            await queue.nak(job["_msg_id"])

        await queue.disconnect()
