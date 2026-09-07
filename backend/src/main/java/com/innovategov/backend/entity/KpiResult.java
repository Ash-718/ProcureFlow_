package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "kpi_results")
@Getter
@Setter
@NoArgsConstructor
public class KpiResult {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "kpi_id", nullable = false)
    private Kpi kpi;

    @Column(name = "recorded_value", nullable = false)
    private BigDecimal recordedValue;

    @Column(name = "recorded_at", nullable = false)
    private Instant recordedAt;

    @Column(columnDefinition = "TEXT")
    private String notes;

    @PrePersist
    void prePersist() {
        if (recordedAt == null) {
            recordedAt = Instant.now();
        }
    }
}
