package com.innovategov.backend.dto.proposal;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
public class ProposalCreateRequest {

    @NotBlank
    private String summary;

    private String proposedApproach;
    private BigDecimal costEstimate;
    private Integer timelineEstimateDays;
}
