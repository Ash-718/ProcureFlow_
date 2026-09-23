"""Schemas for the challenge lifecycle: draft, analyze, approve, publish."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ChallengeStatus, KpiDirection, Level, Tier


class AnalyzeRequest(BaseModel):
    """Free text, plus the three fields only the department can supply.

    Leave budget, timeline or location out and they come back in missing_fields.
    Nothing fills them in on the department's behalf.
    """

    description: str = Field(min_length=1)
    budget: Decimal | None = None
    timeline: str | None = None
    location: str | None = None


class SuggestedKpiOut(BaseModel):
    name: str
    target_value: Decimal | None = None
    unit: str
    measurement_method: str
    direction: KpiDirection


class AnalyzeResponse(BaseModel):
    problem_statement: str
    required_capabilities: list[str]
    expected_outcomes: list[str]
    suggested_kpis: list[SuggestedKpiOut]
    missing_fields: list[str]
    budget: Decimal | None = None
    timeline: str | None = None
    location: str | None = None
    source: str
    attempts: int
    notes: list[str]


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    department_id: int
    category: str | None = None
    district: str | None = None
    requires_onsite: bool = False
    # All three optional: an unanswered field becomes a missing_field, not a guess.
    budget: Decimal | None = None
    timeline: str | None = None
    criticality: Level | None = None
    innovation_potential: Level | None = None


class ChallengeUpdate(BaseModel):
    """Filling in what the analyzer reported missing."""

    title: str | None = None
    category: str | None = None
    district: str | None = None
    requires_onsite: bool | None = None
    budget: Decimal | None = None
    timeline: str | None = None
    criticality: Level | None = None
    innovation_potential: Level | None = None


class KpiIn(BaseModel):
    name: str = Field(min_length=1)
    target_value: Decimal
    unit: str = Field(min_length=1)
    measurement_method: str = Field(min_length=1)
    direction: KpiDirection


class KpiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    startup_id: int | None = None
    name: str
    target_value: Decimal | None = None
    unit: str | None = None
    measurement_method: str | None = None
    direction: KpiDirection
    claimed_value: Decimal | None = None
    evidence: str | None = None
    validated_value: Decimal | None = None
    validated_by: int | None = None
    validation_note: str | None = None
    status: str


class ApproveRequest(BaseModel):
    """Officer approval. This is what locks the KPIs."""

    kpis: list[KpiIn] = Field(min_length=1)
    note: str = Field(min_length=1, description="Why the officer is approving this spec.")


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description_raw: str
    department_id: int
    value: Decimal | None = None
    criticality: Level | None = None
    innovation_potential: Level | None = None
    tier: Tier | None = None
    tier_explanation: str | None = None
    status: ChallengeStatus
    district: str | None = None
    requires_onsite: bool
    category: str | None = None
    structured_spec: dict | None = None
    missing_fields: list[str] | None = None
    kpis_locked: bool
    approved_at: datetime | None = None
    published_at: datetime | None = None
    bid_closes_at: datetime | None = None


class ChallengeDetail(ChallengeOut):
    kpis: list[KpiOut] = []


class PriorPilotOut(BaseModel):
    challenge_id: int
    pilot_id: int
    title: str
    department: str
    district: str | None = None
    category: str | None = None
    startup: str
    outcome: str | None = None
    cost: str | None = None
    lessons_learned: str | None = None
    validated_kpis: list[dict]
    similarity: float


class KnowledgeSearchOut(BaseModel):
    query: str
    matches: list[PriorPilotOut]
    semantic: bool
    note: str
