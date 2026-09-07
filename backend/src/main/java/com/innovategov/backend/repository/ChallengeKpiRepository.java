package com.innovategov.backend.repository;

import com.innovategov.backend.entity.ChallengeKpi;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ChallengeKpiRepository extends JpaRepository<ChallengeKpi, UUID> {
    List<ChallengeKpi> findByChallengeId(UUID challengeId);
}
