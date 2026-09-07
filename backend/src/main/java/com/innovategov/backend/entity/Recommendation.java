package com.innovategov.backend.entity;

import com.innovategov.backend.entity.enums.RecommendationType;
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
@Table(name = "recommendations")
@Getter
@Setter
@NoArgsConstructor
public class Recommendation {

    @Id
    @GeneratedValue
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "pilot_id", nullable = false, unique = true)
    private Pilot pilot;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false)
    private RecommendationType recommendation;

    @Column(name = "cost_score", nullable = false)
    private BigDecimal costScore;

    @Column(name = "performance_score", nullable = false)
    private BigDecimal performanceScore;

    @Column(name = "impact_score", nullable = false)
    private BigDecimal impactScore;

    @Column(name = "rationale_text", nullable = false, columnDefinition = "TEXT")
    private String rationaleText;

    @Column(name = "generated_at", nullable = false)
    private Instant generatedAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "reviewed_by")
    private User reviewedBy;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "final_decision")
    private RecommendationType finalDecision;

    @Column(name = "decided_at")
    private Instant decidedAt;

    @PrePersist
    void prePersist() {
        if (generatedAt == null) {
            generatedAt = Instant.now();
        }
    }
}
