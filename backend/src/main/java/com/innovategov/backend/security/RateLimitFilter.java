package com.innovategov.backend.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Basic fixed-window rate limiter for the auth endpoints (Section 14: "basic rate
 * limiting on auth endpoints"). Deliberately simple — in-memory, per-IP, fixed
 * 60-second window — appropriate for a single-instance hackathon deployment; a
 * production multi-instance deployment would move this to Redis or an API gateway.
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private static final int MAX_REQUESTS_PER_WINDOW = 15;
    private static final long WINDOW_MS = 60_000L;

    private record Window(long windowStart, AtomicInteger count) {}

    private final ConcurrentHashMap<String, Window> buckets = new ConcurrentHashMap<>();

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain
    ) throws ServletException, IOException {
        String path = request.getRequestURI();
        if (!path.startsWith("/api/v1/auth/")) {
            filterChain.doFilter(request, response);
            return;
        }

        String clientKey = request.getRemoteAddr();
        long now = System.currentTimeMillis();

        Window window = buckets.compute(clientKey, (key, existing) -> {
            if (existing == null || now - existing.windowStart() > WINDOW_MS) {
                return new Window(now, new AtomicInteger(1));
            }
            existing.count().incrementAndGet();
            return existing;
        });

        if (window.count().get() > MAX_REQUESTS_PER_WINDOW) {
            response.setStatus(429);
            response.setContentType("application/json");
            response.getWriter().write(
                    "{\"error\":\"RATE_LIMITED\",\"message\":\"Too many auth requests, please wait a minute.\"}");
            return;
        }

        filterChain.doFilter(request, response);
    }
}
