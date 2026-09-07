package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(name = "challenge_kpis")
@Getter
@Setter
@NoArgsConstructor
public class ChallengeKpi {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "challenge_id", nullable = false)
    private Challenge challenge;

    @Column(name = "kpi_name", nullable = false)
    private String kpiName;

    @Column(name = "target_value")
    private BigDecimal targetValue;

    private String unit;

    @Column(nullable = false)
    private BigDecimal weight = BigDecimal.ONE;
}
