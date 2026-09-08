"""
Challenge lifecycle.

Port of Java's `ChallengeService`. The rules worth stating explicitly, because
each is load-bearing for RBAC and each is reproduced exactly:

**Visibility.** An admin sees everything. A non-DRAFT challenge is visible to
any authenticated user. A DRAFT is visible *only* to the government department
that owns it — and an unauthorised read returns **404, not 403**, so the
existence of another department's draft is not disclosed.

**Mutation.** Create, update and publish require a government account with a
department profile. Update and publish additionally require ownership and
`DRAFT` status; editing a published challenge is a **409**.

**Publish** requires at least one requirement, stamps `published_at`, and seeds
the default four-criterion rubric if the challenge has none. The rubric weights
(0.30 / 0.25 / 0.25 / 0.20) are what every later evaluation scores against, so
they are pinned as a constant.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    Challenge,
    ChallengeKpi,
    ChallengeRequirement,
    ChallengeStatus,
    EvaluationCriterion,
    RoleName,
    User,
)
from app.repositories import ChallengeRepository, UserRepository
from app.schemas.challenge import ChallengeDraftRequest, ChallengeResponse
from app.services.audit_service import Action, AuditService
from app.services.embedding_hooks import refresh_challenge_embedding

#: Seeded on publish when a challenge has no rubric yet. Weights sum to 1.00.
DEFAULT_EVALUATION_CRITERIA: tuple[tuple[str, str], ...] = (
    ("Technical Feasibility", "0.30"),
    ("Cost Effectiveness", "0.25"),
    ("Scalability", "0.25"),
    ("Team Capability", "0.20"),
)
DEFAULT_CRITERION_MAX_SCORE = Decimal("10")


class ChallengeService:
    def __init__(self, db: Session):
        self.db = db
        self.challenges = ChallengeRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    # ---------------------------------------------------------------- read

    def get_by_id(self, actor: User, challenge_id: uuid.UUID) -> ChallengeResponse:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")
        self._assert_visible(actor, challenge)
        return ChallengeResponse.from_entity(challenge)

    def list_for_actor(self, actor: User) -> list[ChallengeResponse]:
        role = actor.role.name
        if role is RoleName.ADMIN:
            challenges = self.challenges.list_all()
        elif role is RoleName.GOVERNMENT:
            department = self.users.find_department_by_user(actor.id)
            if department is None:
                raise ApiException.not_found("No department profile for this account")
            challenges = self.challenges.list_by_department(department.id)
        else:
            challenges = self.challenges.list_public()
        return [ChallengeResponse.from_entity(c) for c in challenges]

    # --------------------------------------------------------------- write

    def create(self, actor: User, request: ChallengeDraftRequest) -> ChallengeResponse:
        department = self.users.find_department_by_user(actor.id)
        if department is None:
            raise ApiException.forbidden(
                "Only a government department account can create challenges")

        challenge = self.challenges.add(Challenge(
            department_id=department.id,
            status=ChallengeStatus.DRAFT,
            **self._field_values(request),
        ))
        self._save_requirements_and_kpis(challenge.id, request)

        self.audit.log(actor, Action.CREATE, "Challenge", challenge.id)
        self.db.commit()

        return ChallengeResponse.from_entity(self.challenges.get(challenge.id, fresh=True))

    def update(self, actor: User, challenge_id: uuid.UUID,
               request: ChallengeDraftRequest) -> ChallengeResponse:
        challenge = self._must_own_as_draft(actor, challenge_id)

        for field, value in self._field_values(request).items():
            setattr(challenge, field, value)
        self.db.flush()

        # Wholesale replacement, as the Java service does — see the note on
        # `ChallengeRepository.replace_requirements`.
        self._save_requirements_and_kpis(challenge.id, request, replace=True)

        self.audit.log(actor, Action.UPDATE, "Challenge", challenge.id)
        self.db.commit()

        return ChallengeResponse.from_entity(self.challenges.get(challenge.id, fresh=True))

    def publish(self, actor: User, challenge_id: uuid.UUID) -> ChallengeResponse:
        challenge = self._must_own_as_draft(actor, challenge_id)

        if self.challenges.count_requirements(challenge_id) == 0:
            raise ApiException.bad_request(
                "Add at least one eligibility/technical requirement before publishing")

        challenge.status = ChallengeStatus.PUBLISHED
        challenge.published_at = datetime.now(timezone.utc)
        self.db.flush()

        self._ensure_default_evaluation_criteria(challenge_id)

        self.audit.log(actor, Action.PUBLISH, "Challenge", challenge.id)
        self.db.commit()

        # After commit, mirroring Java's AfterCommitRunner: the AI code reads
        # the row in its own transaction and would not see it before commit.
        refresh_challenge_embedding(self.db, challenge_id)

        return ChallengeResponse.from_entity(self.challenges.get(challenge_id, fresh=True))

    # ------------------------------------------------------------ internal

    def _assert_visible(self, actor: User, challenge: Challenge) -> None:
        role = actor.role.name
        if role is RoleName.ADMIN:
            return
        if challenge.status is not ChallengeStatus.DRAFT:
            return
        if role is RoleName.GOVERNMENT:
            department = self.users.find_department_by_user(actor.id)
            if department is not None and department.id == challenge.department_id:
                return
        # 404 rather than 403 — a draft's existence is itself confidential.
        raise ApiException.not_found("Challenge not found")

    def _must_own_as_draft(self, actor: User, challenge_id: uuid.UUID) -> Challenge:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")

        department = self.users.find_department_by_user(actor.id)
        if department is None:
            raise ApiException.forbidden(
                "Only a government department account can manage challenges")
        if challenge.department_id != department.id:
            raise ApiException.forbidden("You do not own this challenge")
        if challenge.status is not ChallengeStatus.DRAFT:
            raise ApiException.conflict("Only a DRAFT challenge can be edited or published")
        return challenge

    @staticmethod
    def _field_values(request: ChallengeDraftRequest) -> dict:
        return {
            "title": request.title,
            "problem_statement": request.problem_statement,
            "desired_technology": request.desired_technology,
            "domain": request.domain,
            "outcomes_expected": request.outcomes_expected,
            "budget_range": request.budget_range,
            "timeline_days": request.timeline_days,
        }

    def _save_requirements_and_kpis(self, challenge_id: uuid.UUID,
                                    request: ChallengeDraftRequest,
                                    *, replace: bool = False) -> None:
        requirements = [
            ChallengeRequirement(
                challenge_id=challenge_id,
                requirement_type=r.requirement_type,
                description=r.description,
                is_mandatory=r.mandatory,
            )
            for r in request.requirements
        ]
        kpis = [
            ChallengeKpi(
                challenge_id=challenge_id,
                kpi_name=k.kpi_name,
                target_value=Decimal(str(k.target_value)) if k.target_value is not None else None,
                unit=k.unit,
                weight=Decimal(str(k.weight)),
            )
            for k in request.kpis
        ]

        if replace:
            self.challenges.replace_requirements(challenge_id, requirements)
            self.challenges.replace_kpis(challenge_id, kpis)
        else:
            for entity in (*requirements, *kpis):
                self.db.add(entity)
            self.db.flush()

    def _ensure_default_evaluation_criteria(self, challenge_id: uuid.UUID) -> None:
        """Seed the rubric only when the challenge has none — never overwrite."""
        if self.challenges.list_criteria(challenge_id):
            return
        self.challenges.add_criteria([
            EvaluationCriterion(
                challenge_id=challenge_id,
                criterion_name=name,
                max_score=DEFAULT_CRITERION_MAX_SCORE,
                weight=Decimal(weight),
            )
            for name, weight in DEFAULT_EVALUATION_CRITERIA
        ])
