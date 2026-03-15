"""Phase C — FileProxyClient tests (mock httpx).

Tests FPC-001 through FPC-012: initialization, access key management,
download and upload operations.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**overrides):
    """Create a FileProxyClient with mocked settings."""
    defaults = {
        "file_proxy_url": "http://backend:8000/api/v1/internal/file-proxy",
        "worker_access_key": None,
    }
    defaults.update(overrides)

    with patch("app.clients.file_proxy_client.settings") as mock_settings:
        mock_settings.file_proxy_url = defaults["file_proxy_url"]
        mock_settings.worker_access_key = defaults["worker_access_key"]

        from app.clients.file_proxy_client import FileProxyClient
        return FileProxyClient()


def _mock_response(status_code=200, content=b"file bytes", headers=None, json_data=None):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {}
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileProxyClient:
    """FPC-001 to FPC-012."""

    # FPC-001: Initialized with config values
    def test_init_uses_config(self):
        client = _make_client(
            file_proxy_url="http://custom:9000/proxy",
            worker_access_key="sk_init",
        )
        assert client.base_url == "http://custom:9000/proxy"
        assert client._access_key == "sk_init"

    # FPC-002: set_access_key stores key
    def test_set_access_key(self):
        client = _make_client()
        assert client._access_key is None
        client.set_access_key("sk_new")
        assert client._access_key == "sk_new"

    # FPC-003: has_access_key no key -> False
    def test_has_access_key_false(self):
        client = _make_client(worker_access_key=None)
        assert client.has_access_key is False

    # FPC-004: has_access_key key set -> True
    def test_has_access_key_true(self):
        client = _make_client(worker_access_key="sk_exists")
        assert client.has_access_key is True

    # FPC-005: download valid -> returns tuple
    @pytest.mark.asyncio
    async def test_download_valid(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(
            content=b"image data",
            headers={"X-Content-Type": "image/png", "X-File-Name": "photo.png"},
        )

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            content, ct, fname = await client.download("job-1", "file-1")

        assert content == b"image data"
        assert ct == "image/png"
        assert fname == "photo.png"

    # FPC-006: download no access key -> error
    @pytest.mark.asyncio
    async def test_download_no_access_key(self):
        client = _make_client(worker_access_key=None)

        with pytest.raises(RuntimeError, match="Access key not set"):
            await client.download("job-1", "file-1")

    # FPC-007: download HTTP error -> raises
    @pytest.mark.asyncio
    async def test_download_http_error(self):
        client = _make_client()
        client.set_access_key("sk_test")

        mock_resp = _mock_response(status_code=500)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(httpx.HTTPStatusError):
                await client.download("job-1", "file-1")

    # FPC-008: download sends X-Access-Key header
    @pytest.mark.asyncio
    async def test_download_sends_access_key_header(self):
        client = _make_client()
        client.set_access_key("sk_header_test")

        mock_resp = _mock_response(
            content=b"data",
            headers={"X-Content-Type": "image/jpeg", "X-File-Name": "img.jpg"},
        )

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            await client.download("job-1", "file-1")

        call_kwargs = mock_http.post.call_args
        assert call_kwargs.kwargs["headers"]["X-Access-Key"] == "sk_header_test"

    # FPC-009: upload valid -> result_key
    @pytest.mark.asyncio
    async def test_upload_valid(self):
        client = _make_client()
        client.set_access_key("sk_upload")

        mock_resp = _mock_response(
            json_data={"result_key": "results/job-1/file-1/output.txt"},
        )

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            key = await client.upload("job-1", "file-1", b"result text", "text/plain")

        assert key == "results/job-1/file-1/output.txt"

    # FPC-010: upload content base64 encoded
    @pytest.mark.asyncio
    async def test_upload_content_base64(self):
        client = _make_client()
        client.set_access_key("sk_b64")

        raw_content = b"Hello OCR result"
        expected_b64 = base64.b64encode(raw_content).decode()

        mock_resp = _mock_response(json_data={"result_key": "key"})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            await client.upload("job-1", "file-1", raw_content, "text/plain")

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["content"] == expected_b64

    # FPC-011: upload no access key -> error
    @pytest.mark.asyncio
    async def test_upload_no_access_key(self):
        client = _make_client(worker_access_key=None)

        with pytest.raises(RuntimeError, match="Access key not set"):
            await client.upload("job-1", "file-1", b"data", "text/plain")

    # FPC-012: upload sends X-Access-Key header
    @pytest.mark.asyncio
    async def test_upload_sends_access_key_header(self):
        client = _make_client()
        client.set_access_key("sk_upload_header")

        mock_resp = _mock_response(json_data={"result_key": "key"})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.clients.file_proxy_client.httpx.AsyncClient", return_value=mock_http):
            await client.upload("job-1", "file-1", b"data", "text/plain")

        call_kwargs = mock_http.post.call_args
        assert call_kwargs.kwargs["headers"]["X-Access-Key"] == "sk_upload_header"
