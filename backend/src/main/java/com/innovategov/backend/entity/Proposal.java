package com.innovategov.backend.entity;

import com.innovategov.backend.entity.enums.ProposalStatus;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "proposals")
@Getter
@Setter
@NoArgsConstructor
public class Proposal {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "challenge_id", nullable = false)
    private Challenge challenge;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "startup_id", nullable = false)
    private Startup startup;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String summary;

    @Column(name = "proposed_approach", columnDefinition = "TEXT")
    private String proposedApproach;

    @Column(name = "cost_estimate")
    private BigDecimal costEstimate;

    @Column(name = "timeline_estimate_days")
    private Integer timelineEstimateDays;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false)
    private ProposalStatus status = ProposalStatus.SUBMITTED;

    @Column(name = "submitted_at", nullable = false)
    private Instant submittedAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        submittedAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }
}
