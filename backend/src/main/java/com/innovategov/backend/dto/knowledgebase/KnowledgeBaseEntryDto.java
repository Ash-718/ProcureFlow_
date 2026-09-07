package com.innovategov.backend.dto.knowledgebase;

import com.innovategov.backend.entity.PilotKnowledgeBase;
import lombok.Getter;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Getter
public class KnowledgeBaseEntryDto {
    private final UUID id;
    private final UUID pilotId;
    private final String challengeTitle;
    private final String domain;
    private final List<String> technologyTags;
    private final String departmentName;
    private final String startupName;
    private final String outcomeSummary;
    private final Boolean success;
    private final Instant createdAt;

    public KnowledgeBaseEntryDto(PilotKnowledgeBase kb) {
        this.id = kb.getId();
        this.pilotId = kb.getPilot().getId();
        this.challengeTitle = kb.getPilot().getChallenge().getTitle();
        this.domain = kb.getDomain();
        this.technologyTags = List.of(kb.getTechnologyTags());
        this.departmentName = kb.getDepartment().getDepartmentName();
        this.startupName = kb.getPilot().getStartup().getCompanyName();
        this.outcomeSummary = kb.getOutcomeSummary();
        this.success = kb.getSuccess();
        this.createdAt = kb.getCreatedAt();
    }
}
