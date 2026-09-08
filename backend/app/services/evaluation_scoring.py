"""
Weighted aggregation of an expert's per-criterion scores.

Direct port of Java's `EvaluationScoring`. Pure and dependency-free so the
arithmetic can be tested against the Java implementation with fixed inputs.

    total = sum(score * weight) / sum(weight)

rounded to 2 decimal places, ROUND_HALF_UP. Zero when the weights sum to zero,
which also covers an empty score list.

`Decimal` throughout, not float: the Java version uses `BigDecimal` with
explicit `HALF_UP`, and Python's default banker's rounding would disagree on
exact-half values such as 7.125.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class WeightedScore:
    score: Decimal
    weight: Decimal


def weighted_total(scores: list[WeightedScore]) -> Decimal:
    """Weighted average of the given scores, to 2 dp."""
    weighted_sum = Decimal("0")
    weight_total = Decimal("0")
    for entry in scores:
        weighted_sum += entry.score * entry.weight
        weight_total += entry.weight

    if weight_total == 0:
        return Decimal("0")

    return (weighted_sum / weight_total).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = ["WeightedScore", "weighted_total"]
