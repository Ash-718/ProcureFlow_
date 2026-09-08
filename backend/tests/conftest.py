"""
Shared pytest fixtures.

Two session-wide concerns live here.

**Rate-limit reset.** `RateLimitMiddleware` allows 15 requests per minute per
client, and `TestClient` presents a single client host for the whole session —
so a module with more than fifteen auth calls starts getting 429s unrelated to
what it asserts. Clearing the buckets before each test keeps the limiter's own
tests meaningful (they opt out with distinct `X-Forwarded-For` values) while
stopping it from corrupting everything else.

**Leftover test rows.** The suite runs against the real seeded database. Tests
that create rows tag them with a marker domain and purge on module teardown,
but a run interrupted mid-module (Ctrl-C, a crash, a killed session) never
reaches that teardown. The leftovers then fail an *unrelated* module on the
next run — a Phase 7 pilot left behind makes Phase 5's "recommendations == 2"
assertion see three — which is confusing to diagnose because the failure lands
nowhere near its cause. `_purge_leftover_test_rows` runs once at session start
so every session begins from clean seeded data.
"""
from __future__ import annotations

import pytest

# Disable the background model warm-up before `app.main` is imported. Tests that
# need the model load it explicitly and cache it for the session; letting every
# TestClient startup spawn a loader would add ~50s of background work and make
# timings noisy for no benefit.
from app.core.config import settings

settings.ai_warm_up_on_startup = False

from app.main import app  # noqa: E402
from app.security.rate_limit import RateLimitMiddleware  # noqa: E402

#: Marker domains used by the phase test modules to tag rows they create.
TEST_MARKER_DOMAINS = ("phase4-testing", "phase5-embedding-check", "phase6-testing",
                       "phase7-testing", "phase8-testing")


def _find_rate_limiter(application) -> RateLimitMiddleware | None:
    """
    Locate the live middleware instance in the built ASGI stack.

    Starlette builds middleware as a chain of wrappers, each holding the next
    in `.app`, so the instance is reachable only by walking that chain — the
    `user_middleware` list holds configuration, not instances.
    """
    node = getattr(application, "middleware_stack", None)
    seen = 0
    while node is not None and seen < 50:
        if isinstance(node, RateLimitMiddleware):
            return node
        node = getattr(node, "app", None)
        seen += 1
    return None


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate-limit buckets before every test."""
    limiter = _find_rate_limiter(app)
    if limiter is not None:
        limiter.reset()
    yield


@pytest.fixture(scope="session", autouse=True)
def _purge_leftover_test_rows():
    """
    Delete rows left by an interrupted previous run, once per session.

    Deletion is keyed on the marker domains and marker values the test modules
    use, never on seeded identifiers, so a seeded row cannot be caught by it.
    Ordered child-first to respect the foreign keys.
    """
    from sqlalchemy import text

    from app.core.database import SessionLocal, check_connection

    if not check_connection():
        yield
        return

    session = SessionLocal()
    try:
        statements = (
            # Pilot subtree hanging off a marker challenge.
            "DELETE FROM pilot_knowledge_base WHERE pilot_id IN "
            "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM recommendations WHERE pilot_id IN "
            "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM kpi_results WHERE kpi_id IN "
            "  (SELECT k.id FROM kpis k JOIN pilots p ON p.id = k.pilot_id"
            "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = ANY(:domains))",
            "DELETE FROM kpis WHERE pilot_id IN "
            "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM payments WHERE milestone_id IN "
            "  (SELECT m.id FROM pilot_milestones m JOIN pilots p ON p.id = m.pilot_id"
            "   JOIN challenges c ON c.id = p.challenge_id WHERE c.domain = ANY(:domains))",
            "DELETE FROM pilot_milestones WHERE pilot_id IN "
            "  (SELECT p.id FROM pilots p JOIN challenges c ON c.id = p.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM pilots WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM contracts WHERE ip_terms = 'phase7-marker'",
            # Proposal / evaluation subtree.
            "DELETE FROM evaluation_scores WHERE evaluation_id IN "
            "  (SELECT e.id FROM evaluations e JOIN proposals pr ON pr.id = e.proposal_id"
            "   JOIN challenges c ON c.id = pr.challenge_id WHERE c.domain = ANY(:domains))",
            "DELETE FROM evaluations WHERE proposal_id IN "
            "  (SELECT pr.id FROM proposals pr JOIN challenges c ON c.id = pr.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM documents WHERE owner_id IN "
            "  (SELECT pr.id FROM proposals pr JOIN challenges c ON c.id = pr.challenge_id"
            "   WHERE c.domain = ANY(:domains))",
            "DELETE FROM proposals WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            # Challenge subtree.
            "DELETE FROM evaluation_criteria WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM challenge_requirements WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM challenge_kpis WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM match_results WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM audit_logs WHERE entity_id IN "
            "  (SELECT id FROM challenges WHERE domain = ANY(:domains))",
            "DELETE FROM challenges WHERE domain = ANY(:domains)",
            # Startup profile extras and registered accounts.
            "DELETE FROM startup_capabilities WHERE domain_tag = ANY(:domains)",
            "DELETE FROM startup_projects WHERE domain = ANY(:domains)",
            "DELETE FROM audit_logs WHERE actor_user_id IN "
            "  (SELECT id FROM users WHERE email LIKE 'phase%@test.local')",
            "DELETE FROM users WHERE email LIKE 'phase%@test.local'",
            # Notifications are a side effect of nearly every write path — a
            # proposal, an evaluation, a flagged document, a created pilot —
            # and their messages carry no marker to key on. Phase 9 found 116
            # accumulated across earlier runs, which left the demo's
            # notification bell showing 70 unread. `database/seed.sql` inserts
            # exactly these five, so anything else is test residue.
            "DELETE FROM notifications WHERE message NOT IN ("
            "  'RoadSense AI submitted a proposal for \"AI-Based Pothole & Road "
            "Damage Detection System\".',"
            "  'UrbanEye Analytics submitted a proposal for \"AI-Based Pothole & "
            "Road Damage Detection System\".',"
            "  'Your proposal for \"AI-Based Pothole & Road Damage Detection "
            "System\" was submitted successfully.',"
            "  'You have a pending evaluation for a proposal on \"AI-Based Pothole "
            "& Road Damage Detection System\".',"
            "  'Platform seeded with 6 challenges, 16 startups and 2 completed "
            "pilots.')",
        )
        _run_purge(session, statements)
    except Exception:  # noqa: BLE001 - never block the run on cleanup
        session.rollback()

    yield

    # Again on the way out. The entry purge guarantees a clean *starting*
    # state; this one leaves the database clean afterwards, which matters
    # because the same database backs the demo. Notifications in particular
    # are written by both backends during parity tests, after the entry purge
    # has already run.
    try:
        _run_purge(session, statements)
    except Exception:  # noqa: BLE001
        session.rollback()
    finally:
        session.close()


def _run_purge(session, statements) -> None:
    from sqlalchemy import text

    for statement in statements:
        session.execute(text(statement), {"domains": list(TEST_MARKER_DOMAINS)})
    session.commit()
