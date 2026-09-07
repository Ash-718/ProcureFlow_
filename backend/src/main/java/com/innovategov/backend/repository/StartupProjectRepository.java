package com.innovategov.backend.repository;

import com.innovategov.backend.entity.StartupProject;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface StartupProjectRepository extends JpaRepository<StartupProject, UUID> {
    List<StartupProject> findByStartupId(UUID startupId);
}
