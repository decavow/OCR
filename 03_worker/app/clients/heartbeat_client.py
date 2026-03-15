# HTTP client: POST /internal/heartbeat (every 30s)

import asyncio
import logging
from typing import Optional, Callable, Awaitable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class HeartbeatClient:
    """Heartbeat client for worker health reporting."""

    def __init__(self):
        self.base_url = settings.orchestrator_url
        self._access_key: Optional[str] = settings.worker_access_key
        self.instance_id = settings.worker_instance_id
        self.interval_ms = settings.heartbeat_interval_ms
        self._task = None
        self._state = None
        self._action_callback: Optional[Callable[[dict], Awaitable[None]]] = None
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    def set_access_key(self, key: str) -> None:
        """Set access key after approval."""
        self._access_key = key

    def set_action_callback(self, callback: Callable[[dict], Awaitable[None]]) -> None:
        """Set callback for handling heartbeat action responses."""
        self._action_callback = callback

    def set_state(self, state) -> None:
        """Set worker state for heartbeat payload."""
        self._state = state

    async def start(self) -> None:
        """Start heartbeat loop."""
        logger.info(f"Starting heartbeat (interval: {self.interval_ms}ms)")
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop heartbeat loop."""
        logger.info("Stopping heartbeat")
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every interval."""
        while True:
            try:
                await self._send_heartbeat()
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")

            await asyncio.sleep(self.interval_ms / 1000)

    async def _send_heartbeat(self) -> None:
        """Send single heartbeat."""
        payload = {
            "instance_id": self.instance_id,
            "status": "idle",
            "current_job_id": None,
            "files_completed": 0,
            "files_total": 0,
            "error_count": 0,
        }

        if self._state:
            payload.update(self._state.to_heartbeat())

        # Build headers - include access_key only if we have one
        headers = {}
        if self._access_key:
            headers["X-Access-Key"] = self._access_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/heartbeat",
                json=payload,
                headers=headers,
            )

            # 404 = instance not found → need to re-register
            if response.status_code == 404:
                logger.warning(
                    "Instance not found on backend (404). Triggering re-registration."
                )
                if self._action_callback:
                    await self._action_callback({"action": "re_register"})
                return

            response.raise_for_status()

            # Parse response and handle action
            data = response.json()
            action = data.get("action", "continue")
            logger.debug(f"Heartbeat sent, action={action}")

            # Notify worker of action via callback
            if self._action_callback:
                await self._action_callback(data)
