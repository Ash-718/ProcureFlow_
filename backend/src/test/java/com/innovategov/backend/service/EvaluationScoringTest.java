package com.innovategov.backend.service;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static com.innovategov.backend.service.EvaluationScoring.WeightedScore;
import static org.assertj.core.api.Assertions.assertThat;

class EvaluationScoringTest {

    @Test
    void singleCriterion_totalEqualsItsScore() {
        BigDecimal total = EvaluationScoring.weightedTotal(
                List.of(new WeightedScore(BigDecimal.valueOf(8), BigDecimal.ONE)));
        assertThat(total).isEqualByComparingTo("8.00");
    }

    @Test
    void matchesTheDefaultChallengeRubricWeights() {
        // Mirrors ChallengeService.ensureDefaultEvaluationCriteria: Technical Feasibility 0.30,
        // Cost Effectiveness 0.25, Scalability 0.25, Team Capability 0.20.
        List<WeightedScore> scores = List.of(
                new WeightedScore(BigDecimal.valueOf(9.0), new BigDecimal("0.30")),
                new WeightedScore(BigDecimal.valueOf(7.5), new BigDecimal("0.25")),
                new WeightedScore(BigDecimal.valueOf(9.0), new BigDecimal("0.25")),
                new WeightedScore(BigDecimal.valueOf(8.0), new BigDecimal("0.20"))
        );
        BigDecimal expected = BigDecimal.valueOf(9.0).multiply(new BigDecimal("0.30"))
                .add(BigDecimal.valueOf(7.5).multiply(new BigDecimal("0.25")))
                .add(BigDecimal.valueOf(9.0).multiply(new BigDecimal("0.25")))
                .add(BigDecimal.valueOf(8.0).multiply(new BigDecimal("0.20")));
        // weights already sum to 1.00, so the weighted sum IS the weighted average
        assertThat(EvaluationScoring.weightedTotal(scores)).isEqualByComparingTo(expected.setScale(2, java.math.RoundingMode.HALF_UP));
    }

    @Test
    void unequalWeights_areNormalizedByTheirSum() {
        // weight sum = 3, not 1 -- result must still be a proper weighted *average*
        List<WeightedScore> scores = List.of(
                new WeightedScore(BigDecimal.valueOf(10), BigDecimal.valueOf(1)),
                new WeightedScore(BigDecimal.valueOf(4), BigDecimal.valueOf(2))
        );
        // (10*1 + 4*2) / 3 = 18/3 = 6.00
        assertThat(EvaluationScoring.weightedTotal(scores)).isEqualByComparingTo("6.00");
    }

    @Test
    void noScores_returnsZero_ratherThanDividingByZero() {
        assertThat(EvaluationScoring.weightedTotal(List.of())).isEqualByComparingTo("0");
    }

    @Test
    void allZeroWeights_returnsZero_ratherThanDividingByZero() {
        List<WeightedScore> scores = List.of(
                new WeightedScore(BigDecimal.TEN, BigDecimal.ZERO),
                new WeightedScore(BigDecimal.valueOf(5), BigDecimal.ZERO)
        );
        assertThat(EvaluationScoring.weightedTotal(scores)).isEqualByComparingTo("0");
    }
}
