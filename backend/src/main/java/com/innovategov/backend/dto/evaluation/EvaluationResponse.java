package com.innovategov.backend.dto.evaluation;

import com.innovategov.backend.entity.Evaluation;
import com.innovategov.backend.entity.EvaluationScore;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Getter
public class EvaluationResponse {
    private final UUID id;
    private final UUID proposalId;
    private final UUID expertId;
    private final String expertName;
    private final BigDecimal totalScore;
    private final String comments;
    private final String aiAssistSummary;
    private final Instant submittedAt;
    private final List<ScoreDto> scores;

    public EvaluationResponse(Evaluation e, List<EvaluationScore> scores) {
        this.id = e.getId();
        this.proposalId = e.getProposal().getId();
        this.expertId = e.getExpert().getId();
        this.expertName = e.getExpert().getFullName();
        this.totalScore = e.getTotalScore();
        this.comments = e.getComments();
        this.aiAssistSummary = e.getAiAssistSummary();
        this.submittedAt = e.getSubmittedAt();
        this.scores = scores.stream().map(ScoreDto::new).toList();
    }

    @Getter
    public static class ScoreDto {
        private final UUID criterionId;
        private final String criterionName;
        private final BigDecimal score;
        private final String remarks;

        public ScoreDto(EvaluationScore s) {
            this.criterionId = s.getCriterion().getId();
            this.criterionName = s.getCriterion().getCriterionName();
            this.score = s.getScore();
            this.remarks = s.getRemarks();
        }
    }
}
