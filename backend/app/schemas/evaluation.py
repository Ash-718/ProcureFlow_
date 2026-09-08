"""
Expert evaluation payloads.

`aiAssistSummary` is a stored snapshot of the AI analysis as the expert saw it
at submission time, not a live regeneration — the record has to reflect what
they actually read.
"""
from __future__ import annotations

import uuid

from pydantic import Field

from app.schemas.base import CamelModel, CamelRequest, OptionalInstant


class EvaluationCriterionResponse(CamelModel):
    id: uuid.UUID
    criterion_name: str
    max_score: float
    weight: float


class EvaluationScoreResponse(CamelModel):
    criterion_id: uuid.UUID
    #: Joined from `evaluation_criteria` so the UI can label a score without
    #: a second request.
    criterion_name: str
    score: float
    remarks: str | None


class EvaluationResponse(CamelModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    expert_id: uuid.UUID
    #: Joined from `users`.
    expert_name: str
    total_score: float | None
    comments: str | None
    ai_assist_summary: str | None
    submitted_at: OptionalInstant
    scores: list[EvaluationScoreResponse] = []

    @classmethod
    def from_entity(cls, evaluation) -> "EvaluationResponse":
        return cls(
            id=evaluation.id,
            proposal_id=evaluation.proposal_id,
            expert_id=evaluation.expert_id,
            expert_name=evaluation.expert.full_name,
            total_score=(
                float(evaluation.total_score) if evaluation.total_score is not None else None
            ),
            comments=evaluation.comments,
            ai_assist_summary=evaluation.ai_assist_summary,
            submitted_at=evaluation.submitted_at,
            scores=[
                EvaluationScoreResponse(
                    criterion_id=s.criterion_id,
                    criterion_name=s.criterion.criterion_name,
                    score=float(s.score),
                    remarks=s.remarks,
                )
                for s in evaluation.scores
            ],
        )


class AiAnalysisResponse(CamelModel):
    """
    `GET /evaluations/proposals/{id}/ai-analysis`.

    Exactly one field. The Java controller returns `Map.of("summary", ...)` and
    `EvaluationApi.aiAnalysis` is typed `{ summary: string }`, so adding an
    `aiProvider` here would be a contract difference for no gain.
    """

    summary: str


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class EvaluationScoreRequest(CamelRequest):
    criterion_id: uuid.UUID
    score: float = Field(ge=0)
    remarks: str | None = None


class EvaluationSubmitRequest(CamelRequest):
    comments: str | None = None
    scores: list[EvaluationScoreRequest] = Field(min_length=1)


__all__ = [
    "AiAnalysisResponse",
    "EvaluationCriterionResponse",
    "EvaluationResponse",
    "EvaluationScoreRequest",
    "EvaluationScoreResponse",
    "EvaluationSubmitRequest",
]
