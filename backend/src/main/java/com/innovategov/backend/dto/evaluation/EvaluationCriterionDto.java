package com.innovategov.backend.dto.evaluation;

import com.innovategov.backend.entity.EvaluationCriterion;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.UUID;

@Getter
public class EvaluationCriterionDto {
    private final UUID id;
    private final String criterionName;
    private final BigDecimal maxScore;
    private final BigDecimal weight;

    public EvaluationCriterionDto(EvaluationCriterion c) {
        this.id = c.getId();
        this.criterionName = c.getCriterionName();
        this.maxScore = c.getMaxScore();
        this.weight = c.getWeight();
    }
}
