"""
Authentication, authorisation and password handling.

Ports the Spring security stack: `JwtService` -> `jwt`, `BCryptPasswordEncoder`
-> `password`, `JwtAuthenticationFilter` + `AppUserDetailsService` +
`CurrentUserService` + `@PreAuthorize` -> `deps`, and `RateLimitFilter` ->
`rate_limit`.
"""
from app.security.deps import (  # noqa: F401
    AuthenticatedUser,
    CurrentUser,
    CurrentUserEntity,
    get_current_user,
    get_current_user_entity,
    require_roles,
)
from app.security.jwt import create_access_token, decode_token  # noqa: F401
from app.security.password import hash_password, verify_password  # noqa: F401
from app.security.rate_limit import RateLimitMiddleware  # noqa: F401

__all__ = [
    "AuthenticatedUser", "CurrentUser", "CurrentUserEntity",
    "get_current_user", "get_current_user_entity", "require_roles",
    "create_access_token", "decode_token",
    "hash_password", "verify_password",
    "RateLimitMiddleware",
]
