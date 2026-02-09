# GracefulShutdown: SIGTERM/SIGINT handler
# Finish current job or NAK, cleanup, exit

import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handles graceful shutdown on SIGTERM/SIGINT."""

    def __init__(self):
        self.is_shutting_down = False
        self._shutdown_event = asyncio.Event()

    async def handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal."""
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress, ignoring signal")
            return

        self.is_shutting_down = True
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown")

        # Wait for current job to complete or timeout
        # The main loop will check is_shutting_down and exit
        self._shutdown_event.set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
