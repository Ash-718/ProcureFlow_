package com.innovategov.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "pilot_knowledge_base")
@Getter
@Setter
@NoArgsConstructor
public class PilotKnowledgeBase {

    @Id
    @GeneratedValue
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "pilot_id", nullable = false, unique = true)
    private Pilot pilot;

    @Column(nullable = false)
    private String domain;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "technology_tags", nullable = false, columnDefinition = "text[]")
    private String[] technologyTags = new String[0];

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "department_id", nullable = false)
    private GovernmentDepartment department;

    @Column(name = "outcome_summary", columnDefinition = "TEXT")
    private String outcomeSummary;

    private Boolean success;

    @Column(name = "searchable_text", nullable = false, columnDefinition = "TEXT")
    private String searchableText;

    @Column(name = "embedding_model")
    private String embeddingModel;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        createdAt = Instant.now();
    }
}
