package com.innovategov.backend.dto.pilot;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Getter
@Setter
public class PilotCreateRequest {

    @NotNull
    private UUID challengeId;

    @NotNull
    private UUID startupId;

    @NotNull
    private LocalDate startDate;

    private LocalDate endDate;

    @Valid
    private List<MilestoneRequest> milestones = new ArrayList<>();

    @Valid
    private List<KpiDefinitionRequest> kpis = new ArrayList<>();

    private ContractRequest contract;

    @Getter
    @Setter
    public static class MilestoneRequest {
        private String title;
        private LocalDate dueDate;
    }

    @Getter
    @Setter
    public static class KpiDefinitionRequest {
        private String kpiName;
        private BigDecimal targetValue;
        private String unit;
    }

    @Getter
    @Setter
    public static class ContractRequest {
        private BigDecimal contractValue;
        private String ipTerms;
        private String dataTerms;
        private String paymentTerms;
    }
}
