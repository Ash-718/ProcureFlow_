"""
Administrator operations: user management and the audit trail.

Port of Java's `AdminService`. The audit-log listing is paginated and must
return Spring's `PageImpl` envelope — see `app/schemas/base.py::Page`, which
reproduces all eleven of its keys, not just the five the frontend declares.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ApiException
from app.models import AuditLog, User
from app.repositories import UserRepository
from app.schemas.base import Page
from app.schemas.system import AdminUserResponse, AuditLogResponse
from app.services.audit_service import Action, AuditService


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def list_users(self) -> list[AdminUserResponse]:
        return [AdminUserResponse.from_entity(u) for u in self.users.list_all()]

    def set_active(self, actor: User, user_id: uuid.UUID,
                   active: bool) -> AdminUserResponse:
        """
        Enable or disable an account.

        Takes effect immediately: `get_current_user` checks `is_active` on
        every request, so a disabled account is locked out at once rather than
        when its token happens to expire.
        """
        user = self.users.get(user_id)
        if user is None:
            raise ApiException.not_found("User not found")

        user.is_active = active
        self.db.flush()

        self.audit.log(
            actor,
            Action.ACTIVATE_USER if active else Action.DEACTIVATE_USER,
            "User", user_id)
        self.db.commit()

        return AdminUserResponse.from_entity(user)

    def list_audit_logs(self, page: int = 0, size: int = 50) -> Page[AuditLogResponse]:
        """
        One page of the audit trail, newest first.

        `page` is zero-based, matching Spring and the frontend's
        `AdminApi.auditLogs(page = 0, size = 50)`.
        """
        page = max(page, 0)
        size = max(size, 1)

        total = self.db.execute(
            select(func.count()).select_from(AuditLog)).scalar_one()
        rows = self.db.execute(
            select(AuditLog)
            .options(joinedload(AuditLog.actor))
            .order_by(AuditLog.created_at.desc())
            .offset(page * size)
            .limit(size)
        ).unique().scalars().all()

        return Page[AuditLogResponse].create(
            [AuditLogResponse.from_entity(row) for row in rows],
            page=page, size=size, total=total)
