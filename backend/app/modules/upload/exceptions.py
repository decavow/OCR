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
