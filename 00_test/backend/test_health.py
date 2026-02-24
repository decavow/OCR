"""
Test cases for Health and Infrastructure endpoints.

Endpoints:
  - GET /health
  - GET /api/v1/health
"""

import pytest
import httpx

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


class TestHealth:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_health(self, client):
        """Should return healthy status from root endpoint."""
        resp = await client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_api_health(self, client):
        """Should return detailed health from API endpoint."""
        resp = await client.get(f"{API_V1}/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


class TestNATSIntegration:
    """Tests for NATS message queue integration."""

    @pytest.mark.asyncio
    async def test_upload_publishes_to_nats(self, client, auth_headers, sample_png):
        """Should publish job message to NATS after upload."""
        import nats

        # Connect to NATS to monitor messages
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()

        # Get initial message count
        try:
            info = await js.stream_info("OCR_JOBS")
            initial_count = info.state.messages
        except Exception:
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
    async def test_job_message_format(self, client, auth_headers, sample_png):
        """Should publish correctly formatted job message."""
        import nats
        import json

        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()

        # Create a consumer to read messages
        sub = await js.pull_subscribe("ocr.>", durable="test-consumer")

        # Upload file
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            params={"method": "ocr_text_raw", "tier": 0},
            headers=auth_headers
        )

        assert resp.status_code == 200
        upload_data = resp.json()

        # Fetch and verify message
        try:
            msgs = await sub.fetch(batch=1, timeout=5)
            msg_data = json.loads(msgs[0].data.decode())

            assert "job_id" in msg_data
            assert "file_id" in msg_data
            assert "request_id" in msg_data
            assert msg_data["method"] == "ocr_text_raw"
            assert msg_data["tier"] == 0
            assert "object_key" in msg_data

            await msgs[0].ack()
        except nats.errors.TimeoutError:
            pytest.fail("No message received from NATS")

        await nc.close()
