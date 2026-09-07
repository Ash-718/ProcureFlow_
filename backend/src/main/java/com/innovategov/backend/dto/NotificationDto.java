package com.innovategov.backend.dto;

import com.innovategov.backend.entity.Notification;
import lombok.Getter;

import java.time.Instant;
import java.util.UUID;

@Getter
public class NotificationDto {
    private final UUID id;
    private final String type;
    private final String message;
    private final boolean read;
    private final Instant createdAt;

    public NotificationDto(Notification n) {
        this.id = n.getId();
        this.type = n.getType().name();
        this.message = n.getMessage();
        this.read = n.isRead();
        this.createdAt = n.getCreatedAt();
    }
}
