package com.innovategov.backend.dto.knowledgebase;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class SimilarPilotsRequest {
    @NotBlank
    private String title;

    @NotBlank
    private String problemStatement;

    private String desiredTechnology;

    @NotBlank
    private String domain;

    private String outcomesExpected;
}
