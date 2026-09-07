package com.innovategov.backend.dto.pilot;

import com.innovategov.backend.entity.enums.MilestoneStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
public class MilestoneUpdateRequest {
    @NotNull
    private MilestoneStatus status;

    private LocalDate completionDate;
}
