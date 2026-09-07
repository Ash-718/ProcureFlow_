package com.innovategov.backend.controller;

import com.innovategov.backend.dto.evaluation.EvaluationCriterionDto;
import com.innovategov.backend.dto.evaluation.EvaluationResponse;
import com.innovategov.backend.dto.evaluation.EvaluationSubmitRequest;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.EvaluationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/evaluations")
@RequiredArgsConstructor
public class EvaluationController {

    private final EvaluationService evaluationService;
    private final CurrentUserService currentUserService;

    @GetMapping("/proposals/{proposalId}/criteria")
    @PreAuthorize("hasAnyRole('EXPERT', 'GOVERNMENT', 'ADMIN')")
    public ResponseEntity<List<EvaluationCriterionDto>> criteria(@PathVariable UUID proposalId) {
        return ResponseEntity.ok(evaluationService.getCriteriaForProposal(proposalId));
    }

    @GetMapping("/proposals/{proposalId}/ai-analysis")
    @PreAuthorize("hasAnyRole('EXPERT', 'GOVERNMENT', 'ADMIN')")
    public ResponseEntity<Map<String, String>> aiAnalysis(@PathVariable UUID proposalId) {
        return ResponseEntity.ok(Map.of("summary", evaluationService.getAiAnalysis(proposalId)));
    }

    @PostMapping("/proposals/{proposalId}")
    @PreAuthorize("hasRole('EXPERT')")
    public ResponseEntity<EvaluationResponse> submit(@PathVariable UUID proposalId, @Valid @RequestBody EvaluationSubmitRequest request) {
        return ResponseEntity.ok(evaluationService.submit(currentUserService.currentUser(), proposalId, request));
    }
}
