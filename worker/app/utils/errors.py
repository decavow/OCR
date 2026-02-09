# Error classification and custom exceptions


class WorkerError(Exception):
    """Base exception for worker errors."""
    pass


class RetriableError(WorkerError):
    """Error that should trigger a retry."""
    pass


class PermanentError(WorkerError):
    """Error that should not be retried."""
    pass


class DownloadError(RetriableError):
    """Failed to download file from file proxy."""
    pass


class UploadError(RetriableError):
    """Failed to upload result to file proxy."""
    pass


class OCRError(WorkerError):
    """Error during OCR processing."""
    pass


class InvalidImageError(PermanentError):
    """Image format not supported or corrupted."""
    pass


# Error type classification
RETRIABLE_ERRORS = [
    "ConnectionError",
    "TimeoutError",
    "HTTPStatusError",
    "DownloadError",
    "UploadError",
]

NON_RETRIABLE_ERRORS = [
    "ValueError",
    "UnidentifiedImageError",
    "PDFSyntaxError",
    "InvalidImageError",
]


def classify_error(error: Exception) -> tuple[str, bool]:
    """Classify error as retriable or not.

    Returns:
        tuple: (error_message, is_retriable)
    """
    error_type = type(error).__name__
    error_message = str(error)

    # Check custom exception types first
    if isinstance(error, PermanentError):
        return error_message, False
    if isinstance(error, RetriableError):
        return error_message, True

    # Check if retriable by name
    for retriable_type in RETRIABLE_ERRORS:
        if retriable_type in error_type:
            return error_message, True

    # Check if non-retriable by name
    for non_retriable_type in NON_RETRIABLE_ERRORS:
        if non_retriable_type in error_type:
            return error_message, False

    # Default: assume retriable
    return error_message, True
