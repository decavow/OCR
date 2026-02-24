# InvalidFileType, FileTooLarge, BatchTooLarge

from app.core.exceptions import AppException


class UploadError(AppException):
    """Base upload error."""
    pass


class InvalidFileType(UploadError):
    """File type not supported."""
    def __init__(self, mime_type: str):
        super().__init__(f"File type {mime_type} is not supported", code="INVALID_FILE_TYPE")


class FileTooLarge(UploadError):
    """File size exceeds limit."""
    def __init__(self, size: int, max_size: int):
        super().__init__(
            f"File size {size} exceeds limit {max_size}",
            code="FILE_TOO_LARGE"
        )


class BatchTooLarge(UploadError):
    """Batch size exceeds limit."""
    def __init__(self, count: int, max_count: int):
        super().__init__(
            f"Batch size {count} exceeds limit {max_count}",
            code="BATCH_TOO_LARGE"
        )


class BatchTotalSizeTooLarge(UploadError):
    """Total batch size exceeds limit."""
    def __init__(self, total_size: int, max_size: int):
        super().__init__(
            f"Total batch size {total_size} bytes exceeds limit {max_size} bytes",
            code="BATCH_TOTAL_SIZE_TOO_LARGE"
        )


class ServiceNotAvailable(UploadError):
    """Requested method/tier has no approved service."""
    def __init__(self, method: str, tier: int):
        super().__init__(
            f"No approved service available for method '{method}' tier {tier}",
            code="SERVICE_NOT_AVAILABLE"
        )
