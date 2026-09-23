""".
Phase 2 gate: bcrypt, JWT, RBAC and rate limiting.

The decisive tests here are the *interoperability* ones. Anyone can write a
JWT module that verifies its own tokens; what actually de-risks the migration
is proving that a token minted by this backend is accepted by the Spring
backend and vice versa, and that the seeded bcrypt hashes still verify.

Read-only against the database. No inserts, no updates, no schema changes.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, check_connection
from app.main import app
from app.models import RoleName, User
from app.security.jwt import (
    ACCEPTED_ALGORITHMS,
    create_access_token,
    decode_token,
    extract_bearer,
    secret_bytes,
    select_algorithm,
)
from app.security.password import (
    BCRYPT_ROUNDS,
    hash_password,
    needs_rehash,
    verify_password,
)

DEMO_PASSWORD = "Demo@123"

requires_db = pytest.mark.skipif(
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


def _decode_unverified(token: str) -> tuple[dict, dict]:
    header_b64, payload_b64, _ = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    return (
        json.loads(base64.urlsafe_b64decode(pad(header_b64))),
        json.loads(base64.urlsafe_b64decode(pad(payload_b64))),
    )


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_roundtrip(self):
        digest = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", digest)
        assert not verify_password("wrong password", digest)

    def test_uses_spring_default_cost(self):
        digest = hash_password("anything")
        assert digest.startswith("$2b$10$"), digest[:7]
        assert int(digest.split("$")[2]) == BCRYPT_ROUNDS

    def test_salts_differ_per_hash(self):
        assert hash_password("same") != hash_password("same")

    def test_accepts_the_2a_version_tag_spring_also_emits(self):
        """
        Spring has emitted both `$2a$` and `$2b$` digests across versions.

        `$2a$` and `$2b$` differ only in a documented wraparound edge case for
        passwords over 255 bytes, so the same digest body verifies under either
        tag — asserted here by swapping the tag on a known-good hash.
        """
        digest_2b = hash_password("Demo@123")
        digest_2a = "$2a$" + digest_2b[4:]
        assert digest_2b.startswith("$2b$")
        assert verify_password("Demo@123", digest_2a)
        assert not verify_password("Demo@1234", digest_2a)

    def test_rejects_structurally_invalid_hashes(self):
        from app.security.password import is_valid_hash

        assert is_valid_hash("$2b$10$" + "a" * 53)
        assert is_valid_hash("$2a$12$" + "a" * 53)
        for bad in ("", None, "$2b$10$tooshort", "$2c$10$" + "a" * 53,
                    "$2b$xx$" + "a" * 53, "plaintext", "$2b$10$" + "a" * 52):
            assert not is_valid_hash(bad), bad

    def test_long_password_truncates_instead_of_raising(self):
        """
        Java truncates at 72 bytes; Python's bcrypt raises. We truncate.

        Without this, a >72-byte password would work on the Java backend and
        return a 500 on the Python one.
        """
        long_password = "a" * 200
        digest = hash_password(long_password)
        assert verify_password(long_password, digest)
        # bcrypt ignores everything past 72 bytes, so these are the same secret.
        assert verify_password("a" * 72, digest)

    def test_multibyte_password_is_not_split_mid_character(self):
        password = "é" * 100  # 2 bytes each — the 72-byte cut lands mid-character
        digest = hash_password(password)
        assert verify_password(password, digest)

    def test_malformed_hash_returns_false_not_exception(self):
        """
        bcrypt 4.x *panics* (a BaseException) on some malformed digests, which
        an `except Exception` would not stop. A corrupt row must yield a failed
        login, never a crashed request.
        """
        for bad in ("", "not-a-hash", "$2b$", "$2b$10$tooshort",
                    "$2b$10$short", "$" * 60, "x" * 60):
            assert verify_password("x", bad) is False

    def test_needs_rehash(self):
        assert needs_rehash("$2b$04$" + "x" * 53) is True
        assert needs_rehash("$2b$10$" + "x" * 53) is False
        assert needs_rehash("garbage") is True


@requires_db
class TestSeededHashes:
    """The migration fails immediately if these stop verifying."""

    @pytest.mark.parametrize("email", [
        "government@demo.com", "startup@demo.com",
        "expert@demo.com", "admin@demo.com",
    ])
    def test_demo_password_verifies(self, db, email):
        user = db.execute(select(User).where(User.email == email)).scalars().one()
        assert verify_password(DEMO_PASSWORD, user.password_hash), (
            f"{email}: seeded bcrypt hash no longer verifies against {DEMO_PASSWORD!r}"
        )

    def test_wrong_password_rejected(self, db):
        user = db.execute(
            select(User).where(User.email == "government@demo.com")).scalars().one()
        assert not verify_password("Demo@1234", user.password_hash)
        assert not verify_password("demo@123", user.password_hash)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class TestJwtAlgorithmSelection:
    """
    jjwt picks the HMAC algorithm from key length. Getting this wrong is a
    silent, total incompatibility, so each boundary is pinned.
    """

    @pytest.mark.parametrize(("length", "expected"), [
        (32, "HS256"), (47, "HS256"),
        (48, "HS384"), (63, "HS384"),
        (64, "HS512"), (100, "HS512"),
    ])
    def test_boundaries(self, length, expected):
        assert select_algorithm(b"x" * length) == expected

    def test_short_secret_is_zero_padded_to_32_bytes(self):
        """Spring copies a short secret into a 32-byte array; we must too."""
        padded = secret_bytes("short")
        assert len(padded) == 32
        assert padded == b"short" + b"\x00" * 27
        assert select_algorithm(padded) == "HS256"

    def test_project_secret_yields_hs384(self):
        """
        The configured dev secret is 51 bytes, so the live Spring backend issues
        HS384 — confirmed by decoding a real token. Documented as HS256, which
        is wrong; this test pins reality.
        """
        assert select_algorithm(secret_bytes()) == "HS384"


class TestJwtIssuing:
    def test_claim_set_matches_spring(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "a@b.com", "GOVERNMENT")
        header, payload = _decode_unverified(token)

        assert set(payload) == {"sub", "email", "role", "iat", "exp"}
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "a@b.com"
        assert payload["role"] == "GOVERNMENT"
        assert payload["exp"] - payload["iat"] == settings.jwt_expiry_seconds == 86_400

    def test_header_omits_typ_like_jjwt(self):
        header, _ = _decode_unverified(create_access_token(uuid.uuid4(), "a@b.com", "ADMIN"))
        assert header == {"alg": "HS384"}, (
            "jjwt emits only {'alg': ...}; an extra 'typ' would make tokens "
            "non-identical to the Java backend's"
        )

    def test_roundtrip(self):
        user_id = uuid.uuid4()
        claims = decode_token(create_access_token(user_id, "x@y.com", "EXPERT"))
        assert claims["sub"] == str(user_id)
        assert claims["email"] == "x@y.com"
        assert claims["role"] == "EXPERT"

    def test_tampered_token_rejected(self):
        import jwt as pyjwt

        token = create_access_token(uuid.uuid4(), "a@b.com", "STARTUP")
        header, payload, signature = token.split(".")
        payload_dict = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        payload_dict["role"] = "ADMIN"          # privilege escalation attempt
        forged_payload = base64.urlsafe_b64encode(
            json.dumps(payload_dict, separators=(",", ":")).encode()).rstrip(b"=").decode()

        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token(f"{header}.{forged_payload}.{signature}")

    def test_expired_token_rejected(self):
        import jwt as pyjwt

        past = datetime.fromtimestamp(
            time.time() - settings.jwt_expiry_seconds - 60, tz=timezone.utc)
        token = create_access_token(uuid.uuid4(), "a@b.com", "ADMIN", issued_at=past)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_token_signed_with_another_secret_rejected(self):
        import jwt as pyjwt

        foreign = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "email": "a@b.com", "role": "ADMIN",
             "iat": int(time.time()), "exp": int(time.time()) + 3600},
            b"a-completely-different-secret-key-abcdefghijkl", algorithm="HS384")
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token(foreign)

    def test_all_three_hmac_algorithms_are_accepted(self):
        """
        A deployment whose secret length changes must not invalidate live
        tokens, so verification accepts any of the three jjwt may have used.
        """
        assert set(ACCEPTED_ALGORITHMS) == {"HS256", "HS384", "HS512"}


class TestBearerExtraction:
    @pytest.mark.parametrize(("header", "expected"), [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("Bearer   spaced  ", "spaced"),
        (None, None), ("", None), ("abc.def.ghi", None),
        ("bearer abc", None),      # case-sensitive, exactly as Java's startsWith
        ("Bearer ", None), ("Basic dXNlcjpwdw==", None),
    ])
    def test_extract(self, header, expected):
        assert extract_bearer(header) == expected


# ---------------------------------------------------------------------------
# RBAC through the app
# ---------------------------------------------------------------------------

@requires_db
class TestAuthDependencies:
    @staticmethod
    def _token_for(db, email: str) -> str:
        user = db.execute(select(User).where(User.email == email)).scalars().one()
        return create_access_token(user.id, user.email, user.role.name.value)

    @staticmethod
    def _auth(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_no_token_is_401(self, client):
        response = client.get("/api/v1/challenges")
        assert response.status_code == 401
        assert response.json()["message"] == "Authentication required"

    def test_malformed_header_is_401(self, client):
        response = client.get("/api/v1/challenges",
                              headers={"Authorization": "Basic abc"})
        assert response.status_code == 401

    def test_garbage_token_is_401(self, client):
        response = client.get("/api/v1/challenges",
                              headers=self._auth("not.a.token"))
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid authentication token"

    def test_expired_token_is_401_with_a_useful_message(self, client):
        past = datetime.fromtimestamp(
            time.time() - settings.jwt_expiry_seconds - 60, tz=timezone.utc)
        token = create_access_token(uuid.uuid4(), "government@demo.com",
                                    "GOVERNMENT", issued_at=past)
        response = client.get("/api/v1/challenges", headers=self._auth(token))
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()

    def test_token_for_unknown_user_is_401(self, client):
        token = create_access_token(uuid.uuid4(), "ghost@nowhere.test", "ADMIN")
        response = client.get("/api/v1/challenges", headers=self._auth(token))
        assert response.status_code == 401

    @pytest.mark.parametrize(("email", "role"), [
        ("government@demo.com", "GOVERNMENT"),
        ("startup@demo.com", "STARTUP"),
        ("expert@demo.com", "EXPERT"),
        ("admin@demo.com", "ADMIN"),
    ])
    def test_each_demo_role_authenticates(self, client, db, email, role):
        """`/auth/me` echoes the identity the token resolved to."""
        response = client.get("/api/v1/auth/me",
                              headers=self._auth(self._token_for(db, email)))
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == email
        assert body["role"] == role
        assert body["fullName"]

    def test_role_guard_allows_matching_role(self, client, db):
        """STARTUP reaching its own profile: a single-role guard, allowed."""
        response = client.get(
            "/api/v1/startups/me",
            headers=self._auth(self._token_for(db, "startup@demo.com")))
        assert response.status_code == 200

    @pytest.mark.parametrize("email", [
        "government@demo.com", "expert@demo.com", "admin@demo.com"])
    def test_role_guard_rejects_other_roles_with_403(self, client, db, email):
        """
        403, never 401.

        The frontend clears the token and redirects to /login on *any* 401, so
        returning 401 for a role mismatch would silently log users out whenever
        they hit a page they simply lack permission for.
        """
        response = client.get("/api/v1/startups/me",
                              headers=self._auth(self._token_for(db, email)))
        assert response.status_code == 403
        assert response.json()["message"] == (
            "You do not have permission to perform this action")

    def test_multi_role_guard(self, client, db):
        """GET /startups admits GOVERNMENT, EXPERT and ADMIN but not STARTUP."""
        for email in ("government@demo.com", "expert@demo.com", "admin@demo.com"):
            assert client.get("/api/v1/startups",
                              headers=self._auth(self._token_for(db, email))
                              ).status_code == 200, email
        assert client.get("/api/v1/startups",
                          headers=self._auth(self._token_for(db, "startup@demo.com"))
                          ).status_code == 403


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------

class TestErrorContract:
    """`ApiErrorBody` in frontend/src/types/index.ts is the specification."""

    REQUIRED = {"timestamp", "status", "error", "message", "path"}

    def test_401_body_shape(self, client):
        response = client.get("/api/v1/challenges")
        body = response.json()
        assert self.REQUIRED <= set(body)
        assert body["status"] == 401
        assert body["error"] == "Unauthorized"
        assert body["path"] == "/api/v1/challenges"
        assert body["timestamp"].endswith("Z")

    def test_403_body_shape(self, client, db):
        if not check_connection():
            pytest.skip("database unavailable")
        user = db.execute(
            select(User).where(User.email == "government@demo.com")).scalars().one()
        token = create_access_token(user.id, user.email, "GOVERNMENT")
        body = client.get("/api/v1/startups/me",
                          headers={"Authorization": f"Bearer {token}"}).json()
        assert self.REQUIRED <= set(body)
        assert body["status"] == 403
        assert body["error"] == "Forbidden"

    def test_unknown_endpoint_is_404_not_500(self, client):
        """Spring had a real bug here: unmapped paths surfaced as 500."""
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "Not Found"
        assert "No such endpoint" in body["message"]

    def test_error_body_has_no_fastapi_detail_key(self, client):
        """A bare `detail` body would leave the UI on its generic fallback."""
        assert "detail" not in client.get("/api/v1/challenges").json()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_only_auth_paths_are_limited(self, client):
        for _ in range(25):
            assert client.get("/health").status_code == 200

    def test_auth_paths_are_limited_after_15_requests(self, client):
        # A distinct client key keeps this case isolated from the others.
        headers = {"X-Forwarded-For": "203.0.113.200"}
        statuses = [
            client.post("/api/v1/auth/login", json={}, headers=headers).status_code
            for _ in range(20)
        ]
        # The first 15 pass the limiter; the 16th in the window is the first
        # to be rejected, matching RateLimitFilter's `count > MAX` check.
        assert statuses[:15].count(429) == 0, statuses
        assert statuses[15] == 429, statuses

    def test_429_body_matches_java_filter(self, client):
        headers = {"X-Forwarded-For": "203.0.113.201"}
        response = None
        for _ in range(20):
            response = client.post("/api/v1/auth/login", json={}, headers=headers)
            if response.status_code == 429:
                break
        assert response.status_code == 429
        assert response.json() == {
            "error": "RATE_LIMITED",
            "message": "Too many auth requests, please wait a minute.",
        }

    def test_separate_clients_get_separate_budgets(self, client):
        """
        Without per-client keying the Vite proxy would collapse every browser
        into one bucket and 15 total logins would lock out a whole demo.
        """
        for _ in range(16):
            client.post("/api/v1/auth/login", json={},
                        headers={"X-Forwarded-For": "203.0.113.210"})
        fresh = client.post("/api/v1/auth/login", json={},
                            headers={"X-Forwarded-For": "203.0.113.211"})
        assert fresh.status_code != 429
