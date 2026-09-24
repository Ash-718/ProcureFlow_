from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.enums import ChallengeStatus, Tier
from app.models import Challenge, Pilot, Proposal, Award, Kpi
from tests.conftest import auth_header, login


def test_all_statuses_and_tiers_seeded(db) -> None:
    challenges = db.scalars(select(Challenge)).all()
    statuses = {c.status for c in challenges}
    assert statuses == {
        ChallengeStatus.DRAFT,
        ChallengeStatus.ANALYZED,
        ChallengeStatus.APPROVED,
        ChallengeStatus.PUBLISHED,
        ChallengeStatus.EVALUATION,
        ChallengeStatus.PILOT,
        ChallengeStatus.COMPLETED,
        ChallengeStatus.CANCELLED,
    }

    tiers = {c.tier for c in challenges if c.tier is not None}
    assert tiers == {Tier.SMALL, Tier.MEDIUM, Tier.LARGE}

    # Verify at least 2 SMALL, 2 MEDIUM, 2 LARGE
    small_count = sum(1 for c in challenges if c.tier == Tier.SMALL or (c.status == ChallengeStatus.DRAFT))
    medium_count = sum(1 for c in challenges if c.tier == Tier.MEDIUM)
    large_count = sum(1 for c in challenges if c.tier == Tier.LARGE)

    assert small_count >= 2
    assert medium_count >= 2
    assert large_count >= 2


def test_incomplete_challenge_cannot_be_published(txn_client: TestClient, txn_db) -> None:
    token = login(txn_client, "officer@mahagov.in", settings.demo_password)
    headers = auth_header(token)
    # Draft challenge with missing fields
    draft = txn_db.scalar(select(Challenge).where(Challenge.status == ChallengeStatus.DRAFT))
    assert draft is not None
    assert len(draft.missing_fields) > 0

    res = txn_client.post(f"/challenges/{draft.id}/publish", headers=headers)
    assert res.status_code == 409
    body = res.json()
    assert "missing_fields" in body["detail"] or "cannot be published" in str(body["detail"])


def test_full_lifecycle_large_completed_challenge(db) -> None:
    c = db.scalar(
        select(Challenge).where(
            Challenge.title == "Integrated Smart Water Management and Non-Revenue Water Reduction — Nashik District"
        )
    )
    assert c is not None
    assert c.tier == Tier.LARGE
    assert c.status == ChallengeStatus.COMPLETED
    assert c.value == Decimal("78000000")

    # Has multiple proposals (at least 3), an awarded proposal, a pilot, award, and verified KPIs
    proposals = db.scalars(select(Proposal).where(Proposal.challenge_id == c.id)).all()
    assert len(proposals) >= 3
    assert any(p.status.value == "AWARDED" for p in proposals)
    assert any(p.status.value == "DECLINED" for p in proposals)

    pilot = db.scalar(select(Pilot).where(Pilot.challenge_id == c.id))
    assert pilot is not None
    assert pilot.status.value == "CLOSED"
    assert pilot.outcome.value == "SCALE"

    award = db.scalar(select(Award).where(Award.challenge_id == c.id))
    assert award is not None

    verified_kpis = db.scalars(
        select(Kpi).where(Kpi.challenge_id == c.id, Kpi.validated_value.is_not(None))
    ).all()
    assert len(verified_kpis) == 2


def test_cancelled_challenge_exists_and_cancel_endpoint(txn_client: TestClient, txn_db) -> None:
    token = login(txn_client, "officer@mahagov.in", settings.demo_password)
    headers = auth_header(token)
    cancelled = txn_db.scalar(select(Challenge).where(Challenge.status == ChallengeStatus.CANCELLED))
    assert cancelled is not None

    # Test cancel endpoint on an active challenge
    pub = txn_db.scalar(select(Challenge).where(Challenge.status == ChallengeStatus.PUBLISHED))
    assert pub is not None
    res = txn_client.post(f"/challenges/{pub.id}/cancel", json={"reason": "Testing cancellation flow"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == ChallengeStatus.CANCELLED.value
