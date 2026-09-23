"""
`/api/v1/knowledge-base` — searchable record of completed pilots.

The point of the feature: a department can see what has already been tried in
its domain, and how it turned out, before commissioning something similar.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.system import (
    KnowledgeBaseEntryResponse,
    SimilarPilotsRequest,
    SimilarPilotsResponse,
)
from app.security.deps import CurrentUser, require_roles
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])

DbSession = Annotated[Session, Depends(get_db)]
GovernmentOrAdmin = Depends(require_roles(RoleName.GOVERNMENT, RoleName.ADMIN))


@router.get("", response_model=list[KnowledgeBaseEntryResponse])
def search(
    db: DbSession,
    current: CurrentUser,
    domain: Annotated[str | None, Query()] = None,
    technology: Annotated[str | None, Query()] = None,
    success: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> list[KnowledgeBaseEntryResponse]:
    """
    Search past pilots. Open to any authenticated role.

    `success` is tri-state: omit it for everything, `true` for scaled pilots,
    `false` for rejected. Pilots recommended MODIFY have a null `success` and
    are returned only when the filter is omitted — they were neither.
    """
    return KnowledgeBaseService(db).search(
        domain=domain, technology=technology, success=success, query=q)


@router.post("/similar-for-draft", response_model=SimilarPilotsResponse,
             dependencies=[GovernmentOrAdmin])
def similar_for_draft(request: SimilarPilotsRequest,
                      db: DbSession) -> SimilarPilotsResponse:
    """
    Past pilots similar to a challenge being drafted.

    Runs the real embedding pipeline — the draft text is embedded and compared
    by cosine similarity against each stored entry. Scores are percentages.
    """
    return KnowledgeBaseService(db).find_similar_for_draft(request)
