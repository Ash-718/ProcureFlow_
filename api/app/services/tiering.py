"""The tier engine: value, criticality and innovation potential -> tier.

Value alone must not decide the tier.  A cheap failure is containable, so it can
go to the startup-only lane; a cheap failure of something critical is not, so it
cannot.  The engine therefore starts from the value band and then lets the two
risk factors move it.

Every number it uses comes from the rules table.  There are no numeric literals
in this module - the tier steps are expressed as an explicit ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.enums import Level, Tier
from app.services.rules import RuleValue, RulesService

SMALL_TENDER_LIMIT = "SMALL_TENDER_LIMIT"
MEDIUM_TENDER_LIMIT = "MEDIUM_TENDER_LIMIT"

# One step up and one step down the tier ladder, written out rather than
# computed, so the module holds no arithmetic on magic numbers.
_STEP_UP = {Tier.SMALL: Tier.MEDIUM, Tier.MEDIUM: Tier.LARGE, Tier.LARGE: Tier.LARGE}
_STEP_DOWN = {Tier.LARGE: Tier.MEDIUM, Tier.MEDIUM: Tier.SMALL, Tier.SMALL: Tier.SMALL}


class TierInputMissing(ValueError):
    """The engine refuses to classify from incomplete input.

    Guessing a missing value would be inventing a constraint, which the AI and
    the engines are both forbidden from doing.
    """

    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "Cannot classify the tier until these are supplied by the department: "
            + ", ".join(missing)
        )
        self.missing = missing


@dataclass(frozen=True)
class TierFactor:
    """One input, and what it did to the tier."""

    factor: str
    input_value: str
    effect: str
    reason: str


@dataclass(frozen=True)
class TierDecision:
    tier: Tier
    explanation: str
    factors: list[TierFactor]
    rules_cited: list[RuleValue] = field(default_factory=list)

    def as_details(self) -> dict:
        """Shape used for the audit log entry."""
        return {
            "tier": self.tier.value,
            "factors": [
                {
                    "factor": factor.factor,
                    "input": factor.input_value,
                    "effect": factor.effect,
                    "reason": factor.reason,
                }
                for factor in self.factors
            ],
            "rules_cited": [rule.cite() for rule in self.rules_cited],
        }


def classify(
    rules: RulesService,
    *,
    value: Decimal | None,
    criticality: Level | None,
    innovation_potential: Level | None,
) -> TierDecision:
    """Classify a challenge into SMALL, MEDIUM or LARGE with its reasoning."""

    missing = []
    if value is None:
        missing.append("value")
    if criticality is None:
        missing.append("criticality")
    if innovation_potential is None:
        missing.append("innovation_potential")
    if missing:
        raise TierInputMissing(missing)

    small_limit = rules.get(SMALL_TENDER_LIMIT)
    medium_limit = rules.get(MEDIUM_TENDER_LIMIT)

    factors: list[TierFactor] = []

    # --- Step 1: the value band -------------------------------------------
    if value <= small_limit.value:
        tier = Tier.SMALL
        band_reason = (
            f"Value {value:f} is at or below {small_limit.cite()}, so the value band is SMALL."
        )
    elif value <= medium_limit.value:
        tier = Tier.MEDIUM
        band_reason = (
            f"Value {value:f} is above {small_limit.cite()} and at or below "
            f"{medium_limit.cite()}, so the value band is MEDIUM."
        )
    else:
        tier = Tier.LARGE
        band_reason = f"Value {value:f} is above {medium_limit.cite()}, so the value band is LARGE."

    factors.append(
        TierFactor(
            factor="value",
            input_value=f"{value:f}",
            effect=f"starting band {tier.value}",
            reason=band_reason,
        )
    )

    # --- Step 2: criticality can only raise the tier ------------------------
    if criticality is Level.HIGH:
        raised = _STEP_UP[tier]
        factors.append(
            TierFactor(
                factor="criticality",
                input_value=criticality.value,
                effect=f"{tier.value} -> {raised.value}",
                reason=(
                    "Criticality is HIGH, so a failure here is not containable at the value "
                    "band alone and the challenge moves up a tier."
                ),
            )
        )
        tier = raised
    else:
        factors.append(
            TierFactor(
                factor="criticality",
                input_value=criticality.value,
                effect="no change",
                reason=f"Criticality is {criticality.value}, so the value band stands.",
            )
        )

    # --- Step 3: innovation potential can only lower the tier ---------------
    if innovation_potential is Level.HIGH:
        lowered = _STEP_DOWN[tier]
        factors.append(
            TierFactor(
                factor="innovation_potential",
                input_value=innovation_potential.value,
                effect=f"{tier.value} -> {lowered.value}",
                reason=(
                    "Innovation potential is HIGH, so the challenge is worth piloting in a "
                    "more accessible tier where a failure stays contained."
                ),
            )
        )
        tier = lowered
    else:
        factors.append(
            TierFactor(
                factor="innovation_potential",
                input_value=innovation_potential.value,
                effect="no change",
                reason=(
                    f"Innovation potential is {innovation_potential.value}, so there is no "
                    f"case for opening a more accessible tier."
                ),
            )
        )

    # --- Step 4: the floor a high-criticality challenge can never fall below --
    if criticality is Level.HIGH and tier is Tier.SMALL:
        factors.append(
            TierFactor(
                factor="criticality_floor",
                input_value=criticality.value,
                effect=f"{Tier.SMALL.value} -> {Tier.MEDIUM.value}",
                reason=(
                    "A HIGH criticality challenge never lands in the SMALL tier, whatever "
                    "its value or innovation potential."
                ),
            )
        )
        tier = Tier.MEDIUM

    explanation = " ".join(factor.reason for factor in factors) + f" Final tier: {tier.value}."

    return TierDecision(
        tier=tier,
        explanation=explanation,
        factors=factors,
        rules_cited=rules.rules_read,
    )
