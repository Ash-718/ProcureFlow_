package com.innovategov.backend.dto.matching;

import com.fasterxml.jackson.databind.JsonNode;
import com.innovategov.backend.entity.MatchResult;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Getter
public class MatchResultDto {
    private final UUID startupId;
    private final String companyName;
    private final int rank;
    private final BigDecimal overallScore;
    private final BigDecimal semanticSimilarityScore;
    private final BigDecimal technologyMatchScore;
    private final BigDecimal domainMatchScore;
    private final BigDecimal experienceScore;
    private final BigDecimal readinessScore;
    private final List<String> reasons;
    private final List<String> gaps;
    private final String aiProvider;

    public MatchResultDto(MatchResult m, JsonNode explanation) {
        this.startupId = m.getStartup().getId();
        this.companyName = m.getStartup().getCompanyName();
        this.rank = m.getRank();
        this.overallScore = m.getOverallScore();
        this.semanticSimilarityScore = m.getSemanticSimilarityScore();
        this.technologyMatchScore = m.getTechnologyMatchScore();
        this.domainMatchScore = m.getDomainMatchScore();
        this.experienceScore = m.getExperienceScore();
        this.readinessScore = m.getReadinessScore();
        this.aiProvider = m.getAiProvider();
        this.reasons = toStringList(explanation, "reasons");
        this.gaps = toStringList(explanation, "gaps");
    }

    private static List<String> toStringList(JsonNode explanation, String field) {
        if (explanation == null || !explanation.has(field)) return List.of();
        List<String> values = new java.util.ArrayList<>();
        explanation.get(field).forEach(node -> values.add(node.asText()));
        return values;
    }
}
