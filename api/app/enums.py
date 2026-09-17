"""Every enumerated value in the domain, in one place.

These are value sets (the vocabulary of the domain), not thresholds.
Thresholds, limits and percentages belong in the procurement_rules table.
"""

import enum


class CompanyType(str, enum.Enum):
    STARTUP = "STARTUP"
    LEGACY = "LEGACY"
    SME = "SME"
    GOVERNMENT = "GOVERNMENT"


class UserRole(str, enum.Enum):
    GOVERNMENT = "GOVERNMENT"
    STARTUP = "STARTUP"
    EXPERT = "EXPERT"
    ADMIN = "ADMIN"


class Level(str, enum.Enum):
    """Used for both criticality and innovation_potential."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Tier(str, enum.Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class ChallengeStatus(str, enum.Enum):
    DRAFT = "DRAFT"              # free text captured, not analyzed yet
    ANALYZED = "ANALYZED"        # AI analyzer has produced a structured spec
    APPROVED = "APPROVED"        # officer approved the spec and locked the KPIs
    PUBLISHED = "PUBLISHED"      # open for proposals
    EVALUATION = "EVALUATION"    # bid window closed, proposals being evaluated
    PILOT = "PILOT"              # a pilot is running
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class KpiDirection(str, enum.Enum):
    """Which way a KPI is good.

    Achievement can never be judged by comparing a validated value with a target
    alone: "wait time of 6 minutes against a target of 7" is a success and
    "uptime of 93 percent against a target of 95" is not, and the numbers alone
    cannot tell them apart.  Every KPI therefore declares its direction.
    """

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class KpiStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ProposalStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    DECLINED = "DECLINED"
    AWARDED = "AWARDED"
    WITHDRAWN = "WITHDRAWN"


class DeclineReasonCode(str, enum.Enum):
    """Fixed vocabulary - a decline must always carry one of these."""

    FAILED_GENERAL_ELIGIBILITY = "FAILED_GENERAL_ELIGIBILITY"
    FAILED_STARTUP_LANE_ELIGIBILITY = "FAILED_STARTUP_LANE_ELIGIBILITY"
    BELOW_TECHNICAL_SCORE_THRESHOLD = "BELOW_TECHNICAL_SCORE_THRESHOLD"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    KPI_TARGETS_NOT_ADDRESSED = "KPI_TARGETS_NOT_ADDRESSED"
    DEPLOYMENT_READINESS_INSUFFICIENT = "DEPLOYMENT_READINESS_INSUFFICIENT"
    SECURITY_COMPLIANCE_GAP = "SECURITY_COMPLIANCE_GAP"
    INCOMPLETE_SUBMISSION = "INCOMPLETE_SUBMISSION"
    ROTATION_RULE_APPLIED = "ROTATION_RULE_APPLIED"
    STRONGER_ALTERNATIVE_SELECTED = "STRONGER_ALTERNATIVE_SELECTED"
    TIER_ACCESS_RESTRICTION = "TIER_ACCESS_RESTRICTION"


class PilotStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    EVIDENCE_SUBMITTED = "EVIDENCE_SUBMITTED"
    VALIDATED = "VALIDATED"
    CLOSED = "CLOSED"


class PilotOutcome(str, enum.Enum):
    SCALE = "SCALE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


class PartnershipStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class RuleType(str, enum.Enum):
    AMOUNT = "AMOUNT"          # money, in INR
    PERCENTAGE = "PERCENTAGE"  # 0-100
    COUNT = "COUNT"            # a number of things
    DAYS = "DAYS"              # a duration
    SCORE = "SCORE"            # a point on the 0-100 scoring scale
