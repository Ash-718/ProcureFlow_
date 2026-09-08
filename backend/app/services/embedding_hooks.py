"""
Best-effort embedding refresh hooks.

Java's `ChallengeService.publish` and the `StartupService` mutations fired an
`AfterCommitRunner` task that asked the AI service, over HTTP, to recompute an
embedding for the row just saved. These are the in-process replacements: the
same computation, called directly, sharing the caller's session.

**Best effort, deliberately.** Every failure is caught and logged, exactly as
the Java code did, because the matching pipeline computes any missing embedding
on its next run. A model that will not load must never turn a successful
profile save into a 500.

**Called after commit.** The embedding functions run their own `UPDATE` and
`commit`, and they read the row first — so firing before the caller's commit
would look up a row that is not visible yet, which is the bug
`AfterCommitRunner` existed to prevent.

Nothing here fabricates a vector. If the model is unavailable the row keeps a
NULL embedding and `run_matching_for_challenge` computes it later; a wrong
embedding would silently corrupt every future match score, which is far worse
than a missing one.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.utils.logging import get_logger

log = get_logger("services.embedding")


def refresh_challenge_embedding(db: Session, challenge_id: uuid.UUID) -> bool:
    """
    Recompute and store a challenge's embedding.

    Returns whether it succeeded; callers ignore it, but tests assert on it.
    """
    return _refresh("challenge", db, challenge_id)


def refresh_startup_embedding(db: Session, startup_id: uuid.UUID) -> bool:
    """Recompute and store a startup's embedding."""
    return _refresh("startup", db, startup_id)


def refresh_knowledge_base_embedding(db: Session, entry_id: uuid.UUID) -> bool:
    """Recompute and store a knowledge-base entry's embedding."""
    return _refresh("knowledge_base", db, entry_id)


def _refresh(kind: str, db: Session, entity_id: uuid.UUID) -> bool:
    # Imported lazily so that merely importing a service does not drag in
    # sentence-transformers and torch — that import alone costs seconds.
    from app.ai import (
        compute_and_store_challenge_embedding,
        compute_and_store_kb_embedding,
        compute_and_store_startup_embedding,
        get_embedding_provider,
    )

    computers = {
        "challenge": compute_and_store_challenge_embedding,
        "startup": compute_and_store_startup_embedding,
        "knowledge_base": compute_and_store_kb_embedding,
    }

    try:
        provider = get_embedding_provider()
        vector = computers[kind](db, str(entity_id), provider)
    except Exception:  # noqa: BLE001 - best effort, mirroring the Java catch-all
        log.warning(
            "Could not recompute the %s embedding for %s; it will be computed "
            "on the next matching run.", kind, entity_id, exc_info=True,
        )
        # Leave the caller's session usable — the failure may have left an
        # aborted transaction behind.
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False

    log.info("Recomputed the %s embedding for %s (%d dimensions)",
             kind, entity_id, len(vector))
    return True


__all__ = [
    "refresh_challenge_embedding",
    "refresh_knowledge_base_embedding",
    "refresh_startup_embedding",
]
