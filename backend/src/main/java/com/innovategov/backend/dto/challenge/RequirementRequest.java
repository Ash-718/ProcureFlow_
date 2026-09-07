package com.innovategov.backend.dto.challenge;

import com.innovategov.backend.entity.enums.RequirementType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RequirementRequest {

    @NotNull
    private RequirementType requirementType;

    @NotBlank
    private String description;

    private boolean mandatory = true;
}
