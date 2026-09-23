"""Pilots: plan, run, evidence, validation, recommendation, decision.

The two rules this file exists to enforce:

* A startup never validates its own KPI. The validation endpoint checks who is
  asking and refuses the submitting company outright.
* A recommendation changes nothing. The pilot outcome stays empty until an
  officer records a decision, and the decision is what is acted on.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.enums import ChallengeStatus, KpiStatus, PilotStatus, Tier, UserRole
from app.models import Challenge, Company, Kpi, Partnership, Pilot, User
from app.schemas_challenge import KpiOut
from app.schemas_phase5 import (
    KpiEvidenceIn,
    KpiValidationIn,
    MilestoneDraftOut,
    OutcomeDecisionIn,
    PartnershipCreate,
    PartnershipOut,
    PartnershipView,
    PilotOut,
    PilotPlanRequest,
    RecommendationOut,
)
from app.services import audit, pilots as pilot_service

router = APIRouter(tags=["pilots"])

officer_or_admin = require_roles(UserRole.GOVERNMENT, UserRole.ADMIN)
startup_only = require_roles(UserRole.STARTUP)
validator_roles = require_roles(UserRole.EXPERT, UserRole.GOVERNMENT, UserRole.ADMIN)


def _challenge(db: Session, challenge_id: int) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


def _pilot(db: Session, pilot_id: int) -> Pilot:
    pilot = db.get(Pilot, pilot_id)
    if pilot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pilot not found")
    return pilot


def _kpi(db: Session, kpi_id: int) -> Kpi:
    kpi = db.get(Kpi, kpi_id)
    if kpi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
    return kpi


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


@router.get("/challenges/{challenge_id}/milestone-draft", response_model=MilestoneDraftOut)
def milestone_draft(
    challenge_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(officer_or_admin),
) -> MilestoneDraftOut:
    """Draft milestones from the approved KPIs, for the officer to edit."""
    challenge = _challenge(db, challenge_id)
    if not challenge.kpis_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the challenge first: milestones are drafted from locked KPIs.",
        )
    kpis = db.scalars(
        select(Kpi).where(Kpi.challenge_id == challenge.id, Kpi.startup_id.is_(None))
    ).all()
    return MilestoneDraftOut(**pilot_service.draft_milestones(list(kpis)).as_dict())


@router.post("/challenges/{challenge_id}/pilot", response_model=PilotOut)
def start_pilot(
    challenge_id: int,
    payload: PilotPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Pilot:
    """Officer approves the plan and the pilot starts.

    The approved KPIs are copied onto the supplier here: the challenge-level KPI
    stays as the locked specification, and the copy is what the supplier reports
    against.
    """
    challenge = _challenge(db, challenge_id)
    award = next(
        (
            proposal
            for proposal in challenge.proposals
            if proposal.status.value == "AWARDED"
        ),
        None,
    )
    if award is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Award the challenge before starting a pilot.",
        )
    if db.scalar(select(Pilot).where(Pilot.challenge_id == challenge.id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This challenge already has a pilot."
        )

    pilot = Pilot(
        challenge_id=challenge.id,
        startup_id=award.startup_id,
        plan={"approved_by": current_user.id, "note": payload.note},
        milestones=payload.milestones,
        status=PilotStatus.RUNNING,
        cost=payload.cost,
        started_on=payload.started_on,
        planned_end_on=payload.planned_end_on,
    )
    db.add(pilot)

    for kpi in db.scalars(
        select(Kpi).where(Kpi.challenge_id == challenge.id, Kpi.startup_id.is_(None))
    ).all():
        db.add(
            Kpi(
                challenge_id=challenge.id,
                startup_id=award.startup_id,
                name=kpi.name,
                target_value=kpi.target_value,
                unit=kpi.unit,
                measurement_method=kpi.measurement_method,
                direction=kpi.direction,
                status=KpiStatus.PENDING,
            )
        )

    audit.record(
        db,
        action="PILOT_PLAN_APPROVED",
        reason=payload.note,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={"milestones": payload.milestones},
    )
    db.commit()
    db.refresh(pilot)
    return pilot


@router.get("/pilots/{pilot_id}", response_model=PilotOut)
def get_pilot(
    pilot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Pilot:
    return _pilot(db, pilot_id)


@router.get("/challenges/{challenge_id}/kpis", response_model=list[KpiOut])
def challenge_kpis(
    challenge_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Kpi]:
    _challenge(db, challenge_id)
    return list(db.scalars(select(Kpi).where(Kpi.challenge_id == challenge_id)).all())


# ---------------------------------------------------------------------------
# Evidence and validation
# ---------------------------------------------------------------------------


@router.post("/kpis/{kpi_id}/evidence", response_model=KpiOut)
def submit_evidence(
    kpi_id: int,
    payload: KpiEvidenceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(startup_only),
) -> Kpi:
    """The supplier reports what it achieved. This is a claim, not a result."""
    kpi = _kpi(db, kpi_id)
    if kpi.startup_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This KPI belongs to another supplier.",
        )
    if kpi.status is KpiStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This KPI has already been validated and cannot be changed.",
        )

    kpi.claimed_value = payload.claimed_value
    kpi.evidence = payload.evidence
    kpi.claimed_by_user_id = current_user.id
    kpi.claimed_at = datetime.now(timezone.utc)
    kpi.status = KpiStatus.UNDER_REVIEW

    audit.record(
        db,
        action="KPI_EVIDENCE_SUBMITTED",
        reason=f"{kpi.name}: supplier claims {payload.claimed_value} {kpi.unit or ''}".strip(),
        actor=current_user,
        entity_type="kpi",
        entity_id=kpi.id,
        details={"claimed_value": str(payload.claimed_value)},
    )
    db.commit()
    db.refresh(kpi)
    return kpi


@router.post("/kpis/{kpi_id}/validate", response_model=KpiOut)
def validate_kpi(
    kpi_id: int,
    payload: KpiValidationIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(validator_roles),
) -> Kpi:
    """Independent validation.

    The submitting company can never do this, whatever role its account holds.
    That separation is the whole basis on which a pilot replaces a turnover
    requirement, so it is enforced here rather than assumed.
    """
    kpi = _kpi(db, kpi_id)

    if current_user.company_id is not None and current_user.company_id == kpi.startup_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "A company cannot validate its own KPI. Validation is done by an "
                "evaluator or officer independent of the supplier."
            ),
        )
    if kpi.claimed_value is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no claim to validate yet.",
        )

    kpi.validated_value = payload.validated_value
    kpi.validated_by = current_user.id
    kpi.validated_at = datetime.now(timezone.utc)
    kpi.validation_note = payload.validation_note
    kpi.status = KpiStatus.VERIFIED if payload.accepted else KpiStatus.REJECTED

    audit.record(
        db,
        action="KPI_VALIDATED",
        reason=payload.validation_note,
        actor=current_user,
        entity_type="kpi",
        entity_id=kpi.id,
        details={
            "claimed_value": str(kpi.claimed_value),
            "validated_value": str(payload.validated_value),
            "direction": kpi.direction.value,
            "status": kpi.status.value,
        },
    )
    db.commit()
    db.refresh(kpi)
    return kpi


# ---------------------------------------------------------------------------
# Recommendation and decision
# ---------------------------------------------------------------------------


@router.get("/pilots/{pilot_id}/recommendation", response_model=RecommendationOut)
def recommendation(
    pilot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(validator_roles),
) -> RecommendationOut:
    """Compute Scale, Modify or Reject. Changes nothing."""
    pilot = _pilot(db, pilot_id)
    try:
        result = pilot_service.recommend(db, pilot)
    except pilot_service.RecommendationNotReady as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return RecommendationOut(**result.as_dict())


@router.post("/pilots/{pilot_id}/recommendation", response_model=PilotOut)
def store_recommendation(
    pilot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(validator_roles),
) -> Pilot:
    """Record the recommendation against the pilot, still without deciding anything.

    recommended_outcome and outcome are separate columns on purpose: the first is
    what the platform computed, the second is what a person decided.
    """
    pilot = _pilot(db, pilot_id)
    try:
        result = pilot_service.recommend(db, pilot)
    except pilot_service.RecommendationNotReady as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))

    pilot.recommended_outcome = result.outcome
    pilot.recommendation_reasoning = result.as_dict()
    pilot.status = PilotStatus.VALIDATED

    audit.record(
        db,
        action="PILOT_RECOMMENDATION_COMPUTED",
        reason=" ".join(result.reasoning),
        actor=current_user,
        entity_type="pilot",
        entity_id=pilot.id,
        details=result.as_dict(),
    )
    db.commit()
    db.refresh(pilot)
    return pilot


@router.post("/pilots/{pilot_id}/decision", response_model=PilotOut)
def record_decision(
    pilot_id: int,
    payload: OutcomeDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Pilot:
    """The officer decides. Only this makes an outcome effective."""
    pilot = _pilot(db, pilot_id)

    overrides = (
        pilot.recommended_outcome is not None and pilot.recommended_outcome is not payload.outcome
    )
    pilot.outcome = payload.outcome
    pilot.outcome_decided_by = current_user.id
    pilot.outcome_decided_at = datetime.now(timezone.utc)
    pilot.outcome_note = payload.note
    pilot.status = PilotStatus.CLOSED
    if payload.lessons_learned:
        pilot.lessons_learned = payload.lessons_learned
    if payload.completed_on:
        pilot.completed_on = payload.completed_on

    challenge = db.get(Challenge, pilot.challenge_id)
    challenge.status = ChallengeStatus.COMPLETED

    audit.record(
        db,
        action="PILOT_OUTCOME_OVERRIDDEN" if overrides else "PILOT_OUTCOME_DECIDED",
        reason=payload.note,
        actor=current_user,
        entity_type="pilot",
        entity_id=pilot.id,
        details={
            "recommended_outcome": (
                pilot.recommended_outcome.value if pilot.recommended_outcome else None
            ),
            "decided_outcome": payload.outcome.value,
            "overrode_recommendation": overrides,
        },
    )
    db.commit()
    db.refresh(pilot)
    return pilot


# ---------------------------------------------------------------------------
# Partnerships (LARGE tier)
# ---------------------------------------------------------------------------


@router.post("/challenges/{challenge_id}/partnership", response_model=PartnershipOut)
def create_partnership(
    challenge_id: int,
    payload: PartnershipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Partnership:
    """Assign an execution partner on a LARGE challenge.

    Only after the startup's KPIs have validated, and only on LARGE: the startup
    owns the solution and its IP, and the prime contractor executes within an
    assigned scope.
    """
    challenge = _challenge(db, challenge_id)
    if challenge.tier is not Tier.LARGE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Execution partnerships apply to the LARGE tier. This challenge is "
                f"{challenge.tier.value if challenge.tier else 'unclassified'}."
            ),
        )

    validated = db.scalars(
        select(Kpi).where(
            Kpi.challenge_id == challenge.id,
            Kpi.startup_id == payload.startup_id,
            Kpi.status == KpiStatus.VERIFIED,
        )
    ).all()
    if not validated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Assign an execution partner only after the startup has validated KPIs "
                "on this challenge."
            ),
        )

    partnership = Partnership(
        challenge_id=challenge.id,
        startup_id=payload.startup_id,
        legacy_partner_id=payload.legacy_partner_id,
        startup_scope=payload.startup_scope,
        execution_scope=payload.execution_scope,
        milestone_status=[
            {
                "milestone": milestone.get("name", "milestone"),
                "status": "PENDING",
                "payment_to": "startup",
            }
            for milestone in (
                db.scalar(select(Pilot).where(Pilot.challenge_id == challenge.id)).milestones
                or []
            )
        ],
    )
    db.add(partnership)

    audit.record(
        db,
        action="PARTNERSHIP_CREATED",
        reason=payload.note,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={
            "startup_id": payload.startup_id,
            "legacy_partner_id": payload.legacy_partner_id,
        },
    )
    db.commit()
    db.refresh(partnership)
    return partnership


def _may_view_partnership(user: User, partnership: Partnership) -> bool:
    """Officers and admins see any partnership; a company sees only its own."""
    if user.role in (UserRole.GOVERNMENT, UserRole.ADMIN):
        return True
    return user.company_id in (partnership.startup_id, partnership.legacy_partner_id)


@router.get("/partnerships/{partnership_id}", response_model=PartnershipView)
def partnership_view(
    partnership_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartnershipView:
    """Solution Owner and Execution Partner, side by side."""
    partnership = db.get(Partnership, partnership_id)
    if partnership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Partnership not found"
        )
    if not _may_view_partnership(current_user, partnership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This partnership belongs to another company.",
        )

    startup = db.get(Company, partnership.startup_id)
    partner = db.get(Company, partnership.legacy_partner_id)

    return PartnershipView(
        partnership=PartnershipOut.model_validate(partnership),
        solution_owner={
            "role": "Solution Owner",
            "company": startup.name,
            "district": startup.district,
            "scope": partnership.startup_scope,
        },
        execution_partner={
            "role": "Execution Partner",
            "company": partner.name,
            "district": partner.district,
            "scope": partnership.execution_scope,
        },
        ip_note=(
            "The startup owns the solution and its intellectual property. The execution "
            "partner delivers within the assigned scope and acquires no rights to it."
        ),
        payment_note=(
            "Milestone payments are shown as flowing directly to the solution owner. "
            "Display only: this prototype has no payment integration."
        ),
    )


@router.get("/challenges/{challenge_id}/partnerships", response_model=list[PartnershipOut])
def list_partnerships(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Partnership]:
    """Partnerships on a challenge, filtered to what the caller may see."""
    rows = db.scalars(
        select(Partnership).where(Partnership.challenge_id == challenge_id)
    ).all()
    return [row for row in rows if _may_view_partnership(current_user, row)]
