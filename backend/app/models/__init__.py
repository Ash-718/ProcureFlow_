"""
SQLAlchemy models mapped onto the existing INNOVATE-GOV schema.

Importing this package registers every mapped class on ``Base.metadata``, which
is what lets SQLAlchemy resolve the string-form relationships between modules
(``"Challenge"``, ``"Proposal"``, …). Import the package, not the sub-modules,
or configuration fails with an unresolved-name error at first query.

These models **describe** the schema in `database/schema.sql`; they never
create it. See `app/core/database.py`.
"""
from app.models.challenge import Challenge, ChallengeKpi, ChallengeRequirement
from app.models.enums import (
    ChallengeStatus,
    ClientType,
    ContractStatus,
    DocumentOwnerType,
    DocumentType,
    MilestoneStatus,
    NotificationType,
    PaymentStatus,
    PilotStatus,
    ProposalStatus,
    RecommendationType,
    RequirementType,
    RoleName,
    VerificationStatus,
)
from app.models.evaluation import Evaluation, EvaluationCriterion, EvaluationScore
from app.models.identity import GovernmentDepartment, Role, User
from app.models.knowledge_base import PilotKnowledgeBase
from app.models.matching import AiMatchingConfig, MatchResult
from app.models.pilot import (
    Contract,
    Kpi,
    KpiResult,
    Payment,
    Pilot,
    PilotMilestone,
    Recommendation,
)
from app.models.proposal import Document, Proposal
from app.models.startup import Startup, StartupCapability, StartupProject
from app.models.system import AuditLog, Notification

#: Every mapped class, in dependency order. The Phase 1 verification script
#: walks this list to prove each one round-trips against the live database.
ALL_MODELS = [
    Role, User, GovernmentDepartment,
    Startup, StartupCapability, StartupProject,
    Challenge, ChallengeRequirement, ChallengeKpi,
    MatchResult, AiMatchingConfig,
    Proposal, Document,
    EvaluationCriterion, Evaluation, EvaluationScore,
    Contract, Pilot, PilotMilestone, Payment,
    Kpi, KpiResult, Recommendation,
    PilotKnowledgeBase,
    Notification, AuditLog,
]

__all__ = [
    "ALL_MODELS",
    # identity
    "Role", "User", "GovernmentDepartment",
    # startups
    "Startup", "StartupCapability", "StartupProject",
    # challenges
    "Challenge", "ChallengeRequirement", "ChallengeKpi",
    # matching
    "MatchResult", "AiMatchingConfig",
    # proposals & documents
    "Proposal", "Document",
    # evaluation
    "EvaluationCriterion", "Evaluation", "EvaluationScore",
    # pilots
    "Contract", "Pilot", "PilotMilestone", "Payment",
    "Kpi", "KpiResult", "Recommendation",
    # knowledge base
    "PilotKnowledgeBase",
    # system
    "Notification", "AuditLog",
    # enums
    "RoleName", "ChallengeStatus", "RequirementType", "ProposalStatus",
    "DocumentOwnerType", "DocumentType", "VerificationStatus", "PilotStatus",
    "MilestoneStatus", "ContractStatus", "PaymentStatus", "RecommendationType",
    "ClientType", "NotificationType",
]
