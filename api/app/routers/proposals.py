"""Proposals: applying, ranking, expert evaluation, declining and awarding.

The rules that shape this file:

* A decline always carries a coded reason and the sub-score breakdown, and the
  declined startup can read both in its own portal.
* Experience adds to a score; it never gates one. Nobody is filtered out of the
  ranking for having no track record.
* An award is a person's decision, checked against tier access and rotation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.enums import ChallengeStatus, ProposalStatus, UserRole
from app.models import Award, Challenge, Company, Proposal, User
from app.schemas_phase5 import (
    AwardRequest,
    DeclineRequest,
    EvaluationBriefOut,
    EvaluationSubmit,
    MatchOut,
    ProposalCreate,
    ProposalOut,
    RankingOut,
    ShortlistRequest,
)
from app.services import audit, eligibility, matching, pilots
from app.services.rules import RulesService

router = APIRouter(tags=["proposals"])

officer_or_admin = require_roles(UserRole.GOVERNMENT, UserRole.ADMIN)
expert_only = require_roles(UserRole.EXPERT)
startup_only = require_roles(UserRole.STARTUP)
evaluator = require_roles(UserRole.EXPERT, UserRole.GOVERNMENT, UserRole.ADMIN)

# The criteria an expert marks by hand, alongside the computed match.
EXPERT_RUBRIC = [
    "technical_soundness",
    "feasibility_in_the_field",
    "value_for_money",
    "risk_and_mitigation",
    "team_and_delivery_capacity",
]

OPEN_FOR_BIDS = (ChallengeStatus.PUBLISHED, ChallengeStatus.EVALUATION)


def _challenge(db: Session, challenge_id: int) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


def _proposal(db: Session, proposal_id: int) -> Proposal:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return proposal


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


@router.post(
    "/challenges/{challenge_id}/proposals",
    response_model=ProposalOut,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_challenge(
    challenge_id: int,
    payload: ProposalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(startup_only),
) -> Proposal:
    """A startup bids. Eligibility is checked here, by the rules engine."""
    challenge = _challenge(db, challenge_id)
    if challenge.status not in OPEN_FOR_BIDS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This challenge is {challenge.status.value} and is not open for proposals.",
        )
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is not linked to a company.",
        )

    company = db.get(Company, current_user.company_id)
    rules = RulesService(db)
    decision = eligibility.assess(db, rules, company, challenge, actor=current_user)
    if not decision.eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "This bidder is not eligible for this challenge.",
                "assessment": decision.as_dict(),
            },
        )

    existing = db.scalar(
        select(Proposal).where(
            Proposal.challenge_id == challenge.id, Proposal.startup_id == company.id
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This company has already bid on this challenge.",
        )

    result = matching.score_company(db, challenge, company)
    proposal = Proposal(
        challenge_id=challenge.id,
        startup_id=company.id,
        summary=payload.summary,
        status=ProposalStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
        total_score=matching.decimal_score(result),
        sub_scores=matching.as_sub_scores_json(result),
    )
    db.add(proposal)
    db.flush()

    audit.record(
        db,
        action="PROPOSAL_SCORED",
        reason=result.explanation,
        actor=current_user,
        entity_type="proposal",
        entity_id=proposal.id,
        details=matching.as_sub_scores_json(result),
    )
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/challenges/{challenge_id}/proposals", response_model=list[ProposalOut])
def list_proposals(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Proposal]:
    """Officers and experts see the field; a startup sees only its own bid."""
    _challenge(db, challenge_id)
    statement = select(Proposal).where(Proposal.challenge_id == challenge_id)
    if current_user.role is UserRole.STARTUP:
        statement = statement.where(Proposal.startup_id == current_user.company_id)
    return list(db.scalars(statement.order_by(Proposal.total_score.desc())).all())


@router.get("/my/proposals", response_model=list[ProposalOut])
def my_proposals(
    db: Session = Depends(get_db),
    current_user: User = Depends(startup_only),
) -> list[Proposal]:
    """The startup's own bids, with scores and any decline reason."""
    return list(
        db.scalars(
            select(Proposal)
            .where(Proposal.startup_id == current_user.company_id)
            .order_by(Proposal.created_at.desc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


@router.get("/challenges/{challenge_id}/ranking", response_model=RankingOut)
def ranking(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(evaluator),
) -> RankingOut:
    """Rank everyone who bid. Nobody is filtered out for lack of experience."""
    challenge = _challenge(db, challenge_id)
    proposals = db.scalars(
        select(Proposal).where(
            Proposal.challenge_id == challenge.id,
            Proposal.status != ProposalStatus.WITHDRAWN,
        )
    ).all()
    companies = [db.get(Company, proposal.startup_id) for proposal in proposals]
    results = matching.rank(db, challenge, companies)

    return RankingOut(
        challenge_id=challenge.id,
        tier=challenge.tier.value if challenge.tier else None,
        matches=[MatchOut(**result.as_dict()) for result in results],
        note=(
            "Prototype-generated ranking. Every bidder who applied is ranked: a company "
            "with no past work still appears, because a KPI-tracked pilot is what proves "
            "reliability here."
        ),
    )


# ---------------------------------------------------------------------------
# Expert evaluation
# ---------------------------------------------------------------------------


@router.get("/evaluations/queue", response_model=list[ProposalOut])
def evaluation_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_only),
) -> list[Proposal]:
    """Proposals waiting for an evaluator, plus the ones this expert has claimed."""
    return list(
        db.scalars(
            select(Proposal)
            .where(
                Proposal.status.in_([ProposalStatus.SUBMITTED, ProposalStatus.UNDER_REVIEW]),
                (Proposal.claimed_by_user_id.is_(None))
                | (Proposal.claimed_by_user_id == current_user.id),
            )
            .order_by(Proposal.submitted_at)
        ).all()
    )


@router.post("/proposals/{proposal_id}/claim", response_model=ProposalOut)
def claim_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_only),
) -> Proposal:
    proposal = _proposal(db, proposal_id)
    if proposal.claimed_by_user_id not in (None, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another evaluator has already claimed this proposal.",
        )
    proposal.claimed_by_user_id = current_user.id
    proposal.claimed_at = datetime.now(timezone.utc)
    proposal.status = ProposalStatus.UNDER_REVIEW

    audit.record(
        db,
        action="PROPOSAL_CLAIMED",
        reason=f"Claimed for independent evaluation by {current_user.full_name}.",
        actor=current_user,
        entity_type="proposal",
        entity_id=proposal.id,
    )
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/proposals/{proposal_id}/evaluation-brief", response_model=EvaluationBriefOut)
def evaluation_brief(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(evaluator),
) -> EvaluationBriefOut:
    """The AI summary and the computed match, next to the rubric the expert marks."""
    proposal = _proposal(db, proposal_id)
    challenge = db.get(Challenge, proposal.challenge_id)
    company = db.get(Company, proposal.startup_id)
    result = matching.score_company(db, challenge, company)

    return EvaluationBriefOut(
        proposal_id=proposal.id,
        challenge_title=challenge.title,
        company_name=company.name,
        ai_summary=pilots.evaluation_summary(challenge, company, result.explanation),
        computed_match=MatchOut(**result.as_dict()),
        rubric=EXPERT_RUBRIC,
        note=(
            "The summary is AI-assisted and the match is prototype-generated. The rubric "
            "below is scored by you, and your marks are recorded separately."
        ),
    )


@router.post("/proposals/{proposal_id}/evaluation", response_model=ProposalOut)
def submit_evaluation(
    proposal_id: int,
    payload: EvaluationSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_only),
) -> Proposal:
    """Record the expert's own marks, kept apart from the computed sub-scores."""
    proposal = _proposal(db, proposal_id)
    if proposal.claimed_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim this proposal before scoring it.",
        )

    proposal.expert_scores = {
        "scores": [score.model_dump() for score in payload.scores],
        "evaluator_user_id": current_user.id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Manual rubric, scored by a human evaluator. Separate from the computed match."
        ),
    }
    proposal.expert_note = payload.note

    audit.record(
        db,
        action="PROPOSAL_EVALUATED",
        reason=payload.note,
        actor=current_user,
        entity_type="proposal",
        entity_id=proposal.id,
        details=proposal.expert_scores,
    )
    db.commit()
    db.refresh(proposal)
    return proposal


# ---------------------------------------------------------------------------
# Shortlist, decline, award
# ---------------------------------------------------------------------------


@router.post("/proposals/{proposal_id}/shortlist", response_model=ProposalOut)
def shortlist(
    proposal_id: int,
    payload: ShortlistRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Proposal:
    proposal = _proposal(db, proposal_id)
    proposal.status = ProposalStatus.SHORTLISTED
    audit.record(
        db,
        action="PROPOSAL_SHORTLISTED",
        reason=payload.note,
        actor=current_user,
        entity_type="proposal",
        entity_id=proposal.id,
    )
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/proposals/{proposal_id}/decline", response_model=ProposalOut)
def decline(
    proposal_id: int,
    payload: DeclineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Proposal:
    """Decline a bid.

    The reason code is required by the schema, so a decline without one is
    rejected before it reaches this function. The startup sees the code, the
    detail and its own sub-score breakdown in its portal.
    """
    proposal = _proposal(db, proposal_id)
    proposal.status = ProposalStatus.DECLINED
    proposal.decline_reason_code = payload.decline_reason_code
    proposal.decline_detail = payload.decline_detail

    audit.record(
        db,
        action="PROPOSAL_DECLINED",
        reason=f"{payload.decline_reason_code.value}: {payload.decline_detail}",
        actor=current_user,
        entity_type="proposal",
        entity_id=proposal.id,
        details={
            "decline_reason_code": payload.decline_reason_code.value,
            "sub_scores": proposal.sub_scores,
        },
    )
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/proposals/{proposal_id}/award", response_model=ProposalOut)
def award_proposal(
    proposal_id: int,
    payload: AwardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(officer_or_admin),
) -> Proposal:
    """Award the work. Checked against tier access and the rotation rule."""
    proposal = _proposal(db, proposal_id)
    challenge = db.get(Challenge, proposal.challenge_id)
    company = db.get(Company, proposal.startup_id)

    decision = eligibility.assess(db, RulesService(db), company, challenge, actor=current_user)
    if not decision.eligible:
        db.commit()  # keep the rotation or fallback audit entry
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This bidder cannot be awarded this challenge.",
                "assessment": decision.as_dict(),
            },
        )

    proposal.status = ProposalStatus.AWARDED
    db.add(
        Award(
            challenge_id=challenge.id,
            company_id=company.id,
            awarded_by_user_id=current_user.id,
            value=challenge.value,
        )
    )
    challenge.status = ChallengeStatus.PILOT

    audit.record(
        db,
        action="AWARD_RECORDED",
        reason=payload.note,
        actor=current_user,
        entity_type="challenge",
        entity_id=challenge.id,
        details={"company_id": company.id, "proposal_id": proposal.id},
    )
    db.commit()
    db.refresh(proposal)
    return proposal
