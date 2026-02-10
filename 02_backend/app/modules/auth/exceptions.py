# AuthError, InvalidCredentials, EmailExists

from app.core.exceptions import AppException


class AuthError(AppException):
    """Base auth error."""
    pass


class InvalidCredentials(AuthError):
    """Invalid email or password."""
    def __init__(self):
        super().__init__("Invalid email or password", code="INVALID_CREDENTIALS")


class EmailExists(AuthError):
    """Email already registered."""
    def __init__(self):
        super().__init__("Email already exists", code="EMAIL_EXISTS")


class UserAlreadyExists(AuthError):
    """User already exists."""
    def __init__(self, email: str):
        super().__init__(f"User with email {email} already exists", code="USER_EXISTS")


class UserNotFound(AuthError):
    """User not found."""
    def __init__(self):
        super().__init__("User not found", code="USER_NOT_FOUND")


class SessionExpired(AuthError):
    """Session has expired."""
    def __init__(self):
        super().__init__("Session expired", code="SESSION_EXPIRED")
