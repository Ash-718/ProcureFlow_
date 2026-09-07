package com.innovategov.backend.dto;

import com.innovategov.backend.dto.auth.RegisterRequest;
import com.innovategov.backend.dto.challenge.ChallengeCreateRequest;
import com.innovategov.backend.dto.startup.CapabilityRequest;
import com.innovategov.backend.entity.enums.RoleName;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Section 20: "challenge creation validation" / registration validation — verifies
 * the Bean Validation annotations on the request DTOs actually fire as intended.
 */
class ValidationTest {

    private static ValidatorFactory factory;
    private static Validator validator;

    @BeforeAll
    static void setUp() {
        factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @AfterAll
    static void tearDown() {
        factory.close();
    }

    @Test
    void registerRequest_rejectsBlankEmailAndShortPassword() {
        RegisterRequest request = new RegisterRequest();
        request.setEmail("");
        request.setPassword("short");
        request.setFullName("Test User");
        request.setRole(RoleName.STARTUP);
        request.setCompanyName("Test Co");

        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(request);

        assertThat(violations).extracting(v -> v.getPropertyPath().toString())
                .contains("email", "password");
    }

    @Test
    void registerRequest_acceptsValidStartupRegistration() {
        RegisterRequest request = new RegisterRequest();
        request.setEmail("founder@example.com");
        request.setPassword("SecurePass123");
        request.setFullName("Founder Name");
        request.setRole(RoleName.STARTUP);
        request.setCompanyName("Acme Robotics");

        assertThat(validator.validate(request)).isEmpty();
    }

    @Test
    void registerRequest_rejectsInvalidEmailFormat() {
        RegisterRequest request = new RegisterRequest();
        request.setEmail("not-an-email");
        request.setPassword("SecurePass123");
        request.setFullName("Founder Name");
        request.setRole(RoleName.STARTUP);
        request.setCompanyName("Acme Robotics");

        assertThat(validator.validate(request)).extracting(v -> v.getPropertyPath().toString())
                .contains("email");
    }

    @Test
    void challengeCreateRequest_rejectsBlankTitleAndProblemStatement() {
        ChallengeCreateRequest request = new ChallengeCreateRequest();
        request.setTitle("");
        request.setProblemStatement("");
        request.setDomain("smart-mobility");

        Set<ConstraintViolation<ChallengeCreateRequest>> violations = validator.validate(request);

        assertThat(violations).extracting(v -> v.getPropertyPath().toString())
                .contains("title", "problemStatement");
    }

    @Test
    void challengeCreateRequest_acceptsMinimalValidChallenge() {
        ChallengeCreateRequest request = new ChallengeCreateRequest();
        request.setTitle("Smart Streetlight Monitoring");
        request.setProblemStatement("Streetlights fail undetected for weeks at a time.");
        request.setDomain("smart-mobility");

        assertThat(validator.validate(request)).isEmpty();
    }

    @Test
    void capabilityRequest_rejectsProficiencyLevelOutsideOneToFive() {
        CapabilityRequest request = new CapabilityRequest();
        request.setTechnologyTag("Computer Vision");
        request.setDomainTag("smart-mobility");
        request.setProficiencyLevel(7);

        assertThat(validator.validate(request)).extracting(v -> v.getPropertyPath().toString())
                .contains("proficiencyLevel");
    }
}
