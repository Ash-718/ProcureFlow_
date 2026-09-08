"""Startup profile, capabilities and delivery history."""
from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import ClientType
from app.schemas.base import CamelModel, CamelRequest


class StartupCapabilityResponse(CamelModel):
    id: uuid.UUID
    technology_tag: str
    domain_tag: str
    proficiency_level: int
    description: str | None


class StartupProjectResponse(CamelModel):
    id: uuid.UUID
    title: str
    domain: str
    technology_stack: str | None
    client_type: ClientType
    outcome_summary: str | None
    year: int | None


class StartupResponse(CamelModel):
    id: uuid.UUID
    company_name: str
    dpiit_number: str | None
    founded_year: int | None
    team_size: int | None
    city: str | None
    state: str | None
    #: `NUMERIC(5,2)` -> float, so `50.00` serialises as `50.0`.
    readiness_score: float
    description: str | None
    capabilities: list[StartupCapabilityResponse] = []
    projects: list[StartupProjectResponse] = []

    @classmethod
    def from_entity(cls, startup) -> "StartupResponse":
        return cls(
            id=startup.id,
            company_name=startup.company_name,
            dpiit_number=startup.dpiit_number,
            founded_year=startup.founded_year,
            team_size=startup.team_size,
            city=startup.city,
            state=startup.state,
            readiness_score=float(startup.readiness_score),
            description=startup.description,
            capabilities=[
                StartupCapabilityResponse.model_validate(c) for c in startup.capabilities
            ],
            projects=[
                StartupProjectResponse.model_validate(p) for p in startup.projects
            ],
        )


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class UpdateStartupProfileRequest(CamelRequest):
    company_name: str = Field(min_length=1, max_length=255)
    dpiit_number: str | None = None
    founded_year: int | None = None
    team_size: int | None = None
    city: str | None = None
    state: str | None = None
    description: str | None = None
    #: Feeds the readiness component of the matching formula, hence the bounds.
    readiness_score: float | None = Field(default=None, ge=0, le=100)


class CapabilityRequest(CamelRequest):
    technology_tag: str = Field(min_length=1, max_length=120)
    domain_tag: str = Field(min_length=1, max_length=120)
    #: The schema enforces 1-5 with a CHECK constraint; mirrored here so a bad
    #: value is a 400 with a field error rather than a database exception.
    proficiency_level: int = Field(default=3, ge=1, le=5)
    description: str | None = None


class ProjectRequest(CamelRequest):
    title: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=120)
    technology_stack: str | None = None
    client_type: ClientType = ClientType.PRIVATE
    outcome_summary: str | None = None
    year: int | None = None


__all__ = [
    "CapabilityRequest",
    "ProjectRequest",
    "StartupCapabilityResponse",
    "StartupProjectResponse",
    "StartupResponse",
    "UpdateStartupProfileRequest",
]
