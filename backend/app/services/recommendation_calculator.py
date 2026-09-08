"""
Scale / Modify / Reject scoring.

Direct port of Java's `RecommendationCalculator`. Pure and dependency-free, so
the decision maths can be tested against the Java implementation with fixed
inputs — which matters, because these three numbers are shown prominently on
the demo's recommendation screen.

The model, restated from the Java documentation:

``performance_score``
    Mean, across KPIs that have both a target and a recorded result, of how
    close the pilot came to target. Each KPI is capped at 1.0 so wildly
    overshooting one cannot mask failing others.
``impact_score``
    Breadth — the fraction of those KPIs that met or exceeded target.
    Performance captures magnitude; impact captures how many.
``cost_score``
    There is no per-pilot cost ledger in this schema, so cost efficiency is
    approximated by schedule adherence: the fraction of milestones not marked
    DELAYED. A pilot with no milestones scores a neutral 0.5 rather than 0.

``overall`` is the mean of the three, and the thresholds are 0.70 for SCALE and
0.40 for MODIFY.

**Direction.** Some KPIs are better when lower — time-to-detect, latency, a
false-positive rate. The schema has no direction column, so direction is
inferred from the KPI's name via two keyword sets, and the override set wins:
a "Survey Cost Reduction" KPI records *the improvement achieved*, so higher is
better even though it is named after a cost.

**`Decimal`, not float.** Java uses `BigDecimal` with explicit `HALF_UP`;
Python's default banker's rounding would disagree on exact halves.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

#: A KPI whose name contains one of these records an improvement, so higher is
#: always better — even when the underlying quantity (cost, time, a default
#: rate) is something you would normally want to minimise. Checked first.
HIGHER_IS_BETTER_OVERRIDE_KEYWORDS = frozenset({
    "reduction", "increase", "gain", "improvement",
})

#: Otherwise, a name containing one of these is treated as lower-is-better.
LOWER_IS_BETTER_KEYWORDS = frozenset({"time", "delay", "latency", "rate"})

SCALE_THRESHOLD = Decimal("0.70")
MODIFY_THRESHOLD = Decimal("0.40")

_RATIO_PRECISION = Decimal("0.000001")   # 6 dp, as `divide(..., 6, HALF_UP)`
_SCORE_PRECISION = Decimal("0.0001")     # 4 dp, as `divide(..., 4, HALF_UP)`

_ONE = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True)
class KpiAssessment:
    kpi_name: str
    target_value: Decimal | None
    recorded_value: Decimal | None


@dataclass(frozen=True)
class MilestoneAssessment:
    delayed: bool


@dataclass(frozen=True)
class ScoreResult:
    cost_score: Decimal
    performance_score: Decimal
    impact_score: Decimal
    overall: Decimal
    recommendation: str


def is_lower_is_better(kpi_name: str) -> bool:
    """Infer KPI direction from its name. Overrides are checked first."""
    normalised = (kpi_name or "").lower()
    if any(keyword in normalised for keyword in HIGHER_IS_BETTER_OVERRIDE_KEYWORDS):
        return False
    return any(keyword in normalised for keyword in LOWER_IS_BETTER_KEYWORDS)


def achievement_ratio(kpi: KpiAssessment) -> Decimal | None:
    """
    Per-KPI achievement in [0, 1]; 1.0 means target met or exceeded.

    ``None`` when the KPI cannot be assessed — no target, a zero target, or no
    recorded result. Those are *excluded* from the averages rather than counted
    as zero, so an unmeasured KPI does not silently drag a pilot down.
    """
    if kpi.target_value is None or kpi.target_value == 0 or kpi.recorded_value is None:
        return None

    if is_lower_is_better(kpi.kpi_name):
        if kpi.recorded_value <= 0:
            # Zero incidents / zero elapsed time is the best possible outcome,
            # and avoids a division by zero.
            ratio = _ONE
        else:
            ratio = (kpi.target_value / kpi.recorded_value).quantize(
                _RATIO_PRECISION, rounding=ROUND_HALF_UP)
    else:
        ratio = (kpi.recorded_value / kpi.target_value).quantize(
            _RATIO_PRECISION, rounding=ROUND_HALF_UP)

    return max(_ZERO, min(_ONE, ratio))


def performance_score(kpis: list[KpiAssessment]) -> Decimal:
    """Mean achievement ratio across assessable KPIs. Magnitude."""
    ratios = [r for r in (achievement_ratio(k) for k in kpis) if r is not None]
    if not ratios:
        return _ZERO
    return (sum(ratios, _ZERO) / Decimal(len(ratios))).quantize(
        _SCORE_PRECISION, rounding=ROUND_HALF_UP)


def impact_score(kpis: list[KpiAssessment]) -> Decimal:
    """Fraction of assessable KPIs that met or exceeded target. Breadth."""
    ratios = [r for r in (achievement_ratio(k) for k in kpis) if r is not None]
    if not ratios:
        return _ZERO
    met = sum(1 for ratio in ratios if ratio >= _ONE)
    return (Decimal(met) / Decimal(len(ratios))).quantize(
        _SCORE_PRECISION, rounding=ROUND_HALF_UP)


def cost_score(milestones: list[MilestoneAssessment]) -> Decimal:
    """
    Schedule adherence, standing in for cost efficiency.

    No milestones means no schedule data, which is neutral (0.5) rather than a
    failing 0 — the pilot simply cannot be judged on this axis.
    """
    if not milestones:
        return Decimal("0.5")
    on_schedule = sum(1 for m in milestones if not m.delayed)
    return (Decimal(on_schedule) / Decimal(len(milestones))).quantize(
        _SCORE_PRECISION, rounding=ROUND_HALF_UP)


def compute(kpis: list[KpiAssessment],
            milestones: list[MilestoneAssessment]) -> ScoreResult:
    """The three component scores, their mean, and the resulting decision."""
    cost = cost_score(milestones)
    performance = performance_score(kpis)
    impact = impact_score(kpis)
    overall = ((cost + performance + impact) / Decimal(3)).quantize(
        _SCORE_PRECISION, rounding=ROUND_HALF_UP)

    if overall >= SCALE_THRESHOLD:
        recommendation = "SCALE"
    elif overall >= MODIFY_THRESHOLD:
        recommendation = "MODIFY"
    else:
        recommendation = "REJECT"

    return ScoreResult(cost_score=cost, performance_score=performance,
                       impact_score=impact, overall=overall,
                       recommendation=recommendation)


__all__ = [
    "HIGHER_IS_BETTER_OVERRIDE_KEYWORDS",
    "KpiAssessment",
    "LOWER_IS_BETTER_KEYWORDS",
    "MODIFY_THRESHOLD",
    "MilestoneAssessment",
    "SCALE_THRESHOLD",
    "ScoreResult",
    "achievement_ratio",
    "compute",
    "cost_score",
    "impact_score",
    "is_lower_is_better",
    "performance_score",
]
