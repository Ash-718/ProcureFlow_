"""Admin-only endpoints.

Reads for the seed and the audit trail, plus the one write an admin has: editing
a procurement rule.  Because every engine reads its numbers from that table, a
rule edit changes how the platform behaves, so it is audited with the before and
after values and the admin's stated reason.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.enums import UserRole
from app.models import (
    Award,
    AuditLog,
    Challenge,
    Company,
    CompanyFounder,
    Department,
    Founder,
    Kpi,
    Partnership,
    Pilot,
    ProcurementRule,
    Proposal,
    User,
)
from app.schemas import AuditLogOut, ProcurementRuleOut, TableCount
from app.schemas_engine import RuleUpdate, SplittingScanOut
from app.services import audit, fairness, splitting
from app.services.rules import RulesService

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_roles(UserRole.ADMIN)

# Every table we report counts for, in the order the README lists them.
COUNTED_MODELS = [
    Company,
    Founder,
    CompanyFounder,
    Department,
    User,
    Challenge,
    Kpi,
    Proposal,
    Pilot,
    Partnership,
    Award,
    ProcurementRule,
    AuditLog,
]


@router.get("/rules", response_model=list[ProcurementRuleOut])
def list_rules(
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
) -> list[ProcurementRule]:
    rules = db.scalars(
        select(ProcurementRule).order_by(ProcurementRule.rule_name, ProcurementRule.effective_from)
    ).all()
    return list(rules)


@router.get("/table-counts", response_model=list[TableCount])
def table_counts(
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
) -> list[TableCount]:
    counts = []
    for model in COUNTED_MODELS:
        rows = db.scalar(select(func.count()).select_from(model)) or 0
        counts.append(TableCount(table=model.__tablename__, rows=rows))
    return counts


@router.put("/rules/{rule_id}", response_model=ProcurementRuleOut)
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
) -> ProcurementRule:
    """Edit a procurement rule in place, with the change recorded.

    Changing a rule changes how the engines behave, so the before and after
    values and the admin's stated reason go into the audit log.
    """
    rule = db.get(ProcurementRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    editable = payload.model_dump(exclude={"reason"}, exclude_unset=True)
    changes = {}
    for field_name, new_value in editable.items():
        old_value = getattr(rule, field_name)
        if old_value != new_value:
            changes[field_name] = {"from": str(old_value), "to": str(new_value)}
            setattr(rule, field_name, new_value)

    rule.updated_by_user_id = current_user.id

    audit.record(
        db,
        action="PROCUREMENT_RULE_UPDATED",
        reason=payload.reason,
        actor=current_user,
        entity_type="procurement_rule",
        entity_id=rule.id,
        details={"rule_name": rule.rule_name, "changes": changes},
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/audit-log", response_model=list[AuditLogOut])
def audit_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
) -> list[AuditLog]:
    entries = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    ).all()
    return list(entries)


@router.get("/splitting-scan", response_model=SplittingScanOut)
def splitting_scan(
    window_days: int = Query(
        ...,
        gt=0,
        description=(
            "How many days apart challenges may be and still count as one cluster. "
            "No procurement rule defines this, so the admin running the scan supplies it."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
) -> SplittingScanOut:
    """Flag clusters of challenges whose combined value crosses a tier boundary.

    Advisory only. Clusters are surfaced and recorded; nothing is blocked.
    """
    result = splitting.scan_and_log(
        db, RulesService(db), window_days=window_days, actor=current_user
    )
    db.commit()
    return SplittingScanOut(**result.as_dict())


@router.get("/fairness")
def fairness_report(
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
) -> dict:
    """Opportunity concentration, participation and tier spread.

    Counted per founder group rather than per company, so a group operating
    through several entities is visible as one.
    """
    return fairness.report(db, RulesService(db)).as_dict()
