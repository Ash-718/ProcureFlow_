package com.innovategov.backend.repository;

import com.innovategov.backend.entity.PilotMilestone;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface PilotMilestoneRepository extends JpaRepository<PilotMilestone, UUID> {
    List<PilotMilestone> findByPilotId(UUID pilotId);
}
