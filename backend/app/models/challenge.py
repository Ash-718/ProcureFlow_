"""Challenges, their requirements and their KPI definitions."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.core.database import Base
from app.models.base import created_at, nullable_ts, updated_at, uuid_fk, uuid_pk
from app.models.enums import ChallengeStatus, RequirementType, pg_enum
from app.models.identity import GovernmentDepartment


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = uuid_pk()
    department_id: Mapped[uuid.UUID] = uuid_fk(
        "government_departments.id", ondelete="RESTRICT", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    #: Comma-separated; `app.ai.scoring.split_technology_list` parses it.
    desired_technology: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    outcomes_expected: Mapped[str | None] = mapped_column(Text)
    budget_range: Mapped[str | None] = mapped_column(String(120))
    timeline_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[ChallengeStatus] = mapped_column(
        pg_enum(ChallengeStatus, "challenge_status"), nullable=False,
        default=ChallengeStatus.DRAFT, index=True)

    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_updated_at: Mapped[datetime | None] = nullable_ts()

    published_at: Mapped[datetime | None] = nullable_ts()
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    department: Mapped[GovernmentDepartment] = relationship(
        back_populates="challenges", lazy="joined")
    requirements: Mapped[list["ChallengeRequirement"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan")
    kpis: Mapped[list["ChallengeKpi"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan")
    criteria: Mapped[list["EvaluationCriterion"]] = relationship(  # noqa: F821
        back_populates="challenge", cascade="all, delete-orphan")
    proposals: Mapped[list["Proposal"]] = relationship(  # noqa: F821
        back_populates="challenge")
    match_results: Mapped[list["MatchResult"]] = relationship(  # noqa: F821
        back_populates="challenge", cascade="all, delete-orphan")


class ChallengeRequirement(Base):
    __tablename__ = "challenge_requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="CASCADE", index=True)
    requirement_type: Mapped[RequirementType] = mapped_column(
        pg_enum(RequirementType, "requirement_type"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: Column is `is_mandatory`; the API exposes it as `mandatory`.
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    challenge: Mapped[Challenge] = relationship(back_populates="requirements")


class ChallengeKpi(Base):
    __tablename__ = "challenge_kpis"

    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="CASCADE", index=True)
    kpi_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    unit: Mapped[str | None] = mapped_column(String(60))
    weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("1.00"))

    challenge: Mapped[Challenge] = relationship(back_populates="kpis")
