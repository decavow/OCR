# OCRWorker class (poll -> download -> process -> upload loop)

import asyncio
import logging
from typing import Optional

from app.config import settings
from app.core.shutdown import GracefulShutdown
from app.core.processor import OCRProcessor
from app.core.state import WorkerState
from app.clients.queue_client import QueueClient
from app.clients.file_proxy_client import FileProxyClient
from app.clients.orchestrator_client import OrchestratorClient
from app.clients.heartbeat_client import HeartbeatClient
from app.utils.errors import RetriableError, PermanentError

logger = logging.getLogger(__name__)


class OCRWorker:
    """Main OCR worker class."""

    def __init__(self, shutdown_handler: GracefulShutdown):
        self.shutdown = shutdown_handler
        self.state = WorkerState()
        self.processor = OCRProcessor()

        # Clients
        self.queue = QueueClient()
        self.file_proxy = FileProxyClient()
        self.orchestrator = OrchestratorClient()
        self.heartbeat = HeartbeatClient()

        # Approval state
        self._access_key: Optional[str] = settings.worker_access_key
        self.is_approved = self._access_key is not None
        self.is_draining = False

    async def start(self) -> None:
        """Start worker: register and connect to services."""
        logger.info(f"Starting worker {settings.worker_instance_id}")
        logger.info(f"Service type: {settings.worker_service_type}")
        logger.info(f"Subscribing to: {settings.worker_filter_subject}")

        # Step 1: Register with backend
        try:
            reg_result = await self._register()

            if reg_result.get("type_status") == "REJECTED":
                logger.error("Service type has been REJECTED. Shutting down.")
                self.shutdown.is_shutting_down = True
                return

            # If type is already approved, we get access_key immediately
            if reg_result.get("access_key"):
                self._set_access_key(reg_result["access_key"])
                logger.info("Service type already approved. Ready to process jobs.")
            else:
                logger.info(
                    f"Service type status: {reg_result.get('type_status')}. "
                    "Waiting for approval..."
                )

        except Exception as e:
            logger.error(f"Registration failed: {e}")
            # Continue anyway - heartbeat will handle re-registration
            logger.info("Will retry registration via heartbeat...")

        # Step 2: Connect to queue
        await self.queue.connect()

        # Step 3: Start heartbeat with action callback
        self.heartbeat.set_state(self.state)
        self.heartbeat.set_action_callback(self._handle_heartbeat_action)
        await self.heartbeat.start()

        logger.info("Worker started successfully")

    async def _register(self) -> dict:
        """Register instance with backend."""
        return await self.orchestrator.register(
            service_type=settings.worker_service_type,
            instance_id=settings.worker_instance_id,
            display_name=settings.worker_display_name,
            description=settings.worker_description,
            allowed_methods=settings.worker_allowed_methods,
            allowed_tiers=settings.worker_allowed_tiers,
            dev_contact=settings.worker_dev_contact,
            engine_info=self.processor.get_engine_info()
            if hasattr(self.processor, "get_engine_info")
            else None,
            supported_output_formats=settings.worker_supported_formats,
        )

    def _set_access_key(self, key: str) -> None:
        """Set access key on worker and all clients."""
        self._access_key = key
        self.is_approved = True
        self.orchestrator.set_access_key(key)
        self.file_proxy.set_access_key(key)
        self.heartbeat.set_access_key(key)

    async def _handle_heartbeat_action(self, response: dict) -> None:
        """Handle action from heartbeat response."""
        action = response.get("action", "continue")

        if action == "continue":
            pass  # No change

        elif action == "approved":
            # First time receiving approval
            access_key = response.get("access_key")
            if access_key:
                self._set_access_key(access_key)
                logger.info("Service type APPROVED! Starting job processing.")
            else:
                logger.warning("Received 'approved' action but no access_key in response")

        elif action == "drain":
            # Finish current job, don't take new ones
            if not self.is_draining:
                logger.warning("Received DRAIN signal. Finishing current work...")
                self.is_draining = True

        elif action == "shutdown":
            reason = response.get("rejection_reason", "Unknown")
            logger.error(f"Received SHUTDOWN signal. Reason: {reason}")
            await self._graceful_shutdown()

    async def _graceful_shutdown(self) -> None:
        """Cleanup and exit."""
        # Deregister instance
        try:
            await self.orchestrator.deregister(settings.worker_instance_id)
        except Exception as e:
            logger.warning(f"Failed to deregister: {e}")

        self.shutdown.is_shutting_down = True

    async def stop(self) -> None:
        """Stop worker: cleanup and disconnect."""
        logger.info("Stopping worker...")

        await self.heartbeat.stop()
        await self.queue.disconnect()

        # Deregister on clean shutdown
        try:
            await self.orchestrator.deregister(settings.worker_instance_id)
        except Exception as e:
            logger.warning(f"Failed to deregister on shutdown: {e}")

        logger.info("Worker stopped")

    async def run(self) -> None:
        """Main job processing loop."""
        logger.info("Entering main processing loop")

        while not self.shutdown.is_shutting_down:
            try:
                # Only poll if approved and not draining
                if not self.is_approved:
                    logger.debug("Waiting for approval...")
                    await asyncio.sleep(5)
                    continue

                if self.is_draining:
                    logger.debug("Draining mode - not accepting new jobs")
                    await asyncio.sleep(5)
                    continue

                # Poll for job with timeout
                job = await self.queue.pull_job(timeout=5.0)

                if not job:
                    # No job available, continue polling
                    continue

                # Process job
                await self.process_job(job)

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Exiting main loop (shutdown requested)")

    async def process_job(self, job: dict) -> None:
        """Process a single job."""
        job_id = job["job_id"]
        file_id = job["file_id"]
        msg_id = job["_msg_id"]

        logger.info(f"Processing job {job_id}")

        try:
            # Update state
            self.state.start_job(job_id)

            # Download file via File Proxy
            logger.debug(f"Downloading file {file_id}")
            file_content, content_type, filename = await self.file_proxy.download(
                job_id, file_id
            )
            logger.info(f"Downloaded {filename} ({len(file_content)} bytes)")

            # Process OCR
            logger.debug(f"Running OCR (method={job['method']}, format={job['output_format']})")
            result = await self.processor.process(
                file_content=file_content,
                output_format=job["output_format"],
                method=job["method"],
            )
            logger.info(f"OCR complete, result size: {len(result)} bytes")

            # Determine result content type
            fmt = job["output_format"]
            if fmt == "json":
                result_content_type = "application/json"
            elif fmt == "md":
                result_content_type = "text/markdown"
            else:
                result_content_type = "text/plain"

            # Upload result via File Proxy
            logger.debug("Uploading result")
            await self.file_proxy.upload(
                job_id=job_id,
                file_id=file_id,
                content=result,
                content_type=result_content_type,
            )

            # Report success to orchestrator (include engine version)
            engine_info = self.processor.get_engine_info() if hasattr(self.processor, "get_engine_info") else {}
            engine_ver = f"{engine_info.get('engine', 'unknown')} {engine_info.get('version', '')}" if engine_info else None
            await self.orchestrator.update_status(job_id, "COMPLETED", engine_version=engine_ver)

            # Ack message
            await self.queue.ack(msg_id)

            logger.info(f"Job {job_id} completed successfully")

        except RetriableError as e:
            logger.warning(f"Job {job_id} failed (retriable): {e}")
            await self._handle_failure(job_id, msg_id, e, retriable=True)

        except PermanentError as e:
            logger.error(f"Job {job_id} failed (permanent): {e}")
            await self._handle_failure(job_id, msg_id, e, retriable=False)

        except Exception as e:
            logger.error(f"Job {job_id} failed (unexpected): {e}", exc_info=True)
            await self._handle_failure(job_id, msg_id, e, retriable=True)

        finally:
            self.state.end_job()

    async def _handle_failure(
        self,
        job_id: str,
        msg_id: str,
        error: Exception,
        retriable: bool,
    ) -> None:
        """Handle job failure."""
        try:
            # Report failure to orchestrator
            await self.orchestrator.update_status(
                job_id=job_id,
                status="FAILED",
                error=str(error),
                retriable=retriable,
            )
        except Exception as e:
            logger.error(f"Failed to report status: {e}")

        # Nak or term the message
        if retriable:
            await self.queue.nak(msg_id, delay=5.0)  # Retry after 5 seconds
        else:
            await self.queue.term(msg_id)  # Don't retry
