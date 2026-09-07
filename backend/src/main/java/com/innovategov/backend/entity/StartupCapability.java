package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "startup_capabilities")
@Getter
@Setter
@NoArgsConstructor
public class StartupCapability {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "startup_id", nullable = false)
    private Startup startup;

    @Column(name = "technology_tag", nullable = false)
    private String technologyTag;

    @Column(name = "domain_tag", nullable = false)
    private String domainTag;

    @Column(name = "proficiency_level", nullable = false)
    private Integer proficiencyLevel = 3;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        createdAt = Instant.now();
    }
}
