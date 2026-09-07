package com.innovategov.backend.controller;

import com.innovategov.backend.dto.pilot.*;
import com.innovategov.backend.entity.enums.PilotStatus;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.PilotService;
import com.innovategov.backend.service.RecommendationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/pilots")
@RequiredArgsConstructor
public class PilotController {

    private final PilotService pilotService;
    private final RecommendationService recommendationService;
    private final CurrentUserService currentUserService;

    @PostMapping
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<PilotResponse> create(@Valid @RequestBody PilotCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(pilotService.create(currentUserService.currentUser(), request));
    }

    @GetMapping("/{id}")
    public ResponseEntity<PilotResponse> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(pilotService.getById(currentUserService.currentUser(), id));
    }

    @GetMapping
    public ResponseEntity<List<PilotResponse>> list() {
        return ResponseEntity.ok(pilotService.listForActor(currentUserService.currentUser()));
    }

    @PatchMapping("/{id}/milestones/{milestoneId}")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<PilotResponse> updateMilestone(
            @PathVariable UUID id, @PathVariable UUID milestoneId, @Valid @RequestBody MilestoneUpdateRequest request) {
        return ResponseEntity.ok(pilotService.updateMilestone(currentUserService.currentUser(), id, milestoneId, request));
    }

    @PostMapping("/{id}/kpis/{kpiId}/results")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<PilotResponse> addKpiResult(
            @PathVariable UUID id, @PathVariable UUID kpiId, @Valid @RequestBody KpiResultRequest request) {
        return ResponseEntity.ok(pilotService.addKpiResult(currentUserService.currentUser(), id, kpiId, request));
    }

    @PostMapping("/{id}/complete")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<PilotResponse> complete(@PathVariable UUID id, @RequestBody Map<String, PilotStatus> body) {
        PilotStatus finalStatus = body.getOrDefault("finalStatus", PilotStatus.COMPLETED);
        return ResponseEntity.ok(pilotService.complete(currentUserService.currentUser(), id, finalStatus));
    }

    @GetMapping("/{id}/recommendation")
    public ResponseEntity<RecommendationResponse> recommendation(@PathVariable UUID id) {
        return ResponseEntity.ok(recommendationService.getByPilotId(id));
    }

    @PostMapping("/{id}/recommendation/decision")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<RecommendationResponse> decide(@PathVariable UUID id, @Valid @RequestBody FinalDecisionRequest request) {
        return ResponseEntity.ok(recommendationService.recordFinalDecision(
                currentUserService.currentUser(), id, request.getFinalDecision()));
    }
}
