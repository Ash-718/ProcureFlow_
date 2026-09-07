package com.innovategov.backend.service;

import com.innovategov.backend.dto.challenge.ChallengeCreateRequest;
import com.innovategov.backend.dto.challenge.ChallengeResponse;
import com.innovategov.backend.dto.challenge.KpiRequest;
import com.innovategov.backend.dto.challenge.RequirementRequest;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.ChallengeStatus;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.*;
import com.innovategov.backend.util.AfterCommitRunner;
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
public class ChallengeService {

    private final ChallengeRepository challengeRepository;
    private final ChallengeRequirementRepository requirementRepository;
    private final ChallengeKpiRepository kpiRepository;
    private final EvaluationCriterionRepository evaluationCriterionRepository;
    private final GovernmentDepartmentRepository departmentRepository;
    private final AiServiceClient aiServiceClient;
    private final AfterCommitRunner afterCommitRunner;
    private final AuditService auditService;

    @Transactional
    public ChallengeResponse create(User actor, ChallengeCreateRequest request) {
        GovernmentDepartment department = departmentRepository.findByUserId(actor.getId())
                .orElseThrow(() -> ApiException.forbidden("Only a government department account can create challenges"));

        Challenge challenge = new Challenge();
        challenge.setDepartment(department);
        applyFields(challenge, request);
        challenge.setStatus(ChallengeStatus.DRAFT);
        challengeRepository.save(challenge);

        saveRequirementsAndKpis(challenge, request);

        auditService.log(actor, "CREATE", "Challenge", challenge.getId(), null);
        return toResponse(challenge);
    }

    @Transactional
    public ChallengeResponse update(User actor, UUID challengeId, ChallengeCreateRequest request) {
        Challenge challenge = mustOwnAsDraft(actor, challengeId);
        applyFields(challenge, request);
        challengeRepository.save(challenge);

        requirementRepository.deleteAll(requirementRepository.findByChallengeId(challengeId));
        kpiRepository.deleteAll(kpiRepository.findByChallengeId(challengeId));
        saveRequirementsAndKpis(challenge, request);

        auditService.log(actor, "UPDATE", "Challenge", challenge.getId(), null);
        return toResponse(challenge);
    }

    @Transactional
    public ChallengeResponse publish(User actor, UUID challengeId) {
        Challenge challenge = mustOwnAsDraft(actor, challengeId);

        if (challenge.getRequirements().isEmpty() && requirementRepository.findByChallengeId(challengeId).isEmpty()) {
            throw ApiException.badRequest("Add at least one eligibility/technical requirement before publishing");
        }

        challenge.setStatus(ChallengeStatus.PUBLISHED);
        challenge.setPublishedAt(Instant.now());
        challengeRepository.save(challenge);

        ensureDefaultEvaluationCriteria(challenge);

        afterCommitRunner.run(() -> {
            try {
                aiServiceClient.triggerChallengeEmbedding(challengeId);
            } catch (Exception ex) {
                log.warn("Could not eagerly compute embedding for challenge {}: {}", challengeId, ex.getMessage());
            }
        });

        auditService.log(actor, "PUBLISH", "Challenge", challenge.getId(), null);
        return toResponse(challenge);
    }

    public ChallengeResponse getById(User actor, UUID challengeId) {
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));
        assertVisible(actor, challenge);
        return toResponse(challenge);
    }

    public List<ChallengeResponse> listForActor(User actor) {
        RoleName role = actor.getRole().getName();
        List<Challenge> challenges;
        if (role == RoleName.ADMIN) {
            challenges = challengeRepository.findAll();
        } else if (role == RoleName.GOVERNMENT) {
            GovernmentDepartment department = departmentRepository.findByUserId(actor.getId())
                    .orElseThrow(() -> ApiException.notFound("No department profile for this account"));
            challenges = challengeRepository.findByDepartmentId(department.getId());
        } else {
            challenges = challengeRepository.findByStatusIn(
                    List.of(ChallengeStatus.PUBLISHED, ChallengeStatus.MATCHING,
                            ChallengeStatus.SHORTLISTED, ChallengeStatus.PILOT, ChallengeStatus.CLOSED));
        }
        return challenges.stream().map(this::toResponse).toList();
    }

    private void assertVisible(User actor, Challenge challenge) {
        RoleName role = actor.getRole().getName();
        if (role == RoleName.ADMIN) return;
        if (challenge.getStatus() != ChallengeStatus.DRAFT) return;

        if (role == RoleName.GOVERNMENT) {
            GovernmentDepartment department = departmentRepository.findByUserId(actor.getId()).orElse(null);
            if (department != null && department.getId().equals(challenge.getDepartment().getId())) {
                return;
            }
        }
        throw ApiException.notFound("Challenge not found");
    }

    private Challenge mustOwnAsDraft(User actor, UUID challengeId) {
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));
        GovernmentDepartment department = departmentRepository.findByUserId(actor.getId())
                .orElseThrow(() -> ApiException.forbidden("Only a government department account can manage challenges"));
        if (!challenge.getDepartment().getId().equals(department.getId())) {
            throw ApiException.forbidden("You do not own this challenge");
        }
        if (challenge.getStatus() != ChallengeStatus.DRAFT) {
            throw ApiException.conflict("Only a DRAFT challenge can be edited or published");
        }
        return challenge;
    }

    private void applyFields(Challenge challenge, ChallengeCreateRequest request) {
        challenge.setTitle(request.getTitle());
        challenge.setProblemStatement(request.getProblemStatement());
        challenge.setDesiredTechnology(request.getDesiredTechnology());
        challenge.setDomain(request.getDomain());
        challenge.setOutcomesExpected(request.getOutcomesExpected());
        challenge.setBudgetRange(request.getBudgetRange());
        challenge.setTimelineDays(request.getTimelineDays());
    }

    private void saveRequirementsAndKpis(Challenge challenge, ChallengeCreateRequest request) {
        for (RequirementRequest r : request.getRequirements()) {
            ChallengeRequirement requirement = new ChallengeRequirement();
            requirement.setChallenge(challenge);
            requirement.setRequirementType(r.getRequirementType());
            requirement.setDescription(r.getDescription());
            requirement.setMandatory(r.isMandatory());
            requirementRepository.save(requirement);
        }
        for (KpiRequest k : request.getKpis()) {
            ChallengeKpi kpi = new ChallengeKpi();
            kpi.setChallenge(challenge);
            kpi.setKpiName(k.getKpiName());
            kpi.setTargetValue(k.getTargetValue());
            kpi.setUnit(k.getUnit());
            kpi.setWeight(k.getWeight());
            kpiRepository.save(kpi);
        }
    }

    private void ensureDefaultEvaluationCriteria(Challenge challenge) {
        if (!evaluationCriterionRepository.findByChallengeId(challenge.getId()).isEmpty()) {
            return;
        }
        record Default(String name, BigDecimal weight) {}
        List<Default> defaults = List.of(
                new Default("Technical Feasibility", new BigDecimal("0.30")),
                new Default("Cost Effectiveness", new BigDecimal("0.25")),
                new Default("Scalability", new BigDecimal("0.25")),
                new Default("Team Capability", new BigDecimal("0.20"))
        );
        for (Default d : defaults) {
            EvaluationCriterion criterion = new EvaluationCriterion();
            criterion.setChallenge(challenge);
            criterion.setCriterionName(d.name());
            criterion.setMaxScore(BigDecimal.TEN);
            criterion.setWeight(d.weight());
            evaluationCriterionRepository.save(criterion);
        }
    }

    private ChallengeResponse toResponse(Challenge challenge) {
        return new ChallengeResponse(
                challenge,
                requirementRepository.findByChallengeId(challenge.getId()),
                kpiRepository.findByChallengeId(challenge.getId())
        );
    }
}
