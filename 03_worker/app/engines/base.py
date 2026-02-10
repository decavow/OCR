# BaseHandler (interface for all OCR engines)

from abc import ABC, abstractmethod


class BaseHandler(ABC):
    @abstractmethod
    async def process(self, file_content: bytes, output_format: str) -> bytes:
        """Process file and return result."""
        pass
