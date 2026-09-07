package com.innovategov.backend.dto.document;

import com.innovategov.backend.entity.Document;
import lombok.Getter;

import java.time.Instant;
import java.util.UUID;

@Getter
public class DocumentResponse {
    private final UUID id;
    private final String ownerType;
    private final UUID ownerId;
    private final String documentType;
    private final String originalFilename;
    private final String verificationStatus;
    private final String verificationNotes;
    private final Instant uploadedAt;

    public DocumentResponse(Document d) {
        this.id = d.getId();
        this.ownerType = d.getOwnerType().name();
        this.ownerId = d.getOwnerId();
        this.documentType = d.getDocumentType().name();
        this.originalFilename = d.getOriginalFilename();
        this.verificationStatus = d.getVerificationStatus().name();
        this.verificationNotes = d.getVerificationNotes();
        this.uploadedAt = d.getUploadedAt();
    }
}
