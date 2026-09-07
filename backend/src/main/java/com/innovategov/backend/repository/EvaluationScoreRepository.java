package com.innovategov.backend.repository;

import com.innovategov.backend.entity.EvaluationScore;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface EvaluationScoreRepository extends JpaRepository<EvaluationScore, UUID> {
    List<EvaluationScore> findByEvaluationId(UUID evaluationId);
}
