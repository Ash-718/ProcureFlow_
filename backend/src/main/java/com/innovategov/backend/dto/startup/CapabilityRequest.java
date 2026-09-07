package com.innovategov.backend.dto.startup;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class CapabilityRequest {

    @NotBlank
    private String technologyTag;

    @NotBlank
    private String domainTag;

    @Min(1)
    @Max(5)
    private Integer proficiencyLevel = 3;

    private String description;
}
