package com.innovategov.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.innovategov.backend.dto.ai.AiMatchResponse;
import com.innovategov.backend.dto.matching.MatchResultDto;
import com.innovategov.backend.entity.Challenge;
import com.innovategov.backend.entity.GovernmentDepartment;
import com.innovategov.backend.entity.MatchResult;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.entity.enums.NotificationType;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.ChallengeRepository;
import com.innovategov.backend.repository.GovernmentDepartmentRepository;
import com.innovategov.backend.repository.MatchResultRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MatchingService {

    private final ChallengeRepository challengeRepository;
    private final GovernmentDepartmentRepository departmentRepository;
    private final MatchResultRepository matchResultRepository;
    private final AiServiceClient aiServiceClient;
    private final AuditService auditService;
    private final NotificationService notificationService;
    private final ObjectMapper objectMapper;

    public AiMatchResponse runMatching(User actor, UUID challengeId) {
        Challenge challenge = mustAccess(actor, challengeId);

        AiMatchResponse response = aiServiceClient.runMatching(challengeId);

        auditService.log(actor, "RUN_MATCHING", "Challenge", challengeId,
                java.util.Map.of("candidates_considered", response.getTotalCandidatesConsidered()));

        notificationService.notify(challenge.getDepartment().getUser(), NotificationType.MATCH_READY,
                "AI matching finished for \"" + challenge.getTitle() + "\" — " +
                        response.getResults().size() + " candidate(s) ranked.");

        return response;
    }

    public List<MatchResultDto> getResults(User actor, UUID challengeId) {
        mustAccess(actor, challengeId);
        List<MatchResult> results = matchResultRepository.findByChallengeIdOrderByRankAsc(challengeId);
        return results.stream().map(r -> new MatchResultDto(r, parseExplanation(r.getExplanationJson()))).toList();
    }

    private JsonNode parseExplanation(String json) {
        try {
            return json == null ? null : objectMapper.readTree(json);
        } catch (Exception e) {
            return null;
        }
    }

    private Challenge mustAccess(User actor, UUID challengeId) {
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));

        if (actor.getRole().getName() == RoleName.ADMIN) {
            return challenge;
        }
        if (actor.getRole().getName() == RoleName.GOVERNMENT) {
            GovernmentDepartment department = departmentRepository.findByUserId(actor.getId()).orElse(null);
            if (department != null && department.getId().equals(challenge.getDepartment().getId())) {
                return challenge;
            }
        }
        throw ApiException.forbidden("You do not have access to matching results for this challenge");
    }
}
