package com.innovategov.backend.entity;

import com.innovategov.backend.entity.enums.ClientType;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "startup_projects")
@Getter
@Setter
@NoArgsConstructor
public class StartupProject {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "startup_id", nullable = false)
    private Startup startup;

    @Column(nullable = false)
    private String title;

    @Column(nullable = false)
    private String domain;

    @Column(name = "technology_stack")
    private String technologyStack;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "client_type", nullable = false)
    private ClientType clientType = ClientType.PRIVATE;

    @Column(name = "outcome_summary", columnDefinition = "TEXT")
    private String outcomeSummary;

    private Integer year;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        createdAt = Instant.now();
    }
}
