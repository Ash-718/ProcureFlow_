"""Proposals, and the documents attached to them."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Document, DocumentOwnerType, Proposal, ProposalStatus

#: What the expert queue shows: anything still awaiting or under review.
QUEUE_STATUSES = (ProposalStatus.SUBMITTED, ProposalStatus.UNDER_REVIEW)


class ProposalRepository:
    def __init__(self, db: Session):
        self.db = db

    def _loaded(self, *, fresh: bool = False):
        """
        `ProposalResponse` flattens `challengeTitle` and `companyName` from the
        related rows, so both joins are eager — otherwise every list endpoint
        issues 2N extra queries.

        ``fresh`` adds ``populate_existing`` for reads that follow a write; see
        the note in `startup_repository.py` for why that is necessary here.
        """
        statement = (
            select(Proposal)
            .options(
                joinedload(Proposal.challenge),
                joinedload(Proposal.startup),
            )
        )
        return statement.execution_options(populate_existing=True) if fresh else statement

    def get(self, proposal_id: uuid.UUID, *, fresh: bool = False) -> Proposal | None:
        return self.db.execute(
            self._loaded(fresh=fresh).where(Proposal.id == proposal_id)
        ).unique().scalars().one_or_none()

    def find_by_challenge_and_startup(self, challenge_id: uuid.UUID,
                                      startup_id: uuid.UUID) -> Proposal | None:
        """Backs the one-proposal-per-startup-per-challenge rule."""
        return self.db.execute(
            self._loaded().where(
                Proposal.challenge_id == challenge_id,
                Proposal.startup_id == startup_id,
            )
        ).unique().scalars().one_or_none()

    def list_by_challenge(self, challenge_id: uuid.UUID) -> list[Proposal]:
        return list(self.db.execute(
            self._loaded()
            .where(Proposal.challenge_id == challenge_id)
            .order_by(Proposal.submitted_at.desc())
        ).unique().scalars())

    def list_by_startup(self, startup_id: uuid.UUID) -> list[Proposal]:
        return list(self.db.execute(
            self._loaded()
            .where(Proposal.startup_id == startup_id)
            .order_by(Proposal.submitted_at.desc())
        ).unique().scalars())

    def list_queue(self) -> list[Proposal]:
        """
        The expert review queue.

        Filtered in SQL rather than in Python. The Java service loaded every
        proposal and filtered in a stream, which is fine at seed scale but is
        not something worth carrying forward.
        """
        return list(self.db.execute(
            self._loaded()
            .where(Proposal.status.in_(QUEUE_STATUSES))
            .order_by(Proposal.submitted_at.desc())
        ).unique().scalars())

    def add(self, proposal: Proposal) -> Proposal:
        self.db.add(proposal)
        self.db.flush()
        return proposal


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_owner(self, owner_type: DocumentOwnerType,
                       owner_id: uuid.UUID) -> list[Document]:
        return list(self.db.execute(
            select(Document)
            .where(Document.owner_type == owner_type, Document.owner_id == owner_id)
            .order_by(Document.uploaded_at.desc())
        ).scalars())

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def add(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document
