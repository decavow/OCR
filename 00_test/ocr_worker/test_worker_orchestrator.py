"""Phase C — OrchestratorClient tests (mock httpx).

Tests OC-001 through OC-012: register, deregister, and update_status.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**overrides):
    """Create an OrchestratorClient with mocked settings."""
    defaults = {
        "orchestrator_url": "http://backend:8000/api/v1/internal",
        "worker_access_key": None,
    }
    defaults.update(overrides)

    with patch("app.clients.orchestrator_client.settings") as mock_settings:
        mock_settings.orchestrator_url = defaults["orchestrator_url"]
        mock_settings.worker_access_key = defaults["worker_access_key"]

        from app.clients.orchestrator_client import OrchestratorClient
        return OrchestratorClient()


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
    mock_http.patch = AsyncMock(return_value=response)
    return mock_http


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestratorRegister:
    """OC-001 to OC-004: register."""

    # OC-001: register sends correct payload
    @pytest.mark.asyncio
    async def test_register_payload(self):
        client = _make_client()
        mock_resp = _mock_response(json_data={
            "type_status": "APPROVED",
            "instance_status": "ACTIVE",
            "access_key": "sk_new",
        })
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.register(
                service_type="ocr-text-tier0",
                instance_id="worker-1",
                display_name="Test Worker",
                description="A test worker",
                allowed_methods=["ocr_paddle_text"],
                allowed_tiers=[0],
            )

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["service_type"] == "ocr-text-tier0"
        assert payload["instance_id"] == "worker-1"
        assert payload["allowed_methods"] == ["ocr_paddle_text"]
        assert payload["allowed_tiers"] == [0]

    # OC-002: register returns response dict
    @pytest.mark.asyncio
    async def test_register_returns_dict(self):
        client = _make_client()
        expected = {
            "type_status": "PENDING",
            "instance_status": "ACTIVE",
        }
        mock_resp = _mock_response(json_data=expected)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.register(
                service_type="ocr-text-tier0",
                instance_id="w1",
                display_name="W1",
                description="",
                allowed_methods=["ocr_paddle_text"],
                allowed_tiers=[0],
            )

        assert result == expected

    # OC-003: register includes optional fields
    @pytest.mark.asyncio
    async def test_register_optional_fields(self):
        client = _make_client()
        mock_resp = _mock_response(json_data={"type_status": "APPROVED"})
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.register(
                service_type="ocr",
                instance_id="w1",
                display_name="W1",
                description="desc",
                allowed_methods=["ocr_paddle_text"],
                allowed_tiers=[0],
                dev_contact="dev@example.com",
                engine_info={"engine": "paddle", "version": "2.7.3"},
                supported_output_formats=["txt", "json"],
            )

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["dev_contact"] == "dev@example.com"
        assert payload["engine_info"]["engine"] == "paddle"
        assert payload["supported_output_formats"] == ["txt", "json"]

    # OC-004: register HTTP error raises
    @pytest.mark.asyncio
    async def test_register_http_error(self):
        client = _make_client()
        mock_resp = _mock_response(status_code=500)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(httpx.HTTPStatusError):
                await client.register(
                    service_type="ocr",
                    instance_id="w1",
                    display_name="W1",
                    description="",
                    allowed_methods=["ocr_paddle_text"],
                    allowed_tiers=[0],
                )


class TestOrchestratorDeregister:
    """OC-005 to OC-006: deregister."""

    # OC-005: deregister sends instance_id
    @pytest.mark.asyncio
    async def test_deregister_sends_id(self):
        client = _make_client()
        mock_resp = _mock_response(status_code=200)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.deregister("worker-1")

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["instance_id"] == "worker-1"

    # OC-006: deregister swallows errors
    @pytest.mark.asyncio
    async def test_deregister_swallows_errors(self):
        client = _make_client()
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=ConnectionError("offline"))

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            # Should not raise
            await client.deregister("worker-1")


class TestOrchestratorUpdateStatus:
    """OC-007 to OC-012: update_status."""

    # OC-007: update_status PROCESSING
    @pytest.mark.asyncio
    async def test_update_processing(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(status_code=200)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.update_status("job-1", "PROCESSING")

        call_kwargs = mock_http.patch.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["status"] == "PROCESSING"
        assert "error" not in payload

    # OC-008: update_status COMPLETED with engine_version
    @pytest.mark.asyncio
    async def test_update_completed_with_version(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(status_code=200)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.update_status("job-1", "COMPLETED", engine_version="paddleocr 2.7.3")

        call_kwargs = mock_http.patch.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["status"] == "COMPLETED"
        assert payload["engine_version"] == "paddleocr 2.7.3"

    # OC-009: update_status FAILED with error and retriable
    @pytest.mark.asyncio
    async def test_update_failed_retriable(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(status_code=200)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.update_status(
                "job-1", "FAILED", error="timeout", retriable=True,
            )

        call_kwargs = mock_http.patch.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["status"] == "FAILED"
        assert payload["error"] == "timeout"
        assert payload["retriable"] is True

    # OC-010: update_status sends access key header
    @pytest.mark.asyncio
    async def test_update_sends_access_key(self):
        client = _make_client()
        client.set_access_key("sk_header")

        mock_resp = _mock_response(status_code=200)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            await client.update_status("job-1", "PROCESSING")

        call_kwargs = mock_http.patch.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["X-Access-Key"] == "sk_header"

    # OC-011: update_status no access key -> raises
    @pytest.mark.asyncio
    async def test_update_no_access_key(self):
        client = _make_client(worker_access_key=None)

        with pytest.raises(RuntimeError, match="Access key not set"):
            await client.update_status("job-1", "PROCESSING")

    # OC-012: update_status HTTP error -> raises
    @pytest.mark.asyncio
    async def test_update_http_error_raises(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(status_code=500)
        mock_http = _make_mock_http(mock_resp)

        with patch("app.clients.orchestrator_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(httpx.HTTPStatusError):
                await client.update_status("job-1", "PROCESSING")
