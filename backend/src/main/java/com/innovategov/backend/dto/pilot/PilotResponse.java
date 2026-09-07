package com.innovategov.backend.dto.pilot;

import com.innovategov.backend.entity.*;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@Getter
public class PilotResponse {
    private final UUID id;
    private final UUID challengeId;
    private final String challengeTitle;
    private final UUID startupId;
    private final String companyName;
    private final LocalDate startDate;
    private final LocalDate endDate;
    private final String status;
    private final List<MilestoneDto> milestones;
    private final List<KpiDto> kpis;
    private final ContractDto contract;

    public PilotResponse(Pilot pilot, List<PilotMilestone> milestones, List<Kpi> kpis, List<KpiResult> latestResults) {
        this.id = pilot.getId();
        this.challengeId = pilot.getChallenge().getId();
        this.challengeTitle = pilot.getChallenge().getTitle();
        this.startupId = pilot.getStartup().getId();
        this.companyName = pilot.getStartup().getCompanyName();
        this.startDate = pilot.getStartDate();
        this.endDate = pilot.getEndDate();
        this.status = pilot.getStatus().name();
        this.milestones = milestones.stream().map(MilestoneDto::new).toList();
        this.kpis = kpis.stream().map(k -> new KpiDto(k, latestResults.stream()
                .filter(r -> r.getKpi().getId().equals(k.getId())).findFirst().orElse(null))).toList();
        this.contract = pilot.getContract() == null ? null : new ContractDto(pilot.getContract());
    }

    @Getter
    public static class MilestoneDto {
        private final UUID id;
        private final String title;
        private final LocalDate dueDate;
        private final String status;
        private final LocalDate completionDate;

        public MilestoneDto(PilotMilestone m) {
            this.id = m.getId();
            this.title = m.getTitle();
            this.dueDate = m.getDueDate();
            this.status = m.getStatus().name();
            this.completionDate = m.getCompletionDate();
        }
    }

    @Getter
    public static class KpiDto {
        private final UUID id;
        private final String kpiName;
        private final BigDecimal targetValue;
        private final String unit;
        private final BigDecimal latestRecordedValue;
        private final Instant latestRecordedAt;

        public KpiDto(Kpi k, KpiResult latest) {
            this.id = k.getId();
            this.kpiName = k.getKpiName();
            this.targetValue = k.getTargetValue();
            this.unit = k.getUnit();
            this.latestRecordedValue = latest == null ? null : latest.getRecordedValue();
            this.latestRecordedAt = latest == null ? null : latest.getRecordedAt();
        }
    }

    @Getter
    public static class ContractDto {
        private final UUID id;
        private final BigDecimal contractValue;
        private final String ipTerms;
        private final String dataTerms;
        private final String paymentTerms;
        private final String status;

        public ContractDto(Contract c) {
            this.id = c.getId();
            this.contractValue = c.getContractValue();
            this.ipTerms = c.getIpTerms();
            this.dataTerms = c.getDataTerms();
            this.paymentTerms = c.getPaymentTerms();
            this.status = c.getStatus().name();
        }
    }
}
