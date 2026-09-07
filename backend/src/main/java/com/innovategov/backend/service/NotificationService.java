package com.innovategov.backend.service;

import com.innovategov.backend.entity.Notification;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.entity.enums.NotificationType;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notificationRepository;

    public void notify(User user, NotificationType type, String message) {
        Notification notification = new Notification();
        notification.setUser(user);
        notification.setType(type);
        notification.setMessage(message);
        notificationRepository.save(notification);
    }

    public List<Notification> listForUser(UUID userId) {
        return notificationRepository.findByUserIdOrderByCreatedAtDesc(userId);
    }

    public Map<String, Long> unreadCount(UUID userId) {
        return Map.of("unread", notificationRepository.countByUserIdAndReadFalse(userId));
    }

    public void markRead(UUID userId, UUID notificationId) {
        Notification notification = notificationRepository.findById(notificationId)
                .orElseThrow(() -> ApiException.notFound("Notification not found"));
        if (!notification.getUser().getId().equals(userId)) {
            throw ApiException.forbidden("You do not own this notification");
        }
        notification.setRead(true);
        notificationRepository.save(notification);
    }
}
