# IStorageService (abstract)
# NOTE: Used by Edge layer (Upload via API context)
# and Orchestration layer (File Proxy with credentials).
# Processing layer MUST NOT import this module.

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List, BinaryIO


class IStorageService(ABC):
    @abstractmethod
    async def ensure_buckets(self) -> None:
        """Ensure all required buckets exist."""
        pass

    @abstractmethod
    async def bucket_exists(self, bucket: str) -> bool:
        """Check if bucket exists."""
        pass

    @abstractmethod
    async def upload(
        self,
        bucket: str,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """Upload file to storage."""
        pass

    @abstractmethod
    async def upload_stream(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        length: int,
        content_type: str,
    ) -> None:
        """Upload from stream to storage."""
        pass

    @abstractmethod
    async def download(self, bucket: str, object_key: str) -> bytes:
        """Download file from storage."""
        pass

    @abstractmethod
    async def exists(self, bucket: str, object_key: str) -> bool:
        """Check if object exists."""
        pass

    @abstractmethod
    async def list_objects(
        self,
        bucket: str,
        prefix: str,
        recursive: bool,
    ) -> List[str]:
        """List objects in bucket with optional prefix."""
        pass

    @abstractmethod
    async def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires: timedelta,
    ) -> str:
        """Generate presigned URL for download."""
        pass

    @abstractmethod
    async def get_presigned_upload_url(
        self,
        bucket: str,
        object_key: str,
        expires: timedelta,
    ) -> str:
        """Generate presigned URL for upload."""
        pass

    @abstractmethod
    async def move(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Move object between buckets."""
        pass

    @abstractmethod
    async def copy(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Copy object between buckets."""
        pass

    @abstractmethod
    async def delete(self, bucket: str, object_key: str) -> None:
        """Delete object."""
        pass

    @abstractmethod
    async def delete_many(self, bucket: str, object_keys: List[str]) -> None:
        """Delete multiple objects."""
        pass
