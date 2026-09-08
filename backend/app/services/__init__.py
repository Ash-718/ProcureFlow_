"""
Business logic, ported from the Spring service layer.

Each service takes a `Session` and owns its own transaction boundary: it
`flush`es to obtain server-generated ids and `commit`s once the whole operation
is consistent, mirroring the `@Transactional` methods it replaces.
"""
from app.services.admin_service import AdminService
from app.services.audit_service import Action, AuditService
from app.services.auth_service import AuthService
from app.services.challenge_service import ChallengeService
from app.services.document_service import DocumentService
from app.services.evaluation_scoring import WeightedScore, weighted_total
from app.services.evaluation_service import EvaluationService
from app.services.file_storage import FileStorageService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.matching_service import MatchingService
from app.services.notification_service import NotificationService
from app.services.pilot_service import PilotService
from app.services.proposal_service import ProposalService
from app.services.recommendation_service import RecommendationService
from app.services.startup_service import StartupService

__all__ = [
    "Action", "AdminService", "AuditService", "AuthService", "ChallengeService",
    "DocumentService", "EvaluationService", "FileStorageService",
    "KnowledgeBaseService", "MatchingService", "NotificationService",
    "PilotService", "ProposalService", "RecommendationService",
    "StartupService", "WeightedScore", "weighted_total",
]
