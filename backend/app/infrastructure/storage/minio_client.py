# MinIOStorageService: upload, download, presigned_url, move_to_deleted

import logging
from datetime import timedelta
from io import BytesIO
from typing import Optional, List, BinaryIO
from dataclasses import dataclass

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import CopySource

from app.config import settings
from .interface import IStorageService
from .exceptions import (
    StorageError,
    ObjectNotFoundError,
    BucketNotFoundError,
    UploadError,
    DownloadError,
)

logger = logging.getLogger(__name__)


@dataclass
class ObjectInfo:
    """Information about a storage object."""
    bucket: str
    key: str
    size: int
    content_type: str
    etag: str
    last_modified: str


class MinIOStorageService(IStorageService):
    """MinIO implementation of storage service."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = None,
    ):
        self.endpoint = endpoint or settings.minio_endpoint
        self.client = Minio(
            self.endpoint,
            access_key=access_key or settings.minio_access_key,
            secret_key=secret_key or settings.minio_secret_key,
            secure=secure if secure is not None else settings.minio_secure,
        )
        self._buckets = {
            "uploads": settings.minio_bucket_uploads,
            "results": settings.minio_bucket_results,
            "deleted": settings.minio_bucket_deleted,
        }

    @property
    def uploads_bucket(self) -> str:
        return self._buckets["uploads"]

    @property
    def results_bucket(self) -> str:
        return self._buckets["results"]

    @property
    def deleted_bucket(self) -> str:
        return self._buckets["deleted"]

    async def ensure_buckets(self) -> None:
        """Ensure all required buckets exist."""
        for name, bucket in self._buckets.items():
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
            except S3Error as e:
                logger.error(f"Failed to create bucket {bucket}: {e}")
                raise StorageError(f"Failed to ensure bucket {bucket}: {e}")

    async def bucket_exists(self, bucket: str) -> bool:
        """Check if bucket exists."""
        try:
            return self.client.bucket_exists(bucket)
        except S3Error as e:
            logger.error(f"Error checking bucket {bucket}: {e}")
            raise StorageError(f"Failed to check bucket: {e}")

    async def upload(
        self,
        bucket: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload file to storage."""
        try:
            self.client.put_object(
                bucket,
                object_key,
                BytesIO(data),
                len(data),
                content_type=content_type,
            )
            logger.debug(f"Uploaded {bucket}/{object_key} ({len(data)} bytes)")
        except S3Error as e:
            logger.error(f"Upload failed {bucket}/{object_key}: {e}")
            raise UploadError(f"Failed to upload: {e}")

    async def upload_stream(
        self,
        bucket: str,
        object_key: str,
        stream: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload from stream to storage."""
        try:
            self.client.put_object(
                bucket,
                object_key,
                stream,
                length,
                content_type=content_type,
            )
            logger.debug(f"Uploaded stream {bucket}/{object_key} ({length} bytes)")
        except S3Error as e:
            logger.error(f"Upload stream failed {bucket}/{object_key}: {e}")
            raise UploadError(f"Failed to upload stream: {e}")

    async def download(self, bucket: str, object_key: str) -> bytes:
        """Download file from storage."""
        try:
            response = self.client.get_object(bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(bucket, object_key)
            if e.code == "NoSuchBucket":
                raise BucketNotFoundError(bucket)
            logger.error(f"Download failed {bucket}/{object_key}: {e}")
            raise DownloadError(f"Failed to download: {e}")

    async def exists(self, bucket: str, object_key: str) -> bool:
        """Check if object exists."""
        try:
            self.client.stat_object(bucket, object_key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            if e.code == "NoSuchBucket":
                raise BucketNotFoundError(bucket)
            raise StorageError(f"Failed to check existence: {e}")

    async def get_object_info(self, bucket: str, object_key: str) -> ObjectInfo:
        """Get object metadata."""
        try:
            stat = self.client.stat_object(bucket, object_key)
            return ObjectInfo(
                bucket=bucket,
                key=object_key,
                size=stat.size,
                content_type=stat.content_type,
                etag=stat.etag,
                last_modified=str(stat.last_modified),
            )
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(bucket, object_key)
            if e.code == "NoSuchBucket":
                raise BucketNotFoundError(bucket)
            raise StorageError(f"Failed to get object info: {e}")

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """List objects in bucket with optional prefix."""
        try:
            objects = self.client.list_objects(
                bucket,
                prefix=prefix,
                recursive=recursive,
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            if e.code == "NoSuchBucket":
                raise BucketNotFoundError(bucket)
            raise StorageError(f"Failed to list objects: {e}")

    async def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate presigned URL for download."""
        try:
            return self.client.presigned_get_object(
                bucket,
                object_key,
                expires=expires,
            )
        except S3Error as e:
            logger.error(f"Presign failed {bucket}/{object_key}: {e}")
            raise StorageError(f"Failed to generate presigned URL: {e}")

    async def get_presigned_upload_url(
        self,
        bucket: str,
        object_key: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate presigned URL for upload."""
        try:
            return self.client.presigned_put_object(
                bucket,
                object_key,
                expires=expires,
            )
        except S3Error as e:
            logger.error(f"Presign upload failed {bucket}/{object_key}: {e}")
            raise StorageError(f"Failed to generate presigned upload URL: {e}")

    async def move(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Move object between buckets."""
        try:
            # Copy then delete
            self.client.copy_object(
                dest_bucket,
                dest_key,
                CopySource(source_bucket, source_key),
            )
            self.client.remove_object(source_bucket, source_key)
            logger.debug(f"Moved {source_bucket}/{source_key} -> {dest_bucket}/{dest_key}")
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(source_bucket, source_key)
            logger.error(f"Move failed: {e}")
            raise StorageError(f"Failed to move object: {e}")

    async def copy(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Copy object between buckets."""
        try:
            self.client.copy_object(
                dest_bucket,
                dest_key,
                CopySource(source_bucket, source_key),
            )
            logger.debug(f"Copied {source_bucket}/{source_key} -> {dest_bucket}/{dest_key}")
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(source_bucket, source_key)
            raise StorageError(f"Failed to copy object: {e}")

    async def move_to_deleted(self, bucket: str, object_key: str) -> None:
        """Move object to deleted bucket (soft delete)."""
        await self.move(
            bucket,
            object_key,
            self.deleted_bucket,
            f"{bucket}/{object_key}",  # Preserve source bucket in path
        )

    async def delete(self, bucket: str, object_key: str) -> None:
        """Delete object (hard delete - use with caution)."""
        try:
            self.client.remove_object(bucket, object_key)
            logger.debug(f"Deleted {bucket}/{object_key}")
        except S3Error as e:
            if e.code == "NoSuchKey":
                return  # Already deleted, idempotent
            logger.error(f"Delete failed {bucket}/{object_key}: {e}")
            raise StorageError(f"Failed to delete object: {e}")

    async def delete_many(self, bucket: str, object_keys: List[str]) -> None:
        """Delete multiple objects."""
        from minio.deleteobjects import DeleteObject

        try:
            delete_list = [DeleteObject(key) for key in object_keys]
            errors = list(self.client.remove_objects(bucket, delete_list))
            if errors:
                logger.warning(f"Some objects failed to delete: {errors}")
        except S3Error as e:
            logger.error(f"Bulk delete failed: {e}")
            raise StorageError(f"Failed to delete objects: {e}")
