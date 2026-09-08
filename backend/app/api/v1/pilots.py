"""
`/api/v1/pilots` — pilot lifecycle, milestones, KPI tracking and the
Scale / Modify / Reject recommendation.

Reads are open to any authenticated caller and scoped by ownership in the
service; management operations are GOVERNMENT-or-ADMIN.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.pilot import (
    FinalDecisionRequest,
    KpiResultRequest,
    MilestoneUpdateRequest,
    PilotCompleteRequest,
    PilotCreateRequest,
    PilotResponse,
    RecommendationResponse,
)
from app.security.deps import CurrentUserEntity, require_roles
from app.services.pilot_service import PilotService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/api/v1/pilots", tags=["pilots"])

DbSession = Annotated[Session, Depends(get_db)]
GovernmentOrAdmin = Depends(require_roles(RoleName.GOVERNMENT, RoleName.ADMIN))


@router.post("", response_model=PilotResponse,
             status_code=status.HTTP_201_CREATED, dependencies=[GovernmentOrAdmin])
def create_pilot(request: PilotCreateRequest, db: DbSession,
                 actor: CurrentUserEntity) -> PilotResponse:
    """
    Start a controlled pilot. Returns **201**.

    Creates the optional contract, the milestone plan and the KPI definitions,
    moves the challenge to PILOT, and notifies the startup.
    """
    return PilotService(db).create(actor, request)


@router.get("", response_model=list[PilotResponse])
def list_pilots(db: DbSession, actor: CurrentUserEntity) -> list[PilotResponse]:
    """
    Pilots visible to the caller.

    An expert receives an empty list rather than a 403 — matching the Java
    service, which simply has no pilot view for that role.
    """
    return PilotService(db).list_for_actor(actor)


@router.get("/{pilot_id}", response_model=PilotResponse)
def get_pilot(pilot_id: uuid.UUID, db: DbSession,
              actor: CurrentUserEntity) -> PilotResponse:
    return PilotService(db).get_by_id(actor, pilot_id)


@router.patch("/{pilot_id}/milestones/{milestone_id}", response_model=PilotResponse,
              dependencies=[GovernmentOrAdmin])
def update_milestone(pilot_id: uuid.UUID, milestone_id: uuid.UUID,
                     request: MilestoneUpdateRequest, db: DbSession,
                     actor: CurrentUserEntity) -> PilotResponse:
    """
    Move a milestone through its states.

    A milestone belonging to a different pilot is a 404 — the id is only
    addressable through its own pilot.
    """
    return PilotService(db).update_milestone(
        actor, pilot_id, milestone_id, request.status, request.completion_date)


@router.post("/{pilot_id}/kpis/{kpi_id}/results", response_model=PilotResponse,
             dependencies=[GovernmentOrAdmin])
def add_kpi_result(pilot_id: uuid.UUID, kpi_id: uuid.UUID,
                   request: KpiResultRequest, db: DbSession,
                   actor: CurrentUserEntity) -> PilotResponse:
    """
    Record a KPI measurement.

    **Appends** to the KPI's history; it never overwrites the previous value.
    The response shows the latest reading, and every earlier one is retained.
    """
    return PilotService(db).add_kpi_result(
        actor, pilot_id, kpi_id, request.recorded_value, request.notes)


@router.post("/{pilot_id}/complete", response_model=PilotResponse,
             dependencies=[GovernmentOrAdmin])
def complete_pilot(pilot_id: uuid.UUID, request: PilotCompleteRequest,
                   db: DbSession, actor: CurrentUserEntity) -> PilotResponse:
    """
    Close a pilot as COMPLETED or TERMINATED.

    Closes the challenge and generates the Scale / Modify / Reject
    recommendation from the recorded KPIs and milestone adherence.
    """
    return PilotService(db).complete(actor, pilot_id, request.final_status)


@router.get("/{pilot_id}/recommendation", response_model=RecommendationResponse)
def get_recommendation(pilot_id: uuid.UUID, db: DbSession,
                       actor: CurrentUserEntity) -> RecommendationResponse:
    """
    The pilot's recommendation.

    Carries the system's `recommendation` and the human `finalDecision` as
    separate fields; the latter is null until an official records one.
    """
    return RecommendationService(db).get_by_pilot_id(pilot_id)


@router.post("/{pilot_id}/recommendation/decision",
             response_model=RecommendationResponse, dependencies=[GovernmentOrAdmin])
def record_decision(pilot_id: uuid.UUID, request: FinalDecisionRequest,
                    db: DbSession, actor: CurrentUserEntity) -> RecommendationResponse:
    """
    Record the official's decision.

    Leaves the system recommendation untouched, so the two remain comparable —
    including where a human overrode the engine.
    """
    return RecommendationService(db).record_final_decision(
        actor, pilot_id, request.final_decision)
