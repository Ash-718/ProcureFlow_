package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(name = "evaluation_criteria")
@Getter
@Setter
@NoArgsConstructor
public class EvaluationCriterion {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "challenge_id", nullable = false)
    private Challenge challenge;

    @Column(name = "criterion_name", nullable = false)
    private String criterionName;

    @Column(name = "max_score", nullable = false)
    private BigDecimal maxScore = BigDecimal.TEN;

    @Column(nullable = false)
    private BigDecimal weight = BigDecimal.ONE;
}
