package com.innovategov.backend.dto.pilot;

import com.innovategov.backend.entity.Recommendation;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Getter
public class RecommendationResponse {
    private final UUID id;
    private final UUID pilotId;
    private final String recommendation;
    private final BigDecimal costScore;
    private final BigDecimal performanceScore;
    private final BigDecimal impactScore;
    private final String rationaleText;
    private final Instant generatedAt;
    private final String reviewedByName;
    private final String finalDecision;
    private final Instant decidedAt;

    public RecommendationResponse(Recommendation r) {
        this.id = r.getId();
        this.pilotId = r.getPilot().getId();
        this.recommendation = r.getRecommendation().name();
        this.costScore = r.getCostScore();
        this.performanceScore = r.getPerformanceScore();
        this.impactScore = r.getImpactScore();
        this.rationaleText = r.getRationaleText();
        this.generatedAt = r.getGeneratedAt();
        this.reviewedByName = r.getReviewedBy() == null ? null : r.getReviewedBy().getFullName();
        this.finalDecision = r.getFinalDecision() == null ? null : r.getFinalDecision().name();
        this.decidedAt = r.getDecidedAt();
    }
}
