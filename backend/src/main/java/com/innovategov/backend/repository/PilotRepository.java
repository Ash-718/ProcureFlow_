package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Pilot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface PilotRepository extends JpaRepository<Pilot, UUID> {
    List<Pilot> findByChallengeIdIn(List<UUID> challengeIds);
    List<Pilot> findByStartupId(UUID startupId);
}
