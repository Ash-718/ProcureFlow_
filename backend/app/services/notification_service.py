"""
In-app notifications.

Port of Java's `NotificationService`. Writes join the caller's transaction, so
a notification and the action that produced it commit together — a "your
proposal was received" message must never outlive a failed submission.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.models import Notification, NotificationType, User
from app.repositories import NotificationRepository


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notifications = NotificationRepository(db)

    def notify(self, user: User | None, notification_type: NotificationType,
               message: str) -> Notification | None:
        """
        Record a notification for one user.

        Tolerates a missing recipient: a department whose user row has been
        removed should not turn a successful proposal submission into a 500.
        """
        if user is None:
            return None
        return self.notifications.add(Notification(
            user_id=user.id, type=notification_type, message=message))

    def list_for_user(self, user_id: uuid.UUID) -> list[Notification]:
        return self.notifications.list_for_user(user_id)

    def unread_count(self, user_id: uuid.UUID) -> int:
        return self.notifications.unread_count(user_id)

    def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        notification = self.notifications.get(notification_id)
        if notification is None:
            raise ApiException.not_found("Notification not found")
        if notification.user_id != user_id:
            raise ApiException.forbidden("You do not own this notification")
        notification.is_read = True
        self.db.flush()
