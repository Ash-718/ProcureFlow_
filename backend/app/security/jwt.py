"""
JWT issuing and verification, byte-compatible with the Spring `JwtService`.

Why this is more subtle than it looks
-------------------------------------
The Java side calls ``Keys.hmacShaKeyFor(secretBytes)``, and **jjwt picks the
algorithm from the key's length**, not from configuration:

===================  =========
secret length        algorithm
===================  =========
< 32 bytes           HS256 (Spring zero-pads the key to 32 bytes first)
32 – 47 bytes        HS256
48 – 63 bytes        HS384
>= 64 bytes          HS512
===================  =========

The project's default secret is 51 bytes, so the running Spring backend issues
**HS384** tokens — verified by decoding a live token, whose header is
``{"alg":"HS384"}``. The README's "HS256" is inaccurate. Hardcoding HS256 here
would have rejected every token Spring ever issued and produced tokens Spring
would reject in turn.

:func:`select_algorithm` therefore reproduces jjwt's rule, and
:func:`decode_token` accepts any of the three so a token issued by either
backend works against the other during the migration cut-over.

Header shape also matters: jjwt emits ``{"alg": ...}`` with **no ``typ``**,
while PyJWT adds ``"typ": "JWT"`` by default. Passing ``typ=None`` suppresses
it, which makes the tokens byte-identical for identical claims.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings

#: Every algorithm a token from either backend may legitimately carry.
ACCEPTED_ALGORITHMS = ("HS256", "HS384", "HS512")

#: jjwt requires >= 256 bits; Spring zero-pads short secrets up to this length.
_MIN_KEY_BYTES = 32


def secret_bytes(secret: str | None = None) -> bytes:
    """
    Key material, padded exactly the way Spring's ``JwtService`` pads it.

    Spring copies a short secret into a fresh 32-byte array, leaving the
    remainder as zero bytes. Reproducing that matters: a deployment using a
    short secret would otherwise derive a different key and reject every
    existing token.
    """
    raw = (secret if secret is not None else settings.jwt_secret).encode("utf-8")
    if len(raw) < _MIN_KEY_BYTES:
        return raw + b"\x00" * (_MIN_KEY_BYTES - len(raw))
    return raw


def select_algorithm(key: bytes) -> str:
    """jjwt's ``Keys.hmacShaKeyFor`` algorithm selection, by key bit-length."""
    bits = len(key) * 8
    if bits >= 512:
        return "HS512"
    if bits >= 384:
        return "HS384"
    return "HS256"


def create_access_token(user_id: uuid.UUID | str, email: str, role: str,
                        *, issued_at: datetime | None = None) -> str:
    """
    Issue a token with Spring's exact claim set: ``sub``, ``email``, ``role``,
    ``iat``, ``exp``.

    ``iat``/``exp`` are integer seconds since the epoch (JWT NumericDate), which
    is what jjwt writes. ``issued_at`` is injectable so tests can assert
    byte-for-byte equality with a token minted by the Java backend.
    """
    now = issued_at or datetime.now(timezone.utc)
    issued = int(now.timestamp())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": issued,
        "exp": issued + settings.jwt_expiry_seconds,
    }
    key = secret_bytes()
    return jwt.encode(
        payload,
        key,
        algorithm=select_algorithm(key),
        headers={"typ": None},  # PyJWT drops the key entirely when it is falsy
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Verify and decode a token.

    Raises :class:`jwt.InvalidTokenError` (or the ``ExpiredSignatureError``
    subclass) on any failure. Callers translate that into a 401 — the Spring
    filter behaved the same way, clearing the security context rather than
    surfacing a 500.
    """
    return jwt.decode(
        token,
        secret_bytes(),
        algorithms=list(ACCEPTED_ALGORITHMS),
        options={"require": ["sub", "exp"]},
    )


def extract_bearer(authorization: str | None) -> str | None:
    """Pull the credential out of an ``Authorization: Bearer <token>`` header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    return token or None


__all__ = [
    "ACCEPTED_ALGORITHMS",
    "ExpiredSignatureError",
    "InvalidTokenError",
    "create_access_token",
    "decode_token",
    "extract_bearer",
    "secret_bytes",
    "select_algorithm",
]
