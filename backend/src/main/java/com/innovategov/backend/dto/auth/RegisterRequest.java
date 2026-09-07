package com.innovategov.backend.dto.auth;

import com.innovategov.backend.entity.enums.RoleName;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RegisterRequest {

    @NotBlank
    @Email
    private String email;

    @NotBlank
    @Size(min = 8, message = "Password must be at least 8 characters")
    private String password;

    @NotBlank
    private String fullName;

    /** Only STARTUP and GOVERNMENT may self-register; EXPERT/ADMIN are provisioned by an admin. */
    @NotNull
    private RoleName role;

    /** Required when role == STARTUP. */
    private String companyName;

    /** Required when role == GOVERNMENT. */
    private String departmentName;
    private String ministry;
    private String region;
}
