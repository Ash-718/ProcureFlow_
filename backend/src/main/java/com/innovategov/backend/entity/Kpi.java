package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "kpis")
@Getter
@Setter
@NoArgsConstructor
public class Kpi {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "pilot_id", nullable = false)
    private Pilot pilot;

    @Column(name = "kpi_name", nullable = false)
    private String kpiName;

    @Column(name = "target_value")
    private BigDecimal targetValue;

    private String unit;

    @OneToMany(mappedBy = "kpi", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<KpiResult> results = new ArrayList<>();
}
