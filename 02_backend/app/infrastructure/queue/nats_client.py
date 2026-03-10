# NATSQueueService: publish, subscribe, ack, nak

import json
import logging
from typing import Callable, Awaitable, Optional
import nats
from nats.js import JetStreamContext

from app.config import settings
from .interface import IQueueService
from .messages import JobMessage
from .subjects import get_subject

logger = logging.getLogger(__name__)


class NATSQueueService(IQueueService):
    """NATS JetStream queue service."""

    def __init__(self, url: str = None):
        self.url = url or settings.nats_url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.nc is not None and self.nc.is_connected

    async def connect(self) -> None:
        """Connect to NATS server."""
        try:
            self.nc = await nats.connect(self.url)
            self.js = self.nc.jetstream()
            self._connected = True
            logger.info(f"Connected to NATS at {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            try:
                await self.nc.drain()
                self._connected = False
                logger.info("Disconnected from NATS")
            except Exception as e:
                logger.warning(f"Error disconnecting from NATS: {e}")

    async def ensure_streams(self) -> None:
        """Ensure required streams exist."""
        if not self.js:
            raise RuntimeError("Not connected to NATS")

        # Main job stream - captures all ocr.* subjects
        await self._ensure_stream(
            name=settings.nats_stream_name,
            subjects=["ocr.>"],
        )

        # Dead Letter Queue stream
        await self._ensure_stream(
            name=settings.nats_dlq_stream_name,
            subjects=["dlq.>"],
        )

        logger.info("NATS streams verified")

    async def _ensure_stream(self, name: str, subjects: list[str]) -> None:
        """Ensure a stream exists, create if not."""
        try:
            await self.js.stream_info(name)
            logger.debug(f"Stream {name} already exists")
        except Exception:
            # Create new stream
            try:
                await self.js.add_stream(name=name, subjects=subjects)
                logger.info(f"Created stream: {name}")
            except Exception as e:
                logger.warning("Failed to create stream %s: %s", name, e)

    async def publish(self, subject: str, message: JobMessage) -> None:
        """Publish job message to subject."""
        if not self.js:
            raise RuntimeError("Not connected to NATS")

        data = json.dumps(message.to_dict()).encode()
        ack = await self.js.publish(subject, data)
        logger.debug(f"Published to {subject}: job_id={message.job_id}, seq={ack.seq}")

    async def publish_job(
        self,
        job_id: str,
        file_id: str,
        request_id: str,
        method: str,
        tier: int,
        output_format: str,
        object_key: str,
    ) -> None:
        """Convenience method to publish a job."""
        subject = get_subject(method, tier)
        message = JobMessage(
            job_id=job_id,
            file_id=file_id,
            request_id=request_id,
            method=method,
            tier=tier,
            output_format=output_format,
            object_key=object_key,
        )
        await self.publish(subject, message)
        logger.info(f"Published job {job_id} to {subject}")

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[JobMessage], Awaitable[None]],
        durable: str = None,
    ) -> None:
        """Subscribe to subject with handler (pull-based)."""
        if not self.js:
            raise RuntimeError("Not connected to NATS")

        # Create pull subscription
        sub = await self.js.pull_subscribe(
            subject,
            durable=durable or f"worker-{subject.replace('.', '-')}",
        )

        logger.info(f"Subscribed to {subject}")

        # Start consuming in background
        while True:
            try:
                msgs = await sub.fetch(batch=1, timeout=5)
                for msg in msgs:
                    try:
                        data = json.loads(msg.data.decode())
                        job_message = JobMessage.from_dict(data)
                        await handler(job_message)
                        await msg.ack()
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await msg.nak()
            except nats.errors.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in subscription loop: {e}")
                break

    async def ack(self, message_id: str) -> None:
        """Acknowledge message (handled inline in subscribe)."""
        pass

    async def nak(self, message_id: str) -> None:
        """Negative acknowledge (handled inline in subscribe)."""
        pass
