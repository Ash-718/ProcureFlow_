"""
Pilot lifecycle: creation, milestones, KPI measurements and completion.

Port of Java's `PilotService`.

**Visibility.** Admin sees every pilot; a government user sees pilots on their
own department's challenges; a startup sees its own; an expert sees none — the
Java `listForActor` returns an empty list for EXPERT rather than raising, and
that is preserved.

**Management** (create, milestone update, KPI result, complete) requires the
owning department or an admin.

**KPI results are append-only.** `add_kpi_result` inserts a new row every time;
it never updates the previous measurement. The response reports the latest
value, but the history behind it stays intact — the recommendation engine and
any future trend view both depend on that.

**Completion** sets the terminal status, closes the challenge, and generates
the recommendation. Only COMPLETED or TERMINATED are accepted.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import (
    Challenge,
    ChallengeStatus,
    Contract,
    ContractStatus,
    Kpi,
    KpiResult,
    MilestoneStatus,
    NotificationType,
    Pilot,
    PilotMilestone,
    PilotStatus,
    RoleName,
    User,
)
from app.repositories import ChallengeRepository, StartupRepository, UserRepository
from app.repositories.pilot_repository import PilotRepository
from app.schemas.pilot import PilotCreateRequest, PilotResponse
from app.services.audit_service import Action, AuditService
from app.services.notification_service import NotificationService
from app.services.recommendation_service import RecommendationService

#: The only statuses a pilot may be completed into.
TERMINAL_STATUSES = (PilotStatus.COMPLETED, PilotStatus.TERMINATED)


class PilotService:
    def __init__(self, db: Session):
        self.db = db
        self.pilots = PilotRepository(db)
        self.challenges = ChallengeRepository(db)
        self.startups = StartupRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)
        self.recommendations = RecommendationService(db)

    # ---------------------------------------------------------------- read

    def get_by_id(self, actor: User, pilot_id: uuid.UUID) -> PilotResponse:
        pilot = self._must_find(pilot_id)
        self._assert_visible(actor, pilot)
        return PilotResponse.from_entity(pilot)

    def list_for_actor(self, actor: User) -> list[PilotResponse]:
        role = actor.role.name

        if role is RoleName.ADMIN:
            pilots = self.pilots.list_all()
        elif role is RoleName.GOVERNMENT:
            department = self.users.find_department_by_user(actor.id)
            if department is None:
                raise ApiException.not_found("No department profile for this account")
            challenge_ids = [c.id for c in
                             self.challenges.list_by_department(department.id)]
            pilots = self.pilots.list_by_challenges(challenge_ids)
        elif role is RoleName.STARTUP:
            startup = self.startups.find_by_user(actor.id)
            if startup is None:
                raise ApiException.not_found("No startup profile for this account")
            pilots = self.pilots.list_by_startup(startup.id)
        else:
            # EXPERT: an empty list, not a 403. Matches the Java service.
            pilots = []

        return [PilotResponse.from_entity(p) for p in pilots]

    # --------------------------------------------------------------- write

    def create(self, actor: User, request: PilotCreateRequest) -> PilotResponse:
        challenge = self.challenges.get(request.challenge_id)
        if challenge is None:
            raise ApiException.not_found("Challenge not found")
        self._assert_owner_or_admin(actor, challenge)

        startup = self.startups.get(request.startup_id)
        if startup is None:
            raise ApiException.not_found("Startup not found")

        contract = None
        if request.contract is not None:
            contract = self.pilots.add_contract(Contract(
                contract_value=(
                    Decimal(str(request.contract.contract_value))
                    if request.contract.contract_value is not None else None),
                ip_terms=request.contract.ip_terms,
                data_terms=request.contract.data_terms,
                payment_terms=request.contract.payment_terms,
                status=ContractStatus.ACTIVE,
            ))

        pilot = self.pilots.add(Pilot(
            challenge_id=challenge.id,
            startup_id=startup.id,
            contract_id=contract.id if contract is not None else None,
            start_date=request.start_date,
            end_date=request.end_date,
            status=PilotStatus.ACTIVE,
        ))

        for milestone in request.milestones:
            self.pilots.add_milestone(PilotMilestone(
                pilot_id=pilot.id, title=milestone.title,
                due_date=milestone.due_date, status=MilestoneStatus.PENDING))

        for kpi in request.kpis:
            self.pilots.add_kpi(Kpi(
                pilot_id=pilot.id, kpi_name=kpi.kpi_name,
                target_value=(Decimal(str(kpi.target_value))
                              if kpi.target_value is not None else None),
                unit=kpi.unit))

        challenge.status = ChallengeStatus.PILOT
        self.db.flush()

        self.audit.log(actor, Action.CREATE, "Pilot", pilot.id)
        self.notifications.notify(
            startup.user, NotificationType.PILOT_CREATED,
            f'A pilot has been created for "{challenge.title}".')
        self.db.commit()

        return PilotResponse.from_entity(self.pilots.get(pilot.id, fresh=True))

    def update_milestone(self, actor: User, pilot_id: uuid.UUID,
                         milestone_id: uuid.UUID, status: MilestoneStatus,
                         completion_date=None) -> PilotResponse:
        self._get_for_management(actor, pilot_id)

        milestone = self.pilots.get_milestone(pilot_id, milestone_id)
        if milestone is None:
            raise ApiException.not_found("Milestone not found on this pilot")

        milestone.status = status
        milestone.completion_date = completion_date
        self.db.flush()

        self.audit.log(actor, Action.UPDATE_MILESTONE, "PilotMilestone",
                       milestone_id, {"status": status.value})
        self.db.commit()

        return PilotResponse.from_entity(self.pilots.get(pilot_id, fresh=True))

    def add_kpi_result(self, actor: User, pilot_id: uuid.UUID, kpi_id: uuid.UUID,
                       recorded_value: float, notes: str | None = None) -> PilotResponse:
        """
        Append a KPI measurement.

        Strictly an insert. The previous measurement is never modified — the
        history is what makes a pilot's KPI trajectory auditable.
        """
        self._get_for_management(actor, pilot_id)

        kpi = self.pilots.get_kpi(pilot_id, kpi_id)
        if kpi is None:
            raise ApiException.not_found("KPI not found on this pilot")

        value = Decimal(str(recorded_value))
        self.pilots.add_kpi_result(KpiResult(
            kpi_id=kpi.id, recorded_value=value, notes=notes))

        self.audit.log(actor, Action.RECORD_KPI_RESULT, "Kpi", kpi_id,
                       {"recordedValue": str(value)})
        self.db.commit()

        return PilotResponse.from_entity(self.pilots.get(pilot_id, fresh=True))

    def complete(self, actor: User, pilot_id: uuid.UUID,
                 final_status: PilotStatus) -> PilotResponse:
        pilot = self._get_for_management(actor, pilot_id)

        if final_status not in TERMINAL_STATUSES:
            raise ApiException.bad_request(
                "finalStatus must be COMPLETED or TERMINATED")

        pilot.status = final_status
        pilot.challenge.status = ChallengeStatus.CLOSED
        self.db.flush()

        # Scores the pilot and upserts its knowledge-base entry, in this
        # transaction — completion and its recommendation commit together.
        self.recommendations.generate_for_pilot(pilot)

        self.audit.log(actor, Action.COMPLETE_PILOT, "Pilot", pilot_id,
                       {"finalStatus": final_status.value})
        self.db.commit()

        # Only now is the knowledge-base row visible to a fresh read.
        self.recommendations.flush_pending_embeddings()

        return PilotResponse.from_entity(self.pilots.get(pilot_id, fresh=True))

    # ------------------------------------------------------------ internal

    def _must_find(self, pilot_id: uuid.UUID) -> Pilot:
        pilot = self.pilots.get(pilot_id)
        if pilot is None:
            raise ApiException.not_found("Pilot not found")
        return pilot

    def _get_for_management(self, actor: User, pilot_id: uuid.UUID) -> Pilot:
        pilot = self._must_find(pilot_id)
        self._assert_owner_or_admin(actor, pilot.challenge)
        return pilot

    def _assert_owner_or_admin(self, actor: User, challenge: Challenge) -> None:
        if actor.role.name is RoleName.ADMIN:
            return
        department = self.users.find_department_by_user(actor.id)
        if department is None or department.id != challenge.department_id:
            raise ApiException.forbidden("You do not have access to this pilot")

    def _assert_visible(self, actor: User, pilot: Pilot) -> None:
        role = actor.role.name
        if role is RoleName.ADMIN:
            return
        if role is RoleName.GOVERNMENT:
            self._assert_owner_or_admin(actor, pilot.challenge)
            return
        if role is RoleName.STARTUP:
            startup = self.startups.find_by_user(actor.id)
            if startup is not None and startup.id == pilot.startup_id:
                return
        raise ApiException.forbidden("You do not have access to this pilot")
