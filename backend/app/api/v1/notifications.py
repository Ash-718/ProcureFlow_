"""
`/api/v1/notifications` — the caller's own notifications.

Every route is scoped to the authenticated user: there is no way to address
another person's notifications, and `mark_read` verifies ownership before
writing.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.system import NotificationResponse, UnreadCountResponse
from app.security.deps import CurrentUser
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[NotificationResponse])
def list_notifications(db: DbSession,
                       current: CurrentUser) -> list[NotificationResponse]:
    """The caller's notifications, newest first."""
    return [NotificationResponse.from_entity(n)
            for n in NotificationService(db).list_for_user(current.id)]


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(db: DbSession, current: CurrentUser) -> UnreadCountResponse:
    """Backs the header's notification badge."""
    return UnreadCountResponse(
        unread=NotificationService(db).unread_count(current.id))


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: uuid.UUID, db: DbSession,
              current: CurrentUser) -> Response:
    """
    Mark one notification read. **204 No Content**, matching the Java controller.

    Someone else's notification is a 403, not a silent no-op.
    """
    service = NotificationService(db)
    service.mark_read(current.id, notification_id)
    service.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
