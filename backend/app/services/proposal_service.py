"""
Proposal submission, retrieval and status changes.

Port of Java's `ProposalService`. The access rules are the substance here, and
each is reproduced exactly:

**Submit** (STARTUP): the challenge must exist and be accepting — a `DRAFT` or
`CLOSED` challenge is a **409**, as is a second proposal from the same startup
(the table has a UNIQUE on the pair). Notifies the owning department.

**Read one**: an admin or expert may read any proposal; a government user only
those on their own department's challenges; a startup only its own. A startup
reaching for someone else's gets **403**, not 404 — matching Java, and unlike
challenge drafts, where existence itself is confidential.

**Read for a challenge**: government and admin are ownership-checked. Any
expert may list them — the schema has no expert-assignment table, so
"assigned" means "available to any expert", a deliberate documented choice.

**Status change** (GOVERNMENT owner or ADMIN): notifies the startup.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    Challenge,
    ChallengeStatus,
    NotificationType,
    Proposal,
    ProposalStatus,
    RoleName,
    User,
)
from app.repositories import (
    ChallengeRepository,
    ProposalRepository,
    StartupRepository,
    UserRepository,
)
from app.schemas.proposal import ProposalCreateRequest, ProposalResponse
from app.services.audit_service import Action, AuditService
from app.services.notification_service import NotificationService

#: A challenge in either of these states is not open for proposals.
CLOSED_TO_PROPOSALS = (ChallengeStatus.DRAFT, ChallengeStatus.CLOSED)


class ProposalService:
    def __init__(self, db: Session):
        self.db = db
        self.proposals = ProposalRepository(db)
        self.challenges = ChallengeRepository(db)
        self.startups = StartupRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # --------------------------------------------------------------- write

    def submit(self, actor: User, challenge_id: uuid.UUID,
               request: ProposalCreateRequest) -> ProposalResponse:
        startup = self.startups.find_by_user(actor.id)
        if startup is None:
            raise ApiException.forbidden("Only a startup account can submit proposals")

        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")
        if challenge.status in CLOSED_TO_PROPOSALS:
            raise ApiException.conflict(
                "This challenge is not currently accepting proposals")
        if self.proposals.find_by_challenge_and_startup(challenge_id, startup.id):
            raise ApiException.conflict(
                "You have already submitted a proposal for this challenge")

        proposal = self.proposals.add(Proposal(
            challenge_id=challenge_id,
            startup_id=startup.id,
            summary=request.summary,
            proposed_approach=request.proposed_approach,
            cost_estimate=(
                Decimal(str(request.cost_estimate))
                if request.cost_estimate is not None else None),
            timeline_estimate_days=request.timeline_estimate_days,
            status=ProposalStatus.SUBMITTED,
        ))

        self.audit.log(actor, Action.SUBMIT, "Proposal", proposal.id)
        self.notifications.notify(
            challenge.department.user,
            NotificationType.PROPOSAL_SUBMITTED,
            f'{startup.company_name} submitted a proposal for "{challenge.title}".',
        )
        self.db.commit()

        return ProposalResponse.from_entity(self.proposals.get(proposal.id, fresh=True))

    def update_status(self, actor: User, proposal_id: uuid.UUID,
                      new_status: ProposalStatus) -> ProposalResponse:
        proposal = self._must_find(proposal_id)
        self._assert_government_owner_or_admin(actor, proposal.challenge)

        proposal.status = new_status
        self.db.flush()

        self.audit.log(actor, Action.STATUS_CHANGE, "Proposal", proposal.id,
                       {"newStatus": new_status.value})
        self.notifications.notify(
            proposal.startup.user,
            NotificationType.PROPOSAL_STATUS_CHANGE,
            f'Your proposal for "{proposal.challenge.title}" is now {new_status.value}.',
        )
        self.db.commit()

        return ProposalResponse.from_entity(self.proposals.get(proposal_id, fresh=True))

    # ---------------------------------------------------------------- read

    def get_by_id(self, actor: User, proposal_id: uuid.UUID) -> ProposalResponse:
        proposal = self._must_find(proposal_id)
        role = actor.role.name

        if role in (RoleName.ADMIN, RoleName.EXPERT):
            return ProposalResponse.from_entity(proposal)
        if role is RoleName.GOVERNMENT:
            self._assert_government_owner_or_admin(actor, proposal.challenge)
            return ProposalResponse.from_entity(proposal)

        startup = self.startups.find_by_user(actor.id)
        if startup is not None and proposal.startup_id == startup.id:
            return ProposalResponse.from_entity(proposal)
        raise ApiException.forbidden("You do not have access to this proposal")

    def list_for_challenge(self, actor: User,
                           challenge_id: uuid.UUID) -> list[ProposalResponse]:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")
        if actor.role.name in (RoleName.GOVERNMENT, RoleName.ADMIN):
            self._assert_government_owner_or_admin(actor, challenge)
        # An expert reaching this point is permitted: see the module docstring.
        return [ProposalResponse.from_entity(p)
                for p in self.proposals.list_by_challenge(challenge_id)]

    def list_mine(self, actor: User) -> list[ProposalResponse]:
        startup = self.startups.find_by_user(actor.id)
        if startup is None:
            raise ApiException.forbidden("Only a startup account has proposals")
        return [ProposalResponse.from_entity(p)
                for p in self.proposals.list_by_startup(startup.id)]

    def list_expert_queue(self) -> list[ProposalResponse]:
        return [ProposalResponse.from_entity(p) for p in self.proposals.list_queue()]

    def get_entity(self, proposal_id: uuid.UUID) -> Proposal:
        """The ORM row, for services that need more than the response shape."""
        return self._must_find(proposal_id)

    # ------------------------------------------------------------ internal

    def _must_find(self, proposal_id: uuid.UUID) -> Proposal:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ApiException.not_found("Proposal not found")
        return proposal

    def _assert_government_owner_or_admin(self, actor: User, challenge: Challenge) -> None:
        if actor.role.name is RoleName.ADMIN:
            return
        department = self.users.find_department_by_user(actor.id)
        if department is None or department.id != challenge.department_id:
            raise ApiException.forbidden(
                "You do not have access to this challenge's proposals")
