"""
Recommendation generation and the human decision that follows it.

Port of Java's `RecommendationService`. Two properties matter more than
anything else here and are preserved exactly:

**System recommendation and human decision stay separate.** `recommendation` is
what the engine computed; `final_decision` is what an official chose, and stays
NULL until one is recorded. They are distinct columns, written by distinct
methods, and the UI shows them apart. Collapsing them would misrepresent an
undecided pilot as decided.

**`PilotKnowledgeBase.success` is tri-state.** SCALE maps to True, REJECT to
False, and MODIFY to **None** — "we changed it" is not "it failed". Coercing
None to False would silently reclassify every modified pilot as a failure and
corrupt the knowledge base's success filter.

Regeneration is an upsert keyed on the pilot, so re-completing a pilot updates
its recommendation rather than creating a second one.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    MilestoneStatus,
    NotificationType,
    Pilot,
    PilotKnowledgeBase,
    Recommendation,
    RecommendationType,
    RoleName,
    User,
)
from app.repositories import UserRepository
from app.repositories.pilot_repository import KnowledgeBaseRepository, PilotRepository
from app.schemas.pilot import RecommendationResponse
from app.services.audit_service import Action, AuditService
from app.services.notification_service import NotificationService
from app.services.recommendation_calculator import (
    KpiAssessment,
    MilestoneAssessment,
    ScoreResult,
    achievement_ratio,
    compute,
)
from app.utils.logging import get_logger

log = get_logger("services.recommendation")

_TWO_DP = Decimal("0.01")


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.pilots = PilotRepository(db)
        self.knowledge_base = KnowledgeBaseRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)
        #: Knowledge-base entry awaiting an embedding refresh after commit.
        self._pending_embedding: uuid.UUID | None = None

    # ---------------------------------------------------------------- read

    def get_by_pilot_id(self, pilot_id: uuid.UUID) -> RecommendationResponse:
        recommendation = self.pilots.get_recommendation(pilot_id)
        if recommendation is None:
            raise ApiException.not_found(
                "No recommendation has been generated for this pilot yet")
        return RecommendationResponse.from_entity(recommendation)

    # --------------------------------------------------------------- write

    def generate_for_pilot(self, pilot: Pilot) -> Recommendation:
        """
        Score a pilot and upsert its recommendation.

        Called from `PilotService.complete`. Does not commit — it joins the
        caller's transaction so completion and recommendation land together.
        """
        kpis = self.pilots.list_kpis(pilot.id)
        assessments = [
            KpiAssessment(
                kpi_name=kpi.kpi_name,
                target_value=kpi.target_value,
                # The *latest* entry in the append-only history.
                recorded_value=(latest.recorded_value
                                if (latest := self.pilots.latest_kpi_result(kpi.id))
                                else None),
            )
            for kpi in kpis
        ]

        milestones = self.pilots.list_milestones(pilot.id)
        milestone_assessments = [
            MilestoneAssessment(delayed=m.status is MilestoneStatus.DELAYED)
            for m in milestones
        ]

        score = compute(assessments, milestone_assessments)
        recommendation_type = RecommendationType(score.recommendation)

        recommendation = self.pilots.get_recommendation(pilot.id)
        if recommendation is None:
            recommendation = self.pilots.add_recommendation(
                Recommendation(pilot_id=pilot.id,
                               recommendation=recommendation_type,
                               cost_score=score.cost_score,
                               performance_score=score.performance_score,
                               impact_score=score.impact_score,
                               rationale_text=""))

        recommendation.recommendation = recommendation_type
        recommendation.cost_score = score.cost_score
        recommendation.performance_score = score.performance_score
        recommendation.impact_score = score.impact_score
        recommendation.rationale_text = self._build_rationale(
            assessments, milestones, score)
        recommendation.generated_at = datetime.now(timezone.utc)
        self.db.flush()

        self._upsert_knowledge_base_entry(pilot, ai_recommendation=recommendation_type)

        self.notifications.notify(
            pilot.challenge.department.user,
            NotificationType.RECOMMENDATION_READY,
            f'AI recommendation for the "{pilot.challenge.title}" pilot: '
            f"{recommendation_type.value}.",
        )
        return recommendation

    def record_final_decision(self, actor: User, pilot_id: uuid.UUID,
                              final_decision: RecommendationType) -> RecommendationResponse:
        """
        Record the human decision. Leaves the system recommendation untouched.
        """
        recommendation = self.pilots.get_recommendation(pilot_id)
        if recommendation is None:
            raise ApiException.not_found(
                "No recommendation has been generated for this pilot yet")

        if actor.role.name is not RoleName.ADMIN:
            department = self.users.find_department_by_user(actor.id)
            if department is None or \
                    department.id != recommendation.pilot.challenge.department_id:
                raise ApiException.forbidden(
                    "You do not have access to decide on this pilot's recommendation")

        recommendation.final_decision = final_decision
        recommendation.reviewed_by = actor.id
        recommendation.decided_at = datetime.now(timezone.utc)
        self.db.flush()

        # The human decision supersedes the system one in the knowledge base.
        self._upsert_knowledge_base_entry(
            recommendation.pilot, final_decision=final_decision)

        self.audit.log(actor, Action.FINAL_DECISION, "Recommendation",
                       recommendation.id, {"finalDecision": final_decision.value})
        self.db.commit()

        return RecommendationResponse.from_entity(
            self.pilots.get_recommendation(pilot_id, fresh=True))

    # ------------------------------------------------------------ internal

    def _upsert_knowledge_base_entry(
        self,
        pilot: Pilot,
        *,
        ai_recommendation: RecommendationType | None = None,
        final_decision: RecommendationType | None = None,
    ) -> PilotKnowledgeBase:
        """
        Create or refresh this pilot's knowledge-base entry.

        `success` is set only when there is an outcome to record, and the human
        decision wins over the system one. MODIFY leaves it **None** — the
        tri-state is the whole point of the column.
        """
        entry = self.knowledge_base.find_by_pilot(pilot.id)
        challenge = pilot.challenge
        technology_tags = _split_technologies(challenge.desired_technology)

        if entry is None:
            entry = self.knowledge_base.add(PilotKnowledgeBase(
                pilot_id=pilot.id,
                domain=challenge.domain,
                technology_tags=technology_tags,
                department_id=challenge.department_id,
                searchable_text="",
            ))

        entry.domain = challenge.domain
        entry.technology_tags = technology_tags
        entry.department_id = challenge.department_id

        recommendation = self.pilots.get_recommendation(pilot.id)
        entry.outcome_summary = (
            recommendation.rationale_text if recommendation is not None else None)

        effective = final_decision if final_decision is not None else ai_recommendation
        if effective is not None:
            if effective is RecommendationType.SCALE:
                entry.success = True
            elif effective is RecommendationType.REJECT:
                entry.success = False
            else:
                # MODIFY: neither a success nor a failure. Stays NULL.
                entry.success = None

        entry.searchable_text = " ".join([
            challenge.title,
            challenge.domain,
            " ".join(technology_tags),
            pilot.startup.company_name,
            challenge.department.department_name,
        ])
        self.db.flush()

        # Deferred rather than run here: the embedding code reads the row in
        # its own transaction, so it must not fire until the caller commits.
        # This is what Java's AfterCommitRunner existed to prevent.
        self._pending_embedding = entry.id
        return entry

    def flush_pending_embeddings(self) -> None:
        """
        Run the queued embedding refresh, if any.

        Called by the owning service *after* it commits. Safe to call when
        nothing is queued, and best-effort — `refresh_knowledge_base_embedding`
        swallows its own failures.
        """
        entry_id = self._pending_embedding
        if entry_id is None:
            return
        self._pending_embedding = None

        from app.services.embedding_hooks import refresh_knowledge_base_embedding

        refresh_knowledge_base_embedding(self.db, entry_id)

    @staticmethod
    def _build_rationale(assessments: list[KpiAssessment],
                         milestones: list, score: ScoreResult) -> str:
        """
        The explanation shown on the recommendation screen.

        Format is reproduced from the Java `buildRationale` so the two
        backends emit identical text for identical inputs.
        """
        parts = [
            f"Overall score {_two_dp(score.overall)}/1.00 "
            f"(cost {_two_dp(score.cost_score)}, "
            f"performance {_two_dp(score.performance_score)}, "
            f"impact {_two_dp(score.impact_score)}). "
        ]

        for assessment in assessments:
            ratio = achievement_ratio(assessment)
            if ratio is None:
                parts.append(f"{assessment.kpi_name}: no result recorded yet. ")
            else:
                verdict = "met or exceeded" if ratio >= 1 else "fell short of"
                parts.append(
                    f"{assessment.kpi_name} {verdict} its target "
                    f"(recorded {assessment.recorded_value} vs target "
                    f"{assessment.target_value}). ")

        delayed = sum(1 for m in milestones if m.status is MilestoneStatus.DELAYED)
        if delayed > 0:
            parts.append(f"{delayed} of {len(milestones)} milestone(s) were delayed. ")
        elif milestones:
            parts.append("All milestones were delivered on schedule. ")

        parts.append(f"Recommendation: {score.recommendation}.")
        return "".join(parts)


def _two_dp(value: Decimal) -> str:
    """`BigDecimal.setScale(2, HALF_UP)` rendering."""
    return str(value.quantize(_TWO_DP, rounding=ROUND_HALF_UP))


def _split_technologies(desired_technology: str | None) -> list[str]:
    if not desired_technology or not desired_technology.strip():
        return []
    return [part.strip() for part in desired_technology.split(",") if part.strip()]
