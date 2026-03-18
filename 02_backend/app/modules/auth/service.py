# AuthService: register, login, logout, validate_session

import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.infrastructure.database.models import User, Session as UserSession
from app.infrastructure.database.repositories import UserRepository, SessionRepository
from app.config import settings
from .utils import hash_password, verify_password
from .exceptions import InvalidCredentials, UserAlreadyExists, UserNotFound


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    def register(self, email: str, password: str) -> User:
        """Register a new user."""
        # Check if user exists
        existing = self.user_repo.get_by_email(email)
        if existing:
            raise UserAlreadyExists(email)

        # Create user with hashed password
        password_hash = hash_password(password)
        user = self.user_repo.create_user(email, password_hash)
        return user

    def login(self, email: str, password: str) -> tuple[User, UserSession, str]:
        """Login user, return (user, session, raw_token).

        The raw token is returned separately because the session object
        stores only the hash. The raw token must be sent to the client.
        """
        # Find user
        user = self.user_repo.get_by_email(email)
        if not user:
            raise InvalidCredentials()

        # Verify password
        if not verify_password(password, user.password_hash):
            raise InvalidCredentials()

        # Create session (repo hashes the token before storing)
        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
        session = self.session_repo.create_session(user.id, raw_token, expires_at)

        return user, session, raw_token

    def logout(self, token: str) -> bool:
        """Logout user, invalidate session."""
        session = self.session_repo.get_valid(token)
        if session:
            self.session_repo.delete(session)
            return True
        return False

    def validate_session(self, token: str) -> User | None:
        """Validate session token, return user if valid."""
        session = self.session_repo.get_valid(token)
        if not session:
            return None

        user = self.user_repo.get(session.user_id)
        if not user or user.deleted_at is not None:
            return None

        return user

    def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        user = self.user_repo.get(user_id)
        if user and user.deleted_at is None:
            return user
        return None
