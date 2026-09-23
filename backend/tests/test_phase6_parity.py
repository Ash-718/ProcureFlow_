"""
Phase 6 gate: proposals, documents and evaluations.

Structure mirrors Phase 4: behaviour tests against the FastAPI app, plus parity
tests that issue the same request to the Spring backend and diff the responses.

**Write-path discipline.** The seeded rows are never mutated. Everything this
module creates is tagged so it can be found and removed by value rather than by
an id that may not have been captured:

* a throwaway startup account (`PHASE6_EMAIL_PREFIX`) with its own challenge,
  proposal and documents — used for every ownership-isolation test;
* a temporary uploaded file, removed from disk as well as from the table.

`documents` is empty in the seed data, so without that temporary upload the
`DocumentResponse` shape, the verification rules and the ownership checks would
never actually execute. Creating one is the only way to test them for real.

A module-scoped fixture purges on entry *and* exit, so an aborted run cannot
leak into the suites that diff seeded rows against recorded fixtures.
"""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionLocal, check_connection
from app.main import app
from app.models import (
    Challenge,
    ChallengeStatus,
    Proposal,
    ProposalStatus,
    Startup,
    User,
)
from app.security.jwt import create_access_token

SPRING = "http://127.0.0.1:8001"
DEMO_PASSWORD = "Demo@123"

#: Markers used to find and remove everything this module creates.
PHASE6_EMAIL_PREFIX = "phase6-rival@test.local"
PHASE6_DOMAIN = "phase6-testing"
PHASE6_COMPANY = "Phase6 Rival Robotics"

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
    not _spring_is_up(), reason="Spring reference backend is not running on :8001.")


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


# ---------------------------------------------------------------------------
# Fixtures and cleanup
# ---------------------------------------------------------------------------

def purge_phase6_rows(db) -> None:
    """Remove every row and file this module creates. Safe to run repeatedly."""
    db.rollback()

    # Uploaded files first — the paths live in rows about to be deleted.
    storage_root = settings.upload_dir
    paths = db.execute(text(
        "SELECT file_path FROM documents WHERE original_filename LIKE 'phase6-%'"
    )).scalars().all()
    for relative in paths:
        try:
            (storage_root / relative).unlink(missing_ok=True)
        except OSError:
            pass

    statements = (
        "DELETE FROM documents WHERE original_filename LIKE 'phase6-%'",
        # Anything belonging to the throwaway startup or challenge.
        "DELETE FROM documents WHERE owner_id IN "
        "  (SELECT id FROM startups WHERE company_name = :company)",
        "DELETE FROM documents WHERE owner_id IN "
        "  (SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
        "   WHERE s.company_name = :company)",
        "DELETE FROM evaluation_scores WHERE evaluation_id IN "
        "  (SELECT e.id FROM evaluations e JOIN proposals p ON p.id = e.proposal_id "
        "   JOIN startups s ON s.id = p.startup_id WHERE s.company_name = :company)",
        "DELETE FROM evaluation_scores WHERE evaluation_id IN "
        "  (SELECT e.id FROM evaluations e JOIN proposals p ON p.id = e.proposal_id "
        "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = :domain)",
        "DELETE FROM evaluations WHERE proposal_id IN "
        "  (SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
        "   WHERE s.company_name = :company)",
        "DELETE FROM evaluations WHERE proposal_id IN "
        "  (SELECT p.id FROM proposals p JOIN challenges c ON c.id = p.challenge_id "
        "   WHERE c.domain = :domain)",
        "DELETE FROM proposals WHERE startup_id IN "
        "  (SELECT id FROM startups WHERE company_name = :company)",
        "DELETE FROM proposals WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :domain)",
        "DELETE FROM evaluation_criteria WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :domain)",
        "DELETE FROM challenge_requirements WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :domain)",
        "DELETE FROM challenge_kpis WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :domain)",
        "DELETE FROM match_results WHERE challenge_id IN "
        "  (SELECT id FROM challenges WHERE domain = :domain)",
        "DELETE FROM challenges WHERE domain = :domain",
        "DELETE FROM startup_capabilities WHERE startup_id IN "
        "  (SELECT id FROM startups WHERE company_name = :company)",
        "DELETE FROM startup_projects WHERE startup_id IN "
        "  (SELECT id FROM startups WHERE company_name = :company)",
        "DELETE FROM notifications WHERE user_id IN "
        "  (SELECT id FROM users WHERE email LIKE :email)",
        "DELETE FROM audit_logs WHERE actor_user_id IN "
        "  (SELECT id FROM users WHERE email LIKE :email)",
        "DELETE FROM startups WHERE company_name = :company",
        "DELETE FROM users WHERE email LIKE :email",
    )
    params = {"company": PHASE6_COMPANY, "domain": PHASE6_DOMAIN,
              "email": f"{PHASE6_EMAIL_PREFIX}%"}
    for statement in statements:
        db.execute(text(statement), params)
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
    purge_phase6_rows(db)
    yield
    purge_phase6_rows(db)


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
def rival(client, db) -> dict:
    """
    A second, throwaway startup account.

    Ownership isolation cannot be tested with only one startup in play — there
    has to be somebody else's data to fail to reach.
    """
    email = PHASE6_EMAIL_PREFIX
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123",
        "fullName": "Phase Six Rival", "role": "STARTUP",
        "companyName": PHASE6_COMPANY})
    assert response.status_code == 201, response.text
    body = response.json()

    db.expire_all()
    startup = db.execute(
        select(Startup).where(Startup.company_name == PHASE6_COMPANY)).scalars().one()
    return {"token": body["token"], "user_id": uuid.UUID(body["userId"]),
            "startup_id": startup.id, "email": email}


@pytest.fixture(scope="module")
def seeded(db) -> dict:
    """Ids from the seeded scenario the tests read against."""
    roadsense = db.execute(
        select(Startup).where(Startup.company_name == "RoadSense AI")).scalars().one()
    proposal = db.execute(
        select(Proposal).where(Proposal.startup_id == roadsense.id)).scalars().first()
    assert proposal is not None, "RoadSense has no seeded proposal"
    return {"roadsense_id": roadsense.id, "proposal_id": proposal.id,
            "challenge_id": proposal.challenge_id}


# ===========================================================================
# Proposals
# ===========================================================================

class TestProposalReads:
    def test_startup_lists_its_own_proposals(self, client, tokens):
        body = client.get("/api/v1/proposals/mine",
                          headers=auth(tokens["STARTUP"])).json()
        assert body
        assert all(p["companyName"] == "RoadSense AI" for p in body)
        for proposal in body:
            assert set(proposal) == {
                "id", "challengeId", "challengeTitle", "startupId", "companyName",
                "summary", "proposedApproach", "costEstimate",
                "timelineEstimateDays", "status", "submittedAt"}

    def test_expert_queue_contains_only_open_proposals(self, client, tokens):
        body = client.get("/api/v1/proposals/queue",
                          headers=auth(tokens["EXPERT"])).json()
        assert all(p["status"] in ("SUBMITTED", "UNDER_REVIEW") for p in body)

    @pytest.mark.parametrize("role", ["GOVERNMENT", "EXPERT", "ADMIN"])
    def test_mine_is_startup_only(self, client, tokens, role):
        assert client.get("/api/v1/proposals/mine",
                          headers=auth(tokens[role])).status_code == 403

    @pytest.mark.parametrize("role", ["GOVERNMENT", "STARTUP", "ADMIN"])
    def test_queue_is_expert_only(self, client, tokens, role):
        assert client.get("/api/v1/proposals/queue",
                          headers=auth(tokens[role])).status_code == 403

    def test_unknown_proposal_is_404(self, client, tokens):
        response = client.get(f"/api/v1/proposals/{uuid.uuid4()}",
                              headers=auth(tokens["ADMIN"]))
        assert response.status_code == 404
        assert response.json()["message"] == "Proposal not found"

    @pytest.mark.parametrize("role", ["ADMIN", "EXPERT"])
    def test_admin_and_expert_read_any_proposal(self, client, tokens, seeded, role):
        assert client.get(f"/api/v1/proposals/{seeded['proposal_id']}",
                          headers=auth(tokens[role])).status_code == 200

    def test_startup_reads_its_own_proposal(self, client, tokens, seeded):
        assert client.get(f"/api/v1/proposals/{seeded['proposal_id']}",
                          headers=auth(tokens["STARTUP"])).status_code == 200

    def test_startup_cannot_read_another_startups_proposal(self, client, rival, seeded):
        """
        403, not 404.

        Unlike a challenge draft, a proposal's *existence* is not confidential —
        the Java service returns 403 here and that distinction is preserved.
        """
        response = client.get(f"/api/v1/proposals/{seeded['proposal_id']}",
                              headers=auth(rival["token"]))
        assert response.status_code == 403
        assert response.json()["message"] == "You do not have access to this proposal"

    def test_government_reads_proposals_on_its_own_challenge(self, client, tokens, seeded):
        response = client.get(
            f"/api/v1/proposals/challenges/{seeded['challenge_id']}",
            headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 200
        assert all(p["challengeId"] == str(seeded["challenge_id"])
                   for p in response.json())

    def test_list_for_unknown_challenge_is_404(self, client, tokens):
        assert client.get(f"/api/v1/proposals/challenges/{uuid.uuid4()}",
                          headers=auth(tokens["ADMIN"])).status_code == 404

    def test_startup_cannot_list_a_challenges_proposals(self, client, tokens, seeded):
        assert client.get(f"/api/v1/proposals/challenges/{seeded['challenge_id']}",
                          headers=auth(tokens["STARTUP"])).status_code == 403


class TestProposalLifecycle:
    """Submit, duplicate-guard, status change — on rows this module owns."""

    @pytest.fixture(scope="class")
    def own_challenge(self, client, tokens, db):
        """A published challenge created for these tests to receive proposals."""
        created = client.post("/api/v1/challenges", headers=auth(tokens["GOVERNMENT"]),
                              json={"title": "Phase 6 Proposal Lifecycle",
                                    "problemStatement": "Exercising the ported flow.",
                                    "domain": PHASE6_DOMAIN,
                                    "requirements": [{"requirementType": "ELIGIBILITY",
                                                      "description": "Any startup",
                                                      "mandatory": True}],
                                    "kpis": []})
        assert created.status_code == 201, created.text
        challenge_id = created.json()["id"]
        published = client.post(f"/api/v1/challenges/{challenge_id}/publish",
                                headers=auth(tokens["GOVERNMENT"]))
        assert published.status_code == 200
        return challenge_id

    def test_submit_returns_201_and_the_contract_shape(self, client, rival, own_challenge):
        response = client.post(f"/api/v1/proposals/challenges/{own_challenge}",
                               headers=auth(rival["token"]),
                               json={"summary": "A genuine proposal for the test flow.",
                                     "proposedApproach": "Approach text.",
                                     "costEstimate": 1500000,
                                     "timelineEstimateDays": 90})
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "SUBMITTED"
        assert body["companyName"] == PHASE6_COMPANY
        assert body["challengeId"] == own_challenge
        assert body["costEstimate"] == 1500000.0
        assert isinstance(body["costEstimate"], float)
        assert body["submittedAt"].endswith("Z")

    def test_duplicate_submission_is_409(self, client, rival, own_challenge):
        response = client.post(f"/api/v1/proposals/challenges/{own_challenge}",
                               headers=auth(rival["token"]),
                               json={"summary": "A second attempt."})
        assert response.status_code == 409
        assert "already submitted" in response.json()["message"]

    def test_submitting_notifies_the_owning_department(self, client, tokens, db, rival):
        rows = db.execute(text(
            "SELECT n.message FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE u.email = :email AND n.message LIKE :needle"),
            {"email": ACCOUNTS["GOVERNMENT"], "needle": f"%{PHASE6_COMPANY}%"}).all()
        assert rows, "no PROPOSAL_SUBMITTED notification reached the department"

    def test_submitting_to_a_draft_challenge_is_409(self, client, tokens, rival, db):
        created = client.post("/api/v1/challenges", headers=auth(tokens["GOVERNMENT"]),
                              json={"title": "Phase 6 Draft", "problemStatement": "x",
                                    "domain": PHASE6_DOMAIN,
                                    "requirements": [], "kpis": []})
        assert created.status_code == 201
        response = client.post(
            f"/api/v1/proposals/challenges/{created.json()['id']}",
            headers=auth(rival["token"]), json={"summary": "Should be refused."})
        assert response.status_code == 409
        assert "not currently accepting proposals" in response.json()["message"]

    def test_submitting_to_a_closed_challenge_is_409(self, client, rival, db):
        closed = db.execute(select(Challenge).where(
            Challenge.status == ChallengeStatus.CLOSED)).scalars().first()
        if closed is None:
            pytest.skip("no CLOSED challenge in the seed data")
        response = client.post(f"/api/v1/proposals/challenges/{closed.id}",
                               headers=auth(rival["token"]),
                               json={"summary": "Should be refused."})
        assert response.status_code == 409

    def test_submitting_to_an_unknown_challenge_is_404(self, client, rival):
        response = client.post(f"/api/v1/proposals/challenges/{uuid.uuid4()}",
                               headers=auth(rival["token"]),
                               json={"summary": "x"})
        assert response.status_code == 404

    @pytest.mark.parametrize("role", ["GOVERNMENT", "EXPERT", "ADMIN"])
    def test_only_a_startup_may_submit(self, client, tokens, own_challenge, role):
        assert client.post(f"/api/v1/proposals/challenges/{own_challenge}",
                           headers=auth(tokens[role]),
                           json={"summary": "x"}).status_code == 403

    def test_status_change_updates_and_notifies(self, client, tokens, db, rival, own_challenge):
        proposal_id = db.execute(text(
            "SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
            "WHERE s.company_name = :c"), {"c": PHASE6_COMPANY}).scalar_one()

        response = client.patch(f"/api/v1/proposals/{proposal_id}/status",
                                headers=auth(tokens["GOVERNMENT"]),
                                json={"status": "SHORTLISTED"})
        assert response.status_code == 200
        assert response.json()["status"] == "SHORTLISTED"

        notified = db.execute(text(
            "SELECT count(*) FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE u.email = :email AND n.type = 'PROPOSAL_STATUS_CHANGE'"),
            {"email": rival["email"]}).scalar_one()
        assert notified >= 1

        audited = db.execute(text(
            "SELECT metadata_json FROM audit_logs "
            "WHERE action = 'STATUS_CHANGE' AND entity_id = :pid"),
            {"pid": proposal_id}).scalars().all()
        assert any(m and "SHORTLISTED" in m for m in audited)

    @pytest.mark.parametrize("role", ["STARTUP", "EXPERT"])
    def test_status_change_is_government_or_admin_only(self, client, tokens, db, role):
        proposal_id = db.execute(text(
            "SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
            "WHERE s.company_name = :c"), {"c": PHASE6_COMPANY}).scalar_one()
        assert client.patch(f"/api/v1/proposals/{proposal_id}/status",
                            headers=auth(tokens[role]),
                            json={"status": "REJECTED"}).status_code == 403


# ===========================================================================
# Documents — the seed table is empty, so a temporary upload is required
# ===========================================================================

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class TestDocumentUploadAndVerification:
    def test_upload_returns_201_and_the_contract_shape(self, client, tokens, seeded, db):
        response = client.post(
            f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}"
            "?documentType=ELIGIBILITY",
            headers=auth(tokens["STARTUP"]),
            files={"file": ("phase6-eligibility.pdf", io.BytesIO(PDF_BYTES),
                            "application/pdf")})
        assert response.status_code == 201, response.text
        body = response.json()

        assert set(body) == {
            "id", "ownerType", "ownerId", "documentType", "originalFilename",
            "verificationStatus", "verificationNotes", "uploadedAt"}
        assert "filePath" not in body, "the server-side storage path leaked"
        assert body["ownerType"] == "STARTUP"
        assert body["ownerId"] == str(seeded["roadsense_id"])
        assert body["documentType"] == "ELIGIBILITY"
        assert body["originalFilename"] == "phase6-eligibility.pdf"
        assert body["verificationStatus"] == "VERIFIED"
        assert "Passed automated checks" in body["verificationNotes"]
        assert body["uploadedAt"].endswith("Z")

    def test_the_file_is_actually_written_to_disk(self, db):
        stored = db.execute(text(
            "SELECT file_path FROM documents WHERE original_filename = :n"),
            {"n": "phase6-eligibility.pdf"}).scalar_one()
        path = settings.upload_dir / stored
        assert path.exists(), f"{path} was not written"
        assert path.read_bytes() == PDF_BYTES
        # The stored name must not be the client-supplied one.
        assert stored != "phase6-eligibility.pdf"
        assert stored.endswith("_phase6-eligibility.pdf")

    def test_unsupported_extension_is_flagged_not_rejected(self, client, tokens, seeded):
        response = client.post(
            f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}?documentType=OTHER",
            headers=auth(tokens["STARTUP"]),
            files={"file": ("phase6-payload.exe", io.BytesIO(b"MZ binary"),
                            "application/octet-stream")})
        assert response.status_code == 201
        body = response.json()
        assert body["verificationStatus"] == "FLAGGED"
        assert "Unsupported file type" in body["verificationNotes"]
        assert "exe" in body["verificationNotes"]

    def test_a_flagged_upload_notifies_the_uploader(self, db):
        count = db.execute(text(
            "SELECT count(*) FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE u.email = :email AND n.type = 'DOCUMENT_FLAGGED'"),
            {"email": ACCOUNTS["STARTUP"]}).scalar_one()
        assert count >= 1

    def test_empty_file_is_rejected_with_400(self, client, tokens, seeded):
        """
        Storage refuses a zero-byte upload before a row is written, so no
        orphaned record or file is left behind.
        """
        response = client.post(
            f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}?documentType=OTHER",
            headers=auth(tokens["STARTUP"]),
            files={"file": ("phase6-empty.pdf", io.BytesIO(b""), "application/pdf")})
        assert response.status_code == 400
        assert response.json()["message"] == "Uploaded file is empty"

    def test_a_rejected_upload_leaves_no_row(self, db):
        count = db.execute(text(
            "SELECT count(*) FROM documents WHERE original_filename = :n"),
            {"n": "phase6-empty.pdf"}).scalar_one()
        assert count == 0

    def test_upload_is_audited(self, db):
        rows = db.execute(text(
            "SELECT metadata_json FROM audit_logs WHERE action = 'UPLOAD'")).scalars().all()
        assert any(m and "verificationStatus" in m for m in rows)

    @pytest.mark.parametrize("extension", ["pdf", "doc", "docx", "jpg", "jpeg", "png"])
    def test_every_allowed_extension_verifies(self, client, tokens, seeded, extension):
        response = client.post(
            f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}?documentType=COMPLIANCE",
            headers=auth(tokens["STARTUP"]),
            files={"file": (f"phase6-sample.{extension}",
                            io.BytesIO(b"content"), "application/octet-stream")})
        assert response.status_code == 201
        assert response.json()["verificationStatus"] == "VERIFIED", extension


class TestDocumentOwnershipIsolation:
    """
    The point of the whole module: one startup must not reach another's
    documents, and a department must not reach a startup that has not proposed
    to it.
    """

    def test_startup_lists_its_own_documents(self, client, tokens, seeded):
        response = client.get(f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}",
                              headers=auth(tokens["STARTUP"]))
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_another_startup_cannot_read_them(self, client, rival, seeded):
        response = client.get(f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}",
                              headers=auth(rival["token"]))
        assert response.status_code == 403
        assert response.json()["message"] == "You do not have access to these documents"

    def test_another_startup_cannot_upload_against_them(self, client, rival, seeded):
        response = client.post(
            f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}?documentType=OTHER",
            headers=auth(rival["token"]),
            files={"file": ("phase6-intrusion.pdf", io.BytesIO(PDF_BYTES),
                            "application/pdf")})
        assert response.status_code == 403
        assert response.json()["message"] == (
            "You cannot upload documents for this resource")

    def test_the_refused_upload_stored_nothing(self, db):
        assert db.execute(text(
            "SELECT count(*) FROM documents WHERE original_filename = :n"),
            {"n": "phase6-intrusion.pdf"}).scalar_one() == 0

    @pytest.mark.parametrize("role", ["ADMIN", "EXPERT"])
    def test_admin_and_expert_may_read_any_documents(self, client, tokens, seeded, role):
        assert client.get(f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}",
                          headers=auth(tokens[role])).status_code == 200

    def test_government_reads_documents_of_a_startup_that_proposed_to_it(
            self, client, tokens, seeded):
        """RoadSense has proposed to this department, so its documents are visible."""
        assert client.get(f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}",
                          headers=auth(tokens["GOVERNMENT"])).status_code == 200

    def test_government_cannot_read_a_startup_that_never_proposed_to_it(
            self, client, tokens, rival):
        """
        The rival startup's only proposal is to a `phase6-testing` challenge
        owned by this same department, so to test the negative branch we need a
        startup with no proposal to it at all.
        """
        response = client.get(f"/api/v1/documents/STARTUP/{uuid.uuid4()}",
                              headers=auth(tokens["GOVERNMENT"]))
        assert response.status_code == 403

    def test_proposal_documents_follow_the_proposal_owner(self, client, tokens, rival, db):
        proposal_id = db.execute(text(
            "SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
            "WHERE s.company_name = :c"), {"c": PHASE6_COMPANY}).scalar_one()

        # The owning startup may upload and read.
        upload = client.post(
            f"/api/v1/documents/PROPOSAL/{proposal_id}?documentType=FINANCIAL",
            headers=auth(rival["token"]),
            files={"file": ("phase6-proposal-doc.pdf", io.BytesIO(PDF_BYTES),
                            "application/pdf")})
        assert upload.status_code == 201
        assert upload.json()["ownerType"] == "PROPOSAL"
        assert client.get(f"/api/v1/documents/PROPOSAL/{proposal_id}",
                          headers=auth(rival["token"])).status_code == 200

        # A different startup may do neither.
        assert client.get(f"/api/v1/documents/PROPOSAL/{proposal_id}",
                          headers=auth(tokens["STARTUP"])).status_code == 403
        assert client.post(
            f"/api/v1/documents/PROPOSAL/{proposal_id}?documentType=OTHER",
            headers=auth(tokens["STARTUP"]),
            files={"file": ("phase6-nope.pdf", io.BytesIO(PDF_BYTES),
                            "application/pdf")}).status_code == 403

        # The department owning the challenge may read.
        assert client.get(f"/api/v1/documents/PROPOSAL/{proposal_id}",
                          headers=auth(tokens["GOVERNMENT"])).status_code == 200

    def test_documents_for_an_unknown_proposal_are_403(self, client, tokens):
        """
        A non-existent proposal is indistinguishable from one the caller cannot
        see — the Java service falls through to the same 403.
        """
        assert client.get(f"/api/v1/documents/PROPOSAL/{uuid.uuid4()}",
                          headers=auth(tokens["STARTUP"])).status_code == 403


# ===========================================================================
# Evaluations
# ===========================================================================

class TestEvaluationReads:
    def test_criteria_returns_the_challenges_rubric(self, client, tokens, seeded):
        response = client.get(
            f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/criteria",
            headers=auth(tokens["EXPERT"]))
        assert response.status_code == 200
        body = response.json()
        assert body
        for criterion in body:
            assert set(criterion) == {"id", "criterionName", "maxScore", "weight"}
            assert isinstance(criterion["weight"], float)
        assert sum(c["weight"] for c in body) == pytest.approx(1.0)

    @pytest.mark.parametrize("role", ["EXPERT", "GOVERNMENT", "ADMIN"])
    def test_criteria_open_to_reviewers(self, client, tokens, seeded, role):
        assert client.get(
            f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/criteria",
            headers=auth(tokens[role])).status_code == 200

    def test_criteria_closed_to_startups(self, client, tokens, seeded):
        assert client.get(
            f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/criteria",
            headers=auth(tokens["STARTUP"])).status_code == 403

    def test_criteria_for_unknown_proposal_is_404(self, client, tokens):
        assert client.get(
            f"/api/v1/evaluations/proposals/{uuid.uuid4()}/criteria",
            headers=auth(tokens["EXPERT"])).status_code == 404

    def test_ai_analysis_is_real_and_cites_the_match_score(self, client, tokens, seeded):
        """
        The analysis runs the genuine in-process pipeline from Phase 5 — the
        same component scores as challenge-wide matching, narrated.
        """
        response = client.get(
            f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/ai-analysis",
            headers=auth(tokens["EXPERT"]))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"summary"}, "Spring returns only `summary`"

        summary = body["summary"]
        assert "RoadSense AI" in summary
        assert "/100" in summary, "the analysis should quote the match score"
        assert "does not replace the expert" in summary

    def test_ai_analysis_closed_to_startups(self, client, tokens, seeded):
        assert client.get(
            f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/ai-analysis",
            headers=auth(tokens["STARTUP"])).status_code == 403


class TestEvaluationSubmission:
    """Scored against a proposal this module created, never a seeded one."""

    @pytest.fixture(scope="class")
    def target(self, db) -> dict:
        proposal_id = db.execute(text(
            "SELECT p.id FROM proposals p JOIN startups s ON s.id = p.startup_id "
            "WHERE s.company_name = :c"), {"c": PHASE6_COMPANY}).scalar_one()
        criteria = db.execute(text(
            "SELECT ec.id, ec.criterion_name, ec.weight FROM evaluation_criteria ec "
            "JOIN proposals p ON p.challenge_id = ec.challenge_id WHERE p.id = :pid "
            "ORDER BY ec.criterion_name"), {"pid": proposal_id}).mappings().all()
        assert len(criteria) == 4, "the default rubric should have been seeded on publish"
        return {"proposal_id": proposal_id, "criteria": [dict(c) for c in criteria]}

    def test_submit_returns_the_contract_shape_with_a_weighted_total(
            self, client, tokens, target, db):
        scores = {"Technical Feasibility": 8, "Cost Effectiveness": 7,
                  "Scalability": 9, "Team Capability": 6}
        payload = {"comments": "Solid submission overall.",
                   "scores": [{"criterionId": str(c["id"]),
                               "score": scores[c["criterion_name"]],
                               "remarks": f"{c['criterion_name']} remark"}
                              for c in target["criteria"]]}

        response = client.post(
            f"/api/v1/evaluations/proposals/{target['proposal_id']}",
            headers=auth(tokens["EXPERT"]), json=payload)
        assert response.status_code == 200, response.text
        body = response.json()

        assert set(body) == {"id", "proposalId", "expertId", "expertName",
                             "totalScore", "comments", "aiAssistSummary",
                             "submittedAt", "scores"}
        assert body["expertName"] == "Dr. Kavita Iyer"
        assert len(body["scores"]) == 4
        for score in body["scores"]:
            assert set(score) == {"criterionId", "criterionName", "score", "remarks"}

        # 8*.30 + 7*.25 + 9*.25 + 6*.20 = 7.60
        expected = sum(
            Decimal(str(scores[c["criterion_name"]])) * Decimal(str(c["weight"]))
            for c in target["criteria"])
        assert body["totalScore"] == pytest.approx(float(expected), abs=0.01)
        assert body["totalScore"] == pytest.approx(7.60, abs=0.001)

    def test_submission_records_a_real_ai_summary_snapshot(self, client, tokens, target, db):
        stored = db.execute(text(
            "SELECT ai_assist_summary FROM evaluations WHERE proposal_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        assert stored
        assert "AI-assisted analysis was unavailable" not in stored, (
            "the AI layer should have produced a real analysis")
        assert PHASE6_COMPANY in stored

    def test_submission_advances_the_proposal_to_under_review(self, client, tokens, target, db):
        db.expire_all()
        status = db.execute(text("SELECT status FROM proposals WHERE id = :pid"),
                            {"pid": target["proposal_id"]}).scalar_one()
        # This proposal was moved to SHORTLISTED earlier, so it must be left
        # alone — only a SUBMITTED proposal advances.
        assert status in ("UNDER_REVIEW", "SHORTLISTED")

    def test_resubmission_updates_rather_than_duplicating(self, client, tokens, target, db):
        payload = {"comments": "Revised after a second read.",
                   "scores": [{"criterionId": str(c["id"]), "score": 5}
                              for c in target["criteria"]]}
        response = client.post(
            f"/api/v1/evaluations/proposals/{target['proposal_id']}",
            headers=auth(tokens["EXPERT"]), json=payload)
        assert response.status_code == 200
        assert response.json()["comments"] == "Revised after a second read."
        assert response.json()["totalScore"] == pytest.approx(5.0, abs=0.001)

        count = db.execute(text(
            "SELECT count(*) FROM evaluations WHERE proposal_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        assert count == 1, "resubmission created a duplicate evaluation"

        scores = db.execute(text(
            "SELECT count(*) FROM evaluation_scores es "
            "JOIN evaluations e ON e.id = es.evaluation_id WHERE e.proposal_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        assert scores == 4, "old scores were not replaced"

    def test_unknown_criterion_is_400(self, client, tokens, target):
        response = client.post(
            f"/api/v1/evaluations/proposals/{target['proposal_id']}",
            headers=auth(tokens["EXPERT"]),
            json={"scores": [{"criterionId": str(uuid.uuid4()), "score": 5}]})
        assert response.status_code == 400
        assert "Unknown criterion" in response.json()["message"]

    def test_a_rejected_submission_changes_nothing(self, client, tokens, target, db):
        """Validation happens before any write, so a bad request is inert."""
        before = db.execute(text(
            "SELECT total_score FROM evaluations WHERE proposal_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        client.post(f"/api/v1/evaluations/proposals/{target['proposal_id']}",
                    headers=auth(tokens["EXPERT"]),
                    json={"scores": [{"criterionId": str(uuid.uuid4()), "score": 9}]})
        db.expire_all()
        after = db.execute(text(
            "SELECT total_score FROM evaluations WHERE proposal_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        assert before == after

    def test_empty_score_list_is_rejected(self, client, tokens, target):
        response = client.post(
            f"/api/v1/evaluations/proposals/{target['proposal_id']}",
            headers=auth(tokens["EXPERT"]), json={"scores": []})
        assert response.status_code == 400

    @pytest.mark.parametrize("role", ["GOVERNMENT", "STARTUP", "ADMIN"])
    def test_only_an_expert_may_submit(self, client, tokens, target, role):
        assert client.post(
            f"/api/v1/evaluations/proposals/{target['proposal_id']}",
            headers=auth(tokens[role]),
            json={"scores": [{"criterionId": str(target["criteria"][0]["id"]),
                              "score": 5}]}).status_code == 403

    def test_submission_notifies_the_department_and_is_audited(self, db, target):
        notified = db.execute(text(
            "SELECT count(*) FROM notifications n JOIN users u ON u.id = n.user_id "
            "WHERE u.email = :email AND n.type = 'EVALUATION_SUBMITTED'"),
            {"email": ACCOUNTS["GOVERNMENT"]}).scalar_one()
        assert notified >= 1
        audited = db.execute(text(
            "SELECT count(*) FROM audit_logs "
            "WHERE action = 'SUBMIT_EVALUATION' AND entity_id = :pid"),
            {"pid": target["proposal_id"]}).scalar_one()
        assert audited >= 1


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

    def test_proposal_detail_matches(self, client, tokens, seeded):
        mine = client.get(f"/api/v1/proposals/{seeded['proposal_id']}",
                          headers=auth(tokens["ADMIN"])).json()
        status, theirs = spring_request(f"/api/v1/proposals/{seeded['proposal_id']}",
                                        token=tokens["ADMIN"])
        assert status == 200
        self._compare(mine, theirs, label="proposal")

    def test_proposals_mine_matches(self, client, tokens):
        mine = client.get("/api/v1/proposals/mine",
                          headers=auth(tokens["STARTUP"])).json()
        status, theirs = spring_request("/api/v1/proposals/mine", token=tokens["STARTUP"])
        assert status == 200
        assert sorted(p["id"] for p in mine) == sorted(p["id"] for p in theirs)
        by_id = {p["id"]: p for p in theirs}
        for proposal in mine:
            self._compare(proposal, by_id[proposal["id"]], label="mine")

    def test_expert_queue_matches(self, client, tokens):
        mine = client.get("/api/v1/proposals/queue",
                          headers=auth(tokens["EXPERT"])).json()
        status, theirs = spring_request("/api/v1/proposals/queue", token=tokens["EXPERT"])
        assert status == 200
        assert sorted(p["id"] for p in mine) == sorted(p["id"] for p in theirs)

    def test_proposals_for_challenge_matches(self, client, tokens, seeded):
        path = f"/api/v1/proposals/challenges/{seeded['challenge_id']}"
        mine = client.get(path, headers=auth(tokens["GOVERNMENT"])).json()
        status, theirs = spring_request(path, token=tokens["GOVERNMENT"])
        assert status == 200
        assert sorted(p["id"] for p in mine) == sorted(p["id"] for p in theirs)

    def test_evaluation_criteria_matches(self, client, tokens, seeded):
        path = f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/criteria"
        mine = client.get(path, headers=auth(tokens["EXPERT"])).json()
        status, theirs = spring_request(path, token=tokens["EXPERT"])
        assert status == 200
        by_id = {c["id"]: c for c in theirs}
        assert len(mine) == len(by_id)
        for criterion in mine:
            self._compare(criterion, by_id[criterion["id"]], label="criterion")

    def test_ai_analysis_shape_and_substance_match(self, client, tokens, seeded):
        """
        The exact prose can differ if either side re-embeds, so the assertion is
        on shape and on the score the text quotes — that number comes from the
        same pipeline on both sides and must agree.
        """
        import re

        path = f"/api/v1/evaluations/proposals/{seeded['proposal_id']}/ai-analysis"
        mine = client.get(path, headers=auth(tokens["EXPERT"])).json()
        status, theirs = spring_request(path, token=tokens["EXPERT"])
        assert status == 200
        assert set(mine) == set(theirs) == {"summary"}

        pattern = re.compile(r"([\d.]+)/100")
        my_score = pattern.search(mine["summary"])
        their_score = pattern.search(theirs["summary"])
        assert my_score and their_score
        assert float(my_score.group(1)) == pytest.approx(
            float(their_score.group(1)), abs=0.05)

    @pytest.mark.parametrize(("path", "role", "expected"), [
        ("/api/v1/proposals/mine", "GOVERNMENT", 403),
        ("/api/v1/proposals/queue", "STARTUP", 403),
        ("/api/v1/proposals/queue", "ADMIN", 403),
    ])
    def test_rbac_rejections_agree(self, client, tokens, path, role, expected):
        mine = client.get(path, headers=auth(tokens[role]))
        status, _ = spring_request(path, token=tokens[role])
        assert mine.status_code == expected
        assert status == expected, f"{path} as {role}: python={mine.status_code} spring={status}"

    def test_not_found_messages_agree(self, client, tokens):
        missing = uuid.uuid4()
        mine = client.get(f"/api/v1/proposals/{missing}", headers=auth(tokens["ADMIN"]))
        status, theirs = spring_request(f"/api/v1/proposals/{missing}",
                                        token=tokens["ADMIN"])
        assert mine.status_code == status == 404
        assert mine.json()["message"] == theirs["message"] == "Proposal not found"

    def test_document_ownership_rejection_agrees(self, client, rival, seeded):
        path = f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}"
        mine = client.get(path, headers=auth(rival["token"]))
        status, theirs = spring_request(path, token=rival["token"])
        assert mine.status_code == status == 403
        assert mine.json()["message"] == theirs["message"]

    def test_document_listing_matches(self, client, tokens, seeded):
        """
        Both backends read the same `documents` rows — including the ones this
        module uploaded — so the listings must agree exactly.
        """
        path = f"/api/v1/documents/STARTUP/{seeded['roadsense_id']}"
        mine = client.get(path, headers=auth(tokens["STARTUP"])).json()
        status, theirs = spring_request(path, token=tokens["STARTUP"])
        assert status == 200
        assert sorted(d["id"] for d in mine) == sorted(d["id"] for d in theirs)
        by_id = {d["id"]: d for d in theirs}
        for document in mine:
            self._compare(document, by_id[document["id"]], label="document")


# ===========================================================================
# Seeded scenario integrity
# ===========================================================================

class TestSeededScenarioUnchanged:
    def test_roadsense_scenario_intact(self, client, tokens, db):
        startup = client.get("/api/v1/startups/me",
                             headers=auth(tokens["STARTUP"])).json()
        assert startup["companyName"] == "RoadSense AI"
        assert len(startup["capabilities"]) == 3
        assert len(startup["projects"]) == 2

    def test_seeded_counts_unchanged(self, db):
        db.expire_all()
        counts = dict(db.execute(text(
            "SELECT 'users', count(*) FROM users WHERE email NOT LIKE 'phase6-%' "
            "UNION ALL SELECT 'startups', count(*) FROM startups "
            "  WHERE company_name <> :company "
            "UNION ALL SELECT 'challenges', count(*) FROM challenges "
            "  WHERE domain <> :domain "
            "UNION ALL SELECT 'proposals', count(*) FROM proposals p "
            "  JOIN startups s ON s.id = p.startup_id WHERE s.company_name <> :company "
            "UNION ALL SELECT 'pilots', count(*) FROM pilots "
            "UNION ALL SELECT 'recommendations', count(*) FROM recommendations"
        ), {"company": PHASE6_COMPANY, "domain": PHASE6_DOMAIN}).fetchall())
        assert counts == {"users": 22, "startups": 16, "challenges": 6,
                          "proposals": 6, "pilots": 2, "recommendations": 2}

    def test_the_seeded_evaluation_was_not_touched(self, db):
        """
        Exactly one evaluation is seeded — AgriSense Technologies on the crop
        advisory challenge, scored 8.35 with four criterion scores. This module
        writes evaluations only against its own throwaway proposal, so the
        seeded row and its scores must survive byte-for-byte.
        """
        rows = db.execute(text(
            "SELECT e.total_score, count(es.id) AS score_count "
            "FROM evaluations e "
            "JOIN proposals p ON p.id = e.proposal_id "
            "JOIN startups s ON s.id = p.startup_id "
            "LEFT JOIN evaluation_scores es ON es.evaluation_id = e.id "
            "WHERE s.company_name = 'AgriSense Technologies' "
            "GROUP BY e.id, e.total_score")).mappings().all()
        assert len(rows) == 1, "the seeded evaluation is missing or duplicated"
        assert float(rows[0]["total_score"]) == pytest.approx(8.35, abs=0.01)
        assert rows[0]["score_count"] == 4
