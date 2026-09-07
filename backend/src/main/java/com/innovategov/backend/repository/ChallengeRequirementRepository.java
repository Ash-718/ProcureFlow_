package com.innovategov.backend.repository;

import com.innovategov.backend.entity.ChallengeRequirement;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ChallengeRequirementRepository extends JpaRepository<ChallengeRequirement, UUID> {
    List<ChallengeRequirement> findByChallengeId(UUID challengeId);
}
