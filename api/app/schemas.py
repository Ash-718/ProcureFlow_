"""Pydantic schemas for the Phase 1 API surface (auth, identity, admin reads)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.enums import CompanyType, RuleType, UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: CompanyType
    district: str | None = None


class DepartmentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    district: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole
    company: CompanyBrief | None = None
    department: DepartmentBrief | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProcurementRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_name: str
    rule_type: RuleType
    value: Decimal
    active: bool
    # Empty means "prototype setting", not a verified legal requirement.
    source_reference: str | None = None
    effective_from: date
    description: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_label: str
    actor_user_id: int | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    reason: str | None = None
    details: dict | None = None


class TableCount(BaseModel):
    table: str
    rows: int


class FounderCompanyLink(BaseModel):
    founder_id: int
    founder_name: str
    company_count: int
    companies: list[str]
