package com.innovategov.backend.dto.admin;

import com.innovategov.backend.entity.AuditLog;
import lombok.Getter;

import java.time.Instant;
import java.util.UUID;

@Getter
public class AuditLogDto {
    private final UUID id;
    private final String actorEmail;
    private final String action;
    private final String entityType;
    private final UUID entityId;
    private final String metadataJson;
    private final Instant createdAt;

    public AuditLogDto(AuditLog log) {
        this.id = log.getId();
        this.actorEmail = log.getActor() == null ? null : log.getActor().getEmail();
        this.action = log.getAction();
        this.entityType = log.getEntityType();
        this.entityId = log.getEntityId();
        this.metadataJson = log.getMetadataJson();
        this.createdAt = log.getCreatedAt();
    }
}
