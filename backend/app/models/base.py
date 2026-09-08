"""
Shared column helpers.

Every table in this schema uses the same primary-key and timestamp
conventions, and the defaults are *server*-side (`gen_random_uuid()`, `now()`)
rather than Python-side. That is deliberate: `database/schema.sql` remains the
authority on defaults, so a row inserted by psql and one inserted by the API
are indistinguishable.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def uuid_fk(target: str, *, nullable: bool = False, ondelete: str = "RESTRICT",
            unique: bool = False, index: bool = False) -> Mapped[uuid.UUID]:
    from sqlalchemy import ForeignKey

    return mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        unique=unique,
        index=index,
    )


def created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


def updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
        onupdate=lambda: datetime.now(tz=None).astimezone(),
    )


def nullable_ts() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)
