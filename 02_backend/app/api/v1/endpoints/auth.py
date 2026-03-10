# POST /auth/register, /auth/login, /auth/logout, GET /auth/me

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.api.v1.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
    AuthResponse,
)
from app.api.deps import get_db, get_current_user
from app.modules.auth.service import AuthService
from app.modules.auth.exceptions import (
    InvalidCredentials,
    UserAlreadyExists,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=AuthResponse)
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user."""
    auth_service = AuthService(db)
    try:
        user = auth_service.register(data.email, data.password)
        # Auto-login after registration
        user, session = auth_service.login(data.email, data.password)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            token=session.token,
            expires_at=session.expires_at,
        )
    except UserAlreadyExists as e:
        logger.info("Registration failed - user already exists: %s", data.email)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login user."""
    auth_service = AuthService(db)
    try:
        user, session = auth_service.login(data.email, data.password)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            token=session.token,
            expires_at=session.expires_at,
        )
    except InvalidCredentials as e:
        logger.warning("Login failed - invalid credentials: email=%s", data.email)
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Logout user."""
    if not authorization:
        return {"message": "Already logged out"}

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return {"message": "Already logged out"}

    token = parts[1]
    auth_service = AuthService(db)
    auth_service.logout(token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    """Get current user info."""
    return UserResponse.model_validate(current_user)
