"""Identity and RBAC: roles, users, government departments."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import created_at, updated_at, uuid_fk, uuid_pk
from app.models.enums import RoleName, pg_enum


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[RoleName] = mapped_column(
        pg_enum(RoleName, "role_name"), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = uuid_fk("roles.id", ondelete="RESTRICT", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    department: Mapped["GovernmentDepartment | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan")
    startup: Mapped["Startup | None"] = relationship(  # noqa: F821
        back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def role_name(self) -> RoleName:
        """Convenience for guards and JWT claims, which never need the row."""
        return self.role.name


class GovernmentDepartment(Base):
    __tablename__ = "government_departments"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(
        "users.id", ondelete="CASCADE", unique=True, index=True)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ministry: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255))
    contact_designation: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    user: Mapped[User] = relationship(back_populates="department")
    challenges: Mapped[list["Challenge"]] = relationship(  # noqa: F821
        back_populates="department")
