package com.innovategov.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.innovategov.backend.entity.AuditLog;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.repository.AuditLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AuditService {

    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    public void log(User actor, String action, String entityType, UUID entityId, Map<String, Object> metadata) {
        AuditLog log = new AuditLog();
        log.setActor(actor);
        log.setAction(action);
        log.setEntityType(entityType);
        log.setEntityId(entityId);
        if (metadata != null && !metadata.isEmpty()) {
            try {
                log.setMetadataJson(objectMapper.writeValueAsString(metadata));
            } catch (Exception ignored) {
                // Audit metadata is best-effort context, never a reason to fail the primary action.
            }
        }
        auditLogRepository.save(log);
    }
}
