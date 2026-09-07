package com.innovategov.backend.repository;

import com.innovategov.backend.entity.StartupCapability;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface StartupCapabilityRepository extends JpaRepository<StartupCapability, UUID> {
    List<StartupCapability> findByStartupId(UUID startupId);
    void deleteByStartupIdAndId(UUID startupId, UUID id);
}
