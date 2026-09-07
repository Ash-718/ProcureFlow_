package com.innovategov.backend.service;

import com.innovategov.backend.dto.pilot.RecommendationResponse;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.MilestoneStatus;
import com.innovategov.backend.entity.enums.NotificationType;
import com.innovategov.backend.entity.enums.RecommendationType;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.*;
import com.innovategov.backend.util.AfterCommitRunner;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.RoundingMode;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional(readOnly = true)
public class RecommendationService {

    private final KpiRepository kpiRepository;
    private final KpiResultRepository kpiResultRepository;
    private final PilotMilestoneRepository milestoneRepository;
    private final RecommendationRepository recommendationRepository;
    private final PilotKnowledgeBaseRepository knowledgeBaseRepository;
    private final GovernmentDepartmentRepository departmentRepository;
    private final AiServiceClient aiServiceClient;
    private final AuditService auditService;
    private final AfterCommitRunner afterCommitRunner;
    private final NotificationService notificationService;

    @Transactional
    public Recommendation generateForPilot(Pilot pilot) {
        List<Kpi> kpis = kpiRepository.findByPilotId(pilot.getId());
        List<RecommendationCalculator.KpiAssessment> kpiAssessments = kpis.stream()
                .map(k -> new RecommendationCalculator.KpiAssessment(
                        k.getKpiName(),
                        k.getTargetValue(),
                        kpiResultRepository.findByKpiIdOrderByRecordedAtDesc(k.getId()).stream()
                                .findFirst().map(KpiResult::getRecordedValue).orElse(null)))
                .toList();

        List<PilotMilestone> milestones = milestoneRepository.findByPilotId(pilot.getId());
        List<RecommendationCalculator.MilestoneAssessment> milestoneAssessments = milestones.stream()
                .map(m -> new RecommendationCalculator.MilestoneAssessment(m.getStatus() == MilestoneStatus.DELAYED))
                .toList();

        RecommendationCalculator.ScoreResult score = RecommendationCalculator.compute(kpiAssessments, milestoneAssessments);
        RecommendationType recommendationType = RecommendationType.valueOf(score.recommendation());

        Recommendation recommendation = recommendationRepository.findByPilotId(pilot.getId()).orElseGet(Recommendation::new);
        recommendation.setPilot(pilot);
        recommendation.setRecommendation(recommendationType);
        recommendation.setCostScore(score.costScore());
        recommendation.setPerformanceScore(score.performanceScore());
        recommendation.setImpactScore(score.impactScore());
        recommendation.setRationaleText(buildRationale(kpis, kpiAssessments, milestones, score));
        recommendation.setGeneratedAt(Instant.now());
        recommendationRepository.save(recommendation);

        createOrUpdateKnowledgeBaseEntry(pilot, recommendationType, null);

        notificationService.notify(pilot.getChallenge().getDepartment().getUser(), NotificationType.RECOMMENDATION_READY,
                "AI recommendation for the \"" + pilot.getChallenge().getTitle() + "\" pilot: " + recommendationType + ".");

        return recommendation;
    }

    @Transactional
    public RecommendationResponse recordFinalDecision(User actor, UUID pilotId, RecommendationType finalDecision) {
        Recommendation recommendation = recommendationRepository.findByPilotId(pilotId)
                .orElseThrow(() -> ApiException.notFound("No recommendation has been generated for this pilot yet"));

        if (actor.getRole().getName() != RoleName.ADMIN) {
            var department = departmentRepository.findByUserId(actor.getId()).orElse(null);
            if (department == null || !department.getId().equals(recommendation.getPilot().getChallenge().getDepartment().getId())) {
                throw ApiException.forbidden("You do not have access to decide on this pilot's recommendation");
            }
        }

        recommendation.setFinalDecision(finalDecision);
        recommendation.setReviewedBy(actor);
        recommendation.setDecidedAt(Instant.now());
        recommendationRepository.save(recommendation);

        createOrUpdateKnowledgeBaseEntry(recommendation.getPilot(), null, finalDecision);

        auditService.log(actor, "FINAL_DECISION", "Recommendation", recommendation.getId(),
                java.util.Map.of("finalDecision", finalDecision.name()));

        return new RecommendationResponse(recommendation);
    }

    public RecommendationResponse getByPilotId(UUID pilotId) {
        Recommendation recommendation = recommendationRepository.findByPilotId(pilotId)
                .orElseThrow(() -> ApiException.notFound("No recommendation has been generated for this pilot yet"));
        return new RecommendationResponse(recommendation);
    }

    private void createOrUpdateKnowledgeBaseEntry(Pilot pilot, RecommendationType aiRecommendation, RecommendationType finalDecision) {
        PilotKnowledgeBase kb = knowledgeBaseRepository.findAll().stream()
                .filter(k -> k.getPilot().getId().equals(pilot.getId()))
                .findFirst()
                .orElseGet(PilotKnowledgeBase::new);

        Challenge challenge = pilot.getChallenge();
        RecommendationType effective = finalDecision != null ? finalDecision : aiRecommendation;

        kb.setPilot(pilot);
        kb.setDomain(challenge.getDomain());
        kb.setTechnologyTags(splitTechnologies(challenge.getDesiredTechnology()));
        kb.setDepartment(challenge.getDepartment());
        kb.setOutcomeSummary(recommendationRepository.findByPilotId(pilot.getId())
                .map(Recommendation::getRationaleText).orElse(null));
        if (effective != null) {
            kb.setSuccess(effective == RecommendationType.SCALE ? Boolean.TRUE
                    : effective == RecommendationType.REJECT ? Boolean.FALSE : null);
        }
        kb.setSearchableText(challenge.getTitle() + " " + challenge.getDomain() + " " +
                String.join(" ", kb.getTechnologyTags()) + " " + pilot.getStartup().getCompanyName() + " " +
                challenge.getDepartment().getDepartmentName());

        knowledgeBaseRepository.save(kb);

        UUID kbId = kb.getId();
        afterCommitRunner.run(() -> {
            try {
                aiServiceClient.triggerKnowledgeBaseEmbedding(kbId);
            } catch (Exception ex) {
                log.warn("Could not eagerly compute embedding for knowledge base entry {}: {}", kbId, ex.getMessage());
            }
        });
    }

    private String[] splitTechnologies(String desiredTechnology) {
        if (desiredTechnology == null || desiredTechnology.isBlank()) return new String[0];
        return Arrays.stream(desiredTechnology.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toArray(String[]::new);
    }

    private String buildRationale(
            List<Kpi> kpis,
            List<RecommendationCalculator.KpiAssessment> assessments,
            List<PilotMilestone> milestones,
            RecommendationCalculator.ScoreResult score
    ) {
        StringBuilder sb = new StringBuilder();
        sb.append("Overall score ").append(score.overall().setScale(2, RoundingMode.HALF_UP))
                .append("/1.00 (cost ").append(score.costScore().setScale(2, RoundingMode.HALF_UP))
                .append(", performance ").append(score.performanceScore().setScale(2, RoundingMode.HALF_UP))
                .append(", impact ").append(score.impactScore().setScale(2, RoundingMode.HALF_UP)).append("). ");

        for (int i = 0; i < kpis.size(); i++) {
            var a = assessments.get(i);
            var ratio = RecommendationCalculator.achievementRatio(a);
            if (ratio == null) {
                sb.append(a.kpiName()).append(": no result recorded yet. ");
            } else {
                boolean met = ratio.compareTo(java.math.BigDecimal.ONE) >= 0;
                sb.append(a.kpiName()).append(" ").append(met ? "met or exceeded" : "fell short of")
                        .append(" its target (recorded ").append(a.recordedValue())
                        .append(" vs target ").append(a.targetValue()).append("). ");
            }
        }

        long delayed = milestones.stream().filter(m -> m.getStatus() == MilestoneStatus.DELAYED).count();
        if (delayed > 0) {
            sb.append(delayed).append(" of ").append(milestones.size()).append(" milestone(s) were delayed. ");
        } else if (!milestones.isEmpty()) {
            sb.append("All milestones were delivered on schedule. ");
        }

        sb.append("Recommendation: ").append(score.recommendation()).append(".");
        return sb.toString();
    }
}
