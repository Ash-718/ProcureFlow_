"""
`/api/v1/startups` — profile self-service and the directory.

The `/me` endpoints resolve the caller's own startup from their user id, so a
startup can never address another's profile through them. The directory
endpoints are read-only and restricted to GOVERNMENT, EXPERT and ADMIN.

Route order matters: `/me` is declared before `/{startup_id}` so the literal
wins. Declared the other way round, FastAPI would try to parse `"me"` as a UUID
and return a validation error.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.startup import (
    CapabilityRequest,
    ProjectRequest,
    StartupResponse,
    UpdateStartupProfileRequest,
)
from app.security.deps import CurrentUserEntity, require_roles
from app.services.startup_service import StartupService

router = APIRouter(prefix="/api/v1/startups", tags=["startups"])

DbSession = Annotated[Session, Depends(get_db)]
StartupOnly = Depends(require_roles(RoleName.STARTUP))
ReviewerRoles = Depends(
    require_roles(RoleName.GOVERNMENT, RoleName.EXPERT, RoleName.ADMIN))


# ---------------------------------------------------------------------------
# Self-service — declared before /{startup_id}
# ---------------------------------------------------------------------------

@router.get("/me", response_model=StartupResponse, dependencies=[StartupOnly])
def my_profile(db: DbSession, actor: CurrentUserEntity) -> StartupResponse:
    service = StartupService(db)
    return service.get_profile(service.get_startup_for_user(actor.id).id)


@router.put("/me", response_model=StartupResponse, dependencies=[StartupOnly])
def update_my_profile(request: UpdateStartupProfileRequest, db: DbSession,
                      actor: CurrentUserEntity) -> StartupResponse:
    """
    Replace the caller's profile.

    A full replacement: an omitted optional field is cleared, which is what the
    Java service does. `readinessScore` is the one exception — omitting it
    leaves the current value alone.
    """
    service = StartupService(db)
    startup = service.get_startup_for_user(actor.id)
    return service.update_profile(actor, startup.id, request)


@router.post("/me/capabilities", response_model=StartupResponse,
             dependencies=[StartupOnly])
def add_capability(request: CapabilityRequest, db: DbSession,
                   actor: CurrentUserEntity) -> StartupResponse:
    """
    Add a capability and return the **whole** profile.

    200, not 201: the Java controller returns `ResponseEntity.ok` with the full
    profile so the client can re-render without a second request.
    """
    service = StartupService(db)
    startup = service.get_startup_for_user(actor.id)
    return service.add_capability(actor, startup.id, request)


@router.delete("/me/capabilities/{capability_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[StartupOnly])
def delete_capability(capability_id: uuid.UUID, db: DbSession,
                      actor: CurrentUserEntity) -> Response:
    """
    Remove one of the caller's capabilities.

    **204 No Content**, matching the Java controller. Idempotent: deleting an
    id that does not exist (or belongs to someone else) also returns 204 rather
    than disclosing which.
    """
    service = StartupService(db)
    startup = service.get_startup_for_user(actor.id)
    service.delete_capability(actor, startup.id, capability_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/projects", response_model=StartupResponse,
             dependencies=[StartupOnly])
def add_project(request: ProjectRequest, db: DbSession,
                actor: CurrentUserEntity) -> StartupResponse:
    """Add a past project and return the whole profile."""
    service = StartupService(db)
    startup = service.get_startup_for_user(actor.id)
    return service.add_project(actor, startup.id, request)


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------

@router.get("", response_model=list[StartupResponse], dependencies=[ReviewerRoles])
def list_startups(db: DbSession) -> list[StartupResponse]:
    """Every startup profile — the candidate pool matching draws from."""
    return StartupService(db).list_all()


@router.get("/{startup_id}", response_model=StartupResponse,
            dependencies=[ReviewerRoles])
def get_startup(startup_id: uuid.UUID, db: DbSession) -> StartupResponse:
    return StartupService(db).get_profile(startup_id)
