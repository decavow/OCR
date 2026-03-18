# NATS pull subscriber (specific subject filter)

import json
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

import nats
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, AckPolicy

from app.config import settings

logger = logging.getLogger(__name__)

# Pending message TTL: auto-cleanup entries older than this (seconds)
_PENDING_MSG_TTL = 3600  # 1 hour


@dataclass
class JobMessage:
    """Parsed job message from NATS."""
    job_id: str
    file_id: str
    request_id: str
    method: str
    tier: int
    output_format: str
    object_key: str
    _msg: Any  # Original NATS message for ack/nak


class QueueClient:
    """NATS JetStream pull subscriber for OCR jobs."""

    STREAM_NAME = "OCR_JOBS"

    def __init__(self):
        self.nc = None
        self.js: JetStreamContext = None
        self.subscription = None
        self._pending_messages: Dict[str, tuple] = {}  # msg_id -> (nats_msg, timestamp)

    def _cleanup_stale_pending(self) -> None:
        """Remove pending messages older than TTL to prevent memory leak."""
        now = time.monotonic()
        stale = [
            mid for mid, (_, ts) in self._pending_messages.items()
            if now - ts > _PENDING_MSG_TTL
        ]
        for mid in stale:
            self._pending_messages.pop(mid, None)
            logger.warning(f"Cleaned up stale pending message: {mid}")

    async def connect(self) -> None:
        """Connect to NATS and create pull subscription."""
        logger.info(f"Connecting to NATS at {settings.nats_url}")
        self.nc = await nats.connect(
            settings.nats_url,
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
        )
        self.js = self.nc.jetstream()

        # Use service TYPE (not instance ID) for consumer name
        # This allows multiple workers to share the same consumer = load balancing
        consumer_name = settings.worker_service_type.replace("-", "_")

        # Create pull subscription with filter
        # filter_subject: e.g., "ocr.ocr_paddle_text.tier0"
        logger.info(f"Subscribing to {settings.worker_filter_subject} with consumer {consumer_name}")

        self.subscription = await self.js.pull_subscribe(
            subject=settings.worker_filter_subject,
            durable=consumer_name,
            stream=self.STREAM_NAME,
        )

        logger.info("Connected to NATS JetStream")

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self.nc:
            logger.info("Disconnecting from NATS")
            await self.nc.drain()
            self.nc = None

    async def pull_job(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Pull next job from queue.

        Returns dict with job fields plus _msg_id for ack/nak.
        Returns None if no message available.
        """
        if not self.subscription:
            return None

        try:
            messages = await self.subscription.fetch(batch=1, timeout=timeout)
            if not messages:
                return None

            msg = messages[0]

            # Parse message data
            data = json.loads(msg.data.decode())

            # Generate unique message id
            msg_id = f"{msg.metadata.sequence.stream}_{msg.metadata.sequence.consumer}"

            # Store message for ack/nak (with timestamp for TTL cleanup)
            self._pending_messages[msg_id] = (msg, time.monotonic())

            # Periodically cleanup stale entries
            if len(self._pending_messages) > 10:
                self._cleanup_stale_pending()

            logger.info(f"Pulled job {data.get('job_id')} from queue")

            # Return job data with message id
            return {
                "job_id": data["job_id"],
                "file_id": data["file_id"],
                "request_id": data["request_id"],
                "method": data["method"],
                "tier": data["tier"],
                "output_format": data["output_format"],
                "object_key": data["object_key"],
                "_msg_id": msg_id,
            }

        except nats.errors.TimeoutError:
            # No messages available
            return None
        except Exception as e:
            logger.error(f"Error pulling job: {e}")
            return None

    async def ack(self, msg_id: str) -> None:
        """Acknowledge message as successfully processed."""
        entry = self._pending_messages.pop(msg_id, None)
        if entry:
            msg, _ = entry
            await msg.ack()
            logger.debug(f"Acked message {msg_id}")

    async def nak(self, msg_id: str, delay: float = None) -> None:
        """
        Negative acknowledge - requeue message.

        Args:
            msg_id: Message identifier
            delay: Optional delay in seconds before redelivery
        """
        entry = self._pending_messages.pop(msg_id, None)
        if entry:
            msg, _ = entry
            if delay:
                await msg.nak(delay=delay)
            else:
                await msg.nak()
            logger.debug(f"Naked message {msg_id}")

    async def term(self, msg_id: str) -> None:
        """
        Terminate message - do not redeliver.
        Use for permanently failed jobs.
        """
        entry = self._pending_messages.pop(msg_id, None)
        if entry:
            msg, _ = entry
            await msg.term()
            logger.debug(f"Terminated message {msg_id}")
