"""Phase 4 checks: the problem analyzer, KPI locking and the knowledge base."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import ChallengeStatus, KpiDirection
from app.models import Challenge, Department, Kpi
from app.services import analyzer, embeddings, knowledge, llm
from tests.conftest import auth_header, login

WATER_PROBLEM = (
    "Our distribution network in the city loses a large share of treated water before it "
    "reaches households. We cannot detect where the losses happen and the field team finds "
    "out only when a road caves in. We want to monitor the network and identify losses early."
)


@pytest.fixture
def officer_token(txn_client, demo_password: str) -> str:
    return login(txn_client, "officer@mahagov.in", demo_password)


def department_id(db, code: str = "WSSD") -> int:
    return db.scalars(select(Department).where(Department.code == code)).one().id


# ---------------------------------------------------------------------------
# The analyzer never invents a constraint
# ---------------------------------------------------------------------------


def test_missing_budget_and_timeline_are_reported_not_invented() -> None:
    """The exit criterion: nothing gets filled in on the department's behalf."""
    outcome = analyzer.analyze(WATER_PROBLEM)

    assert outcome.result.budget is None
    assert outcome.result.timeline is None
    assert outcome.result.location is None
    assert "budget" in outcome.result.missing_fields
    assert "timeline" in outcome.result.missing_fields
    assert "location" in outcome.result.missing_fields


def test_supplied_fields_are_echoed_back_unchanged() -> None:
    outcome = analyzer.analyze(
        WATER_PROBLEM,
        budget=Decimal("4200000"),
        timeline="6 months",
        location="Nashik",
    )
    assert outcome.result.budget == Decimal("4200000")
    assert outcome.result.timeline == "6 months"
    assert outcome.result.location == "Nashik"
    for field_name in ("budget", "timeline", "location"):
        assert field_name not in outcome.result.missing_fields


def test_the_analyzer_produces_measurable_kpis_with_a_direction() -> None:
    outcome = analyzer.analyze(WATER_PROBLEM)
    assert outcome.result.suggested_kpis
    for kpi in outcome.result.suggested_kpis:
        assert kpi.name
        assert kpi.unit
        assert kpi.measurement_method
        assert isinstance(kpi.direction, KpiDirection)


def test_the_template_fallback_produces_schema_valid_output_with_no_key() -> None:
    """The exit criterion: the demo works offline."""
    assert not llm.is_configured(), "this suite expects no LLM key in the environment"

    outcome = analyzer.analyze(WATER_PROBLEM)
    assert outcome.source == "template"
    # model_validate on its own output proves it satisfies the strict schema.
    analyzer.AnalysisResult.model_validate(outcome.result.model_dump())
    assert "template" in " ".join(outcome.notes).lower()


def test_the_template_never_invents_a_target_value() -> None:
    """It proposes what to measure, not how much - the officer supplies numbers."""
    outcome = analyzer.analyze(WATER_PROBLEM)
    assert outcome.source == "template"
    assert all(kpi.target_value is None for kpi in outcome.result.suggested_kpis)
    assert analyzer.MISSING_KPI_TARGETS in outcome.result.missing_fields


def test_the_template_is_deterministic() -> None:
    first = analyzer.analyze(WATER_PROBLEM)
    second = analyzer.analyze(WATER_PROBLEM)
    assert first.result.model_dump() == second.result.model_dump()


def test_the_template_reads_the_departments_own_words() -> None:
    """Capabilities are drawn from the text, not from a fixed list."""
    detection = analyzer.analyze("We need to detect illegal dumping in the ward.")
    scheduling = analyzer.analyze("We need to schedule and route the collection fleet.")
    assert detection.result.required_capabilities != scheduling.result.required_capabilities


def test_the_analyze_endpoint_reports_missing_fields(txn_client, officer_token: str) -> None:
    response = txn_client.post(
        "/challenges/analyze",
        json={"description": WATER_PROBLEM},
        headers=auth_header(officer_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["budget"] is None
    assert {"budget", "timeline", "location"} <= set(body["missing_fields"])


def test_the_analyze_endpoint_is_closed_to_startups(txn_client, demo_password: str) -> None:
    token = login(txn_client, "founder@startup.in", demo_password)
    response = txn_client.post(
        "/challenges/analyze",
        json={"description": WATER_PROBLEM},
        headers=auth_header(token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Publishing is blocked while anything is missing
# ---------------------------------------------------------------------------


def create_draft(client, token: str, db, **overrides) -> dict:
    payload = {
        "title": "Reduce water losses in the distribution network",
        "description": WATER_PROBLEM,
        "department_id": department_id(db),
        "category": "WATER",
    }
    payload.update(overrides)
    response = client.post("/challenges", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def test_a_new_draft_records_what_is_missing(txn_client, txn_db, officer_token: str) -> None:
    draft = create_draft(txn_client, officer_token, txn_db)
    assert draft["value"] is None
    assert {"budget", "timeline", "location"} <= set(draft["missing_fields"])
    assert draft["status"] == ChallengeStatus.ANALYZED.value


def test_publishing_is_blocked_while_fields_are_missing(
    txn_client, txn_db, officer_token: str
) -> None:
    """The exit criterion."""
    draft = create_draft(txn_client, officer_token, txn_db)
    response = txn_client.post(
        f"/challenges/{draft['id']}/publish", headers=auth_header(officer_token)
    )
    assert response.status_code == 409
    assert "budget" in response.json()["detail"]["missing_fields"]


def test_approval_is_blocked_while_the_department_fields_are_missing(
    txn_client, txn_db, officer_token: str
) -> None:
    draft = create_draft(txn_client, officer_token, txn_db)
    response = txn_client.post(
        f"/challenges/{draft['id']}/approve",
        json={
            "kpis": [
                {
                    "name": "Leak detection accuracy",
                    "target_value": "85",
                    "unit": "percent",
                    "measurement_method": "Excavation results against flagged locations",
                    "direction": "HIGHER_IS_BETTER",
                }
            ],
            "note": "Approving the spec.",
        },
        headers=auth_header(officer_token),
    )
    assert response.status_code == 409
    assert "budget" in response.json()["detail"]["missing_fields"]


def filled_draft(client, token: str, db) -> dict:
    """A draft with everything the department owns supplied."""
    draft = create_draft(client, token, db)
    response = client.patch(
        f"/challenges/{draft['id']}",
        json={
            "budget": "4200000",
            "timeline": "6 months",
            "district": "Nashik",
            "criticality": "MEDIUM",
            "innovation_potential": "HIGH",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_filling_the_gaps_clears_missing_fields(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = filled_draft(txn_client, officer_token, txn_db)
    assert challenge["missing_fields"] == []


KPI_PAYLOAD = {
    "kpis": [
        {
            "name": "Leak localisation accuracy",
            "target_value": "85",
            "unit": "percent",
            "measurement_method": "Excavation results against flagged locations",
            "direction": "HIGHER_IS_BETTER",
        },
        {
            "name": "Time to locate a reported burst",
            "target_value": "12",
            "unit": "hours",
            "measurement_method": "Report timestamp to field confirmation",
            "direction": "LOWER_IS_BETTER",
        },
    ],
    "note": "KPIs agreed with the executive engineer.",
}


def approved_challenge(client, token: str, db) -> dict:
    challenge = filled_draft(client, token, db)
    response = client.post(
        f"/challenges/{challenge['id']}/approve",
        json=KPI_PAYLOAD,
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# KPIs lock at approval
# ---------------------------------------------------------------------------


def test_approval_locks_the_kpis(txn_client, txn_db, officer_token: str) -> None:
    challenge = approved_challenge(txn_client, officer_token, txn_db)
    assert challenge["kpis_locked"] is True
    assert challenge["status"] == ChallengeStatus.APPROVED.value
    assert len(challenge["kpis"]) == 2
    assert {kpi["direction"] for kpi in challenge["kpis"]} == {
        "HIGHER_IS_BETTER",
        "LOWER_IS_BETTER",
    }


def test_kpis_cannot_be_modified_after_approval(
    txn_client, txn_db, officer_token: str
) -> None:
    """The exit criterion: locked means locked."""
    challenge = approved_challenge(txn_client, officer_token, txn_db)

    again = txn_client.post(
        f"/challenges/{challenge['id']}/approve",
        json=KPI_PAYLOAD,
        headers=auth_header(officer_token),
    )
    assert again.status_code == 409
    assert "locked" in again.json()["detail"]

    added = txn_client.post(
        f"/challenges/{challenge['id']}/kpis", headers=auth_header(officer_token)
    )
    assert added.status_code == 409
    assert "locked" in added.json()["detail"]


def test_kpis_cannot_be_modified_after_publication(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = approved_challenge(txn_client, officer_token, txn_db)
    published = txn_client.post(
        f"/challenges/{challenge['id']}/publish", headers=auth_header(officer_token)
    )
    assert published.status_code == 200, published.text

    stored = txn_db.get(Challenge, challenge["id"])
    txn_db.refresh(stored)
    assert stored.kpis_locked is True

    response = txn_client.post(
        f"/challenges/{challenge['id']}/approve",
        json=KPI_PAYLOAD,
        headers=auth_header(officer_token),
    )
    assert response.status_code == 409


def test_an_approved_challenge_can_no_longer_be_edited(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = approved_challenge(txn_client, officer_token, txn_db)
    response = txn_client.patch(
        f"/challenges/{challenge['id']}",
        json={"budget": "999"},
        headers=auth_header(officer_token),
    )
    assert response.status_code == 409


def test_publishing_classifies_the_tier_and_opens_the_bid_window(
    txn_client, txn_db, officer_token: str
) -> None:
    challenge = approved_challenge(txn_client, officer_token, txn_db)
    response = txn_client.post(
        f"/challenges/{challenge['id']}/publish", headers=auth_header(officer_token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # 42,00,000 with MEDIUM criticality and HIGH innovation: SMALL band, no
    # escalation, innovation cannot go below SMALL.
    assert body["tier"] == "SMALL"
    assert body["tier_explanation"]
    assert body["status"] == ChallengeStatus.PUBLISHED.value
    assert body["published_at"] and body["bid_closes_at"]


def test_publishing_requires_approval_first(txn_client, txn_db, officer_token: str) -> None:
    challenge = filled_draft(txn_client, officer_token, txn_db)
    response = txn_client.post(
        f"/challenges/{challenge['id']}/publish", headers=auth_header(officer_token)
    )
    assert response.status_code == 409
    assert "Approve the challenge first" in response.json()["detail"]


def test_a_startup_cannot_see_an_unpublished_challenge(
    txn_client, txn_db, officer_token: str, demo_password: str
) -> None:
    draft = create_draft(txn_client, officer_token, txn_db)
    startup = login(txn_client, "founder@startup.in", demo_password)
    assert (
        txn_client.get(f"/challenges/{draft['id']}", headers=auth_header(startup)).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


needs_embeddings = pytest.mark.skipif(
    not embeddings.is_available(),
    reason=f"embedding model unavailable: {embeddings.status().error}",
)


@needs_embeddings
def test_a_differently_worded_problem_finds_the_past_pilot(txn_db) -> None:
    """The exit criterion, and the point of using embeddings at all.

    The seeded pilot is called "Reduce non-revenue water losses in Nashik zone 3".
    The query below shares almost no vocabulary with it.
    """
    result = knowledge.search(
        txn_db,
        "treated water disappearing from the pipeline network before it reaches homes",
        limit=3,
    )
    assert result.semantic is True
    titles = [match.title for match in result.matches]
    assert any("non-revenue water" in title.lower() for title in titles), titles


@needs_embeddings
def test_knowledge_matches_carry_outcome_cost_and_lessons(txn_db) -> None:
    result = knowledge.search(txn_db, "water leakage detection in a city network", limit=1)
    match = result.matches[0]
    assert match.outcome in {"SCALE", "MODIFY", "REJECT"}
    assert match.cost is not None
    assert match.lessons_learned
    assert match.validated_kpis


@needs_embeddings
def test_knowledge_search_ranks_the_closest_pilot_first(txn_db) -> None:
    result = knowledge.search(
        txn_db, "crop disease early warning for grape growers", limit=8
    )
    assert "grape" in result.matches[0].title.lower()


@needs_embeddings
def test_the_knowledge_endpoint_is_available_at_draft_time(
    txn_client, officer_token: str
) -> None:
    response = txn_client.post(
        "/challenges/knowledge-search",
        json={"description": "pipeline water losses we cannot locate"},
        headers=auth_header(officer_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["semantic"] is True
    assert body["matches"]
    assert body["matches"][0]["similarity"] > 0


def test_knowledge_search_degrades_honestly_without_the_model(txn_db) -> None:
    """With no model it reports that, rather than returning silent nonsense."""
    result = knowledge.search(txn_db, "anything at all")
    if embeddings.is_available():
        assert result.semantic is True
    else:
        assert result.semantic is False
        assert result.matches == []
        assert "unavailable" in result.note


def test_ai_status_endpoint_is_honest(client) -> None:
    body = client.get("/ai-status").json()
    assert body["llm"]["configured"] is False
    assert "template" in body["llm"]["fallback"].lower()
    assert body["embeddings"]["model"] == "all-MiniLM-L6-v2"
