"""
Python mirrors of the 14 native PostgreSQL enum types.

Each class inherits ``str`` so the members serialise to plain JSON strings —
`"GOVERNMENT"`, not `"RoleName.GOVERNMENT"` — which is what the frontend's
union types in `types/index.ts` expect.

:func:`pg_enum` builds the SQLAlchemy column type. Three settings matter and
all three are easy to get wrong:

* ``name`` must be the exact PostgreSQL type name, or SQLAlchemy emits a cast
  against a type that does not exist.
* ``create_type=False`` stops SQLAlchemy trying to ``CREATE TYPE`` — the types
  already exist and are owned by ``database/schema.sql``.
* ``values_callable`` sends the member *values* rather than their Python
  *names*. They are identical here, but relying on that implicitly is how a
  future member like ``IN_PROGRESS = "IN PROGRESS"`` silently breaks.
"""
from __future__ import annotations

from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM as PgEnum


def pg_enum(python_enum: type[Enum], type_name: str) -> PgEnum:
    """SQLAlchemy column type bound to an existing PostgreSQL enum type."""
    return PgEnum(
        python_enum,
        name=type_name,
        create_type=False,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


class RoleName(str, Enum):
    GOVERNMENT = "GOVERNMENT"
    STARTUP = "STARTUP"
    EXPERT = "EXPERT"
    ADMIN = "ADMIN"


class ChallengeStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    MATCHING = "MATCHING"
    SHORTLISTED = "SHORTLISTED"
    PILOT = "PILOT"
    CLOSED = "CLOSED"


class RequirementType(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    TECHNICAL = "TECHNICAL"
    COMPLIANCE = "COMPLIANCE"


class ProposalStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"


class DocumentOwnerType(str, Enum):
    STARTUP = "STARTUP"
    PROPOSAL = "PROPOSAL"


class DocumentType(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    COMPLIANCE = "COMPLIANCE"
    FINANCIAL = "FINANCIAL"
    OTHER = "OTHER"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"


class PilotStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class MilestoneStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    DELAYED = "DELAYED"


class ContractStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    RELEASED = "RELEASED"
    HELD = "HELD"


class RecommendationType(str, Enum):
    SCALE = "SCALE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


class ClientType(str, Enum):
    GOVERNMENT = "GOVERNMENT"
    PRIVATE = "PRIVATE"


class NotificationType(str, Enum):
    MATCH_READY = "MATCH_READY"
    PROPOSAL_SUBMITTED = "PROPOSAL_SUBMITTED"
    PROPOSAL_STATUS_CHANGE = "PROPOSAL_STATUS_CHANGE"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_FLAGGED = "DOCUMENT_FLAGGED"
    EVALUATION_ASSIGNED = "EVALUATION_ASSIGNED"
    EVALUATION_SUBMITTED = "EVALUATION_SUBMITTED"
    SHORTLISTED = "SHORTLISTED"
    PILOT_CREATED = "PILOT_CREATED"
    MILESTONE_DUE = "MILESTONE_DUE"
    MILESTONE_UPDATED = "MILESTONE_UPDATED"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    GENERAL = "GENERAL"


#: Maps each Python enum to its PostgreSQL type name. Used by the Phase 1
#: verification script to assert that every member round-trips.
ENUM_TYPE_NAMES: dict[type[Enum], str] = {
    RoleName: "role_name",
    ChallengeStatus: "challenge_status",
    RequirementType: "requirement_type",
    ProposalStatus: "proposal_status",
    DocumentOwnerType: "document_owner_type",
    DocumentType: "document_type",
    VerificationStatus: "verification_status",
    PilotStatus: "pilot_status",
    MilestoneStatus: "milestone_status",
    ContractStatus: "contract_status",
    PaymentStatus: "payment_status",
    RecommendationType: "recommendation_type",
    ClientType: "client_type",
    NotificationType: "notification_type",
}
