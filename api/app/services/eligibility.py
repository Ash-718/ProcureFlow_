"""Two-gate eligibility, and tier access.

Gate 1 is general: it applies to every bidder, startup or not, and asks only
whether the bidder is a legally constituted entity that has made a technical
submission.  It carries no turnover floor and no experience requirement - those
are exactly the barriers this platform exists to remove.

Gate 2 is the startup lane: recognition, company age, size, prior participation.
A large firm can pass gate 1 and still fail gate 2, which is the point.

Eligibility is rule-based.  No part of this module asks an LLM anything, and
every threshold it applies is read from the rules table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import CompanyType, KpiStatus, ProposalStatus, Tier
from app.models import Award, Challenge, Company, Kpi, Proposal, User
from app.services.fallback import FallbackDecision, evaluate_and_log
from app.services.rotation import RotationDecision, evaluate_and_log as evaluate_rotation
from app.services.rules import RuleValue, RulesService

GATE_GENERAL = "GATE_1_GENERAL"
GATE_STARTUP_LANE = "GATE_2_STARTUP_LANE"


@dataclass(frozen=True)
class CriterionResult:
    code: str
    label: str
    passed: bool
    reason: str
    # Which procurement rule this criterion applied, where one applies at all.
    basis: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "label": self.label,
            "passed": self.passed,
            "reason": self.reason,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    criteria: list[CriterionResult]

    def as_dict(self) -> dict:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "criteria": [criterion.as_dict() for criterion in self.criteria],
        }


@dataclass(frozen=True)
class TierAccessResult:
    tier: Tier
    allowed: bool
    reason: str
    fallback: FallbackDecision | None = None
    rotation: RotationDecision | None = None
    validated_kpi_history: dict | None = None

    def as_dict(self) -> dict:
        return {
            "tier": self.tier.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "fallback": self.fallback.as_details() if self.fallback else None,
            "rotation": self.rotation.as_details() if self.rotation else None,
            "validated_kpi_history": self.validated_kpi_history,
        }


@dataclass(frozen=True)
class EligibilityDecision:
    company_id: int
    company_name: str
    company_type: CompanyType
    tier: Tier | None
    gate_one: GateResult
    gate_two: GateResult
    tier_access: TierAccessResult | None
    eligible: bool
    rules_cited: list[RuleValue]

    def as_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "company_type": self.company_type.value,
            "tier": self.tier.value if self.tier else None,
            "gate_one": self.gate_one.as_dict(),
            "gate_two": self.gate_two.as_dict(),
            "tier_access": self.tier_access.as_dict() if self.tier_access else None,
            "eligible": self.eligible,
            "rules_cited": [rule.cite() for rule in self.rules_cited],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NO_RULE_APPLIES = "No procurement rule applies; this is a presence check, not a threshold."

# The startup lane has no age or size limit in procurement_rule, and an engine may
# not invent one.  Age and size are therefore recorded as facts about the bidder,
# for the officer to read, and they do not decide the gate.
NO_LIMIT_DEFINED = (
    "Reported, not applied: no procurement rule defines a limit for this criterion, "
    "so the platform imposes none."
)


def completed_years(start: date, as_of: date) -> int:
    """Whole years between two dates, without any calendar arithmetic constants."""
    had_anniversary_this_year = (as_of.month, as_of.day) >= (start.month, start.day)
    return as_of.year - start.year - (not had_anniversary_this_year)


def prior_participation(db: Session, company_id: int) -> dict:
    """What this company has already done on the platform.

    Reported, never used to block in gate 2: acting on repeat participation is
    the rotation rule, which applies to the SMALL tier only.
    """
    awards = db.scalar(
        select(func.count()).select_from(Award).where(Award.company_id == company_id)
    )
    proposals = db.scalar(
        select(func.count())
        .select_from(Proposal)
        .where(
            Proposal.startup_id == company_id,
            Proposal.status != ProposalStatus.WITHDRAWN,
        )
    )
    # COUNT always returns a row, so these are never None.
    return {"awards": awards, "proposals": proposals}


def validated_kpi_history(db: Session, company_id: int) -> dict:
    """Validated KPI track record, which is what feeds scoring in the LARGE tier.

    Only KPIs an independent validator marked VERIFIED are counted, and only the
    counts are reported here.  Whether a KPI beat its target is not computed:
    the table does not record whether a higher or a lower number is better, so
    comparing validated_value with target_value would be wrong for any KPI
    measured in hours or minutes.
    """
    verified = db.scalar(
        select(func.count())
        .select_from(Kpi)
        .where(Kpi.startup_id == company_id, Kpi.status == KpiStatus.VERIFIED)
    )
    challenges = db.scalar(
        select(func.count(func.distinct(Kpi.challenge_id))).where(
            Kpi.startup_id == company_id, Kpi.status == KpiStatus.VERIFIED
        )
    )
    return {
        "verified_kpis": verified,
        "challenges_with_verified_kpis": challenges,
        "note": "Counts only. Achievement against target is scored in the matching engine.",
    }


# ---------------------------------------------------------------------------
# Gate 1: general eligibility, applied to every bidder
# ---------------------------------------------------------------------------


def gate_one(company: Company) -> GateResult:
    criteria = [
        CriterionResult(
            code="LEGAL_REGISTRATION",
            label="Legally constituted entity",
            passed=company.incorporation_date is not None,
            reason=(
                f"Incorporation date on record: {company.incorporation_date}."
                if company.incorporation_date
                else "No incorporation date on record."
            ),
            basis=NO_RULE_APPLIES,
        ),
        CriterionResult(
            code="TECHNICAL_PROFILE",
            label="Technical capability statement submitted",
            passed=bool(company.profile_text and company.profile_text.strip()),
            reason=(
                "A capability profile is on record."
                if company.profile_text and company.profile_text.strip()
                else "No capability profile on record."
            ),
            basis=NO_RULE_APPLIES,
        ),
    ]
    return GateResult(
        gate=GATE_GENERAL,
        passed=all(criterion.passed for criterion in criteria),
        criteria=criteria,
    )


# ---------------------------------------------------------------------------
# Gate 2: the startup lane
# ---------------------------------------------------------------------------


def gate_two(
    db: Session,
    company: Company,
    *,
    as_of: date | None = None,
) -> GateResult:
    """The startup lane gate: recognition, company age, size, prior participation.

    Only recognition decides the gate.  The rules table defines no maximum company
    age and no maximum size, and inventing either would be exactly the kind of
    threshold this platform exists to question, so age and size are reported as
    facts instead.  Prior participation is reported too: acting on repeat wins is
    the rotation rule, which applies to the SMALL tier only.

    The gate reads no procurement rule at all, which is why it takes no rules
    service.
    """
    as_of = as_of or date.today()

    criteria: list[CriterionResult] = [
        CriterionResult(
            code="STARTUP_RECOGNITION",
            label="Recognised startup",
            passed=bool(company.dpiit_recognised),
            reason=(
                "The company is recorded as a recognised startup."
                if company.dpiit_recognised
                else "The company is not recorded as a recognised startup."
            ),
            basis=NO_RULE_APPLIES,
        ),
        CriterionResult(
            code="STARTUP_COMPANY_AGE",
            label="Company age",
            passed=True,
            reason=(
                f"Incorporated {company.incorporation_date}, "
                f"{completed_years(company.incorporation_date, as_of)} completed years ago."
                if company.incorporation_date
                else "No incorporation date on record, so company age is unknown."
            ),
            basis=NO_LIMIT_DEFINED,
        ),
        CriterionResult(
            code="STARTUP_SIZE",
            label="Company size",
            passed=True,
            reason=(
                f"The company employs {company.employee_count} people."
                if company.employee_count is not None
                else "No employee count on record, so company size is unknown."
            ),
            basis=NO_LIMIT_DEFINED,
        ),
    ]

    history = prior_participation(db, company.id)
    criteria.append(
        CriterionResult(
            code="PRIOR_PARTICIPATION",
            label="Prior participation on the platform",
            passed=True,
            reason=(
                f"{history['proposals']} prior proposals and {history['awards']} prior awards "
                f"on record. Prior participation does not bar a bidder from the startup lane."
            ),
            basis=NO_LIMIT_DEFINED,
        )
    )

    return GateResult(
        gate=GATE_STARTUP_LANE,
        passed=all(criterion.passed for criterion in criteria),
        criteria=criteria,
    )


# ---------------------------------------------------------------------------
# Tier access
# ---------------------------------------------------------------------------


def tier_access(
    db: Session,
    rules: RulesService,
    challenge: Challenge,
    company: Company,
    startup_lane_passed: bool,
    *,
    actor: User | None = None,
    now: datetime | None = None,
) -> TierAccessResult:
    tier = challenge.tier
    is_startup = company.type is CompanyType.STARTUP

    if tier is Tier.SMALL:
        if not is_startup:
            return TierAccessResult(
                tier=tier,
                allowed=False,
                reason=(
                    f"The SMALL tier is reserved for startups. {company.name} is registered "
                    f"as {company.type.value}."
                ),
            )
        if not startup_lane_passed:
            return TierAccessResult(
                tier=tier,
                allowed=False,
                reason="The SMALL tier is the startup lane, and gate 2 was not passed.",
            )

        # Rotation applies to the SMALL tier and nowhere else.
        rotation = evaluate_rotation(db, rules, challenge, company, actor=actor)
        if rotation.blocked:
            return TierAccessResult(
                tier=tier,
                allowed=False,
                reason=rotation.reason_text,
                rotation=rotation,
            )
        return TierAccessResult(
            tier=tier,
            allowed=True,
            reason="Startup in the startup-only tier, with the startup lane gate passed.",
            rotation=rotation,
        )

    if tier is Tier.MEDIUM:
        if is_startup:
            return TierAccessResult(
                tier=tier,
                allowed=startup_lane_passed,
                reason=(
                    "MEDIUM is startup-first, and the startup lane gate was passed."
                    if startup_lane_passed
                    else "MEDIUM is startup-first, but the startup lane gate was not passed."
                ),
            )
        decision = evaluate_and_log(db, rules, challenge, actor=actor, now=now)
        return TierAccessResult(
            tier=tier,
            allowed=decision.fired,
            reason=(
                "MEDIUM is startup-first. "
                + (
                    "The fallback trigger has fired, so large firms may bid."
                    if decision.fired
                    else "The fallback trigger has not fired, so the tier stays startup-only."
                )
            ),
            fallback=decision,
        )

    return TierAccessResult(
        tier=tier,
        allowed=True,
        reason=(
            "LARGE is open and merit-based. Validated KPI history is carried into technical "
            "scoring; startups participate through a partnership in which the startup owns "
            "the solution and its IP."
        ),
        validated_kpi_history=validated_kpi_history(db, company.id),
    )


# ---------------------------------------------------------------------------
# The whole assessment
# ---------------------------------------------------------------------------


def assess(
    db: Session,
    rules: RulesService,
    company: Company,
    challenge: Challenge | None = None,
    *,
    actor: User | None = None,
    as_of: date | None = None,
    now: datetime | None = None,
) -> EligibilityDecision:
    """Run both gates, and tier access when a challenge is supplied."""

    one = gate_one(company)
    two = gate_two(db, company, as_of=as_of)

    access = None
    if challenge is not None and challenge.tier is not None:
        access = tier_access(db, rules, challenge, company, two.passed, actor=actor, now=now)

    eligible = one.passed and (access.allowed if access else two.passed)

    return EligibilityDecision(
        company_id=company.id,
        company_name=company.name,
        company_type=company.type,
        tier=challenge.tier if challenge else None,
        gate_one=one,
        gate_two=two,
        tier_access=access,
        eligible=eligible,
        rules_cited=rules.rules_read,
    )
