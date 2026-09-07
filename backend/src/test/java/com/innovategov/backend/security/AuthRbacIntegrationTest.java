package com.innovategov.backend.security;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Section 20: "authentication + RBAC enforcement". Runs against the real, already-
 * seeded local Postgres instance (see database/seed.sql) rather than an in-memory
 * substitute, because the schema leans on native Postgres enum/array/jsonb types
 * that an H2 compatibility mode does not faithfully emulate. Requires the dev
 * database (docker compose up, or the local instance under database/) to be
 * running with the demo accounts seeded — see README "Running the tests".
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AuthRbacIntegrationTest {

    @Autowired
    private TestRestTemplate restTemplate;

    private static String governmentToken;
    private static String startupToken;
    private static String expertToken;

    @BeforeAll
    static void loginAll(@Autowired TestRestTemplate restTemplate) {
        governmentToken = login(restTemplate, "government@demo.com");
        startupToken = login(restTemplate, "startup@demo.com");
        expertToken = login(restTemplate, "expert@demo.com");
    }

    private static String login(TestRestTemplate restTemplate, String email) {
        ResponseEntity<Map> response = restTemplate.postForEntity(
                "/api/v1/auth/login", Map.of("email", email, "password", "Demo@123"), Map.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return (String) response.getBody().get("token");
    }

    private HttpEntity<Void> authHeader(String token) {
        HttpHeaders headers = new HttpHeaders();
        if (token != null) headers.setBearerAuth(token);
        return new HttpEntity<>(headers);
    }

    @Test
    void anonymousRequest_toProtectedEndpoint_isRejected() {
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/challenges", HttpMethod.GET, authHeader(null), String.class);
        assertThat(response.getStatusCode()).isIn(HttpStatus.UNAUTHORIZED, HttpStatus.FORBIDDEN);
    }

    @Test
    void invalidToken_isRejected() {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth("not-a-real-jwt");
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/challenges", HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(response.getStatusCode()).isIn(HttpStatus.UNAUTHORIZED, HttpStatus.FORBIDDEN);
    }

    @Test
    void governmentAccount_canListChallenges() {
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/challenges", HttpMethod.GET, authHeader(governmentToken), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void startupAccount_cannotCreateChallenge_governmentOnlyEndpoint() {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(startupToken);
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> body = new HttpEntity<>(
                Map.of("title", "x", "problemStatement", "y", "domain", "z"), headers);

        ResponseEntity<String> response = restTemplate.postForEntity("/api/v1/challenges", body, String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void expertAccount_cannotSubmitProposal_startupOnlyEndpoint() {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(expertToken);
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> body = new HttpEntity<>(Map.of("summary", "test"), headers);

        ResponseEntity<String> response = restTemplate.postForEntity(
                "/api/v1/proposals/challenges/00000000-0000-0000-0000-000000000000", body, String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void startupAccount_canReadOwnProfile() {
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/startups/me", HttpMethod.GET, authHeader(startupToken), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("RoadSense AI");
    }

    @Test
    void governmentAccount_cannotReadStartupSelfEndpoint_wrongRole() {
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/startups/me", HttpMethod.GET, authHeader(governmentToken), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void adminOnlyEndpoint_rejectsNonAdminRoles() {
        ResponseEntity<String> response = restTemplate.exchange(
                "/api/v1/admin/users", HttpMethod.GET, authHeader(governmentToken), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }
}
