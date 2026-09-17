"""Phase 3 checks: founder groups, the rotation rule and splitting detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import CompanyType, Level, ProposalStatus, Tier
from app.models import (
    AuditLog,
    Award,
    Challenge,
    Company,
    CompanyFounder,
    Department,
    Founder,
    Proposal,
)
from app.services import founders, rotation, splitting
from app.services.rules import RulesService


@pytest.fixture
def rules(txn_db) -> RulesService:
    return RulesService(txn_db)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def department(db, code: str = "WSSD") -> Department:
    return db.scalars(select(Department).where(Department.code == code)).one()


def make_challenge(
    db,
    tier: Tier,
    *,
    category: str = "WATER",
    department_code: str = "WSSD",
    value: Decimal = Decimal("1000000"),
    created_at: datetime | None = None,
) -> Challenge:
    challenge = Challenge(
        title=f"Phase 3 challenge ({tier.value}, {category})",
        description_raw="Created by the Phase 3 tests.",
        department_id=department(db, department_code).id,
        value=value,
        criticality=Level.LOW,
        innovation_potential=Level.LOW,
        tier=tier,
        district="Pune",
        category=category,
    )
    db.add(challenge)
    db.flush()
    if created_at is not None:
        challenge.created_at = created_at
        db.flush()
    return challenge


def make_company(db, name: str, *, dpiit: bool = True) -> Company:
    company = Company(
        name=name,
        type=CompanyType.STARTUP,
        district="Pune",
        profile_text="Phase 3 test company.",
        dpiit_recognised=dpiit,
        incorporation_date=datetime.now(timezone.utc).date(),
        employee_count=10,
    )
    db.add(company)
    db.flush()
    return company


def make_founder(db, name: str, companies: list[Company]) -> Founder:
    founder = Founder(name=name, email=f"{name.lower().replace(' ', '.')}@phase3.test")
    db.add(founder)
    db.flush()
    for company in companies:
        db.add(CompanyFounder(company_id=company.id, founder_id=founder.id))
    db.flush()
    return founder


def award_to(db, challenge: Challenge, company: Company, *, days_ago: int) -> Award:
    award = Award(
        challenge_id=challenge.id,
        company_id=company.id,
        awarded_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        value=challenge.value,
    )
    db.add(award)
    db.flush()
    return award


def add_qualified_rivals(db, challenge: Challenge, rules: RulesService, how_many: int) -> None:
    """Other startups bidding on this challenge at or above the technical bar."""
    passing = rules.decimal("MIN_TECH_SCORE")
    rivals = db.scalars(
        select(Company)
        .where(Company.type == CompanyType.STARTUP, Company.name.notlike("Phase 3%"))
        .limit(how_many)
    ).all()
    for rival in rivals:
        db.add(
            Proposal(
                challenge_id=challenge.id,
                startup_id=rival.id,
                status=ProposalStatus.SUBMITTED,
                total_score=passing,
            )
        )
    db.flush()


def two_consecutive_awards(db, company_a: Company, company_b: Company, category: str) -> None:
    """Two prior SMALL awards in the same department and category."""
    first = make_challenge(db, Tier.SMALL, category=category)
    second = make_challenge(db, Tier.SMALL, category=category)
    award_to(db, first, company_a, days_ago=200)
    award_to(db, second, company_b, days_ago=100)


# ---------------------------------------------------------------------------
# Founder groups
# ---------------------------------------------------------------------------


def test_founder_group_spans_companies_sharing_a_founder(txn_db) -> None:
    """Sneha Pawar is on three seeded companies, so all three are one group."""
    aqua = txn_db.scalars(select(Company).where(Company.name == "AgriTrace Solutions")).one()
    group = founders.resolve(txn_db, aqua.id)
    assert {"AgriTrace Solutions", "FarmSight AI", "GreenYield Labs"} <= set(group.company_names)
    assert "Sneha Pawar" in group.founder_names


def test_founder_group_of_a_company_with_one_founder_is_itself(txn_db) -> None:
    company = txn_db.scalars(select(Company).where(Company.name == "JalNet Telemetry")).one()
    group = founders.resolve(txn_db, company.id)
    assert group.company_names == ["JalNet Telemetry"]


def test_a_new_company_joins_the_group_through_its_founder(txn_db) -> None:
    old = make_company(txn_db, "Phase 3 Original Ltd")
    fresh = make_company(txn_db, "Phase 3 Reincorporated Ltd")
    make_founder(txn_db, "Repeat Founder", [old, fresh])

    group = founders.resolve(txn_db, fresh.id)
    assert old.id in group.company_ids
    assert fresh.id in group.company_ids


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


def test_same_founder_new_company_is_still_blocked_on_the_third_award(
    txn_db, rules: RulesService
) -> None:
    """The case the rule exists for: a new entity does not reset the counter."""
    first_company = make_company(txn_db, "Phase 3 Rotation One")
    second_company = make_company(txn_db, "Phase 3 Rotation Two")
    third_company = make_company(txn_db, "Phase 3 Rotation Three")
    make_founder(
        txn_db, "Persistent Founder", [first_company, second_company, third_company]
    )

    two_consecutive_awards(txn_db, first_company, second_company, "ROTATION_TEST")

    third = make_challenge(txn_db, Tier.SMALL, category="ROTATION_TEST")
    add_qualified_rivals(txn_db, third, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, third, third_company)

    assert decision.applies is True
    assert decision.blocked is True
    assert decision.consecutive_awards == 2
    assert "Persistent Founder" in decision.reason_text
    # The bid comes from a company that has never been awarded anything.
    assert third_company.id not in {
        award.company_id for award in txn_db.scalars(select(Award)).all()
    }


def test_rotation_does_not_fire_on_the_medium_tier(txn_db, rules: RulesService) -> None:
    company_a = make_company(txn_db, "Phase 3 Medium One")
    company_b = make_company(txn_db, "Phase 3 Medium Two")
    make_founder(txn_db, "Medium Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "MEDIUM_TEST")

    challenge = make_challenge(txn_db, Tier.MEDIUM, category="MEDIUM_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, challenge, company_b)
    assert decision.applies is False
    assert decision.blocked is False
    assert "SMALL tier only" in decision.reason_text


def test_rotation_does_not_fire_on_the_large_tier(txn_db, rules: RulesService) -> None:
    company_a = make_company(txn_db, "Phase 3 Large One")
    company_b = make_company(txn_db, "Phase 3 Large Two")
    make_founder(txn_db, "Large Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "LARGE_TEST")

    challenge = make_challenge(txn_db, Tier.LARGE, category="LARGE_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, challenge, company_b)
    assert decision.applies is False
    assert decision.blocked is False


def test_rotation_does_not_fire_without_qualified_alternatives(
    txn_db, rules: RulesService
) -> None:
    """Rotating an award to nobody helps no one."""
    company_a = make_company(txn_db, "Phase 3 Alone One")
    company_b = make_company(txn_db, "Phase 3 Alone Two")
    make_founder(txn_db, "Lonely Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "ALONE_TEST")

    challenge = make_challenge(txn_db, Tier.SMALL, category="ALONE_TEST")
    # No rival proposals at all.

    decision = rotation.evaluate(txn_db, rules, challenge, company_b)
    assert decision.applies is True
    assert decision.blocked is False
    assert decision.qualified_alternatives == 0
    assert "would serve the department worse" in decision.reason_text


def test_rivals_below_the_technical_score_are_not_alternatives(
    txn_db, rules: RulesService
) -> None:
    company_a = make_company(txn_db, "Phase 3 Weak One")
    company_b = make_company(txn_db, "Phase 3 Weak Two")
    make_founder(txn_db, "Weak Rivals Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "WEAK_TEST")

    challenge = make_challenge(txn_db, Tier.SMALL, category="WEAK_TEST")
    below = rules.decimal("MIN_TECH_SCORE") - Decimal("1")
    for rival in txn_db.scalars(
        select(Company).where(Company.type == CompanyType.STARTUP).limit(5)
    ).all():
        txn_db.add(
            Proposal(
                challenge_id=challenge.id,
                startup_id=rival.id,
                status=ProposalStatus.SUBMITTED,
                total_score=below,
            )
        )
    txn_db.flush()

    decision = rotation.evaluate(txn_db, rules, challenge, company_b)
    assert decision.qualified_alternatives == 0
    assert decision.blocked is False


def test_a_single_prior_award_does_not_trigger_rotation(txn_db, rules: RulesService) -> None:
    company = make_company(txn_db, "Phase 3 First Timer")
    make_founder(txn_db, "First Timer Founder", [company])
    first = make_challenge(txn_db, Tier.SMALL, category="FIRST_TEST")
    award_to(txn_db, first, company, days_ago=50)

    challenge = make_challenge(txn_db, Tier.SMALL, category="FIRST_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, challenge, company)
    assert decision.consecutive_awards == 1
    assert decision.blocked is False


def test_the_run_breaks_when_someone_else_wins(txn_db, rules: RulesService) -> None:
    ours = make_company(txn_db, "Phase 3 Run One")
    also_ours = make_company(txn_db, "Phase 3 Run Two")
    make_founder(txn_db, "Run Founder", [ours, also_ours])
    outsider = make_company(txn_db, "Phase 3 Outsider")
    make_founder(txn_db, "Outsider Founder", [outsider])

    first = make_challenge(txn_db, Tier.SMALL, category="RUN_TEST")
    second = make_challenge(txn_db, Tier.SMALL, category="RUN_TEST")
    third = make_challenge(txn_db, Tier.SMALL, category="RUN_TEST")
    award_to(txn_db, first, ours, days_ago=300)
    award_to(txn_db, second, also_ours, days_ago=200)
    award_to(txn_db, third, outsider, days_ago=100)  # breaks the run

    challenge = make_challenge(txn_db, Tier.SMALL, category="RUN_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, challenge, ours)
    assert decision.consecutive_awards == 0
    assert decision.blocked is False


def test_rotation_counts_only_the_same_department_and_category(
    txn_db, rules: RulesService
) -> None:
    company_a = make_company(txn_db, "Phase 3 Scope One")
    company_b = make_company(txn_db, "Phase 3 Scope Two")
    make_founder(txn_db, "Scope Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "SCOPE_TEST")

    # Same department, a different category.
    other = make_challenge(txn_db, Tier.SMALL, category="A_DIFFERENT_CATEGORY")
    add_qualified_rivals(txn_db, other, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))
    assert rotation.evaluate(txn_db, rules, other, company_b).blocked is False

    # Same category, a different department.
    elsewhere = make_challenge(
        txn_db, Tier.SMALL, category="SCOPE_TEST", department_code="AGRI"
    )
    add_qualified_rivals(txn_db, elsewhere, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))
    assert rotation.evaluate(txn_db, rules, elsewhere, company_b).blocked is False


def test_a_rotation_block_is_audited_with_its_reason(txn_db, rules: RulesService) -> None:
    company_a = make_company(txn_db, "Phase 3 Audit One")
    company_b = make_company(txn_db, "Phase 3 Audit Two")
    make_founder(txn_db, "Audited Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "AUDIT_TEST")

    challenge = make_challenge(txn_db, Tier.SMALL, category="AUDIT_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate_and_log(txn_db, rules, challenge, company_b)
    assert decision.blocked is True
    txn_db.flush()

    entry = txn_db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "challenge", AuditLog.entity_id == challenge.id)
        .order_by(AuditLog.id.desc())
    ).first()
    assert entry.action == "ROTATION_RULE_BLOCKED_AWARD"
    assert entry.actor_label == "rotation-rule"
    assert "Audited Founder" in entry.reason
    assert entry.details["consecutive_awards"] == 2
    assert any("MIN_QUALIFIED_ALTERNATIVES" in cite for cite in entry.details["rules_cited"])


def test_rotation_blocks_small_tier_access(txn_db, rules: RulesService) -> None:
    """The block reaches the eligibility assessment, not just the rotation service."""
    from app.services import eligibility

    company_a = make_company(txn_db, "Phase 3 Access One")
    company_b = make_company(txn_db, "Phase 3 Access Two")
    make_founder(txn_db, "Access Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "ACCESS_TEST")

    challenge = make_challenge(txn_db, Tier.SMALL, category="ACCESS_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = eligibility.assess(txn_db, rules, company_b, challenge)
    assert decision.tier_access.allowed is False
    assert decision.tier_access.rotation.blocked is True
    assert decision.eligible is False


def test_rotation_reads_its_thresholds_from_the_rules_table(
    txn_db, rules: RulesService
) -> None:
    company_a = make_company(txn_db, "Phase 3 Threshold One")
    company_b = make_company(txn_db, "Phase 3 Threshold Two")
    make_founder(txn_db, "Threshold Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "THRESHOLD_TEST")

    challenge = make_challenge(txn_db, Tier.SMALL, category="THRESHOLD_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    decision = rotation.evaluate(txn_db, rules, challenge, company_b)
    cited = {rule.rule_name for rule in decision.rules_cited}
    assert cited == {"MIN_QUALIFIED_ALTERNATIVES", "MIN_TECH_SCORE"}


# ---------------------------------------------------------------------------
# Splitting detection
# ---------------------------------------------------------------------------


def test_splitting_detector_flags_a_split_requirement(txn_db, rules: RulesService) -> None:
    """Three SMALL challenges that add up to a MEDIUM one."""
    small_limit = rules.decimal("SMALL_TENDER_LIMIT")
    now = datetime.now(timezone.utc)
    each = small_limit - Decimal("1")

    for offset in (0, 3, 6):
        make_challenge(
            txn_db,
            Tier.SMALL,
            category="SPLIT_TEST",
            value=each,
            created_at=now - timedelta(days=offset),
        )

    result = splitting.scan(txn_db, rules, window_days=30)
    clusters = [c for c in result.clusters if c.category == "SPLIT_TEST"]

    assert len(clusters) == 1
    cluster = clusters[0]
    assert len(cluster.members) == 3
    assert cluster.highest_individual_band is Tier.SMALL
    assert cluster.combined_band is Tier.MEDIUM
    assert cluster.combined_value == each * 3
    assert "one requirement bought in pieces" in cluster.reason


def test_splitting_detector_ignores_challenges_outside_the_window(
    txn_db, rules: RulesService
) -> None:
    small_limit = rules.decimal("SMALL_TENDER_LIMIT")
    now = datetime.now(timezone.utc)
    each = small_limit - Decimal("1")

    for offset in (0, 200, 400):
        make_challenge(
            txn_db,
            Tier.SMALL,
            category="SPREAD_TEST",
            value=each,
            created_at=now - timedelta(days=offset),
        )

    result = splitting.scan(txn_db, rules, window_days=30)
    assert [c for c in result.clusters if c.category == "SPREAD_TEST"] == []


def test_splitting_detector_ignores_different_departments(
    txn_db, rules: RulesService
) -> None:
    small_limit = rules.decimal("SMALL_TENDER_LIMIT")
    now = datetime.now(timezone.utc)
    each = small_limit - Decimal("1")

    for code in ("WSSD", "AGRI", "UDD"):
        make_challenge(
            txn_db,
            Tier.SMALL,
            category="CROSS_DEPT_TEST",
            department_code=code,
            value=each,
            created_at=now,
        )

    result = splitting.scan(txn_db, rules, window_days=30)
    assert [c for c in result.clusters if c.category == "CROSS_DEPT_TEST"] == []


def test_splitting_detector_does_not_flag_a_total_that_stays_in_band(
    txn_db, rules: RulesService
) -> None:
    now = datetime.now(timezone.utc)
    for offset in (0, 1):
        make_challenge(
            txn_db,
            Tier.SMALL,
            category="IN_BAND_TEST",
            value=Decimal("100000"),
            created_at=now - timedelta(days=offset),
        )
    result = splitting.scan(txn_db, rules, window_days=30)
    assert [c for c in result.clusters if c.category == "IN_BAND_TEST"] == []


def test_splitting_detector_only_flags_and_never_blocks(txn_db, rules: RulesService) -> None:
    result = splitting.scan(txn_db, rules, window_days=30)
    assert "nothing here blocks a challenge" in result.summary


def test_a_flagged_cluster_is_audited(txn_db, rules: RulesService) -> None:
    small_limit = rules.decimal("SMALL_TENDER_LIMIT")
    now = datetime.now(timezone.utc)
    for offset in (0, 2, 4):
        make_challenge(
            txn_db,
            Tier.SMALL,
            category="AUDITED_SPLIT",
            value=small_limit - Decimal("1"),
            created_at=now - timedelta(days=offset),
        )

    splitting.scan_and_log(txn_db, rules, window_days=30)
    txn_db.flush()

    entries = txn_db.scalars(
        select(AuditLog).where(AuditLog.action == "SPLITTING_PATTERN_FLAGGED")
    ).all()
    assert entries
    assert any("AUDITED_SPLIT" in (entry.details or {}).get("category", "") for entry in entries)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_splitting_scan_endpoint_is_admin_only(txn_client, demo_password: str) -> None:
    from tests.conftest import auth_header, login

    officer = login(txn_client, "officer@mahagov.in", demo_password)
    assert (
        txn_client.get("/admin/splitting-scan?window_days=30", headers=auth_header(officer))
    ).status_code == 403

    admin = login(txn_client, "admin@procureflow.in", demo_password)
    response = txn_client.get(
        "/admin/splitting-scan?window_days=30", headers=auth_header(admin)
    )
    assert response.status_code == 200, response.text
    assert response.json()["window_days"] == 30


def test_splitting_scan_requires_a_window(txn_client, demo_password: str) -> None:
    """No procurement rule defines 'closely timed', so the caller must say."""
    from tests.conftest import auth_header, login

    admin = login(txn_client, "admin@procureflow.in", demo_password)
    assert txn_client.get("/admin/splitting-scan", headers=auth_header(admin)).status_code == 422


def test_founder_group_endpoint(txn_client, txn_db, demo_password: str) -> None:
    from tests.conftest import auth_header, login

    company = txn_db.scalars(select(Company).where(Company.name == "FarmSight AI")).one()
    officer = login(txn_client, "officer@mahagov.in", demo_password)
    response = txn_client.get(
        f"/engine/companies/{company.id}/founder-group", headers=auth_header(officer)
    )
    assert response.status_code == 200
    assert "Sneha Pawar" in response.json()["founders"]


def test_rotation_endpoint(txn_client, txn_db, rules: RulesService, demo_password: str) -> None:
    from tests.conftest import auth_header, login

    company_a = make_company(txn_db, "Phase 3 Endpoint One")
    company_b = make_company(txn_db, "Phase 3 Endpoint Two")
    make_founder(txn_db, "Endpoint Founder", [company_a, company_b])
    two_consecutive_awards(txn_db, company_a, company_b, "ENDPOINT_TEST")
    challenge = make_challenge(txn_db, Tier.SMALL, category="ENDPOINT_TEST")
    add_qualified_rivals(txn_db, challenge, rules, rules.integer("MIN_QUALIFIED_ALTERNATIVES"))

    officer = login(txn_client, "officer@mahagov.in", demo_password)
    response = txn_client.get(
        f"/engine/challenges/{challenge.id}/rotation/{company_b.id}",
        headers=auth_header(officer),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocked"] is True
    assert body["consecutive_awards"] == 2
    assert "Endpoint Founder" in body["founder_group"]["founders"]
