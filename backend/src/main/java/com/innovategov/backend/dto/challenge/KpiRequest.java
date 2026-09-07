package com.innovategov.backend.dto.challenge;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
public class KpiRequest {

    @NotBlank
    private String kpiName;

    private BigDecimal targetValue;
    private String unit;
    private BigDecimal weight = BigDecimal.ONE;
}
