# SessionRepository

from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session as DbSession

from .base import BaseRepository
from app.infrastructure.database.models import Session
from app.modules.auth.utils import hash_token


class SessionRepository(BaseRepository[Session]):
    """Repository for Session operations.

    Tokens are stored as SHA-256 hashes. Callers pass raw tokens;
    hashing is handled internally by this repository.
    """

    def __init__(self, db: DbSession):
        super().__init__(db, Session)

    def get_valid(self, token: str) -> Optional[Session]:
        """Get valid (non-expired) session by raw token (hashed before lookup)."""
        now = datetime.now(timezone.utc)
        token_hashed = hash_token(token)
        return self.db.query(Session).filter(
            Session.token == token_hashed,
            Session.expires_at > now
        ).first()

    def get_by_user(self, user_id: str) -> List[Session]:
        """Get all sessions for user."""
        return self.db.query(Session).filter(
            Session.user_id == user_id
        ).all()

    def create_session(
        self,
        user_id: str,
        token: str,
        expires_at: datetime = None,
        expires_hours: int = 24,
    ) -> Session:
        """Create new session. Token is hashed before storage."""
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        token_hashed = hash_token(token)
        session = Session(user_id=user_id, token=token_hashed, expires_at=expires_at)
        return self.create(session)

    def delete_by_user(self, user_id: str) -> int:
        """Delete all sessions for user. Returns deleted count."""
        count = self.db.query(Session).filter(
            Session.user_id == user_id
        ).delete()
        self.db.commit()
        return count

    def delete_expired(self) -> int:
        """Delete all expired sessions. Returns deleted count."""
        now = datetime.now(timezone.utc)
        count = self.db.query(Session).filter(
            Session.expires_at <= now
        ).delete()
        self.db.commit()
        return count
