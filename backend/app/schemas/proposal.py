"""Proposals and documents."""
from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import (
    DocumentOwnerType,
    DocumentType,
    ProposalStatus,
    VerificationStatus,
)
from app.schemas.base import CamelModel, CamelRequest, Instant


class ProposalResponse(CamelModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    #: Joined from `challenges`.
    challenge_title: str
    startup_id: uuid.UUID
    #: Joined from `startups`.
    company_name: str
    summary: str
    proposed_approach: str | None
    cost_estimate: float | None
    timeline_estimate_days: int | None
    status: ProposalStatus
    submitted_at: Instant

    @classmethod
    def from_entity(cls, proposal) -> "ProposalResponse":
        return cls(
            id=proposal.id,
            challenge_id=proposal.challenge_id,
            challenge_title=proposal.challenge.title,
            startup_id=proposal.startup_id,
            company_name=proposal.startup.company_name,
            summary=proposal.summary,
            proposed_approach=proposal.proposed_approach,
            cost_estimate=(
                float(proposal.cost_estimate) if proposal.cost_estimate is not None else None
            ),
            timeline_estimate_days=proposal.timeline_estimate_days,
            status=proposal.status,
            submitted_at=proposal.submitted_at,
        )


class DocumentResponse(CamelModel):
    """
    An uploaded document.

    `file_path` is deliberately absent: it is a server-side location and the
    Java DTO withheld it too. Exposing it would leak the storage layout.
    """

    id: uuid.UUID
    owner_type: DocumentOwnerType
    owner_id: uuid.UUID
    document_type: DocumentType
    original_filename: str | None
    verification_status: VerificationStatus
    verification_notes: str | None
    uploaded_at: Instant


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class ProposalCreateRequest(CamelRequest):
    summary: str = Field(min_length=1)
    proposed_approach: str | None = None
    cost_estimate: float | None = None
    timeline_estimate_days: int | None = None


class ProposalStatusUpdateRequest(CamelRequest):
    status: ProposalStatus


__all__ = [
    "DocumentResponse",
    "ProposalCreateRequest",
    "ProposalResponse",
    "ProposalStatusUpdateRequest",
]
