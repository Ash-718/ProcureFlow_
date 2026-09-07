package com.innovategov.backend.service;

import com.innovategov.backend.dto.pilot.KpiResultRequest;
import com.innovategov.backend.dto.pilot.MilestoneUpdateRequest;
import com.innovategov.backend.dto.pilot.PilotCreateRequest;
import com.innovategov.backend.dto.pilot.PilotResponse;
import com.innovategov.backend.entity.*;
import com.innovategov.backend.entity.enums.*;
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
public class PilotService {

    private final PilotRepository pilotRepository;
    private final PilotMilestoneRepository milestoneRepository;
    private final KpiRepository kpiRepository;
    private final KpiResultRepository kpiResultRepository;
    private final ContractRepository contractRepository;
    private final ChallengeRepository challengeRepository;
    private final StartupRepository startupRepository;
    private final GovernmentDepartmentRepository departmentRepository;
    private final RecommendationService recommendationService;
    private final AuditService auditService;
    private final NotificationService notificationService;

    @Transactional
    public PilotResponse create(User actor, PilotCreateRequest request) {
        Challenge challenge = challengeRepository.findById(request.getChallengeId())
                .orElseThrow(() -> ApiException.notFound("Challenge not found"));
        assertOwnerOrAdmin(actor, challenge);

        Startup startup = startupRepository.findById(request.getStartupId())
                .orElseThrow(() -> ApiException.notFound("Startup not found"));

        Contract contract = null;
        if (request.getContract() != null) {
            contract = new Contract();
            contract.setContractValue(request.getContract().getContractValue());
            contract.setIpTerms(request.getContract().getIpTerms());
            contract.setDataTerms(request.getContract().getDataTerms());
            contract.setPaymentTerms(request.getContract().getPaymentTerms());
            contract.setStatus(ContractStatus.ACTIVE);
            contractRepository.save(contract);
        }

        Pilot pilot = new Pilot();
        pilot.setChallenge(challenge);
        pilot.setStartup(startup);
        pilot.setContract(contract);
        pilot.setStartDate(request.getStartDate());
        pilot.setEndDate(request.getEndDate());
        pilot.setStatus(PilotStatus.ACTIVE);
        pilotRepository.save(pilot);

        for (PilotCreateRequest.MilestoneRequest m : request.getMilestones()) {
            PilotMilestone milestone = new PilotMilestone();
            milestone.setPilot(pilot);
            milestone.setTitle(m.getTitle());
            milestone.setDueDate(m.getDueDate());
            milestone.setStatus(MilestoneStatus.PENDING);
            milestoneRepository.save(milestone);
        }
        for (PilotCreateRequest.KpiDefinitionRequest k : request.getKpis()) {
            Kpi kpi = new Kpi();
            kpi.setPilot(pilot);
            kpi.setKpiName(k.getKpiName());
            kpi.setTargetValue(k.getTargetValue());
            kpi.setUnit(k.getUnit());
            kpiRepository.save(kpi);
        }

        challenge.setStatus(ChallengeStatus.PILOT);
        challengeRepository.save(challenge);

        auditService.log(actor, "CREATE", "Pilot", pilot.getId(), null);
        notificationService.notify(startup.getUser(), NotificationType.PILOT_CREATED,
                "A pilot has been created for \"" + challenge.getTitle() + "\".");

        return toResponse(pilot);
    }

    @Transactional
    public PilotResponse updateMilestone(User actor, UUID pilotId, UUID milestoneId, MilestoneUpdateRequest request) {
        Pilot pilot = getPilotForManagement(actor, pilotId);
        PilotMilestone milestone = milestoneRepository.findById(milestoneId)
                .filter(m -> m.getPilot().getId().equals(pilotId))
                .orElseThrow(() -> ApiException.notFound("Milestone not found on this pilot"));
        milestone.setStatus(request.getStatus());
        milestone.setCompletionDate(request.getCompletionDate());
        milestoneRepository.save(milestone);
        auditService.log(actor, "UPDATE_MILESTONE", "PilotMilestone", milestoneId,
                java.util.Map.of("status", request.getStatus().name()));
        return toResponse(pilot);
    }

    @Transactional
    public PilotResponse addKpiResult(User actor, UUID pilotId, UUID kpiId, KpiResultRequest request) {
        Pilot pilot = getPilotForManagement(actor, pilotId);
        Kpi kpi = kpiRepository.findById(kpiId)
                .filter(k -> k.getPilot().getId().equals(pilotId))
                .orElseThrow(() -> ApiException.notFound("KPI not found on this pilot"));

        KpiResult result = new KpiResult();
        result.setKpi(kpi);
        result.setRecordedValue(request.getRecordedValue());
        result.setNotes(request.getNotes());
        kpiResultRepository.save(result);

        auditService.log(actor, "RECORD_KPI_RESULT", "Kpi", kpiId,
                java.util.Map.of("recordedValue", request.getRecordedValue().toString()));
        return toResponse(pilot);
    }

    @Transactional
    public PilotResponse complete(User actor, UUID pilotId, PilotStatus finalStatus) {
        Pilot pilot = getPilotForManagement(actor, pilotId);
        if (finalStatus != PilotStatus.COMPLETED && finalStatus != PilotStatus.TERMINATED) {
            throw ApiException.badRequest("finalStatus must be COMPLETED or TERMINATED");
        }
        pilot.setStatus(finalStatus);
        pilotRepository.save(pilot);

        pilot.getChallenge().setStatus(ChallengeStatus.CLOSED);
        challengeRepository.save(pilot.getChallenge());

        recommendationService.generateForPilot(pilot);

        auditService.log(actor, "COMPLETE_PILOT", "Pilot", pilotId,
                java.util.Map.of("finalStatus", finalStatus.name()));
        return toResponse(pilot);
    }

    public PilotResponse getById(User actor, UUID pilotId) {
        Pilot pilot = pilotRepository.findById(pilotId)
                .orElseThrow(() -> ApiException.notFound("Pilot not found"));
        assertVisible(actor, pilot);
        return toResponse(pilot);
    }

    public List<PilotResponse> listForActor(User actor) {
        RoleName role = actor.getRole().getName();
        List<Pilot> pilots;
        if (role == RoleName.ADMIN) {
            pilots = pilotRepository.findAll();
        } else if (role == RoleName.GOVERNMENT) {
            GovernmentDepartment department = departmentRepository.findByUserId(actor.getId())
                    .orElseThrow(() -> ApiException.notFound("No department profile for this account"));
            List<UUID> challengeIds = challengeRepository.findByDepartmentId(department.getId())
                    .stream().map(Challenge::getId).toList();
            pilots = pilotRepository.findByChallengeIdIn(challengeIds);
        } else if (role == RoleName.STARTUP) {
            Startup startup = startupRepository.findByUserId(actor.getId())
                    .orElseThrow(() -> ApiException.notFound("No startup profile for this account"));
            pilots = pilotRepository.findByStartupId(startup.getId());
        } else {
            pilots = List.of();
        }
        return pilots.stream().map(this::toResponse).toList();
    }

    private Pilot getPilotForManagement(User actor, UUID pilotId) {
        Pilot pilot = pilotRepository.findById(pilotId)
                .orElseThrow(() -> ApiException.notFound("Pilot not found"));
        assertOwnerOrAdmin(actor, pilot.getChallenge());
        return pilot;
    }

    private void assertOwnerOrAdmin(User actor, Challenge challenge) {
        if (actor.getRole().getName() == RoleName.ADMIN) return;
        GovernmentDepartment department = departmentRepository.findByUserId(actor.getId()).orElse(null);
        if (department == null || !department.getId().equals(challenge.getDepartment().getId())) {
            throw ApiException.forbidden("You do not have access to this pilot");
        }
    }

    private void assertVisible(User actor, Pilot pilot) {
        RoleName role = actor.getRole().getName();
        if (role == RoleName.ADMIN) return;
        if (role == RoleName.GOVERNMENT) {
            assertOwnerOrAdmin(actor, pilot.getChallenge());
            return;
        }
        if (role == RoleName.STARTUP) {
            Startup startup = startupRepository.findByUserId(actor.getId()).orElse(null);
            if (startup != null && startup.getId().equals(pilot.getStartup().getId())) return;
        }
        throw ApiException.forbidden("You do not have access to this pilot");
    }

    private PilotResponse toResponse(Pilot pilot) {
        List<PilotMilestone> milestones = milestoneRepository.findByPilotId(pilot.getId());
        List<Kpi> kpis = kpiRepository.findByPilotId(pilot.getId());
        List<KpiResult> latest = kpis.stream()
                .map(k -> kpiResultRepository.findByKpiIdOrderByRecordedAtDesc(k.getId())
                        .stream().findFirst().orElse(null))
                .filter(r -> r != null)
                .toList();
        return new PilotResponse(pilot, milestones, kpis, latest);
    }
}
