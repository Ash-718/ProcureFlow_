"""Phase 2 checks: the rules service, the tier engine and two-gate eligibility."""

from __future__ import annotations

import ast
import pathlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import CompanyType, Level, ProposalStatus, Tier
from app.models import (
    AuditLog,
    Challenge,
    Company,
    Department,
    ProcurementRule,
    Proposal,
)
from app.services import barriers, eligibility, fallback
from app.services.rules import RuleNotFound, RulesService
from app.services.tiering import TierInputMissing, classify
from tests.conftest import auth_header, login

ONE = Decimal("1")


@pytest.fixture
def rules(txn_db) -> RulesService:
    return RulesService(txn_db)


def tier_for(
    rules: RulesService,
    value: Decimal,
    criticality: Level = Level.LOW,
    innovation: Level = Level.LOW,
) -> Tier:
    return classify(
        rules, value=value, criticality=criticality, innovation_potential=innovation
    ).tier


# ---------------------------------------------------------------------------
# The rules service
# ---------------------------------------------------------------------------


def test_rules_service_reads_the_table(rules: RulesService) -> None:
    small = rules.get("SMALL_TENDER_LIMIT")
    assert small.value == Decimal("5000000.00")
    assert small.is_prototype_setting is True
    assert "prototype setting" in small.cite()


def test_a_missing_rule_raises_rather_than_defaulting(rules: RulesService) -> None:
    with pytest.raises(RuleNotFound) as error:
        rules.get("NO_SUCH_RULE")
    assert "never fall back to a built-in default" in str(error.value)


def test_the_service_remembers_what_it_read(rules: RulesService) -> None:
    rules.get("MIN_TECH_SCORE")
    rules.get("BID_WINDOW_DAYS")
    assert [rule.rule_name for rule in rules.rules_read] == [
        "BID_WINDOW_DAYS",
        "MIN_TECH_SCORE",
    ]


def test_an_inactive_rule_is_invisible_to_the_engine(txn_db, rules: RulesService) -> None:
    rule = txn_db.scalars(
        select(ProcurementRule).where(ProcurementRule.rule_name == "MIN_TECH_SCORE")
    ).first()
    rule.active = False
    txn_db.flush()
    with pytest.raises(RuleNotFound):
        RulesService(txn_db).get("MIN_TECH_SCORE")


# ---------------------------------------------------------------------------
# Tier boundaries
# ---------------------------------------------------------------------------


def test_value_at_the_small_limit_is_small(rules: RulesService) -> None:
    limit = rules.decimal("SMALL_TENDER_LIMIT")
    assert tier_for(rules, limit) is Tier.SMALL


def test_value_just_above_the_small_limit_is_medium(rules: RulesService) -> None:
    limit = rules.decimal("SMALL_TENDER_LIMIT")
    assert tier_for(rules, limit + ONE) is Tier.MEDIUM


def test_value_at_the_medium_limit_is_medium(rules: RulesService) -> None:
    limit = rules.decimal("MEDIUM_TENDER_LIMIT")
    assert tier_for(rules, limit) is Tier.MEDIUM


def test_value_just_above_the_medium_limit_is_large(rules: RulesService) -> None:
    limit = rules.decimal("MEDIUM_TENDER_LIMIT")
    assert tier_for(rules, limit + ONE) is Tier.LARGE


def test_a_low_value_high_criticality_challenge_does_not_land_in_small(
    rules: RulesService,
) -> None:
    """The case the whole tier engine exists for."""
    tiny = rules.decimal("SMALL_TENDER_LIMIT") - ONE
    decision = classify(
        rules, value=tiny, criticality=Level.HIGH, innovation_potential=Level.LOW
    )
    assert decision.tier is not Tier.SMALL
    assert decision.tier is Tier.MEDIUM
    assert "Criticality is HIGH" in decision.explanation


def test_high_innovation_cannot_drag_a_critical_challenge_into_small(
    rules: RulesService,
) -> None:
    tiny = rules.decimal("SMALL_TENDER_LIMIT") - ONE
    decision = classify(
        rules, value=tiny, criticality=Level.HIGH, innovation_potential=Level.HIGH
    )
    assert decision.tier is Tier.MEDIUM
    assert any(factor.factor == "criticality_floor" for factor in decision.factors)


def test_high_innovation_opens_a_more_accessible_tier(rules: RulesService) -> None:
    mid = rules.decimal("SMALL_TENDER_LIMIT") + ONE
    assert tier_for(rules, mid, Level.LOW, Level.LOW) is Tier.MEDIUM
    assert tier_for(rules, mid, Level.LOW, Level.HIGH) is Tier.SMALL


def test_value_alone_does_not_decide_the_tier(rules: RulesService) -> None:
    """Same value, three different tiers, depending on the risk factors."""
    value = rules.decimal("SMALL_TENDER_LIMIT") + ONE
    assert tier_for(rules, value, Level.LOW, Level.HIGH) is Tier.SMALL
    assert tier_for(rules, value, Level.LOW, Level.LOW) is Tier.MEDIUM
    assert tier_for(rules, value, Level.HIGH, Level.LOW) is Tier.LARGE


def test_the_explanation_cites_the_rules_it_used(rules: RulesService) -> None:
    decision = classify(
        rules,
        value=Decimal("1000000"),
        criticality=Level.LOW,
        innovation_potential=Level.LOW,
    )
    assert "SMALL_TENDER_LIMIT" in decision.explanation
    assert any("SMALL_TENDER_LIMIT" in citation for citation in decision.as_details()["rules_cited"])


def test_classification_refuses_to_guess_a_missing_input(rules: RulesService) -> None:
    with pytest.raises(TierInputMissing) as error:
        classify(rules, value=None, criticality=None, innovation_potential=Level.LOW)
    assert error.value.missing == ["value", "criticality"]


# ---------------------------------------------------------------------------
# Two-gate eligibility
# ---------------------------------------------------------------------------


def a_startup(db) -> Company:
    return db.scalars(select(Company).where(Company.name == "AquaSense Analytics")).one()


def a_legacy_firm(db) -> Company:
    return db.scalars(select(Company).where(Company.name == "Deshmukh Infra Ltd")).one()


def failed_codes(gate) -> set[str]:
    return {criterion.code for criterion in gate.criteria if not criterion.passed}


def test_gate_one_passes_a_startup(txn_db, rules: RulesService) -> None:
    assert eligibility.gate_one(a_startup(txn_db)).passed is True


def test_a_large_firm_passes_gate_one_but_fails_gate_two(txn_db, rules: RulesService) -> None:
    """The two-gate design in one assertion."""
    legacy = a_legacy_firm(txn_db)

    gate_one = eligibility.gate_one(legacy)
    gate_two = eligibility.gate_two(txn_db, legacy)

    assert gate_one.passed is True, "a large firm is a legally constituted, capable bidder"
    assert gate_two.passed is False, "but it is not in the startup lane"
    assert failed_codes(gate_two) == {"STARTUP_RECOGNITION"}


def test_gate_two_passes_a_recognised_young_startup(txn_db, rules: RulesService) -> None:
    gate = eligibility.gate_two(txn_db, a_startup(txn_db))
    assert gate.passed is True
    assert failed_codes(gate) == set()


def test_gate_two_fails_an_unrecognised_startup(txn_db, rules: RulesService) -> None:
    company = txn_db.scalars(select(Company).where(Company.name == "BinBuddy Systems")).one()
    gate = eligibility.gate_two(txn_db, company)
    assert gate.passed is False
    assert failed_codes(gate) == {"STARTUP_RECOGNITION"}


def test_gate_two_applies_no_limit_the_rules_table_does_not_define(
    txn_db, rules: RulesService
) -> None:
    """Company age and size are reported, never used to exclude.

    No procurement rule sets a maximum age or size for the startup lane, and an
    engine may not invent one, so a company far outside any plausible lane still
    passes those two criteria. Only recognition decides the gate.
    """
    company = a_startup(txn_db)
    company.employee_count = 100000
    company.incorporation_date = date(1980, 1, 1)
    txn_db.flush()

    gate = eligibility.gate_two(txn_db, company)
    age = next(c for c in gate.criteria if c.code == "STARTUP_COMPANY_AGE")
    size = next(c for c in gate.criteria if c.code == "STARTUP_SIZE")

    assert age.passed is True
    assert size.passed is True
    assert "no procurement rule defines a limit" in age.basis
    assert "no procurement rule defines a limit" in size.basis
    assert gate.passed is True


def test_gate_one_fails_a_company_with_no_registration(txn_db, rules: RulesService) -> None:
    company = a_startup(txn_db)
    company.incorporation_date = None
    txn_db.flush()
    assert eligibility.gate_one(company).passed is False


def test_prior_participation_never_blocks_the_startup_lane(txn_db, rules: RulesService) -> None:
    """AquaSense has a past award in the seed, and is still in the lane."""
    company = a_startup(txn_db)
    history = eligibility.prior_participation(txn_db, company.id)
    assert history["awards"] > 0
    gate = eligibility.gate_two(txn_db, company)
    participation = next(c for c in gate.criteria if c.code == "PRIOR_PARTICIPATION")
    assert participation.passed is True


def test_gate_two_reads_no_procurement_rule_at_all(txn_db) -> None:
    gate = eligibility.gate_two(txn_db, a_startup(txn_db))
    assert {criterion.code for criterion in gate.criteria} == {
        "STARTUP_RECOGNITION",
        "STARTUP_COMPANY_AGE",
        "STARTUP_SIZE",
        "PRIOR_PARTICIPATION",
    }
    # Nothing in the gate cites a threshold, because none is defined for it.
    assert all("= " not in criterion.basis for criterion in gate.criteria)


def test_company_age_arithmetic() -> None:
    assert eligibility.completed_years(date(2020, 6, 11), date(2026, 6, 10)) == 5
    assert eligibility.completed_years(date(2020, 6, 11), date(2026, 6, 11)) == 6


# ---------------------------------------------------------------------------
# Tier access
# ---------------------------------------------------------------------------


def make_challenge(
    db,
    tier: Tier,
    *,
    published_days_ago: int | None = None,
    bid_closes_at: datetime | None = None,
) -> Challenge:
    department = db.scalars(select(Department).where(Department.code == "WSSD")).one()
    published_at = (
        datetime.now(timezone.utc) - timedelta(days=published_days_ago)
        if published_days_ago is not None
        else None
    )
    challenge = Challenge(
        title=f"Test challenge ({tier.value})",
        description_raw="Created by the Phase 2 tests.",
        department_id=department.id,
        value=Decimal("1000000"),
        criticality=Level.LOW,
        innovation_potential=Level.LOW,
        tier=tier,
        district="Pune",
        category="WATER",
        published_at=published_at,
        bid_closes_at=bid_closes_at,
    )
    db.add(challenge)
    db.flush()
    return challenge


def add_proposal(db, challenge: Challenge, company: Company, score: Decimal | None) -> Proposal:
    proposal = Proposal(
        challenge_id=challenge.id,
        startup_id=company.id,
        status=ProposalStatus.SUBMITTED,
        total_score=score,
    )
    db.add(proposal)
    db.flush()
    return proposal


def test_small_tier_rejects_a_large_firm(txn_db, rules: RulesService) -> None:
    challenge = make_challenge(txn_db, Tier.SMALL)
    decision = eligibility.assess(txn_db, rules, a_legacy_firm(txn_db), challenge)
    assert decision.tier_access.allowed is False
    assert "reserved for startups" in decision.tier_access.reason
    assert decision.eligible is False


def test_small_tier_admits_a_startup(txn_db, rules: RulesService) -> None:
    challenge = make_challenge(txn_db, Tier.SMALL)
    decision = eligibility.assess(txn_db, rules, a_startup(txn_db), challenge)
    assert decision.tier_access.allowed is True
    assert decision.eligible is True


def test_medium_tier_is_startup_first(txn_db, rules: RulesService) -> None:
    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=None)
    decision = eligibility.assess(txn_db, rules, a_startup(txn_db), challenge)
    assert decision.tier_access.allowed is True


def test_medium_stays_closed_to_large_firms_while_the_window_is_open(
    txn_db, rules: RulesService
) -> None:
    bid_window = rules.integer("BID_WINDOW_DAYS")
    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=bid_window - 1)
    decision = eligibility.assess(txn_db, rules, a_legacy_firm(txn_db), challenge)
    assert decision.tier_access.allowed is False
    assert decision.tier_access.fallback.fired is False
    assert decision.tier_access.fallback.window_closed is False


def test_the_fallback_trigger_opens_medium_when_the_startup_lane_is_thin(
    txn_db, rules: RulesService
) -> None:
    bid_window = rules.integer("BID_WINDOW_DAYS")
    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=bid_window + 1)
    decision = eligibility.assess(txn_db, rules, a_legacy_firm(txn_db), challenge)

    assert decision.tier_access.allowed is True
    trigger = decision.tier_access.fallback
    assert trigger.fired is True
    assert trigger.qualified_startup_bids < rules.integer("MIN_STARTUP_BIDS")


def test_the_fallback_trigger_stays_shut_when_enough_startups_qualify(
    txn_db, rules: RulesService
) -> None:
    bid_window = rules.integer("BID_WINDOW_DAYS")
    min_bids = rules.integer("MIN_STARTUP_BIDS")
    passing_score = rules.decimal("MIN_TECH_SCORE")

    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=bid_window + 1)
    startups = txn_db.scalars(
        select(Company).where(Company.type == CompanyType.STARTUP).limit(min_bids)
    ).all()
    for company in startups:
        add_proposal(txn_db, challenge, company, passing_score)

    decision = eligibility.assess(txn_db, rules, a_legacy_firm(txn_db), challenge)
    assert decision.tier_access.fallback.qualified_startup_bids == min_bids
    assert decision.tier_access.fallback.fired is False
    assert decision.tier_access.allowed is False


def test_bids_below_the_technical_score_do_not_count_as_qualified(
    txn_db, rules: RulesService
) -> None:
    bid_window = rules.integer("BID_WINDOW_DAYS")
    min_bids = rules.integer("MIN_STARTUP_BIDS")
    below = rules.decimal("MIN_TECH_SCORE") - ONE

    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=bid_window + 1)
    startups = txn_db.scalars(
        select(Company).where(Company.type == CompanyType.STARTUP).limit(min_bids)
    ).all()
    for company in startups:
        add_proposal(txn_db, challenge, company, below)

    decision = fallback.evaluate(txn_db, rules, challenge)
    assert decision.startup_bids == min_bids
    assert decision.qualified_startup_bids == 0
    assert decision.fired is True


def test_large_tier_is_open_and_carries_validated_kpi_history(
    txn_db, rules: RulesService
) -> None:
    challenge = make_challenge(txn_db, Tier.LARGE)
    decision = eligibility.assess(txn_db, rules, a_legacy_firm(txn_db), challenge)
    assert decision.tier_access.allowed is True

    startup_decision = eligibility.assess(txn_db, rules, a_startup(txn_db), challenge)
    history = startup_decision.tier_access.validated_kpi_history
    assert history["verified_kpis"] > 0


def test_every_fallback_evaluation_is_audited(txn_db, rules: RulesService) -> None:
    bid_window = rules.integer("BID_WINDOW_DAYS")
    challenge = make_challenge(txn_db, Tier.MEDIUM, published_days_ago=bid_window + 1)
    fallback.evaluate_and_log(txn_db, rules, challenge)
    txn_db.flush()

    entry = txn_db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "challenge", AuditLog.entity_id == challenge.id)
        .order_by(AuditLog.id.desc())
    ).first()

    assert entry.action == "MEDIUM_FALLBACK_TRIGGER_FIRED"
    assert entry.actor_label == "fallback-trigger"
    assert entry.reason
    # The values that fired it are in the record, not just the verdict.
    assert entry.details["qualified_startup_bids"] == 0
    assert any("MIN_STARTUP_BIDS" in citation for citation in entry.details["rules_cited"])


# ---------------------------------------------------------------------------
# Barrier analysis
# ---------------------------------------------------------------------------


def test_barrier_analysis_flags_the_classic_exclusions(rules: RulesService) -> None:
    analysis = barriers.analyse(
        rules,
        [
            barriers.ProposedCriterion(
                barriers.BarrierCode.TURNOVER_FLOOR, "Annual turnover of at least 5 crore"
            ),
            barriers.ProposedCriterion(
                barriers.BarrierCode.YEARS_IN_BUSINESS, "At least 5 years in business"
            ),
            barriers.ProposedCriterion(
                barriers.BarrierCode.PRIOR_GOVERNMENT_PROJECTS,
                "Two completed government projects",
            ),
        ],
    )
    assert analysis.flagged == len(analysis.criteria)
    assert all(flag.excludes_startups for flag in analysis.criteria)
    assert all(flag.classification is barriers.Classification.TRADITIONAL for flag in analysis.criteria)
    assert all(flag.rule_cited for flag in analysis.criteria)


def test_barrier_analysis_makes_no_claim_about_unknown_criteria(rules: RulesService) -> None:
    analysis = barriers.analyse(
        rules,
        [barriers.ProposedCriterion(barriers.BarrierCode.OTHER, "Must hold a valid ISO 27001")],
    )
    flag = analysis.criteria[0]
    assert flag.excludes_startups is None
    assert flag.classification is barriers.Classification.UNCLASSIFIED
    assert analysis.flagged == 0


def test_barrier_analysis_only_flags_and_never_blocks(rules: RulesService) -> None:
    analysis = barriers.analyse(
        rules,
        [barriers.ProposedCriterion(barriers.BarrierCode.TURNOVER_FLOOR, "5 crore")],
    )
    assert "flags for the officer, not a block" in analysis.summary
    assert "Officer decides" in analysis.criteria[0].officer_action


# ---------------------------------------------------------------------------
# No hard-coded thresholds
# ---------------------------------------------------------------------------

ENGINE_MODULES = [
    "app/services/rules.py",
    "app/services/tiering.py",
    "app/services/eligibility.py",
    "app/services/fallback.py",
    "app/services/barriers.py",
]


@pytest.mark.parametrize("module_path", ENGINE_MODULES)
def test_no_numeric_literal_appears_in_tier_or_eligibility_logic(module_path: str) -> None:
    """Non-negotiable rule 1, enforced by the test suite rather than by review.

    Every threshold these modules apply is read from procurement_rule, so a bare
    number in any of them is a bug.
    """
    source = pathlib.Path(module_path).read_text(encoding="utf-8")
    offenders = [
        (node.lineno, node.value)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ]
    assert offenders == [], f"{module_path} contains numeric literals: {offenders}"


# ---------------------------------------------------------------------------
# Changing a rule changes behaviour
# ---------------------------------------------------------------------------


def test_editing_a_rule_changes_the_tier_engine(txn_client, txn_db, demo_password: str) -> None:
    """The demonstration the exit criteria ask for, through the admin API."""
    rules = RulesService(txn_db)
    small_limit = rules.decimal("SMALL_TENDER_LIMIT")
    value = small_limit - ONE

    token = login(txn_client, "admin@procureflow.in", demo_password)
    officer = login(txn_client, "officer@mahagov.in", demo_password)

    body = {"value": str(value), "criticality": "LOW", "innovation_potential": "LOW"}
    before = txn_client.post("/engine/tier", json=body, headers=auth_header(officer))
    assert before.status_code == 200
    assert before.json()["tier"] == Tier.SMALL.value

    rule_id = txn_db.scalars(
        select(ProcurementRule.id).where(ProcurementRule.rule_name == "SMALL_TENDER_LIMIT")
    ).one()
    edit = txn_client.put(
        f"/admin/rules/{rule_id}",
        json={
            "value": str(value - ONE),
            "reason": "Phase 2 demonstration: lower the SMALL ceiling below the test value.",
        },
        headers=auth_header(token),
    )
    assert edit.status_code == 200, edit.text

    after = txn_client.post("/engine/tier", json=body, headers=auth_header(officer))
    assert after.json()["tier"] == Tier.MEDIUM.value, "the same input now classifies differently"


def test_a_rule_edit_is_audited_with_before_and_after(
    txn_client, txn_db, demo_password: str
) -> None:
    token = login(txn_client, "admin@procureflow.in", demo_password)
    rule_id = txn_db.scalars(
        select(ProcurementRule.id).where(ProcurementRule.rule_name == "MIN_TECH_SCORE")
    ).one()

    response = txn_client.put(
        f"/admin/rules/{rule_id}",
        json={"value": "70", "reason": "Raise the technical bar for the demo."},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    entry = txn_db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "procurement_rule", AuditLog.entity_id == rule_id)
        .order_by(AuditLog.id.desc())
    ).first()
    assert entry.action == "PROCUREMENT_RULE_UPDATED"
    assert entry.reason == "Raise the technical bar for the demo."
    assert entry.details["changes"]["value"]["from"].startswith("60")
    assert entry.details["changes"]["value"]["to"].startswith("70")


def test_rule_editing_is_admin_only(txn_client, txn_db, demo_password: str) -> None:
    officer = login(txn_client, "officer@mahagov.in", demo_password)
    rule_id = txn_db.scalars(
        select(ProcurementRule.id).where(ProcurementRule.rule_name == "MIN_TECH_SCORE")
    ).one()
    response = txn_client.put(
        f"/admin/rules/{rule_id}",
        json={"value": "70", "reason": "should not be allowed"},
        headers=auth_header(officer),
    )
    assert response.status_code == 403


def test_a_rule_edit_needs_a_reason(txn_client, txn_db, demo_password: str) -> None:
    token = login(txn_client, "admin@procureflow.in", demo_password)
    rule_id = txn_db.scalars(
        select(ProcurementRule.id).where(ProcurementRule.rule_name == "MIN_TECH_SCORE")
    ).one()
    response = txn_client.put(
        f"/admin/rules/{rule_id}", json={"value": "70"}, headers=auth_header(token)
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Engine endpoints
# ---------------------------------------------------------------------------


def test_classify_endpoint_persists_and_audits(txn_client, txn_db, demo_password: str) -> None:
    challenge = make_challenge(txn_db, Tier.SMALL)
    challenge.tier = None
    challenge.value = Decimal("1000000")
    challenge.criticality = Level.HIGH
    challenge.innovation_potential = Level.LOW
    txn_db.flush()

    token = login(txn_client, "officer@mahagov.in", demo_password)
    response = txn_client.post(
        f"/engine/challenges/{challenge.id}/classify", headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tier"] == Tier.MEDIUM.value
    assert body["persisted"] is True

    txn_db.refresh(challenge)
    assert challenge.tier is Tier.MEDIUM
    assert challenge.tier_explanation

    entry = txn_db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "challenge", AuditLog.entity_id == challenge.id)
        .order_by(AuditLog.id.desc())
    ).first()
    assert entry.action == "TIER_CLASSIFIED"
    assert entry.actor_user_id is not None


def test_classify_endpoint_refuses_a_challenge_with_no_value(
    txn_client, txn_db, demo_password: str
) -> None:
    challenge = make_challenge(txn_db, Tier.SMALL)
    challenge.value = None
    txn_db.flush()

    token = login(txn_client, "officer@mahagov.in", demo_password)
    response = txn_client.post(
        f"/engine/challenges/{challenge.id}/classify", headers=auth_header(token)
    )
    assert response.status_code == 422
    assert "value" in response.json()["detail"]["missing_fields"]


def test_engine_endpoints_reject_a_startup_account(
    txn_client, txn_db, demo_password: str
) -> None:
    token = login(txn_client, "founder@startup.in", demo_password)
    response = txn_client.post(
        "/engine/tier",
        json={"value": "1000000", "criticality": "LOW", "innovation_potential": "LOW"},
        headers=auth_header(token),
    )
    assert response.status_code == 403


def test_eligibility_endpoint_returns_both_gates(
    txn_client, txn_db, demo_password: str
) -> None:
    challenge = make_challenge(txn_db, Tier.SMALL)
    legacy = a_legacy_firm(txn_db)
    token = login(txn_client, "officer@mahagov.in", demo_password)

    response = txn_client.get(
        f"/engine/challenges/{challenge.id}/eligibility/{legacy.id}", headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gate_one"]["passed"] is True
    assert body["gate_two"]["passed"] is False
    assert body["tier_access"]["allowed"] is False
    assert body["eligible"] is False


def test_barrier_analysis_endpoint(txn_client, txn_db, demo_password: str) -> None:
    token = login(txn_client, "officer@mahagov.in", demo_password)
    response = txn_client.post(
        "/engine/barrier-analysis",
        json={
            "criteria": [
                {"code": "TURNOVER_FLOOR", "detail": "Annual turnover of at least 5 crore"},
                {"code": "OTHER", "detail": "Must hold a valid ISO 27001 certificate"},
            ]
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flagged"] == 1
    assert body["criteria"][0]["rule_cited"]
