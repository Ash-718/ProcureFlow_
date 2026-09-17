"""The one way anything gets written to audit_log.

Non-negotiable rule 7: every classification, score, fallback trigger, approval
and override is logged with an actor, a timestamp and a reason.  The timestamp
is the database default, so callers only supply actor, action and reason.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    *,
    action: str,
    reason: str,
    actor: User | None = None,
    actor_label: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Append one audit entry.

    Pass actor for a human action.  For an engine decision pass actor_label
    instead (for example "tier-engine" or "rotation-rule").
    """

    if actor is None and actor_label is None:
        raise ValueError("An audit entry needs either an actor or an actor_label")

    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_label=actor_label or f"{actor.full_name} <{actor.email}>",
        action=action,
        reason=reason,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
    return entry
