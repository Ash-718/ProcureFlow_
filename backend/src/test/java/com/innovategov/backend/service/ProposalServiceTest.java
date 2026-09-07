package com.innovategov.backend.service;

import com.innovategov.backend.dto.proposal.ProposalCreateRequest;
import com.innovategov.backend.dto.proposal.ProposalResponse;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.ChallengeStatus;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.when;

/**
 * Section 20: "proposal submission" business-rule tests. Repositories are
 * mocked so these run without a database — the RBAC/lifecycle rules under
 * test live entirely in ProposalService itself.
 */
@ExtendWith(MockitoExtension.class)
class ProposalServiceTest {

    @Mock private ProposalRepository proposalRepository;
    @Mock private ChallengeRepository challengeRepository;
    @Mock private StartupRepository startupRepository;
    @Mock private GovernmentDepartmentRepository departmentRepository;
    @Mock private AuditService auditService;
    @Mock private NotificationService notificationService;

    @InjectMocks
    private ProposalService proposalService;

    private User startupUser;
    private Startup startup;
    private Challenge publishedChallenge;
    private UUID challengeId;

    @BeforeEach
    void setUp() {
        Role role = new Role();
        role.setName(RoleName.STARTUP);

        startupUser = new User();
        startupUser.setId(UUID.randomUUID());
        startupUser.setRole(role);

        startup = new Startup();
        startup.setId(UUID.randomUUID());
        startup.setUser(startupUser);
        startup.setCompanyName("RoadSense AI");

        GovernmentDepartment department = new GovernmentDepartment();
        department.setId(UUID.randomUUID());
        department.setDepartmentName("Urban Development Department");

        challengeId = UUID.randomUUID();
        publishedChallenge = new Challenge();
        publishedChallenge.setId(challengeId);
        publishedChallenge.setTitle("AI-Based Pothole Detection");
        publishedChallenge.setStatus(ChallengeStatus.PUBLISHED);
        publishedChallenge.setDepartment(department);

        lenient().when(startupRepository.findByUserId(startupUser.getId())).thenReturn(Optional.of(startup));
        lenient().when(challengeRepository.findById(challengeId)).thenReturn(Optional.of(publishedChallenge));
        lenient().when(proposalRepository.save(any(Proposal.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    private ProposalCreateRequest validRequest() {
        ProposalCreateRequest request = new ProposalCreateRequest();
        request.setSummary("Deploy our proven CV pipeline.");
        return request;
    }

    @Test
    void submit_succeedsForPublishedChallengeWithNoExistingProposal() {
        when(proposalRepository.findByChallengeIdAndStartupId(challengeId, startup.getId()))
                .thenReturn(Optional.empty());

        ProposalResponse response = proposalService.submit(startupUser, challengeId, validRequest());

        assertThat(response.getCompanyName()).isEqualTo("RoadSense AI");
        assertThat(response.getChallengeTitle()).isEqualTo("AI-Based Pothole Detection");
        assertThat(response.getStatus()).isEqualTo("SUBMITTED");
    }

    @Test
    void submit_rejectsASecondProposalFromTheSameStartupToTheSameChallenge() {
        Proposal existing = new Proposal();
        existing.setId(UUID.randomUUID());
        when(proposalRepository.findByChallengeIdAndStartupId(challengeId, startup.getId()))
                .thenReturn(Optional.of(existing));

        assertThatThrownBy(() -> proposalService.submit(startupUser, challengeId, validRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("already submitted");
    }

    @Test
    void submit_rejectsAProposalToADraftChallenge() {
        publishedChallenge.setStatus(ChallengeStatus.DRAFT);

        assertThatThrownBy(() -> proposalService.submit(startupUser, challengeId, validRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not currently accepting proposals");
    }

    @Test
    void submit_rejectsAProposalToAClosedChallenge() {
        publishedChallenge.setStatus(ChallengeStatus.CLOSED);

        assertThatThrownBy(() -> proposalService.submit(startupUser, challengeId, validRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not currently accepting proposals");
    }

    @Test
    void submit_acceptsAProposalToAChallengeInMatchingOrShortlistedOrPilotStatus() {
        when(proposalRepository.findByChallengeIdAndStartupId(challengeId, startup.getId()))
                .thenReturn(Optional.empty());

        for (ChallengeStatus status : new ChallengeStatus[]{
                ChallengeStatus.MATCHING, ChallengeStatus.SHORTLISTED, ChallengeStatus.PILOT}) {
            publishedChallenge.setStatus(status);
            ProposalResponse response = proposalService.submit(startupUser, challengeId, validRequest());
            assertThat(response.getStatus()).isEqualTo("SUBMITTED");
        }
    }

    @Test
    void submit_rejectsANonStartupAccount() {
        Role govRole = new Role();
        govRole.setName(RoleName.GOVERNMENT);
        User govUser = new User();
        govUser.setId(UUID.randomUUID());
        govUser.setRole(govRole);
        when(startupRepository.findByUserId(govUser.getId())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> proposalService.submit(govUser, challengeId, validRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("Only a startup account");
    }

    @Test
    void submit_rejectsWhenChallengeDoesNotExist() {
        UUID missingId = UUID.randomUUID();
        when(challengeRepository.findById(missingId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> proposalService.submit(startupUser, missingId, validRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("Challenge not found");
    }
}
