"""
Audit trail writes.

Port of Java's `AuditService`. Two behaviours carried over deliberately:

* metadata is written only when non-empty, so a routine LOGIN row keeps
  ``metadata_json`` NULL exactly as it does today;
* a failure to serialise metadata never fails the action being audited —
  audit context is supporting detail, not the operation itself.

The action vocabulary is pinned as constants. The Java code used string
literals, which is how a trail ends up with `UPDATE_PROFILE` and
`PROFILE_UPDATE` both in it and neither filterable.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.utils.logging import get_logger

log = get_logger("services.audit")


class Action:
    """Actions the Java backend writes. Keep in sync when porting a service."""

    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    PUBLISH = "PUBLISH"
    UPDATE_PROFILE = "UPDATE_PROFILE"
    RUN_MATCHING = "RUN_MATCHING"
    SUBMIT = "SUBMIT"
    STATUS_CHANGE = "STATUS_CHANGE"
    UPLOAD = "UPLOAD"
    SUBMIT_EVALUATION = "SUBMIT_EVALUATION"
    UPDATE_MILESTONE = "UPDATE_MILESTONE"
    RECORD_KPI_RESULT = "RECORD_KPI_RESULT"
    COMPLETE_PILOT = "COMPLETE_PILOT"
    FINAL_DECISION = "FINAL_DECISION"
    ACTIVATE_USER = "ACTIVATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(self, actor: User | None, action: str, entity_type: str,
            entity_id: uuid.UUID | None = None,
            metadata: dict[str, Any] | None = None) -> AuditLog:
        """
        Append an audit row.

        Does not commit — the entry joins the caller's transaction so an
        audited action and its record land together or not at all.
        """
        metadata_json: str | None = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata, default=str)
            except (TypeError, ValueError):
                # Best-effort context; never a reason to fail the primary action.
                log.warning("Could not serialise audit metadata for %s/%s",
                            action, entity_type)

        entry = AuditLog(
            actor_user_id=actor.id if actor is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata_json,
        )
        self.db.add(entry)
        self.db.flush()
        return entry
