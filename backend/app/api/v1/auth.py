"""
`/api/v1/auth` — registration, login, current user.

Public except `/me`. Rate limited to 15 requests per minute per client by the
middleware in `app/security/rate_limit.py`, matching Java's `RateLimitFilter`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
)
from app.security.deps import CurrentUser
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=AuthResponse,
             status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: DbSession) -> AuthResponse:
    """
    Self-service registration for a startup or a government department.

    Returns **201**, matching `AuthController.register`. Experts and admins are
    provisioned by an administrator and are rejected here with a 403.
    """
    return AuthService(db).register(request)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: DbSession) -> AuthResponse:
    return AuthService(db).login(request)


@router.get("/me", response_model=CurrentUserResponse)
def me(current: CurrentUser) -> CurrentUserResponse:
    """
    The authenticated caller.

    Served from the token-resolved identity rather than a fresh query — the
    dependency has already loaded and validated the user.
    """
    return CurrentUserResponse(
        id=current.id,
        email=current.email,
        full_name=current.full_name,
        role=current.role,
    )
