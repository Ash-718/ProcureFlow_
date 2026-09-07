package com.innovategov.backend.dto.startup;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
public class UpdateStartupProfileRequest {

    @NotBlank
    private String companyName;

    private String dpiitNumber;
    private Integer foundedYear;
    private Integer teamSize;
    private String city;
    private String state;
    private String description;

    /** Self-reported pilot-readiness score (0-100); factored into AI matching's readiness component. */
    @DecimalMin("0")
    @DecimalMax("100")
    private BigDecimal readinessScore;
}
