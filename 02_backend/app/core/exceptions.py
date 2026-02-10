# Base exceptions hierarchy


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} {id} not found", code="NOT_FOUND")


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


class UnauthorizedError(AppException):
    """Unauthorized access."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="UNAUTHORIZED")


class ForbiddenError(AppException):
    """Forbidden access."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="FORBIDDEN")
