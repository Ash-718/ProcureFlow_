package com.innovategov.backend.dto.challenge;

import com.innovategov.backend.entity.Challenge;
import com.innovategov.backend.entity.ChallengeKpi;
import com.innovategov.backend.entity.ChallengeRequirement;
import lombok.Getter;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Getter
public class ChallengeResponse {
    private final UUID id;
    private final UUID departmentId;
    private final String departmentName;
    private final String title;
    private final String problemStatement;
    private final String desiredTechnology;
    private final String domain;
    private final String outcomesExpected;
    private final String budgetRange;
    private final Integer timelineDays;
    private final String status;
    private final Instant publishedAt;
    private final List<RequirementDto> requirements;
    private final List<KpiDto> kpis;

    public ChallengeResponse(Challenge c, List<ChallengeRequirement> requirements, List<ChallengeKpi> kpis) {
        this.id = c.getId();
        this.departmentId = c.getDepartment().getId();
        this.departmentName = c.getDepartment().getDepartmentName();
        this.title = c.getTitle();
        this.problemStatement = c.getProblemStatement();
        this.desiredTechnology = c.getDesiredTechnology();
        this.domain = c.getDomain();
        this.outcomesExpected = c.getOutcomesExpected();
        this.budgetRange = c.getBudgetRange();
        this.timelineDays = c.getTimelineDays();
        this.status = c.getStatus().name();
        this.publishedAt = c.getPublishedAt();
        this.requirements = requirements.stream().map(RequirementDto::new).toList();
        this.kpis = kpis.stream().map(KpiDto::new).toList();
    }

    @Getter
    public static class RequirementDto {
        private final UUID id;
        private final String requirementType;
        private final String description;
        private final boolean mandatory;

        public RequirementDto(ChallengeRequirement r) {
            this.id = r.getId();
            this.requirementType = r.getRequirementType().name();
            this.description = r.getDescription();
            this.mandatory = r.isMandatory();
        }
    }

    @Getter
    public static class KpiDto {
        private final UUID id;
        private final String kpiName;
        private final Object targetValue;
        private final String unit;
        private final Object weight;

        public KpiDto(ChallengeKpi k) {
            this.id = k.getId();
            this.kpiName = k.getKpiName();
            this.targetValue = k.getTargetValue();
            this.unit = k.getUnit();
            this.weight = k.getWeight();
        }
    }
}
