"""Proposals and uploaded documents.

`documents` is polymorphic — `owner_id` points at either a startup or a
proposal and carries no foreign key, because it cannot reference two tables.
Access control for it therefore lives entirely in the service layer, never in
the database. That is the same arrangement the Java `DocumentService` used and
it must be preserved when the service is ported.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import created_at, updated_at, uuid_fk, uuid_pk
from app.models.challenge import Challenge
from app.models.enums import (
    DocumentOwnerType,
    DocumentType,
    ProposalStatus,
    VerificationStatus,
    pg_enum,
)
from app.models.startup import Startup


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("challenge_id", "startup_id",
                         name="proposals_challenge_id_startup_id_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # RESTRICT on both sides: a proposal is an audit-relevant record and must
    # not vanish because a challenge or startup row was removed.
    challenge_id: Mapped[uuid.UUID] = uuid_fk(
        "challenges.id", ondelete="RESTRICT", index=True)
    startup_id: Mapped[uuid.UUID] = uuid_fk(
        "startups.id", ondelete="RESTRICT", index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_approach: Mapped[str | None] = mapped_column(Text)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    timeline_estimate_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[ProposalStatus] = mapped_column(
        pg_enum(ProposalStatus, "proposal_status"), nullable=False,
        default=ProposalStatus.SUBMITTED, index=True)
    submitted_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    challenge: Mapped[Challenge] = relationship(back_populates="proposals", lazy="joined")
    startup: Mapped[Startup] = relationship(lazy="joined")
    evaluations: Mapped[list["Evaluation"]] = relationship(  # noqa: F821
        back_populates="proposal", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_type: Mapped[DocumentOwnerType] = mapped_column(
        pg_enum(DocumentOwnerType, "document_owner_type"), nullable=False)
    #: Deliberately un-constrained: points at `startups.id` or `proposals.id`.
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        pg_enum(DocumentType, "document_type"), nullable=False)
    #: Server-side path. Never exposed to clients.
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        pg_enum(VerificationStatus, "verification_status"), nullable=False,
        default=VerificationStatus.PENDING, index=True)
    verification_notes: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = created_at()
