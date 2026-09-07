package com.innovategov.backend.controller;

import com.innovategov.backend.dto.ai.AiKnowledgeBaseSimilarResponse;
import com.innovategov.backend.dto.knowledgebase.KnowledgeBaseEntryDto;
import com.innovategov.backend.dto.knowledgebase.SimilarPilotsRequest;
import com.innovategov.backend.service.KnowledgeBaseService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/knowledge-base")
@RequiredArgsConstructor
public class KnowledgeBaseController {

    private final KnowledgeBaseService knowledgeBaseService;

    @GetMapping
    public ResponseEntity<List<KnowledgeBaseEntryDto>> search(
            @RequestParam(required = false) String domain,
            @RequestParam(required = false) String technology,
            @RequestParam(required = false) Boolean success,
            @RequestParam(required = false) String q
    ) {
        return ResponseEntity.ok(knowledgeBaseService.search(domain, technology, success, q));
    }

    @PostMapping("/similar-for-draft")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'ADMIN')")
    public ResponseEntity<AiKnowledgeBaseSimilarResponse> similarForDraft(@Valid @RequestBody SimilarPilotsRequest request) {
        return ResponseEntity.ok(knowledgeBaseService.findSimilarForDraft(
                request.getTitle(), request.getProblemStatement(), request.getDesiredTechnology(),
                request.getDomain(), request.getOutcomesExpected()));
    }
}
