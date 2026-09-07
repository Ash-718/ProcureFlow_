package com.innovategov.backend.dto.evaluation;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import lombok.Getter;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
public class EvaluationSubmitRequest {

    private String comments;

    @NotEmpty
    @Valid
    private List<EvaluationScoreRequest> scores;
}
