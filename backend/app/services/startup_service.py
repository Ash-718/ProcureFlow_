"""
Startup profile management.

Port of Java's `StartupService`. Points where the Java behaviour is specific
and is reproduced rather than tidied:

* `updateProfile` assigns every optional field **unconditionally**, so omitting
  one clears it — a PUT replacing the whole resource. Only `readinessScore` is
  guarded by a null check. That asymmetry is in the Java code and changing it
  here would make the two backends disagree on the same request.
* Adding a capability or project returns the **whole** profile, not the created
  child, and does **not** write an audit entry. Only `updateProfile` does.
* Every mutation queues a best-effort embedding refresh, because capabilities
  and projects feed the matching formula.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import Startup, StartupCapability, StartupProject, User
from app.repositories import StartupRepository
from app.schemas.startup import (
    CapabilityRequest,
    ProjectRequest,
    StartupResponse,
    UpdateStartupProfileRequest,
)
from app.services.audit_service import Action, AuditService
from app.services.embedding_hooks import refresh_startup_embedding


class StartupService:
    def __init__(self, db: Session):
        self.db = db
        self.startups = StartupRepository(db)
        self.audit = AuditService(db)

    # ---------------------------------------------------------------- read

    def get_startup_for_user(self, user_id: uuid.UUID) -> Startup:
        startup = self.startups.find_by_user(user_id)
        if startup is None:
            raise ApiException.not_found("No startup profile found for this account")
        return startup

    def get_profile(self, startup_id: uuid.UUID, *, fresh: bool = False) -> StartupResponse:
        startup = self.startups.get(startup_id, fresh=fresh)
        if startup is None:
            raise ApiException.not_found("Startup not found")
        return StartupResponse.from_entity(startup)

    def list_all(self) -> list[StartupResponse]:
        return [StartupResponse.from_entity(s) for s in self.startups.list_all()]

    # --------------------------------------------------------------- write

    def update_profile(self, actor: User, startup_id: uuid.UUID,
                       request: UpdateStartupProfileRequest) -> StartupResponse:
        startup = self._must_own(actor, startup_id)

        # Unconditional assignment: a PUT replaces the resource, so an omitted
        # field is cleared. Matches the Java setters exactly.
        startup.company_name = request.company_name
        startup.dpiit_number = request.dpiit_number
        startup.founded_year = request.founded_year
        startup.team_size = request.team_size
        startup.city = request.city
        startup.state = request.state
        startup.description = request.description
        if request.readiness_score is not None:
            startup.readiness_score = Decimal(str(request.readiness_score))
        self.db.flush()

        self.audit.log(actor, Action.UPDATE_PROFILE, "Startup", startup.id)
        self.db.commit()
        refresh_startup_embedding(self.db, startup_id)

        return self.get_profile(startup_id, fresh=True)

    def add_capability(self, actor: User, startup_id: uuid.UUID,
                       request: CapabilityRequest) -> StartupResponse:
        self._must_own(actor, startup_id)
        self.startups.add_capability(StartupCapability(
            startup_id=startup_id,
            technology_tag=request.technology_tag,
            domain_tag=request.domain_tag,
            proficiency_level=request.proficiency_level,
            description=request.description,
        ))
        self.db.commit()
        refresh_startup_embedding(self.db, startup_id)
        return self.get_profile(startup_id, fresh=True)

    def delete_capability(self, actor: User, startup_id: uuid.UUID,
                          capability_id: uuid.UUID) -> None:
        self._must_own(actor, startup_id)
        # Scoped delete: a capability belonging to another startup matches no
        # rows rather than being removed. Java behaves the same way, and like
        # Java this reports success either way — DELETE is idempotent.
        self.startups.delete_capability(startup_id, capability_id)
        self.db.commit()
        refresh_startup_embedding(self.db, startup_id)

    def add_project(self, actor: User, startup_id: uuid.UUID,
                    request: ProjectRequest) -> StartupResponse:
        self._must_own(actor, startup_id)
        self.startups.add_project(StartupProject(
            startup_id=startup_id,
            title=request.title,
            domain=request.domain,
            technology_stack=request.technology_stack,
            client_type=request.client_type,
            outcome_summary=request.outcome_summary,
            year=request.year,
        ))
        self.db.commit()
        refresh_startup_embedding(self.db, startup_id)
        return self.get_profile(startup_id, fresh=True)

    # ------------------------------------------------------------ internal

    def _must_own(self, actor: User, startup_id: uuid.UUID) -> Startup:
        startup = self.startups.get(startup_id)
        if startup is None:
            raise ApiException.not_found("Startup not found")
        if startup.user_id != actor.id:
            raise ApiException.forbidden("You do not own this startup profile")
        return startup
