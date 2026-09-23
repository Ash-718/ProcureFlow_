"""
`/api/v1/proposals` — submission, listing and status changes.

Route order matters: `/mine` and `/queue` are declared before `/{proposal_id}`,
or FastAPI would try to parse those literals as UUIDs.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.proposal import (
    ProposalCreateRequest,
    ProposalResponse,
    ProposalStatusUpdateRequest,
)
from app.security.deps import CurrentUserEntity, require_roles
from app.services.proposal_service import ProposalService

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])

DbSession = Annotated[Session, Depends(get_db)]
StartupOnly = Depends(require_roles(RoleName.STARTUP))
ExpertOnly = Depends(require_roles(RoleName.EXPERT))
ReviewerRoles = Depends(
    require_roles(RoleName.GOVERNMENT, RoleName.EXPERT, RoleName.ADMIN))
GovernmentOrAdmin = Depends(require_roles(RoleName.GOVERNMENT, RoleName.ADMIN))


@router.post("/challenges/{challenge_id}", response_model=ProposalResponse,
             status_code=status.HTTP_201_CREATED, dependencies=[StartupOnly])
def submit_proposal(challenge_id: uuid.UUID, request: ProposalCreateRequest,
                    db: DbSession, actor: CurrentUserEntity) -> ProposalResponse:
    """
    Submit a proposal to a challenge.

    409 if the challenge is DRAFT or CLOSED, or if this startup has already
    proposed to it — one proposal per startup per challenge.
    """
    return ProposalService(db).submit(actor, challenge_id, request)


@router.get("/mine", response_model=list[ProposalResponse], dependencies=[StartupOnly])
def list_my_proposals(db: DbSession, actor: CurrentUserEntity) -> list[ProposalResponse]:
    return ProposalService(db).list_mine(actor)


@router.get("/queue", response_model=list[ProposalResponse], dependencies=[ExpertOnly])
def expert_queue(db: DbSession) -> list[ProposalResponse]:
    """Proposals awaiting or under review — the expert's work list."""
    return ProposalService(db).list_expert_queue()


@router.get("/challenges/{challenge_id}", response_model=list[ProposalResponse],
            dependencies=[ReviewerRoles])
def list_for_challenge(challenge_id: uuid.UUID, db: DbSession,
                       actor: CurrentUserEntity) -> list[ProposalResponse]:
    """
    Proposals for one challenge.

    Government and admin callers are ownership-checked in the service; any
    expert may list them, since the schema models no expert assignment.
    """
    return ProposalService(db).list_for_challenge(actor, challenge_id)


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_proposal(proposal_id: uuid.UUID, db: DbSession,
                 actor: CurrentUserEntity) -> ProposalResponse:
    """
    One proposal.

    Open to every role, then narrowed by ownership in the service: a startup
    reaching for another's proposal gets 403.
    """
    return ProposalService(db).get_by_id(actor, proposal_id)


@router.patch("/{proposal_id}/status", response_model=ProposalResponse,
              dependencies=[GovernmentOrAdmin])
def update_status(proposal_id: uuid.UUID, request: ProposalStatusUpdateRequest,
                  db: DbSession, actor: CurrentUserEntity) -> ProposalResponse:
    """Move a proposal through its lifecycle. Notifies the startup."""
    return ProposalService(db).update_status(actor, proposal_id, request.status)
