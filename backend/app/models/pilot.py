"""Pilots, contracts, milestones, payments, pilot KPIs and recommendations.

Two properties of this group are load-bearing for the recommendation engine
and must survive the port:

* `kpi_results` is **append-only**. Every measurement is kept so a pilot's KPI
  history is auditable; readers always take the *latest* result per KPI rather
  than overwriting.
* `recommendations.recommendation` (generated) and `.final_decision` (human)
  are **separate columns**. The schema itself enforces "AI assists, human
  decides", and the UI must keep them visually separate too.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import created_at, nullable_ts, updated_at, uuid_fk, uuid_pk
from app.models.challenge import Challenge
from app.models.enums import (
    ContractStatus,
    MilestoneStatus,
    PaymentStatus,
    PilotStatus,
    RecommendationType,
    pg_enum,
)
from app.models.identity import User
from app.models.startup import Startup


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    ip_terms: Mapped[str | None] = mapped_column(Text)
    data_terms: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    signed_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ContractStatus] = mapped_column(
        pg_enum(ContractStatus, "contract_status"), nullable=False,
        default=ContractStatus.DRAFT)
    created_at: Mapped[datetime] = created_at()

    payments: Mapped[list["Payment"]] = relationship(back_populates="contract")


class Pilot(Base):
    __tablename__ = "pilots"

    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="RESTRICT", index=True)
    startup_id: Mapped[uuid.UUID] = uuid_fk(
        "startups.id", ondelete="RESTRICT", index=True)
    #: Nullable — a pilot can run (and complete) without a formal contract row.
    contract_id: Mapped[uuid.UUID | None] = uuid_fk(
        "contracts.id", nullable=True, ondelete="SET NULL")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[PilotStatus] = mapped_column(
        pg_enum(PilotStatus, "pilot_status"), nullable=False,
        default=PilotStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    challenge: Mapped[Challenge] = relationship(lazy="joined")
    startup: Mapped[Startup] = relationship(lazy="joined")
    contract: Mapped[Contract | None] = relationship(lazy="joined")
    milestones: Mapped[list["PilotMilestone"]] = relationship(
        back_populates="pilot", cascade="all, delete-orphan",
        order_by="PilotMilestone.due_date")
    kpis: Mapped[list["Kpi"]] = relationship(
        back_populates="pilot", cascade="all, delete-orphan")
    recommendation: Mapped["Recommendation | None"] = relationship(
        back_populates="pilot", uselist=False, cascade="all, delete-orphan")
    knowledge_base_entry: Mapped["PilotKnowledgeBase | None"] = relationship(  # noqa: F821
        back_populates="pilot", uselist=False, cascade="all, delete-orphan")


class PilotMilestone(Base):
    __tablename__ = "pilot_milestones"

    id: Mapped[uuid.UUID] = uuid_pk()
    pilot_id: Mapped[uuid.UUID] = uuid_fk("pilots.id", ondelete="CASCADE", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[MilestoneStatus] = mapped_column(
        pg_enum(MilestoneStatus, "milestone_status"), nullable=False,
        default=MilestoneStatus.PENDING)
    completion_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = created_at()

    pilot: Mapped[Pilot] = relationship(back_populates="milestones")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = uuid_fk(
        "contracts.id", ondelete="RESTRICT", index=True)
    #: Nullable — a payment may be milestone-linked or a flat disbursement.
    milestone_id: Mapped[uuid.UUID | None] = uuid_fk(
        "pilot_milestones.id", nullable=True, ondelete="SET NULL", index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), nullable=False,
        default=PaymentStatus.PENDING)
    released_at: Mapped[datetime | None] = nullable_ts()
    created_at: Mapped[datetime] = created_at()

    contract: Mapped[Contract] = relationship(back_populates="payments")
    milestone: Mapped[PilotMilestone | None] = relationship()


class Kpi(Base):
    """Pilot-level KPI. Copied from `challenge_kpis` when a pilot is created,
    so a pilot can adjust targets without mutating the challenge definition."""

    __tablename__ = "kpis"

    id: Mapped[uuid.UUID] = uuid_pk()
    pilot_id: Mapped[uuid.UUID] = uuid_fk("pilots.id", ondelete="CASCADE", index=True)
    kpi_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    unit: Mapped[str | None] = mapped_column(String(60))

    pilot: Mapped[Pilot] = relationship(back_populates="kpis")
    results: Mapped[list["KpiResult"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan",
        order_by="KpiResult.recorded_at")

    @property
    def latest_result(self) -> "KpiResult | None":
        return self.results[-1] if self.results else None


class KpiResult(Base):
    __tablename__ = "kpi_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    kpi_id: Mapped[uuid.UUID] = uuid_fk("kpis.id", ondelete="CASCADE", index=True)
    recorded_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    recorded_at: Mapped[datetime] = created_at()
    notes: Mapped[str | None] = mapped_column(Text)

    kpi: Mapped[Kpi] = relationship(back_populates="results")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = uuid_pk()
    pilot_id: Mapped[uuid.UUID] = uuid_fk(
        "pilots.id", ondelete="CASCADE", unique=True, index=True)
    #: System-generated outcome.
    recommendation: Mapped[RecommendationType] = mapped_column(
        pg_enum(RecommendationType, "recommendation_type"), nullable=False)
    cost_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    performance_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    impact_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    rationale_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = created_at()

    reviewed_by: Mapped[uuid.UUID | None] = uuid_fk(
        "users.id", nullable=True, ondelete="SET NULL")
    #: Human decision. Stays NULL until an official records it.
    final_decision: Mapped[RecommendationType | None] = mapped_column(
        pg_enum(RecommendationType, "recommendation_type"), nullable=True)
    decided_at: Mapped[datetime | None] = nullable_ts()

    pilot: Mapped[Pilot] = relationship(back_populates="recommendation")
    reviewer: Mapped[User | None] = relationship(lazy="joined")
