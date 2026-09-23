"""Expert evaluation: per-challenge rubric, evaluations, per-criterion scores.

`ai_assist_summary` stores a *snapshot* of the AI analysis text as it was when
the expert submitted — not a live pointer. The expert's record has to reflect
what they actually read, even if the model or the proposal changes later.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import created_at, nullable_ts, uuid_fk, uuid_pk
from app.models.challenge import Challenge
from app.models.identity import User
from app.models.proposal import Proposal


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="CASCADE", index=True)
    criterion_name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("10.00"))
    weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("1.00"))

    challenge: Mapped[Challenge] = relationship(back_populates="criteria")


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("proposal_id", "expert_id",
                         name="evaluations_proposal_id_expert_id_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    proposal_id: Mapped[uuid.UUID] = uuid_fk(
        "proposals.id", ondelete="CASCADE", index=True)
    expert_id: Mapped[uuid.UUID] = uuid_fk(
        "users.id", ondelete="RESTRICT", index=True)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    comments: Mapped[str | None] = mapped_column(Text)
    ai_assist_summary: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = nullable_ts()
    created_at: Mapped[datetime] = created_at()

    proposal: Mapped[Proposal] = relationship(back_populates="evaluations")
    expert: Mapped[User] = relationship(lazy="joined")
    scores: Mapped[list["EvaluationScore"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "criterion_id",
                         name="evaluation_scores_evaluation_id_criterion_id_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    evaluation_id: Mapped[uuid.UUID] = uuid_fk(
        "evaluations.id", ondelete="CASCADE", index=True)
    criterion_id: Mapped[uuid.UUID] = uuid_fk(
        "evaluation_criteria.id", ondelete="RESTRICT")
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    evaluation: Mapped[Evaluation] = relationship(back_populates="scores")
    criterion: Mapped[EvaluationCriterion] = relationship(lazy="joined")
