"""
AI matching payloads.

Two distinct shapes, and the difference is easy to get wrong:

* :class:`MatchResponse` — what ``POST /matching/challenges/{id}/run`` returns.
  Component scores are **nested** under ``componentScores``.
* :class:`MatchResultRow` — what ``GET /matching/challenges/{id}`` returns,
  read back from ``match_results``. The same scores are **flat**, with
  different key names (``semanticSimilarityScore`` rather than
  ``semanticSimilarity``).

The frontend has separate types for each and renders both, so neither can be
collapsed into the other.

Every value here originates in the real scoring pipeline
(`app/ai/scoring.py` from Phase 5). Nothing in this module computes or
defaults a score.
"""
from __future__ import annotations

import uuid

from app.schemas.base import CamelModel


class ComponentScores(CamelModel):
    """
    The five weighted components, 0-100.

    Note the deliberately inconsistent naming — three bare, two suffixed with
    ``Score``. That is what the frontend's `ComponentScores` interface
    declares, so it is reproduced exactly rather than tidied.
    """

    semantic_similarity: float
    technology_match: float
    domain_match: float
    experience_score: float
    readiness_score: float


class MatchCandidate(CamelModel):
    """One ranked startup in a live matching run."""

    startup_id: uuid.UUID
    company_name: str
    rank: int
    overall_score: float
    component_scores: ComponentScores
    #: Deterministic, template-built explanations from `app/ai/explanations.py`.
    reasons: list[str] = []
    gaps: list[str] = []


class MatchResponse(CamelModel):
    """`POST /matching/challenges/{challengeId}/run`."""

    challenge_id: uuid.UUID
    #: e.g. `"local-fallback"` — the embedding provider that actually ran.
    ai_provider: str
    #: The weighted formula in force, surfaced so the UI can show the maths.
    weights: dict[str, float]
    total_candidates_considered: int
    results: list[MatchCandidate] = []


class MatchResultRow(CamelModel):
    """
    `GET /matching/challenges/{challengeId}` — one persisted `match_results` row.

    Flat scores, unlike :class:`MatchCandidate`.
    """

    startup_id: uuid.UUID
    company_name: str
    rank: int
    overall_score: float
    semantic_similarity_score: float
    technology_match_score: float
    domain_match_score: float
    experience_score: float
    readiness_score: float
    reasons: list[str] = []
    gaps: list[str] = []
    ai_provider: str

    @classmethod
    def from_entity(cls, result) -> "MatchResultRow":
        """
        Build from a `MatchResult` row.

        `explanation_json` is written by the AI pipeline; the `.get` defaults
        cover a row persisted by an older revision that lacked one of the keys,
        rather than substituting for a missing computation.
        """
        explanation = result.explanation_json or {}
        return cls(
            startup_id=result.startup_id,
            company_name=result.startup.company_name,
            rank=result.rank,
            overall_score=float(result.overall_score),
            semantic_similarity_score=float(result.semantic_similarity_score),
            technology_match_score=float(result.technology_match_score),
            domain_match_score=float(result.domain_match_score),
            experience_score=float(result.experience_score),
            readiness_score=float(result.readiness_score),
            reasons=explanation.get("reasons", []),
            gaps=explanation.get("gaps", []),
            ai_provider=result.ai_provider,
        )


__all__ = [
    "ComponentScores",
    "MatchCandidate",
    "MatchResponse",
    "MatchResultRow",
]
