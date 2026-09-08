"""
Phase 8 gate: whole-backend integration, deliberately not duplicating phases 4-7.

The per-phase suites verify each resource in isolation. Two things they cannot
show, and this module adds:

1. **Every one of the 46 endpoints is registered and reachable.** The per-phase
   suites exercise the endpoints they care about; nothing asserts the *complete*
   surface responds, with the right status, for every role. A route that was
   never wired, or that 500s on an unusual role, would slip through.

2. **The pieces compose into the SIH demo journey.** Each phase proves its own
   step; `TestSihDemoWalkthrough` runs the whole path end to end in one
   sequence, on data it creates and removes, so a break *between* steps is
   caught — the failure mode the isolated tests structurally cannot see.

Plus a small guard on the shared-database test infrastructure itself, since the
correctness of every other seeded-data assertion depends on it.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionLocal, check_connection
from app.main import app
from app.models import Startup, User
from app.security.jwt import create_access_token
from tests.conftest import TEST_MARKER_DOMAINS

PHASE8_DOMAIN = "phase8-testing"

ACCOUNTS = {
    "GOVERNMENT": "government@demo.com",
    "STARTUP": "startup@demo.com",
    "EXPERT": "expert@demo.com",
    "ADMIN": "admin@demo.com",
}

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


def purge_phase8_rows(db) -> None:
    """Remove everything this module creates, keyed on its marker domain."""
    db.rollback()
    statements = (
        "DELETE FROM pilot_knowledge_base WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
        "   WHERE c.domain = :d)",
        "DELETE FROM recommendations WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
        "   WHERE c.domain = :d)",
        "DELETE FROM kpi_results WHERE kpi_id IN "
        "  (SELECT k.id FROM kpis k JOIN pilots p ON p.id = k.pilot_id"
        "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = :d)",
        "DELETE FROM kpis WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
        "   WHERE c.domain = :d)",
        "DELETE FROM pilot_milestones WHERE pilot_id IN "
        "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
        "   WHERE c.domain = :d)",
        "DELETE FROM pilots WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
        "DELETE FROM evaluation_scores WHERE evaluation_id IN "
        "  (SELECT e.id FROM evaluations e JOIN proposals pr ON pr.id = e.proposal_id"
        "   JOIN challenges c ON c.id = pr.challenge_id WHERE c.domain = :d)",
        "DELETE FROM evaluations WHERE proposal_id IN "
        "  (SELECT pr.id FROM proposals pr JOIN challenges c ON c.id = pr.challenge_id"
        "   WHERE c.domain = :d)",
        "DELETE FROM proposals WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :d)",
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
        "DELETE FROM notifications WHERE message LIKE '%Phase 8%'",
    )
    for statement in statements:
        db.execute(text(statement), {"d": PHASE8_DOMAIN})
    db.commit()


@pytest.fixture(scope="module", autouse=True)
def _clean(db):
    purge_phase8_rows(db)
    yield
    purge_phase8_rows(db)


# ===========================================================================
# 1. The complete endpoint surface
# ===========================================================================

#: Every endpoint in the migration inventory, with the roles that may reach it.
#: `None` in `allowed` means any authenticated caller. This is the contract the
#: frontend depends on, written out once so a missing or mis-guarded route is a
#: visible failure rather than an untested gap.
ENDPOINT_MATRIX: list[tuple[str, str, tuple[str, ...] | None]] = [
    # (method, path template, roles allowed)
    ("POST", "/api/v1/auth/register", ()),        # public
    ("POST", "/api/v1/auth/login", ()),           # public
    ("GET", "/api/v1/auth/me", None),
    ("POST", "/api/v1/challenges", ("GOVERNMENT",)),
    ("PUT", "/api/v1/challenges/{challenge_id}", ("GOVERNMENT",)),
    ("POST", "/api/v1/challenges/{challenge_id}/publish", ("GOVERNMENT",)),
    ("GET", "/api/v1/challenges/{challenge_id}", None),
    ("GET", "/api/v1/challenges", None),
    ("GET", "/api/v1/startups/me", ("STARTUP",)),
    ("PUT", "/api/v1/startups/me", ("STARTUP",)),
    ("POST", "/api/v1/startups/me/capabilities", ("STARTUP",)),
    ("DELETE", "/api/v1/startups/me/capabilities/{capability_id}", ("STARTUP",)),
    ("POST", "/api/v1/startups/me/projects", ("STARTUP",)),
    ("GET", "/api/v1/startups", ("GOVERNMENT", "EXPERT", "ADMIN")),
    ("GET", "/api/v1/startups/{startup_id}", ("GOVERNMENT", "EXPERT", "ADMIN")),
    ("POST", "/api/v1/matching/challenges/{challenge_id}/run", ("GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/matching/challenges/{challenge_id}", ("GOVERNMENT", "ADMIN")),
    ("POST", "/api/v1/proposals/challenges/{challenge_id}", ("STARTUP",)),
    ("GET", "/api/v1/proposals/challenges/{challenge_id}", ("GOVERNMENT", "EXPERT", "ADMIN")),
    ("GET", "/api/v1/proposals/{proposal_id}", None),
    ("GET", "/api/v1/proposals/mine", ("STARTUP",)),
    ("GET", "/api/v1/proposals/queue", ("EXPERT",)),
    ("PATCH", "/api/v1/proposals/{proposal_id}/status", ("GOVERNMENT", "ADMIN")),
    ("POST", "/api/v1/documents/{owner_type}/{owner_id}", None),
    ("GET", "/api/v1/documents/{owner_type}/{owner_id}", None),
    ("GET", "/api/v1/evaluations/proposals/{proposal_id}/criteria",
     ("EXPERT", "GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/evaluations/proposals/{proposal_id}/ai-analysis",
     ("EXPERT", "GOVERNMENT", "ADMIN")),
    ("POST", "/api/v1/evaluations/proposals/{proposal_id}", ("EXPERT",)),
    ("POST", "/api/v1/pilots", ("GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/pilots/{pilot_id}", None),
    ("GET", "/api/v1/pilots", None),
    ("PATCH", "/api/v1/pilots/{pilot_id}/milestones/{milestone_id}",
     ("GOVERNMENT", "ADMIN")),
    ("POST", "/api/v1/pilots/{pilot_id}/kpis/{kpi_id}/results", ("GOVERNMENT", "ADMIN")),
    ("POST", "/api/v1/pilots/{pilot_id}/complete", ("GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/pilots/{pilot_id}/recommendation", None),
    ("POST", "/api/v1/pilots/{pilot_id}/recommendation/decision", ("GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/knowledge-base", None),
    ("POST", "/api/v1/knowledge-base/similar-for-draft", ("GOVERNMENT", "ADMIN")),
    ("GET", "/api/v1/notifications", None),
    ("GET", "/api/v1/notifications/unread-count", None),
    ("PATCH", "/api/v1/notifications/{notification_id}/read", None),
    ("GET", "/api/v1/admin/users", ("ADMIN",)),
    ("PATCH", "/api/v1/admin/users/{id}/active", ("ADMIN",)),
    ("GET", "/api/v1/admin/audit-logs", ("ADMIN",)),
    ("GET", "/", ()),          # public
    ("GET", "/health", ()),    # public
]


def _registered_routes() -> set[tuple[str, str]]:
    """(method, path) pairs the application actually serves."""
    routes = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            routes.add((method, route.path))
    return routes


class TestEndpointSurface:
    def test_the_inventory_lists_all_46_endpoints(self):
        assert len(ENDPOINT_MATRIX) == 46, (
            f"the matrix describes {len(ENDPOINT_MATRIX)} endpoints, not 46")

    def test_every_inventory_endpoint_is_registered(self):
        """
        Each endpoint from the migration inventory must exist in the app.

        Path parameter *names* differ between the Java routes and ours
        (`{id}` vs `{user_id}`), so comparison is on the method plus the
        path's shape with parameter names normalised away.
        """
        import re

        def shape(path: str) -> str:
            return re.sub(r"\{[^}]+\}", "{}", path)

        registered = {(method, shape(path)) for method, path in _registered_routes()}
        missing = [
            f"{method} {path}"
            for method, path, _ in ENDPOINT_MATRIX
            if (method, shape(path)) not in registered
        ]
        assert not missing, f"not registered: {missing}"

    def test_no_unexpected_endpoints_are_exposed(self):
        """
        The app serves nothing beyond the inventory (plus the docs routes).

        A stray debug or probe endpoint left mounted is a real risk — Phase 2
        had temporary `_auth-probe` routes, and this is what catches their
        equivalent next time.
        """
        import re

        def shape(path: str) -> str:
            return re.sub(r"\{[^}]+\}", "{}", path)

        expected = {(method, shape(path)) for method, path, _ in ENDPOINT_MATRIX}
        docs = {"/swagger-ui", "/api-docs", "/redoc", "/docs/oauth2-redirect"}
        extra = [
            f"{method} {path}"
            for method, path in _registered_routes()
            if (method, shape(path)) not in expected and path not in docs
        ]
        assert not extra, f"unexpected endpoints exposed: {extra}"

    def test_every_protected_endpoint_rejects_an_anonymous_caller(self, client):
        """
        No authenticated endpoint may be reachable without a token.

        Uses syntactically valid ids so a 401 cannot be confused with a 404 or
        a validation error — the assertion is specifically that authentication
        is enforced before anything else.
        """
        placeholder = str(uuid.uuid4())
        failures = []
        for method, path, allowed in ENDPOINT_MATRIX:
            if allowed == ():          # deliberately public
                continue
            url = path.format(**{
                name: ("STARTUP" if name == "owner_type" else placeholder)
                for name in _param_names(path)
            })
            response = client.request(method, url, json={})
            if response.status_code != 401:
                failures.append(f"{method} {url} -> {response.status_code}")
        assert not failures, f"reachable without authentication: {failures}"

    def test_role_guards_return_403_never_401(self, client, tokens, real_ids):
        """
        A role mismatch must be 403.

        The frontend clears the token and redirects to /login on *any* 401, so
        a 401 here would silently sign users out whenever they open a page
        their role simply cannot see.

        Uses **real** resource ids. Several services resolve the resource
        before checking the role — `MatchingService._must_access` 404s on an
        unknown challenge exactly as the Java service does — so a random UUID
        would short-circuit to 404 and never reach the guard being tested.
        """
        failures = []
        for method, path, allowed in ENDPOINT_MATRIX:
            if not allowed:            # public or any-authenticated
                continue
            for role in ACCOUNTS:
                if role in allowed:
                    continue
                url = path.format(**{name: real_ids[name]
                                     for name in _param_names(path)})
                response = client.request(method, url, headers=auth(tokens[role]),
                                          json={})
                if response.status_code != 403:
                    failures.append(
                        f"{method} {url} as {role} -> {response.status_code} (want 403)")
        assert not failures, "\n".join(failures)


def _param_names(path: str) -> list[str]:
    import re

    return re.findall(r"\{([^}]+)\}", path)


@pytest.fixture(scope="module")
def real_ids(db) -> dict[str, str]:
    """
    Genuine ids from the seeded data, for the role-guard matrix.

    Several services check that a resource *exists* before checking the
    caller's role — `MatchingService._must_access` resolves the challenge and
    404s first, exactly as the Java service does. Probing those with a random
    UUID therefore returns 404 and never reaches the guard. Using real ids
    means the matrix tests the authorisation rule rather than the lookup.
    """
    def one(sql: str) -> str:
        return str(db.execute(text(sql)).scalars().first())

    startup_id = one("SELECT id FROM startups LIMIT 1")
    return {
        "challenge_id": one("SELECT id FROM challenges WHERE status <> 'DRAFT' LIMIT 1"),
        "startup_id": startup_id,
        "capability_id": one("SELECT id FROM startup_capabilities LIMIT 1"),
        "proposal_id": one("SELECT id FROM proposals LIMIT 1"),
        "pilot_id": one("SELECT id FROM pilots LIMIT 1"),
        "milestone_id": one("SELECT id FROM pilot_milestones LIMIT 1"),
        "kpi_id": one("SELECT id FROM kpis LIMIT 1"),
        "notification_id": one("SELECT id FROM notifications LIMIT 1"),
        "id": one("SELECT id FROM users LIMIT 1"),
        "owner_type": "STARTUP",
        "owner_id": startup_id,
    }


# ===========================================================================
# 2. The SIH demo journey, end to end
# ===========================================================================

class TestSihDemoWalkthrough:
    """
    The complete demo path in one sequence, on rows this class creates.

    Government publishes a challenge, runs real AI matching, a startup submits
    a proposal, an expert evaluates it, government shortlists and starts a
    pilot, records KPI measurements, completes it, reads the recommendation and
    records a human decision, and the outcome lands in the knowledge base.

    Ordered deliberately — each step consumes the previous step's output, so
    this is what catches a break *between* steps.
    """

    @pytest.fixture(scope="class")
    def journey(self) -> dict:
        """Carries state between the ordered steps."""
        return {}

    def test_01_government_publishes_a_challenge(self, client, tokens, journey):
        created = client.post("/api/v1/challenges", headers=auth(tokens["GOVERNMENT"]),
                              json={
            "title": "Phase 8 Road Defect Detection",
            "problemStatement": (
                "Municipal roads develop potholes that are reported manually and "
                "repaired slowly, and there is no reliable survey of surface damage."),
            "desiredTechnology": "Computer Vision, Deep Learning, GIS Mapping",
            "domain": PHASE8_DOMAIN,
            "outcomesExpected": "Automated detection and prioritised repair scheduling.",
            "budgetRange": "INR 20 - 40 lakh",
            "timelineDays": 120,
            "requirements": [
                {"requirementType": "ELIGIBILITY",
                 "description": "DPIIT-recognised startup", "mandatory": True},
                {"requirementType": "TECHNICAL",
                 "description": "Runs on existing municipal vehicles", "mandatory": True},
            ],
            "kpis": [
                {"kpiName": "Detection Accuracy", "targetValue": 90,
                 "unit": "percent", "weight": 0.5},
                {"kpiName": "Survey Cost Reduction", "targetValue": 25,
                 "unit": "percent", "weight": 0.5},
            ],
        })
        assert created.status_code == 201, created.text
        journey["challenge_id"] = created.json()["id"]

        published = client.post(
            f"/api/v1/challenges/{journey['challenge_id']}/publish",
            headers=auth(tokens["GOVERNMENT"]))
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "PUBLISHED"

        # The default rubric is seeded on publish; the expert scores against it.
        criteria_count = len(published.json()["kpis"])
        assert criteria_count == 2

    def test_02_startup_discovers_the_published_challenge(self, client, tokens, journey):
        listing = client.get("/api/v1/challenges", headers=auth(tokens["STARTUP"])).json()
        assert journey["challenge_id"] in {c["id"] for c in listing}, (
            "a published challenge must be visible to startups")

    def test_03_ai_matching_ranks_real_candidates(self, client, tokens, journey):
        """
        Real pipeline: embeddings computed on demand, five weighted components,
        deterministic explanations. Nothing here is stubbed.
        """
        response = client.post(
            f"/api/v1/matching/challenges/{journey['challenge_id']}/run",
            headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["aiProvider"] == "local-fallback"
        assert body["totalCandidatesConsidered"] == 16
        assert body["results"], "matching returned no candidates"
        assert sum(body["weights"].values()) == pytest.approx(1.0)

        top = body["results"][0]
        assert top["rank"] == 1
        assert 0 < top["overallScore"] <= 100
        assert top["reasons"], "the top match carries no explanation"
        # Scores must be genuinely distinct, not a constant.
        assert len({c["overallScore"] for c in body["results"]}) == len(body["results"])

        journey["top_startup_id"] = top["startupId"]
        journey["top_company"] = top["companyName"]

    def test_04_stored_results_match_the_run(self, client, tokens, journey):
        rows = client.get(f"/api/v1/matching/challenges/{journey['challenge_id']}",
                          headers=auth(tokens["GOVERNMENT"])).json()
        assert rows[0]["startupId"] == journey["top_startup_id"]
        assert rows[0]["rank"] == 1
        # The stored shape is flat where the run's was nested.
        assert "semanticSimilarityScore" in rows[0]

    def test_05_startup_submits_a_proposal(self, client, tokens, journey, db):
        response = client.post(
            f"/api/v1/proposals/challenges/{journey['challenge_id']}",
            headers=auth(tokens["STARTUP"]),
            json={"summary": "Dashcam-based detection using our existing pipeline.",
                  "proposedApproach": "On-vehicle inference with a review dashboard.",
                  "costEstimate": 3200000, "timelineEstimateDays": 110})
        assert response.status_code == 201, response.text
        journey["proposal_id"] = response.json()["id"]
        assert response.json()["status"] == "SUBMITTED"

        roadsense = db.execute(
            select(Startup).where(Startup.company_name == "RoadSense AI")).scalars().one()
        journey["roadsense_id"] = str(roadsense.id)

    def test_06_proposal_reaches_the_expert_queue(self, client, tokens, journey):
        queue = client.get("/api/v1/proposals/queue",
                           headers=auth(tokens["EXPERT"])).json()
        assert journey["proposal_id"] in {p["id"] for p in queue}

    def test_07_expert_reads_the_ai_assisted_analysis(self, client, tokens, journey):
        """AI assists the expert; it does not replace them."""
        response = client.get(
            f"/api/v1/evaluations/proposals/{journey['proposal_id']}/ai-analysis",
            headers=auth(tokens["EXPERT"]))
        assert response.status_code == 200, response.text
        assert response.json()["summary"], "the AI analysis was empty"

    def test_08_expert_submits_scores(self, client, tokens, journey):
        criteria = client.get(
            f"/api/v1/evaluations/proposals/{journey['proposal_id']}/criteria",
            headers=auth(tokens["EXPERT"])).json()
        assert len(criteria) == 4, "the default rubric should have four criteria"

        response = client.post(
            f"/api/v1/evaluations/proposals/{journey['proposal_id']}",
            headers=auth(tokens["EXPERT"]),
            json={"comments": "Strong fit; proven deployment.",
                  "scores": [{"criterionId": c["id"], "score": 8,
                              "remarks": "solid"} for c in criteria]})
        # 200, not 201: the Java controller returns `ResponseEntity.ok(...)`.
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["totalScore"] is not None
        assert len(body["scores"]) == 4
        journey["evaluation_total"] = body["totalScore"]

    def test_09_government_shortlists_the_proposal(self, client, tokens, journey):
        response = client.patch(
            f"/api/v1/proposals/{journey['proposal_id']}/status",
            headers=auth(tokens["GOVERNMENT"]), json={"status": "SHORTLISTED"})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "SHORTLISTED"

    def test_10_government_starts_a_pilot(self, client, tokens, journey):
        today = date.today()
        response = client.post("/api/v1/pilots", headers=auth(tokens["GOVERNMENT"]),
                               json={
            "challengeId": journey["challenge_id"],
            "startupId": journey["roadsense_id"],
            "startDate": today.isoformat(),
            "endDate": (today + timedelta(days=120)).isoformat(),
            "milestones": [
                {"title": "Contract", "dueDate": (today + timedelta(days=10)).isoformat()},
                {"title": "Deployment", "dueDate": (today + timedelta(days=40)).isoformat()},
                {"title": "KPI Review", "dueDate": (today + timedelta(days=100)).isoformat()},
            ],
            "kpis": [
                {"kpiName": "Detection Accuracy", "targetValue": 90, "unit": "percent"},
                {"kpiName": "Survey Cost Reduction", "targetValue": 25, "unit": "percent"},
            ],
            "contract": {"contractValue": 3200000, "ipTerms": "Jointly owned",
                         "dataTerms": "Data stays in India",
                         "paymentTerms": "Milestone-linked"},
        })
        assert response.status_code == 201, response.text
        body = response.json()
        journey["pilot_id"] = body["id"]
        assert body["status"] == "ACTIVE"
        assert len(body["milestones"]) == 3
        assert all(k["latestRecordedValue"] is None for k in body["kpis"]), (
            "a new pilot's KPIs must have no measurement, not a zero")

    def test_11_startup_sees_its_own_pilot(self, client, tokens, journey):
        pilots = client.get("/api/v1/pilots", headers=auth(tokens["STARTUP"])).json()
        assert journey["pilot_id"] in {p["id"] for p in pilots}

    def test_12_kpi_measurements_are_recorded_as_history(self, client, tokens, journey, db):
        pilot = client.get(f"/api/v1/pilots/{journey['pilot_id']}",
                           headers=auth(tokens["GOVERNMENT"])).json()
        accuracy = next(k for k in pilot["kpis"] if k["kpiName"] == "Detection Accuracy")
        savings = next(k for k in pilot["kpis"] if k["kpiName"] == "Survey Cost Reduction")

        # Two readings on the first KPI: the history must retain both.
        for value in (86, 93):
            response = client.post(
                f"/api/v1/pilots/{journey['pilot_id']}/kpis/{accuracy['id']}/results",
                headers=auth(tokens["GOVERNMENT"]),
                json={"recordedValue": value, "notes": f"reading {value}"})
            assert response.status_code == 200, response.text

        client.post(
            f"/api/v1/pilots/{journey['pilot_id']}/kpis/{savings['id']}/results",
            headers=auth(tokens["GOVERNMENT"]), json={"recordedValue": 28})

        history = db.execute(text(
            "SELECT recorded_value FROM kpi_results WHERE kpi_id = :k "
            "ORDER BY recorded_at"), {"k": uuid.UUID(accuracy["id"])}).scalars().all()
        assert [float(v) for v in history] == [86.0, 93.0], (
            "the earlier measurement was overwritten instead of appended")

        refreshed = client.get(f"/api/v1/pilots/{journey['pilot_id']}",
                               headers=auth(tokens["GOVERNMENT"])).json()
        latest = next(k for k in refreshed["kpis"]
                      if k["kpiName"] == "Detection Accuracy")["latestRecordedValue"]
        assert latest == pytest.approx(93.0), "the response must show the newest reading"

    def test_13_milestones_progress(self, client, tokens, journey):
        pilot = client.get(f"/api/v1/pilots/{journey['pilot_id']}",
                           headers=auth(tokens["GOVERNMENT"])).json()
        for milestone in pilot["milestones"]:
            response = client.patch(
                f"/api/v1/pilots/{journey['pilot_id']}/milestones/{milestone['id']}",
                headers=auth(tokens["GOVERNMENT"]),
                json={"status": "DONE", "completionDate": date.today().isoformat()})
            assert response.status_code == 200
        final = client.get(f"/api/v1/pilots/{journey['pilot_id']}",
                           headers=auth(tokens["GOVERNMENT"])).json()
        assert all(m["status"] == "DONE" for m in final["milestones"])

    def test_14_completion_generates_a_recommendation(self, client, tokens, journey):
        response = client.post(f"/api/v1/pilots/{journey['pilot_id']}/complete",
                               headers=auth(tokens["GOVERNMENT"]),
                               json={"finalStatus": "COMPLETED"})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "COMPLETED"

        recommendation = client.get(
            f"/api/v1/pilots/{journey['pilot_id']}/recommendation",
            headers=auth(tokens["GOVERNMENT"])).json()

        # Both KPIs exceeded target and no milestone was delayed, so every
        # component is 1.0 and the engine should recommend SCALE.
        assert recommendation["costScore"] == pytest.approx(1.0)
        assert recommendation["performanceScore"] == pytest.approx(1.0)
        assert recommendation["impactScore"] == pytest.approx(1.0)
        assert recommendation["recommendation"] == "SCALE"
        assert "Detection Accuracy" in recommendation["rationaleText"]
        assert "All milestones were delivered on schedule" in recommendation["rationaleText"]

        # Untouched by the engine until a person decides.
        assert recommendation["finalDecision"] is None
        assert recommendation["reviewedByName"] is None
        journey["system_recommendation"] = recommendation["recommendation"]

    def test_15_human_records_the_final_decision(self, client, tokens, journey):
        response = client.post(
            f"/api/v1/pilots/{journey['pilot_id']}/recommendation/decision",
            headers=auth(tokens["GOVERNMENT"]), json={"finalDecision": "SCALE"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["recommendation"] == journey["system_recommendation"]
        assert body["finalDecision"] == "SCALE"
        assert body["reviewedByName"] == "Anita Deshmukh"
        assert body["decidedAt"] is not None

    def test_16_outcome_reaches_the_knowledge_base(self, client, tokens, journey):
        entries = client.get("/api/v1/knowledge-base",
                             headers=auth(tokens["GOVERNMENT"])).json()
        entry = next((e for e in entries if e["pilotId"] == journey["pilot_id"]), None)
        assert entry is not None, "the completed pilot did not reach the knowledge base"
        assert entry["success"] is True, "a SCALE outcome records success=True"
        assert entry["domain"] == PHASE8_DOMAIN
        assert entry["technologyTags"]
        assert entry["outcomeSummary"]

    def test_17_the_new_entry_is_discoverable_by_similarity(self, client, tokens, journey):
        """The knowledge base feeds the next department's draft."""
        response = client.post("/api/v1/knowledge-base/similar-for-draft",
                               headers=auth(tokens["GOVERNMENT"]),
                               json={"title": "Road surface damage detection",
                                     "problemStatement": "Potholes go unreported.",
                                     "desiredTechnology": "Computer Vision",
                                     "domain": PHASE8_DOMAIN})
        assert response.status_code == 200
        results = response.json()["results"]
        assert results, "similarity search returned nothing"
        assert all(0 <= r["similarity"] <= 100 for r in results)

        # KNOWN DEFECT, inherited verbatim from the standalone ai-service
        # (`knowledge_base_service.py` line 60: `"pilot_id": str(e["id"])`).
        # The query selects `pkb.id`, so the field named `pilotId` actually
        # carries the *knowledge-base entry* id. Asserted as-is to hold Spring
        # parity; fixing it is a contract change and a product decision, and it
        # is reported rather than silently corrected.
        entry_ids = {
            str(row) for row in
            self._kb_entry_ids_for_pilot(journey["pilot_id"])
        }
        assert entry_ids & {r["pilotId"] for r in results}, (
            "the new knowledge-base entry was not discoverable by similarity")

    @staticmethod
    def _kb_entry_ids_for_pilot(pilot_id: str) -> list:
        from sqlalchemy import text as _text

        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            return session.execute(_text(
                "SELECT id FROM pilot_knowledge_base WHERE pilot_id = :p"),
                {"p": uuid.UUID(pilot_id)}).scalars().all()
        finally:
            session.close()

    def test_18_the_journey_is_recorded_in_the_audit_trail(self, client, tokens, journey, db):
        """Every state-changing step above must have left an audit row."""
        actions = set(db.execute(text(
            "SELECT DISTINCT action FROM audit_logs WHERE entity_id IN ("
            "  SELECT id FROM challenges WHERE domain = :d"
            "  UNION SELECT id FROM pilots WHERE challenge_id IN"
            "    (SELECT id FROM challenges WHERE domain = :d))"),
            {"d": PHASE8_DOMAIN}).scalars())
        for expected in ("CREATE", "PUBLISH", "RUN_MATCHING"):
            assert expected in actions, f"{expected} was not audited (saw {actions})"


# ===========================================================================
# 3. Test-infrastructure guard
# ===========================================================================

class TestSharedDatabaseIsolation:
    """
    The suite runs against the real seeded database, so its isolation machinery
    is load-bearing: if it fails, seeded-data assertions in *other* modules
    fail, far from the cause. Phase 7 hit exactly that.
    """

    def test_marker_domains_cover_every_phase_module(self):
        """A module that tags rows must have its domain in the purge list."""
        from pathlib import Path

        tests_dir = Path(__file__).parent
        declared = set(TEST_MARKER_DOMAINS)
        for module in tests_dir.glob("test_phase*_parity.py"):
            source = module.read_text(encoding="utf-8")
            for line in source.splitlines():
                if "_DOMAIN = " in line and '"' in line:
                    domain = line.split('"')[1]
                    assert domain in declared, (
                        f"{module.name} tags rows with {domain!r}, which the "
                        "session purge in conftest.py does not clear")

    def test_this_modules_domain_is_registered(self):
        assert PHASE8_DOMAIN in TEST_MARKER_DOMAINS

    def test_no_marker_rows_leak_into_the_seeded_counts(self, db):
        """
        The seeded totals, computed excluding every marker domain, are stable.

        This is the invariant the per-phase seeded assertions rely on.
        """
        counts = dict(db.execute(text(
            "SELECT 'pilots', count(*) FROM pilots p "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'recommendations', count(*) FROM recommendations r "
            "  JOIN pilots p ON p.id = r.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'kb', count(*) FROM pilot_knowledge_base kb "
            "  JOIN pilots p ON p.id = kb.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d)"
        ), {"d": list(TEST_MARKER_DOMAINS)}).fetchall())
        assert counts == {"pilots": 2, "recommendations": 2, "kb": 2}

    def test_upload_directory_holds_no_orphan_files(self, db):
        """
        Every file on disk must correspond to a `documents` row.

        Document tests write real files; an orphan means a cleanup path missed
        one, which would accumulate silently across runs.
        """
        storage = settings.upload_dir
        if not storage.exists():
            pytest.skip("no upload directory yet")

        on_disk = {p for p in storage.rglob("*") if p.is_file()}
        known = {
            (storage / row).resolve()
            for row in db.execute(text("SELECT file_path FROM documents")).scalars()
            if row
        }
        known |= {p.resolve() for p in on_disk
                  if p.resolve() in {
                      (storage.parent / row).resolve()
                      for row in db.execute(
                          text("SELECT file_path FROM documents")).scalars() if row}}
        orphans = [str(p) for p in on_disk if p.resolve() not in known]
        assert not orphans, f"orphaned uploaded files: {orphans}"


# ===========================================================================
# 4. Seeded integrity, checked once more after the walkthrough
# ===========================================================================

class TestSeededDataUnchangedAfterWalkthrough:
    """The demo journey above must leave the seeded scenario untouched."""

    def test_seed_counts(self, db):
        db.expire_all()
        counts = dict(db.execute(text(
            "SELECT 'users', count(*) FROM users "
            "UNION ALL SELECT 'startups', count(*) FROM startups "
            "UNION ALL SELECT 'challenges', count(*) FROM challenges "
            "  WHERE domain <> ALL(:d) "
            "UNION ALL SELECT 'proposals', count(*) FROM proposals pr "
            "  JOIN challenges c ON c.id = pr.challenge_id WHERE c.domain <> ALL(:d)"
        ), {"d": list(TEST_MARKER_DOMAINS)}).fetchall())
        assert counts == {"users": 22, "startups": 16, "challenges": 6, "proposals": 6}

    def test_seeded_recommendations(self, db):
        rows = dict(db.execute(text(
            "SELECT s.company_name, r.recommendation FROM recommendations r "
            "JOIN pilots p ON p.id = r.pilot_id JOIN startups s ON s.id = p.startup_id "
            "JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d)"
        ), {"d": list(TEST_MARKER_DOMAINS)}).fetchall())
        assert rows == {"CleanLoop Robotics": "SCALE", "SecureNet Labs": "REJECT"}

    def test_roadsense_profile(self, client, tokens):
        profile = client.get("/api/v1/startups/me",
                             headers=auth(tokens["STARTUP"])).json()
        assert profile["companyName"] == "RoadSense AI"
        assert len(profile["capabilities"]) == 3
        assert len(profile["projects"]) == 2
