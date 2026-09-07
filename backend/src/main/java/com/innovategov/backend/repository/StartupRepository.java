package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Startup;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface StartupRepository extends JpaRepository<Startup, UUID> {
    Optional<Startup> findByUserId(UUID userId);
}
