"""
Value-level parity: schemas built from real rows must equal Spring's JSON.

`test_contract_parity.py` proves the *field names* line up. This suite goes
further and proves the *values* do: it loads the same database rows Spring
served when `tests/fixtures/spring_contract.json` was captured, builds the
Pydantic response, and diffs it against the recorded JSON key by key.

That is what catches encoding drift a name-level check cannot see — a score
serialised as `"79.086"` instead of `79.086`, a timestamp as `+00:00` instead
of `Z`, an enum as `RoleName.ADMIN` instead of `ADMIN`, or a tri-state
`success` flattened to `false`.

Requires PostgreSQL; skips cleanly without it. Read-only.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal, check_connection

FIXTURE_FILE = Path(__file__).parent / "fixtures" / "spring_contract.json"

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="PostgreSQL is not reachable; start it on :5433.",
)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def fixture() -> dict:
    assert FIXTURE_FILE.exists(), (
        f"{FIXTURE_FILE} is missing. Regenerate with "
        "tests/capture_spring_contract.py while the Spring backend runs.")
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


def dump(model) -> dict:
    """Serialise exactly as FastAPI will: by alias, JSON mode."""
    return json.loads(model.model_dump_json(by_alias=True))


def assert_matches(actual: dict, expected: dict, *, label: str,
                   ignore: set[str] = frozenset()) -> None:
    """Compare two response bodies key by key, reporting every difference."""
    assert set(actual) == set(expected), (
        f"{label}: key mismatch — "
        f"only python: {sorted(set(actual) - set(expected))}, "
        f"only spring: {sorted(set(expected) - set(actual))}"
    )
    differences = [
        f"    {key}: python={actual[key]!r} spring={expected[key]!r}"
        for key in expected
        if key not in ignore and actual[key] != expected[key]
    ]
    assert not differences, f"{label}: value mismatch\n" + "\n".join(differences)


# ---------------------------------------------------------------------------

class TestChallengeParity:
    def test_challenge_detail_matches_spring(self, db, fixture):
        from app.models import Challenge
        from app.schemas import ChallengeResponse

        expected = fixture["challenge_detail"]["body"]
        challenge = db.get(Challenge, uuid.UUID(expected["id"]))
        assert challenge is not None, "the captured challenge is gone from the database"

        actual = dump(ChallengeResponse.from_entity(challenge))
        # Nested collections are compared separately: Spring's ordering comes
        # from its own query, and order is not part of the contract.
        assert_matches(actual, expected, label="Challenge",
                       ignore={"requirements", "kpis"})

        assert len(actual["requirements"]) == len(expected["requirements"])
        by_id = {r["id"]: r for r in expected["requirements"]}
        for requirement in actual["requirements"]:
            assert_matches(requirement, by_id[requirement["id"]], label="requirement")

        assert len(actual["kpis"]) == len(expected["kpis"])
        by_id = {k["id"]: k for k in expected["kpis"]}
        for kpi in actual["kpis"]:
            assert_matches(kpi, by_id[kpi["id"]], label="kpi")


class TestStartupParity:
    def test_startup_detail_matches_spring(self, db, fixture):
        from app.models import Startup
        from app.schemas import StartupResponse

        expected = fixture["startup_detail"]["body"]
        startup = db.get(Startup, uuid.UUID(expected["id"]))
        assert startup is not None

        actual = dump(StartupResponse.from_entity(startup))
        assert_matches(actual, expected, label="Startup",
                       ignore={"capabilities", "projects"})

        by_id = {c["id"]: c for c in expected["capabilities"]}
        assert len(actual["capabilities"]) == len(by_id)
        for capability in actual["capabilities"]:
            assert_matches(capability, by_id[capability["id"]], label="capability")

        by_id = {p["id"]: p for p in expected["projects"]}
        assert len(actual["projects"]) == len(by_id)
        for project in actual["projects"]:
            assert_matches(project, by_id[project["id"]], label="project")

    def test_readiness_score_is_a_number_not_a_decimal_string(self, db, fixture):
        from app.models import Startup
        from app.schemas import StartupResponse

        startup = db.get(Startup, uuid.UUID(fixture["startup_detail"]["body"]["id"]))
        payload = dump(StartupResponse.from_entity(startup))
        assert isinstance(payload["readinessScore"], float)


class TestMatchingParity:
    def test_match_result_rows_match_spring(self, db, fixture):
        from app.models import MatchResult
        from app.schemas import MatchResultRow

        expected_rows = fixture["matching_results"]["body"]
        if not expected_rows:
            pytest.skip("no match results captured")

        challenge_id = uuid.UUID(
            fixture["matching_results"]["path"].rsplit("/", 1)[-1])
        rows = db.execute(
            select(MatchResult)
            .where(MatchResult.challenge_id == challenge_id)
            .order_by(MatchResult.rank)
        ).scalars().all()
        assert len(rows) == len(expected_rows)

        by_startup = {r["startupId"]: r for r in expected_rows}
        for row in rows:
            actual = dump(MatchResultRow.from_entity(row))
            assert_matches(actual, by_startup[str(row.startup_id)],
                           label=f"MatchResultRow rank {row.rank}")

    def test_roadsense_still_ranks_first_with_real_scores(self, db, fixture):
        """
        The demo's headline claim, asserted against stored pipeline output.

        Nothing here recomputes a score — it reads what the real AI pipeline
        persisted, which is the point.
        """
        expected_rows = fixture["matching_results"]["body"]
        if not expected_rows:
            pytest.skip("no match results captured")
        top = min(expected_rows, key=lambda r: r["rank"])
        assert top["rank"] == 1
        assert top["companyName"] == "RoadSense AI"
        assert 0 < top["overallScore"] <= 100
        assert top["reasons"], "the top match has no explanation"


class TestPilotParity:
    def test_pilot_detail_matches_spring(self, db, fixture):
        from app.models import Pilot
        from app.schemas import PilotResponse

        expected = fixture["pilot_detail"]["body"]
        pilot = db.get(Pilot, uuid.UUID(expected["id"]))
        assert pilot is not None

        actual = dump(PilotResponse.from_entity(pilot))
        assert_matches(actual, expected, label="Pilot",
                       ignore={"milestones", "kpis", "contract"})

        by_id = {m["id"]: m for m in expected["milestones"]}
        for milestone in actual["milestones"]:
            assert_matches(milestone, by_id[milestone["id"]], label="milestone")

        by_id = {k["id"]: k for k in expected["kpis"]}
        for kpi in actual["kpis"]:
            assert_matches(kpi, by_id[kpi["id"]], label="kpi")

        if expected["contract"] is None:
            assert actual["contract"] is None
        else:
            assert_matches(actual["contract"], expected["contract"], label="contract")

    def test_latest_kpi_result_is_read_from_the_append_only_history(self, db, fixture):
        """`latestRecordedValue` must be the newest row, not the first."""
        from app.models import Pilot
        from app.schemas import PilotResponse

        pilot = db.get(Pilot, uuid.UUID(fixture["pilot_detail"]["body"]["id"]))
        payload = dump(PilotResponse.from_entity(pilot))
        by_id = {k["id"]: k for k in fixture["pilot_detail"]["body"]["kpis"]}
        for kpi in payload["kpis"]:
            assert kpi["latestRecordedValue"] == by_id[kpi["id"]]["latestRecordedValue"]

    def test_recommendation_matches_spring(self, db, fixture):
        from app.models import Recommendation
        from app.schemas import RecommendationResponse

        expected = fixture["pilot_recommendation"]["body"]
        recommendation = db.get(Recommendation, uuid.UUID(expected["id"]))
        assert recommendation is not None
        assert_matches(dump(RecommendationResponse.from_entity(recommendation)),
                       expected, label="Recommendation")

    def test_system_recommendation_and_human_decision_stay_separate(self, db, fixture):
        from app.models import Recommendation
        from app.schemas import RecommendationResponse

        expected = fixture["pilot_recommendation"]["body"]
        payload = dump(RecommendationResponse.from_entity(
            db.get(Recommendation, uuid.UUID(expected["id"]))))
        assert "recommendation" in payload and "finalDecision" in payload
        assert payload["recommendation"] == expected["recommendation"]
        assert payload["finalDecision"] == expected["finalDecision"]


class TestKnowledgeBaseParity:
    def test_entries_match_spring(self, db, fixture):
        from app.models import PilotKnowledgeBase
        from app.schemas import KnowledgeBaseEntryResponse

        expected_rows = fixture["knowledge_base"]["body"]
        if not expected_rows:
            pytest.skip("knowledge base is empty")
        by_id = {r["id"]: r for r in expected_rows}
        entries = db.execute(select(PilotKnowledgeBase)).scalars().all()
        for entry in entries:
            expected = by_id.get(str(entry.id))
            if expected is None:
                continue
            assert_matches(dump(KnowledgeBaseEntryResponse.from_entity(entry)),
                           expected, label="KnowledgeBaseEntry")

    def test_success_is_not_coerced_to_bool(self, db):
        """MODIFY pilots must stay `null`, never `false`."""
        from app.models import PilotKnowledgeBase
        from app.schemas import KnowledgeBaseEntryResponse

        for entry in db.execute(select(PilotKnowledgeBase)).scalars():
            payload = dump(KnowledgeBaseEntryResponse.from_entity(entry))
            assert payload["success"] is entry.success


class TestSimpleParity:
    def test_notifications_match_spring(self, db, fixture):
        from app.models import Notification
        from app.schemas import NotificationResponse

        expected_rows = fixture["notifications"]["body"]
        if not expected_rows:
            pytest.skip("no notifications captured")
        by_id = {r["id"]: r for r in expected_rows}
        for notification in db.execute(select(Notification)).scalars():
            expected = by_id.get(str(notification.id))
            if expected is None:
                continue
            assert_matches(dump(NotificationResponse.from_entity(notification)),
                           expected, label="NotificationItem")

    def test_admin_users_match_spring(self, db, fixture):
        from app.models import User
        from app.schemas import AdminUserResponse

        by_id = {r["id"]: r for r in fixture["admin_users"]["body"]}
        for user in db.execute(select(User)).scalars():
            expected = by_id.get(str(user.id))
            if expected is None:
                continue
            assert_matches(dump(AdminUserResponse.from_entity(user)),
                           expected, label="AdminUser")

    def test_proposals_match_spring(self, db, fixture):
        from app.models import Proposal
        from app.schemas import ProposalResponse

        expected = fixture["proposal_detail"]["body"]
        proposal = db.get(Proposal, uuid.UUID(expected["id"]))
        assert proposal is not None
        assert_matches(dump(ProposalResponse.from_entity(proposal)),
                       expected, label="Proposal")

    def test_evaluation_criteria_match_spring(self, db, fixture):
        from app.models import EvaluationCriterion
        from app.schemas import EvaluationCriterionResponse

        expected_rows = fixture["evaluation_criteria"]["body"]
        if not expected_rows:
            pytest.skip("no criteria captured")
        by_id = {r["id"]: r for r in expected_rows}
        for criterion_id, expected in by_id.items():
            criterion = db.get(EvaluationCriterion, uuid.UUID(criterion_id))
            assert criterion is not None
            assert_matches(
                dump(EvaluationCriterionResponse.model_validate(criterion)),
                expected, label="EvaluationCriterionItem")


class TestPageValueParity:
    def test_audit_log_page_matches_spring(self, db, fixture):
        """
        Rebuild the captured audit-log page and compare the envelope.

        `content` is excluded: `audit_logs` grows with every login, so the rows
        on page 0 legitimately differ from the capture. The envelope arithmetic
        is what this asserts.
        """
        from app.schemas import Page
        from app.schemas.system import AuditLogResponse

        expected = fixture["admin_audit_logs"]["body"]
        page = Page[AuditLogResponse].create(
            [], page=expected["number"], size=expected["size"],
            total=expected["totalElements"])
        actual = dump(page)

        assert set(actual) == set(expected)
        for key in ("totalElements", "totalPages", "number", "size", "first", "last"):
            assert actual[key] == expected[key], f"{key}"
        assert set(actual["pageable"]) == set(expected["pageable"])
        assert set(actual["sort"]) == set(expected["sort"])
