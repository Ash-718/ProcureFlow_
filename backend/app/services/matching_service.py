"""
AI startup matching.

Port of Java's `MatchingService`, with the Phase 5 change: `AiServiceClient`
made an HTTP call to :8081, and this calls `app.ai.run_matching_for_challenge`
directly on the caller's session. The pipeline, the weights, the embeddings and
the explanations are unchanged — only the transport is gone.

Access is restricted to the owning department or an admin. A startup must never
see how it ranked against its competitors, so this is a real control rather
than a formality.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ApiException
from app.models import Challenge, MatchResult, NotificationType, RoleName, User
from app.repositories import ChallengeRepository, UserRepository
from app.schemas.matching import (
    ComponentScores,
    MatchCandidate,
    MatchResponse,
    MatchResultRow,
)
from app.services.audit_service import Action, AuditService
from app.services.notification_service import NotificationService


class MatchingService:
    def __init__(self, db: Session):
        self.db = db
        self.challenges = ChallengeRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def run_matching(self, actor: User, challenge_id: uuid.UUID) -> MatchResponse:
        """
        Score every startup against one challenge and persist the ranking.

        Delegates to the real pipeline, which embeds anything not yet embedded,
        computes the five weighted components, and replaces this challenge's
        rows in `match_results`.
        """
        challenge = self._must_access(actor, challenge_id)

        from app.ai import get_embedding_provider, run_matching_for_challenge

        try:
            result = run_matching_for_challenge(
                self.db, str(challenge_id), get_embedding_provider(),
                top_n=settings.match_top_n)
        except ValueError as exc:
            raise ApiException.not_found(str(exc)) from exc

        self.audit.log(actor, Action.RUN_MATCHING, "Challenge", challenge_id,
                       {"candidates_considered": result["total_candidates_considered"]})
        self.notifications.notify(
            challenge.department.user, NotificationType.MATCH_READY,
            f'AI matching finished for "{challenge.title}" — '
            f"{len(result['results'])} candidate(s) ranked.")
        self.db.commit()

        return MatchResponse(
            challenge_id=uuid.UUID(result["challenge_id"])
            if isinstance(result["challenge_id"], str) else result["challenge_id"],
            ai_provider=result["ai_provider"],
            weights=result["weights"],
            total_candidates_considered=result["total_candidates_considered"],
            results=[
                MatchCandidate(
                    startup_id=candidate["startup_id"],
                    company_name=candidate["company_name"],
                    rank=candidate["rank"],
                    overall_score=candidate["overall_score"],
                    component_scores=ComponentScores(**candidate["component_scores"]),
                    reasons=candidate["reasons"],
                    gaps=candidate["gaps"],
                )
                for candidate in result["results"]
            ],
        )

    def get_results(self, actor: User, challenge_id: uuid.UUID) -> list[MatchResultRow]:
        """The stored ranking from the most recent run, best first."""
        self._must_access(actor, challenge_id)

        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        rows = self.db.execute(
            select(MatchResult)
            .options(joinedload(MatchResult.startup))
            .where(MatchResult.challenge_id == challenge_id)
            .order_by(MatchResult.rank)
        ).unique().scalars().all()
        return [MatchResultRow.from_entity(row) for row in rows]

    # ------------------------------------------------------------ internal

    def _must_access(self, actor: User, challenge_id: uuid.UUID) -> Challenge:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")

        if actor.role.name is RoleName.ADMIN:
            return challenge
        if actor.role.name is RoleName.GOVERNMENT:
            department = self.users.find_department_by_user(actor.id)
            if department is not None and department.id == challenge.department_id:
                return challenge

        raise ApiException.forbidden(
            "You do not have access to matching results for this challenge")
