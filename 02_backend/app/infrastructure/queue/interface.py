# IQueueService (abstract)

from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable

from .messages import JobMessage


class IQueueService(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """Connect to queue server."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from queue server."""
        pass

    @abstractmethod
    async def ensure_streams(self) -> None:
        """Ensure required streams exist."""
        pass

    @abstractmethod
    async def publish(self, subject: str, message: JobMessage) -> None:
        """Publish message to subject."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        subject: str,
        handler: Callable[[JobMessage], Awaitable[None]],
    ) -> None:
        """Subscribe to subject with handler."""
        pass

    @abstractmethod
    async def ack(self, message_id: str) -> None:
        """Acknowledge message."""
        pass

    @abstractmethod
    async def nak(self, message_id: str) -> None:
        """Negative acknowledge (requeue)."""
        pass
