"""The challenge lifecycle: draft, analyze, fill the gaps, approve, publish.

The order matters and the server enforces it:

* analyze structures the text but never fills in budget, timeline or location
* a challenge cannot be published while anything is still missing
* approval locks the KPIs, and locked KPIs cannot be changed by anyone
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.enums import ChallengeStatus, KpiStatus, UserRole
from app.models import Challenge, Department, Kpi, User
from app.schemas_challenge import (
    AnalyzeRequest,
    AnalyzeResponse,
    ApproveRequest,
    ChallengeCreate,
    ChallengeDetail,
    ChallengeOut,
    ChallengeUpdate,
    KnowledgeSearchOut,
)
from app.services import analyzer, audit, knowledge
from app.services.analyzer import DEPARTMENT_ONLY_FIELDS, MISSING_KPI_TARGETS
from app.services.rules import RuleNotFound, RulesService
from app.services.tiering import TierInputMissing, classify

router = APIRouter(prefix="/challenges", tags=["challenges"])

officer_or_admin = require_roles(UserRole.GOVERNMENT, UserRole.ADMIN)

BID_WINDOW_DAYS = "BID_WINDOW_DAYS"

# Tier classification needs these two, and the department supplies them.
CLASSIFICATION_FIELDS = ("criticality", "innovation_potential")


def _get(db: Session, challenge_id: int) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


def missing_fields_for(challenge: Challenge) -> list[str]:
    """Everything still outstanding before this challenge can be published.

    Recomputed from the record rather than trusted from the last analysis, so
    filling a gap actually clears it.
    """
    missing: list[str] = []
    if challenge.value is None:
        missing.append("budget")
    spec = challenge.structured_spec or {}
    if not spec.get("timeline"):
        missing.append("timeline")
    if not challenge.district:
        missing.append("location")
    for field_name in CLASSIFICATION_FIELDS:
        if getattr(challenge, field_name) is None:
            missing.append(field_name)
    if not spec.get("problem_statement"):
        missing.append("analysis")
    return missing


def refresh_missing_fields(challenge: Challenge) -> list[str]:
    challenge.missing_fields = missing_fields_for(challenge)
    return challenge.missing_fields


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_problem(
    payload: AnalyzeRequest,
    current_user: User = Depends(officer_or_admin),
) -> AnalyzeResponse:
    """Structure a plain-language problem. Saves nothing.

    Budget, timeline and location are echoed only when supplied. Anything absent
    comes back in missing_fields, never filled in.
    """
    outcome = analyzer.analyze(
        payload.description,
        budget=payload.budget,
        timeline=payload.timeline,
        location=payload.location,
    )
    return AnalyzeResponse(**outcome.as_dict())


# ---------------------------------------------------------------------------
# Draft and edit
# ---------------------------------------------------------------------------


@router.post("", response_model=ChallengeDetail, status_code=status.HTTP_201_CREATED)
def create_challenge(
    payload: ChallengeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Challenge:
    """Create a draft and run the analyzer over it."""
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    outcome = analyzer.analyze(
        payload.description,
        budget=payload.budget,
        timeline=payload.timeline,
        location=payload.district,
    )

    challenge = Challenge(
        title=payload.title,
        description_raw=payload.description,
        department_id=payload.department_id,
        created_by_user_id=current_user.id,
        value=payload.budget,
        criticality=payload.criticality,
        innovation_potential=payload.innovation_potential,
        district=payload.district,
        requires_onsite=payload.requires_onsite,
        category=payload.category,
        status=ChallengeStatus.ANALYZED,
        structured_spec={
            **outcome.result.model_dump(mode="json"),
            "analysis_source": outcome.source,
            "analysis_notes": outcome.notes,
        },
    )
    db.add(challenge)
    db.flush()
    refresh_missing_fields(challenge)
    knowledge.index_challenge(db, challenge)

    audit.record(
        db,
        action="CHALLENGE_ANALYZED",
        reason=(
            f"Problem structured by the {outcome.source} analyzer. "
            f"Outstanding fields: {', '.join(challenge.missing_fields) or 'none'}."
        ),
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={"source": outcome.source, "missing_fields": challenge.missing_fields},
    )
    db.commit()
    db.refresh(challenge)
    return challenge


@router.get("", response_model=list[ChallengeOut])
def list_challenges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: ChallengeStatus | None = Query(default=None, alias="status"),
) -> list[Challenge]:
    """Challenges a signed-in user may see.

    A startup sees published work and anything further along; government, expert
    and admin users see drafts too.
    """
    statement = select(Challenge).order_by(Challenge.created_at.desc())
    if current_user.role is UserRole.STARTUP:
        statement = statement.where(
            Challenge.status.in_(
                [
                    ChallengeStatus.PUBLISHED,
                    ChallengeStatus.EVALUATION,
                    ChallengeStatus.PILOT,
                    ChallengeStatus.COMPLETED,
                ]
            )
        )
    if status_filter is not None:
        statement = statement.where(Challenge.status == status_filter)
    return list(db.scalars(statement).all())


@router.get("/{challenge_id}", response_model=ChallengeDetail)
def get_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Challenge:
    challenge = _get(db, challenge_id)
    if current_user.role is UserRole.STARTUP and challenge.status in (
        ChallengeStatus.DRAFT,
        ChallengeStatus.ANALYZED,
        ChallengeStatus.APPROVED,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This challenge is not published yet"
        )
    return challenge


@router.patch("/{challenge_id}", response_model=ChallengeDetail)
def update_challenge(
    challenge_id: int,
    payload: ChallengeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Challenge:
    """Fill in what the analyzer reported missing."""
    challenge = _get(db, challenge_id)
    if challenge.status not in (ChallengeStatus.DRAFT, ChallengeStatus.ANALYZED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A challenge in status {challenge.status.value} can no longer be edited.",
        )

    data = payload.model_dump(exclude_unset=True)
    if "budget" in data:
        challenge.value = data.pop("budget")
    if "timeline" in data:
        spec = dict(challenge.structured_spec or {})
        spec["timeline"] = data.pop("timeline")
        challenge.structured_spec = spec
    for field_name, value in data.items():
        setattr(challenge, field_name, value)

    refresh_missing_fields(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Approve: this is what locks the KPIs
# ---------------------------------------------------------------------------


@router.post("/{challenge_id}/approve", response_model=ChallengeDetail)
def approve_challenge(
    challenge_id: int,
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Challenge:
    """Officer approval: record the KPIs and lock them.

    After this the KPI set is immutable. Everything the platform later judges a
    pilot against is fixed here, by a person, before anyone bids.
    """
    challenge = _get(db, challenge_id)

    if challenge.kpis_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The KPIs for this challenge are locked and cannot be approved again.",
        )

    outstanding = [
        field_name
        for field_name in missing_fields_for(challenge)
        if field_name in DEPARTMENT_ONLY_FIELDS or field_name in CLASSIFICATION_FIELDS
    ]
    if outstanding:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Fill in what the department owns before approving.",
                "missing_fields": outstanding,
            },
        )

    for kpi in payload.kpis:
        db.add(
            Kpi(
                challenge_id=challenge.id,
                name=kpi.name,
                target_value=kpi.target_value,
                unit=kpi.unit,
                measurement_method=kpi.measurement_method,
                direction=kpi.direction,
                status=KpiStatus.PENDING,
            )
        )

    challenge.kpis_locked = True
    challenge.approved_by_user_id = current_user.id
    challenge.approved_at = datetime.now(timezone.utc)
    challenge.status = ChallengeStatus.APPROVED

    spec = dict(challenge.structured_spec or {})
    spec[MISSING_KPI_TARGETS] = None
    challenge.structured_spec = spec
    refresh_missing_fields(challenge)

    audit.record(
        db,
        action="CHALLENGE_APPROVED_KPIS_LOCKED",
        reason=payload.note,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={
            "kpis": [kpi.model_dump(mode="json") for kpi in payload.kpis],
            "locked": True,
        },
    )
    db.commit()
    db.refresh(challenge)
    return challenge


@router.post("/{challenge_id}/kpis", response_model=ChallengeDetail)
def add_kpi_after_approval(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Challenge:
    """Always refuses once KPIs are locked.

    It exists so that an attempt to change a locked KPI gets a clear answer
    rather than a 404 that looks like a bug.
    """
    challenge = _get(db, challenge_id)
    if challenge.kpis_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "KPIs were locked at officer approval and cannot be added to or changed. "
                "They are what the pilot will be judged against."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="KPIs are recorded through the approval endpoint, which locks them.",
    )


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


@router.post("/{challenge_id}/publish", response_model=ChallengeDetail)
def publish_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Challenge:
    """Classify the tier, open the bid window, and publish.

    Blocked while anything is missing: an incomplete challenge is not something
    startups should be spending days bidding on.
    """
    challenge = _get(db, challenge_id)

    outstanding = missing_fields_for(challenge)
    if outstanding:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This challenge cannot be published while fields are missing.",
                "missing_fields": outstanding,
            },
        )
    if not challenge.kpis_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the challenge first: publishing requires locked KPIs.",
        )

    rules = RulesService(db)
    try:
        decision = classify(
            rules,
            value=challenge.value,
            criticality=challenge.criticality,
            innovation_potential=challenge.innovation_potential,
        )
        bid_window = rules.integer(BID_WINDOW_DAYS)
    except TierInputMissing as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(error), "missing_fields": error.missing},
        )
    except RuleNotFound as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))

    challenge.tier = decision.tier
    challenge.tier_explanation = decision.explanation
    challenge.status = ChallengeStatus.PUBLISHED
    challenge.published_at = datetime.now(timezone.utc)
    challenge.bid_closes_at = challenge.published_at + timedelta(days=bid_window)
    knowledge.index_challenge(db, challenge)

    audit.record(
        db,
        action="TIER_CLASSIFIED",
        reason=decision.explanation,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details=decision.as_details(),
    )
    audit.record(
        db,
        action="CHALLENGE_PUBLISHED",
        reason=(
            f"Published in the {decision.tier.value} tier. Bids close "
            f"{challenge.bid_closes_at.isoformat()}."
        ),
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={"tier": decision.tier.value, "bid_window_days": bid_window},
    )
    db.commit()
    db.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


@router.post("/knowledge-search", response_model=KnowledgeSearchOut)
def knowledge_search(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(officer_or_admin),
    limit: int = Query(default=3, ge=1, le=20),
) -> KnowledgeSearchOut:
    """Has anyone already piloted a solution to this? Shown at draft time."""
    result = knowledge.search(db, payload.description, limit=limit)
    return KnowledgeSearchOut(**result.as_dict())


@router.get("/{challenge_id}/similar", response_model=KnowledgeSearchOut)
def similar_pilots(
    challenge_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(officer_or_admin),
    limit: int = Query(default=3, ge=1, le=20),
) -> KnowledgeSearchOut:
    challenge = _get(db, challenge_id)
    result = knowledge.search(db, knowledge.challenge_text(challenge), limit=limit + 1)
    # A published challenge matches itself; drop it.
    result.matches[:] = [
        match for match in result.matches if match.challenge_id != challenge.id
    ][:limit]
    return KnowledgeSearchOut(**result.as_dict())
