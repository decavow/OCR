# BaseRepository (CRUD helpers)

from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model

    def get(self, id: str) -> Optional[T]:
        """Get by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all with pagination."""
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj: T) -> T:
        """Create new record."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: T) -> T:
        """Save (create or update) record."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: T) -> T:
        """Update existing record."""
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: T) -> None:
        """Delete record (hard delete)."""
        self.db.delete(obj)
        self.db.commit()

    def count(self) -> int:
        """Count all records."""
        return self.db.query(self.model).count()
