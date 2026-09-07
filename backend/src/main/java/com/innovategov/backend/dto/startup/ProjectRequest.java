package com.innovategov.backend.dto.startup;

import com.innovategov.backend.entity.enums.ClientType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ProjectRequest {

    @NotBlank
    private String title;

    @NotBlank
    private String domain;

    private String technologyStack;

    @NotNull
    private ClientType clientType = ClientType.PRIVATE;

    private String outcomeSummary;
    private Integer year;
}
