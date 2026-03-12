# AccessDenied, ServiceNotRegistered, FileNotInJob

from app.core.exceptions import AppException


class FileProxyError(AppException):
    """Base file proxy error."""
    pass


class AccessDenied(FileProxyError):
    """Access denied."""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, code="ACCESS_DENIED")


class ServiceNotRegistered(FileProxyError):
    """Service not registered or disabled."""
    def __init__(self, message: str = "Service not registered or disabled"):
        super().__init__(message, code="SERVICE_NOT_REGISTERED")


class FileNotInJob(FileProxyError):
    """File does not belong to job."""
    def __init__(self):
        super().__init__("File does not belong to job", code="FILE_NOT_IN_JOB")
