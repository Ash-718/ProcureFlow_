package com.innovategov.backend.service;

import com.innovategov.backend.dto.admin.AdminUserDto;
import com.innovategov.backend.dto.admin.AuditLogDto;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.AuditLogRepository;
import com.innovategov.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AdminService {

    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;
    private final AuditService auditService;

    public List<AdminUserDto> listUsers() {
        return userRepository.findAll().stream().map(AdminUserDto::new).toList();
    }

    @Transactional
    public AdminUserDto setActive(User actor, UUID userId, boolean active) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> ApiException.notFound("User not found"));
        user.setActive(active);
        userRepository.save(user);
        auditService.log(actor, active ? "ACTIVATE_USER" : "DEACTIVATE_USER", "User", userId, null);
        return new AdminUserDto(user);
    }

    public Page<AuditLogDto> listAuditLogs(int page, int size) {
        return auditLogRepository
                .findAllByOrderByCreatedAtDesc(PageRequest.of(page, size, Sort.by("createdAt").descending()))
                .map(AuditLogDto::new);
    }
}
