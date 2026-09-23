"""
Query layer.

One module per aggregate, mirroring the Spring Data repositories. Keeping the
queries here rather than inline in the services means the ownership and
visibility rules in the service layer read as business logic rather than as
SQLAlchemy, and it gives the AI code one obvious place to look for an existing
query instead of writing a second one.
"""
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.pilot_repository import (
    KnowledgeBaseRepository,
    PilotRepository,
)
from app.repositories.proposal_repository import DocumentRepository, ProposalRepository
from app.repositories.startup_repository import StartupRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "ChallengeRepository",
    "DocumentRepository",
    "EvaluationRepository",
    "KnowledgeBaseRepository",
    "NotificationRepository",
    "PilotRepository",
    "ProposalRepository",
    "StartupRepository",
    "UserRepository",
]
