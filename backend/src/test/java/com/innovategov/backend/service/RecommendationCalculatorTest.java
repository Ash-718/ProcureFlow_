package com.innovategov.backend.service;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static com.innovategov.backend.service.RecommendationCalculator.KpiAssessment;
import static com.innovategov.backend.service.RecommendationCalculator.MilestoneAssessment;
import static org.assertj.core.api.Assertions.assertThat;

class RecommendationCalculatorTest {

    @Test
    void higherIsBetterKpiFullyMet_scoresOneHundredPercent() {
        BigDecimal ratio = RecommendationCalculator.achievementRatio(
                new KpiAssessment("Segregation Compliance", BigDecimal.valueOf(75), BigDecimal.valueOf(81)));
        assertThat(ratio).isEqualByComparingTo("1.0");
    }

    @Test
    void higherIsBetterKpiPartiallyMet_scoresProportionally() {
        BigDecimal ratio = RecommendationCalculator.achievementRatio(
                new KpiAssessment("Farmer Adoption", BigDecimal.valueOf(20000), BigDecimal.valueOf(10000)));
        assertThat(ratio).isEqualByComparingTo("0.5");
    }

    @Test
    void lowerIsBetterKpiBeatsTarget_scoresOneHundredPercent() {
        // "Mean Time to Detect" -- lower is better; recorded (30) beats target (60)
        BigDecimal ratio = RecommendationCalculator.achievementRatio(
                new KpiAssessment("Mean Time to Detect", BigDecimal.valueOf(60), BigDecimal.valueOf(30)));
        assertThat(ratio).isEqualByComparingTo("1.0");
    }

    @Test
    void lowerIsBetterKpiMissesTarget_scoresProportionally() {
        // recorded (145) is worse than target (60) -> ratio = 60/145
        BigDecimal ratio = RecommendationCalculator.achievementRatio(
                new KpiAssessment("Mean Time to Detect", BigDecimal.valueOf(60), BigDecimal.valueOf(145)));
        assertThat(ratio).isEqualByComparingTo(BigDecimal.valueOf(60).divide(BigDecimal.valueOf(145), 6, java.math.RoundingMode.HALF_UP));
    }

    @Test
    void reductionFramedKpi_isTreatedAsHigherIsBetter_evenThoughItNamesACostOrTimeQuantity() {
        // "Survey Cost Reduction" / "Loan Default Reduction" / "Referral Time Reduction": the
        // *recorded value* is already the improvement percentage, so exceeding target is good,
        // despite the name containing "cost"/"default"/"time" which would otherwise suggest
        // lower-is-better.
        assertThat(RecommendationCalculator.isLowerIsBetter("Survey Cost Reduction")).isFalse();
        assertThat(RecommendationCalculator.isLowerIsBetter("Loan Default Reduction")).isFalse();
        assertThat(RecommendationCalculator.isLowerIsBetter("Referral Time Reduction")).isFalse();

        BigDecimal ratio = RecommendationCalculator.achievementRatio(
                new KpiAssessment("Survey Cost Reduction", BigDecimal.valueOf(40), BigDecimal.valueOf(45)));
        assertThat(ratio).isEqualByComparingTo("1.0"); // exceeded target reduction -> fully met, not penalized
    }

    @Test
    void rawTimeOrRateKpi_withoutReductionFraming_isTreatedAsLowerIsBetter() {
        assertThat(RecommendationCalculator.isLowerIsBetter("Mean Time to Detect")).isTrue();
        assertThat(RecommendationCalculator.isLowerIsBetter("False Positive Rate")).isTrue();
    }

    @Test
    void kpiWithoutTargetOrResult_isExcludedFromScoring() {
        assertThat(RecommendationCalculator.achievementRatio(new KpiAssessment("X", null, BigDecimal.TEN))).isNull();
        assertThat(RecommendationCalculator.achievementRatio(new KpiAssessment("X", BigDecimal.TEN, null))).isNull();
        assertThat(RecommendationCalculator.achievementRatio(new KpiAssessment("X", BigDecimal.ZERO, BigDecimal.TEN))).isNull();
    }

    @Test
    void costScore_isFractionOfMilestonesNotDelayed() {
        List<MilestoneAssessment> milestones = List.of(
                new MilestoneAssessment(false), new MilestoneAssessment(false), new MilestoneAssessment(true));
        assertThat(RecommendationCalculator.costScore(milestones)).isEqualByComparingTo(
                BigDecimal.valueOf(2).divide(BigDecimal.valueOf(3), 4, java.math.RoundingMode.HALF_UP));
    }

    @Test
    void costScore_withNoMilestones_isNeutral() {
        assertThat(RecommendationCalculator.costScore(List.of())).isEqualByComparingTo("0.5");
    }

    @Test
    void strongPilot_allKpisExceeded_noDelays_recommendsScale() {
        // Mirrors the seeded CleanLoop Robotics pilot: all 3 KPIs beat target, no delayed milestones.
        List<KpiAssessment> kpis = List.of(
                new KpiAssessment("Segregation Compliance", BigDecimal.valueOf(75), BigDecimal.valueOf(81)),
                new KpiAssessment("Collection Cost Reduction", BigDecimal.valueOf(20), BigDecimal.valueOf(24)),
                new KpiAssessment("Route Efficiency Gain", BigDecimal.valueOf(20), BigDecimal.valueOf(23))
        );
        List<MilestoneAssessment> milestones = List.of(
                new MilestoneAssessment(false), new MilestoneAssessment(false), new MilestoneAssessment(false));

        RecommendationCalculator.ScoreResult result = RecommendationCalculator.compute(kpis, milestones);

        assertThat(result.overall()).isGreaterThanOrEqualTo(RecommendationCalculator.SCALE_THRESHOLD);
        assertThat(result.recommendation()).isEqualTo("SCALE");
    }

    @Test
    void weakPilot_allKpisMissedByWideMargin_withDelays_recommendsReject() {
        // Mirrors the seeded SecureNet Labs pilot: all 3 KPIs miss target badly, one delayed milestone.
        List<KpiAssessment> kpis = List.of(
                new KpiAssessment("Mean Time to Detect", BigDecimal.valueOf(60), BigDecimal.valueOf(145)),
                new KpiAssessment("False Positive Rate", BigDecimal.valueOf(10), BigDecimal.valueOf(27)),
                new KpiAssessment("Incidents Mitigated", BigDecimal.valueOf(90), BigDecimal.valueOf(61))
        );
        List<MilestoneAssessment> milestones = List.of(
                new MilestoneAssessment(false), new MilestoneAssessment(true), new MilestoneAssessment(false));

        RecommendationCalculator.ScoreResult result = RecommendationCalculator.compute(kpis, milestones);

        assertThat(result.overall()).isLessThan(RecommendationCalculator.MODIFY_THRESHOLD);
        assertThat(result.recommendation()).isEqualTo("REJECT");
    }

    @Test
    void mixedPilot_partialAchievement_recommendsModify() {
        // performance = avg(0.8, 0.8) = 0.8; impact = 0 (neither met target); cost = 1.0 (on schedule)
        // overall = (1.0 + 0.8 + 0) / 3 = 0.60 -> within [0.40, 0.70) -> MODIFY
        List<KpiAssessment> kpis = List.of(
                new KpiAssessment("Farmer Adoption", BigDecimal.valueOf(20000), BigDecimal.valueOf(16000)),
                new KpiAssessment("Yield Improvement", BigDecimal.valueOf(15), BigDecimal.valueOf(12))
        );
        List<MilestoneAssessment> milestones = List.of(
                new MilestoneAssessment(false), new MilestoneAssessment(false));

        RecommendationCalculator.ScoreResult result = RecommendationCalculator.compute(kpis, milestones);

        assertThat(result.overall())
                .isGreaterThanOrEqualTo(RecommendationCalculator.MODIFY_THRESHOLD)
                .isLessThan(RecommendationCalculator.SCALE_THRESHOLD);
        assertThat(result.recommendation()).isEqualTo("MODIFY");
    }

    @Test
    void decisionBoundaries_areInclusiveAtScaleThreshold_exclusiveBelow() {
        // overall exactly at 0.70 -> SCALE (>=)
        List<KpiAssessment> kpis = List.of(new KpiAssessment("X", BigDecimal.TEN, BigDecimal.valueOf(7)));
        List<MilestoneAssessment> milestones = List.of(new MilestoneAssessment(false));
        // performance = 0.7, impact = 0 (7 < 10, not met), cost = 1.0 -> overall = (1.0+0.7+0)/3 = 0.5667 -> MODIFY
        RecommendationCalculator.ScoreResult result = RecommendationCalculator.compute(kpis, milestones);
        assertThat(result.recommendation()).isEqualTo("MODIFY");
    }
}
