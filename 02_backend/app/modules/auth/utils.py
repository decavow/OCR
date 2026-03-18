# hash_password(), verify_password(), hash_token()

import hashlib
import bcrypt


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_token(token: str) -> str:
    """Hash a session token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()
