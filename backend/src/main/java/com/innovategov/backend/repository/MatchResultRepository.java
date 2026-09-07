package com.innovategov.backend.repository;

import com.innovategov.backend.entity.MatchResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface MatchResultRepository extends JpaRepository<MatchResult, UUID> {
    List<MatchResult> findByChallengeIdOrderByRankAsc(UUID challengeId);
    List<MatchResult> findByStartupIdOrderByOverallScoreDesc(UUID startupId);
}
