"""
Phase 1 gate: every SQLAlchemy model must round-trip against the live database.

These are *integration* tests against the real seeded PostgreSQL instance, not
unit tests with mocks — that is the point. The whole risk in Phase 1 is that a
model silently disagrees with `database/schema.sql` (a wrong column name, a
`String` where a native enum is required, a `Float` where the column is
`NUMERIC`). Only a real query finds that.

The suite is **strictly read-only**: it never inserts, updates or deletes, so
it cannot disturb the seeded demo scenario. The one write-shaped check —
enum round-tripping — is done with a `SELECT ... ::enum` cast rather than an
INSERT.

Run:  backend/.venv/Scripts/python.exe -m pytest tests/test_models_roundtrip.py -v
Skips cleanly (rather than failing) when PostgreSQL is not running.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, inspect, select, text

from app.core.database import SessionLocal, check_connection, engine
from app.models import ALL_MODELS
from app.models.enums import ENUM_TYPE_NAMES

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="PostgreSQL is not reachable; start it on :5433 to run these tests.",
)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()   # guarantee nothing this suite did can persist
        session.close()


# ---------------------------------------------------------------------------
# Schema agreement
# ---------------------------------------------------------------------------

def test_all_expected_tables_exist():
    """Every mapped table is present in the live database."""
    actual = set(inspect(engine).get_table_names())
    expected = {model.__tablename__ for model in ALL_MODELS}
    assert expected <= actual, f"Missing tables: {sorted(expected - actual)}"


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__tablename__)
def test_model_columns_match_database(model):
    """
    Every column a model declares exists in the real table.

    Catches typos and renames. The converse (a database column the model omits)
    is intentionally allowed — a model may legitimately expose a subset.
    """
    actual = {c["name"] for c in inspect(engine).get_columns(model.__tablename__)}
    declared = {c.name for c in model.__table__.columns}
    assert declared <= actual, (
        f"{model.__tablename__}: model declares columns absent from the database: "
        f"{sorted(declared - actual)}"
    )


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__tablename__)
def test_model_selects_and_hydrates(db, model):
    """
    Issue a real SELECT and fully hydrate a row.

    This is the test that actually exercises type handling: UUIDs, native
    enums, NUMERIC→Decimal, TIMESTAMPTZ, `double precision[]`, `text[]` and
    JSONB all get decoded here. Empty tables pass trivially — the point is that
    the query compiles and any returned row materialises.
    """
    instance = db.execute(select(model).limit(1)).scalars().first()
    if instance is None:
        pytest.skip(f"{model.__tablename__} is empty in the seed data")

    for column in model.__table__.columns:
        getattr(instance, column.key)  # forces decode; raises on a type mismatch


# ---------------------------------------------------------------------------
# Native enum handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("python_enum", "type_name"),
    list(ENUM_TYPE_NAMES.items()),
    ids=list(ENUM_TYPE_NAMES.values()),
)
def test_enum_members_match_postgres_type(db, python_enum, type_name):
    """
    The Python enum and the PostgreSQL type must have identical member sets.

    A missing member means a value from the database cannot be decoded; an
    extra one means a write will fail with `invalid input value for enum`.
    """
    rows = db.execute(
        text("SELECT unnest(enum_range(NULL::" + type_name + "))::text")
    ).scalars().all()
    assert set(rows) == {m.value for m in python_enum}, (
        f"{type_name}: database has {sorted(rows)}, "
        f"Python has {sorted(m.value for m in python_enum)}"
    )


# ---------------------------------------------------------------------------
# Seeded demo scenario — must survive the whole migration untouched
# ---------------------------------------------------------------------------

def test_seeded_roles_present(db):
    from app.models import Role, RoleName

    names = {r.name for r in db.execute(select(Role)).scalars()}
    assert names == set(RoleName)


def test_seeded_demo_accounts_present(db):
    """The four demo logins the SIH walkthrough depends on."""
    from app.models import User

    emails = {
        "government@demo.com": "GOVERNMENT",
        "startup@demo.com": "STARTUP",
        "expert@demo.com": "EXPERT",
        "admin@demo.com": "ADMIN",
    }
    for email, expected_role in emails.items():
        user = db.execute(select(User).where(User.email == email)).scalars().one_or_none()
        assert user is not None, f"Demo account {email} is missing"
        assert user.is_active is True
        assert user.role.name.value == expected_role
        # bcrypt hashes must be intact for Phase 2's password verification.
        assert user.password_hash.startswith("$2"), f"{email} has a non-bcrypt hash"


def test_roadsense_demo_scenario_intact(db):
    """
    The pothole/RoadSense scenario is the spine of the demo.

    Asserted here so any later phase that damages it fails loudly and early.
    """
    from app.models import Challenge, Startup

    startup = db.execute(
        select(Startup).where(Startup.company_name == "RoadSense AI")
    ).scalars().one_or_none()
    assert startup is not None, "RoadSense AI startup is missing from the seed data"
    assert startup.capabilities, "RoadSense AI has no capabilities — matching would score 0"
    assert startup.projects, "RoadSense AI has no past projects"

    challenge = db.execute(
        select(Challenge).where(Challenge.title.ilike("%pothole%"))
    ).scalars().first()
    assert challenge is not None, "The pothole detection challenge is missing"
    assert challenge.domain
    assert challenge.problem_statement


def test_seed_row_counts_are_plausible(db):
    """
    Guards against a truncated or partially-loaded database.

    Lower bounds only — later phases legitimately add rows, and this must not
    become a test that fails every time someone uses the app.
    """
    from app.models import (
        Challenge, MatchResult, Pilot, PilotKnowledgeBase, Proposal, Startup, User,
    )

    minimums = {
        User: 20, Startup: 15, Challenge: 5,
        Proposal: 5, Pilot: 2, PilotKnowledgeBase: 2, MatchResult: 8,
    }
    for model, minimum in minimums.items():
        count = db.execute(select(func.count()).select_from(model)).scalar_one()
        assert count >= minimum, (
            f"{model.__tablename__} has {count} rows, expected at least {minimum}. "
            "The seed data may have been reset or truncated."
        )


# ---------------------------------------------------------------------------
# Relationship traversal
# ---------------------------------------------------------------------------

def test_relationships_traverse(db):
    """Walk the object graph the API responses will need to build."""
    from app.models import Challenge, Pilot, Proposal, Startup

    startup = db.execute(select(Startup)).scalars().first()
    assert startup.user.email
    _ = [(c.technology_tag, c.domain_tag, c.proficiency_level) for c in startup.capabilities]
    _ = [(p.title, p.client_type.value) for p in startup.projects]

    challenge = db.execute(select(Challenge)).scalars().first()
    assert challenge.department.department_name
    _ = [r.requirement_type.value for r in challenge.requirements]
    _ = [k.kpi_name for k in challenge.kpis]

    proposal = db.execute(select(Proposal)).scalars().first()
    assert proposal.challenge.title
    assert proposal.startup.company_name

    pilot = db.execute(select(Pilot)).scalars().first()
    assert pilot.challenge.title
    assert pilot.startup.company_name
    for kpi in pilot.kpis:
        _ = kpi.latest_result  # append-only history; readers take the latest


def test_array_and_jsonb_columns_decode(db):
    """`double precision[]`, `text[]` and JSONB must arrive as Python types."""
    from app.models import MatchResult, PilotKnowledgeBase, Startup

    embedded = db.execute(
        select(Startup).where(Startup.embedding.isnot(None))
    ).scalars().first()
    if embedded is not None:
        assert isinstance(embedded.embedding, list)
        assert all(isinstance(v, float) for v in embedded.embedding[:5])

    match = db.execute(select(MatchResult)).scalars().first()
    if match is not None:
        assert isinstance(match.explanation_json, dict)

    entry = db.execute(select(PilotKnowledgeBase)).scalars().first()
    if entry is not None:
        assert isinstance(entry.technology_tags, list)
        # Tri-state: True | False | None. Never coerce to bool.
        assert entry.success is None or isinstance(entry.success, bool)


def test_knowledge_base_success_is_tristate(db):
    """`success` must remain nullable — MODIFY is neither success nor failure."""
    from app.models import PilotKnowledgeBase

    column = PilotKnowledgeBase.__table__.columns["success"]
    assert column.nullable is True
