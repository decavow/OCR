"""Phase C — HeartbeatClient tests (mock httpx + asyncio).

Tests HC-001 through HC-013: state management, start/stop lifecycle,
and _send_heartbeat behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**overrides):
    """Create a HeartbeatClient with mocked settings."""
    defaults = {
        "orchestrator_url": "http://backend:8000/api/v1/internal",
        "worker_access_key": None,
        "worker_instance_id": "worker-test-1",
        "heartbeat_interval_ms": 30000,
    }
    defaults.update(overrides)

    with patch("app.clients.heartbeat_client.settings") as mock_settings:
        mock_settings.orchestrator_url = defaults["orchestrator_url"]
        mock_settings.worker_access_key = defaults["worker_access_key"]
        mock_settings.worker_instance_id = defaults["worker_instance_id"]
        mock_settings.heartbeat_interval_ms = defaults["heartbeat_interval_ms"]

        from app.clients.heartbeat_client import HeartbeatClient
        return HeartbeatClient()


def _mock_response(status_code=200, json_data=None):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


def _make_mock_http(response):
    """Create a mock httpx.AsyncClient context manager."""
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=response)
    return mock_http


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHeartbeatState:
    """HC-001 to HC-003: set_state, set_action_callback, set_access_key."""

    # HC-001: set_state stores state object
    def test_set_state(self):
        client = _make_client()
        state = MagicMock()
        client.set_state(state)
        assert client._state is state

    # HC-002: set_action_callback stores callback
    def test_set_action_callback(self):
        client = _make_client()
        cb = AsyncMock()
        client.set_action_callback(cb)
        assert client._action_callback is cb

    # HC-003: set_access_key stores key
    def test_set_access_key(self):
        client = _make_client()
        assert client._access_key is None
        client.set_access_key("sk_hb")
        assert client._access_key == "sk_hb"


class TestHeartbeatLifecycle:
    """HC-004 to HC-006: start and stop."""

    # HC-004: start creates asyncio task
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        client = _make_client()
        # Mock _heartbeat_loop to prevent actual execution
        client._heartbeat_loop = AsyncMock()

        await client.start()
        assert client._task is not None
        # Cleanup
        client._task.cancel()
        try:
            await client._task
        except asyncio.CancelledError:
            pass

    # HC-005: stop cancels task
    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        client = _make_client()
        client._heartbeat_loop = AsyncMock()

        await client.start()
        assert client._task is not None

        await client.stop()
        assert client._task.cancelled() or client._task.done()

    # HC-006: stop with no task does not raise
    @pytest.mark.asyncio
    async def test_stop_no_task(self):
        client = _make_client()
        assert client._task is None
        # Should not raise
        await client.stop()


class TestHeartbeatSend:
    """HC-007 to HC-013: _send_heartbeat behavior."""

    # HC-007: sends default payload when no state
    @pytest.mark.asyncio
    async def test_send_default_payload(self):
        client = _make_client(worker_instance_id="w-test")
        mock_resp = _mock_response(json_data={"action": "continue"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["instance_id"] == "w-test"
        assert payload["status"] == "idle"
        assert payload["current_job_id"] is None

    # HC-008: sends state data when state is set
    @pytest.mark.asyncio
    async def test_send_with_state(self):
        client = _make_client()
        state = MagicMock()
        state.to_heartbeat.return_value = {
            "status": "processing",
            "current_job_id": "job-42",
            "files_completed": 3,
            "files_total": 5,
            "error_count": 1,
        }
        client.set_state(state)

        mock_resp = _mock_response(json_data={"action": "continue"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["status"] == "processing"
        assert payload["current_job_id"] == "job-42"
        state.to_heartbeat.assert_called_once()

    # HC-009: sends X-Access-Key header when key is set
    @pytest.mark.asyncio
    async def test_send_with_access_key(self):
        client = _make_client()
        client.set_access_key("sk_heartbeat")

        mock_resp = _mock_response(json_data={"action": "continue"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()

        call_kwargs = mock_http.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["X-Access-Key"] == "sk_heartbeat"

    # HC-010: no X-Access-Key header when key is None
    @pytest.mark.asyncio
    async def test_send_without_access_key(self):
        client = _make_client(worker_access_key=None)

        mock_resp = _mock_response(json_data={"action": "continue"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()

        call_kwargs = mock_http.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert "X-Access-Key" not in headers

    # HC-011: invokes action callback with response data
    @pytest.mark.asyncio
    async def test_send_invokes_callback(self):
        client = _make_client()
        callback = AsyncMock()
        client.set_action_callback(callback)

        resp_data = {"action": "drain", "reason": "maintenance"}
        mock_resp = _mock_response(json_data=resp_data)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()

        callback.assert_awaited_once_with(resp_data)

    # HC-012: no callback set -> no error
    @pytest.mark.asyncio
    async def test_send_no_callback_ok(self):
        client = _make_client()
        assert client._action_callback is None

        mock_resp = _mock_response(json_data={"action": "continue"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            # Should not raise
            await client._send_heartbeat()

    # HC-013: HTTP error propagates from _send_heartbeat
    @pytest.mark.asyncio
    async def test_send_http_error(self):
        client = _make_client()

        mock_resp = _mock_response(status_code=503)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(httpx.HTTPStatusError):
                await client._send_heartbeat()

    # HC-014: 404 triggers re_register callback instead of raising
    @pytest.mark.asyncio
    async def test_send_404_triggers_re_register(self):
        client = _make_client()
        callback = AsyncMock()
        client.set_action_callback(callback)

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()  # Should NOT raise

        callback.assert_awaited_once_with({"action": "re_register"})

    # HC-015: 404 with no callback does not raise
    @pytest.mark.asyncio
    async def test_send_404_no_callback_ok(self):
        client = _make_client()
        assert client._action_callback is None

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.heartbeat_client.httpx.AsyncClient", return_value=mock_http):
            await client._send_heartbeat()  # Should not raise
