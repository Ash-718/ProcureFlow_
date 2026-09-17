"""Splitting detection.

A large requirement broken into several small ones lands in a tier it does not
belong to.  This detector looks for clusters of closely timed challenges from
the same department in the same category whose values, added together, cross a
tier boundary that none of them crosses alone.

It surfaces clusters to admins and never blocks anything.  A department may have
a perfectly good reason to buy in stages, and the platform is not in a position
to know.

The time window is supplied by whoever runs the scan.  No procurement rule
defines what "closely timed" means, and the detector does not invent one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Tier
from app.models import Challenge, Department, User
from app.services import audit
from app.services.rules import RuleValue, RulesService

SMALL_TENDER_LIMIT = "SMALL_TENDER_LIMIT"
MEDIUM_TENDER_LIMIT = "MEDIUM_TENDER_LIMIT"

# Ordering only, so a combined band can be compared with the highest single one.
_TIER_ORDER = {Tier.SMALL: 1, Tier.MEDIUM: 2, Tier.LARGE: 3}


@dataclass(frozen=True)
class ClusterMember:
    challenge_id: int
    title: str
    value: Decimal
    created_at: datetime
    band: Tier


@dataclass(frozen=True)
class SplittingCluster:
    department: str
    category: str | None
    window_days: int
    members: list[ClusterMember]
    combined_value: Decimal
    highest_individual_band: Tier
    combined_band: Tier
    reason: str

    def as_dict(self) -> dict:
        return {
            "department": self.department,
            "category": self.category,
            "window_days": self.window_days,
            "members": [
                {
                    "challenge_id": member.challenge_id,
                    "title": member.title,
                    "value": str(member.value),
                    "created_at": member.created_at.isoformat(),
                    "band": member.band.value,
                }
                for member in self.members
            ],
            "combined_value": str(self.combined_value),
            "highest_individual_band": self.highest_individual_band.value,
            "combined_band": self.combined_band.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SplittingScan:
    window_days: int
    clusters: list[SplittingCluster]
    rules_cited: list[RuleValue]
    summary: str

    def as_dict(self) -> dict:
        return {
            "window_days": self.window_days,
            "clusters": [cluster.as_dict() for cluster in self.clusters],
            "rules_cited": [rule.cite() for rule in self.rules_cited],
            "summary": self.summary,
        }


def value_band(value: Decimal, small_limit: Decimal, medium_limit: Decimal) -> Tier:
    """The tier band a value falls in, by value alone.

    This is not the tier engine: criticality and innovation potential belong to a
    single challenge and cannot be added up across several.  The detector
    compares like with like by using the value band on both sides.
    """
    if value <= small_limit:
        return Tier.SMALL
    if value <= medium_limit:
        return Tier.MEDIUM
    return Tier.LARGE


def scan(
    db: Session,
    rules: RulesService,
    *,
    window_days: int,
    now: datetime | None = None,
) -> SplittingScan:
    """Find clusters whose combined value crosses a band none of them crosses alone."""

    now = now or datetime.now(timezone.utc)
    small_limit = rules.get(SMALL_TENDER_LIMIT)
    medium_limit = rules.get(MEDIUM_TENDER_LIMIT)

    challenges = db.scalars(
        select(Challenge)
        .where(Challenge.value.isnot(None))
        .order_by(Challenge.department_id, Challenge.category, Challenge.created_at)
    ).all()

    departments = {
        department.id: department.name for department in db.scalars(select(Department)).all()
    }

    # Group by department and category: same buyer, same kind of work.
    grouped: dict[tuple[int, str | None], list[Challenge]] = {}
    for challenge in challenges:
        grouped.setdefault((challenge.department_id, challenge.category), []).append(challenge)

    window = timedelta(days=window_days)
    clusters: list[SplittingCluster] = []

    for (department_id, category), group in grouped.items():
        # Walk the group in time order and cut it into runs where each challenge
        # starts within the window of the run's first challenge.
        run: list[Challenge] = []
        for challenge in group:
            if run and challenge.created_at - run[0].created_at > window:
                clusters.extend(
                    _flag(run, departments[department_id], category, window_days,
                          small_limit.value, medium_limit.value)
                )
                run = []
            run.append(challenge)
        clusters.extend(
            _flag(run, departments[department_id], category, window_days,
                  small_limit.value, medium_limit.value)
        )

    summary = (
        f"{len(clusters)} cluster(s) flagged within a {window_days}-day window. "
        f"Flagged for review only: a department may have good reason to buy in stages, "
        f"and nothing here blocks a challenge."
    )
    return SplittingScan(
        window_days=window_days,
        clusters=clusters,
        rules_cited=[small_limit, medium_limit],
        summary=summary,
    )


def _flag(
    run: list[Challenge],
    department_name: str,
    category: str | None,
    window_days: int,
    small_limit: Decimal,
    medium_limit: Decimal,
) -> list[SplittingCluster]:
    """Turn one run of challenges into a cluster, if its total crosses a band."""

    if len(run) < 2:
        return []

    members = [
        ClusterMember(
            challenge_id=challenge.id,
            title=challenge.title,
            value=challenge.value,
            created_at=challenge.created_at,
            band=value_band(challenge.value, small_limit, medium_limit),
        )
        for challenge in run
    ]
    combined_value = sum((member.value for member in members), Decimal())
    combined_band = value_band(combined_value, small_limit, medium_limit)
    highest_individual = max(members, key=lambda member: _TIER_ORDER[member.band]).band

    if _TIER_ORDER[combined_band] <= _TIER_ORDER[highest_individual]:
        return []

    reason = (
        f"{len(members)} challenges from {department_name} in category {category}, raised "
        f"within {window_days} days, are individually in the {highest_individual.value} band "
        f"but total {combined_value:f}, which is in the {combined_band.value} band. Worth "
        f"checking whether this is one requirement bought in pieces."
    )
    return [
        SplittingCluster(
            department=department_name,
            category=category,
            window_days=window_days,
            members=members,
            combined_value=combined_value,
            highest_individual_band=highest_individual,
            combined_band=combined_band,
            reason=reason,
        )
    ]


def scan_and_log(
    db: Session,
    rules: RulesService,
    *,
    window_days: int,
    actor: User | None = None,
    now: datetime | None = None,
) -> SplittingScan:
    """Run the scan, and record any cluster it surfaces."""

    result = scan(db, rules, window_days=window_days, now=now)
    for cluster in result.clusters:
        audit.record(
            db,
            action="SPLITTING_PATTERN_FLAGGED",
            reason=cluster.reason,
            actor=actor,
            actor_label=None if actor else "splitting-detector",
            entity_type="department",
            entity_id=None,
            details=cluster.as_dict(),
        )
    return result
