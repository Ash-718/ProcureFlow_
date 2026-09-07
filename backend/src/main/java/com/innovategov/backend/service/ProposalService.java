package com.innovategov.backend.service;

import com.innovategov.backend.dto.proposal.ProposalCreateRequest;
import com.innovategov.backend.dto.proposal.ProposalResponse;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.ChallengeStatus;
import com.innovategov.backend.entity.enums.NotificationType;
import com.innovategov.backend.entity.enums.ProposalStatus;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProposalService {

    private final ProposalRepository proposalRepository;
    private final ChallengeRepository challengeRepository;
    private final StartupRepository startupRepository;
    private final GovernmentDepartmentRepository departmentRepository;
    private final AuditService auditService;
    private final NotificationService notificationService;

    @Transactional
    public ProposalResponse submit(User actor, UUID challengeId, ProposalCreateRequest request) {
        Startup startup = startupRepository.findByUserId(actor.getId())
                .orElseThrow(() -> ApiException.forbidden("Only a startup account can submit proposals"));
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));

        if (challenge.getStatus() == ChallengeStatus.DRAFT || challenge.getStatus() == ChallengeStatus.CLOSED) {
            throw ApiException.conflict("This challenge is not currently accepting proposals");
        }
        if (proposalRepository.findByChallengeIdAndStartupId(challengeId, startup.getId()).isPresent()) {
            throw ApiException.conflict("You have already submitted a proposal for this challenge");
        }

        Proposal proposal = new Proposal();
        proposal.setChallenge(challenge);
        proposal.setStartup(startup);
        proposal.setSummary(request.getSummary());
        proposal.setProposedApproach(request.getProposedApproach());
        proposal.setCostEstimate(request.getCostEstimate());
        proposal.setTimelineEstimateDays(request.getTimelineEstimateDays());
        proposal.setStatus(ProposalStatus.SUBMITTED);
        proposalRepository.save(proposal);

        auditService.log(actor, "SUBMIT", "Proposal", proposal.getId(), null);
        notificationService.notify(challenge.getDepartment().getUser(), NotificationType.PROPOSAL_SUBMITTED,
                startup.getCompanyName() + " submitted a proposal for \"" + challenge.getTitle() + "\".");

        return new ProposalResponse(proposal);
    }

    @Transactional
    public ProposalResponse updateStatus(User actor, UUID proposalId, ProposalStatus newStatus) {
        Proposal proposal = proposalRepository.findById(proposalId)
                .orElseThrow(() -> ApiException.notFound("Proposal not found"));
        assertGovernmentOwnerOrAdmin(actor, proposal.getChallenge());

        proposal.setStatus(newStatus);
        proposalRepository.save(proposal);

        auditService.log(actor, "STATUS_CHANGE", "Proposal", proposal.getId(),
                java.util.Map.of("newStatus", newStatus.name()));
        notificationService.notify(proposal.getStartup().getUser(), NotificationType.PROPOSAL_STATUS_CHANGE,
                "Your proposal for \"" + proposal.getChallenge().getTitle() + "\" is now " + newStatus + ".");

        return new ProposalResponse(proposal);
    }

    public List<ProposalResponse> listForChallenge(User actor, UUID challengeId) {
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));
        RoleName role = actor.getRole().getName();
        if (role == RoleName.GOVERNMENT || role == RoleName.ADMIN) {
            assertGovernmentOwnerOrAdmin(actor, challenge);
        }
        // EXPERT: any expert may view proposals to evaluate — the schema has no
        // separate assignment table, so "assigned" is treated as "available to any expert".
        return proposalRepository.findByChallengeId(challengeId).stream().map(ProposalResponse::new).toList();
    }

    public List<ProposalResponse> listMine(User actor) {
        Startup startup = startupRepository.findByUserId(actor.getId())
                .orElseThrow(() -> ApiException.forbidden("Only a startup account has proposals"));
        return proposalRepository.findByStartupId(startup.getId()).stream().map(ProposalResponse::new).toList();
    }

    public List<ProposalResponse> listAllForExpertQueue() {
        return proposalRepository.findAll().stream()
                .filter(p -> p.getStatus() == ProposalStatus.SUBMITTED || p.getStatus() == ProposalStatus.UNDER_REVIEW)
                .map(ProposalResponse::new).toList();
    }

    public Proposal getEntity(UUID proposalId) {
        return proposalRepository.findById(proposalId)
                .orElseThrow(() -> ApiException.notFound("Proposal not found"));
    }

    public ProposalResponse getById(User actor, UUID proposalId) {
        Proposal proposal = getEntity(proposalId);
        RoleName role = actor.getRole().getName();
        if (role == RoleName.ADMIN || role == RoleName.EXPERT) {
            return new ProposalResponse(proposal);
        }
        if (role == RoleName.GOVERNMENT) {
            assertGovernmentOwnerOrAdmin(actor, proposal.getChallenge());
            return new ProposalResponse(proposal);
        }
        // STARTUP: only the owner may view it
        Startup startup = startupRepository.findByUserId(actor.getId()).orElse(null);
        if (startup != null && proposal.getStartup().getId().equals(startup.getId())) {
            return new ProposalResponse(proposal);
        }
        throw ApiException.forbidden("You do not have access to this proposal");
    }

    void assertGovernmentOwnerOrAdmin(User actor, Challenge challenge) {
        if (actor.getRole().getName() == RoleName.ADMIN) return;
        GovernmentDepartment department = departmentRepository.findByUserId(actor.getId()).orElse(null);
        if (department == null || !department.getId().equals(challenge.getDepartment().getId())) {
            throw ApiException.forbidden("You do not have access to this challenge's proposals");
        }
    }
}
