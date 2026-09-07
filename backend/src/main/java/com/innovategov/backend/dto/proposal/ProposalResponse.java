package com.innovategov.backend.dto.proposal;

import com.innovategov.backend.entity.Proposal;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Getter
public class ProposalResponse {
    private final UUID id;
    private final UUID challengeId;
    private final String challengeTitle;
    private final UUID startupId;
    private final String companyName;
    private final String summary;
    private final String proposedApproach;
    private final BigDecimal costEstimate;
    private final Integer timelineEstimateDays;
    private final String status;
    private final Instant submittedAt;

    public ProposalResponse(Proposal p) {
        this.id = p.getId();
        this.challengeId = p.getChallenge().getId();
        this.challengeTitle = p.getChallenge().getTitle();
        this.startupId = p.getStartup().getId();
        this.companyName = p.getStartup().getCompanyName();
        this.summary = p.getSummary();
        this.proposedApproach = p.getProposedApproach();
        this.costEstimate = p.getCostEstimate();
        this.timelineEstimateDays = p.getTimelineEstimateDays();
        this.status = p.getStatus().name();
        this.submittedAt = p.getSubmittedAt();
    }
}
