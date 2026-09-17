"""Endpoints that expose the Phase 2 engines.

Each one returns its reasoning, not just its answer, and the ones that change
state or fire a trigger write to the audit log.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.enums import UserRole
from app.models import Challenge, Company, User
from app.schemas_engine import (
    BarrierAnalysisOut,
    BarrierRequest,
    ChallengeTierOut,
    EligibilityOut,
    FallbackOut,
    FounderGroupOut,
    RotationOut,
    TierDecisionOut,
    TierRequest,
)
from app.services import audit, barriers, eligibility, fallback, founders, rotation
from app.services.rules import RuleNotFound, RulesService
from app.services.tiering import TierInputMissing, classify

router = APIRouter(prefix="/engine", tags=["engine"])

officer_or_admin = require_roles(UserRole.GOVERNMENT, UserRole.ADMIN)


def rules_service(db: Session = Depends(get_db)) -> RulesService:
    return RulesService(db)


def _missing_rule(error: RuleNotFound) -> HTTPException:
    """A missing rule is a configuration problem, not a bad request."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _get_challenge(db: Session, challenge_id: int) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


def _get_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def _tier_payload(decision) -> dict:
    return {
        "tier": decision.tier,
        "explanation": decision.explanation,
        "factors": [
            {
                "factor": factor.factor,
                "input_value": factor.input_value,
                "effect": factor.effect,
                "reason": factor.reason,
            }
            for factor in decision.factors
        ],
        "rules_cited": [rule.cite() for rule in decision.rules_cited],
    }


# ---------------------------------------------------------------------------
# Tier engine
# ---------------------------------------------------------------------------


@router.post("/tier", response_model=TierDecisionOut)
def preview_tier(
    payload: TierRequest,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    _: User = Depends(officer_or_admin),
) -> TierDecisionOut:
    """Classify without saving anything - the officer's preview while drafting."""
    try:
        decision = classify(
            rules,
            value=payload.value,
            criticality=payload.criticality,
            innovation_potential=payload.innovation_potential,
        )
    except RuleNotFound as error:
        raise _missing_rule(error)
    return TierDecisionOut(**_tier_payload(decision))


@router.post("/challenges/{challenge_id}/classify", response_model=ChallengeTierOut)
def classify_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    current_user: User = Depends(officer_or_admin),
) -> ChallengeTierOut:
    """Classify a stored challenge, save the tier, and log the classification."""
    challenge = _get_challenge(db, challenge_id)

    try:
        decision = classify(
            rules,
            value=challenge.value,
            criticality=challenge.criticality,
            innovation_potential=challenge.innovation_potential,
        )
    except TierInputMissing as error:
        # The department has to supply these. Nothing is guessed on their behalf.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(error), "missing_fields": error.missing},
        )
    except RuleNotFound as error:
        raise _missing_rule(error)

    challenge.tier = decision.tier
    challenge.tier_explanation = decision.explanation

    audit.record(
        db,
        action="TIER_CLASSIFIED",
        reason=decision.explanation,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details=decision.as_details(),
    )
    db.commit()

    return ChallengeTierOut(challenge_id=challenge.id, persisted=True, **_tier_payload(decision))


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


@router.get("/companies/{company_id}/eligibility", response_model=EligibilityOut)
def company_eligibility(
    company_id: int,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    _: User = Depends(officer_or_admin),
) -> EligibilityOut:
    """Both gates for a company, with no challenge in play."""
    company = _get_company(db, company_id)
    try:
        decision = eligibility.assess(db, rules, company)
    except RuleNotFound as error:
        raise _missing_rule(error)
    return EligibilityOut(**decision.as_dict())


@router.get(
    "/challenges/{challenge_id}/eligibility/{company_id}",
    response_model=EligibilityOut,
)
def challenge_eligibility(
    challenge_id: int,
    company_id: int,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    current_user: User = Depends(officer_or_admin),
) -> EligibilityOut:
    """Both gates plus tier access for a company against one challenge."""
    challenge = _get_challenge(db, challenge_id)
    company = _get_company(db, company_id)

    if challenge.tier is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The challenge has no tier yet. Classify it first.",
        )

    try:
        decision = eligibility.assess(db, rules, company, challenge, actor=current_user)
    except RuleNotFound as error:
        raise _missing_rule(error)

    # Assessing MEDIUM access for a non-startup evaluates the fallback trigger,
    # which writes an audit entry.
    db.commit()
    return EligibilityOut(**decision.as_dict())


@router.post("/challenges/{challenge_id}/fallback", response_model=FallbackOut)
def evaluate_fallback(
    challenge_id: int,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    current_user: User = Depends(officer_or_admin),
) -> FallbackOut:
    """Evaluate the MEDIUM-tier fallback trigger and log the values behind it."""
    challenge = _get_challenge(db, challenge_id)
    try:
        decision = fallback.evaluate_and_log(db, rules, challenge, actor=current_user)
    except RuleNotFound as error:
        raise _missing_rule(error)
    db.commit()
    return FallbackOut(**decision.as_details())


# ---------------------------------------------------------------------------
# Barrier analysis
# ---------------------------------------------------------------------------


@router.post("/barrier-analysis", response_model=BarrierAnalysisOut)
def barrier_analysis(
    payload: BarrierRequest,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    _: User = Depends(officer_or_admin),
) -> BarrierAnalysisOut:
    """Flag proposed eligibility criteria that exclude startups. Nothing is blocked."""
    proposed = [
        barriers.ProposedCriterion(code=item.code, detail=item.detail)
        for item in payload.criteria
    ]
    try:
        analysis = barriers.analyse(rules, proposed)
    except RuleNotFound as error:
        raise _missing_rule(error)
    return BarrierAnalysisOut(**analysis.as_dict())


# ---------------------------------------------------------------------------
# Rotation and founder groups
# ---------------------------------------------------------------------------


@router.get(
    "/challenges/{challenge_id}/rotation/{company_id}",
    response_model=RotationOut,
)
def check_rotation(
    challenge_id: int,
    company_id: int,
    db: Session = Depends(get_db),
    rules: RulesService = Depends(rules_service),
    current_user: User = Depends(officer_or_admin),
) -> RotationOut:
    """Whether the rotation rule blocks an award to this company.

    Rotation applies to the SMALL tier only, and a block is written to the audit
    log with the founder group and the values behind it.
    """
    challenge = _get_challenge(db, challenge_id)
    company = _get_company(db, company_id)
    try:
        decision = rotation.evaluate_and_log(db, rules, challenge, company, actor=current_user)
    except RuleNotFound as error:
        raise _missing_rule(error)
    db.commit()
    return RotationOut(**decision.as_details())


@router.get("/companies/{company_id}/founder-group", response_model=FounderGroupOut)
def founder_group(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(officer_or_admin),
) -> FounderGroupOut:
    """Every company connected to this one by a shared founder."""
    company = _get_company(db, company_id)
    return FounderGroupOut(**founders.resolve(db, company.id).as_dict())
