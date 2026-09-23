"""
HISTORICAL ARTIFACT — the Spring Boot backend has been removed (Phase 10).

These tests proved that the Python backend and the Java backend issued and
accepted each other's JWTs — the property that made the cut-over safe. They
require a live Spring backend on :8001, which no longer exists, so the whole
module now **skips**. It is retained deliberately, as the record of how that
compatibility was established rather than asserted.

The lasting evidence lives in `tests/fixtures/spring_contract.json`, captured
from the running Java backend before removal. `test_contract_parity.py` and
`test_schema_value_parity.py` assert against that fixture and need no Spring.

Cross-backend interoperability against the live Spring Boot reference.

This is the test that actually de-risks the auth migration. It talks to the
running Java backend on :8001 and proves the two implementations agree on the
wire, in both directions:

1. a token minted by **Python** is accepted by **Spring**;
2. a token minted by **Spring** is decoded by **Python**;
3. given identical claims, the two produce **byte-identical** tokens.

Point 3 is what makes the Phase 10 cut-over safe: anyone holding a session when
the backend is swapped keeps it, because either backend honours the other's
tokens.

The suite skips cleanly when the Spring backend is not running, so it never
blocks a normal test run — and it is deleted along with the Java backend in
Phase 10, its job done.

Read-only apart from `POST /auth/login`, which the Java `AuthService` records as
a `LOGIN` audit entry. That is an append to `audit_logs`, not a change to any
seeded row.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal, check_connection
from app.models import User
from app.security.jwt import create_access_token, decode_token

SPRING_BASE_URL = "http://127.0.0.1:8001"
DEMO_PASSWORD = "Demo@123"


def _spring_is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{SPRING_BASE_URL}/health", timeout=3) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False


pytestmark = [
    pytest.mark.skipif(
        not check_connection(),
        reason="PostgreSQL is not reachable; start it on :5433.",
    ),
    pytest.mark.skipif(
        not _spring_is_up(),
        reason=(
            "Spring reference backend is not running on :8001. "
            "These interoperability checks are optional and are removed in Phase 10."
        ),
    ),
]


def _request(path: str, *, token: str | None = None, method: str = "GET",
             body: dict | None = None) -> tuple[int, object]:
    request = urllib.request.Request(f"{SPRING_BASE_URL}{path}", method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    payload = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, payload, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def _skip_if_rate_limited(status: int, body: object) -> None:
    """
    Treat Spring's own rate limiter as "not applicable", never as a failure.

    The Java `RateLimitFilter` allows 15 requests per minute to `/api/v1/auth/`.
    Re-running this suite inside one window legitimately exhausts that budget,
    and a 429 there says the limiter works — it says nothing about the
    interoperability being asserted.
    """
    if status == 429:
        pytest.skip("Spring's auth rate limit (15/min) is exhausted; re-run in a minute.")


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def gov_user(db) -> User:
    return db.execute(
        select(User).where(User.email == "government@demo.com")).scalars().one()


@pytest.fixture(scope="module")
def spring_token() -> str:
    status, body = _request(
        "/api/v1/auth/login", method="POST",
        body={"email": "government@demo.com", "password": DEMO_PASSWORD})
    _skip_if_rate_limited(status, body)
    assert status == 200, f"Spring login failed: {status} {body}"
    return body["token"]


class TestTokenInteroperability:
    def test_spring_accepts_a_python_minted_token(self, gov_user):
        """The Phase 10 cut-over depends on this holding."""
        token = create_access_token(
            gov_user.id, gov_user.email, gov_user.role.name.value)
        status, body = _request("/api/v1/auth/me", token=token)
        _skip_if_rate_limited(status, body)
        assert status == 200, f"Spring rejected a Python token: {status} {body}"
        assert body["email"] == gov_user.email
        assert body["role"] == "GOVERNMENT"
        assert body["id"] == str(gov_user.id)

    def test_python_decodes_a_spring_minted_token(self, spring_token, gov_user):
        claims = decode_token(spring_token)
        assert claims["sub"] == str(gov_user.id)
        assert claims["email"] == "government@demo.com"
        assert claims["role"] == "GOVERNMENT"
        assert claims["exp"] - claims["iat"] == 86_400

    def test_identical_claims_produce_identical_tokens(self, spring_token):
        """
        Byte-for-byte equality.

        Covers the claim set, JSON key order, the compact separators, the
        algorithm choice and the absence of a `typ` header all at once — any
        divergence in any of them changes the output.
        """
        claims = decode_token(spring_token)
        reissued = create_access_token(
            claims["sub"], claims["email"], claims["role"],
            issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        )
        assert reissued == spring_token

    def test_spring_uses_hs384_as_this_backend_predicts(self, spring_token):
        """Guards the algorithm-selection rule against a config drift."""
        import base64

        header_b64 = spring_token.split(".")[0]
        header = json.loads(
            base64.urlsafe_b64decode(header_b64 + "=" * (-len(header_b64) % 4)))
        assert header == {"alg": "HS384"}


class TestCredentialInteroperability:
    @pytest.mark.parametrize("email", [
        "government@demo.com", "startup@demo.com",
        "expert@demo.com", "admin@demo.com",
    ])
    def test_all_demo_accounts_log_in_against_spring(self, email):
        """
        Confirms the shared expectation: these credentials work today, and the
        Phase 2 bcrypt tests prove they will still work on the Python backend.
        """
        status, body = _request("/api/v1/auth/login", method="POST",
                                body={"email": email, "password": DEMO_PASSWORD})
        _skip_if_rate_limited(status, body)
        assert status == 200, f"{email}: {status} {body}"
        assert body["email"] == email
        assert body["token"]

    def test_wrong_password_is_rejected_by_spring(self):
        status, body = _request("/api/v1/auth/login", method="POST",
                                body={"email": "government@demo.com",
                                      "password": "wrong-password"})
        _skip_if_rate_limited(status, body)
        assert status == 401


class TestErrorContractParity:
    """The error body this backend emits must match what Spring emits."""

    REQUIRED = {"timestamp", "status", "error", "message", "path"}

    @pytest.mark.parametrize(("label", "token"), [
        ("no Authorization header", None),
        ("malformed header", "garbage"),
        ("well-formed but invalid token", "aaa.bbb.ccc"),
    ])
    def test_spring_answers_403_for_every_auth_failure(self, label, token):
        """
        Documents Spring's actual behaviour, which is **403, never 401**.

        Spring Security's default `AccessDeniedHandler` handles anonymous
        requests, and no `AuthenticationEntryPoint` was configured to return
        401. The consequence is a real defect in the running app: the
        frontend's axios interceptor logs the user out on 401 only, so when a
        24-hour token expires the user is never redirected to /login — every
        page just shows a permission error until they clear storage by hand.

        The Python backend deliberately diverges: 401 for *authentication*
        failures, 403 for *authorisation* failures. That is the semantically
        correct split and it activates the redirect logic the frontend already
        contains. See `app/security/deps.py`.

        This test asserts the *old* behaviour so the divergence is explicit and
        reviewable rather than accidental. It is deleted with the Java backend
        in Phase 10.
        """
        # A non-`/auth/` path: `/api/v1/auth/*` is rate limited, so probing it
        # here would race the limiter instead of the contract.
        status, body = _request("/api/v1/challenges", token=token)
        assert status == 403, f"{label}: expected Spring's 403, got {status}"
        # And the body is empty — `Content-Length: 0`, not an ErrorResponse.
        # `apiErrorMessage()` therefore finds no `.message` and falls back to
        # the generic axios text, which is why an expired session currently
        # surfaces as "Something went wrong" rather than a sign-in prompt.
        assert body == "", f"{label}: expected an empty body, got {body!r}"

    def test_python_backend_returns_401_where_spring_returned_403(self):
        """The divergence above, asserted from the Python side."""
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/challenges")
        assert response.status_code == 401
        assert response.json()["message"] == "Authentication required"

    def test_spring_403_body_shape(self, db):
        """A startup hitting a GOVERNMENT-only endpoint gets 403, not 401."""
        user = db.execute(
            select(User).where(User.email == "startup@demo.com")).scalars().one()
        token = create_access_token(user.id, user.email, "STARTUP")
        status, body = _request("/api/v1/challenges", token=token, method="POST",
                                body={"title": "x", "problemStatement": "x",
                                      "domain": "x", "requirements": [], "kpis": []})
        assert status == 403, f"expected 403, got {status}: {body}"
        parsed = json.loads(body) if isinstance(body, str) else body
        assert self.REQUIRED <= set(parsed)
