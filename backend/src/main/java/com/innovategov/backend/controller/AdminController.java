package com.innovategov.backend.controller;

import com.innovategov.backend.dto.admin.AdminUserDto;
import com.innovategov.backend.dto.admin.AuditLogDto;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.AdminService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class AdminController {

    private final AdminService adminService;
    private final CurrentUserService currentUserService;

    @GetMapping("/users")
    public ResponseEntity<List<AdminUserDto>> listUsers() {
        return ResponseEntity.ok(adminService.listUsers());
    }

    @PatchMapping("/users/{id}/active")
    public ResponseEntity<AdminUserDto> setActive(@PathVariable UUID id, @RequestBody Map<String, Boolean> body) {
        boolean active = body.getOrDefault("active", true);
        return ResponseEntity.ok(adminService.setActive(currentUserService.currentUser(), id, active));
    }

    @GetMapping("/audit-logs")
    public ResponseEntity<Page<AuditLogDto>> auditLogs(
            @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "50") int size) {
        return ResponseEntity.ok(adminService.listAuditLogs(page, size));
    }
}
