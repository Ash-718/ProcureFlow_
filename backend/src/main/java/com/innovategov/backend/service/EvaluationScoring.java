package com.innovategov.backend.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * Pure weighted-average aggregation for expert evaluation scores (Section 20:
 * "evaluation scoring aggregation"). Kept dependency-free for direct unit testing.
 */
public final class EvaluationScoring {

    private EvaluationScoring() {}

    public record WeightedScore(BigDecimal score, BigDecimal weight) {}

    /** Weighted average of scores, rounded to 2 decimal places. Zero if there are no weighted scores. */
    public static BigDecimal weightedTotal(List<WeightedScore> scores) {
        BigDecimal weightedSum = BigDecimal.ZERO;
        BigDecimal weightTotal = BigDecimal.ZERO;
        for (WeightedScore s : scores) {
            weightedSum = weightedSum.add(s.score().multiply(s.weight()));
            weightTotal = weightTotal.add(s.weight());
        }
        if (weightTotal.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return weightedSum.divide(weightTotal, 2, RoundingMode.HALF_UP);
    }
}
