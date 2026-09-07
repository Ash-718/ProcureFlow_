package com.innovategov.backend.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Unauthenticated landing points so hitting the backend's base URL in a
 * browser shows something meaningful instead of a blank 403 (Spring Security
 * otherwise rejects "/" like any other unmapped, authenticated-by-default path),
 * and a plain /health alongside the fuller /actuator/health — both do a real
 * DB round trip, neither is a hardcoded "ok".
 */
@RestController
@RequiredArgsConstructor
public class RootController {

    private final DataSource dataSource;

    @GetMapping("/")
    public Map<String, Object> root() {
        return Map.of(
                "service", "INNOVATE-GOV Backend API",
                "status", "ok",
                "docs", "/swagger-ui.html",
                "health", "/health",
                "api", "/api/v1"
        );
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "INNOVATE-GOV Backend API");

        boolean dbUp;
        try (Connection connection = dataSource.getConnection()) {
            dbUp = connection.isValid(2);
        } catch (SQLException e) {
            dbUp = false;
        }
        body.put("database", dbUp ? "UP" : "DOWN");
        body.put("status", dbUp ? "ok" : "degraded");

        return ResponseEntity.status(dbUp ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE).body(body);
    }
}
