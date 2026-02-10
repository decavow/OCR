# AccessDenied, ServiceNotRegistered, FileNotInJob

from app.core.exceptions import AppException


class FileProxyError(AppException):
    """Base file proxy error."""
    pass


class AccessDenied(FileProxyError):
    """Access denied."""
    def __init__(self):
        super().__init__("Access denied", code="ACCESS_DENIED")


class ServiceNotRegistered(FileProxyError):
    """Service not registered or disabled."""
    def __init__(self):
        super().__init__("Service not registered or disabled", code="SERVICE_NOT_REGISTERED")


class FileNotInJob(FileProxyError):
    """File does not belong to job."""
    def __init__(self):
        super().__init__("File does not belong to job", code="FILE_NOT_IN_JOB")
