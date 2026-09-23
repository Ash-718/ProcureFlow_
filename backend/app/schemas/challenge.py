"""
Challenge payloads.

Note two column-to-field renames the frontend depends on:
``challenge_requirements.is_mandatory`` is exposed as ``mandatory``, and the
department's name is flattened onto the challenge as ``departmentName``.
"""
from __future__ import annotations

import uuid

from pydantic import Field, computed_field

from app.models.enums import ChallengeStatus, RequirementType
from app.schemas.base import CamelModel, CamelRequest, OptionalInstant


class ChallengeRequirementResponse(CamelModel):
    id: uuid.UUID
    requirement_type: RequirementType
    description: str
    #: Column is `is_mandatory`; the API and frontend both call it `mandatory`.
    mandatory: bool


class ChallengeKpiResponse(CamelModel):
    id: uuid.UUID
    kpi_name: str
    #: `NUMERIC` on the database side — `float` here so Jackson's number
    #: encoding is reproduced (`75.00` -> `75.0`), not a Decimal string.
    target_value: float | None
    unit: str | None
    weight: float


class ChallengeResponse(CamelModel):
    id: uuid.UUID
    department_id: uuid.UUID
    #: Joined from `government_departments`, not a column on `challenges`.
    department_name: str
    title: str
    problem_statement: str
    desired_technology: str | None
    domain: str
    outcomes_expected: str | None
    budget_range: str | None
    timeline_days: int | None
    status: ChallengeStatus
    published_at: OptionalInstant
    requirements: list[ChallengeRequirementResponse] = []
    kpis: list[ChallengeKpiResponse] = []

    @classmethod
    def from_entity(cls, challenge) -> "ChallengeResponse":
        """Build from a `Challenge` ORM row, flattening the joined fields."""
        return cls(
            id=challenge.id,
            department_id=challenge.department_id,
            department_name=challenge.department.department_name,
            title=challenge.title,
            problem_statement=challenge.problem_statement,
            desired_technology=challenge.desired_technology,
            domain=challenge.domain,
            outcomes_expected=challenge.outcomes_expected,
            budget_range=challenge.budget_range,
            timeline_days=challenge.timeline_days,
            status=challenge.status,
            published_at=challenge.published_at,
            requirements=[
                ChallengeRequirementResponse(
                    id=r.id,
                    requirement_type=r.requirement_type,
                    description=r.description,
                    mandatory=r.is_mandatory,
                )
                for r in challenge.requirements
            ],
            kpis=[
                ChallengeKpiResponse(
                    id=k.id,
                    kpi_name=k.kpi_name,
                    target_value=float(k.target_value) if k.target_value is not None else None,
                    unit=k.unit,
                    weight=float(k.weight),
                )
                for k in challenge.kpis
            ],
        )


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class RequirementRequest(CamelRequest):
    requirement_type: RequirementType
    description: str = Field(min_length=1)
    mandatory: bool = True


class KpiRequest(CamelRequest):
    kpi_name: str = Field(min_length=1)
    target_value: float | None = None
    unit: str | None = None
    weight: float = 1.0


class ChallengeDraftRequest(CamelRequest):
    """The frontend's `ChallengeDraft`, used by both create and update."""

    title: str = Field(min_length=1, max_length=255)
    problem_statement: str = Field(min_length=1)
    desired_technology: str | None = None
    domain: str = Field(min_length=1, max_length=120)
    outcomes_expected: str | None = None
    budget_range: str | None = None
    timeline_days: int | None = None
    requirements: list[RequirementRequest] = []
    kpis: list[KpiRequest] = []


__all__ = [
    "ChallengeDraftRequest",
    "ChallengeKpiResponse",
    "ChallengeRequirementResponse",
    "ChallengeResponse",
    "KpiRequest",
    "RequirementRequest",
]
