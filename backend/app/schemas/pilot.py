"""
Pilot, milestone, KPI, contract and recommendation payloads.

Two details carried over from the schema and worth restating here, because a
schema layer is exactly where they get flattened by accident:

* ``PilotKpiItem`` exposes the **latest** measurement from an append-only
  ``kpi_results`` history. It is not a mutable current value.
* ``Recommendation`` keeps ``recommendation`` (system-generated) and
  ``finalDecision`` (human) as separate fields. The UI must show them
  separately; merging them would misrepresent an undecided pilot as decided.
"""
from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import (
    MilestoneStatus,
    PilotStatus,
    RecommendationType,
)
from app.schemas.base import (
    CamelModel,
    CamelRequest,
    Instant,
    LocalDate,
    OptionalInstant,
    OptionalLocalDate,
)


class PilotMilestoneResponse(CamelModel):
    id: uuid.UUID
    title: str
    due_date: OptionalLocalDate
    status: MilestoneStatus
    completion_date: OptionalLocalDate


class PilotKpiResponse(CamelModel):
    id: uuid.UUID
    kpi_name: str
    target_value: float | None
    unit: str | None
    #: Most recent entry in the append-only `kpi_results` history; `None` until
    #: a measurement has been recorded.
    latest_recorded_value: float | None
    latest_recorded_at: OptionalInstant


class PilotContractResponse(CamelModel):
    id: uuid.UUID
    contract_value: float | None
    ip_terms: str | None
    data_terms: str | None
    payment_terms: str | None
    #: The frontend types this as a plain string, not a union.
    status: str


class PilotResponse(CamelModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    challenge_title: str
    startup_id: uuid.UUID
    company_name: str
    start_date: LocalDate
    end_date: OptionalLocalDate
    status: PilotStatus
    milestones: list[PilotMilestoneResponse] = []
    kpis: list[PilotKpiResponse] = []
    #: Null when the pilot runs without a formal contract row.
    contract: PilotContractResponse | None = None

    @classmethod
    def from_entity(cls, pilot) -> "PilotResponse":
        kpis: list[PilotKpiResponse] = []
        for kpi in pilot.kpis:
            latest = kpi.latest_result
            kpis.append(PilotKpiResponse(
                id=kpi.id,
                kpi_name=kpi.kpi_name,
                target_value=float(kpi.target_value) if kpi.target_value is not None else None,
                unit=kpi.unit,
                latest_recorded_value=(
                    float(latest.recorded_value) if latest is not None else None),
                latest_recorded_at=latest.recorded_at if latest is not None else None,
            ))

        contract = None
        if pilot.contract is not None:
            contract = PilotContractResponse(
                id=pilot.contract.id,
                contract_value=(
                    float(pilot.contract.contract_value)
                    if pilot.contract.contract_value is not None else None),
                ip_terms=pilot.contract.ip_terms,
                data_terms=pilot.contract.data_terms,
                payment_terms=pilot.contract.payment_terms,
                status=pilot.contract.status.value,
            )

        return cls(
            id=pilot.id,
            challenge_id=pilot.challenge_id,
            challenge_title=pilot.challenge.title,
            startup_id=pilot.startup_id,
            company_name=pilot.startup.company_name,
            start_date=pilot.start_date,
            end_date=pilot.end_date,
            status=pilot.status,
            milestones=[
                PilotMilestoneResponse.model_validate(m) for m in pilot.milestones
            ],
            kpis=kpis,
            contract=contract,
        )


class RecommendationResponse(CamelModel):
    """
    `GET /pilots/{id}/recommendation`.

    `recommendation` is the engine's output; `finalDecision` is the official's,
    and stays `null` until one is recorded. `reviewedByName` names the person
    who decided, or `null`.
    """

    id: uuid.UUID
    pilot_id: uuid.UUID
    recommendation: RecommendationType
    cost_score: float
    performance_score: float
    impact_score: float
    rationale_text: str
    generated_at: Instant
    reviewed_by_name: str | None
    final_decision: RecommendationType | None
    decided_at: OptionalInstant

    @classmethod
    def from_entity(cls, recommendation) -> "RecommendationResponse":
        return cls(
            id=recommendation.id,
            pilot_id=recommendation.pilot_id,
            recommendation=recommendation.recommendation,
            cost_score=float(recommendation.cost_score),
            performance_score=float(recommendation.performance_score),
            impact_score=float(recommendation.impact_score),
            rationale_text=recommendation.rationale_text,
            generated_at=recommendation.generated_at,
            reviewed_by_name=(
                recommendation.reviewer.full_name if recommendation.reviewer else None),
            final_decision=recommendation.final_decision,
            decided_at=recommendation.decided_at,
        )


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class MilestoneCreateRequest(CamelRequest):
    title: str = Field(min_length=1, max_length=255)
    due_date: OptionalLocalDate = None


class PilotKpiCreateRequest(CamelRequest):
    kpi_name: str = Field(min_length=1, max_length=255)
    target_value: float | None = None
    unit: str | None = None


class ContractCreateRequest(CamelRequest):
    contract_value: float | None = None
    ip_terms: str | None = None
    data_terms: str | None = None
    payment_terms: str | None = None


class PilotCreateRequest(CamelRequest):
    challenge_id: uuid.UUID
    startup_id: uuid.UUID
    start_date: LocalDate
    end_date: OptionalLocalDate = None
    milestones: list[MilestoneCreateRequest] = []
    kpis: list[PilotKpiCreateRequest] = []
    contract: ContractCreateRequest | None = None


class MilestoneUpdateRequest(CamelRequest):
    status: MilestoneStatus
    completion_date: OptionalLocalDate = None


class KpiResultRequest(CamelRequest):
    recorded_value: float
    notes: str | None = None


class PilotCompleteRequest(CamelRequest):
    #: Only the two terminal states are accepted.
    final_status: PilotStatus

    @property
    def is_valid_terminal_state(self) -> bool:
        return self.final_status in (PilotStatus.COMPLETED, PilotStatus.TERMINATED)


class FinalDecisionRequest(CamelRequest):
    final_decision: RecommendationType


__all__ = [
    "ContractCreateRequest",
    "FinalDecisionRequest",
    "KpiResultRequest",
    "MilestoneCreateRequest",
    "MilestoneUpdateRequest",
    "PilotCompleteRequest",
    "PilotContractResponse",
    "PilotCreateRequest",
    "PilotKpiCreateRequest",
    "PilotKpiResponse",
    "PilotMilestoneResponse",
    "PilotResponse",
    "RecommendationResponse",
]
