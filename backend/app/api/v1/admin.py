"""
`/api/v1/admin` — user management and the audit trail.

ADMIN-only, enforced on the router so no individual route can omit it.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RoleName
from app.schemas.base import Page
from app.schemas.system import AdminUserResponse, AuditLogResponse, SetActiveRequest
from app.security.deps import CurrentUserEntity, require_roles
from app.services.admin_service import AdminService

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(RoleName.ADMIN))],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: DbSession) -> list[AdminUserResponse]:
    return AdminService(db).list_users()


@router.patch("/users/{user_id}/active", response_model=AdminUserResponse)
def set_active(user_id: uuid.UUID, request: SetActiveRequest, db: DbSession,
               actor: CurrentUserEntity) -> AdminUserResponse:
    """
    Enable or disable an account. Takes effect on the account's next request.
    """
    return AdminService(db).set_active(actor, user_id, request.active)


@router.get("/audit-logs", response_model=Page[AuditLogResponse])
def list_audit_logs(
    db: DbSession,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> Page[AuditLogResponse]:
    """
    A page of the audit trail, newest first.

    Returns Spring's full `PageImpl` envelope — `content`, `pageable`, `sort`,
    `totalElements`, `totalPages`, `first`, `last`, `numberOfElements`,
    `empty`, `number`, `size` — not just the five keys the frontend declares.
    `page` is zero-based.
    """
    return AdminService(db).list_audit_logs(page=page, size=size)
