"""Matching results and the configurable weight table.

`match_results` is a *snapshot*, not a history: `MatchingService` deletes every
row for a challenge and reinserts the current run, so the table always reflects
the latest computation. `UNIQUE (challenge_id, startup_id)` enforces that.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import created_at, uuid_fk, uuid_pk
from app.models.challenge import Challenge
from app.models.startup import Startup


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("challenge_id", "startup_id", name="match_results_challenge_id_startup_id_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="CASCADE", index=True)
    startup_id: Mapped[uuid.UUID] = uuid_fk(
        "startups.id", ondelete="CASCADE", index=True)

    # All six scores are on a 0-100 scale, NUMERIC(6,3) in the database.
    overall_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    semantic_similarity_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    technology_match_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    domain_match_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    experience_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    readiness_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)

    #: `{"reasons": [...], "gaps": [...], "components": {...}}` — the payload
    #: the match-explainability UI renders.
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_provider: Mapped[str] = mapped_column(
        String(60), nullable=False, default="local-fallback")
    computed_at: Mapped[datetime] = created_at()

    challenge: Mapped[Challenge] = relationship(back_populates="match_results")
    startup: Mapped[Startup] = relationship(lazy="joined")


class AiMatchingConfig(Base):
    """
    Persisted matching weights.

    Seeded by `database/schema.sql` and shown in the UI so the formula is
    visible rather than buried in settings. The running weights come from
    `Settings.matching_weights`; this table documents the defaults.
    """

    __tablename__ = "ai_matching_config"

    id: Mapped[uuid.UUID] = uuid_pk()
    config_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
