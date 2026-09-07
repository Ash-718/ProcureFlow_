package com.innovategov.backend.entity;

import com.innovategov.backend.entity.enums.ChallengeStatus;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "challenges")
@Getter
@Setter
@NoArgsConstructor
public class Challenge {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "department_id", nullable = false)
    private GovernmentDepartment department;

    @Column(nullable = false)
    private String title;

    @Column(name = "problem_statement", nullable = false, columnDefinition = "TEXT")
    private String problemStatement;

    @Column(name = "desired_technology")
    private String desiredTechnology;

    @Column(nullable = false)
    private String domain;

    @Column(name = "outcomes_expected", columnDefinition = "TEXT")
    private String outcomesExpected;

    @Column(name = "budget_range")
    private String budgetRange;

    @Column(name = "timeline_days")
    private Integer timelineDays;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false)
    private ChallengeStatus status = ChallengeStatus.DRAFT;

    @Column(name = "embedding_model")
    private String embeddingModel;

    @Column(name = "embedding_updated_at")
    private Instant embeddingUpdatedAt;

    @Column(name = "published_at")
    private Instant publishedAt;

    @OneToMany(mappedBy = "challenge", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<ChallengeRequirement> requirements = new ArrayList<>();

    @OneToMany(mappedBy = "challenge", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<ChallengeKpi> kpis = new ArrayList<>();

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }
}
