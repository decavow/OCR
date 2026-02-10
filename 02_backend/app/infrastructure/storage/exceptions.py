# Storage Exceptions


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class ObjectNotFoundError(StorageError):
    """Object not found in storage."""

    def __init__(self, bucket: str, object_key: str):
        self.bucket = bucket
        self.object_key = object_key
        super().__init__(f"Object not found: {bucket}/{object_key}")


class BucketNotFoundError(StorageError):
    """Bucket not found."""

    def __init__(self, bucket: str):
        self.bucket = bucket
        super().__init__(f"Bucket not found: {bucket}")


class UploadError(StorageError):
    """Error uploading object."""
    pass


class DownloadError(StorageError):
    """Error downloading object."""
    pass
