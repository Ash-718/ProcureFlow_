package com.innovategov.backend.repository;

import com.innovategov.backend.entity.Proposal;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProposalRepository extends JpaRepository<Proposal, UUID> {
    List<Proposal> findByChallengeId(UUID challengeId);
    List<Proposal> findByStartupId(UUID startupId);
    Optional<Proposal> findByChallengeIdAndStartupId(UUID challengeId, UUID startupId);
    List<Proposal> findByChallengeIdIn(List<UUID> challengeIds);
}
