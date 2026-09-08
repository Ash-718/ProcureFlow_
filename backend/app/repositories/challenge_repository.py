"""Challenges, their requirements, KPIs and evaluation rubric."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Challenge,
    ChallengeKpi,
    ChallengeRequirement,
    ChallengeStatus,
    EvaluationCriterion,
)

#: The statuses a non-owner may see. Excludes DRAFT, which is private to the
#: department that owns it.
PUBLIC_STATUSES = (
    ChallengeStatus.PUBLISHED,
    ChallengeStatus.MATCHING,
    ChallengeStatus.SHORTLISTED,
    ChallengeStatus.PILOT,
    ChallengeStatus.CLOSED,
)


class ChallengeRepository:
    def __init__(self, db: Session):
        self.db = db

    def _loaded(self, *, fresh: bool = False):
        """
        Eager-load the collections every response needs.

        `ChallengeResponse` always renders requirements and KPIs, so loading
        them up front turns the list endpoint from 1 + 2N queries into 3.

        ``fresh=True`` adds ``populate_existing`` and is required after a
        write: with ``expire_on_commit=False`` a committed mutation leaves the
        identity-mapped object holding its previous collection, so an updated
        challenge would come back with its old requirements.
        """
        statement = (
            select(Challenge)
            .options(
                selectinload(Challenge.requirements),
                selectinload(Challenge.kpis),
                selectinload(Challenge.department),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def get(self, challenge_id: uuid.UUID, *, fresh: bool = False) -> Challenge | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Challenge.id == challenge_id)
        ).scalars().one_or_none()

    def list_all(self) -> list[Challenge]:
        return list(self.db.execute(
            self._loaded().order_by(Challenge.created_at.desc())).scalars())

    def list_by_department(self, department_id: uuid.UUID) -> list[Challenge]:
        return list(self.db.execute(
            self._loaded()
            .where(Challenge.department_id == department_id)
            .order_by(Challenge.created_at.desc())
        ).scalars())

    def list_public(self) -> list[Challenge]:
        """Everything a startup or expert is allowed to browse."""
        return list(self.db.execute(
            self._loaded()
            .where(Challenge.status.in_(PUBLIC_STATUSES))
            .order_by(Challenge.created_at.desc())
        ).scalars())

    def add(self, challenge: Challenge) -> Challenge:
        self.db.add(challenge)
        self.db.flush()
        return challenge

    # -- requirements and KPIs -------------------------------------------

    def replace_requirements(self, challenge_id: uuid.UUID,
                             requirements: list[ChallengeRequirement]) -> None:
        """
        Delete-then-insert, matching `ChallengeService.update`.

        The Java code replaces both collections wholesale rather than diffing
        them, so requirement IDs change on every edit. Preserved deliberately:
        nothing references a requirement by ID, and diffing would be a
        behavioural change rather than a port.
        """
        self.db.execute(
            delete(ChallengeRequirement)
            .where(ChallengeRequirement.challenge_id == challenge_id))
        for requirement in requirements:
            self.db.add(requirement)
        self.db.flush()

    def replace_kpis(self, challenge_id: uuid.UUID, kpis: list[ChallengeKpi]) -> None:
        self.db.execute(
            delete(ChallengeKpi).where(ChallengeKpi.challenge_id == challenge_id))
        for kpi in kpis:
            self.db.add(kpi)
        self.db.flush()

    def count_requirements(self, challenge_id: uuid.UUID) -> int:
        from sqlalchemy import func

        return self.db.execute(
            select(func.count()).select_from(ChallengeRequirement)
            .where(ChallengeRequirement.challenge_id == challenge_id)
        ).scalar_one()

    # -- evaluation rubric ------------------------------------------------

    def list_criteria(self, challenge_id: uuid.UUID) -> list[EvaluationCriterion]:
        return list(self.db.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.challenge_id == challenge_id)
        ).scalars())

    def add_criteria(self, criteria: list[EvaluationCriterion]) -> None:
        for criterion in criteria:
            self.db.add(criterion)
        self.db.flush()
