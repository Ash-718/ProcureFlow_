package com.innovategov.backend.dto.startup;

import com.innovategov.backend.entity.Startup;
import com.innovategov.backend.entity.StartupCapability;
import com.innovategov.backend.entity.StartupProject;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Getter
public class StartupResponse {
    private final UUID id;
    private final String companyName;
    private final String dpiitNumber;
    private final Integer foundedYear;
    private final Integer teamSize;
    private final String city;
    private final String state;
    private final BigDecimal readinessScore;
    private final String description;
    private final List<CapabilityDto> capabilities;
    private final List<ProjectDto> projects;

    public StartupResponse(Startup startup, List<StartupCapability> capabilities, List<StartupProject> projects) {
        this.id = startup.getId();
        this.companyName = startup.getCompanyName();
        this.dpiitNumber = startup.getDpiitNumber();
        this.foundedYear = startup.getFoundedYear();
        this.teamSize = startup.getTeamSize();
        this.city = startup.getCity();
        this.state = startup.getState();
        this.readinessScore = startup.getReadinessScore();
        this.description = startup.getDescription();
        this.capabilities = capabilities.stream().map(CapabilityDto::new).toList();
        this.projects = projects.stream().map(ProjectDto::new).toList();
    }

    @Getter
    public static class CapabilityDto {
        private final UUID id;
        private final String technologyTag;
        private final String domainTag;
        private final Integer proficiencyLevel;
        private final String description;

        public CapabilityDto(StartupCapability c) {
            this.id = c.getId();
            this.technologyTag = c.getTechnologyTag();
            this.domainTag = c.getDomainTag();
            this.proficiencyLevel = c.getProficiencyLevel();
            this.description = c.getDescription();
        }
    }

    @Getter
    public static class ProjectDto {
        private final UUID id;
        private final String title;
        private final String domain;
        private final String technologyStack;
        private final String clientType;
        private final String outcomeSummary;
        private final Integer year;

        public ProjectDto(StartupProject p) {
            this.id = p.getId();
            this.title = p.getTitle();
            this.domain = p.getDomain();
            this.technologyStack = p.getTechnologyStack();
            this.clientType = p.getClientType().name();
            this.outcomeSummary = p.getOutcomeSummary();
            this.year = p.getYear();
        }
    }
}
