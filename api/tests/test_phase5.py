"""Phase 5 checks: matching, evaluation, pilots and partnerships."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import (
    ChallengeStatus,
    CompanyType,
    KpiDirection,
    KpiStatus,
    Level,
    PilotOutcome,
    PilotStatus,
    ProposalStatus,
    Tier,
    UserRole,
)
from app.models import Challenge, Company, Department, Kpi, Pilot, Proposal, User
from app.security import hash_password
from app.services import matching, pilots as pilot_service
from tests.conftest import auth_header, login


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def make_challenge(
    db,
    *,
    tier: Tier = Tier.SMALL,
    requires_onsite: bool = False,
    district: str = "Pune",
    category: str = "WATER",
    status: ChallengeStatus = ChallengeStatus.PUBLISHED,
) -> Challenge:
    department = db.scalars(select(Department).where(Department.code == "WSSD")).one()
    now = datetime.now(timezone.utc)
    challenge = Challenge(
        title="Detect and reduce water losses in the distribution network",
        description_raw=(
            "Treated water is lost in the distribution network before it reaches "
            "households and we cannot locate the losses."
        ),
        department_id=department.id,
        value=Decimal("4000000"),
        criticality=Level.MEDIUM,
        innovation_potential=Level.LOW,
        tier=tier,
        status=status,
        district=district,
        requires_onsite=requires_onsite,
        category=category,
        kpis_locked=True,
        approved_at=now,
        published_at=now,
        bid_closes_at=now + timedelta(days=21),
    )
    db.add(challenge)
    db.flush()
    return challenge


def add_challenge_kpis(db, challenge: Challenge) -> None:
    """Locked specification KPIs, one of each direction."""
    db.add(
        Kpi(
            challenge_id=challenge.id,
            name="Leak localisation accuracy",
            target_value=Decimal("85"),
            unit="percent",
            measurement_method="Excavation results against flagged locations",
            direction=KpiDirection.HIGHER_IS_BETTER,
        )
    )
    db.add(
        Kpi(
            challenge_id=challenge.id,
            name="Time to locate a reported burst",
            target_value=Decimal("12"),
            unit="hours",
            measurement_method="Report timestamp to field confirmation",
            direction=KpiDirection.LOWER_IS_BETTER,
        )
    )
    db.flush()


def make_startup(db, name: str, *, district: str = "Pune", employees: int = 10) -> Company:
    company = Company(
        name=name,
        type=CompanyType.STARTUP,
        district=district,
        profile_text=(
            "Acoustic leak detection and water loss analytics for municipal networks."
        ),
        dpiit_recognised=True,
        incorporation_date=date(2022, 1, 1),
        employee_count=employees,
    )
    db.add(company)
    db.flush()
    return company


def make_startup_user(db, company: Company, email: str) -> User:
    user = User(
        email=email,
        full_name=f"Founder of {company.name}",
        password_hash=hash_password("demo1234"),
        role=UserRole.STARTUP,
        company_id=company.id,
    )
    db.add(user)
    db.flush()
    return user


def seeded(db, name: str) -> Company:
    return db.scalars(select(Company).where(Company.name == name)).one()


# ---------------------------------------------------------------------------
# Matching: experience adds, never gates
# ---------------------------------------------------------------------------


def test_a_startup_with_no_past_work_still_ranks(txn_db) -> None:
    """The exit criterion, and the core promise of the platform."""
    challenge = make_challenge(txn_db)
    newcomer = make_startup(txn_db, "Phase 5 Brand New Ltd")
    veteran = seeded(txn_db, "AquaSense Analytics")

    results = matching.rank(txn_db, challenge, [newcomer, veteran])
    ranked_ids = [result.company_id for result in results]

    assert newcomer.id in ranked_ids, "a company with no history must still be ranked"
    newcomer_result = next(r for r in results if r.company_id == newcomer.id)
    assert newcomer_result.total_score > 0
    assert newcomer_result.track_record["evidence"] == matching.SELF_DECLARED

    experience = next(
        sub for sub in newcomer_result.sub_scores if sub.criterion == "relevant_experience"
    )
    assert experience.score == 0
    assert "does not exclude the bidder" in experience.reason


def test_verified_experience_outranks_self_declared_all_else_equal(txn_db) -> None:
    challenge = make_challenge(txn_db)
    veteran = seeded(txn_db, "AquaSense Analytics")
    newcomer = make_startup(txn_db, "Phase 5 Newcomer Ltd", employees=veteran.employee_count)
    newcomer.profile_text = veteran.profile_text
    newcomer.embedding = veteran.embedding
    txn_db.flush()

    results = {r.company_id: r for r in matching.rank(txn_db, challenge, [veteran, newcomer])}
    assert results[veteran.id].total_score > results[newcomer.id].total_score
    assert results[veteran.id].track_record["evidence"] == matching.VERIFIED


def test_every_sub_score_carries_a_reason(txn_db) -> None:
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    result = matching.score_company(txn_db, challenge, company)

    assert {sub.criterion for sub in result.sub_scores} == set(matching.CRITERIA_WEIGHTS)
    for sub in result.sub_scores:
        assert sub.reason.strip(), f"{sub.criterion} has no reason"
    assert "Prototype-generated" in result.as_dict()["disclaimer"]


# ---------------------------------------------------------------------------
# Proximity
# ---------------------------------------------------------------------------


def test_proximity_does_not_affect_ranking_when_onsite_is_not_required(txn_db) -> None:
    """The exit criterion."""
    challenge = make_challenge(txn_db, requires_onsite=False, district="Pune")
    local = make_startup(txn_db, "Phase 5 Local Ltd", district="Pune")
    distant = make_startup(txn_db, "Phase 5 Distant Ltd", district="Nagpur")
    distant.profile_text = local.profile_text
    txn_db.flush()

    local_result = matching.score_company(txn_db, challenge, local)
    distant_result = matching.score_company(txn_db, challenge, distant)

    assert local_result.proximity["applied"] is False
    assert distant_result.proximity["applied"] is False
    assert "no bearing on the ranking" in local_result.proximity["reason"]
    assert local_result.total_score == distant_result.total_score


def test_proximity_credits_but_never_excludes_when_onsite_is_required(txn_db) -> None:
    challenge = make_challenge(txn_db, requires_onsite=True, district="Pune")
    local = make_startup(txn_db, "Phase 5 Onsite Local Ltd", district="Pune")
    distant = make_startup(txn_db, "Phase 5 Onsite Distant Ltd", district="Nagpur")
    distant.profile_text = local.profile_text
    txn_db.flush()

    local_result = matching.score_company(txn_db, challenge, local)
    distant_result = matching.score_company(txn_db, challenge, distant)

    assert local_result.proximity["applied"] is True
    assert local_result.total_score > distant_result.total_score
    # The distant bidder is still ranked, and told why no credit applied.
    assert distant_result.total_score > 0
    assert "never excludes a bidder" in distant_result.proximity["reason"]


# ---------------------------------------------------------------------------
# KPI direction
# ---------------------------------------------------------------------------


def test_kpi_achievement_respects_direction(txn_db) -> None:
    """A bare >= comparison would get both of these backwards."""
    lower = Kpi(
        challenge_id=make_challenge(txn_db).id,
        name="Average wait time",
        target_value=Decimal("7"),
        validated_value=Decimal("6"),
        unit="minutes",
        measurement_method="Stop-level sampling",
        direction=KpiDirection.LOWER_IS_BETTER,
    )
    higher = Kpi(
        challenge_id=lower.challenge_id,
        name="Uptime",
        target_value=Decimal("95"),
        validated_value=Decimal("93"),
        unit="percent",
        measurement_method="Daily reporting",
        direction=KpiDirection.HIGHER_IS_BETTER,
    )

    assert matching.kpi_met(lower) is True, "6 minutes beats a 7 minute target"
    assert matching.kpi_met(higher) is False, "93 percent misses a 95 percent target"


def test_seeded_history_uses_direction_correctly(txn_db) -> None:
    kpi = txn_db.scalars(
        select(Kpi).where(Kpi.name == "Maintenance response time")
    ).first()
    assert kpi.direction is KpiDirection.LOWER_IS_BETTER
    # Validated 52 hours against a 48 hour target: missed, despite 52 > 48.
    assert matching.kpi_met(kpi) is False


# ---------------------------------------------------------------------------
# Applying, declining, awarding
# ---------------------------------------------------------------------------


@pytest.fixture
def officer_token(txn_client, demo_password: str) -> str:
    return login(txn_client, "officer@mahagov.in", demo_password)


@pytest.fixture
def expert_token(txn_client, demo_password: str) -> str:
    return login(txn_client, "expert@evaluator.in", demo_password)


def apply_as_seeded_startup(txn_client, txn_db, challenge: Challenge) -> dict:
    token = login(txn_client, "founder@startup.in", "demo1234")
    response = txn_client.post(
        f"/challenges/{challenge.id}/proposals",
        json={"summary": "Acoustic sensing across the pilot zone."},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_startup_can_apply_and_gets_a_scored_breakdown(txn_client, txn_db) -> None:
    challenge = make_challenge(txn_db)
    add_challenge_kpis(txn_db, challenge)
    proposal = apply_as_seeded_startup(txn_client, txn_db, challenge)

    assert proposal["total_score"] is not None
    assert len(proposal["sub_scores"]["criteria"]) == len(matching.CRITERIA_WEIGHTS)
    assert all(item["reason"] for item in proposal["sub_scores"]["criteria"])


def test_a_proposal_cannot_be_declined_without_a_reason_code(
    txn_client, txn_db, officer_token: str
) -> None:
    """The exit criterion: the schema refuses it outright."""
    challenge = make_challenge(txn_db)
    proposal = apply_as_seeded_startup(txn_client, txn_db, challenge)

    no_code = txn_client.post(
        f"/proposals/{proposal['id']}/decline",
        json={"decline_detail": "Not selected."},
        headers=auth_header(officer_token),
    )
    assert no_code.status_code == 422

    bad_code = txn_client.post(
        f"/proposals/{proposal['id']}/decline",
        json={"decline_reason_code": "BECAUSE_I_SAID_SO", "decline_detail": "No."},
        headers=auth_header(officer_token),
    )
    assert bad_code.status_code == 422

    no_detail = txn_client.post(
        f"/proposals/{proposal['id']}/decline",
        json={"decline_reason_code": "CAPABILITY_MISMATCH"},
        headers=auth_header(officer_token),
    )
    assert no_detail.status_code == 422


def test_a_declined_startup_sees_the_code_and_its_own_breakdown(
    txn_client, txn_db, officer_token: str, demo_password: str
) -> None:
    challenge = make_challenge(txn_db)
    proposal = apply_as_seeded_startup(txn_client, txn_db, challenge)

    declined = txn_client.post(
        f"/proposals/{proposal['id']}/decline",
        json={
            "decline_reason_code": "STRONGER_ALTERNATIVE_SELECTED",
            "decline_detail": "Another bid scored higher on deployment readiness.",
        },
        headers=auth_header(officer_token),
    )
    assert declined.status_code == 200, declined.text

    startup = login(txn_client, "founder@startup.in", demo_password)
    mine = txn_client.get("/my/proposals", headers=auth_header(startup)).json()
    row = next(item for item in mine if item["id"] == proposal["id"])

    assert row["decline_reason_code"] == "STRONGER_ALTERNATIVE_SELECTED"
    assert "deployment readiness" in row["decline_detail"]
    assert row["sub_scores"]["criteria"]


def test_a_startup_cannot_see_another_startups_proposal(
    txn_client, txn_db, demo_password: str
) -> None:
    challenge = make_challenge(txn_db)
    apply_as_seeded_startup(txn_client, txn_db, challenge)

    other = make_startup(txn_db, "Phase 5 Other Ltd")
    make_startup_user(txn_db, other, "other@phase5.test")
    token = login(txn_client, "other@phase5.test", "demo1234")

    visible = txn_client.get(
        f"/challenges/{challenge.id}/proposals", headers=auth_header(token)
    ).json()
    assert visible == []


# ---------------------------------------------------------------------------
# Expert evaluation
# ---------------------------------------------------------------------------


def test_an_expert_claims_from_the_queue_and_scores_by_hand(
    txn_client, txn_db, expert_token: str
) -> None:
    challenge = make_challenge(txn_db)
    proposal = apply_as_seeded_startup(txn_client, txn_db, challenge)

    queue = txn_client.get("/evaluations/queue", headers=auth_header(expert_token)).json()
    assert any(item["id"] == proposal["id"] for item in queue)

    claimed = txn_client.post(
        f"/proposals/{proposal['id']}/claim", headers=auth_header(expert_token)
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == ProposalStatus.UNDER_REVIEW.value

    brief = txn_client.get(
        f"/proposals/{proposal['id']}/evaluation-brief", headers=auth_header(expert_token)
    ).json()
    assert brief["ai_summary"]["summary"]
    assert brief["computed_match"]["sub_scores"]
    assert brief["rubric"]

    scored = txn_client.post(
        f"/proposals/{proposal['id']}/evaluation",
        json={
            "scores": [
                {"criterion": "technical_soundness", "score": 78, "reason": "Sound approach."},
                {"criterion": "feasibility_in_the_field", "score": 65, "reason": "Needs staff."},
            ],
            "note": "Recommend shortlisting with conditions.",
        },
        headers=auth_header(expert_token),
    )
    assert scored.status_code == 200, scored.text
    body = scored.json()
    assert len(body["expert_scores"]["scores"]) == 2
    # The expert's marks stay separate from the computed match.
    assert body["sub_scores"]["criteria"]


def test_an_expert_must_claim_before_scoring(txn_client, txn_db, expert_token: str) -> None:
    challenge = make_challenge(txn_db)
    proposal = apply_as_seeded_startup(txn_client, txn_db, challenge)
    response = txn_client.post(
        f"/proposals/{proposal['id']}/evaluation",
        json={
            "scores": [{"criterion": "technical_soundness", "score": 50, "reason": "x"}],
            "note": "n",
        },
        headers=auth_header(expert_token),
    )
    assert response.status_code == 409


def test_the_evaluation_queue_is_closed_to_startups(
    txn_client, demo_password: str
) -> None:
    token = login(txn_client, "founder@startup.in", demo_password)
    assert txn_client.get("/evaluations/queue", headers=auth_header(token)).status_code == 403


# ---------------------------------------------------------------------------
# Pilots: evidence and independent validation
# ---------------------------------------------------------------------------


def running_pilot(txn_db, challenge: Challenge, company: Company) -> Pilot:
    pilot = Pilot(
        challenge_id=challenge.id,
        startup_id=company.id,
        plan={"note": "test pilot"},
        milestones=[{"name": "Closure"}],
        status=PilotStatus.RUNNING,
        started_on=date(2026, 1, 1),
        planned_end_on=date(2026, 6, 1),
    )
    txn_db.add(pilot)
    txn_db.flush()
    return pilot


def supplier_kpis(txn_db, challenge: Challenge, company: Company) -> list[Kpi]:
    rows = [
        Kpi(
            challenge_id=challenge.id,
            startup_id=company.id,
            name="Leak localisation accuracy",
            target_value=Decimal("85"),
            unit="percent",
            measurement_method="Excavation results",
            direction=KpiDirection.HIGHER_IS_BETTER,
        ),
        Kpi(
            challenge_id=challenge.id,
            startup_id=company.id,
            name="Time to locate a reported burst",
            target_value=Decimal("12"),
            unit="hours",
            measurement_method="Report to confirmation",
            direction=KpiDirection.LOWER_IS_BETTER,
        ),
    ]
    for row in rows:
        txn_db.add(row)
    txn_db.flush()
    return rows


def test_the_submitting_company_cannot_validate_its_own_kpi(
    txn_client, txn_db, demo_password: str
) -> None:
    """The exit criterion, and the basis on which a pilot replaces turnover proof."""
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    running_pilot(txn_db, challenge, company)
    kpi = supplier_kpis(txn_db, challenge, company)[0]

    startup = login(txn_client, "founder@startup.in", demo_password)
    submitted = txn_client.post(
        f"/kpis/{kpi.id}/evidence",
        json={"claimed_value": "91", "evidence": "Excavation log for 34 flagged sites."},
        headers=auth_header(startup),
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == KpiStatus.UNDER_REVIEW.value

    # The same account now tries to validate its own claim.
    refused = txn_client.post(
        f"/kpis/{kpi.id}/validate",
        json={"validated_value": "91", "validation_note": "Looks right to us."},
        headers=auth_header(startup),
    )
    assert refused.status_code == 403

    txn_db.refresh(kpi)
    assert kpi.validated_value is None
    assert kpi.validated_by is None
    assert kpi.status is KpiStatus.UNDER_REVIEW


def test_a_government_user_at_the_supplier_company_is_also_refused(
    txn_client, txn_db
) -> None:
    """The check is on the company, not on the role."""
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    kpi = supplier_kpis(txn_db, challenge, company)[0]
    kpi.claimed_value = Decimal("91")
    kpi.status = KpiStatus.UNDER_REVIEW

    insider = User(
        email="insider@phase5.test",
        full_name="Insider with an officer role",
        password_hash=hash_password("demo1234"),
        role=UserRole.GOVERNMENT,
        company_id=company.id,
    )
    txn_db.add(insider)
    txn_db.flush()

    token = login(txn_client, "insider@phase5.test", "demo1234")
    response = txn_client.post(
        f"/kpis/{kpi.id}/validate",
        json={"validated_value": "91", "validation_note": "Fine."},
        headers=auth_header(token),
    )
    assert response.status_code == 403


def test_an_independent_evaluator_can_validate(
    txn_client, txn_db, expert_token: str
) -> None:
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    kpi = supplier_kpis(txn_db, challenge, company)[0]
    kpi.claimed_value = Decimal("91")
    kpi.status = KpiStatus.UNDER_REVIEW
    txn_db.flush()

    response = txn_client.post(
        f"/kpis/{kpi.id}/validate",
        json={
            "validated_value": "88",
            "validation_note": "Verified 88 percent against excavation records.",
        },
        headers=auth_header(expert_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["validated_value"] == "88.00"
    assert body["claimed_value"] == "91.00"
    assert body["validated_by"] is not None
    assert body["status"] == KpiStatus.VERIFIED.value


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def validated_pilot(txn_db, *, accuracy: Decimal, hours: Decimal, late: bool = False) -> Pilot:
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    pilot = running_pilot(txn_db, challenge, company)
    pilot.completed_on = date(2026, 7, 1) if late else date(2026, 5, 20)

    accuracy_kpi, hours_kpi = supplier_kpis(txn_db, challenge, company)
    for kpi, value in ((accuracy_kpi, accuracy), (hours_kpi, hours)):
        kpi.claimed_value = value
        kpi.validated_value = value
        kpi.status = KpiStatus.VERIFIED
    txn_db.flush()
    return pilot


def test_the_recommendation_is_deterministic(txn_db) -> None:
    """The exit criterion: same inputs, same answer, every time."""
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))
    runs = [pilot_service.recommend(txn_db, pilot).as_dict() for _ in range(5)]
    assert all(run == runs[0] for run in runs)


def test_all_targets_met_on_schedule_recommends_scale(txn_db) -> None:
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))
    result = pilot_service.recommend(txn_db, pilot)
    assert result.outcome is PilotOutcome.SCALE
    assert result.kpis_met == 2


def test_a_missed_target_recommends_modify(txn_db) -> None:
    pilot = validated_pilot(txn_db, accuracy=Decimal("70"), hours=Decimal("10"))
    result = pilot_service.recommend(txn_db, pilot)
    assert result.outcome is PilotOutcome.MODIFY
    assert result.kpis_met == 1


def test_no_target_met_recommends_reject(txn_db) -> None:
    pilot = validated_pilot(txn_db, accuracy=Decimal("70"), hours=Decimal("30"))
    result = pilot_service.recommend(txn_db, pilot)
    assert result.outcome is PilotOutcome.REJECT
    assert result.kpis_met == 0


def test_meeting_every_target_late_recommends_modify(txn_db) -> None:
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"), late=True)
    result = pilot_service.recommend(txn_db, pilot)
    assert result.outcome is PilotOutcome.MODIFY
    assert result.on_schedule is False


def test_unknown_schedule_is_not_reported_as_late(txn_db) -> None:
    """Unknown and late are different things, and the reasoning must not confuse them."""
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    pilot = running_pilot(txn_db, challenge, company)
    pilot.completed_on = None  # the officer has not recorded a completion date

    for kpi, value in zip(supplier_kpis(txn_db, challenge, company), [Decimal("88"), Decimal("10")]):
        kpi.claimed_value = value
        kpi.validated_value = value
        kpi.status = KpiStatus.VERIFIED
    txn_db.flush()

    result = pilot_service.recommend(txn_db, pilot)
    assert result.on_schedule is None
    assert result.outcome is PilotOutcome.MODIFY
    joined = " ".join(result.reasoning)
    assert "could not be confirmed" in joined
    assert "did not finish on schedule" not in joined


def test_the_recommendation_uses_direction_not_a_bare_comparison(txn_db) -> None:
    """10 hours against a 12 hour target is a success, even though 10 < 12."""
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))
    result = pilot_service.recommend(txn_db, pilot)
    hours = next(item for item in result.kpi_detail if "burst" in item["name"])
    assert hours["direction"] == "LOWER_IS_BETTER"
    assert hours["met"] is True


def test_a_recommendation_needs_every_kpi_validated(txn_db) -> None:
    challenge = make_challenge(txn_db)
    company = seeded(txn_db, "AquaSense Analytics")
    pilot = running_pilot(txn_db, challenge, company)
    supplier_kpis(txn_db, challenge, company)

    with pytest.raises(pilot_service.RecommendationNotReady):
        pilot_service.recommend(txn_db, pilot)


# ---------------------------------------------------------------------------
# A recommendation has no effect until an officer decides
# ---------------------------------------------------------------------------


def test_the_recommendation_changes_nothing_until_an_officer_decides(
    txn_client, txn_db, officer_token: str, expert_token: str
) -> None:
    """The exit criterion: nothing is auto-awarded and nothing auto-closes."""
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))

    computed = txn_client.get(
        f"/pilots/{pilot.id}/recommendation", headers=auth_header(expert_token)
    )
    assert computed.status_code == 200, computed.text
    assert computed.json()["recommended_outcome"] == PilotOutcome.SCALE.value
    assert "no effect until an officer records a decision" in computed.json()["status"]

    txn_db.refresh(pilot)
    assert pilot.outcome is None, "reading a recommendation must not set an outcome"

    stored = txn_client.post(
        f"/pilots/{pilot.id}/recommendation", headers=auth_header(expert_token)
    )
    assert stored.status_code == 200
    txn_db.refresh(pilot)
    assert pilot.recommended_outcome is PilotOutcome.SCALE
    assert pilot.outcome is None, "storing a recommendation must not set an outcome"
    assert pilot.outcome_decided_by is None

    decided = txn_client.post(
        f"/pilots/{pilot.id}/decision",
        json={
            "outcome": "SCALE",
            "note": "Accepted at the review meeting.",
            "lessons_learned": "Baseline collection needs two weeks.",
        },
        headers=auth_header(officer_token),
    )
    assert decided.status_code == 200, decided.text
    txn_db.refresh(pilot)
    assert pilot.outcome is PilotOutcome.SCALE
    assert pilot.outcome_decided_by is not None
    assert pilot.outcome_decided_at is not None


def test_an_officer_can_decide_against_the_recommendation_and_it_is_audited(
    txn_client, txn_db, officer_token: str, expert_token: str
) -> None:
    from app.models import AuditLog

    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))
    txn_client.post(f"/pilots/{pilot.id}/recommendation", headers=auth_header(expert_token))

    response = txn_client.post(
        f"/pilots/{pilot.id}/decision",
        json={"outcome": "MODIFY", "note": "Scaling deferred pending a budget decision."},
        headers=auth_header(officer_token),
    )
    assert response.status_code == 200

    entry = txn_db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "pilot", AuditLog.entity_id == pilot.id)
        .order_by(AuditLog.id.desc())
    ).first()
    assert entry.action == "PILOT_OUTCOME_OVERRIDDEN"
    assert entry.details["recommended_outcome"] == "SCALE"
    assert entry.details["decided_outcome"] == "MODIFY"
    assert entry.details["overrode_recommendation"] is True


def test_a_startup_cannot_record_the_decision(
    txn_client, txn_db, demo_password: str
) -> None:
    pilot = validated_pilot(txn_db, accuracy=Decimal("88"), hours=Decimal("10"))
    token = login(txn_client, "founder@startup.in", demo_password)
    response = txn_client.post(
        f"/pilots/{pilot.id}/decision",
        json={"outcome": "SCALE", "note": "We think it went well."},
        headers=auth_header(token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def test_milestones_are_drafted_from_the_approved_kpis(txn_db) -> None:
    challenge = make_challenge(txn_db)
    add_challenge_kpis(txn_db, challenge)
    kpis = txn_db.scalars(
        select(Kpi).where(Kpi.challenge_id == challenge.id, Kpi.startup_id.is_(None))
    ).all()

    draft = pilot_service.draft_milestones(list(kpis))
    assert draft.source == "template"
    text = " ".join(str(milestone) for milestone in draft.milestones)
    for kpi in kpis:
        assert kpi.name in text
    # No invented dates, budgets or payment amounts.
    assert "date" not in text.lower() or "baseline" in text.lower()


def test_milestone_drafting_requires_locked_kpis(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = make_challenge(txn_db)
    challenge.kpis_locked = False
    txn_db.flush()
    response = txn_client.get(
        f"/challenges/{challenge.id}/milestone-draft", headers=auth_header(officer_token)
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Partnerships
# ---------------------------------------------------------------------------


def test_a_partnership_needs_validated_kpis_and_the_large_tier(
    txn_client, txn_db, officer_token: str
) -> None:
    small = make_challenge(txn_db, tier=Tier.SMALL)
    company = seeded(txn_db, "AquaSense Analytics")
    partner = seeded(txn_db, "Deshmukh Infra Ltd")

    refused = txn_client.post(
        f"/challenges/{small.id}/partnership",
        json={
            "startup_id": company.id,
            "legacy_partner_id": partner.id,
            "startup_scope": "Owns the solution and its IP.",
            "execution_scope": "Civil works.",
            "note": "Should not apply on SMALL.",
        },
        headers=auth_header(officer_token),
    )
    assert refused.status_code == 409
    assert "LARGE tier" in refused.json()["detail"]


def test_a_large_tier_partnership_shows_both_sides(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = make_challenge(txn_db, tier=Tier.LARGE)
    company = seeded(txn_db, "AquaSense Analytics")
    partner = seeded(txn_db, "Deshmukh Infra Ltd")
    running_pilot(txn_db, challenge, company)

    kpi = supplier_kpis(txn_db, challenge, company)[0]
    kpi.claimed_value = Decimal("88")
    kpi.validated_value = Decimal("88")
    kpi.status = KpiStatus.VERIFIED
    txn_db.flush()

    created = txn_client.post(
        f"/challenges/{challenge.id}/partnership",
        json={
            "startup_id": company.id,
            "legacy_partner_id": partner.id,
            "startup_scope": "Owns the solution, the algorithms and the IP.",
            "execution_scope": "Trenching, installation and site restoration.",
            "note": "Execution partner assigned after KPI validation.",
        },
        headers=auth_header(officer_token),
    )
    assert created.status_code == 200, created.text

    view = txn_client.get(
        f"/partnerships/{created.json()['id']}", headers=auth_header(officer_token)
    ).json()
    assert view["solution_owner"]["company"] == "AquaSense Analytics"
    assert view["execution_partner"]["company"] == "Deshmukh Infra Ltd"
    assert "owns the solution and its intellectual property" in view["ip_note"]
    assert "no payment integration" in view["payment_note"]
    assert view["partnership"]["milestone_status"][0]["payment_to"] == "startup"


def test_an_unrelated_company_cannot_open_a_partnership(
    txn_client, txn_db, officer_token: str
) -> None:
    """A partnership is visible to its two parties and to the department. Nobody else."""
    challenge = make_challenge(txn_db, tier=Tier.LARGE)
    company = seeded(txn_db, "AquaSense Analytics")
    partner = seeded(txn_db, "Deshmukh Infra Ltd")
    running_pilot(txn_db, challenge, company)
    kpi = supplier_kpis(txn_db, challenge, company)[0]
    kpi.claimed_value = Decimal("88")
    kpi.validated_value = Decimal("88")
    kpi.status = KpiStatus.VERIFIED
    txn_db.flush()

    created = txn_client.post(
        f"/challenges/{challenge.id}/partnership",
        json={
            "startup_id": company.id,
            "legacy_partner_id": partner.id,
            "startup_scope": "Owns the solution and its IP.",
            "execution_scope": "Trenching and installation.",
            "note": "Assigned after validation.",
        },
        headers=auth_header(officer_token),
    )
    partnership_id = created.json()["id"]

    # The solution owner can see it.
    owner = login(txn_client, "founder@startup.in", "demo1234")
    assert (
        txn_client.get(f"/partnerships/{partnership_id}", headers=auth_header(owner)).status_code
        == 200
    )

    # An unrelated startup cannot.
    outsider_company = make_startup(txn_db, "Phase 5 Unrelated Ltd")
    make_startup_user(txn_db, outsider_company, "unrelated@phase5.test")
    outsider = login(txn_client, "unrelated@phase5.test", "demo1234")
    assert (
        txn_client.get(
            f"/partnerships/{partnership_id}", headers=auth_header(outsider)
        ).status_code
        == 403
    )
    assert (
        txn_client.get(
            f"/challenges/{challenge.id}/partnerships", headers=auth_header(outsider)
        ).json()
        == []
    )
