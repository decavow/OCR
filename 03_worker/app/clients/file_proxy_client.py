# HTTP client: POST /internal/file-proxy/download|upload

import base64
import logging
from typing import Optional, Tuple
from urllib.parse import unquote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout scales: large files need more time
_DOWNLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)  # 5 min for large downloads
_UPLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)    # 5 min for large uploads
# Max file size we'll process in memory (500 MB)
_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class FileProxyClient:
    """HTTP client for file proxy endpoints."""

    def __init__(self):
        self.base_url = settings.file_proxy_url
        self._access_key: Optional[str] = settings.worker_access_key

    def set_access_key(self, key: str) -> None:
        """Set access key after approval."""
        self._access_key = key

    @property
    def has_access_key(self) -> bool:
        """Check if access key is set."""
        return self._access_key is not None

    async def download(self, job_id: str, file_id: str) -> Tuple[bytes, str, str]:
        """
        Download file for processing.

        Args:
            job_id: Job identifier
            file_id: File identifier

        Returns:
            Tuple of (content, content_type, filename)
        """
        if not self._access_key:
            raise RuntimeError("Access key not set - not approved yet")

        logger.info(f"Downloading file {file_id} for job {job_id}")

        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/download",
                json={"job_id": job_id, "file_id": file_id},
                headers={"X-Access-Key": self._access_key},
            )
            response.raise_for_status()

            content = response.content
            content_len = len(content)

            if content_len > _MAX_FILE_SIZE_BYTES:
                raise RuntimeError(
                    f"File too large ({content_len} bytes, max {_MAX_FILE_SIZE_BYTES}). "
                    "Reduce file size or increase worker memory."
                )

            # Extract metadata from headers
            content_type = response.headers.get("X-Content-Type", "application/octet-stream")
            filename = unquote(response.headers.get("X-File-Name", "unknown"))

            logger.debug(f"Downloaded {content_len} bytes, type={content_type}")

            return content, content_type, filename

    async def upload(
        self,
        job_id: str,
        file_id: str,
        content: bytes,
        content_type: str = "text/plain",
    ) -> str:
        """
        Upload result to storage.

        Args:
            job_id: Job identifier
            file_id: File identifier
            content: Result content bytes
            content_type: MIME type of result

        Returns:
            Result object key
        """
        if not self._access_key:
            raise RuntimeError("Access key not set - not approved yet")

        logger.info(f"Uploading result for job {job_id}, size={len(content)}")

        async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/upload",
                json={
                    "job_id": job_id,
                    "file_id": file_id,
                    "content": base64.b64encode(content).decode(),
                    "content_type": content_type,
                },
                headers={"X-Access-Key": self._access_key},
            )
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Upload successful: {result.get('result_key')}")

            return result.get("result_key", "")
