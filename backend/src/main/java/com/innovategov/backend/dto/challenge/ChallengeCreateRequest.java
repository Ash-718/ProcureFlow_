package com.innovategov.backend.dto.challenge;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class ChallengeCreateRequest {

    @NotBlank
    private String title;

    @NotBlank
    private String problemStatement;

    private String desiredTechnology;

    @NotBlank
    private String domain;

    private String outcomesExpected;
    private String budgetRange;
    private Integer timelineDays;

    @Valid
    private List<RequirementRequest> requirements = new ArrayList<>();

    @Valid
    private List<KpiRequest> kpis = new ArrayList<>();
}
