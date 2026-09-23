"""The rotation rule.

SMALL tier only.  A founder group that already holds two consecutive awards in
the same department and the same category does not take a third, provided there
are genuinely other startups able to do the work.

Two deliberate limits on it:

* It never applies to MEDIUM or LARGE.  A startup winning repeatedly on merit in
  an open tier is the system working, not a problem to correct.
* It never applies when no qualified alternative exists.  Rotating an award to
  nobody would serve the department worse than repeating a supplier that works,
  which is why MIN_QUALIFIED_ALTERNATIVES lives in the rules table.

Resolution is at founder level, so re-entering through a newly incorporated
company does not reset the count.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import CompanyType, ProposalStatus, Tier
from app.models import Award, Challenge, Company, Proposal, User
from app.services import audit
from app.services.founders import FounderGroup, resolve
from app.services.rules import RuleValue, RulesService

MIN_QUALIFIED_ALTERNATIVES = "MIN_QUALIFIED_ALTERNATIVES"
MIN_TECH_SCORE = "MIN_TECH_SCORE"

# The specification states the rule as blocking "a third consecutive award": the
# first two are allowed, the third is not.  That ordinal is part of how the rule
# is defined rather than a tunable limit - the tunable part is
# MIN_QUALIFIED_ALTERNATIVES, which is exactly why the specification puts that
# one in the rules table and not this one.
CONSECUTIVE_AWARDS_ALLOWED = 2


@dataclass(frozen=True)
class RotationDecision:
    applies: bool
    blocked: bool
    consecutive_awards: int
    qualified_alternatives: int
    founder_group: FounderGroup | None
    reasons: list[str]
    rules_cited: list[RuleValue]

    def as_details(self) -> dict:
        return {
            "applies": self.applies,
            "blocked": self.blocked,
            "consecutive_awards": self.consecutive_awards,
            "qualified_alternatives": self.qualified_alternatives,
            "founder_group": self.founder_group.as_dict() if self.founder_group else None,
            "reasons": self.reasons,
            "rules_cited": [rule.cite() for rule in self.rules_cited],
        }

    @property
    def reason_text(self) -> str:
        return " ".join(self.reasons)


def consecutive_awards_for_group(
    db: Session,
    group: FounderGroup,
    department_id: int,
    category: str | None,
) -> int:
    """How many awards at the head of this department and category run went to the group.

    Counting stops at the first award that went to anyone else, which is what
    makes the run consecutive rather than merely frequent.
    """
    awards = db.scalars(
        select(Award)
        .join(Challenge, Challenge.id == Award.challenge_id)
        .where(Challenge.department_id == department_id, Challenge.category == category)
        .order_by(Award.awarded_at.desc(), Award.id.desc())
    ).all()

    run = 0
    for award in awards:
        if award.company_id in group.company_ids:
            run += 1
        else:
            break
    return run


def qualified_alternatives(
    db: Session,
    challenge: Challenge,
    group: FounderGroup,
    min_tech_score,
) -> int:
    """Other startups on this challenge scoring at or above the technical bar."""
    proposals = db.scalars(
        select(Proposal)
        .join(Company, Company.id == Proposal.startup_id)
        .where(
            Proposal.challenge_id == challenge.id,
            Company.type == CompanyType.STARTUP,
            Proposal.status != ProposalStatus.WITHDRAWN,
            Proposal.startup_id.notin_(group.company_ids),
        )
    ).all()
    return len(
        [
            proposal
            for proposal in proposals
            if proposal.total_score is not None and proposal.total_score >= min_tech_score
        ]
    )


def evaluate(
    db: Session,
    rules: RulesService,
    challenge: Challenge,
    company: Company,
) -> RotationDecision:
    """Decide whether the rotation rule blocks an award to this company."""

    if challenge.tier is not Tier.SMALL:
        return RotationDecision(
            applies=False,
            blocked=False,
            consecutive_awards=0,
            qualified_alternatives=0,
            founder_group=None,
            reasons=[
                f"Rotation applies to the SMALL tier only. This challenge is "
                f"{challenge.tier.value if challenge.tier else 'unclassified'}, so a repeat "
                f"winner here is merit, not a pattern to correct."
            ],
            rules_cited=[],
        )

    group = resolve(db, company.id)
    run = consecutive_awards_for_group(db, group, challenge.department_id, challenge.category)

    min_alternatives = rules.get(MIN_QUALIFIED_ALTERNATIVES)
    min_score = rules.get(MIN_TECH_SCORE)
    alternatives = qualified_alternatives(db, challenge, group, min_score.value)

    reasons = [
        f"Founder group {', '.join(group.founder_names)} holds {run} consecutive award(s) "
        f"in this department and category, across {len(group.company_ids)} company(ies): "
        f"{', '.join(group.company_names)}."
    ]

    if run < CONSECUTIVE_AWARDS_ALLOWED:
        reasons.append(
            "That is short of the consecutive run the rotation rule acts on, so the award "
            "may proceed."
        )
        blocked = False
    elif alternatives < int(min_alternatives.value):
        reasons.append(
            f"The consecutive run would reach {run + 1}, but only {alternatives} other "
            f"qualified startup(s) scored at or above {min_score.cite()}, which is short of "
            f"{min_alternatives.cite()}. Rotating to nobody would serve the department worse "
            f"than a supplier that works, so the rule does not fire."
        )
        blocked = False
    else:
        reasons.append(
            f"This would be consecutive award number {run + 1} for the same founder group, "
            f"and {alternatives} other qualified startup(s) scored at or above "
            f"{min_score.cite()}, meeting {min_alternatives.cite()}. The rotation rule blocks "
            f"the award."
        )
        blocked = True

    return RotationDecision(
        applies=True,
        blocked=blocked,
        consecutive_awards=run,
        qualified_alternatives=alternatives,
        founder_group=group,
        reasons=reasons,
        rules_cited=[min_alternatives, min_score],
    )


def evaluate_and_log(
    db: Session,
    rules: RulesService,
    challenge: Challenge,
    company: Company,
    *,
    actor: User | None = None,
) -> RotationDecision:
    """Evaluate rotation, and record it when it blocks an award."""

    decision = evaluate(db, rules, challenge, company)

    if decision.blocked:
        audit.record(
            db,
            action="ROTATION_RULE_BLOCKED_AWARD",
            reason=decision.reason_text,
            actor=actor,
            actor_label=None if actor else "rotation-rule",
            entity_type="challenge",
            entity_id=challenge.id,
            details={**decision.as_details(), "company_id": company.id},
        )
    return decision
