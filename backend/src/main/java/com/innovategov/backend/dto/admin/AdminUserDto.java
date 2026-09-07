package com.innovategov.backend.dto.admin;

import com.innovategov.backend.entity.User;
import lombok.Getter;

import java.time.Instant;
import java.util.UUID;

@Getter
public class AdminUserDto {
    private final UUID id;
    private final String email;
    private final String fullName;
    private final String role;
    private final boolean active;
    private final Instant createdAt;

    public AdminUserDto(User u) {
        this.id = u.getId();
        this.email = u.getEmail();
        this.fullName = u.getFullName();
        this.role = u.getRole().getName().name();
        this.active = u.isActive();
        this.createdAt = u.getCreatedAt();
    }
}
