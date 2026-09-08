"""
Knowledge base of completed pilots.

Port of Java's `KnowledgeBaseService`. Filtering is done in Python over the
whole table, matching the Java implementation and for the reason it gives: the
dataset is a few dozen closed pilots at most, and an in-memory filter is
simpler and just as correct as a dynamic query builder at that size.

The `success` filter is the part to be careful with. It is **tri-state**, and
the comparison is an identity check against `True` / `False` / `None`. A
truthiness test would make `success=false` also match the `None` rows —
silently reporting every MODIFY pilot as a failure.

`find_similar_for_draft` calls the real in-process embedding pipeline from
`app.ai`; it computes genuine cosine similarities and never a placeholder.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.pilot_repository import KnowledgeBaseRepository
from app.schemas.system import (
    KnowledgeBaseEntryResponse,
    SimilarPilotMatch,
    SimilarPilotsRequest,
    SimilarPilotsResponse,
)


class KnowledgeBaseService:
    def __init__(self, db: Session):
        self.db = db
        self.entries = KnowledgeBaseRepository(db)

    def search(self, *, domain: str | None = None, technology: str | None = None,
               success: bool | None = None,
               query: str | None = None) -> list[KnowledgeBaseEntryResponse]:
        """
        Filter past pilots. Every argument is optional and they combine with AND.

        `success` distinguishes three cases: ``True`` for scaled pilots,
        ``False`` for rejected, and ``None`` meaning "do not filter" — which is
        why the check below is `is None` rather than a falsy test.
        """
        results = []
        for entry in self.entries.list_all():
            if domain is not None and entry.domain.lower() != domain.lower():
                continue
            if technology is not None and not any(
                    technology.lower() in tag.lower()
                    for tag in (entry.technology_tags or [])):
                continue
            # Identity comparison: `success=False` must not match a NULL row.
            if success is not None and entry.success is not success:
                continue
            if query and query.lower() not in (entry.searchable_text or "").lower():
                continue
            results.append(KnowledgeBaseEntryResponse.from_entity(entry))
        return results

    def find_similar_for_draft(
            self, request: SimilarPilotsRequest) -> SimilarPilotsResponse:
        """
        Past pilots semantically similar to a challenge being drafted.

        Runs the genuine embedding pipeline: the draft's text is embedded with
        `all-MiniLM-L6-v2` and compared by cosine similarity against each
        stored entry's embedding.
        """
        from app.ai import find_similar_pilots_for_challenge, get_embedding_provider

        provider = get_embedding_provider()
        matches = find_similar_pilots_for_challenge(
            self.db, provider,
            title=request.title,
            problem_statement=request.problem_statement,
            desired_technology=request.desired_technology,
            domain=request.domain,
            outcomes_expected=request.outcomes_expected,
        )
        return SimilarPilotsResponse(
            ai_provider=provider.name,
            results=[SimilarPilotMatch(**match) for match in matches],
        )
