"""
Pydantic schemas — the API contract layer.

Every response model derives from `CamelModel`, so FastAPI emits camelCase and
the frontend's `types/index.ts` keeps matching field-for-field. Numbers are
`float` (never `Decimal`) and timestamps use the Java `Instant` encoding; see
`app/schemas/base.py` for why both matter.

`SCHEMA_CONTRACT_MAP` binds each schema to the TypeScript interface it must
satisfy. `tests/test_contract_parity.py` walks it and fails if the two ever
drift, which is the only way a camelCase mistake gets caught — a mismatch
produces `undefined` in the browser, never an error.
"""
from app.schemas.auth import (
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.base import (
    CamelModel,
    CamelRequest,
    Instant,
    LocalDate,
    OptionalInstant,
    OptionalLocalDate,
    Page,
    PageableInfo,
    SortInfo,
    format_instant,
    format_local_date,
)
from app.schemas.challenge import (
    ChallengeDraftRequest,
    ChallengeKpiResponse,
    ChallengeRequirementResponse,
    ChallengeResponse,
    KpiRequest,
    RequirementRequest,
)
from app.schemas.evaluation import (
    AiAnalysisResponse,
    EvaluationCriterionResponse,
    EvaluationResponse,
    EvaluationScoreRequest,
    EvaluationScoreResponse,
    EvaluationSubmitRequest,
)
from app.schemas.matching import (
    ComponentScores,
    MatchCandidate,
    MatchResponse,
    MatchResultRow,
)
from app.schemas.pilot import (
    ContractCreateRequest,
    FinalDecisionRequest,
    KpiResultRequest,
    MilestoneCreateRequest,
    MilestoneUpdateRequest,
    PilotCompleteRequest,
    PilotContractResponse,
    PilotCreateRequest,
    PilotKpiCreateRequest,
    PilotKpiResponse,
    PilotMilestoneResponse,
    PilotResponse,
    RecommendationResponse,
)
from app.schemas.proposal import (
    DocumentResponse,
    ProposalCreateRequest,
    ProposalResponse,
    ProposalStatusUpdateRequest,
)
from app.schemas.startup import (
    CapabilityRequest,
    ProjectRequest,
    StartupCapabilityResponse,
    StartupProjectResponse,
    StartupResponse,
    UpdateStartupProfileRequest,
)
from app.schemas.system import (
    AdminUserResponse,
    AuditLogResponse,
    KnowledgeBaseEntryResponse,
    NotificationResponse,
    SetActiveRequest,
    SimilarPilotMatch,
    SimilarPilotsRequest,
    SimilarPilotsResponse,
    UnreadCountResponse,
)

#: Pydantic response schema -> the TypeScript interface it must satisfy.
#: Kept here rather than in the test so adding a schema without declaring its
#: contract is a visible omission.
SCHEMA_CONTRACT_MAP: dict[type, str] = {
    AuthResponse: "AuthResponse",
    CurrentUserResponse: "CurrentUser",
    ChallengeRequirementResponse: "ChallengeRequirement",
    ChallengeKpiResponse: "ChallengeKpi",
    ChallengeResponse: "Challenge",
    StartupCapabilityResponse: "StartupCapability",
    StartupProjectResponse: "StartupProject",
    StartupResponse: "Startup",
    ComponentScores: "ComponentScores",
    MatchCandidate: "MatchCandidate",
    MatchResponse: "MatchResponse",
    MatchResultRow: "MatchResultRow",
    ProposalResponse: "Proposal",
    DocumentResponse: "DocumentItem",
    EvaluationCriterionResponse: "EvaluationCriterionItem",
    EvaluationScoreResponse: "EvaluationScoreItem",
    EvaluationResponse: "Evaluation",
    PilotMilestoneResponse: "PilotMilestoneItem",
    PilotKpiResponse: "PilotKpiItem",
    PilotContractResponse: "PilotContract",
    PilotResponse: "Pilot",
    RecommendationResponse: "Recommendation",
    KnowledgeBaseEntryResponse: "KnowledgeBaseEntry",
    SimilarPilotMatch: "SimilarPilotMatch",
    NotificationResponse: "NotificationItem",
    AdminUserResponse: "AdminUser",
    AuditLogResponse: "AuditLogItem",
}

#: Request schema -> the TypeScript request type or inline payload it accepts.
REQUEST_CONTRACT_MAP: dict[type, str] = {
    ChallengeDraftRequest: "ChallengeDraft",
    UpdateStartupProfileRequest: "UpdateStartupProfileRequest",
}

__all__ = [
    "SCHEMA_CONTRACT_MAP", "REQUEST_CONTRACT_MAP",
    # base
    "CamelModel", "CamelRequest", "Instant", "LocalDate", "OptionalInstant",
    "OptionalLocalDate", "Page", "PageableInfo", "SortInfo",
    "format_instant", "format_local_date",
    # auth
    "AuthResponse", "CurrentUserResponse", "LoginRequest", "RegisterRequest",
    # challenge
    "ChallengeResponse", "ChallengeRequirementResponse", "ChallengeKpiResponse",
    "ChallengeDraftRequest", "RequirementRequest", "KpiRequest",
    # startup
    "StartupResponse", "StartupCapabilityResponse", "StartupProjectResponse",
    "UpdateStartupProfileRequest", "CapabilityRequest", "ProjectRequest",
    # matching
    "ComponentScores", "MatchCandidate", "MatchResponse", "MatchResultRow",
    # proposal & documents
    "ProposalResponse", "ProposalCreateRequest", "ProposalStatusUpdateRequest",
    "DocumentResponse",
    # evaluation
    "EvaluationResponse", "EvaluationCriterionResponse", "EvaluationScoreResponse",
    "EvaluationSubmitRequest", "EvaluationScoreRequest", "AiAnalysisResponse",
    # pilot
    "PilotResponse", "PilotMilestoneResponse", "PilotKpiResponse",
    "PilotContractResponse", "RecommendationResponse", "PilotCreateRequest",
    "MilestoneCreateRequest", "MilestoneUpdateRequest", "PilotKpiCreateRequest",
    "ContractCreateRequest", "KpiResultRequest", "PilotCompleteRequest",
    "FinalDecisionRequest",
    # system
    "KnowledgeBaseEntryResponse", "SimilarPilotMatch", "SimilarPilotsResponse",
    "SimilarPilotsRequest", "NotificationResponse", "UnreadCountResponse",
    "AdminUserResponse", "SetActiveRequest", "AuditLogResponse",
]
