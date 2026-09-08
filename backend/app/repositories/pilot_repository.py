"""
Pilots, milestones, KPIs, KPI results, recommendations and the knowledge base.

The KPI-result methods are the ones to be careful with: `kpi_results` is
**append-only**. Nothing here updates or deletes a result row — `add_result`
inserts, and `latest_result` reads the newest. Overwriting would destroy the
audit history the recommendation engine and the KPI timeline both depend on.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Contract,
    Kpi,
    KpiResult,
    Pilot,
    PilotKnowledgeBase,
    PilotMilestone,
    Recommendation,
)


class PilotRepository:
    def __init__(self, db: Session):
        self.db = db

    def _loaded(self, *, fresh: bool = False):
        """
        Everything `PilotResponse` renders, eager-loaded.

        `Kpi.results` is included because `latest_result` walks it; without the
        eager load, a pilot with six KPIs issues six extra queries per response.
        """
        statement = (
            select(Pilot)
            .options(
                joinedload(Pilot.challenge),
                joinedload(Pilot.startup),
                joinedload(Pilot.contract),
                selectinload(Pilot.milestones),
                selectinload(Pilot.kpis).selectinload(Kpi.results),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def get(self, pilot_id: uuid.UUID, *, fresh: bool = False) -> Pilot | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Pilot.id == pilot_id)
        ).unique().scalars().one_or_none()

    def list_all(self) -> list[Pilot]:
        return list(self.db.execute(
            self._loaded().order_by(Pilot.start_date.desc())).unique().scalars())

    def list_by_challenges(self, challenge_ids: list[uuid.UUID]) -> list[Pilot]:
        if not challenge_ids:
            return []
        return list(self.db.execute(
            self._loaded()
            .where(Pilot.challenge_id.in_(challenge_ids))
            .order_by(Pilot.start_date.desc())
        ).unique().scalars())

    def list_by_startup(self, startup_id: uuid.UUID) -> list[Pilot]:
        return list(self.db.execute(
            self._loaded()
            .where(Pilot.startup_id == startup_id)
            .order_by(Pilot.start_date.desc())
        ).unique().scalars())

    def add(self, pilot: Pilot) -> Pilot:
        self.db.add(pilot)
        self.db.flush()
        return pilot

    def add_contract(self, contract: Contract) -> Contract:
        self.db.add(contract)
        self.db.flush()
        return contract

    # -- milestones -------------------------------------------------------

    def list_milestones(self, pilot_id: uuid.UUID) -> list[PilotMilestone]:
        return list(self.db.execute(
            select(PilotMilestone)
            .where(PilotMilestone.pilot_id == pilot_id)
            .order_by(PilotMilestone.due_date)
        ).scalars())

    def get_milestone(self, pilot_id: uuid.UUID,
                      milestone_id: uuid.UUID) -> PilotMilestone | None:
        """Scoped to the pilot — a milestone id alone must not be addressable."""
        return self.db.execute(
            select(PilotMilestone).where(
                PilotMilestone.id == milestone_id,
                PilotMilestone.pilot_id == pilot_id,
            )
        ).scalars().one_or_none()

    def add_milestone(self, milestone: PilotMilestone) -> PilotMilestone:
        self.db.add(milestone)
        self.db.flush()
        return milestone

    # -- KPIs -------------------------------------------------------------

    def list_kpis(self, pilot_id: uuid.UUID) -> list[Kpi]:
        return list(self.db.execute(
            select(Kpi).options(selectinload(Kpi.results))
            .where(Kpi.pilot_id == pilot_id)
        ).unique().scalars())

    def get_kpi(self, pilot_id: uuid.UUID, kpi_id: uuid.UUID) -> Kpi | None:
        return self.db.execute(
            select(Kpi).options(selectinload(Kpi.results))
            .where(Kpi.id == kpi_id, Kpi.pilot_id == pilot_id)
        ).unique().scalars().one_or_none()

    def add_kpi(self, kpi: Kpi) -> Kpi:
        self.db.add(kpi)
        self.db.flush()
        return kpi

    def add_kpi_result(self, result: KpiResult) -> KpiResult:
        """
        Append one measurement.

        Insert only. `kpi_results` is append-only history, so a re-measurement
        adds a row rather than replacing the previous value.
        """
        self.db.add(result)
        self.db.flush()
        return result

    def latest_kpi_result(self, kpi_id: uuid.UUID) -> KpiResult | None:
        """Newest measurement for one KPI, by `recorded_at`."""
        return self.db.execute(
            select(KpiResult)
            .where(KpiResult.kpi_id == kpi_id)
            .order_by(KpiResult.recorded_at.desc())
            .limit(1)
        ).scalars().first()

    def count_kpi_results(self, kpi_id: uuid.UUID) -> int:
        from sqlalchemy import func

        return self.db.execute(
            select(func.count()).select_from(KpiResult)
            .where(KpiResult.kpi_id == kpi_id)
        ).scalar_one()

    # -- recommendations --------------------------------------------------

    def get_recommendation(self, pilot_id: uuid.UUID,
                           *, fresh: bool = False) -> Recommendation | None:
        statement = (
            select(Recommendation)
            .options(
                joinedload(Recommendation.reviewer),
                joinedload(Recommendation.pilot).joinedload(Pilot.challenge),
            )
            .where(Recommendation.pilot_id == pilot_id)
        )
        if fresh:
            statement = statement.execution_options(populate_existing=True)
        return self.db.execute(statement).unique().scalars().one_or_none()

    def add_recommendation(self, recommendation: Recommendation) -> Recommendation:
        self.db.add(recommendation)
        self.db.flush()
        return recommendation


class KnowledgeBaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def _loaded(self, *, fresh: bool = False):
        statement = (
            select(PilotKnowledgeBase)
            .options(
                joinedload(PilotKnowledgeBase.department),
                joinedload(PilotKnowledgeBase.pilot).joinedload(Pilot.challenge),
                joinedload(PilotKnowledgeBase.pilot).joinedload(Pilot.startup),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def list_all(self) -> list[PilotKnowledgeBase]:
        return list(self.db.execute(
            self._loaded().order_by(PilotKnowledgeBase.created_at.desc())
        ).unique().scalars())

    def find_by_pilot(self, pilot_id: uuid.UUID,
                      *, fresh: bool = False) -> PilotKnowledgeBase | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(PilotKnowledgeBase.pilot_id == pilot_id)
        ).unique().scalars().one_or_none()

    def add(self, entry: PilotKnowledgeBase) -> PilotKnowledgeBase:
        self.db.add(entry)
        self.db.flush()
        return entry
