package com.innovategov.backend.entity;

import com.innovategov.backend.entity.enums.RequirementType;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.UUID;

@Entity
@Table(name = "challenge_requirements")
@Getter
@Setter
@NoArgsConstructor
public class ChallengeRequirement {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "challenge_id", nullable = false)
    private Challenge challenge;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "requirement_type", nullable = false)
    private RequirementType requirementType;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(name = "is_mandatory", nullable = false)
    private boolean mandatory = true;
}
