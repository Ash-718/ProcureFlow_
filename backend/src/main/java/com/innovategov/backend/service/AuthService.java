package com.innovategov.backend.service;

import com.innovategov.backend.dto.auth.AuthResponse;
import com.innovategov.backend.dto.auth.LoginRequest;
import com.innovategov.backend.dto.auth.RegisterRequest;
import com.innovategov.backend.entity.GovernmentDepartment;
import com.innovategov.backend.entity.Role;
import com.innovategov.backend.entity.Startup;
import com.innovategov.backend.entity.User;
import com.innovategov.backend.entity.enums.RoleName;
import com.innovategov.backend.exception.ApiException;
import com.innovategov.backend.repository.GovernmentDepartmentRepository;
import com.innovategov.backend.repository.RoleRepository;
import com.innovategov.backend.repository.StartupRepository;
import com.innovategov.backend.repository.UserRepository;
import com.innovategov.backend.security.JwtService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final GovernmentDepartmentRepository governmentDepartmentRepository;
    private final StartupRepository startupRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuditService auditService;

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (request.getRole() == RoleName.ADMIN || request.getRole() == RoleName.EXPERT) {
            throw ApiException.forbidden("Admin and Expert accounts can only be provisioned by an administrator");
        }
        if (userRepository.existsByEmail(request.getEmail())) {
            throw ApiException.conflict("An account with this email already exists");
        }
        if (request.getRole() == RoleName.STARTUP && isBlank(request.getCompanyName())) {
            throw ApiException.badRequest("companyName is required when registering as a startup");
        }
        if (request.getRole() == RoleName.GOVERNMENT && isBlank(request.getDepartmentName())) {
            throw ApiException.badRequest("departmentName is required when registering as a government department");
        }

        Role role = roleRepository.findByName(request.getRole())
                .orElseThrow(() -> ApiException.notFound("Role not found: " + request.getRole()));

        User user = new User();
        user.setEmail(request.getEmail().toLowerCase().trim());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setFullName(request.getFullName());
        user.setRole(role);
        user.setActive(true);
        userRepository.save(user);

        if (request.getRole() == RoleName.STARTUP) {
            Startup startup = new Startup();
            startup.setUser(user);
            startup.setCompanyName(request.getCompanyName());
            startup.setReadinessScore(BigDecimal.valueOf(50));
            startupRepository.save(startup);
        } else {
            GovernmentDepartment department = new GovernmentDepartment();
            department.setUser(user);
            department.setDepartmentName(request.getDepartmentName());
            department.setMinistry(request.getMinistry());
            department.setRegion(request.getRegion());
            governmentDepartmentRepository.save(department);
        }

        auditService.log(user, "REGISTER", "User", user.getId(), Map.of("role", role.getName().name()));

        String token = jwtService.generateToken(user.getId(), user.getEmail(), role.getName().name());
        return new AuthResponse(token, user.getId(), user.getEmail(), user.getFullName(), role.getName().name());
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail().toLowerCase().trim())
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "Invalid email or password"));

        if (!user.isActive()) {
            throw ApiException.forbidden("This account has been deactivated");
        }
        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Invalid email or password");
        }

        auditService.log(user, "LOGIN", "User", user.getId(), null);

        String token = jwtService.generateToken(user.getId(), user.getEmail(), user.getRole().getName().name());
        return new AuthResponse(token, user.getId(), user.getEmail(), user.getFullName(), user.getRole().getName().name());
    }

    private boolean isBlank(String s) {
        return s == null || s.isBlank();
    }
}
