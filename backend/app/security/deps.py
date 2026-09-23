"""
Authentication and RBAC dependencies.

Replaces `JwtAuthenticationFilter` + `AppUserDetailsService` +
`CurrentUserService` + `@PreAuthorize` with FastAPI dependencies. Resolution
follows the Java filter exactly: read the bearer token, verify it, take the
**`email` claim** (not `sub`) and load the user by email.

One deliberate divergence, flagged rather than hidden
-----------------------------------------------------
The Java filter builds a `UsernamePasswordAuthenticationToken` directly from
`UserDetails` and never consults `isEnabled()`. The practical effect is that a
deactivated user keeps full access until their token expires — up to 24 hours —
which makes `PATCH /admin/users/{id}/active` far weaker than it appears.

:func:`get_current_user` enforces `is_active` on every request. That closes the
hole and matches the evident intent of `AdminService.setActive` and the active
check already present in `AuthService.login`. It changes no response shape and
no frontend behaviour; the only observable difference is that deactivating a
user now takes effect immediately.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Callable, Iterable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ApiException
from app.models import RoleName, User
from app.security.jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
    decode_token,
    extract_bearer,
)


@dataclass(frozen=True)
class AuthenticatedUser:
    """
    Request-scoped identity, mirroring Java's `AuthenticatedUser`.

    Holds only what guards and audit records need. Endpoints that must persist
    a reference to the actor use :func:`get_current_user_entity` to obtain the
    managed ORM row, the same split the Java `CurrentUserService` made.
    """

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleName
    active: bool

    @property
    def is_government(self) -> bool:
        return self.role is RoleName.GOVERNMENT

    @property
    def is_startup(self) -> bool:
        return self.role is RoleName.STARTUP

    @property
    def is_expert(self) -> bool:
        return self.role is RoleName.EXPERT

    @property
    def is_admin(self) -> bool:
        return self.role is RoleName.ADMIN

    def has_role(self, *roles: RoleName | str) -> bool:
        wanted = {r.value if isinstance(r, RoleName) else str(r).upper() for r in roles}
        return self.role.value in wanted


def _load_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalars().one_or_none()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticatedUser:
    """
    Resolve the caller from the ``Authorization`` header.

    Raises 401 for a missing, malformed, expired or unverifiable token, for an
    unknown subject, and for a deactivated account.
    """
    token = extract_bearer(request.headers.get("Authorization"))
    if token is None:
        raise ApiException.unauthorized("Authentication required")

    try:
        claims = decode_token(token)
    except ExpiredSignatureError as exc:
        raise ApiException.unauthorized("Your session has expired. Please sign in again.") from exc
    except InvalidTokenError as exc:
        raise ApiException.unauthorized("Invalid authentication token") from exc

    email = claims.get("email")
    if not email:
        raise ApiException.unauthorized("Invalid authentication token")

    user = _load_user_by_email(db, email)
    if user is None:
        # The account was deleted while a token was still live.
        raise ApiException.unauthorized("Invalid authentication token")
    if not user.is_active:
        raise ApiException.forbidden("This account has been deactivated")

    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name,
        active=user.is_active,
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_current_user_entity(
    current: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """The managed `User` row, for services that persist an actor reference."""
    user = db.get(User, current.id)
    if user is None:
        raise ApiException.not_found("Authenticated user no longer exists")
    return user


CurrentUserEntity = Annotated[User, Depends(get_current_user_entity)]


def require_roles(*roles: RoleName | str) -> Callable[..., AuthenticatedUser]:
    """
    Guard equivalent to `@PreAuthorize("hasAnyRole(...)")`.

    Usage::

        @router.post("", dependencies=[Depends(require_roles(RoleName.GOVERNMENT))])

    or, when the endpoint also needs the identity::

        user: Annotated[AuthenticatedUser, Depends(require_roles(RoleName.ADMIN))]

    Returns 403 on a role mismatch, matching Spring's `AccessDeniedException`
    handling. Authentication failures still surface as 401 from
    :func:`get_current_user`, so the frontend's 401-only redirect keeps working:
    a role mismatch must not bounce the user to the login page.
    """
    allowed = {r.value if isinstance(r, RoleName) else str(r).upper() for r in roles}

    def guard(current: CurrentUser) -> AuthenticatedUser:
        if current.role.value not in allowed:
            raise ApiException.forbidden(
                "You do not have permission to perform this action")
        return current

    return guard


def require_any_role(roles: Iterable[RoleName | str]) -> Callable[..., AuthenticatedUser]:
    """`require_roles` for a role list built at runtime."""
    return require_roles(*roles)


__all__ = [
    "AuthenticatedUser",
    "CurrentUser",
    "CurrentUserEntity",
    "get_current_user",
    "get_current_user_entity",
    "require_any_role",
    "require_roles",
]
