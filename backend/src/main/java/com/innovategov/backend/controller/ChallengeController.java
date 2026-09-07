package com.innovategov.backend.controller;

import com.innovategov.backend.dto.challenge.ChallengeCreateRequest;
import com.innovategov.backend.dto.challenge.ChallengeResponse;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.ChallengeService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/challenges")
@RequiredArgsConstructor
public class ChallengeController {

    private final ChallengeService challengeService;
    private final CurrentUserService currentUserService;

    @PostMapping
    @PreAuthorize("hasRole('GOVERNMENT')")
    public ResponseEntity<ChallengeResponse> create(@Valid @RequestBody ChallengeCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(challengeService.create(currentUserService.currentUser(), request));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('GOVERNMENT')")
    public ResponseEntity<ChallengeResponse> update(@PathVariable UUID id, @Valid @RequestBody ChallengeCreateRequest request) {
        return ResponseEntity.ok(challengeService.update(currentUserService.currentUser(), id, request));
    }

    @PostMapping("/{id}/publish")
    @PreAuthorize("hasRole('GOVERNMENT')")
    public ResponseEntity<ChallengeResponse> publish(@PathVariable UUID id) {
        return ResponseEntity.ok(challengeService.publish(currentUserService.currentUser(), id));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ChallengeResponse> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(challengeService.getById(currentUserService.currentUser(), id));
    }

    @GetMapping
    public ResponseEntity<List<ChallengeResponse>> list() {
        return ResponseEntity.ok(challengeService.listForActor(currentUserService.currentUser()));
    }
}
