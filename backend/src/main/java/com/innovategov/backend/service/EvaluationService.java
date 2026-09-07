package com.innovategov.backend.service;

import com.innovategov.backend.dto.evaluation.EvaluationCriterionDto;
import com.innovategov.backend.dto.evaluation.EvaluationResponse;
import com.innovategov.backend.dto.evaluation.EvaluationScoreRequest;
import com.innovategov.backend.dto.evaluation.EvaluationSubmitRequest;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.NotificationType;
import com.innovategov.backend.entity.enums.ProposalStatus;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional(readOnly = true)
public class EvaluationService {

    private final ProposalRepository proposalRepository;
    private final EvaluationCriterionRepository criterionRepository;
    private final EvaluationRepository evaluationRepository;
    private final EvaluationScoreRepository evaluationScoreRepository;
    private final AiServiceClient aiServiceClient;
    private final AuditService auditService;
    private final NotificationService notificationService;

    public List<EvaluationCriterionDto> getCriteriaForProposal(UUID proposalId) {
        Proposal proposal = mustFindProposal(proposalId);
        return criterionRepository.findByChallengeId(proposal.getChallenge().getId()).stream()
                .map(EvaluationCriterionDto::new).toList();
    }

    public String getAiAnalysis(UUID proposalId) {
        mustFindProposal(proposalId);
        return aiServiceClient.getProposalAnalysis(proposalId);
    }

    @Transactional
    public EvaluationResponse submit(User expert, UUID proposalId, EvaluationSubmitRequest request) {
        Proposal proposal = mustFindProposal(proposalId);
        List<EvaluationCriterion> criteria = criterionRepository.findByChallengeId(proposal.getChallenge().getId());

        Evaluation evaluation = evaluationRepository.findByProposalIdAndExpertId(proposalId, expert.getId())
                .orElseGet(Evaluation::new);
        evaluation.setProposal(proposal);
        evaluation.setExpert(expert);
        evaluation.setComments(request.getComments());

        String aiSummary = safeAiSummary(proposalId);
        evaluation.setAiAssistSummary(aiSummary);
        evaluation.setSubmittedAt(Instant.now());
        evaluationRepository.save(evaluation);

        evaluationScoreRepository.deleteAll(evaluationScoreRepository.findByEvaluationId(evaluation.getId()));

        List<EvaluationScoring.WeightedScore> weightedScores = new java.util.ArrayList<>();
        for (EvaluationScoreRequest scoreReq : request.getScores()) {
            EvaluationCriterion criterion = criteria.stream()
                    .filter(c -> c.getId().equals(scoreReq.getCriterionId()))
                    .findFirst()
                    .orElseThrow(() -> ApiException.badRequest("Unknown criterion for this challenge: " + scoreReq.getCriterionId()));

            EvaluationScore score = new EvaluationScore();
            score.setEvaluation(evaluation);
            score.setCriterion(criterion);
            score.setScore(scoreReq.getScore());
            score.setRemarks(scoreReq.getRemarks());
            evaluationScoreRepository.save(score);

            weightedScores.add(new EvaluationScoring.WeightedScore(scoreReq.getScore(), criterion.getWeight()));
        }

        BigDecimal totalScore = EvaluationScoring.weightedTotal(weightedScores);
        evaluation.setTotalScore(totalScore);
        evaluationRepository.save(evaluation);

        if (proposal.getStatus() == ProposalStatus.SUBMITTED) {
            proposal.setStatus(ProposalStatus.UNDER_REVIEW);
            proposalRepository.save(proposal);
        }

        auditService.log(expert, "SUBMIT_EVALUATION", "Proposal", proposalId,
                java.util.Map.of("totalScore", totalScore.toString()));
        notificationService.notify(proposal.getChallenge().getDepartment().getUser(), NotificationType.EVALUATION_SUBMITTED,
                "Expert " + expert.getFullName() + " scored " + proposal.getStartup().getCompanyName() +
                        "'s proposal " + totalScore + "/10 for \"" + proposal.getChallenge().getTitle() + "\".");

        return new EvaluationResponse(evaluation, evaluationScoreRepository.findByEvaluationId(evaluation.getId()));
    }

    private String safeAiSummary(UUID proposalId) {
        try {
            return aiServiceClient.getProposalAnalysis(proposalId);
        } catch (Exception ex) {
            log.warn("AI analysis unavailable while submitting evaluation for proposal {}: {}", proposalId, ex.getMessage());
            return "AI-assisted analysis was unavailable at submission time.";
        }
    }

    private Proposal mustFindProposal(UUID proposalId) {
        return proposalRepository.findById(proposalId)
                .orElseThrow(() -> ApiException.notFound("Proposal not found"));
    }
}
