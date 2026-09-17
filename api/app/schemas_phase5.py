"""Schemas for matching, evaluation, pilots and partnerships."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DeclineReasonCode, PartnershipStatus, PilotOutcome, PilotStatus


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class SubScoreOut(BaseModel):
    criterion: str
    score: float
    weight: float
    reason: str


class MatchOut(BaseModel):
    company_id: int
    company_name: str
    total_score: float
    sub_scores: list[SubScoreOut]
    proximity: dict
    track_record: dict
    explanation: str
    disclaimer: str


class RankingOut(BaseModel):
    challenge_id: int
    tier: str | None = None
    matches: list[MatchOut]
    note: str


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


class ProposalCreate(BaseModel):
    summary: str = Field(min_length=1, description="How the startup would solve it.")


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    startup_id: int
    summary: str | None = None
    status: str
    total_score: Decimal | None = None
    sub_scores: dict | None = None
    decline_reason_code: DeclineReasonCode | None = None
    decline_detail: str | None = None
    submitted_at: datetime | None = None
    claimed_by_user_id: int | None = None
    expert_scores: dict | None = None
    expert_note: str | None = None


class DeclineRequest(BaseModel):
    """A decline always carries a coded reason. There is no default."""

    decline_reason_code: DeclineReasonCode
    decline_detail: str = Field(
        min_length=1, description="What the startup is told, in plain language."
    )


class ShortlistRequest(BaseModel):
    note: str = Field(min_length=1)


class AwardRequest(BaseModel):
    note: str = Field(min_length=1, description="Why this bidder is being awarded.")


# ---------------------------------------------------------------------------
# Expert evaluation
# ---------------------------------------------------------------------------


class EvaluationBriefOut(BaseModel):
    proposal_id: int
    challenge_title: str
    company_name: str
    ai_summary: dict
    computed_match: MatchOut | None = None
    rubric: list[str]
    note: str


class ExpertScoreIn(BaseModel):
    criterion: str = Field(min_length=1)
    score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=1, description="Every mark carries a reason.")


class EvaluationSubmit(BaseModel):
    scores: list[ExpertScoreIn] = Field(min_length=1)
    note: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Pilots
# ---------------------------------------------------------------------------


class PilotPlanRequest(BaseModel):
    """Officer-approved plan. Dates come from the officer, never from the model."""

    milestones: list[dict] = Field(min_length=1)
    started_on: date
    planned_end_on: date
    cost: Decimal | None = None
    note: str = Field(min_length=1)


class PilotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    startup_id: int
    plan: dict | None = None
    milestones: list | None = None
    status: PilotStatus
    recommended_outcome: PilotOutcome | None = None
    recommendation_reasoning: dict | None = None
    outcome: PilotOutcome | None = None
    outcome_decided_by: int | None = None
    outcome_decided_at: datetime | None = None
    outcome_note: str | None = None
    cost: Decimal | None = None
    lessons_learned: str | None = None
    started_on: date | None = None
    planned_end_on: date | None = None
    completed_on: date | None = None


class MilestoneDraftOut(BaseModel):
    milestones: list[dict]
    source: str
    notes: list[str]


class KpiEvidenceIn(BaseModel):
    claimed_value: Decimal
    evidence: str = Field(min_length=1)


class KpiValidationIn(BaseModel):
    validated_value: Decimal
    validation_note: str = Field(min_length=1)
    accepted: bool = True


class RecommendationOut(BaseModel):
    recommended_outcome: PilotOutcome
    kpis_total: int
    kpis_met: int
    kpis_missed: int
    on_schedule: bool | None = None
    reasoning: list[str]
    kpi_detail: list[dict]
    status: str


class OutcomeDecisionIn(BaseModel):
    """The officer's decision. Only this makes an outcome effective."""

    outcome: PilotOutcome
    note: str = Field(min_length=1)
    lessons_learned: str | None = None
    completed_on: date | None = None


# ---------------------------------------------------------------------------
# Partnerships
# ---------------------------------------------------------------------------


class PartnershipCreate(BaseModel):
    startup_id: int
    legacy_partner_id: int
    startup_scope: str = Field(min_length=1)
    execution_scope: str = Field(min_length=1)
    note: str = Field(min_length=1)


class PartnershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    startup_id: int
    legacy_partner_id: int
    startup_scope: str | None = None
    execution_scope: str | None = None
    status: PartnershipStatus
    milestone_status: list | None = None


class PartnershipView(BaseModel):
    """Solution Owner and Execution Partner, side by side."""

    partnership: PartnershipOut
    solution_owner: dict
    execution_partner: dict
    ip_note: str
    payment_note: str
