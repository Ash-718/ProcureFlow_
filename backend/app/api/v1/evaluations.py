"""`/api/v1/evaluations` — rubric, AI-assisted analysis and expert scoring."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.evaluation import (
    AiAnalysisResponse,
    EvaluationCriterionResponse,
    EvaluationResponse,
    EvaluationSubmitRequest,
)
from app.security.deps import CurrentUserEntity, require_roles
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])

DbSession = Annotated[Session, Depends(get_db)]
ReviewerRoles = Depends(
    require_roles(RoleName.EXPERT, RoleName.GOVERNMENT, RoleName.ADMIN))
ExpertOnly = Depends(require_roles(RoleName.EXPERT))


@router.get("/proposals/{proposal_id}/criteria",
            response_model=list[EvaluationCriterionResponse],
            dependencies=[ReviewerRoles])
def get_criteria(proposal_id: uuid.UUID,
                 db: DbSession) -> list[EvaluationCriterionResponse]:
    """The rubric for the proposal's challenge."""
    return EvaluationService(db).get_criteria_for_proposal(proposal_id)


@router.get("/proposals/{proposal_id}/ai-analysis",
            response_model=AiAnalysisResponse, dependencies=[ReviewerRoles])
def get_ai_analysis(proposal_id: uuid.UUID, db: DbSession) -> AiAnalysisResponse:
    """
    AI-assisted analysis of one proposal.

    Narrates the same component scores the matching pipeline computes — the
    expert view is deliberately not a second, unaccountable model. The text
    itself says it does not replace the expert's judgment.
    """
    return AiAnalysisResponse(
        summary=EvaluationService(db).get_ai_analysis(proposal_id))


@router.post("/proposals/{proposal_id}", response_model=EvaluationResponse,
             dependencies=[ExpertOnly])
def submit_evaluation(proposal_id: uuid.UUID, request: EvaluationSubmitRequest,
                      db: DbSession, actor: CurrentUserEntity) -> EvaluationResponse:
    """
    Record an expert's scores. 200, not 201 — re-submitting updates in place.

    Advances a SUBMITTED proposal to UNDER_REVIEW and notifies the department.
    """
    return EvaluationService(db).submit(actor, proposal_id, request)
