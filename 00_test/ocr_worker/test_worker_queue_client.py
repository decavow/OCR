"""Phase C — QueueClient tests (mock nats module).

Tests QC-001 through QC-011: connect, disconnect, pull_job, ack, nak, term.

Since the `nats` package may not be installed in the test environment,
we pre-install mock modules in sys.modules before importing QueueClient.
"""

import json
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock nats module hierarchy before importing QueueClient
# ---------------------------------------------------------------------------

def _install_nats_mocks():
    """Install mock nats modules into sys.modules so queue_client can import."""
    nats_mod = ModuleType("nats")
    nats_mod.connect = AsyncMock()

    nats_errors = ModuleType("nats.errors")
    nats_errors.TimeoutError = type("TimeoutError", (Exception,), {})
    nats_mod.errors = nats_errors

    nats_js = ModuleType("nats.js")
    nats_js_api = ModuleType("nats.js.api")
    nats_js_ctx = ModuleType("nats.js")

    # Stub JetStreamContext, ConsumerConfig, etc.
    nats_js.JetStreamContext = MagicMock
    nats_js_api.ConsumerConfig = MagicMock
    nats_js_api.DeliverPolicy = MagicMock
    nats_js_api.AckPolicy = MagicMock

    sys.modules.setdefault("nats", nats_mod)
    sys.modules.setdefault("nats.errors", nats_errors)
    sys.modules.setdefault("nats.js", nats_js)
    sys.modules.setdefault("nats.js.api", nats_js_api)

    return nats_mod


_nats_mock = _install_nats_mocks()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Create a QueueClient with mocked settings."""
    with patch("app.clients.queue_client.settings") as mock_settings:
        mock_settings.nats_url = "nats://localhost:4222"
        mock_settings.worker_service_type = "ocr-text-tier0"
        mock_settings.worker_filter_subject = "ocr.ocr_paddle_text.tier0"

        from app.clients.queue_client import QueueClient
        return QueueClient()


def _make_nats_message(data: dict, stream_seq: int = 1, consumer_seq: int = 1):
    """Create a mock NATS message."""
    msg = MagicMock()
    msg.data = json.dumps(data).encode()
    msg.metadata = SimpleNamespace(
        sequence=SimpleNamespace(stream=stream_seq, consumer=consumer_seq),
    )
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    msg.term = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQueueConnect:
    """QC-001, QC-002: connect and disconnect."""

    # QC-001: connect creates NATS connection and pull subscription
    @pytest.mark.asyncio
    async def test_connect(self):
        client = _make_client()

        mock_nc = MagicMock()
        mock_js = MagicMock()
        mock_sub = MagicMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)
        mock_js.pull_subscribe = AsyncMock(return_value=mock_sub)

        with patch("app.clients.queue_client.nats") as mock_nats:
            mock_nats.connect = AsyncMock(return_value=mock_nc)

            await client.connect()

        assert client.nc is mock_nc
        assert client.js is mock_js
        assert client.subscription is mock_sub
        mock_js.pull_subscribe.assert_awaited_once()

        # Verify subject and stream
        call_kwargs = mock_js.pull_subscribe.call_args
        assert call_kwargs.kwargs["subject"] == "ocr.ocr_paddle_text.tier0"
        assert call_kwargs.kwargs["stream"] == "OCR_JOBS"

    # QC-002: disconnect drains and clears connection
    @pytest.mark.asyncio
    async def test_disconnect(self):
        client = _make_client()
        mock_nc = MagicMock()
        mock_nc.drain = AsyncMock()
        client.nc = mock_nc

        await client.disconnect()

        mock_nc.drain.assert_awaited_once()
        assert client.nc is None


class TestQueuePullJob:
    """QC-003 to QC-006: pull_job behavior."""

    # QC-003: pull_job valid -> returns dict
    @pytest.mark.asyncio
    async def test_pull_job_valid(self):
        client = _make_client()
        job_data = {
            "job_id": "j-1",
            "file_id": "f-1",
            "request_id": "r-1",
            "method": "ocr_paddle_text",
            "tier": 0,
            "output_format": "txt",
            "object_key": "user/req/file/img.png",
        }
        mock_msg = _make_nats_message(job_data, stream_seq=10, consumer_seq=5)

        mock_sub = MagicMock()
        mock_sub.fetch = AsyncMock(return_value=[mock_msg])
        client.subscription = mock_sub

        result = await client.pull_job(timeout=5.0)

        assert result is not None
        assert result["job_id"] == "j-1"
        assert result["file_id"] == "f-1"
        assert result["method"] == "ocr_paddle_text"
        assert result["_msg_id"] == "10_5"

    # QC-004: pull_job timeout -> None
    @pytest.mark.asyncio
    async def test_pull_job_timeout(self):
        client = _make_client()

        mock_sub = MagicMock()

        # Use the mocked nats.errors.TimeoutError
        nats_errors = sys.modules["nats.errors"]
        mock_sub.fetch = AsyncMock(side_effect=nats_errors.TimeoutError)
        client.subscription = mock_sub

        result = await client.pull_job(timeout=1.0)
        assert result is None

    # QC-005: pull_job parse error -> None
    @pytest.mark.asyncio
    async def test_pull_job_parse_error(self):
        client = _make_client()

        bad_msg = MagicMock()
        bad_msg.data = b"not valid json"

        mock_sub = MagicMock()
        mock_sub.fetch = AsyncMock(return_value=[bad_msg])
        client.subscription = mock_sub

        result = await client.pull_job()
        assert result is None

    # QC-006: pull_job stores message with timestamp for later ack/nak
    @pytest.mark.asyncio
    async def test_pull_job_stores_message(self):
        client = _make_client()
        job_data = {
            "job_id": "j-2",
            "file_id": "f-2",
            "request_id": "r-2",
            "method": "ocr_paddle_text",
            "tier": 0,
            "output_format": "txt",
            "object_key": "key",
        }
        mock_msg = _make_nats_message(job_data, stream_seq=20, consumer_seq=10)

        mock_sub = MagicMock()
        mock_sub.fetch = AsyncMock(return_value=[mock_msg])
        client.subscription = mock_sub

        result = await client.pull_job()

        msg_id = result["_msg_id"]
        assert msg_id in client._pending_messages
        # _pending_messages stores (msg, timestamp) tuples
        entry = client._pending_messages[msg_id]
        assert isinstance(entry, tuple)
        assert entry[0] is mock_msg
        assert isinstance(entry[1], float)  # monotonic timestamp


class TestQueueAckNakTerm:
    """QC-007 to QC-011: ack, nak, term."""

    # QC-007: ack valid message
    @pytest.mark.asyncio
    async def test_ack_valid(self):
        client = _make_client()
        mock_msg = MagicMock()
        mock_msg.ack = AsyncMock()
        client._pending_messages["msg-1"] = (mock_msg, 1000.0)

        await client.ack("msg-1")

        mock_msg.ack.assert_awaited_once()
        assert "msg-1" not in client._pending_messages

    # QC-008: ack unknown message id -> no error
    @pytest.mark.asyncio
    async def test_ack_unknown(self):
        client = _make_client()
        # Should not raise
        await client.ack("nonexistent")

    # QC-009: nak with delay
    @pytest.mark.asyncio
    async def test_nak_with_delay(self):
        client = _make_client()
        mock_msg = MagicMock()
        mock_msg.nak = AsyncMock()
        client._pending_messages["msg-2"] = (mock_msg, 1000.0)

        await client.nak("msg-2", delay=5.0)

        mock_msg.nak.assert_awaited_once_with(delay=5.0)
        assert "msg-2" not in client._pending_messages

    # QC-010: nak without delay
    @pytest.mark.asyncio
    async def test_nak_without_delay(self):
        client = _make_client()
        mock_msg = MagicMock()
        mock_msg.nak = AsyncMock()
        client._pending_messages["msg-3"] = (mock_msg, 1000.0)

        await client.nak("msg-3")

        mock_msg.nak.assert_awaited_once_with()
        assert "msg-3" not in client._pending_messages

    # QC-011: term valid message
    @pytest.mark.asyncio
    async def test_term_valid(self):
        client = _make_client()
        mock_msg = MagicMock()
        mock_msg.term = AsyncMock()
        client._pending_messages["msg-4"] = (mock_msg, 1000.0)

        await client.term("msg-4")

        mock_msg.term.assert_awaited_once()
        assert "msg-4" not in client._pending_messages
