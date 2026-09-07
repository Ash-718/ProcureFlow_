package com.innovategov.backend.dto.pilot;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
public class KpiResultRequest {
    @NotNull
    private BigDecimal recordedValue;

    private String notes;
}
