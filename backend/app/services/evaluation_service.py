"""
Expert evaluation: rubric, AI-assisted analysis and scoring.

Port of Java's `EvaluationService`, with the one change Phase 5 makes possible:
`AiServiceClient.getProposalAnalysis` was an HTTP call to :8081 and is now a
direct call into `app.ai.proposal_analysis`. The analysis text itself is
unchanged — the same component scores from the same matching model, narrated.

Behaviours carried over deliberately:

* **Re-submission updates.** `evaluations` has UNIQUE (proposal, expert), so a
  second submission edits the existing row and *replaces* its scores rather
  than adding a duplicate.
* **`ai_assist_summary` is a snapshot.** It records what the expert actually
  read at submission time, not a value regenerated later.
* **AI failure is not fatal.** If the analysis cannot be produced, the
  evaluation still saves with a plain sentence in its place — an expert's work
  must never be lost because a model would not load.
* **`SUBMITTED` advances to `UNDER_REVIEW`** on first evaluation; any other
  status is left alone.
* An unknown criterion id is a **400**, not a silent skip.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    Evaluation,
    EvaluationScore,
    NotificationType,
    Proposal,
    ProposalStatus,
    User,
)
from app.repositories import EvaluationRepository, ProposalRepository
from app.schemas.evaluation import (
    EvaluationCriterionResponse,
    EvaluationResponse,
    EvaluationSubmitRequest,
)
from app.services.audit_service import Action, AuditService
from app.services.evaluation_scoring import WeightedScore, weighted_total
from app.services.notification_service import NotificationService
from app.utils.logging import get_logger

log = get_logger("services.evaluation")

#: Recorded in place of the analysis when the AI layer is unavailable.
AI_UNAVAILABLE_TEXT = "AI-assisted analysis was unavailable at submission time."


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.evaluations = EvaluationRepository(db)
        self.proposals = ProposalRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # ---------------------------------------------------------------- read

    def get_criteria_for_proposal(
            self, proposal_id: uuid.UUID) -> list[EvaluationCriterionResponse]:
        proposal = self._must_find(proposal_id)
        return [
            EvaluationCriterionResponse.model_validate(c)
            for c in self.evaluations.list_criteria(proposal.challenge_id)
        ]

    def get_ai_analysis(self, proposal_id: uuid.UUID) -> str:
        """
        The AI-assisted summary for one proposal.

        Errors propagate here, unlike in `submit`: this endpoint exists purely
        to fetch the analysis, so failing loudly is the honest outcome rather
        than returning placeholder prose the expert might mistake for a result.
        """
        self._must_find(proposal_id)
        from app.ai import (
            generate_proposal_analysis,
            get_embedding_provider,
            get_text_generation_provider,
        )

        try:
            return generate_proposal_analysis(
                self.db, str(proposal_id),
                get_embedding_provider(), get_text_generation_provider())
        except ValueError as exc:
            raise ApiException.not_found(str(exc)) from exc

    # --------------------------------------------------------------- write

    def submit(self, expert: User, proposal_id: uuid.UUID,
               request: EvaluationSubmitRequest) -> EvaluationResponse:
        proposal = self._must_find(proposal_id)
        criteria = {c.id: c for c in
                    self.evaluations.list_criteria(proposal.challenge_id)}

        # Validate every criterion before writing anything, so a bad request
        # cannot leave a half-scored evaluation behind.
        for score_request in request.scores:
            if score_request.criterion_id not in criteria:
                raise ApiException.bad_request(
                    f"Unknown criterion for this challenge: {score_request.criterion_id}")

        evaluation = self.evaluations.find_by_proposal_and_expert(proposal_id, expert.id)
        if evaluation is None:
            evaluation = self.evaluations.add(Evaluation(
                proposal_id=proposal_id, expert_id=expert.id))

        evaluation.comments = request.comments
        evaluation.ai_assist_summary = self._safe_ai_summary(proposal_id)
        evaluation.submitted_at = datetime.now(timezone.utc)
        self.db.flush()

        weighted: list[WeightedScore] = []
        rows: list[EvaluationScore] = []
        for score_request in request.scores:
            criterion = criteria[score_request.criterion_id]
            score = Decimal(str(score_request.score))
            rows.append(EvaluationScore(
                evaluation_id=evaluation.id,
                criterion_id=criterion.id,
                score=score,
                remarks=score_request.remarks,
            ))
            weighted.append(WeightedScore(score=score, weight=criterion.weight))

        self.evaluations.replace_scores(evaluation.id, rows)

        total = weighted_total(weighted)
        evaluation.total_score = total

        if proposal.status is ProposalStatus.SUBMITTED:
            proposal.status = ProposalStatus.UNDER_REVIEW
        self.db.flush()

        self.audit.log(expert, Action.SUBMIT_EVALUATION, "Proposal", proposal_id,
                       {"totalScore": str(total)})
        self.notifications.notify(
            proposal.challenge.department.user,
            NotificationType.EVALUATION_SUBMITTED,
            f"Expert {expert.full_name} scored {proposal.startup.company_name}'s "
            f'proposal {total}/10 for "{proposal.challenge.title}".',
        )
        self.db.commit()

        return EvaluationResponse.from_entity(
            self.evaluations.get(evaluation.id, fresh=True))

    # ------------------------------------------------------------ internal

    def _safe_ai_summary(self, proposal_id: uuid.UUID) -> str:
        """
        The analysis, or a plain sentence saying it was unavailable.

        Best-effort by design: losing an expert's scores because a model failed
        to load would be far worse than storing an honest placeholder.
        """
        try:
            return self.get_ai_analysis(proposal_id)
        except Exception:  # noqa: BLE001 - mirrors the Java catch-all
            log.warning(
                "AI analysis unavailable while submitting an evaluation for "
                "proposal %s; recording a placeholder.", proposal_id, exc_info=True)
            return AI_UNAVAILABLE_TEXT

    def _must_find(self, proposal_id: uuid.UUID) -> Proposal:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ApiException.not_found("Proposal not found")
        return proposal
