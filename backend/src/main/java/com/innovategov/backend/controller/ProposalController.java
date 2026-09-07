package com.innovategov.backend.controller;

import com.innovategov.backend.dto.proposal.ProposalCreateRequest;
import com.innovategov.backend.dto.proposal.ProposalResponse;
import com.innovategov.backend.dto.proposal.ProposalStatusUpdateRequest;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.ProposalService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/proposals")
@RequiredArgsConstructor
public class ProposalController {

    private final ProposalService proposalService;
    private final CurrentUserService currentUserService;

    @PostMapping("/challenges/{challengeId}")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<ProposalResponse> submit(@PathVariable UUID challengeId, @Valid @RequestBody ProposalCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(proposalService.submit(currentUserService.currentUser(), challengeId, request));
    }

    @GetMapping("/challenges/{challengeId}")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'EXPERT', 'ADMIN')")
    public ResponseEntity<List<ProposalResponse>> listForChallenge(@PathVariable UUID challengeId) {
        return ResponseEntity.ok(proposalService.listForChallenge(currentUserService.currentUser(), challengeId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProposalResponse> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(proposalService.getById(currentUserService.currentUser(), id));
    }

    @GetMapping("/mine")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<List<ProposalResponse>> listMine() {
        return ResponseEntity.ok(proposalService.listMine(currentUserService.currentUser()));
    }

    @GetMapping("/queue")
    @PreAuthorize("hasRole('EXPERT')")
    public ResponseEntity<List<ProposalResponse>> queue() {
        return ResponseEntity.ok(proposalService.listAllForExpertQueue());
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<ProposalResponse> updateStatus(@PathVariable UUID id, @Valid @RequestBody ProposalStatusUpdateRequest request) {
        return ResponseEntity.ok(proposalService.updateStatus(currentUserService.currentUser(), id, request.getStatus()));
    }
}
