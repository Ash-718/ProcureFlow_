"""The fairness and governance view.

Counted per founder group, not per company.  Counting companies is how
concentration hides: the same three people behind four entities look like four
different suppliers until you resolve them to the people.

Nothing here is a judgement.  It reports what happened and labels how solid each
number is, including saying plainly when a target it is measured against is a
prototype setting with no source behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import CompanyType
from app.models import Award, Challenge, Company, Partnership
from app.services.founders import resolve
from app.services.rules import RuleNotFound, RulesService

STARTUP_ALLOCATION_PCT = "STARTUP_ALLOCATION_PCT"


@dataclass(frozen=True)
class FairnessReport:
    founder_groups: list[dict]
    execution_firms: list[dict]
    startup_participation: dict
    tier_distribution: list[dict]
    totals: dict

    def as_dict(self) -> dict:
        return {
            "founder_groups": self.founder_groups,
            "execution_firms": self.execution_firms,
            "startup_participation": self.startup_participation,
            "tier_distribution": self.tier_distribution,
            "totals": self.totals,
        }


def opportunities_per_founder_group(db: Session) -> list[dict]:
    """Awards per group of people, with the companies each group operates through."""
    startups = db.scalars(select(Company).where(Company.type == CompanyType.STARTUP)).all()

    seen: set[frozenset[int]] = set()
    groups: list[dict] = []

    for company in startups:
        group = resolve(db, company.id)
        key = frozenset(group.founder_ids) or frozenset({-company.id})
        if key in seen:
            continue
        seen.add(key)

        awards = db.scalars(
            select(Award).where(Award.company_id.in_(group.company_ids))
        ).all()
        if not awards:
            continue

        groups.append(
            {
                "founders": group.founder_names,
                "companies": group.company_names,
                "company_count": len(group.company_ids),
                "awards": len(awards),
                "total_value": str(sum((award.value or Decimal() for award in awards), Decimal())),
                "note": (
                    "Counted across every company these founders operate through, so a "
                    "newly incorporated entity does not read as a new supplier."
                )
                if len(group.company_ids) > 1
                else None,
            }
        )

    groups.sort(key=lambda row: (-row["awards"], row["founders"]))
    return groups


def partnerships_per_execution_firm(db: Session) -> list[dict]:
    rows = db.execute(
        select(Company.name, func.count(Partnership.id))
        .join(Partnership, Partnership.legacy_partner_id == Company.id)
        .group_by(Company.name)
        .order_by(func.count(Partnership.id).desc())
    ).all()
    return [{"firm": name, "partnerships": count} for name, count in rows]


def startup_participation(db: Session, rules: RulesService) -> dict:
    """Share of awards going to startups, against the platform's target."""
    total_awards = db.scalar(select(func.count()).select_from(Award)) or 0
    startup_awards = (
        db.scalar(
            select(func.count())
            .select_from(Award)
            .join(Company, Company.id == Award.company_id)
            .where(Company.type == CompanyType.STARTUP)
        )
        or 0
    )
    share = (startup_awards / total_awards * 100) if total_awards else 0.0

    try:
        rule = rules.get(STARTUP_ALLOCATION_PCT)
    except RuleNotFound:
        return {
            "startup_awards": startup_awards,
            "total_awards": total_awards,
            "share_pct": round(share, 1),
            "target_pct": None,
            "target_label": "No participation target is configured.",
            "target_is_prototype_setting": None,
        }

    return {
        "startup_awards": startup_awards,
        "total_awards": total_awards,
        "share_pct": round(share, 1),
        "target_pct": float(rule.value),
        "meets_target": share >= float(rule.value),
        "target_is_prototype_setting": rule.is_prototype_setting,
        "target_label": (
            f"{rule.rule_name} is a prototype setting with no source reference. It is a "
            f"working target for this demonstration, not a statutory requirement."
            if rule.is_prototype_setting
            else f"{rule.rule_name}, source: {rule.source_reference}"
        ),
    }


def tier_distribution(db: Session) -> list[dict]:
    rows = db.execute(
        select(Challenge.tier, func.count(Challenge.id))
        .where(Challenge.tier.isnot(None))
        .group_by(Challenge.tier)
    ).all()
    return [{"tier": tier.value, "challenges": count} for tier, count in rows]


def report(db: Session, rules: RulesService) -> FairnessReport:
    return FairnessReport(
        founder_groups=opportunities_per_founder_group(db),
        execution_firms=partnerships_per_execution_firm(db),
        startup_participation=startup_participation(db, rules),
        tier_distribution=tier_distribution(db),
        totals={
            "startups": db.scalar(
                select(func.count()).select_from(Company).where(
                    Company.type == CompanyType.STARTUP
                )
            ),
            "legacy_firms": db.scalar(
                select(func.count()).select_from(Company).where(
                    Company.type == CompanyType.LEGACY
                )
            ),
            "challenges": db.scalar(select(func.count()).select_from(Challenge)),
            "awards": db.scalar(select(func.count()).select_from(Award)),
            "sample_data_note": (
                "Every company and pilot in this view is sample data generated for the "
                "prototype."
            ),
        },
    )
