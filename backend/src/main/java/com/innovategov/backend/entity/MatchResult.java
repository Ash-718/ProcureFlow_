package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Read-only from the backend's perspective for the score/explanation fields — these
 * are written exclusively by the AI service (see ai-service/app/services/matching_service.py).
 * The backend's MatchingController proxies the "compute" call to the AI service and
 * reads rows back through this entity for display.
 */
@Entity
@Table(name = "match_results")
@Getter
@Setter
@NoArgsConstructor
public class MatchResult {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "challenge_id", nullable = false)
    private Challenge challenge;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "startup_id", nullable = false)
    private Startup startup;

    @Column(name = "overall_score", nullable = false)
    private BigDecimal overallScore;

    @Column(name = "semantic_similarity_score", nullable = false)
    private BigDecimal semanticSimilarityScore;

    @Column(name = "technology_match_score", nullable = false)
    private BigDecimal technologyMatchScore;

    @Column(name = "domain_match_score", nullable = false)
    private BigDecimal domainMatchScore;

    @Column(name = "experience_score", nullable = false)
    private BigDecimal experienceScore;

    @Column(name = "readiness_score", nullable = false)
    private BigDecimal readinessScore;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "explanation_json", nullable = false, columnDefinition = "jsonb")
    private String explanationJson;

    @Column(nullable = false)
    private Integer rank;

    @Column(name = "ai_provider", nullable = false)
    private String aiProvider;

    @Column(name = "computed_at", nullable = false)
    private Instant computedAt;

    @PrePersist
    void prePersist() {
        if (computedAt == null) {
            computedAt = Instant.now();
        }
    }
}
