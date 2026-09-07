package com.innovategov.backend.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Pure, dependency-free scoring logic for the Scale/Modify/Reject recommendation
 * engine (Section 7). Kept free of JPA/Spring so the decision math is directly
 * unit-testable with fixed inputs (Section 20).
 *
 * Design notes (documented since the spec doesn't fully pin these down):
 *  - performance_score: average, across KPIs with both a target and a recorded
 *    result, of how close the pilot came to target (capped at 1.0 per KPI so
 *    wildly overshooting one KPI can't mask failing others).
 *  - impact_score: breadth — the fraction of those KPIs that met or exceeded
 *    target. performance_score captures magnitude, impact_score captures breadth.
 *  - cost_score: this prototype has no per-pilot actual-vs-budgeted cost ledger,
 *    so cost efficiency is approximated by schedule adherence — the fraction of
 *    milestones completed without being marked DELAYED. A pilot that blew its
 *    timeline is treated as having blown its cost efficiency too, which is a
 *    reasonable proxy and, importantly, a transparent and reproducible one.
 *  - Some KPIs are "lower is better" (time-to-detect, false-positive rate, cost
 *    reduction targets phrased as a ceiling). Since the schema has no explicit
 *    direction column, direction is inferred from the KPI name via a keyword
 *    list — documented here rather than hidden.
 */
public final class RecommendationCalculator {

    // "reduction"/"increase"/"gain"/"improvement" KPIs are excluded even if they also match a
    // keyword below (e.g. "Survey Cost Reduction", "Loan Default Reduction", "Referral Time
    // Reduction") because the *recorded value already is the improvement/percentage achieved* —
    // higher is always better for those, regardless of the underlying quantity being named after
    // something you'd normally want to minimize (cost, time, default rate).
    private static final Set<String> HIGHER_IS_BETTER_OVERRIDE_KEYWORDS = Set.of(
            "reduction", "increase", "gain", "improvement"
    );
    private static final Set<String> LOWER_IS_BETTER_KEYWORDS = Set.of(
            "time", "delay", "latency", "rate"
    );

    public static final BigDecimal SCALE_THRESHOLD = new BigDecimal("0.70");
    public static final BigDecimal MODIFY_THRESHOLD = new BigDecimal("0.40");

    private RecommendationCalculator() {}

    public record KpiAssessment(String kpiName, BigDecimal targetValue, BigDecimal recordedValue) {}

    public record MilestoneAssessment(boolean delayed) {}

    public record ScoreResult(BigDecimal costScore, BigDecimal performanceScore, BigDecimal impactScore, BigDecimal overall, String recommendation) {}

    public static boolean isLowerIsBetter(String kpiName) {
        String normalized = kpiName.toLowerCase(Locale.ROOT);
        if (HIGHER_IS_BETTER_OVERRIDE_KEYWORDS.stream().anyMatch(normalized::contains)) {
            return false;
        }
        return LOWER_IS_BETTER_KEYWORDS.stream().anyMatch(normalized::contains);
    }

    /** Per-KPI achievement ratio in [0, 1] — 1.0 means target met or exceeded. */
    public static BigDecimal achievementRatio(KpiAssessment kpi) {
        if (kpi.targetValue() == null || kpi.targetValue().compareTo(BigDecimal.ZERO) == 0 || kpi.recordedValue() == null) {
            return null;
        }
        BigDecimal ratio;
        if (isLowerIsBetter(kpi.kpiName())) {
            if (kpi.recordedValue().compareTo(BigDecimal.ZERO) <= 0) {
                ratio = BigDecimal.ONE; // zero incidents/zero time is the best possible outcome
            } else {
                ratio = kpi.targetValue().divide(kpi.recordedValue(), 6, RoundingMode.HALF_UP);
            }
        } else {
            ratio = kpi.recordedValue().divide(kpi.targetValue(), 6, RoundingMode.HALF_UP);
        }
        return ratio.min(BigDecimal.ONE).max(BigDecimal.ZERO);
    }

    public static BigDecimal performanceScore(List<KpiAssessment> kpis) {
        List<BigDecimal> ratios = kpis.stream().map(RecommendationCalculator::achievementRatio)
                .filter(r -> r != null).toList();
        if (ratios.isEmpty()) return BigDecimal.ZERO;
        BigDecimal sum = ratios.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.divide(BigDecimal.valueOf(ratios.size()), 4, RoundingMode.HALF_UP);
    }

    public static BigDecimal impactScore(List<KpiAssessment> kpis) {
        List<BigDecimal> ratios = kpis.stream().map(RecommendationCalculator::achievementRatio)
                .filter(r -> r != null).toList();
        if (ratios.isEmpty()) return BigDecimal.ZERO;
        long metOrExceeded = ratios.stream().filter(r -> r.compareTo(BigDecimal.ONE) >= 0).count();
        return BigDecimal.valueOf(metOrExceeded).divide(BigDecimal.valueOf(ratios.size()), 4, RoundingMode.HALF_UP);
    }

    public static BigDecimal costScore(List<MilestoneAssessment> milestones) {
        if (milestones.isEmpty()) return BigDecimal.valueOf(0.5); // no schedule data — neutral, not penalized
        long onSchedule = milestones.stream().filter(m -> !m.delayed()).count();
        return BigDecimal.valueOf(onSchedule).divide(BigDecimal.valueOf(milestones.size()), 4, RoundingMode.HALF_UP);
    }

    public static ScoreResult compute(List<KpiAssessment> kpis, List<MilestoneAssessment> milestones) {
        BigDecimal cost = costScore(milestones);
        BigDecimal performance = performanceScore(kpis);
        BigDecimal impact = impactScore(kpis);
        BigDecimal overall = cost.add(performance).add(impact)
                .divide(BigDecimal.valueOf(3), 4, RoundingMode.HALF_UP);

        String recommendation;
        if (overall.compareTo(SCALE_THRESHOLD) >= 0) {
            recommendation = "SCALE";
        } else if (overall.compareTo(MODIFY_THRESHOLD) >= 0) {
            recommendation = "MODIFY";
        } else {
            recommendation = "REJECT";
        }
        return new ScoreResult(cost, performance, impact, overall, recommendation);
    }
}
