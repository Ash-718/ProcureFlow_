"""Startups, their capabilities and their delivery history.

`capabilities` and `projects` are the direct inputs to the technology, domain
and experience components of the matching formula, so their tags and
`proficiency_level` are load-bearing rather than descriptive.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.core.database import Base
from app.models.base import created_at, nullable_ts, updated_at, uuid_fk, uuid_pk
from app.models.enums import ClientType, pg_enum
from app.models.identity import User


class Startup(Base):
    __tablename__ = "startups"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(
        "users.id", ondelete="CASCADE", unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dpiit_number: Mapped[str | None] = mapped_column(String(100))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    team_size: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    readiness_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("50.00"))
    description: Mapped[str | None] = mapped_column(Text)

    # `double precision[]` rather than pgvector — see the note at the top of
    # database/schema.sql. Cosine similarity is computed in numpy.
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_updated_at: Mapped[datetime | None] = nullable_ts()

    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    user: Mapped[User] = relationship(back_populates="startup")
    capabilities: Mapped[list["StartupCapability"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan",
        order_by="StartupCapability.created_at")
    projects: Mapped[list["StartupProject"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan",
        order_by="StartupProject.created_at")


class StartupCapability(Base):
    __tablename__ = "startup_capabilities"
    __table_args__ = (
        CheckConstraint("proficiency_level BETWEEN 1 AND 5",
                        name="startup_capabilities_proficiency_level_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    startup_id: Mapped[uuid.UUID] = uuid_fk(
        "startups.id", ondelete="CASCADE", index=True)
    technology_tag: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    domain_tag: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    proficiency_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()

    startup: Mapped[Startup] = relationship(back_populates="capabilities")


class StartupProject(Base):
    __tablename__ = "startup_projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    startup_id: Mapped[uuid.UUID] = uuid_fk(
        "startups.id", ondelete="CASCADE", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    technology_stack: Mapped[str | None] = mapped_column(String(255))
    client_type: Mapped[ClientType] = mapped_column(
        pg_enum(ClientType, "client_type"), nullable=False, default=ClientType.PRIVATE)
    outcome_summary: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at()

    startup: Mapped[Startup] = relationship(back_populates="projects")
