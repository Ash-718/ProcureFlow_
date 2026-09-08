"""Authentication payloads — `AuthResponse` and `CurrentUser` in the frontend types."""
from __future__ import annotations

import uuid

from pydantic import EmailStr, Field, field_validator

from app.models.enums import RoleName
from app.schemas.base import CamelModel, CamelRequest


class LoginRequest(CamelRequest):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        # `AuthService.login` looks up `email.toLowerCase().trim()`.
        return value.strip().lower()


class RegisterRequest(CamelRequest):
    """
    Matches the frontend's register payload.

    `companyName` / `departmentName` are conditionally required — the rule is
    enforced in the service layer rather than here, so the error message and
    HTTP status match the Java `AuthService` exactly (400 with a sentence,
    rather than a 400 with a `fieldErrors` map).
    """

    email: str
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    role: RoleName

    company_name: str | None = None
    department_name: str | None = None
    ministry: str | None = None
    region: str | None = None

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthResponse(CamelModel):
    """Emitted by both `POST /auth/login` and `POST /auth/register`."""

    token: str
    user_id: uuid.UUID
    email: str
    full_name: str
    role: RoleName


class CurrentUserResponse(CamelModel):
    """`GET /auth/me`."""

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleName


__all__ = [
    "AuthResponse",
    "CurrentUserResponse",
    "LoginRequest",
    "RegisterRequest",
]
