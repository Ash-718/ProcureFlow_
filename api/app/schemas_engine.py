"""Request and response schemas for the Phase 2 engines."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.enums import Level, Tier
from app.services.barriers import BarrierCode


# ---------------------------------------------------------------------------
# Tier engine
# ---------------------------------------------------------------------------


class TierRequest(BaseModel):
    """A tier preview. Every field is required: the engine never guesses one."""

    value: Decimal
    criticality: Level
    innovation_potential: Level


class TierFactorOut(BaseModel):
    factor: str
    input_value: str
    effect: str
    reason: str


class TierDecisionOut(BaseModel):
    tier: Tier
    explanation: str
    factors: list[TierFactorOut]
    rules_cited: list[str]


class ChallengeTierOut(TierDecisionOut):
    challenge_id: int
    persisted: bool


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


class CriterionOut(BaseModel):
    code: str
    label: str
    passed: bool
    reason: str
    basis: str


class GateOut(BaseModel):
    gate: str
    passed: bool
    criteria: list[CriterionOut]


class FallbackOut(BaseModel):
    fired: bool
    window_closed: bool
    window_closes_at: str | None = None
    startup_bids: int
    qualified_startup_bids: int
    reasons: list[str]
    rules_cited: list[str]


class RotationOut(BaseModel):
    applies: bool
    blocked: bool
    consecutive_awards: int
    qualified_alternatives: int
    founder_group: dict | None = None
    reasons: list[str]
    rules_cited: list[str]


class TierAccessOut(BaseModel):
    tier: Tier
    allowed: bool
    reason: str
    fallback: FallbackOut | None = None
    rotation: RotationOut | None = None
    validated_kpi_history: dict | None = None


class EligibilityOut(BaseModel):
    company_id: int
    company_name: str
    company_type: str
    tier: Tier | None = None
    gate_one: GateOut
    gate_two: GateOut
    tier_access: TierAccessOut | None = None
    eligible: bool
    rules_cited: list[str]


# ---------------------------------------------------------------------------
# Barrier analysis
# ---------------------------------------------------------------------------


class ProposedCriterionIn(BaseModel):
    code: BarrierCode
    detail: str = Field(default="", description="The criterion as the department worded it.")


class BarrierRequest(BaseModel):
    criteria: list[ProposedCriterionIn]


class CriterionFlagOut(BaseModel):
    code: str
    label: str
    detail: str
    excludes_startups: bool | None = None
    classification: str
    reason: str
    rule_cited: str | None = None
    officer_action: str


class BarrierAnalysisOut(BaseModel):
    criteria: list[CriterionFlagOut]
    flagged: int
    summary: str


# ---------------------------------------------------------------------------
# Rule editing
# ---------------------------------------------------------------------------


class RuleUpdate(BaseModel):
    """Every field is optional; only what is supplied changes."""

    value: Decimal | None = None
    active: bool | None = None
    source_reference: str | None = None
    effective_from: date | None = None
    description: str | None = None
    # An override of a governance setting is recorded with a reason, always.
    reason: str = Field(min_length=1, description="Why this rule is being changed.")



# ---------------------------------------------------------------------------
# Splitting detection
# ---------------------------------------------------------------------------


class ClusterMemberOut(BaseModel):
    challenge_id: int
    title: str
    value: str
    created_at: str
    band: Tier


class SplittingClusterOut(BaseModel):
    department: str
    category: str | None = None
    window_days: int
    members: list[ClusterMemberOut]
    combined_value: str
    highest_individual_band: Tier
    combined_band: Tier
    reason: str


class SplittingScanOut(BaseModel):
    window_days: int
    clusters: list[SplittingClusterOut]
    rules_cited: list[str]
    summary: str


class FounderGroupOut(BaseModel):
    company_ids: list[int]
    founder_ids: list[int]
    founders: list[str]
    companies: list[str]
