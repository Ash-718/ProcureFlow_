"""Startup profiles, capabilities and delivery history."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import Startup, StartupCapability, StartupProject


class StartupRepository:
    def __init__(self, db: Session):
        self.db = db

    def _loaded(self, *, fresh: bool = False):
        """
        Base query with the response collections eager-loaded.

        ``fresh=True`` adds ``populate_existing``, which is required after a
        write. The session is configured with ``expire_on_commit=False`` (so
        response serialisation cannot trigger a detached lazy-load), which
        means a committed mutation leaves the identity-mapped object holding
        its *previous* collection — `selectinload` will not overwrite an
        already-loaded collection unless told to. Without this, adding a
        capability returns a profile that does not contain it.
        """
        statement = (
            select(Startup)
            .options(
                selectinload(Startup.capabilities),
                selectinload(Startup.projects),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def get(self, startup_id: uuid.UUID, *, fresh: bool = False) -> Startup | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Startup.id == startup_id)
        ).scalars().one_or_none()

    def find_by_user(self, user_id: uuid.UUID, *, fresh: bool = False) -> Startup | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Startup.user_id == user_id)
        ).scalars().one_or_none()

    def list_all(self) -> list[Startup]:
        return list(self.db.execute(
            self._loaded().order_by(Startup.company_name)).scalars())

    # -- capabilities -----------------------------------------------------

    def add_capability(self, capability: StartupCapability) -> StartupCapability:
        self.db.add(capability)
        self.db.flush()
        return capability

    def delete_capability(self, startup_id: uuid.UUID, capability_id: uuid.UUID) -> int:
        """
        Delete one capability, scoped to its owning startup.

        The `startup_id` predicate is the security control, not a convenience:
        without it a startup could delete another's capability by guessing an
        ID. `StartupCapabilityRepository.deleteByStartupIdAndId` scopes it the
        same way. Returns the number of rows removed.
        """
        result = self.db.execute(
            delete(StartupCapability).where(
                StartupCapability.id == capability_id,
                StartupCapability.startup_id == startup_id,
            )
        )
        self.db.flush()
        return result.rowcount or 0

    # -- projects ---------------------------------------------------------

    def add_project(self, project: StartupProject) -> StartupProject:
        self.db.add(project)
        self.db.flush()
        return project

    def refresh(self, startup: Startup) -> Startup:
        """Re-read the collections after a mutation so the response is current."""
        self.db.refresh(startup)
        return startup
