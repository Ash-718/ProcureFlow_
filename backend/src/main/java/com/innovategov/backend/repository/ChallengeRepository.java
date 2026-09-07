package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Challenge;
import com.innovategov.backend.entity.enums.ChallengeStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ChallengeRepository extends JpaRepository<Challenge, UUID> {
    List<Challenge> findByDepartmentId(UUID departmentId);
    List<Challenge> findByStatusIn(List<ChallengeStatus> statuses);
    List<Challenge> findByStatus(ChallengeStatus status);
}
