"""Evaluation rubric, evaluations and per-criterion scores."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Evaluation, EvaluationCriterion, EvaluationScore


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    # -- rubric -----------------------------------------------------------

    def list_criteria(self, challenge_id: uuid.UUID) -> list[EvaluationCriterion]:
        return list(self.db.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.challenge_id == challenge_id)
            .order_by(EvaluationCriterion.criterion_name)
        ).scalars())

    def get_criterion(self, criterion_id: uuid.UUID) -> EvaluationCriterion | None:
        return self.db.get(EvaluationCriterion, criterion_id)

    # -- evaluations ------------------------------------------------------

    def _loaded(self, *, fresh: bool = False):
        """
        `EvaluationResponse` needs the expert's name and each score's criterion
        name, so both are eager-loaded.
        """
        statement = (
            select(Evaluation)
            .options(
                joinedload(Evaluation.expert),
                selectinload(Evaluation.scores).joinedload(EvaluationScore.criterion),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def get(self, evaluation_id: uuid.UUID, *, fresh: bool = False) -> Evaluation | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Evaluation.id == evaluation_id)
        ).unique().scalars().one_or_none()

    def find_by_proposal_and_expert(self, proposal_id: uuid.UUID,
                                    expert_id: uuid.UUID) -> Evaluation | None:
        """
        One evaluation per expert per proposal — the table has a UNIQUE on the
        pair, and re-submitting updates rather than duplicating.
        """
        return self.db.execute(
            self._loaded().where(
                Evaluation.proposal_id == proposal_id,
                Evaluation.expert_id == expert_id,
            )
        ).unique().scalars().one_or_none()

    def list_by_proposal(self, proposal_id: uuid.UUID) -> list[Evaluation]:
        return list(self.db.execute(
            self._loaded()
            .where(Evaluation.proposal_id == proposal_id)
            .order_by(Evaluation.created_at)
        ).unique().scalars())

    def add(self, evaluation: Evaluation) -> Evaluation:
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    # -- scores -----------------------------------------------------------

    def replace_scores(self, evaluation_id: uuid.UUID,
                       scores: list[EvaluationScore]) -> None:
        """
        Delete-then-insert, matching `EvaluationService.submit`.

        A resubmission replaces the whole score set rather than diffing it, so
        a criterion dropped from the second submission genuinely disappears.
        """
        self.db.execute(
            delete(EvaluationScore)
            .where(EvaluationScore.evaluation_id == evaluation_id))
        for score in scores:
            self.db.add(score)
        self.db.flush()

    def list_scores(self, evaluation_id: uuid.UUID) -> list[EvaluationScore]:
        return list(self.db.execute(
            select(EvaluationScore)
            .options(joinedload(EvaluationScore.criterion))
            .where(EvaluationScore.evaluation_id == evaluation_id)
        ).unique().scalars())
