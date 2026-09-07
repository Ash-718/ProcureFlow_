package com.innovategov.backend.dto.proposal;

import com.innovategov.backend.entity.enums.ProposalStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ProposalStatusUpdateRequest {
    @NotNull
    private ProposalStatus status;
}
