package com.innovategov.backend.dto.pilot;

import com.innovategov.backend.entity.enums.RecommendationType;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class FinalDecisionRequest {
    @NotNull
    private RecommendationType finalDecision;
}
