package com.innovategov.backend.service;

import com.innovategov.backend.dto.startup.CapabilityRequest;
import com.innovategov.backend.dto.startup.ProjectRequest;
import com.innovategov.backend.dto.startup.StartupResponse;
import com.innovategov.backend.dto.startup.UpdateStartupProfileRequest;
import com.innovategov.backend.entity.Startup;
import com.innovategov.backend.entity.StartupCapability;
import com.innovategov.backend.entity.StartupProject;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.StartupCapabilityRepository;
import com.innovategov.backend.repository.StartupProjectRepository;
import com.innovategov.backend.repository.StartupRepository;
import com.innovategov.backend.util.AfterCommitRunner;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional(readOnly = true)
public class StartupService {

    private final StartupRepository startupRepository;
    private final StartupCapabilityRepository capabilityRepository;
    private final StartupProjectRepository projectRepository;
    private final AiServiceClient aiServiceClient;
    private final AuditService auditService;
    private final AfterCommitRunner afterCommitRunner;

    public Startup getStartupForUser(UUID userId) {
        return startupRepository.findByUserId(userId)
                .orElseThrow(() -> ApiException.notFound("No startup profile found for this account"));
    }

    public StartupResponse getProfile(UUID startupId) {
        Startup startup = startupRepository.findById(startupId)
                .orElseThrow(() -> ApiException.notFound("Startup not found"));
        return toResponse(startup);
    }

    public List<StartupResponse> listAll() {
        return startupRepository.findAll().stream().map(this::toResponse).toList();
    }

    @Transactional
    public StartupResponse updateProfile(User actor, UUID startupId, UpdateStartupProfileRequest request) {
        Startup startup = mustOwn(actor, startupId);
        startup.setCompanyName(request.getCompanyName());
        startup.setDpiitNumber(request.getDpiitNumber());
        startup.setFoundedYear(request.getFoundedYear());
        startup.setTeamSize(request.getTeamSize());
        startup.setCity(request.getCity());
        startup.setState(request.getState());
        startup.setDescription(request.getDescription());
        if (request.getReadinessScore() != null) {
            startup.setReadinessScore(request.getReadinessScore());
        }
        startupRepository.save(startup);
        recomputeEmbeddingBestEffort(startup.getId());
        auditService.log(actor, "UPDATE_PROFILE", "Startup", startup.getId(), null);
        return toResponse(startup);
    }

    @Transactional
    public StartupResponse addCapability(User actor, UUID startupId, CapabilityRequest request) {
        Startup startup = mustOwn(actor, startupId);
        StartupCapability capability = new StartupCapability();
        capability.setStartup(startup);
        capability.setTechnologyTag(request.getTechnologyTag());
        capability.setDomainTag(request.getDomainTag());
        capability.setProficiencyLevel(request.getProficiencyLevel());
        capability.setDescription(request.getDescription());
        capabilityRepository.save(capability);
        recomputeEmbeddingBestEffort(startupId);
        return toResponse(startup);
    }

    @Transactional
    public void deleteCapability(User actor, UUID startupId, UUID capabilityId) {
        mustOwn(actor, startupId);
        capabilityRepository.deleteByStartupIdAndId(startupId, capabilityId);
        recomputeEmbeddingBestEffort(startupId);
    }

    @Transactional
    public StartupResponse addProject(User actor, UUID startupId, ProjectRequest request) {
        Startup startup = mustOwn(actor, startupId);
        StartupProject project = new StartupProject();
        project.setStartup(startup);
        project.setTitle(request.getTitle());
        project.setDomain(request.getDomain());
        project.setTechnologyStack(request.getTechnologyStack());
        project.setClientType(request.getClientType());
        project.setOutcomeSummary(request.getOutcomeSummary());
        project.setYear(request.getYear());
        projectRepository.save(project);
        recomputeEmbeddingBestEffort(startupId);
        return toResponse(startup);
    }

    private Startup mustOwn(User actor, UUID startupId) {
        Startup startup = startupRepository.findById(startupId)
                .orElseThrow(() -> ApiException.notFound("Startup not found"));
        if (!startup.getUser().getId().equals(actor.getId())) {
            throw ApiException.forbidden("You do not own this startup profile");
        }
        return startup;
    }

    private void recomputeEmbeddingBestEffort(UUID startupId) {
        afterCommitRunner.run(() -> {
            try {
                aiServiceClient.triggerStartupEmbedding(startupId);
            } catch (Exception ex) {
                // Non-fatal: the AI service lazily computes a missing embedding the next time
                // matching runs, so a transient failure here must never block a profile save.
                log.warn("Could not eagerly recompute embedding for startup {}: {}", startupId, ex.getMessage());
            }
        });
    }

    private StartupResponse toResponse(Startup startup) {
        List<StartupCapability> capabilities = capabilityRepository.findByStartupId(startup.getId());
        List<StartupProject> projects = projectRepository.findByStartupId(startup.getId());
        return new StartupResponse(startup, capabilities, projects);
    }
}
