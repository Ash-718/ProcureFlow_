"""Shared FastAPI dependencies: the current user and server-side RBAC."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.enums import UserRole
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    user = db.get(User, int(payload.get("sub", 0)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


def require_roles(*allowed: UserRole) -> Callable[[User], User]:
    """Server-side RBAC.

    The client hides screens it should not show; this is the enforcement that
    actually counts.
    """

    allowed_values = {role.value for role in allowed}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role {current_user.role.value} may not use this endpoint "
                    f"(allowed: {', '.join(sorted(allowed_values))})"
                ),
            )
        return current_user

    return dependency
