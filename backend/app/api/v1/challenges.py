"""
`/api/v1/challenges` — challenge authoring and browsing.

Write operations are GOVERNMENT-only; reads are open to any authenticated user
and scoped by role inside the service (an admin sees everything, a department
sees its own including drafts, everyone else sees published-and-beyond).
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.challenge import ChallengeDraftRequest, ChallengeResponse
from app.security.deps import CurrentUserEntity, require_roles
from app.services.challenge_service import ChallengeService

router = APIRouter(prefix="/api/v1/challenges", tags=["challenges"])

DbSession = Annotated[Session, Depends(get_db)]
GovernmentOnly = Depends(require_roles(RoleName.GOVERNMENT))


@router.post("", response_model=ChallengeResponse,
             status_code=status.HTTP_201_CREATED,
             dependencies=[GovernmentOnly])
def create_challenge(request: ChallengeDraftRequest, db: DbSession,
                     actor: CurrentUserEntity) -> ChallengeResponse:
    """Create a DRAFT challenge. Returns **201**, matching the Java controller."""
    return ChallengeService(db).create(actor, request)


@router.put("/{challenge_id}", response_model=ChallengeResponse,
            dependencies=[GovernmentOnly])
def update_challenge(challenge_id: uuid.UUID, request: ChallengeDraftRequest,
                     db: DbSession, actor: CurrentUserEntity) -> ChallengeResponse:
    """
    Replace a DRAFT challenge.

    409 if the challenge has already been published — requirements and KPIs are
    replaced wholesale, which is not safe once proposals reference them.
    """
    return ChallengeService(db).update(actor, challenge_id, request)


@router.post("/{challenge_id}/publish", response_model=ChallengeResponse,
             dependencies=[GovernmentOnly])
def publish_challenge(challenge_id: uuid.UUID, db: DbSession,
                      actor: CurrentUserEntity) -> ChallengeResponse:
    """
    Publish a DRAFT, making it visible to startups and experts.

    Seeds the default evaluation rubric if none exists, and queues an embedding
    refresh so the challenge is matchable.
    """
    return ChallengeService(db).publish(actor, challenge_id)


@router.get("/{challenge_id}", response_model=ChallengeResponse)
def get_challenge(challenge_id: uuid.UUID, db: DbSession,
                  actor: CurrentUserEntity) -> ChallengeResponse:
    """
    One challenge.

    A draft belonging to another department returns **404**, not 403 — its
    existence is not disclosed.
    """
    return ChallengeService(db).get_by_id(actor, challenge_id)


@router.get("", response_model=list[ChallengeResponse])
def list_challenges(db: DbSession, actor: CurrentUserEntity) -> list[ChallengeResponse]:
    """Challenges visible to the caller, scoped by role."""
    return ChallengeService(db).list_for_actor(actor)
