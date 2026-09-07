package com.innovategov.backend.service;

import com.innovategov.backend.dto.ai.AiKnowledgeBaseSimilarResponse;
import com.innovategov.backend.dto.ai.AiMatchResponse;
import com.innovategov.backend.exception.ApiException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;

/**
 * Thin HTTP client to the AI service (Section 5/6). Every call here is a real HTTP
 * round trip that triggers real computation in ai-service — nothing here fabricates
 * scores. If the AI service is down, callers get a clear 503 rather than the request
 * hanging or silently returning fake data (Section 19: graceful degradation).
 */
@Service
@Slf4j
public class AiServiceClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public AiServiceClient(
            RestTemplateBuilder builder,
            @Value("${app.ai-service.url}") String baseUrl
    ) {
        this.baseUrl = baseUrl;
        // java.net.http.HttpClient defaults to Version.HTTP_2, which attempts an h2c upgrade
        // negotiation even against a plain http:// URL. uvicorn only speaks HTTP/1.1, and that
        // negotiation attempt corrupts request framing against it (requests with a body arrive
        // empty, or uvicorn logs "Invalid HTTP request received" on a reused connection).
        // Pinning HTTP_1_1 avoids the negotiation entirely.
        this.restTemplate = builder
                .requestFactory(() -> new JdkClientHttpRequestFactory(
                        HttpClient.newBuilder()
                                .version(HttpClient.Version.HTTP_1_1)
                                .connectTimeout(Duration.ofSeconds(5))
                                .build()))
                .readTimeout(Duration.ofSeconds(60)) // embedding a challenge + N startups on first run can take a few seconds
                .build();
    }

    public void triggerStartupEmbedding(UUID startupId) {
        post("/api/v1/ai/embeddings/startup/" + startupId, Object.class);
    }

    public void triggerChallengeEmbedding(UUID challengeId) {
        post("/api/v1/ai/embeddings/challenge/" + challengeId, Object.class);
    }

    public void triggerKnowledgeBaseEmbedding(UUID pilotKnowledgeBaseId) {
        post("/api/v1/ai/embeddings/knowledge-base/" + pilotKnowledgeBaseId, Object.class);
    }

    public AiMatchResponse runMatching(UUID challengeId) {
        return post("/api/v1/ai/match/" + challengeId, AiMatchResponse.class);
    }

    public String getProposalAnalysis(UUID proposalId) {
        try {
            Map<?, ?> response = restTemplate.getForObject(
                    baseUrl + "/api/v1/ai/analysis/proposal/" + proposalId, Map.class);
            return response != null ? String.valueOf(response.get("summary")) : null;
        } catch (RestClientException ex) {
            log.warn("AI service unreachable for proposal analysis {}: {}", proposalId, ex.getMessage());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "The AI service is currently unavailable. Please try again shortly.");
        }
    }

    public AiKnowledgeBaseSimilarResponse findSimilarPilots(
            String title, String problemStatement, String desiredTechnology, String domain, String outcomesExpected
    ) {
        Map<String, Object> body = Map.of(
                "title", title,
                "problem_statement", problemStatement,
                "desired_technology", desiredTechnology == null ? "" : desiredTechnology,
                "domain", domain,
                "outcomes_expected", outcomesExpected == null ? "" : outcomesExpected
        );
        try {
            return restTemplate.postForObject(
                    baseUrl + "/api/v1/ai/knowledge-base/similar", body, AiKnowledgeBaseSimilarResponse.class);
        } catch (RestClientException ex) {
            log.warn("AI service unreachable for knowledge-base similarity search: {}", ex.getMessage());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "The AI service is currently unavailable. Please try again shortly.");
        }
    }

    private <T> T post(String path, Class<T> responseType) {
        try {
            return restTemplate.postForObject(baseUrl + path, null, responseType);
        } catch (RestClientException ex) {
            log.warn("AI service call to {} failed: {}", path, ex.getMessage());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "The AI service is currently unavailable. Please try again shortly.");
        }
    }
}
