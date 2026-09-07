package com.innovategov.backend.dto.ai;

import com.fasterxml.jackson.annotation.JsonAlias;
import lombok.Getter;
import lombok.Setter;

import java.util.List;

/**
 * Mirrors ai-service's KnowledgeBaseSimilarResponse schema, but — like
 * AiMatchResponse — is also returned directly to the frontend, so it must
 * serialize as camelCase. @JsonAlias accepts ai-service's snake_case on input
 * without affecting the camelCase name used when this object is serialized back out.
 */
@Getter
@Setter
public class AiKnowledgeBaseSimilarResponse {

    @JsonAlias("ai_provider")
    private String aiProvider;

    private List<Match> results;

    @Getter
    @Setter
    public static class Match {
        @JsonAlias("pilot_id")
        private String pilotId;

        @JsonAlias("challenge_title")
        private String challengeTitle;

        private String domain;

        @JsonAlias("technology_tags")
        private List<String> technologyTags;

        @JsonAlias("outcome_summary")
        private String outcomeSummary;

        private Boolean success;
        private double similarity;
    }
}
