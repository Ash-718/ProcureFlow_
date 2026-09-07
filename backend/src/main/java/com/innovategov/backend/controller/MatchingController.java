package com.innovategov.backend.controller;

import com.innovategov.backend.dto.ai.AiMatchResponse;
import com.innovategov.backend.dto.matching.MatchResultDto;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.MatchingService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/matching")
@RequiredArgsConstructor
public class MatchingController {

    private final MatchingService matchingService;
    private final CurrentUserService currentUserService;

    @PostMapping("/challenges/{challengeId}/run")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<AiMatchResponse> run(@PathVariable UUID challengeId) {
        return ResponseEntity.ok(matchingService.runMatching(currentUserService.currentUser(), challengeId));
    }

    @GetMapping("/challenges/{challengeId}")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<List<MatchResultDto>> results(@PathVariable UUID challengeId) {
        return ResponseEntity.ok(matchingService.getResults(currentUserService.currentUser(), challengeId));
    }
}
