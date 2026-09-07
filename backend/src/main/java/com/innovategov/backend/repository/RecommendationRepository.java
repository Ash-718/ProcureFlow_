package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Recommendation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface RecommendationRepository extends JpaRepository<Recommendation, UUID> {
    Optional<Recommendation> findByPilotId(UUID pilotId);
}
