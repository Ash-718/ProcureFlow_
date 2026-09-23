"""Test fixtures.

Phase 1 tests run against the seeded development database and only read from
it, so they never disturb the demo state.  If the database is not reachable the
whole suite is skipped with a clear message rather than erroring out.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, engine, get_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def require_database() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"Database not reachable ({exc}). Run: python -m scripts.reset_db")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def txn_db():
    """A session whose writes are always rolled back.

    Engine tests need to create challenges and proposals, and the demo database
    has to survive the test run untouched.  The session runs inside an outer
    transaction with savepoints, so code under test can call commit() and still
    leave nothing behind.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def txn_client(txn_db: Session) -> TestClient:
    """A client whose requests run in the rolled-back session."""
    app.dependency_overrides[get_db] = lambda: txn_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def demo_password() -> str:
    return settings.demo_password


def login(client: TestClient, email: str, password: str) -> str:
    """Return a bearer token, failing the test if the login does not work."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
