"""Knowledge base of completed pilots.

`success` is a genuine **tri-state**: `True` when the final decision was SCALE,
`False` when REJECT, and `NULL` for MODIFY or an undecided pilot. It must never
be coerced to a plain boolean — "we modified it" is not "it failed", and the
knowledge-base filter depends on that distinction.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.core.database import Base
from app.models.base import created_at, uuid_fk, uuid_pk
from app.models.identity import GovernmentDepartment
from app.models.pilot import Pilot


class PilotKnowledgeBase(Base):
    __tablename__ = "pilot_knowledge_base"

    id: Mapped[uuid.UUID] = uuid_pk()
    pilot_id: Mapped[uuid.UUID] = uuid_fk(
        "pilots.id", ondelete="CASCADE", unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    #: Native `text[]`, GIN-indexed for fast tag-overlap search.
    technology_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list)
    department_id: Mapped[uuid.UUID] = uuid_fk(
        "government_departments.id", ondelete="RESTRICT", index=True)
    outcome_summary: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool | None] = mapped_column(Boolean, index=True)
    #: Concatenated text the embedding is computed from.
    searchable_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at()

    pilot: Mapped[Pilot] = relationship(back_populates="knowledge_base_entry")
    department: Mapped[GovernmentDepartment] = relationship(lazy="joined")
