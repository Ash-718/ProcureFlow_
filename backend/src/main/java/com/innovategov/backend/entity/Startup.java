package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "startups")
@Getter
@Setter
@NoArgsConstructor
public class Startup {

    @Id
    @GeneratedValue
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false, unique = true)
    private User user;

    @Column(name = "company_name", nullable = false)
    private String companyName;

    @Column(name = "dpiit_number")
    private String dpiitNumber;

    @Column(name = "founded_year")
    private Integer foundedYear;

    @Column(name = "team_size")
    private Integer teamSize;

    private String city;
    private String state;

    @Column(name = "readiness_score", nullable = false)
    private BigDecimal readinessScore = BigDecimal.valueOf(50);

    @Column(columnDefinition = "TEXT")
    private String description;

    // Embeddings are written exclusively by the AI service; the backend never
    // computes or interprets vector values, only triggers computation via HTTP.
    @Column(name = "embedding_model")
    private String embeddingModel;

    @Column(name = "embedding_updated_at")
    private Instant embeddingUpdatedAt;

    @OneToMany(mappedBy = "startup", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<StartupCapability> capabilities = new ArrayList<>();

    @OneToMany(mappedBy = "startup", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<StartupProject> projects = new ArrayList<>();

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
