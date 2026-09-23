"""SQLAlchemy models for ProcureFlow.

Design notes that matter for the non-negotiable rules:

* kpi.claimed_value (filled by the startup) and kpi.validated_value (filled by
  an independent validator) are separate columns, and kpi.validated_by records
  who validated.  A startup can never validate its own KPI.
* procurement_rule is the single home of every threshold, limit and percentage.
  source_reference is deliberately nullable: an empty value means "prototype
  setting, not a verified legal requirement" and the UI shows that distinction.
* audit_log records the actor, the timestamp and the reason for every
  classification, score, fallback trigger, approval and override.
* Embeddings are stored as JSON arrays of floats.  Cosine similarity is computed
  in Python, so no pgvector extension is required.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import (
    ChallengeStatus,
    CompanyType,
    DeclineReasonCode,
    KpiDirection,
    KpiStatus,
    Level,
    PartnershipStatus,
    PilotOutcome,
    PilotStatus,
    ProposalStatus,
    RuleType,
    Tier,
    UserRole,
)


def _enum(python_enum, name: str) -> SAEnum:
    """Postgres enum type that stores the enum value (not the member name)."""
    return SAEnum(python_enum, name=name, values_callable=lambda e: [m.value for m in e])


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Organisations and people
# ---------------------------------------------------------------------------


class Company(TimestampMixin, Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    type: Mapped[CompanyType] = mapped_column(_enum(CompanyType, "company_type"), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100))
    profile_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB)
    dpiit_recognised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    incorporation_date: Mapped[date | None] = mapped_column(Date)
    employee_count: Mapped[int | None] = mapped_column(Integer)

    founders: Mapped[list[CompanyFounder]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(back_populates="company")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Company {self.id} {self.name}>"


class Founder(TimestampMixin, Base):
    """A natural person.

    Rotation and shell detection resolve at this level, so re-entering through a
    newly incorporated company does not reset any counter.
    """

    __tablename__ = "founder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), unique=True)
    # Stand-in for a government identity reference (e.g. DIN / PAN).
    identity_ref: Mapped[str | None] = mapped_column(String(50), unique=True)

    companies: Mapped[list[CompanyFounder]] = relationship(
        back_populates="founder", cascade="all, delete-orphan"
    )


class CompanyFounder(Base):
    __tablename__ = "company_founder"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), primary_key=True
    )
    founder_id: Mapped[int] = mapped_column(
        ForeignKey("founder.id", ondelete="CASCADE"), primary_key=True
    )
    role_title: Mapped[str | None] = mapped_column(String(100))

    company: Mapped[Company] = relationship(back_populates="founders")
    founder: Mapped[Founder] = relationship(back_populates="companies")


class Department(TimestampMixin, Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    district: Mapped[str | None] = mapped_column(String(100))

    challenges: Mapped[list[Challenge]] = relationship(back_populates="department")


class User(TimestampMixin, Base):
    # "user" is a reserved word in Postgres, so the table is app_user.
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # A STARTUP user belongs to a company; a GOVERNMENT user to a department.
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="SET NULL"))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL")
    )

    company: Mapped[Company | None] = relationship(back_populates="users")
    department: Mapped[Department | None] = relationship()


# ---------------------------------------------------------------------------
# Procurement lifecycle
# ---------------------------------------------------------------------------


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    # Exactly what the department typed, in plain language.
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )

    # Nullable because the AI never invents a budget: if the department did not
    # supply one it stays empty and the field lands in missing_fields.
    value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    criticality: Mapped[Level | None] = mapped_column(_enum(Level, "level"))
    innovation_potential: Mapped[Level | None] = mapped_column(_enum(Level, "level"))

    tier: Mapped[Tier | None] = mapped_column(_enum(Tier, "tier"))
    tier_explanation: Mapped[str | None] = mapped_column(Text)

    status: Mapped[ChallengeStatus] = mapped_column(
        _enum(ChallengeStatus, "challenge_status"),
        default=ChallengeStatus.DRAFT,
        nullable=False,
    )
    district: Mapped[str | None] = mapped_column(String(100))
    requires_onsite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))

    embedding: Mapped[list[float] | None] = mapped_column(JSONB)
    structured_spec: Mapped[dict | None] = mapped_column(JSONB)
    missing_fields: Mapped[list[str] | None] = mapped_column(JSONB, default=list)

    # KPIs lock at officer approval and are immutable afterwards.
    kpis_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bid_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    department: Mapped[Department] = relationship(back_populates="challenges")
    kpis: Mapped[list[Kpi]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    proposals: Mapped[list[Proposal]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )


class Kpi(TimestampMixin, Base):
    """A measurable target.

    claimed_value is what the startup reports; validated_value is what an
    independent validator confirms.  They are deliberately separate columns.
    """

    __tablename__ = "kpi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenge.id", ondelete="CASCADE"), nullable=False
    )
    # Null while the KPI belongs to the challenge spec and no startup is engaged.
    startup_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    unit: Mapped[str | None] = mapped_column(String(50))
    measurement_method: Mapped[str | None] = mapped_column(Text)
    # Required, and never defaulted: achievement cannot be computed without it.
    direction: Mapped[KpiDirection] = mapped_column(
        _enum(KpiDirection, "kpi_direction"), nullable=False
    )

    claimed_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    evidence: Mapped[str | None] = mapped_column(Text)
    claimed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    validated_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_note: Mapped[str | None] = mapped_column(Text)

    status: Mapped[KpiStatus] = mapped_column(
        _enum(KpiStatus, "kpi_status"), default=KpiStatus.PENDING, nullable=False
    )

    challenge: Mapped[Challenge] = relationship(back_populates="kpis")
    startup: Mapped[Company | None] = relationship(foreign_keys=[startup_id])


class Proposal(TimestampMixin, Base):
    __tablename__ = "proposal"
    __table_args__ = (UniqueConstraint("challenge_id", "startup_id", name="uq_proposal_once"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenge.id", ondelete="CASCADE"), nullable=False
    )
    startup_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProposalStatus] = mapped_column(
        _enum(ProposalStatus, "proposal_status"), default=ProposalStatus.SUBMITTED, nullable=False
    )

    total_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # Per-criterion sub-scores, each with its own reason.  Never a bare number.
    sub_scores: Mapped[dict | None] = mapped_column(JSONB)

    decline_reason_code: Mapped[DeclineReasonCode | None] = mapped_column(
        _enum(DeclineReasonCode, "decline_reason_code")
    )
    decline_detail: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # An expert claims a proposal out of the queue and scores it by hand, next to
    # the AI summary. The manual rubric is kept apart from the computed
    # sub_scores so the two are never confused for one another.
    claimed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expert_scores: Mapped[dict | None] = mapped_column(JSONB)
    expert_note: Mapped[str | None] = mapped_column(Text)

    challenge: Mapped[Challenge] = relationship(back_populates="proposals")
    startup: Mapped[Company] = relationship()


class Pilot(TimestampMixin, Base):
    __tablename__ = "pilot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenge.id", ondelete="CASCADE"), nullable=False
    )
    startup_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )

    plan: Mapped[dict | None] = mapped_column(JSONB)
    milestones: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[PilotStatus] = mapped_column(
        _enum(PilotStatus, "pilot_status"), default=PilotStatus.PLANNED, nullable=False
    )

    # The recommendation is computed deterministically, but only an officer
    # decision makes an outcome effective.
    recommended_outcome: Mapped[PilotOutcome | None] = mapped_column(
        _enum(PilotOutcome, "pilot_outcome")
    )
    recommendation_reasoning: Mapped[dict | None] = mapped_column(JSONB)
    outcome: Mapped[PilotOutcome | None] = mapped_column(_enum(PilotOutcome, "pilot_outcome"))
    outcome_decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    outcome_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_note: Mapped[str | None] = mapped_column(Text)

    cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    lessons_learned: Mapped[str | None] = mapped_column(Text)
    started_on: Mapped[date | None] = mapped_column(Date)
    planned_end_on: Mapped[date | None] = mapped_column(Date)
    completed_on: Mapped[date | None] = mapped_column(Date)

    challenge: Mapped[Challenge] = relationship()
    startup: Mapped[Company] = relationship(foreign_keys=[startup_id])


class Partnership(TimestampMixin, Base):
    """LARGE-tier arrangement.

    The startup owns the solution and its IP; the prime contractor executes
    within an assigned scope.
    """

    __tablename__ = "partnership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    startup_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    legacy_partner_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenge.id", ondelete="CASCADE"), nullable=False
    )

    startup_scope: Mapped[str | None] = mapped_column(Text)
    execution_scope: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PartnershipStatus] = mapped_column(
        _enum(PartnershipStatus, "partnership_status"),
        default=PartnershipStatus.PROPOSED,
        nullable=False,
    )
    # Display-only milestone and payment state.  No payment integration.
    milestone_status: Mapped[list | None] = mapped_column(JSONB)

    startup: Mapped[Company] = relationship(foreign_keys=[startup_id])
    legacy_partner: Mapped[Company] = relationship(foreign_keys=[legacy_partner_id])
    challenge: Mapped[Challenge] = relationship()


class Award(TimestampMixin, Base):
    __tablename__ = "award"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenge.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    awarded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))

    challenge: Mapped[Challenge] = relationship()
    company: Mapped[Company] = relationship()


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


class ProcurementRule(TimestampMixin, Base):
    """The only place a threshold, limit or percentage may live.

    source_reference empty  -> prototype setting, shown as such in the UI.
    source_reference filled -> traceable to a published policy document.
    """

    __tablename__ = "procurement_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    rule_type: Mapped[RuleType] = mapped_column(_enum(RuleType, "rule_type"), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(300))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProcurementRule {self.rule_name}={self.value}>"


class AuditLog(Base):
    """Append-only trail.

    Actor, timestamp and reason for everything that classifies, scores, triggers
    a fallback, approves or overrides.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    # Free-text actor label so system actions ("tier-engine") stay readable too.
    actor_label: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)

    actor: Mapped[User | None] = relationship()
