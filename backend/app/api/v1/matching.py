"""
`/api/v1/matching` — AI startup discovery for a challenge.

Restricted to the owning department and admins. A startup must never see how it
ranked against its competitors, so this is a substantive access control.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.matching import MatchResponse, MatchResultRow
from app.security.deps import CurrentUserEntity, require_roles
from app.services.matching_service import MatchingService

router = APIRouter(prefix="/api/v1/matching", tags=["matching"])

DbSession = Annotated[Session, Depends(get_db)]
GovernmentOrAdmin = Depends(require_roles(RoleName.GOVERNMENT, RoleName.ADMIN))


@router.post("/challenges/{challenge_id}/run", response_model=MatchResponse,
             dependencies=[GovernmentOrAdmin])
def run_matching(challenge_id: uuid.UUID, db: DbSession,
                 actor: CurrentUserEntity) -> MatchResponse:
    """
    Rank every startup against this challenge.

    Runs the real pipeline: `all-MiniLM-L6-v2` embeddings, the five weighted
    components, and deterministic template explanations. Component scores come
    back **nested** under `componentScores`.
    """
    return MatchingService(db).run_matching(actor, challenge_id)


@router.get("/challenges/{challenge_id}", response_model=list[MatchResultRow])
def get_results(challenge_id: uuid.UUID, db: DbSession,
                actor: CurrentUserEntity) -> list[MatchResultRow]:
    """
    The stored ranking from the most recent run.

    Note the shape difference from the run endpoint: these rows carry the
    scores **flat** (`semanticSimilarityScore`, …), which is what the
    frontend's `MatchResultRow` expects.
    """
    return MatchingService(db).get_results(actor, challenge_id)
