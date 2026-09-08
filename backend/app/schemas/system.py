"""
Knowledge base, notifications and admin payloads.

Two column-to-field renames the frontend depends on live here:
``notifications.is_read`` is exposed as ``read``, and ``users.is_active`` as
``active``.
"""
from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import NotificationType, RoleName
from app.schemas.base import CamelModel, CamelRequest, Instant


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

class KnowledgeBaseEntryResponse(CamelModel):
    id: uuid.UUID
    pilot_id: uuid.UUID
    challenge_title: str
    domain: str
    technology_tags: list[str] = []
    department_name: str
    startup_name: str
    outcome_summary: str | None
    #: Genuinely tri-state: `true` = SCALE, `false` = REJECT, `null` = MODIFY
    #: or undecided. Must never be coerced to a plain boolean.
    success: bool | None
    created_at: Instant

    @classmethod
    def from_entity(cls, entry) -> "KnowledgeBaseEntryResponse":
        return cls(
            id=entry.id,
            pilot_id=entry.pilot_id,
            challenge_title=entry.pilot.challenge.title,
            domain=entry.domain,
            technology_tags=list(entry.technology_tags or []),
            department_name=entry.department.department_name,
            startup_name=entry.pilot.startup.company_name,
            outcome_summary=entry.outcome_summary,
            success=entry.success,
            created_at=entry.created_at,
        )


class SimilarPilotMatch(CamelModel):
    """
    One result from `POST /knowledge-base/similar-for-draft`.

    `similarity` is a real cosine similarity from the embedding pipeline.
    """

    pilot_id: uuid.UUID
    challenge_title: str
    domain: str
    technology_tags: list[str] = []
    outcome_summary: str | None
    success: bool | None
    similarity: float


class SimilarPilotsResponse(CamelModel):
    ai_provider: str
    results: list[SimilarPilotMatch] = []


class SimilarPilotsRequest(CamelRequest):
    title: str = Field(min_length=1)
    problem_statement: str = Field(min_length=1)
    desired_technology: str | None = None
    domain: str = Field(min_length=1)
    outcomes_expected: str | None = None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationResponse(CamelModel):
    id: uuid.UUID
    type: NotificationType
    message: str
    #: Column is `is_read`.
    read: bool
    created_at: Instant

    @classmethod
    def from_entity(cls, notification) -> "NotificationResponse":
        return cls(
            id=notification.id,
            type=notification.type,
            message=notification.message,
            read=notification.is_read,
            created_at=notification.created_at,
        )


class UnreadCountResponse(CamelModel):
    unread: int


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class AdminUserResponse(CamelModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: RoleName
    #: Column is `is_active`.
    active: bool
    created_at: Instant

    @classmethod
    def from_entity(cls, user) -> "AdminUserResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            active=user.is_active,
            created_at=user.created_at,
        )


class SetActiveRequest(CamelRequest):
    active: bool


class AuditLogResponse(CamelModel):
    id: uuid.UUID
    #: Joined from `users`; null when the actor's account was deleted, since
    #: `actor_user_id` is ON DELETE SET NULL and the trail outlives the account.
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    #: The Java DTO serialised the JSONB column to a *string*, and the
    #: frontend types it as `string | null`. Preserved rather than "fixed" to
    #: an object, which would break `AuditLogItem`.
    metadata_json: str | None
    created_at: Instant

    @classmethod
    def from_entity(cls, entry) -> "AuditLogResponse":
        import json

        metadata = entry.metadata_json
        if metadata is not None and not isinstance(metadata, str):
            metadata = json.dumps(metadata, separators=(",", ":"))
        return cls(
            id=entry.id,
            actor_email=entry.actor.email if entry.actor else None,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            metadata_json=metadata,
            created_at=entry.created_at,
        )


__all__ = [
    "AdminUserResponse",
    "AuditLogResponse",
    "KnowledgeBaseEntryResponse",
    "NotificationResponse",
    "SetActiveRequest",
    "SimilarPilotMatch",
    "SimilarPilotsRequest",
    "SimilarPilotsResponse",
    "UnreadCountResponse",
]
