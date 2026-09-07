package com.innovategov.backend.controller;

import com.innovategov.backend.dto.document.DocumentResponse;
import com.innovategov.backend.entity.enums.DocumentOwnerType;
import com.innovategov.backend.entity.enums.DocumentType;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.DocumentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;
    private final CurrentUserService currentUserService;

    @PostMapping(value = "/{ownerType}/{ownerId}", consumes = "multipart/form-data")
    public ResponseEntity<DocumentResponse> upload(
            @PathVariable DocumentOwnerType ownerType,
            @PathVariable UUID ownerId,
            @RequestParam DocumentType documentType,
            @RequestParam("file") MultipartFile file
    ) {
        DocumentResponse response = documentService.upload(
                currentUserService.currentUser(), ownerType, ownerId, documentType, file);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/{ownerType}/{ownerId}")
    public ResponseEntity<List<DocumentResponse>> list(
            @PathVariable DocumentOwnerType ownerType, @PathVariable UUID ownerId
    ) {
        return ResponseEntity.ok(documentService.listForOwner(currentUserService.currentUser(), ownerType, ownerId));
    }
}
