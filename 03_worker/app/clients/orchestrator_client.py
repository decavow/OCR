# HTTP client for orchestrator endpoints

import logging
from typing import Optional, List, Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OrchestratorClient:
    """HTTP client for orchestrator endpoints."""

    def __init__(self):
        self.base_url = settings.orchestrator_url
        self._access_key: Optional[str] = settings.worker_access_key
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def set_access_key(self, key: str) -> None:
        """Set access key after approval."""
        self._access_key = key

    @property
    def has_access_key(self) -> bool:
        """Check if access key is set."""
        return self._access_key is not None

    async def register(
        self,
        service_type: str,
        instance_id: str,
        display_name: str,
        description: str,
        allowed_methods: List[str],
        allowed_tiers: List[int],
        dev_contact: Optional[str] = None,
        engine_info: Optional[Dict[str, Any]] = None,
        supported_output_formats: Optional[List[str]] = None,
    ) -> dict:
        """
        Register instance with backend.

        Returns:
            Response with instance_status, type_status, and optionally access_key
        """
        logger.info(f"Registering instance {instance_id} (type: {service_type})")

        payload = {
            "service_type": service_type,
            "instance_id": instance_id,
            "display_name": display_name,
            "description": description,
            "allowed_methods": allowed_methods,
            "allowed_tiers": allowed_tiers,
        }
        if dev_contact:
            payload["dev_contact"] = dev_contact
        if engine_info:
            payload["engine_info"] = engine_info
        if supported_output_formats:
            payload["supported_output_formats"] = supported_output_formats

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/register",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def deregister(self, instance_id: str) -> None:
        """Deregister instance on shutdown."""
        logger.info(f"Deregistering instance {instance_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/deregister",
                    json={"instance_id": instance_id},
                )
                # Ignore errors on deregister - best effort
                if response.status_code == 200:
                    logger.debug("Deregistered successfully")
        except Exception as e:
            logger.warning(f"Failed to deregister: {e}")

    async def update_status(
        self,
        job_id: str,
        status: str,
        error: str = None,
        retriable: bool = True,
    ) -> None:
        """
        Update job status in orchestrator.

        Args:
            job_id: Job identifier
            status: New status (PROCESSING, COMPLETED, FAILED)
            error: Error message if failed
            retriable: Whether the job can be retried
        """
        logger.info(f"Updating job {job_id} status to {status}")

        payload = {"status": status}
        if error:
            payload["error"] = error
            payload["retriable"] = retriable

        if not self._access_key:
            raise RuntimeError("Access key not set - not approved yet")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.base_url}/jobs/{job_id}/status",
                    json=payload,
                    headers={"X-Access-Key": self._access_key},
                )
                response.raise_for_status()
                logger.debug(f"Status updated successfully")

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update status: HTTP {e.response.status_code}")
            raise

        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            raise
