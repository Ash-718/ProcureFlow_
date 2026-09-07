package com.innovategov.backend.repository;

import com.innovategov.backend.entity.EvaluationCriterion;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface EvaluationCriterionRepository extends JpaRepository<EvaluationCriterion, UUID> {
    List<EvaluationCriterion> findByChallengeId(UUID challengeId);
}
