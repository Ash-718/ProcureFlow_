"""
Phase 4 gate: auth / challenge / startup routers, checked against Spring.

Two kinds of test here:

* **Behaviour tests** run against the FastAPI app and assert the ported rules —
  status codes, RBAC, ownership, draft visibility, the publish preconditions.
* **Parity tests** issue the *same request* to both backends and diff the
  responses. Those are the ones that catch a rule that was reimplemented
  slightly differently rather than ported.

Everything is read-only against seeded data **except** the write-path tests,
which create their own throwaway rows (a registered account, a draft challenge)
and never touch a seeded record. The RoadSense/pothole scenario is asserted
intact at the end.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.database import SessionLocal, check_connection
from app.main import app
from app.models import Challenge, ChallengeStatus, Startup, User
from app.security.jwt import create_access_token

SPRING = "http://127.0.0.1:8001"
DEMO_PASSWORD = "Demo@123"

#: Tags every row a test creates, so cleanup can find them by value rather
#: than by an id that may never have been captured.
MARKER_DOMAIN = "phase4-testing"

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


def _spring_is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{SPRING}/health", timeout=3) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


spring_required = pytest.mark.skipif(
    not _spring_is_up(),
    reason="Spring reference backend is not running on :8001.",
)


def spring_request(path: str, *, token: str | None = None, method: str = "GET",
                   body: dict | None = None) -> tuple[int, Any]:
    request = urllib.request.Request(f"{SPRING}{path}", method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    payload = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, payload, timeout=20) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


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


@pytest.fixture(scope="module", autouse=True)
def _clean_marker_rows(db):
    """
    Guarantee the seeded data is pristine either side of this module.

    Other suites diff the seeded startup and challenges against recorded Spring
    fixtures, so a row leaked from here fails them rather than this one — which
    makes the failure hard to attribute. Purging on both entry and exit keeps
    that from happening even after an aborted run.
    """
    purge_marker_rows(db)
    yield
    purge_marker_rows(db)


@pytest.fixture(scope="module")
def tokens(db) -> dict[str, str]:
    """A token per demo role, minted locally to avoid Spring's rate limiter."""
    issued = {}
    for role, email in ACCOUNTS.items():
        user = db.execute(select(User).where(User.email == email)).scalars().one()
        issued[role] = create_access_token(user.id, user.email, user.role.name.value)
    return issued


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def purge_marker_rows(db, startup_id: uuid.UUID | None = None) -> None:
    """
    Remove every row a test tagged with `MARKER_DOMAIN`.

    Value-keyed rather than id-keyed so it works even when a test aborted
    before recording what it created.
    """
    db.rollback()
    db.execute(text("DELETE FROM startup_capabilities WHERE domain_tag = :d"),
               {"d": MARKER_DOMAIN})
    db.execute(text("DELETE FROM startup_projects WHERE domain = :d"),
               {"d": MARKER_DOMAIN})
    db.execute(text(
        "DELETE FROM evaluation_criteria WHERE challenge_id IN "
        "(SELECT id FROM challenges WHERE domain = :d)"), {"d": MARKER_DOMAIN})
    db.execute(text(
        "DELETE FROM challenge_requirements WHERE challenge_id IN "
        "(SELECT id FROM challenges WHERE domain = :d)"), {"d": MARKER_DOMAIN})
    db.execute(text(
        "DELETE FROM challenge_kpis WHERE challenge_id IN "
        "(SELECT id FROM challenges WHERE domain = :d)"), {"d": MARKER_DOMAIN})
    db.execute(text(
        "DELETE FROM audit_logs WHERE entity_id IN "
        "(SELECT id FROM challenges WHERE domain = :d)"), {"d": MARKER_DOMAIN})
    db.execute(text("DELETE FROM challenges WHERE domain = :d"), {"d": MARKER_DOMAIN})
    if startup_id is not None:
        db.execute(text("DELETE FROM audit_logs WHERE entity_id = :sid"),
                   {"sid": startup_id})
    db.commit()


# ===========================================================================
# Auth
# ===========================================================================

class TestAuthEndpoints:
    def test_login_returns_the_contract_shape(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "government@demo.com", "password": DEMO_PASSWORD})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"token", "userId", "email", "fullName", "role"}
        assert body["email"] == "government@demo.com"
        assert body["role"] == "GOVERNMENT"
        assert body["fullName"] == "Anita Deshmukh"

    def test_login_is_case_insensitive_on_email(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "  GOVERNMENT@Demo.COM  ", "password": DEMO_PASSWORD})
        assert response.status_code == 200

    def test_wrong_password_is_401_with_the_generic_message(self, client):
        response = client.post("/api/v1/auth/login", json={
            "email": "government@demo.com", "password": "wrong"})
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid email or password"

    def test_unknown_email_is_indistinguishable_from_a_wrong_password(self, client):
        """Identical status and message, or the endpoint enumerates accounts."""
        unknown = client.post("/api/v1/auth/login", json={
            "email": "nobody@nowhere.test", "password": "whatever1"})
        wrong = client.post("/api/v1/auth/login", json={
            "email": "government@demo.com", "password": "wrongpass"})
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["message"] == wrong.json()["message"]

    def test_me_returns_the_caller(self, client, tokens):
        body = client.get("/api/v1/auth/me", headers=auth(tokens["EXPERT"])).json()
        assert set(body) == {"id", "email", "fullName", "role"}
        assert body["role"] == "EXPERT"

    @pytest.mark.parametrize("role", ["ADMIN", "EXPERT"])
    def test_privileged_roles_cannot_self_register(self, client, role):
        response = client.post("/api/v1/auth/register", json={
            "email": f"newbie-{uuid.uuid4().hex[:8]}@test.local",
            "password": "Password123", "fullName": "Test User", "role": role})
        assert response.status_code == 403
        assert "provisioned by an administrator" in response.json()["message"]

    def test_duplicate_email_is_409(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "government@demo.com", "password": "Password123",
            "fullName": "Impostor", "role": "GOVERNMENT",
            "departmentName": "Fake Department"})
        assert response.status_code == 409
        assert response.json()["message"] == "An account with this email already exists"

    def test_startup_registration_requires_company_name(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": f"s-{uuid.uuid4().hex[:8]}@test.local",
            "password": "Password123", "fullName": "Founder", "role": "STARTUP"})
        assert response.status_code == 400
        assert "companyName is required" in response.json()["message"]

    def test_government_registration_requires_department_name(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": f"g-{uuid.uuid4().hex[:8]}@test.local",
            "password": "Password123", "fullName": "Officer", "role": "GOVERNMENT"})
        assert response.status_code == 400
        assert "departmentName is required" in response.json()["message"]

    def test_short_password_is_a_400_with_field_errors(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": f"x-{uuid.uuid4().hex[:8]}@test.local", "password": "short",
            "fullName": "X", "role": "STARTUP", "companyName": "X Ltd"})
        assert response.status_code == 400
        assert response.json()["fieldErrors"]


@pytest.mark.usefixtures("db")
class TestRegistrationWritePath:
    """
    Exercises the full registration path, then removes what it created.

    Cleanup is by primary key on rows this test inserted, so no seeded record
    can be affected.
    """

    def test_startup_registration_creates_profile_and_audit_row(self, client, db):
        email = f"phase4-{uuid.uuid4().hex[:10]}@test.local"
        response = client.post("/api/v1/auth/register", json={
            "email": email, "password": "Password123",
            "fullName": "Phase Four Tester", "role": "STARTUP",
            "companyName": "Phase Four Robotics"})
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["email"] == email
        assert body["role"] == "STARTUP"
        assert body["token"]

        user_id = uuid.UUID(body["userId"])
        try:
            db.expire_all()
            user = db.get(User, user_id)
            assert user is not None and user.is_active
            assert user.password_hash.startswith("$2b$10$")

            startup = db.execute(
                select(Startup).where(Startup.user_id == user_id)).scalars().one()
            assert startup.company_name == "Phase Four Robotics"
            assert float(startup.readiness_score) == 50.0

            audit = db.execute(text(
                "SELECT action, entity_type, metadata_json FROM audit_logs "
                "WHERE actor_user_id = :uid"), {"uid": user_id}).fetchall()
            assert ("REGISTER", "User") in [(a, e) for a, e, _ in audit]
            assert any(m and "STARTUP" in m for _, _, m in audit)

            # The new account can immediately authenticate.
            login = client.post("/api/v1/auth/login",
                                json={"email": email, "password": "Password123"})
            assert login.status_code == 200
        finally:
            db.execute(text("DELETE FROM audit_logs WHERE actor_user_id = :uid"),
                       {"uid": user_id})
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
            db.commit()


# ===========================================================================
# Challenges
# ===========================================================================

class TestChallengeVisibility:
    def test_government_sees_only_its_own_department(self, client, tokens, db):
        body = client.get("/api/v1/challenges", headers=auth(tokens["GOVERNMENT"])).json()
        assert isinstance(body, list) and body

        gov = db.execute(
            select(User).where(User.email == ACCOUNTS["GOVERNMENT"])).scalars().one()
        department_id = str(gov.department.id)
        assert all(c["departmentId"] == department_id for c in body)

    def test_admin_sees_every_challenge(self, client, tokens, db):
        body = client.get("/api/v1/challenges", headers=auth(tokens["ADMIN"])).json()
        total = db.execute(select(Challenge)).scalars().all()
        assert len(body) == len(total)

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_others_never_see_drafts(self, client, tokens, role):
        body = client.get("/api/v1/challenges", headers=auth(tokens[role])).json()
        assert all(c["status"] != "DRAFT" for c in body)

    def test_startup_cannot_read_another_departments_draft(self, client, tokens, db):
        """A draft must 404 for a non-owner, not 403 — existence is confidential."""
        draft = db.execute(
            select(Challenge).where(Challenge.status == ChallengeStatus.DRAFT)
        ).scalars().first()
        if draft is None:
            pytest.skip("no DRAFT challenge in the seed data")
        response = client.get(f"/api/v1/challenges/{draft.id}",
                              headers=auth(tokens["STARTUP"]))
        assert response.status_code == 404
        assert response.json()["message"] == "Challenge not found"

    def test_unknown_challenge_is_404(self, client, tokens):
        response = client.get(f"/api/v1/challenges/{uuid.uuid4()}",
                              headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 404

    def test_write_endpoints_reject_non_government_with_403(self, client, tokens):
        for role in ("STARTUP", "EXPERT"):
            response = client.post("/api/v1/challenges", headers=auth(tokens[role]),
                                   json={"title": "x", "problemStatement": "x",
                                         "domain": "x", "requirements": [], "kpis": []})
            assert response.status_code == 403, role


class TestChallengeLifecycle:
    """Create -> update -> publish, on a challenge this test owns and removes."""

    def test_full_lifecycle(self, client, tokens, db):
        draft_payload = {
            "title": "Phase 4 Parity Challenge",
            "problemStatement": "Verifying the ported challenge lifecycle.",
            "desiredTechnology": "Computer Vision, IoT",
            "domain": MARKER_DOMAIN,
            "outcomesExpected": "A verified port.",
            "budgetRange": "INR 1 - 2 lakh",
            "timelineDays": 30,
            "requirements": [
                {"requirementType": "ELIGIBILITY",
                 "description": "DPIIT-recognised startup", "mandatory": True},
            ],
            "kpis": [
                {"kpiName": "Parity", "targetValue": 100, "unit": "percent",
                 "weight": 1.0},
            ],
        }

        try:
            created = client.post("/api/v1/challenges",
                                  headers=auth(tokens["GOVERNMENT"]),
                                  json=draft_payload)
            assert created.status_code == 201, created.text
            body = created.json()
            challenge_id = body["id"]
            assert body["status"] == "DRAFT"
            assert body["publishedAt"] is None
            assert body["title"] == draft_payload["title"]
            assert len(body["requirements"]) == 1
            assert body["requirements"][0]["mandatory"] is True
            assert len(body["kpis"]) == 1
            assert body["kpis"][0]["targetValue"] == 100.0
            assert body["departmentName"]

            # --- update replaces the collections wholesale -----------------
            updated_payload = dict(draft_payload)
            updated_payload["title"] = "Phase 4 Parity Challenge (edited)"
            updated_payload["requirements"] = [
                {"requirementType": "TECHNICAL",
                 "description": "Runs on existing hardware", "mandatory": False},
                {"requirementType": "COMPLIANCE",
                 "description": "Data stays in India", "mandatory": True},
            ]
            updated = client.put(f"/api/v1/challenges/{challenge_id}",
                                 headers=auth(tokens["GOVERNMENT"]),
                                 json=updated_payload)
            assert updated.status_code == 200, updated.text
            assert updated.json()["title"].endswith("(edited)")
            assert len(updated.json()["requirements"]) == 2
            assert updated.json()["status"] == "DRAFT"

            # --- a startup still cannot see the draft ----------------------
            assert client.get(f"/api/v1/challenges/{challenge_id}",
                              headers=auth(tokens["STARTUP"])).status_code == 404

            # --- publish ---------------------------------------------------
            published = client.post(f"/api/v1/challenges/{challenge_id}/publish",
                                    headers=auth(tokens["GOVERNMENT"]))
            assert published.status_code == 200, published.text
            assert published.json()["status"] == "PUBLISHED"
            assert published.json()["publishedAt"] is not None

            # --- the default rubric was seeded -----------------------------
            criteria = db.execute(text(
                "SELECT criterion_name, weight, max_score FROM evaluation_criteria "
                "WHERE challenge_id = :cid ORDER BY criterion_name"),
                {"cid": uuid.UUID(challenge_id)}).fetchall()
            assert len(criteria) == 4
            assert {row[0] for row in criteria} == {
                "Technical Feasibility", "Cost Effectiveness",
                "Scalability", "Team Capability"}
            assert sum(float(row[1]) for row in criteria) == pytest.approx(1.00)
            assert all(float(row[2]) == 10.0 for row in criteria)

            # --- now visible to a startup ----------------------------------
            assert client.get(f"/api/v1/challenges/{challenge_id}",
                              headers=auth(tokens["STARTUP"])).status_code == 200

            # --- a published challenge can no longer be edited -------------
            conflict = client.put(f"/api/v1/challenges/{challenge_id}",
                                  headers=auth(tokens["GOVERNMENT"]),
                                  json=updated_payload)
            assert conflict.status_code == 409
            assert "DRAFT" in conflict.json()["message"]

            assert client.post(f"/api/v1/challenges/{challenge_id}/publish",
                               headers=auth(tokens["GOVERNMENT"])).status_code == 409
        finally:
            purge_marker_rows(db)

    def test_publish_requires_at_least_one_requirement(self, client, tokens, db):
        try:
            created = client.post("/api/v1/challenges",
                                  headers=auth(tokens["GOVERNMENT"]),
                                  json={"title": "No requirements",
                                        "problemStatement": "x",
                                        "domain": MARKER_DOMAIN,
                                        "requirements": [], "kpis": []})
            assert created.status_code == 201
            challenge_id = uuid.UUID(created.json()["id"])
            response = client.post(f"/api/v1/challenges/{challenge_id}/publish",
                                   headers=auth(tokens["GOVERNMENT"]))
            assert response.status_code == 400
            assert "at least one" in response.json()["message"]
        finally:
            purge_marker_rows(db)


# ===========================================================================
# Startups
# ===========================================================================

class TestStartupEndpoints:
    def test_startup_reads_its_own_profile(self, client, tokens):
        body = client.get("/api/v1/startups/me", headers=auth(tokens["STARTUP"])).json()
        assert body["companyName"] == "RoadSense AI"
        assert body["capabilities"] and body["projects"]
        assert isinstance(body["readinessScore"], float)

    @pytest.mark.parametrize("role", ["GOVERNMENT", "EXPERT", "ADMIN"])
    def test_directory_is_open_to_reviewers(self, client, tokens, role, db):
        body = client.get("/api/v1/startups", headers=auth(tokens[role])).json()
        assert len(body) == len(db.execute(select(Startup)).scalars().all())

    def test_startup_cannot_read_the_directory(self, client, tokens):
        assert client.get("/api/v1/startups",
                          headers=auth(tokens["STARTUP"])).status_code == 403

    def test_unknown_startup_is_404(self, client, tokens):
        response = client.get(f"/api/v1/startups/{uuid.uuid4()}",
                              headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 404
        assert response.json()["message"] == "Startup not found"

    def test_capability_and_project_round_trip(self, client, tokens, db):
        """
        Add a capability and a project, then remove them.

        Both endpoints return the whole profile and 200 (not 201), matching the
        Java controller; the delete returns 204.
        """
        before = client.get("/api/v1/startups/me", headers=auth(tokens["STARTUP"])).json()
        capability_count = len(before["capabilities"])
        project_count = len(before["projects"])
        startup_id = uuid.UUID(before["id"])

        # The whole body is guarded, and cleanup is keyed on the marker tag
        # rather than on ids captured mid-test. An assertion that fires before
        # an id is captured must still leave the seeded profile untouched —
        # other suites diff this startup against a recorded fixture, so a
        # single leaked row fails them.
        try:
            added = client.post("/api/v1/startups/me/capabilities",
                                headers=auth(tokens["STARTUP"]),
                                json={"technologyTag": "Phase4 Testing",
                                      "domainTag": MARKER_DOMAIN,
                                      "proficiencyLevel": 4,
                                      "description": "Temporary parity-test capability"})
            assert added.status_code == 200, added.text
            assert len(added.json()["capabilities"]) == capability_count + 1
            capability_id = next(
                c["id"] for c in added.json()["capabilities"]
                if c["technologyTag"] == "Phase4 Testing")

            project = client.post("/api/v1/startups/me/projects",
                                  headers=auth(tokens["STARTUP"]),
                                  json={"title": "Phase 4 Parity Project",
                                        "domain": MARKER_DOMAIN,
                                        "clientType": "GOVERNMENT", "year": 2026})
            assert project.status_code == 200
            assert len(project.json()["projects"]) == project_count + 1

            deleted = client.delete(f"/api/v1/startups/me/capabilities/{capability_id}",
                                    headers=auth(tokens["STARTUP"]))
            assert deleted.status_code == 204
            assert deleted.content == b""

            after = client.get("/api/v1/startups/me",
                               headers=auth(tokens["STARTUP"])).json()
            assert len(after["capabilities"]) == capability_count
        finally:
            purge_marker_rows(db, startup_id)

    def test_deleting_a_foreign_capability_is_a_no_op(self, client, tokens, db):
        """
        Idempotent and scoped: a random id changes nothing and still returns
        204, so the endpoint cannot be used to probe for capability ids.
        """
        before = client.get("/api/v1/startups/me", headers=auth(tokens["STARTUP"])).json()
        response = client.delete(f"/api/v1/startups/me/capabilities/{uuid.uuid4()}",
                                 headers=auth(tokens["STARTUP"]))
        assert response.status_code == 204
        after = client.get("/api/v1/startups/me", headers=auth(tokens["STARTUP"])).json()
        assert len(after["capabilities"]) == len(before["capabilities"])

    def test_capability_proficiency_is_bounded(self, client, tokens):
        """The 1-5 CHECK constraint surfaces as a 400, not a database error."""
        for level in (0, 6, -1):
            response = client.post("/api/v1/startups/me/capabilities",
                                   headers=auth(tokens["STARTUP"]),
                                   json={"technologyTag": "X", "domainTag": "Y",
                                         "proficiencyLevel": level})
            assert response.status_code == 400, level
            assert response.json()["fieldErrors"]


# ===========================================================================
# Spring-vs-Python parity
# ===========================================================================

@spring_required
class TestSpringParity:
    """The same request to both backends must produce the same response."""

    @staticmethod
    def _compare(python_body, spring_body, *, label: str,
                 ignore: set[str] = frozenset()) -> None:
        assert type(python_body) is type(spring_body), (
            f"{label}: python returned {type(python_body).__name__}, "
            f"spring returned {type(spring_body).__name__}")
        if isinstance(python_body, dict):
            assert set(python_body) == set(spring_body), (
                f"{label}: key mismatch — "
                f"only python {sorted(set(python_body) - set(spring_body))}, "
                f"only spring {sorted(set(spring_body) - set(python_body))}")
            for key in spring_body:
                if key in ignore:
                    continue
                TestSpringParity._compare(python_body[key], spring_body[key],
                                          label=f"{label}.{key}", ignore=ignore)
        elif isinstance(python_body, list):
            assert len(python_body) == len(spring_body), (
                f"{label}: length {len(python_body)} vs {len(spring_body)}")
        else:
            assert python_body == spring_body, (
                f"{label}: python={python_body!r} spring={spring_body!r}")

    def test_auth_me_matches(self, client, tokens):
        mine = client.get("/api/v1/auth/me", headers=auth(tokens["GOVERNMENT"])).json()
        status, theirs = spring_request("/api/v1/auth/me", token=tokens["GOVERNMENT"])
        if status == 429:
            pytest.skip("Spring auth rate limit exhausted")
        assert status == 200
        self._compare(mine, theirs, label="auth/me")

    @pytest.mark.parametrize("role", ["GOVERNMENT", "STARTUP", "EXPERT", "ADMIN"])
    def test_challenge_list_matches(self, client, tokens, role):
        """
        Role-scoped visibility must agree exactly.

        Compared as sorted id lists: ordering is not part of the contract, but
        *which* challenges each role can see very much is.
        """
        mine = client.get("/api/v1/challenges", headers=auth(tokens[role])).json()
        status, theirs = spring_request("/api/v1/challenges", token=tokens[role])
        assert status == 200, theirs

        assert sorted(c["id"] for c in mine) == sorted(c["id"] for c in theirs), (
            f"{role}: different challenges visible")
        assert sorted((c["id"], c["status"]) for c in mine) == \
               sorted((c["id"], c["status"]) for c in theirs)

    def test_challenge_detail_matches_field_for_field(self, client, tokens, db):
        challenge = db.execute(
            select(Challenge).where(Challenge.status != ChallengeStatus.DRAFT)
        ).scalars().first()
        assert challenge is not None

        mine = client.get(f"/api/v1/challenges/{challenge.id}",
                          headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(f"/api/v1/challenges/{challenge.id}",
                                        token=tokens["ADMIN"])
        assert status == 200
        self._compare(mine, theirs, label="challenge",
                      ignore={"requirements", "kpis"})

        for collection in ("requirements", "kpis"):
            by_id = {item["id"]: item for item in theirs[collection]}
            assert len(mine[collection]) == len(by_id)
            for item in mine[collection]:
                self._compare(item, by_id[item["id"]], label=collection)

    def test_startup_detail_matches_field_for_field(self, client, tokens, db):
        startup = db.execute(
            select(Startup).where(Startup.company_name == "RoadSense AI")
        ).scalars().one()

        mine = client.get(f"/api/v1/startups/{startup.id}",
                          headers=auth(tokens["GOVERNMENT"])).json()
        status, theirs = spring_request(f"/api/v1/startups/{startup.id}",
                                        token=tokens["GOVERNMENT"])
        assert status == 200
        self._compare(mine, theirs, label="startup",
                      ignore={"capabilities", "projects"})

        for collection in ("capabilities", "projects"):
            by_id = {item["id"]: item for item in theirs[collection]}
            assert len(mine[collection]) == len(by_id)
            for item in mine[collection]:
                self._compare(item, by_id[item["id"]], label=collection)

    def test_startup_list_matches(self, client, tokens):
        mine = client.get("/api/v1/startups", headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request("/api/v1/startups", token=tokens["ADMIN"])
        assert status == 200
        assert sorted(s["id"] for s in mine) == sorted(s["id"] for s in theirs)

    def test_startup_me_matches(self, client, tokens):
        mine = client.get("/api/v1/startups/me", headers=auth(tokens["STARTUP"])).json()
        status, theirs = spring_request("/api/v1/startups/me", token=tokens["STARTUP"])
        assert status == 200
        self._compare(mine, theirs, label="startups/me",
                      ignore={"capabilities", "projects"})

    @pytest.mark.parametrize(("path", "role", "expected"), [
        ("/api/v1/startups", "STARTUP", 403),
        ("/api/v1/startups/me", "GOVERNMENT", 403),
        ("/api/v1/startups/me", "EXPERT", 403),
    ])
    def test_rbac_rejections_agree(self, client, tokens, path, role, expected):
        mine = client.get(path, headers=auth(tokens[role]))
        status, _ = spring_request(path, token=tokens[role])
        assert mine.status_code == expected
        assert status == expected, (
            f"{path} as {role}: python={mine.status_code} spring={status}")

    def test_not_found_status_and_message_agree(self, client, tokens):
        missing = uuid.uuid4()
        mine = client.get(f"/api/v1/challenges/{missing}",
                          headers=auth(tokens["GOVERNMENT"]))
        status, theirs = spring_request(f"/api/v1/challenges/{missing}",
                                        token=tokens["GOVERNMENT"])
        assert mine.status_code == status == 404
        assert mine.json()["message"] == theirs["message"] == "Challenge not found"

    def test_login_responses_agree(self, client):
        payload = {"email": "expert@demo.com", "password": DEMO_PASSWORD}
        mine = client.post("/api/v1/auth/login", json=payload).json()
        status, theirs = spring_request("/api/v1/auth/login", method="POST", body=payload)
        if status == 429:
            pytest.skip("Spring auth rate limit exhausted")
        assert status == 200
        # Tokens differ only by `iat`; every identity field must match.
        for key in ("userId", "email", "fullName", "role"):
            assert mine[key] == theirs[key], key
        assert set(mine) == set(theirs)


# ===========================================================================
# Demo scenario integrity
# ===========================================================================

class TestDemoScenarioIntact:
    def test_roadsense_and_pothole_challenge_unchanged(self, client, tokens, db):
        """Phase 4 must leave the SIH walkthrough exactly as it was."""
        startup = client.get("/api/v1/startups/me",
                             headers=auth(tokens["STARTUP"])).json()
        assert startup["companyName"] == "RoadSense AI"
        assert any("Computer Vision" in c["technologyTag"]
                   for c in startup["capabilities"])

        challenges = client.get("/api/v1/challenges",
                                headers=auth(tokens["ADMIN"])).json()
        pothole = [c for c in challenges if "pothole" in c["title"].lower()]
        assert pothole, "the pothole challenge is missing"
        assert pothole[0]["kpis"], "the pothole challenge lost its KPIs"

    def test_seed_row_counts_unchanged(self, db):
        db.expire_all()
        counts = dict(db.execute(text(
            "SELECT 'users', count(*) FROM users "
            "UNION ALL SELECT 'startups', count(*) FROM startups "
            "UNION ALL SELECT 'challenges', count(*) FROM challenges "
            "UNION ALL SELECT 'proposals', count(*) FROM proposals "
            "UNION ALL SELECT 'pilots', count(*) FROM pilots"
        )).fetchall())
        assert counts["users"] == 22
        assert counts["startups"] == 16
        assert counts["challenges"] == 6
        assert counts["proposals"] == 6
        assert counts["pilots"] == 2
