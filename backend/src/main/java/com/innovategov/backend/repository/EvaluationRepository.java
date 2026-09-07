package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Evaluation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface EvaluationRepository extends JpaRepository<Evaluation, UUID> {
    List<Evaluation> findByExpertId(UUID expertId);
    List<Evaluation> findByProposalId(UUID proposalId);
    Optional<Evaluation> findByProposalIdAndExpertId(UUID proposalId, UUID expertId);
}
