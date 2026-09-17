"""Phase 1 checks: schema, seed data, auth and server-side RBAC.

The seed-count tests assert exactly what the seed produces, so they need a
freshly seeded database. Walking the demo adds rows and will fail them - which
is the point: they are checking the seed, not the application. Run
"npm run test:fresh" to reset and test in one step.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.enums import CompanyType, UserRole
from app.models import (
    Award,
    Challenge,
    Company,
    CompanyFounder,
    Department,
    Founder,
    Kpi,
    Pilot,
    ProcurementRule,
    User,
)
from tests.conftest import auth_header, login

DEMO_ACCOUNTS = {
    "officer@mahagov.in": UserRole.GOVERNMENT,
    "founder@startup.in": UserRole.STARTUP,
    "expert@evaluator.in": UserRole.EXPERT,
    "admin@procureflow.in": UserRole.ADMIN,
}


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("email,expected_role", list(DEMO_ACCOUNTS.items()))
def test_every_demo_account_can_log_in(
    client: TestClient, demo_password: str, email: str, expected_role: UserRole
) -> None:
    response = client.post("/auth/login", json={"email": email, "password": demo_password})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == expected_role.value
    assert body["access_token"]


def test_login_rejects_a_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "admin@procureflow.in", "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_me_returns_the_logged_in_user(client: TestClient, demo_password: str) -> None:
    token = login(client, "founder@startup.in", demo_password)
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["company"]["name"] == "AquaSense Analytics"


# ---------------------------------------------------------------------------
# Server-side RBAC
# ---------------------------------------------------------------------------


def test_admin_endpoint_requires_authentication(client: TestClient) -> None:
    assert client.get("/admin/rules").status_code == 401


@pytest.mark.parametrize(
    "email", ["officer@mahagov.in", "founder@startup.in", "expert@evaluator.in"]
)
def test_admin_endpoint_rejects_every_other_role(
    client: TestClient, demo_password: str, email: str
) -> None:
    token = login(client, email, demo_password)
    response = client.get("/admin/rules", headers=auth_header(token))
    assert response.status_code == 403, response.text
    assert "may not use this endpoint" in response.json()["detail"]


def test_admin_endpoint_accepts_the_admin(client: TestClient, demo_password: str) -> None:
    token = login(client, "admin@procureflow.in", demo_password)
    response = client.get("/admin/rules", headers=auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) > 0


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def test_seeded_companies(db) -> None:
    startups = db.scalar(
        select(func.count()).select_from(Company).where(Company.type == CompanyType.STARTUP)
    )
    legacy = db.scalar(
        select(func.count()).select_from(Company).where(Company.type == CompanyType.LEGACY)
    )
    assert startups == 30
    assert legacy == 10


def test_startups_are_spread_across_districts(db) -> None:
    districts = db.scalars(
        select(Company.district).where(Company.type == CompanyType.STARTUP).distinct()
    ).all()
    assert len(districts) >= 10


def test_four_demo_accounts_one_per_role(db) -> None:
    roles = db.scalars(select(User.role)).all()
    assert sorted(role.value for role in roles) == sorted(
        role.value for role in DEMO_ACCOUNTS.values()
    )


def test_eight_past_challenges_each_with_a_completed_pilot(db) -> None:
    assert db.scalar(select(func.count()).select_from(Challenge)) == 8
    assert db.scalar(select(func.count()).select_from(Pilot)) == 8
    assert db.scalar(select(func.count()).select_from(Award)) == 8
    assert db.scalar(select(func.count()).select_from(Department)) == 8


def test_every_past_kpi_has_a_validated_value_separate_from_the_claim(db) -> None:
    kpis = db.scalars(select(Kpi)).all()
    assert len(kpis) == 16
    for kpi in kpis:
        assert kpi.claimed_value is not None
        assert kpi.validated_value is not None
        assert kpi.status.value == "VERIFIED"


def test_at_least_three_founders_appear_on_two_or_more_companies(db) -> None:
    rows = db.execute(
        select(Founder.name, func.count(CompanyFounder.company_id).label("companies"))
        .join(CompanyFounder, CompanyFounder.founder_id == Founder.id)
        .group_by(Founder.id, Founder.name)
        .having(func.count(CompanyFounder.company_id) > 1)
    ).all()
    assert len(rows) >= 3, f"only {len(rows)} founders span multiple companies"


def test_every_company_has_at_least_one_founder_or_is_a_legacy_firm(db) -> None:
    startups_without_founders = db.scalars(
        select(Company.name)
        .outerjoin(CompanyFounder, CompanyFounder.company_id == Company.id)
        .where(Company.type == CompanyType.STARTUP, CompanyFounder.founder_id.is_(None))
    ).all()
    assert startups_without_founders == []


# ---------------------------------------------------------------------------
# Procurement rules
# ---------------------------------------------------------------------------


REQUIRED_RULES = {
    "MIN_STARTUP_BIDS",
    "MIN_TECH_SCORE",
    "BID_WINDOW_DAYS",
    "STARTUP_ALLOCATION_PCT",
    "SMALL_TENDER_LIMIT",
    "MEDIUM_TENDER_LIMIT",
    "MIN_QUALIFIED_ALTERNATIVES",
}


def test_exactly_the_seven_required_rules_are_seeded_and_active(db) -> None:
    seeded = {
        rule.rule_name
        for rule in db.scalars(select(ProcurementRule).where(ProcurementRule.active.is_(True)))
    }
    # Exactly the seven the specification names - no invented rules.
    assert seeded == REQUIRED_RULES


def test_every_seeded_rule_is_labelled_a_prototype_setting(db) -> None:
    rules = db.scalars(select(ProcurementRule)).all()
    # All seven are prototype assumptions, so none of them claims a legal source.
    # The column stays nullable so the UI can show the distinction once a rule is
    # traced to a published policy document.
    assert all(rule.source_reference is None for rule in rules)
    assert all(rule.effective_from is not None for rule in rules)
