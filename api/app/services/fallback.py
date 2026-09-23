"""The MEDIUM-tier fallback trigger.

MEDIUM is startup-first.  It opens to large firms only when the rules engine
says the startup lane did not produce a viable field within the bid window.

Every value that decides this comes from the rules table, and the values that
fired the trigger are written to the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import CompanyType, ProposalStatus
from app.models import Challenge, Company, Proposal, User
from app.services import audit
from app.services.rules import RuleValue, RulesService

MIN_STARTUP_BIDS = "MIN_STARTUP_BIDS"
MIN_TECH_SCORE = "MIN_TECH_SCORE"
BID_WINDOW_DAYS = "BID_WINDOW_DAYS"

# A withdrawn proposal is not a bid the department can choose from.
_COUNTED_STATUSES = [status for status in ProposalStatus if status is not ProposalStatus.WITHDRAWN]


@dataclass(frozen=True)
class FallbackDecision:
    fired: bool
    window_closed: bool
    window_closes_at: datetime | None
    startup_bids: int
    qualified_startup_bids: int
    reasons: list[str]
    rules_cited: list[RuleValue]

    def as_details(self) -> dict:
        return {
            "fired": self.fired,
            "window_closed": self.window_closed,
            "window_closes_at": self.window_closes_at.isoformat() if self.window_closes_at else None,
            "startup_bids": self.startup_bids,
            "qualified_startup_bids": self.qualified_startup_bids,
            "reasons": self.reasons,
            "rules_cited": [rule.cite() for rule in self.rules_cited],
        }


def _window_closes_at(challenge: Challenge, bid_window_days: int) -> datetime | None:
    """When the bid window shuts.

    An explicit bid_closes_at on the challenge wins; otherwise it is the
    publication date plus the window from the rules table.  If the challenge was
    never published there is no window, and the trigger cannot fire.
    """
    if challenge.bid_closes_at is not None:
        return challenge.bid_closes_at
    if challenge.published_at is not None:
        return challenge.published_at + timedelta(days=bid_window_days)
    return None


def evaluate(
    db: Session,
    rules: RulesService,
    challenge: Challenge,
    *,
    now: datetime | None = None,
) -> FallbackDecision:
    """Decide whether a MEDIUM challenge may open to large firms."""

    now = now or datetime.now(timezone.utc)

    min_startup_bids = rules.get(MIN_STARTUP_BIDS)
    min_tech_score = rules.get(MIN_TECH_SCORE)
    bid_window_days = rules.get(BID_WINDOW_DAYS)

    closes_at = _window_closes_at(challenge, int(bid_window_days.value))
    window_closed = closes_at is not None and now >= closes_at

    startup_proposals = list(
        db.scalars(
            select(Proposal)
            .join(Company, Company.id == Proposal.startup_id)
            .where(
                Proposal.challenge_id == challenge.id,
                Company.type == CompanyType.STARTUP,
                Proposal.status.in_(_COUNTED_STATUSES),
            )
        ).all()
    )
    qualified = [
        proposal
        for proposal in startup_proposals
        if proposal.total_score is not None and proposal.total_score >= min_tech_score.value
    ]

    reasons: list[str] = []

    if closes_at is None:
        reasons.append(
            "The challenge has no bid window yet, so the fallback trigger cannot be evaluated."
        )
    elif not window_closed:
        reasons.append(
            f"The bid window is still open until {closes_at.isoformat()}, derived from "
            f"{bid_window_days.cite()}. MEDIUM stays startup-first until it closes."
        )

    too_few_bids = len(qualified) < int(min_startup_bids.value)
    none_above_threshold = not qualified

    if too_few_bids:
        reasons.append(
            f"Qualified startup bids: {len(qualified)}, which is fewer than "
            f"{min_startup_bids.cite()}."
        )
    else:
        reasons.append(
            f"Qualified startup bids: {len(qualified)}, which meets {min_startup_bids.cite()}."
        )

    if none_above_threshold:
        reasons.append(
            f"No startup bid scored at or above {min_tech_score.cite()} "
            f"(bids received: {len(startup_proposals)})."
        )

    fired = window_closed and (too_few_bids or none_above_threshold)

    if fired:
        reasons.append(
            "Fallback trigger fired: this MEDIUM challenge may open to large firms."
        )
    elif window_closed:
        reasons.append(
            "Fallback trigger did not fire: the startup lane produced a viable field."
        )

    return FallbackDecision(
        fired=fired,
        window_closed=window_closed,
        window_closes_at=closes_at,
        startup_bids=len(startup_proposals),
        qualified_startup_bids=len(qualified),
        reasons=reasons,
        rules_cited=[min_startup_bids, min_tech_score, bid_window_days],
    )


def evaluate_and_log(
    db: Session,
    rules: RulesService,
    challenge: Challenge,
    *,
    actor: User | None = None,
    now: datetime | None = None,
) -> FallbackDecision:
    """Evaluate the trigger and write the values that decided it to the audit log."""

    decision = evaluate(db, rules, challenge, now=now)
    audit.record(
        db,
        action="MEDIUM_FALLBACK_TRIGGER_FIRED" if decision.fired else "MEDIUM_FALLBACK_EVALUATED",
        reason=" ".join(decision.reasons),
        actor=actor,
        actor_label=None if actor else "fallback-trigger",
        entity_type="challenge",
        entity_id=challenge.id,
        details=decision.as_details(),
    )
    return decision
