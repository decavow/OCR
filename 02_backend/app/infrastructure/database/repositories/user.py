# UserRepository

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from .base import BaseRepository
from app.infrastructure.database.models import User


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get active user by email."""
        return self.db.query(User).filter(
            User.email == email,
            User.deleted_at.is_(None)
        ).first()

    def get_active(self, user_id: str) -> Optional[User]:
        """Get active user by ID (not deleted)."""
        return self.db.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None)
        ).first()

    def email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        return self.db.query(User).filter(
            User.email == email,
            User.deleted_at.is_(None)
        ).first() is not None

    def create_user(self, email: str, password_hash: str) -> User:
        """Create new user."""
        user = User(email=email, password_hash=password_hash)
        return self.create(user)

    def soft_delete(self, user: User) -> User:
        """Soft delete user."""
        user.deleted_at = datetime.now(timezone.utc)
        return self.update(user)

    def count_active(self, exclude_admins: bool = False) -> int:
        """Count all active users."""
        query = self.db.query(User).filter(User.deleted_at.is_(None))
        if exclude_admins:
            query = query.filter(User.is_admin.is_(False))
        return query.count()

    def get_all_active(self, skip: int = 0, limit: int = 100, exclude_admins: bool = False) -> list[User]:
        """Get all active users with pagination."""
        query = self.db.query(User).filter(User.deleted_at.is_(None))
        if exclude_admins:
            query = query.filter(User.is_admin.is_(False))
        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
