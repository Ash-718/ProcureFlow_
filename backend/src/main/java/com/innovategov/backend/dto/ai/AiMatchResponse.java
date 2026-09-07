package com.innovategov.backend.dto.ai;

import com.fasterxml.jackson.annotation.JsonAlias;
import lombok.Getter;
import lombok.Setter;

import java.util.List;
import java.util.Map;

/**
 * Mirrors ai-service's MatchResponse schema (app/schemas/matching.py) for
 * deserializing its response, but this same object is also returned directly to
 * the frontend by MatchingController — so it must serialize as camelCase (this
 * API's convention everywhere else), not the snake_case ai-service uses.
 * @JsonAlias accepts the snake_case name on the way in without affecting the
 * (camelCase) name used on the way out — unlike @JsonProperty, which is
 * bidirectional and would leak snake_case into the frontend response too.
 */
@Getter
@Setter
public class AiMatchResponse {

    @JsonAlias("challenge_id")
    private String challengeId;

    @JsonAlias("ai_provider")
    private String aiProvider;

    private Map<String, Double> weights;

    @JsonAlias("total_candidates_considered")
    private int totalCandidatesConsidered;

    private List<Candidate> results;

    @Getter
    @Setter
    public static class Candidate {
        @JsonAlias("startup_id")
        private String startupId;

        @JsonAlias("company_name")
        private String companyName;

        private int rank;

        @JsonAlias("overall_score")
        private double overallScore;

        @JsonAlias("component_scores")
        private ComponentScores componentScores;

        private List<String> reasons;
        private List<String> gaps;
    }

    @Getter
    @Setter
    public static class ComponentScores {
        @JsonAlias("semantic_similarity")
        private double semanticSimilarity;

        @JsonAlias("technology_match")
        private double technologyMatch;

        @JsonAlias("domain_match")
        private double domainMatch;

        @JsonAlias("experience_score")
        private double experienceScore;

        @JsonAlias("readiness_score")
        private double readinessScore;
    }
}
