"""
HISTORICAL TOOL — the Spring Boot backend has been removed (Phase 10).

This recorded `tests/fixtures/spring_contract.json`: 24 real responses from the
running Java backend, which the contract-parity suites still diff against. It
cannot be re-run now that Spring is gone, and is kept so the fixture's origin
is documented rather than mysterious.

Capture live Spring responses as golden contract fixtures.

`frontend/src/types/index.ts` declares field *names* and TypeScript types, but
it cannot tell us how Jackson actually encodes a `BigDecimal`, an `Instant` or
a `LocalDate` on the wire — and those encodings are exactly where a Pydantic
port silently drifts (a `Decimal` serialised as `"92.400"` instead of `92.4`
turns `overallScore.toFixed(1)` into a runtime error).

So the specification used by `test_contract_parity.py` is the real bytes the
Java backend emits today. This script records them once into
`tests/fixtures/spring_contract.json`.

Run (with PostgreSQL and the Spring backend up):

    backend/.venv/Scripts/python.exe tests/capture_spring_contract.py

It is a developer tool, not a test — pytest ignores it (no `test_` prefix).

Read-only against the API apart from one `POST /auth/login`, which appends a
`LOGIN` audit row exactly as any sign-in does.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SPRING = "http://127.0.0.1:8001"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "spring_contract.json"
DEMO_PASSWORD = "Demo@123"

ACCOUNTS = {
    "GOVERNMENT": "government@demo.com",
    "STARTUP": "startup@demo.com",
    "EXPERT": "expert@demo.com",
    "ADMIN": "admin@demo.com",
}


def request(path: str, *, token: str | None = None, method: str = "GET",
            body: dict | None = None) -> tuple[int, Any]:
    req = urllib.request.Request(f"{SPRING}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    payload = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, payload, timeout=20) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def login(email: str) -> str:
    status, body = request("/api/v1/auth/login", method="POST",
                           body={"email": email, "password": DEMO_PASSWORD})
    if status != 200:
        raise SystemExit(f"Login failed for {email}: {status} {body}")
    return body["token"]


def main() -> int:
    status, _ = request("/health")
    if status != 200:
        print("Spring backend is not responding on :8001", file=sys.stderr)
        return 1

    tokens = {role: login(email) for role, email in ACCOUNTS.items()}
    gov, startup, expert, admin = (
        tokens["GOVERNMENT"], tokens["STARTUP"], tokens["EXPERT"], tokens["ADMIN"])

    captured: dict[str, Any] = {
        "_meta": {
            "source": "Spring Boot backend on :8001",
            "purpose": "Golden fixtures for the FastAPI contract parity tests.",
        }
    }

    def record(name: str, path: str, token: str | None, **kwargs) -> Any:
        status, body = request(path, token=token, **kwargs)
        captured[name] = {"path": path, "status": status, "body": body}
        marker = "ok " if status < 400 else "ERR"
        print(f"  [{marker}] {status} {name:34} {path}")
        return body

    print("Capturing Spring contract fixtures...")

    # --- auth ------------------------------------------------------------
    status, auth_body = request("/api/v1/auth/login", method="POST",
                                body={"email": ACCOUNTS["GOVERNMENT"],
                                      "password": DEMO_PASSWORD})
    captured["auth_login"] = {"path": "/api/v1/auth/login", "status": status,
                              "body": auth_body}
    print(f"  [ok ] {status} auth_login                         /api/v1/auth/login")
    record("auth_me", "/api/v1/auth/me", gov)

    # --- challenges ------------------------------------------------------
    challenges = record("challenges_list", "/api/v1/challenges", gov)
    challenge_id = challenges[0]["id"] if challenges else None
    if challenge_id:
        record("challenge_detail", f"/api/v1/challenges/{challenge_id}", gov)

    # --- startups --------------------------------------------------------
    startups = record("startups_list", "/api/v1/startups", gov)
    record("startup_me", "/api/v1/startups/me", startup)
    if startups:
        record("startup_detail", f"/api/v1/startups/{startups[0]['id']}", gov)

    # --- matching (real AI pipeline; may take a few seconds) -------------
    pilot_challenge = None
    for candidate in challenges or []:
        if "pothole" in candidate["title"].lower():
            pilot_challenge = candidate
            break
    pilot_challenge = pilot_challenge or (challenges[0] if challenges else None)
    if pilot_challenge:
        cid = pilot_challenge["id"]
        record("matching_results", f"/api/v1/matching/challenges/{cid}", gov)

    # --- proposals -------------------------------------------------------
    record("proposals_mine", "/api/v1/proposals/mine", startup)
    queue = record("proposals_queue", "/api/v1/proposals/queue", expert)
    if challenge_id:
        record("proposals_for_challenge",
               f"/api/v1/proposals/challenges/{challenge_id}", gov)
    proposal_id = queue[0]["id"] if queue else None
    if proposal_id:
        record("proposal_detail", f"/api/v1/proposals/{proposal_id}", gov)
        record("evaluation_criteria",
               f"/api/v1/evaluations/proposals/{proposal_id}/criteria", expert)
        record("documents_for_proposal",
               f"/api/v1/documents/PROPOSAL/{proposal_id}", gov)

    # --- pilots ----------------------------------------------------------
    pilots = record("pilots_list", "/api/v1/pilots", gov)
    if pilots:
        pid = pilots[0]["id"]
        record("pilot_detail", f"/api/v1/pilots/{pid}", gov)
        record("pilot_recommendation", f"/api/v1/pilots/{pid}/recommendation", gov)

    # --- knowledge base --------------------------------------------------
    record("knowledge_base", "/api/v1/knowledge-base", gov)

    # --- notifications ---------------------------------------------------
    record("notifications", "/api/v1/notifications", gov)
    record("notifications_unread", "/api/v1/notifications/unread-count", gov)

    # --- admin (Page<T> lives here) --------------------------------------
    record("admin_users", "/api/v1/admin/users", admin)
    record("admin_audit_logs", "/api/v1/admin/audit-logs?page=0&size=5", admin)

    # --- error shapes ----------------------------------------------------
    record("error_404", "/api/v1/challenges/00000000-0000-0000-0000-000000000000", gov)
    record("error_403_role", "/api/v1/admin/users", startup)

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(captured, indent=2, sort_keys=False), encoding="utf-8")

    populated = sum(1 for k, v in captured.items()
                    if k != "_meta" and v.get("body") not in (None, [], {}))
    print(f"\nWrote {FIXTURE_PATH} ({len(captured) - 1} endpoints, {populated} with data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
