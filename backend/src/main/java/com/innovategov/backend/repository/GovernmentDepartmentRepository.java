package com.innovategov.backend.repository;

import com.innovategov.backend.entity.GovernmentDepartment;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface GovernmentDepartmentRepository extends JpaRepository<GovernmentDepartment, UUID> {
    Optional<GovernmentDepartment> findByUserId(UUID userId);
}
