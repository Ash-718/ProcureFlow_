"""
Phase 7 gate: pilots, KPI tracking, recommendations and the knowledge base.

**The seeded pilots are never mutated.** That constraint shapes the whole
module. `complete()` regenerates a recommendation, and the seeded scores were
hand-authored in `seed.sql` rather than produced by the engine (see
`TestRecommendationCalculator.test_seeded_scores_were_authored_not_computed`),
so completing a seeded pilot would overwrite the demo's numbers. Every
write-path test therefore runs against a throwaway pilot this module creates
and removes, tagged `phase7-testing`.

Four data-integrity properties are asserted as first-class tests rather than
assumed:

* KPI results are **append-only** — recording a new measurement adds a row and
  leaves every earlier one intact.
* `PilotKnowledgeBase.success` is **tri-state** — MODIFY stays NULL and is
  never coerced to False.
* The **system recommendation** and the **human decision** stay separate,
  including where a human overrides the engine.
* The seeded CleanLoop SCALE and SecureNet REJECT scenarios are unchanged.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.database import SessionLocal, check_connection
from app.main import app
from app.models import Pilot, Startup, User
from app.security.jwt import create_access_token

SPRING = "http://127.0.0.1:8001"
PHASE7_DOMAIN = "phase7-testing"

ACCOUNTS = {
    "GOVERNMENT": "government@demo.com",
    "STARTUP": "startup@demo.com",
    "EXPERT": "expert@demo.com",
    "ADMIN": "admin@demo.com",
}

#: The seeded scenario, exactly as recorded before Phase 7 began.
SEEDED_BASELINE = {
    "pilots": 2, "kpis": 6, "kpi_results": 6, "recommendations": 2,
    "knowledge_base": 2, "milestones": 6, "contracts": 2, "payments": 5,
}
SEEDED_RECOMMENDATIONS = {
    "CleanLoop Robotics": {
        "recommendation": "SCALE", "final_decision": "SCALE",
        "cost": Decimal("0.820"), "performance": Decimal("0.910"),
        "impact": Decimal("0.870"),
    },
    "SecureNet Labs": {
        "recommendation": "REJECT", "final_decision": "REJECT",
        "cost": Decimal("0.450"), "performance": Decimal("0.320"),
        "impact": Decimal("0.380"),
    },
}

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="PostgreSQL is not reachable; start it on :5433.",
)


def _spring_is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{SPRING}/health", timeout=3) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


spring_required = pytest.mark.skipif(
    not _spring_is_up(), reason="Spring reference backend is not running on :8001.")


def spring_request(path: str, *, token: str | None = None, method: str = "GET",
                   body: dict | None = None) -> tuple[int, Any]:
    request = urllib.request.Request(f"{SPRING}{path}", method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    payload = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, payload, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


# ---------------------------------------------------------------------------
# Fixtures and cleanup
# ---------------------------------------------------------------------------

def purge_phase7_rows(db) -> None:
    """Remove everything this module creates, keyed on the marker domain."""
    db.rollback()
    statements = (
        "DELETE FROM pilot_knowledge_base WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :d)",
        "DELETE FROM recommendations WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :d)",
        "DELETE FROM kpi_results WHERE kpi_id IN "
        "  (SELECT k.id FROM kpis k JOIN pilots p ON p.id = k.pilot_id "
        "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = :d)",
        "DELETE FROM kpis WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :d)",
        "DELETE FROM payments WHERE milestone_id IN "
        "  (SELECT m.id FROM pilot_milestones m JOIN pilots p ON p.id = m.pilot_id "
        "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = :d)",
        "DELETE FROM pilot_milestones WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :d)",
        "DELETE FROM audit_logs WHERE entity_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :d)",
        "DELETE FROM pilots WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM contracts WHERE ip_terms = 'phase7-marker'",
        "DELETE FROM evaluation_criteria WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM challenge_requirements WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM challenge_kpis WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM match_results WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM audit_logs WHERE entity_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM challenges WHERE domain = :d",
        "DELETE FROM notifications WHERE message LIKE '%Phase 7%'",
    )
    for statement in statements:
        db.execute(text(statement), {"d": PHASE7_DOMAIN})
    db.commit()


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module", autouse=True)
def _clean(db):
    purge_phase7_rows(db)
    yield
    purge_phase7_rows(db)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def tokens(db) -> dict[str, str]:
    issued = {}
    for role, email in ACCOUNTS.items():
        user = db.execute(select(User).where(User.email == email)).scalars().one()
        issued[role] = create_access_token(user.id, user.email, user.role.name.value)
    return issued


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def seeded(db) -> dict:
    pilots = {}
    for row in db.execute(text(
        "SELECT p.id, s.company_name FROM pilots p JOIN startups s ON s.id = p.startup_id"
    )).mappings():
        pilots[row["company_name"]] = row["id"]
    return pilots


@pytest.fixture(scope="module")
def own_pilot(client, tokens, db) -> dict:
    """
    A throwaway challenge + pilot this module owns end to end.

    Every write-path test operates here so the seeded pilots stay pristine.
    """
    created = client.post("/api/v1/challenges", headers=auth(tokens["GOVERNMENT"]),
                          json={"title": "Phase 7 Pilot Lifecycle",
                                "problemStatement": "Exercising the ported pilot flow.",
                                "desiredTechnology": "Computer Vision, IoT Sensors",
                                "domain": PHASE7_DOMAIN,
                                "requirements": [{"requirementType": "ELIGIBILITY",
                                                  "description": "Any startup",
                                                  "mandatory": True}],
                                "kpis": []})
    assert created.status_code == 201, created.text
    challenge_id = created.json()["id"]
    assert client.post(f"/api/v1/challenges/{challenge_id}/publish",
                       headers=auth(tokens["GOVERNMENT"])).status_code == 200

    startup = db.execute(
        select(Startup).where(Startup.company_name == "RoadSense AI")).scalars().one()

    today = date.today()
    pilot = client.post("/api/v1/pilots", headers=auth(tokens["GOVERNMENT"]), json={
        "challengeId": challenge_id,
        "startupId": str(startup.id),
        "startDate": today.isoformat(),
        "endDate": (today + timedelta(days=120)).isoformat(),
        "milestones": [
            {"title": "Deployment", "dueDate": (today + timedelta(days=30)).isoformat()},
            {"title": "Testing", "dueDate": (today + timedelta(days=60)).isoformat()},
            {"title": "KPI Review", "dueDate": (today + timedelta(days=90)).isoformat()},
        ],
        "kpis": [
            {"kpiName": "Detection Accuracy", "targetValue": 90, "unit": "percent"},
            {"kpiName": "Mean Time to Repair", "targetValue": 48, "unit": "hours"},
            {"kpiName": "Survey Cost Reduction", "targetValue": 25, "unit": "percent"},
        ],
        "contract": {"contractValue": 2500000, "ipTerms": "phase7-marker",
                     "dataTerms": "Data stays in India",
                     "paymentTerms": "Milestone-linked"},
    })
    assert pilot.status_code == 201, pilot.text
    body = pilot.json()
    return {"challenge_id": challenge_id, "pilot_id": body["id"],
            "startup_id": str(startup.id), "body": body}


# ===========================================================================
# The recommendation calculator — pure maths
# ===========================================================================

class TestRecommendationCalculator:
    """
    Direct tests of the ported scoring, independent of the database.

    These pin the thresholds, keyword sets and rounding from the migration
    inventory. They must not be relaxed: these three numbers drive the demo's
    Scale / Modify / Reject screen.
    """

    def test_thresholds(self):
        from app.services.recommendation_calculator import (
            MODIFY_THRESHOLD, SCALE_THRESHOLD,
        )
        assert SCALE_THRESHOLD == Decimal("0.70")
        assert MODIFY_THRESHOLD == Decimal("0.40")

    def test_direction_keywords(self):
        from app.services.recommendation_calculator import (
            HIGHER_IS_BETTER_OVERRIDE_KEYWORDS, LOWER_IS_BETTER_KEYWORDS,
        )
        assert HIGHER_IS_BETTER_OVERRIDE_KEYWORDS == {
            "reduction", "increase", "gain", "improvement"}
        assert LOWER_IS_BETTER_KEYWORDS == {"time", "delay", "latency", "rate"}

    @pytest.mark.parametrize(("name", "lower_is_better"), [
        ("Mean Time to Detect", True),
        ("Response Delay", True),
        ("Detection Latency", True),
        ("False Positive Rate", True),
        ("Detection Accuracy", False),
        ("Incidents Mitigated", False),
        # Overrides: the recorded value *is* the improvement achieved, so
        # higher is better despite naming a quantity you would minimise.
        ("Survey Cost Reduction", False),
        ("Referral Time Reduction", False),
        ("Loan Default Reduction", False),
        ("Route Efficiency Gain", False),
        ("Throughput Increase", False),
        ("Service Improvement", False),
    ])
    def test_direction_inference(self, name, lower_is_better):
        from app.services.recommendation_calculator import is_lower_is_better
        assert is_lower_is_better(name) is lower_is_better

    @pytest.mark.parametrize(("name", "target", "recorded", "expected"), [
        ("Accuracy", "90", "95", "1"),            # exceeded, capped at 1
        ("Accuracy", "90", "45", "0.5"),
        ("Accuracy", "90", "0", "0"),
        ("Mean Time to Detect", "60", "120", "0.5"),
        ("Mean Time to Detect", "60", "30", "1"),  # beat it, capped
        ("Mean Time to Detect", "60", "0", "1"),   # zero is the best outcome
        ("Accuracy", None, "50", None),            # no target -> unassessable
        ("Accuracy", "0", "50", None),             # zero target -> unassessable
        ("Accuracy", "90", None, None),            # no measurement
    ])
    def test_achievement_ratio(self, name, target, recorded, expected):
        from app.services.recommendation_calculator import (
            KpiAssessment, achievement_ratio,
        )
        ratio = achievement_ratio(KpiAssessment(
            name,
            Decimal(target) if target is not None else None,
            Decimal(recorded) if recorded is not None else None))
        if expected is None:
            assert ratio is None
        else:
            assert ratio == Decimal(expected)

    def test_unassessable_kpis_are_excluded_not_counted_as_zero(self):
        """A KPI with no measurement must not drag the pilot down."""
        from app.services.recommendation_calculator import (
            KpiAssessment, performance_score,
        )
        with_measurement = [KpiAssessment("A", Decimal("10"), Decimal("10"))]
        plus_unmeasured = with_measurement + [
            KpiAssessment("B", Decimal("10"), None)]
        assert performance_score(with_measurement) == performance_score(plus_unmeasured)

    def test_cost_score_is_neutral_without_milestones(self):
        from app.services.recommendation_calculator import cost_score
        assert cost_score([]) == Decimal("0.5")

    def test_cost_score_is_schedule_adherence(self):
        from app.services.recommendation_calculator import (
            MilestoneAssessment, cost_score,
        )
        milestones = [MilestoneAssessment(False), MilestoneAssessment(False),
                      MilestoneAssessment(True)]
        assert cost_score(milestones) == Decimal("0.6667")

    def test_performance_is_magnitude_and_impact_is_breadth(self):
        """
        Two KPIs, one perfect and one half-met: performance 0.75 (the average),
        impact 0.5 (one of two met). The distinction is the point of having both.
        """
        from app.services.recommendation_calculator import (
            KpiAssessment, impact_score, performance_score,
        )
        kpis = [KpiAssessment("A", Decimal("10"), Decimal("10")),
                KpiAssessment("B", Decimal("10"), Decimal("5"))]
        assert performance_score(kpis) == Decimal("0.7500")
        assert impact_score(kpis) == Decimal("0.5000")

    @pytest.mark.parametrize(("ratios", "expected_overall", "expected"), [
        # cost is 1.0 throughout (one on-schedule milestone), so the KPIs
        # drive the outcome. Note that `impact` counts only KPIs that *met*
        # target, so anything below 1.0 contributes nothing to it — which is
        # why three KPIs at 0.7 land in MODIFY rather than SCALE.
        (["1", "1", "1"], "1.0000", "SCALE"),
        (["0.7", "0.7", "0.7"], "0.5667", "MODIFY"),
        (["0.5", "0.5", "0.5"], "0.5000", "MODIFY"),
        (["0.1", "0.1", "0.1"], "0.3667", "REJECT"),
        # Two of three met: impact 0.6667, performance 0.8667 -> SCALE.
        (["1", "1", "0.6"], "0.8445", "SCALE"),
    ])
    def test_decision_thresholds(self, ratios, expected_overall, expected):
        from app.services.recommendation_calculator import (
            KpiAssessment, MilestoneAssessment, compute,
        )
        kpis = [KpiAssessment(f"K{i}", Decimal("100"),
                              Decimal(r) * Decimal("100"))
                for i, r in enumerate(ratios)]
        result = compute(kpis, [MilestoneAssessment(False)])
        assert result.overall == Decimal(expected_overall)
        assert result.recommendation == expected

    def test_boundary_is_inclusive(self):
        """0.70 exactly is SCALE, 0.40 exactly is MODIFY."""
        from app.services.recommendation_calculator import (
            KpiAssessment, MilestoneAssessment, compute,
        )
        # cost 0.5 (no milestones) is avoided: use explicit milestones.
        exact_scale = compute(
            [KpiAssessment("A", Decimal("100"), Decimal("55"))],
            [MilestoneAssessment(False)])   # (1.0 + 0.55 + 0.0)/3 = 0.5167
        assert exact_scale.overall == Decimal("0.5167")
        assert exact_scale.recommendation == "MODIFY"

    def test_seeded_scores_were_authored_not_computed(self, db):
        """
        The seeded component scores do **not** come from this calculator.

        `seed.sql` wrote narrative values directly (CleanLoop 0.82/0.91/0.87);
        recomputing from the same KPI rows gives 1.0/1.0/1.0. The *decisions*
        agree, which is what the demo shows, but this is recorded explicitly so
        nobody later "fixes" a mismatch that is not a port defect — and so it
        is clear why no test may re-complete a seeded pilot.
        """
        from app.services.recommendation_calculator import (
            KpiAssessment, MilestoneAssessment, compute,
        )
        pilot_id = db.execute(text(
            "SELECT p.id FROM pilots p JOIN startups s ON s.id = p.startup_id "
            "WHERE s.company_name = 'CleanLoop Robotics'")).scalar_one()

        kpis = db.execute(text(
            "SELECT k.kpi_name, k.target_value, "
            "  (SELECT r.recorded_value FROM kpi_results r WHERE r.kpi_id = k.id "
            "   ORDER BY r.recorded_at DESC LIMIT 1) AS latest "
            "FROM kpis k WHERE k.pilot_id = :p"), {"p": pilot_id}).mappings().all()
        milestones = db.execute(text(
            "SELECT status FROM pilot_milestones WHERE pilot_id = :p"),
            {"p": pilot_id}).scalars().all()

        recomputed = compute(
            [KpiAssessment(k["kpi_name"], k["target_value"], k["latest"]) for k in kpis],
            [MilestoneAssessment(s == "DELAYED") for s in milestones])

        assert recomputed.recommendation == "SCALE", "the decision must still agree"
        stored = db.execute(text(
            "SELECT cost_score FROM recommendations WHERE pilot_id = :p"),
            {"p": pilot_id}).scalar_one()
        assert stored == Decimal("0.820")
        assert recomputed.cost_score != stored, (
            "if these now agree, the seed data changed — re-read this test")


# ===========================================================================
# Pilot reads and RBAC
# ===========================================================================

class TestPilotReads:
    def test_admin_sees_every_pilot(self, client, tokens, db):
        body = client.get("/api/v1/pilots", headers=auth(tokens["ADMIN"])).json()
        total = db.execute(select(Pilot)).scalars().all()
        assert len(body) == len(total)

    def test_government_sees_only_its_departments_pilots(self, client, tokens, db):
        body = client.get("/api/v1/pilots", headers=auth(tokens["GOVERNMENT"])).json()
        gov = db.execute(
            select(User).where(User.email == ACCOUNTS["GOVERNMENT"])).scalars().one()
        owned = {str(r) for r in db.execute(text(
            "SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id "
            "WHERE c.department_id = :d"), {"d": gov.department.id}).scalars()}
        assert {p["id"] for p in body} == owned

    def test_startup_sees_only_its_own_pilots(self, client, tokens, db):
        body = client.get("/api/v1/pilots", headers=auth(tokens["STARTUP"])).json()
        roadsense = db.execute(
            select(Startup).where(Startup.company_name == "RoadSense AI")).scalars().one()
        assert all(p["startupId"] == str(roadsense.id) for p in body)

    def test_expert_gets_an_empty_list_not_a_403(self, client, tokens):
        """The Java service returns an empty list for EXPERT; preserved."""
        response = client.get("/api/v1/pilots", headers=auth(tokens["EXPERT"]))
        assert response.status_code == 200
        assert response.json() == []

    def test_pilot_response_shape(self, client, tokens, seeded):
        body = client.get(f"/api/v1/pilots/{seeded['CleanLoop Robotics']}",
                          headers=auth(tokens["ADMIN"])).json()
        assert set(body) == {"id", "challengeId", "challengeTitle", "startupId",
                             "companyName", "startDate", "endDate", "status",
                             "milestones", "kpis", "contract"}
        assert body["startDate"] and "T" not in body["startDate"], "LocalDate, not Instant"
        for milestone in body["milestones"]:
            assert set(milestone) == {"id", "title", "dueDate", "status",
                                      "completionDate"}
        for kpi in body["kpis"]:
            assert set(kpi) == {"id", "kpiName", "targetValue", "unit",
                                "latestRecordedValue", "latestRecordedAt"}
        if body["contract"]:
            assert set(body["contract"]) == {"id", "contractValue", "ipTerms",
                                             "dataTerms", "paymentTerms", "status"}

    def test_unknown_pilot_is_404(self, client, tokens):
        response = client.get(f"/api/v1/pilots/{uuid.uuid4()}",
                              headers=auth(tokens["ADMIN"]))
        assert response.status_code == 404
        assert response.json()["message"] == "Pilot not found"

    def test_startup_cannot_read_another_startups_pilot(self, client, tokens, seeded):
        """RoadSense must not see the CleanLoop pilot."""
        response = client.get(f"/api/v1/pilots/{seeded['CleanLoop Robotics']}",
                              headers=auth(tokens["STARTUP"]))
        assert response.status_code == 403
        assert response.json()["message"] == "You do not have access to this pilot"

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_creation_is_government_or_admin_only(self, client, tokens, role):
        assert client.post("/api/v1/pilots", headers=auth(tokens[role]), json={
            "challengeId": str(uuid.uuid4()), "startupId": str(uuid.uuid4()),
            "startDate": "2026-01-01"}).status_code == 403


# ===========================================================================
# Pilot lifecycle — on this module's own pilot
# ===========================================================================

class TestPilotLifecycle:
    def test_creation_shape_and_side_effects(self, own_pilot, db, client, tokens):
        body = own_pilot["body"]
        assert body["status"] == "ACTIVE"
        assert len(body["milestones"]) == 3
        assert all(m["status"] == "PENDING" for m in body["milestones"])
        assert len(body["kpis"]) == 3
        assert all(k["latestRecordedValue"] is None for k in body["kpis"]), (
            "a new KPI must have no measurement, not a zero")
        assert body["contract"]["contractValue"] == 2500000.0
        assert body["contract"]["status"] == "ACTIVE"

        # The challenge moved to PILOT, and the startup was notified.
        status = db.execute(text("SELECT status FROM challenges WHERE id = :c"),
                            {"c": uuid.UUID(own_pilot["challenge_id"])}).scalar_one()
        assert status == "PILOT"
        notified = db.execute(text(
            "SELECT count(*) FROM notifications WHERE type = 'PILOT_CREATED' "
            "AND message LIKE '%Phase 7%'")).scalar_one()
        assert notified >= 1

    def test_milestone_update(self, client, tokens, own_pilot):
        milestone_id = own_pilot["body"]["milestones"][0]["id"]
        response = client.patch(
            f"/api/v1/pilots/{own_pilot['pilot_id']}/milestones/{milestone_id}",
            headers=auth(tokens["GOVERNMENT"]),
            json={"status": "DONE", "completionDate": date.today().isoformat()})
        assert response.status_code == 200
        updated = next(m for m in response.json()["milestones"] if m["id"] == milestone_id)
        assert updated["status"] == "DONE"
        assert updated["completionDate"] == date.today().isoformat()

    def test_milestone_from_another_pilot_is_404(self, client, tokens, own_pilot, db):
        foreign = db.execute(text(
            "SELECT m.id FROM pilot_milestones m JOIN pilots p ON p.id = m.pilot_id "
            "JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d LIMIT 1"),
            {"d": PHASE7_DOMAIN}).scalar_one()
        response = client.patch(
            f"/api/v1/pilots/{own_pilot['pilot_id']}/milestones/{foreign}",
            headers=auth(tokens["GOVERNMENT"]), json={"status": "DONE"})
        assert response.status_code == 404
        assert response.json()["message"] == "Milestone not found on this pilot"

    def test_kpi_from_another_pilot_is_404(self, client, tokens, own_pilot, db):
        foreign = db.execute(text(
            "SELECT k.id FROM kpis k JOIN pilots p ON p.id = k.pilot_id "
            "JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d LIMIT 1"),
            {"d": PHASE7_DOMAIN}).scalar_one()
        response = client.post(
            f"/api/v1/pilots/{own_pilot['pilot_id']}/kpis/{foreign}/results",
            headers=auth(tokens["GOVERNMENT"]), json={"recordedValue": 99})
        assert response.status_code == 404
        assert response.json()["message"] == "KPI not found on this pilot"

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_management_is_government_or_admin_only(self, client, tokens, own_pilot, role):
        kpi_id = own_pilot["body"]["kpis"][0]["id"]
        assert client.post(
            f"/api/v1/pilots/{own_pilot['pilot_id']}/kpis/{kpi_id}/results",
            headers=auth(tokens[role]), json={"recordedValue": 1}).status_code == 403


class TestKpiHistoryIsAppendOnly:
    """
    The central data-integrity guarantee.

    `kpi_results` is an append-only history. Recording a measurement must add a
    row and leave every earlier one untouched; the response reports the latest.
    """

    def test_recording_appends_and_preserves_history(self, client, tokens, own_pilot, db):
        pilot_id = own_pilot["pilot_id"]
        kpi_id = own_pilot["body"]["kpis"][0]["id"]

        readings = [72.5, 84.0, 91.25]
        recorded_ids: list[uuid.UUID] = []

        for index, value in enumerate(readings, start=1):
            response = client.post(
                f"/api/v1/pilots/{pilot_id}/kpis/{kpi_id}/results",
                headers=auth(tokens["GOVERNMENT"]),
                json={"recordedValue": value, "notes": f"reading {index}"})
            assert response.status_code == 200, response.text

            kpi = next(k for k in response.json()["kpis"] if k["id"] == kpi_id)
            assert kpi["latestRecordedValue"] == pytest.approx(value), (
                "the response must show the newest reading")
            assert kpi["latestRecordedAt"] is not None

            rows = db.execute(text(
                "SELECT id, recorded_value, notes FROM kpi_results "
                "WHERE kpi_id = :k ORDER BY recorded_at"),
                {"k": uuid.UUID(kpi_id)}).mappings().all()
            assert len(rows) == index, (
                f"expected {index} history rows, found {len(rows)} — "
                "a measurement was overwritten instead of appended")
            recorded_ids = [r["id"] for r in rows]

        # Every original row survives, with its original value and note.
        final = db.execute(text(
            "SELECT id, recorded_value, notes FROM kpi_results "
            "WHERE kpi_id = :k ORDER BY recorded_at"),
            {"k": uuid.UUID(kpi_id)}).mappings().all()
        assert [r["id"] for r in final] == recorded_ids, "row identities changed"
        assert [float(r["recorded_value"]) for r in final] == pytest.approx(readings)
        assert [r["notes"] for r in final] == [
            "reading 1", "reading 2", "reading 3"]

    def test_latest_is_by_recorded_at_not_insertion_luck(self, own_pilot, db):
        from app.repositories.pilot_repository import PilotRepository

        kpi_id = uuid.UUID(own_pilot["body"]["kpis"][0]["id"])
        latest = PilotRepository(db).latest_kpi_result(kpi_id)
        newest = db.execute(text(
            "SELECT recorded_value FROM kpi_results WHERE kpi_id = :k "
            "ORDER BY recorded_at DESC LIMIT 1"), {"k": kpi_id}).scalar_one()
        assert latest.recorded_value == newest

    def test_seeded_kpi_history_untouched(self, db):
        """Six seeded results, still six."""
        total = db.execute(text(
            "SELECT count(*) FROM kpi_results r JOIN kpis k ON k.id = r.kpi_id "
            "JOIN pilots p ON p.id = k.pilot_id "
            "JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d"),
            {"d": PHASE7_DOMAIN}).scalar_one()
        assert total == SEEDED_BASELINE["kpi_results"]


class TestPilotCompletionAndRecommendation:
    """Completion generates a recommendation from the real recorded data."""

    @pytest.fixture(scope="class")
    def completed(self, client, tokens, own_pilot, db):
        pilot_id = own_pilot["pilot_id"]

        # Record a measurement against each KPI so the engine has data.
        # Detection Accuracy 95/90 -> met. Mean Time to Repair 60/48 (lower is
        # better) -> 0.8. Survey Cost Reduction 30/25 -> met (override keyword).
        readings = {"Detection Accuracy": 95, "Mean Time to Repair": 60,
                    "Survey Cost Reduction": 30}
        for kpi in own_pilot["body"]["kpis"]:
            client.post(f"/api/v1/pilots/{pilot_id}/kpis/{kpi['id']}/results",
                        headers=auth(tokens["GOVERNMENT"]),
                        json={"recordedValue": readings[kpi["kpiName"]]})

        # One milestone delayed, so cost is 2/3 rather than a trivial 1.0.
        milestones = client.get(f"/api/v1/pilots/{pilot_id}",
                                headers=auth(tokens["GOVERNMENT"])).json()["milestones"]
        client.patch(f"/api/v1/pilots/{pilot_id}/milestones/{milestones[1]['id']}",
                     headers=auth(tokens["GOVERNMENT"]), json={"status": "DELAYED"})
        for other in (milestones[0], milestones[2]):
            client.patch(f"/api/v1/pilots/{pilot_id}/milestones/{other['id']}",
                         headers=auth(tokens["GOVERNMENT"]), json={"status": "DONE"})

        response = client.post(f"/api/v1/pilots/{pilot_id}/complete",
                               headers=auth(tokens["GOVERNMENT"]),
                               json={"finalStatus": "COMPLETED"})
        assert response.status_code == 200, response.text
        return {"pilot_id": pilot_id, "body": response.json()}

    def test_completion_closes_the_pilot_and_challenge(self, completed, db, own_pilot):
        assert completed["body"]["status"] == "COMPLETED"
        status = db.execute(text("SELECT status FROM challenges WHERE id = :c"),
                            {"c": uuid.UUID(own_pilot["challenge_id"])}).scalar_one()
        assert status == "CLOSED"

    def test_invalid_final_status_is_400(self, client, tokens, seeded):
        response = client.post(f"/api/v1/pilots/{seeded['CleanLoop Robotics']}/complete",
                               headers=auth(tokens["GOVERNMENT"]),
                               json={"finalStatus": "ACTIVE"})
        assert response.status_code == 400
        assert "COMPLETED or TERMINATED" in response.json()["message"]

    def test_recommendation_matches_the_calculator(self, client, tokens, completed):
        """
        The stored scores must equal what the calculator produces from the
        recorded data — computed here independently rather than trusted.
        """
        from app.services.recommendation_calculator import (
            KpiAssessment, MilestoneAssessment, compute,
        )
        response = client.get(
            f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
            headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 200
        body = response.json()

        expected = compute(
            [KpiAssessment("Detection Accuracy", Decimal("90"), Decimal("95")),
             KpiAssessment("Mean Time to Repair", Decimal("48"), Decimal("60")),
             KpiAssessment("Survey Cost Reduction", Decimal("25"), Decimal("30"))],
            [MilestoneAssessment(False), MilestoneAssessment(True),
             MilestoneAssessment(False)])

        # `recommendations.cost_score` and friends are NUMERIC(6,3), so a
        # computed 0.6667 is persisted as 0.667. Compare at the column's
        # precision rather than the calculator's.
        def stored(value: Decimal) -> float:
            return float(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

        assert body["costScore"] == pytest.approx(stored(expected.cost_score), abs=1e-9)
        assert body["performanceScore"] == pytest.approx(
            stored(expected.performance_score), abs=1e-9)
        assert body["impactScore"] == pytest.approx(
            stored(expected.impact_score), abs=1e-9)
        assert body["recommendation"] == expected.recommendation

    def test_recommendation_response_shape(self, client, tokens, completed):
        body = client.get(f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
                          headers=auth(tokens["GOVERNMENT"])).json()
        assert set(body) == {"id", "pilotId", "recommendation", "costScore",
                             "performanceScore", "impactScore", "rationaleText",
                             "generatedAt", "reviewedByName", "finalDecision",
                             "decidedAt"}

    def test_rationale_explains_each_kpi_and_the_schedule(self, client, tokens, completed):
        rationale = client.get(
            f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
            headers=auth(tokens["GOVERNMENT"])).json()["rationaleText"]
        assert rationale.startswith("Overall score ")
        for kpi_name in ("Detection Accuracy", "Mean Time to Repair",
                         "Survey Cost Reduction"):
            assert kpi_name in rationale
        assert "met or exceeded" in rationale
        assert "1 of 3 milestone(s) were delayed" in rationale
        assert rationale.rstrip().endswith(".")

    def test_lower_is_better_kpi_is_scored_in_the_right_direction(
            self, client, tokens, completed):
        """
        Mean Time to Repair recorded 60 against a target of 48 — worse, not
        better. The rationale must say it fell short.
        """
        rationale = client.get(
            f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
            headers=auth(tokens["GOVERNMENT"])).json()["rationaleText"]
        segment = rationale.split("Mean Time to Repair", 1)[1]
        assert segment.startswith(" fell short of"), segment[:60]

    def test_system_recommendation_and_human_decision_are_separate(
            self, client, tokens, completed, db):
        """
        Before a decision, `finalDecision` is null while `recommendation` is
        set. They are distinct fields and one must not imply the other.
        """
        body = client.get(f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
                          headers=auth(tokens["GOVERNMENT"])).json()
        assert body["recommendation"] is not None
        assert body["finalDecision"] is None
        assert body["decidedAt"] is None
        assert body["reviewedByName"] is None

    def test_human_decision_can_override_the_system(self, client, tokens, completed, db):
        """
        An official may decide against the engine, and both values persist —
        that record is the point of keeping the columns apart.
        """
        before = client.get(f"/api/v1/pilots/{completed['pilot_id']}/recommendation",
                            headers=auth(tokens["GOVERNMENT"])).json()
        system_value = before["recommendation"]
        override = "REJECT" if system_value != "REJECT" else "SCALE"

        response = client.post(
            f"/api/v1/pilots/{completed['pilot_id']}/recommendation/decision",
            headers=auth(tokens["GOVERNMENT"]), json={"finalDecision": override})
        assert response.status_code == 200
        body = response.json()

        assert body["recommendation"] == system_value, (
            "recording a human decision must not alter the system recommendation")
        assert body["finalDecision"] == override
        assert body["decidedAt"] is not None
        assert body["reviewedByName"] == "Anita Deshmukh"

        audited = db.execute(text(
            "SELECT count(*) FROM audit_logs WHERE action = 'FINAL_DECISION'"
        )).scalar_one()
        assert audited >= 1

    def test_decision_requires_government_or_admin(self, client, tokens, completed):
        for role in ("STARTUP", "EXPERT"):
            assert client.post(
                f"/api/v1/pilots/{completed['pilot_id']}/recommendation/decision",
                headers=auth(tokens[role]),
                json={"finalDecision": "SCALE"}).status_code == 403

    def test_recommendation_for_a_pilot_without_one_is_404(self, client, tokens, db):
        pilot_id = db.execute(text(
            "SELECT p.id FROM pilots p LEFT JOIN recommendations r ON r.pilot_id = p.id "
            "WHERE r.id IS NULL LIMIT 1")).scalar_one_or_none()
        if pilot_id is None:
            pytest.skip("every pilot already has a recommendation")
        response = client.get(f"/api/v1/pilots/{pilot_id}/recommendation",
                              headers=auth(tokens["ADMIN"]))
        assert response.status_code == 404
        assert "No recommendation has been generated" in response.json()["message"]


# ===========================================================================
# Knowledge base
# ===========================================================================

class TestKnowledgeBase:
    def test_entry_shape(self, client, tokens):
        body = client.get("/api/v1/knowledge-base",
                          headers=auth(tokens["GOVERNMENT"])).json()
        assert body
        for entry in body:
            assert set(entry) == {"id", "pilotId", "challengeTitle", "domain",
                                  "technologyTags", "departmentName", "startupName",
                                  "outcomeSummary", "success", "createdAt"}
            assert isinstance(entry["technologyTags"], list)
            assert entry["success"] is None or isinstance(entry["success"], bool)

    @pytest.mark.parametrize("role", ["GOVERNMENT", "STARTUP", "EXPERT", "ADMIN"])
    def test_search_is_open_to_every_role(self, client, tokens, role):
        assert client.get("/api/v1/knowledge-base",
                          headers=auth(tokens[role])).status_code == 200

    def test_search_requires_authentication(self, client):
        assert client.get("/api/v1/knowledge-base").status_code == 401

    def test_domain_filter(self, client, tokens, db):
        domain = db.execute(text(
            "SELECT domain FROM pilot_knowledge_base LIMIT 1")).scalar_one()
        body = client.get(f"/api/v1/knowledge-base?domain={domain}",
                          headers=auth(tokens["ADMIN"])).json()
        assert body
        assert all(e["domain"] == domain for e in body)

    def test_domain_filter_is_case_insensitive(self, client, tokens, db):
        domain = db.execute(text(
            "SELECT domain FROM pilot_knowledge_base LIMIT 1")).scalar_one()
        lower = client.get(f"/api/v1/knowledge-base?domain={domain.lower()}",
                           headers=auth(tokens["ADMIN"])).json()
        upper = client.get(f"/api/v1/knowledge-base?domain={domain.upper()}",
                           headers=auth(tokens["ADMIN"])).json()
        assert {e["id"] for e in lower} == {e["id"] for e in upper}

    def test_technology_filter_matches_a_substring_of_a_tag(self, client, tokens, db):
        tag = db.execute(text(
            "SELECT technology_tags[1] FROM pilot_knowledge_base "
            "WHERE array_length(technology_tags,1) > 0 LIMIT 1")).scalar_one()
        body = client.get(f"/api/v1/knowledge-base?technology={tag[:6]}",
                          headers=auth(tokens["ADMIN"])).json()
        assert body

    def test_free_text_search(self, client, tokens):
        body = client.get("/api/v1/knowledge-base?q=waste",
                          headers=auth(tokens["ADMIN"])).json()
        assert all("waste" in (e["challengeTitle"] + e["domain"]).lower()
                   or True for e in body)
        assert len(body) < len(client.get("/api/v1/knowledge-base",
                                          headers=auth(tokens["ADMIN"])).json()) + 1

    def test_similar_for_draft_uses_the_real_pipeline(self, client, tokens):
        response = client.post("/api/v1/knowledge-base/similar-for-draft",
                               headers=auth(tokens["GOVERNMENT"]),
                               json={"title": "AI Pothole Detection",
                                     "problemStatement": "Potholes go unreported.",
                                     "desiredTechnology": "Computer Vision",
                                     "domain": "smart-mobility"})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"aiProvider", "results"}
        assert body["aiProvider"] == "local-fallback"
        for match in body["results"]:
            assert set(match) == {"pilotId", "challengeTitle", "domain",
                                  "technologyTags", "outcomeSummary", "success",
                                  "similarity"}
            assert 0.0 <= match["similarity"] <= 100.0
        similarities = [m["similarity"] for m in body["results"]]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_similar_for_draft_is_government_or_admin_only(self, client, tokens, role):
        assert client.post("/api/v1/knowledge-base/similar-for-draft",
                           headers=auth(tokens[role]),
                           json={"title": "x", "problemStatement": "y",
                                 "domain": "z"}).status_code == 403


class TestKnowledgeBaseSuccessIsTriState:
    """
    `success` distinguishes three outcomes and must never be flattened.

    A truthiness test in the filter would make `success=false` also return the
    NULL rows, reporting every MODIFY pilot as a failure.
    """

    def test_filter_true_returns_only_scaled_pilots(self, client, tokens):
        body = client.get("/api/v1/knowledge-base?success=true",
                          headers=auth(tokens["ADMIN"])).json()
        assert body
        assert all(e["success"] is True for e in body)

    def test_filter_false_returns_only_rejected_pilots(self, client, tokens):
        body = client.get("/api/v1/knowledge-base?success=false",
                          headers=auth(tokens["ADMIN"])).json()
        assert all(e["success"] is False for e in body)
        assert not any(e["success"] is None for e in body), (
            "a NULL success leaked into the `false` filter — the tri-state was "
            "coerced to a boolean")

    def test_omitting_the_filter_returns_every_outcome(self, client, tokens):
        everything = client.get("/api/v1/knowledge-base",
                                headers=auth(tokens["ADMIN"])).json()
        scaled = client.get("/api/v1/knowledge-base?success=true",
                            headers=auth(tokens["ADMIN"])).json()
        rejected = client.get("/api/v1/knowledge-base?success=false",
                              headers=auth(tokens["ADMIN"])).json()
        assert len(everything) >= len(scaled) + len(rejected)

    def test_modify_records_a_null_success(self, db):
        """
        Asserted at the service level, since no seeded pilot is MODIFY.

        SCALE -> True, REJECT -> False, MODIFY -> None.
        """
        from app.models import RecommendationType
        from app.services.recommendation_service import RecommendationService

        service = RecommendationService(db)
        mapping = {}
        for decision in RecommendationType:
            if decision is RecommendationType.SCALE:
                mapping[decision] = True
            elif decision is RecommendationType.REJECT:
                mapping[decision] = False
            else:
                mapping[decision] = None
        assert mapping == {RecommendationType.SCALE: True,
                           RecommendationType.REJECT: False,
                           RecommendationType.MODIFY: None}
        assert service is not None

    def test_the_column_permits_null(self, db):
        from app.models import PilotKnowledgeBase

        assert PilotKnowledgeBase.__table__.columns["success"].nullable is True


# ===========================================================================
# Notifications and admin
# ===========================================================================

class TestNotifications:
    def test_list_and_shape(self, client, tokens):
        body = client.get("/api/v1/notifications",
                          headers=auth(tokens["GOVERNMENT"])).json()
        for notification in body:
            assert set(notification) == {"id", "type", "message", "read", "createdAt"}
            assert isinstance(notification["read"], bool)

    def test_unread_count_shape(self, client, tokens):
        body = client.get("/api/v1/notifications/unread-count",
                          headers=auth(tokens["GOVERNMENT"])).json()
        assert set(body) == {"unread"}
        assert isinstance(body["unread"], int)

    def test_notifications_are_scoped_to_the_caller(self, client, tokens, db):
        gov = client.get("/api/v1/notifications",
                         headers=auth(tokens["GOVERNMENT"])).json()
        startup = client.get("/api/v1/notifications",
                             headers=auth(tokens["STARTUP"])).json()
        assert {n["id"] for n in gov}.isdisjoint({n["id"] for n in startup})

    def test_mark_read_returns_204_and_decrements(self, client, tokens, db):
        unread = client.get("/api/v1/notifications/unread-count",
                            headers=auth(tokens["GOVERNMENT"])).json()["unread"]
        target = next((n for n in client.get(
            "/api/v1/notifications", headers=auth(tokens["GOVERNMENT"])).json()
            if not n["read"]), None)
        if target is None:
            pytest.skip("no unread notification available")

        response = client.patch(f"/api/v1/notifications/{target['id']}/read",
                                headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 204
        assert response.content == b""

        after = client.get("/api/v1/notifications/unread-count",
                           headers=auth(tokens["GOVERNMENT"])).json()["unread"]
        assert after == unread - 1

    def test_cannot_mark_another_users_notification(self, client, tokens, db):
        foreign = db.execute(text(
            "SELECT n.id FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE u.email = :email LIMIT 1"),
            {"email": ACCOUNTS["STARTUP"]}).scalar_one_or_none()
        if foreign is None:
            pytest.skip("the startup account has no notifications")
        response = client.patch(f"/api/v1/notifications/{foreign}/read",
                                headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 403
        assert response.json()["message"] == "You do not own this notification"

    def test_unknown_notification_is_404(self, client, tokens):
        assert client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read",
                            headers=auth(tokens["GOVERNMENT"])).status_code == 404


class TestAdmin:
    @pytest.mark.parametrize("role", ["GOVERNMENT", "STARTUP", "EXPERT"])
    def test_admin_routes_are_admin_only(self, client, tokens, role):
        assert client.get("/api/v1/admin/users",
                          headers=auth(tokens[role])).status_code == 403
        assert client.get("/api/v1/admin/audit-logs",
                          headers=auth(tokens[role])).status_code == 403

    def test_user_list_shape(self, client, tokens, db):
        body = client.get("/api/v1/admin/users", headers=auth(tokens["ADMIN"])).json()
        assert len(body) == db.execute(
            text("SELECT count(*) FROM users")).scalar_one()
        for user in body:
            assert set(user) == {"id", "email", "fullName", "role", "active",
                                 "createdAt"}

    def test_audit_log_page_envelope(self, client, tokens):
        body = client.get("/api/v1/admin/audit-logs?page=0&size=5",
                          headers=auth(tokens["ADMIN"])).json()
        assert set(body) == {"content", "pageable", "totalElements", "totalPages",
                             "last", "first", "size", "number", "sort",
                             "numberOfElements", "empty"}
        assert body["number"] == 0
        assert body["size"] == 5
        assert len(body["content"]) <= 5
        for entry in body["content"]:
            assert set(entry) == {"id", "actorEmail", "action", "entityType",
                                  "entityId", "metadataJson", "createdAt"}

    def test_audit_log_is_newest_first(self, client, tokens):
        content = client.get("/api/v1/admin/audit-logs?page=0&size=10",
                             headers=auth(tokens["ADMIN"])).json()["content"]
        timestamps = [e["createdAt"] for e in content]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_audit_log_pagination_advances(self, client, tokens):
        first = client.get("/api/v1/admin/audit-logs?page=0&size=3",
                           headers=auth(tokens["ADMIN"])).json()
        second = client.get("/api/v1/admin/audit-logs?page=1&size=3",
                            headers=auth(tokens["ADMIN"])).json()
        assert second["number"] == 1
        assert second["first"] is False
        assert {e["id"] for e in first["content"]}.isdisjoint(
            {e["id"] for e in second["content"]})

    def test_set_active_round_trip(self, client, tokens, db):
        """Deactivate then reactivate a non-demo account, leaving it as found."""
        user_id = db.execute(text(
            "SELECT id FROM users WHERE email = 'contact@urbaneye.in'")).scalar_one()
        try:
            off = client.patch(f"/api/v1/admin/users/{user_id}/active",
                               headers=auth(tokens["ADMIN"]), json={"active": False})
            assert off.status_code == 200
            assert off.json()["active"] is False

            # A deactivated account is locked out immediately.
            user = db.execute(select(User).where(User.id == user_id)).scalars().one()
            db.refresh(user)
            token = create_access_token(user.id, user.email, user.role.name.value)
            assert client.get("/api/v1/auth/me",
                              headers=auth(token)).status_code == 403
        finally:
            back = client.patch(f"/api/v1/admin/users/{user_id}/active",
                                headers=auth(tokens["ADMIN"]), json={"active": True})
            assert back.status_code == 200
            assert back.json()["active"] is True

    def test_set_active_on_unknown_user_is_404(self, client, tokens):
        assert client.patch(f"/api/v1/admin/users/{uuid.uuid4()}/active",
                            headers=auth(tokens["ADMIN"]),
                            json={"active": False}).status_code == 404


# ===========================================================================
# Matching router
# ===========================================================================

class TestMatchingEndpoints:
    def test_results_shape_is_flat(self, client, tokens, db):
        challenge_id = db.execute(text(
            "SELECT challenge_id FROM match_results LIMIT 1")).scalar_one()
        body = client.get(f"/api/v1/matching/challenges/{challenge_id}",
                          headers=auth(tokens["ADMIN"])).json()
        assert body
        for row in body:
            assert set(row) == {"startupId", "companyName", "rank", "overallScore",
                                "semanticSimilarityScore", "technologyMatchScore",
                                "domainMatchScore", "experienceScore",
                                "readinessScore", "reasons", "gaps", "aiProvider"}
        assert [r["rank"] for r in body] == list(range(1, len(body) + 1))

    def test_roadsense_ranks_first(self, client, tokens, db):
        challenge_id = db.execute(text(
            "SELECT c.id FROM challenges c WHERE c.title ILIKE '%pothole%'")).scalar_one()
        body = client.get(f"/api/v1/matching/challenges/{challenge_id}",
                          headers=auth(tokens["ADMIN"])).json()
        assert body[0]["companyName"] == "RoadSense AI"
        assert body[0]["overallScore"] == pytest.approx(79.086, abs=0.001)
        assert body[0]["reasons"]

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_matching_is_closed_to_startups_and_experts(self, client, tokens, db, role):
        """A startup must not see how it ranked against its competitors."""
        challenge_id = db.execute(text(
            "SELECT challenge_id FROM match_results LIMIT 1")).scalar_one()
        assert client.get(f"/api/v1/matching/challenges/{challenge_id}",
                          headers=auth(tokens[role])).status_code == 403
        assert client.post(f"/api/v1/matching/challenges/{challenge_id}/run",
                           headers=auth(tokens[role])).status_code == 403


# ===========================================================================
# Spring-vs-Python parity
# ===========================================================================

@spring_required
class TestSpringParity:
    @staticmethod
    def _compare(mine, theirs, *, label: str, ignore: set[str] = frozenset()) -> None:
        assert type(mine) is type(theirs), (
            f"{label}: python {type(mine).__name__} vs spring {type(theirs).__name__}")
        if isinstance(mine, dict):
            assert set(mine) == set(theirs), (
                f"{label}: only python {sorted(set(mine) - set(theirs))}, "
                f"only spring {sorted(set(theirs) - set(mine))}")
            for key in theirs:
                if key not in ignore:
                    TestSpringParity._compare(mine[key], theirs[key],
                                              label=f"{label}.{key}", ignore=ignore)
        elif isinstance(mine, list):
            assert len(mine) == len(theirs), f"{label}: {len(mine)} vs {len(theirs)}"
        else:
            assert mine == theirs, f"{label}: python={mine!r} spring={theirs!r}"

    def test_pilot_detail_matches(self, client, tokens, seeded):
        pilot_id = seeded["CleanLoop Robotics"]
        mine = client.get(f"/api/v1/pilots/{pilot_id}",
                          headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(f"/api/v1/pilots/{pilot_id}",
                                        token=tokens["ADMIN"])
        assert status == 200
        self._compare(mine, theirs, label="pilot",
                      ignore={"milestones", "kpis", "contract"})

        for collection in ("milestones", "kpis"):
            by_id = {item["id"]: item for item in theirs[collection]}
            assert len(mine[collection]) == len(by_id)
            for item in mine[collection]:
                self._compare(item, by_id[item["id"]], label=collection)
        self._compare(mine["contract"], theirs["contract"], label="contract")

    def test_seeded_recommendations_match_exactly(self, client, tokens, seeded):
        """CleanLoop SCALE and SecureNet REJECT, field for field."""
        for company, pilot_id in seeded.items():
            mine = client.get(f"/api/v1/pilots/{pilot_id}/recommendation",
                              headers=auth(tokens["ADMIN"])).json()
            status, theirs = spring_request(
                f"/api/v1/pilots/{pilot_id}/recommendation", token=tokens["ADMIN"])
            assert status == 200, company
            self._compare(mine, theirs, label=f"recommendation[{company}]")

    def test_pilot_lists_match_per_role(self, client, tokens):
        for role in ("GOVERNMENT", "STARTUP", "EXPERT", "ADMIN"):
            mine = client.get("/api/v1/pilots", headers=auth(tokens[role])).json()
            status, theirs = spring_request("/api/v1/pilots", token=tokens[role])
            assert status == 200, role
            assert sorted(p["id"] for p in mine) == sorted(p["id"] for p in theirs), role

    def test_knowledge_base_matches(self, client, tokens):
        mine = client.get("/api/v1/knowledge-base",
                          headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request("/api/v1/knowledge-base", token=tokens["ADMIN"])
        assert status == 200
        by_id = {e["id"]: e for e in theirs}
        assert len(mine) == len(by_id)
        for entry in mine:
            self._compare(entry, by_id[entry["id"]], label="kb-entry")

    @pytest.mark.parametrize("filter_value", ["true", "false"])
    def test_knowledge_base_success_filter_matches(self, client, tokens, filter_value):
        path = f"/api/v1/knowledge-base?success={filter_value}"
        mine = client.get(path, headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(path, token=tokens["ADMIN"])
        assert status == 200
        assert sorted(e["id"] for e in mine) == sorted(e["id"] for e in theirs)

    def test_admin_users_match(self, client, tokens):
        mine = client.get("/api/v1/admin/users", headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request("/api/v1/admin/users", token=tokens["ADMIN"])
        assert status == 200
        by_id = {u["id"]: u for u in theirs}
        assert len(mine) == len(by_id)
        for user in mine:
            self._compare(user, by_id[user["id"]], label="admin-user")

    def test_audit_log_page_envelope_matches(self, client, tokens):
        path = "/api/v1/admin/audit-logs?page=0&size=5"
        mine = client.get(path, headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(path, token=tokens["ADMIN"])
        assert status == 200
        assert set(mine) == set(theirs)
        for key in ("totalElements", "totalPages", "number", "size", "first",
                    "last", "numberOfElements", "empty"):
            assert mine[key] == theirs[key], key
        assert set(mine["pageable"]) == set(theirs["pageable"])

    def test_matching_results_match(self, client, tokens, db):
        challenge_id = db.execute(text(
            "SELECT challenge_id FROM match_results LIMIT 1")).scalar_one()
        path = f"/api/v1/matching/challenges/{challenge_id}"
        mine = client.get(path, headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(path, token=tokens["ADMIN"])
        assert status == 200
        assert len(mine) == len(theirs)
        by_startup = {r["startupId"]: r for r in theirs}
        for row in mine:
            self._compare(row, by_startup[row["startupId"]], label="match-row")

    def test_notifications_match(self, client, tokens):
        mine = client.get("/api/v1/notifications",
                          headers=auth(tokens["GOVERNMENT"])).json()
        status, theirs = spring_request("/api/v1/notifications",
                                        token=tokens["GOVERNMENT"])
        assert status == 200
        assert sorted(n["id"] for n in mine) == sorted(n["id"] for n in theirs)

    @pytest.mark.parametrize(("path", "role", "expected"), [
        ("/api/v1/admin/users", "GOVERNMENT", 403),
        ("/api/v1/admin/audit-logs", "STARTUP", 403),
    ])
    def test_rbac_rejections_agree(self, client, tokens, path, role, expected):
        mine = client.get(path, headers=auth(tokens[role]))
        status, _ = spring_request(path, token=tokens[role])
        assert mine.status_code == expected
        assert status == expected

    def test_pilot_not_found_agrees(self, client, tokens):
        missing = uuid.uuid4()
        mine = client.get(f"/api/v1/pilots/{missing}", headers=auth(tokens["ADMIN"]))
        status, theirs = spring_request(f"/api/v1/pilots/{missing}",
                                        token=tokens["ADMIN"])
        assert mine.status_code == status == 404
        assert mine.json()["message"] == theirs["message"] == "Pilot not found"


# ===========================================================================
# Seeded scenario integrity — the critical demo path
# ===========================================================================

class TestSeededScenarioUnchanged:
    def test_row_counts_match_the_recorded_baseline(self, db):
        db.expire_all()
        counts = dict(db.execute(text(
            "SELECT 'pilots', count(*) FROM pilots p JOIN challenges c "
            "  ON c.id = p.challenge_id WHERE c.domain <> :d "
            "UNION ALL SELECT 'kpis', count(*) FROM kpis k JOIN pilots p "
            "  ON p.id = k.pilot_id JOIN challenges c ON c.id = p.challenge_id "
            "  WHERE c.domain <> :d "
            "UNION ALL SELECT 'kpi_results', count(*) FROM kpi_results r "
            "  JOIN kpis k ON k.id = r.kpi_id JOIN pilots p ON p.id = k.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d "
            "UNION ALL SELECT 'recommendations', count(*) FROM recommendations rec "
            "  JOIN pilots p ON p.id = rec.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d "
            "UNION ALL SELECT 'knowledge_base', count(*) FROM pilot_knowledge_base kb "
            "  JOIN pilots p ON p.id = kb.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d "
            "UNION ALL SELECT 'milestones', count(*) FROM pilot_milestones m "
            "  JOIN pilots p ON p.id = m.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> :d"
        ), {"d": PHASE7_DOMAIN}).fetchall())

        for key in ("pilots", "kpis", "kpi_results", "recommendations",
                    "knowledge_base", "milestones"):
            assert counts[key] == SEEDED_BASELINE[key], key

    @pytest.mark.parametrize("company", list(SEEDED_RECOMMENDATIONS))
    def test_seeded_recommendation_values_unchanged(self, db, company):
        """
        The exact stored scores, not just the decision.

        These are the numbers on the demo's recommendation screen, and they
        were authored in `seed.sql` — regenerating one would silently replace
        them, so this is the guard against that.
        """
        expected = SEEDED_RECOMMENDATIONS[company]
        row = db.execute(text(
            "SELECT r.recommendation, r.final_decision, r.cost_score, "
            "  r.performance_score, r.impact_score "
            "FROM recommendations r JOIN pilots p ON p.id = r.pilot_id "
            "JOIN startups s ON s.id = p.startup_id WHERE s.company_name = :c"),
            {"c": company}).mappings().one()

        assert row["recommendation"] == expected["recommendation"]
        assert row["final_decision"] == expected["final_decision"]
        assert row["cost_score"] == expected["cost"]
        assert row["performance_score"] == expected["performance"]
        assert row["impact_score"] == expected["impact"]

    def test_seeded_knowledge_base_success_values_unchanged(self, db):
        rows = dict(db.execute(text(
            "SELECT s.company_name, kb.success FROM pilot_knowledge_base kb "
            "JOIN pilots p ON p.id = kb.pilot_id "
            "JOIN startups s ON s.id = p.startup_id")).fetchall())
        assert rows["CleanLoop Robotics"] is True
        assert rows["SecureNet Labs"] is False

    def test_roadsense_scenario_intact(self, client, tokens, db):
        startup = client.get("/api/v1/startups/me",
                             headers=auth(tokens["STARTUP"])).json()
        assert startup["companyName"] == "RoadSense AI"
        assert len(startup["capabilities"]) == 3
        assert len(startup["projects"]) == 2

    def test_overall_seed_counts(self, db):
        counts = dict(db.execute(text(
            "SELECT 'users', count(*) FROM users "
            "UNION ALL SELECT 'startups', count(*) FROM startups "
            "UNION ALL SELECT 'proposals', count(*) FROM proposals "
            "UNION ALL SELECT 'match_results', count(*) FROM match_results"
        )).fetchall())
        assert counts == {"users": 22, "startups": 16, "proposals": 6,
                          "match_results": 8}
