package com.innovategov.backend.controller;

import com.innovategov.backend.dto.startup.CapabilityRequest;
import com.innovategov.backend.dto.startup.ProjectRequest;
import com.innovategov.backend.dto.startup.StartupResponse;
import com.innovategov.backend.dto.startup.UpdateStartupProfileRequest;
import com.innovategov.backend.entity.Startup;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.security.CurrentUserService;
import com.innovategov.backend.service.StartupService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/startups")
@RequiredArgsConstructor
public class StartupController {

    private final StartupService startupService;
    private final CurrentUserService currentUserService;

    @GetMapping("/me")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<StartupResponse> myProfile() {
        Startup startup = startupService.getStartupForUser(currentUserService.principal().getId());
        return ResponseEntity.ok(startupService.getProfile(startup.getId()));
    }

    @PutMapping("/me")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<StartupResponse> updateMyProfile(@Valid @RequestBody UpdateStartupProfileRequest request) {
        User actor = currentUserService.currentUser();
        Startup startup = startupService.getStartupForUser(actor.getId());
        return ResponseEntity.ok(startupService.updateProfile(actor, startup.getId(), request));
    }

    @PostMapping("/me/capabilities")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<StartupResponse> addMyCapability(@Valid @RequestBody CapabilityRequest request) {
        User actor = currentUserService.currentUser();
        Startup startup = startupService.getStartupForUser(actor.getId());
        return ResponseEntity.ok(startupService.addCapability(actor, startup.getId(), request));
    }

    @DeleteMapping("/me/capabilities/{capabilityId}")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<Void> deleteMyCapability(@PathVariable UUID capabilityId) {
        User actor = currentUserService.currentUser();
        Startup startup = startupService.getStartupForUser(actor.getId());
        startupService.deleteCapability(actor, startup.getId(), capabilityId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/me/projects")
    @PreAuthorize("hasRole('STARTUP')")
    public ResponseEntity<StartupResponse> addMyProject(@Valid @RequestBody ProjectRequest request) {
        User actor = currentUserService.currentUser();
        Startup startup = startupService.getStartupForUser(actor.getId());
        return ResponseEntity.ok(startupService.addProject(actor, startup.getId(), request));
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'EXPERT', 'ADMIN')")
    public ResponseEntity<List<StartupResponse>> listAll() {
        return ResponseEntity.ok(startupService.listAll());
    }

    @GetMapping("/{startupId}")
    @PreAuthorize("hasAnyRole('GOVERNMENT', 'EXPERT', 'ADMIN')")
    public ResponseEntity<StartupResponse> getById(@PathVariable UUID startupId) {
        return ResponseEntity.ok(startupService.getProfile(startupId));
    }
}
