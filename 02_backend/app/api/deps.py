# Dependencies: get_db, get_current_user, get_storage, get_queue

from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status, Header
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import User
from app.infrastructure.database.repositories import SessionRepository, UserRepository


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user from session token."""
    if not authorization:
        raise UnauthorizedError("Authorization header required")

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Invalid authorization header format")
    token = parts[1]

    # Validate session
    session_repo = SessionRepository(db)
    session = session_repo.get_valid(token)
    if not session:
        raise UnauthorizedError("Invalid or expired session")

    # Get user
    user_repo = UserRepository(db)
    user = user_repo.get(session.user_id)
    if not user or user.deleted_at is not None:
        raise UnauthorizedError("User not found")

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require current user to be admin."""
    if not current_user.is_admin:
        raise ForbiddenError("Admin access required")
    return current_user


async def get_current_user_optional(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None


def get_storage():
    """Get storage service."""
    from app.core.lifespan import storage_service
    return storage_service


def get_queue():
    """Get queue service."""
    from app.core.lifespan import queue_service
    return queue_service


def get_job_service(db: Session = Depends(get_db), queue=Depends(get_queue)):
    """Get JobService instance."""
    from app.modules.job.service import JobService
    return JobService(db, queue)


def get_request_id(request: Request) -> Optional[str]:
    """Get correlation request_id from request state."""
    return getattr(request.state, "request_id", None)
