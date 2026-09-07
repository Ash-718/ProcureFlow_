package com.innovategov.backend.dto.evaluation;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.UUID;

@Getter
@Setter
public class EvaluationScoreRequest {
    @NotNull
    private UUID criterionId;

    @NotNull
    private BigDecimal score;

    private String remarks;
}
