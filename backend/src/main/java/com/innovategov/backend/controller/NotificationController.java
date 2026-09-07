package com.innovategov.backend.controller;

import com.innovategov.backend.dto.NotificationDto;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;
    private final CurrentUserService currentUserService;

    @GetMapping
    public ResponseEntity<List<NotificationDto>> list() {
        return ResponseEntity.ok(notificationService.listForUser(currentUserService.principal().getId())
                .stream().map(NotificationDto::new).toList());
    }

    @GetMapping("/unread-count")
    public ResponseEntity<Map<String, Long>> unreadCount() {
        return ResponseEntity.ok(notificationService.unreadCount(currentUserService.principal().getId()));
    }

    @PatchMapping("/{id}/read")
    public ResponseEntity<Void> markRead(@PathVariable UUID id) {
        notificationService.markRead(currentUserService.principal().getId(), id);
        return ResponseEntity.noContent().build();
    }
}
