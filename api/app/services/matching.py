"""The matching engine.

A ranked shortlist with an overall score and six sub-scores, each carrying a
short reason.  Never a bare number: an officer has to be able to explain to a
declined startup exactly what they were marked down on, and a startup has to be
able to read the same thing in its own portal.

Two rules shape the scoring more than anything else:

* Experience adds to a score and never gates one.  A company with no track
  record at all still ranks, because the pilot is what proves reliability here.
* Proximity counts only when the challenge actually requires people on site, and
  even then it never excludes a bidder.

Weights are fixed shares of one score, written here as the composition of the
score itself rather than as tunable policy.  Nothing in this module reads or
imposes a procurement threshold; qualification against MIN_TECH_SCORE happens in
the rules-driven engines that consume these scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import KpiStatus, PilotOutcome
from app.models import Challenge, Company, Kpi, Pilot
from app.services import embeddings

# The six criteria, and the share of the overall score each carries.
# These are the definition of the composite score, not procurement thresholds.
CRITERIA_WEIGHTS = {
    "technology_fit": 0.30,
    "relevant_experience": 0.20,
    "kpi_compatibility": 0.15,
    "deployment_readiness": 0.15,
    "team_capability": 0.10,
    "security_compliance": 0.10,
}

# Proximity is a separate, additive consideration, applied only when the
# challenge requires people on site. It can lift a score and never lower one.
ONSITE_PROXIMITY_BONUS = 5.0

SCORE_MAX = 100.0

VERIFIED = "VERIFIED"
SELF_DECLARED = "SELF_DECLARED"


@dataclass(frozen=True)
class SubScore:
    criterion: str
    score: float
    weight: float
    reason: str

    def as_dict(self) -> dict:
        return {
            "criterion": self.criterion,
            "score": round(self.score, 2),
            "weight": self.weight,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MatchResult:
    company_id: int
    company_name: str
    total_score: float
    sub_scores: list[SubScore]
    proximity: dict
    track_record: dict
    explanation: str

    def as_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "total_score": round(self.total_score, 2),
            "sub_scores": [sub.as_dict() for sub in self.sub_scores],
            "proximity": self.proximity,
            "track_record": self.track_record,
            "explanation": self.explanation,
            "disclaimer": (
                "Prototype-generated score, not an official evaluation criterion."
            ),
        }


# ---------------------------------------------------------------------------
# Track record
# ---------------------------------------------------------------------------


def track_record(db: Session, company_id: int) -> dict:
    """What a company has actually done, split by how well it is evidenced.

    VERIFIED work was completed on this platform with KPIs validated by someone
    other than the supplier.  SELF_DECLARED is the company's own account of
    itself, which counts for less and is labelled as such.
    """
    verified_kpis = db.scalars(
        select(Kpi).where(Kpi.startup_id == company_id, Kpi.status == KpiStatus.VERIFIED)
    ).all()

    met = [kpi for kpi in verified_kpis if kpi_met(kpi)]
    pilots = db.scalars(select(Pilot).where(Pilot.startup_id == company_id)).all()
    scaled = [pilot for pilot in pilots if pilot.outcome is PilotOutcome.SCALE]

    return {
        "evidence": VERIFIED if verified_kpis else SELF_DECLARED,
        "verified_kpis": len(verified_kpis),
        "verified_kpis_met": len(met),
        "pilots_completed": len(pilots),
        "pilots_scaled": len(scaled),
    }


def kpi_met(kpi: Kpi) -> bool:
    """Did a validated KPI hit its target?

    Direction decides the comparison. A validated 6 minutes against a target of 7
    is a success; a validated 93 percent against a target of 95 is not. Comparing
    the numbers without the direction would get one of those backwards.
    """
    if kpi.validated_value is None or kpi.target_value is None:
        return False
    if kpi.direction.value == "LOWER_IS_BETTER":
        return kpi.validated_value <= kpi.target_value
    return kpi.validated_value >= kpi.target_value


# ---------------------------------------------------------------------------
# The individual criteria
# ---------------------------------------------------------------------------


def _semantic_fit(challenge: Challenge, company: Company) -> tuple[float, str]:
    """How close the company's stated capability is to what the challenge needs."""
    similarity = embeddings.cosine_similarity(challenge.embedding, company.embedding)
    if similarity is None:
        return (
            SCORE_MAX / 2,
            "No embedding available for this pair, so technology fit is held at the "
            "midpoint rather than guessed either way.",
        )

    # Cosine runs -1..1; the useful range here is 0..1 and negatives mean unrelated.
    score = max(0.0, min(1.0, similarity)) * SCORE_MAX
    return (
        score,
        f"Capability profile matches the challenge text with a cosine similarity of "
        f"{similarity:.3f}.",
    )


def _experience(record: dict) -> tuple[float, str]:
    """Experience adds to the score. It never gates.

    A company with nothing on record starts at zero here and can still win on the
    other five criteria - which is the whole point of a KPI-tracked pilot.
    """
    if record["evidence"] == SELF_DECLARED:
        return (
            0.0,
            "No platform-verified delivery yet, so this criterion adds nothing. It does "
            "not exclude the bidder: a pilot is how a first-time supplier proves itself.",
        )

    met_ratio = record["verified_kpis_met"] / record["verified_kpis"]
    scaled_bonus = min(record["pilots_scaled"], 2) / 2
    score = (met_ratio * 0.7 + scaled_bonus * 0.3) * SCORE_MAX
    return (
        score,
        f"VERIFIED track record: {record['verified_kpis_met']} of {record['verified_kpis']} "
        f"validated KPIs met their target across {record['pilots_completed']} completed "
        f"pilot(s), {record['pilots_scaled']} of which were scaled.",
    )


def _kpi_compatibility(db: Session, challenge: Challenge, record: dict) -> tuple[float, str]:
    """Has this company been measured on this kind of thing before?"""
    challenge_kpis = db.scalars(
        select(Kpi).where(Kpi.challenge_id == challenge.id, Kpi.startup_id.is_(None))
    ).all()
    if not challenge_kpis:
        return (
            SCORE_MAX / 2,
            "The challenge has no approved KPIs yet, so compatibility is held at the "
            "midpoint.",
        )
    if record["evidence"] == SELF_DECLARED:
        return (
            SCORE_MAX / 2,
            f"The challenge sets {len(challenge_kpis)} KPI(s). The bidder has no validated "
            f"KPI history, so there is nothing to compare against yet.",
        )

    met_ratio = record["verified_kpis_met"] / record["verified_kpis"]
    return (
        met_ratio * SCORE_MAX,
        f"The bidder has met {record['verified_kpis_met']} of {record['verified_kpis']} "
        f"validated KPI targets on past work, against the {len(challenge_kpis)} KPI(s) "
        f"this challenge sets.",
    )


def _deployment_readiness(company: Company, record: dict) -> tuple[float, str]:
    """Can they actually put this in the field?"""
    signals = []
    score = 0.0

    if record["pilots_completed"]:
        score += SCORE_MAX * 0.5
        signals.append(f"{record['pilots_completed']} completed pilot(s) on the platform")
    if company.employee_count:
        score += SCORE_MAX * 0.3
        signals.append(f"a team of {company.employee_count}")
    if company.district:
        score += SCORE_MAX * 0.2
        signals.append(f"an operating base in {company.district}")

    if not signals:
        return (0.0, "No deployment signals on record.")
    return (min(score, SCORE_MAX), "Deployment signals: " + ", ".join(signals) + ".")


def _team_capability(company: Company, as_of: date) -> tuple[float, str]:
    """Size and how long the team has been at it, as far as the record shows."""
    if not company.employee_count:
        return (0.0, "No team size on record.")

    # A larger team and a longer run both help, with diminishing returns.
    size_part = min(company.employee_count / 50, 1.0) * 0.6
    years = 0
    if company.incorporation_date:
        years = as_of.year - company.incorporation_date.year
    age_part = min(years / 5, 1.0) * 0.4

    return (
        (size_part + age_part) * SCORE_MAX,
        f"A team of {company.employee_count}, operating for {years} year(s).",
    )


def _security_compliance(company: Company, record: dict) -> tuple[float, str]:
    """What the platform can actually evidence about compliance.

    The prototype records no certifications, so this reflects only what is on
    file: formal registration, and delivery already accepted by a department.
    """
    score = 0.0
    signals = []
    if company.incorporation_date:
        score += SCORE_MAX * 0.4
        signals.append("formally registered")
    if company.dpiit_recognised:
        score += SCORE_MAX * 0.2
        signals.append("recognised startup")
    if record["evidence"] == VERIFIED:
        score += SCORE_MAX * 0.4
        signals.append("already delivered under a departmental pilot")

    if not signals:
        return (
            0.0,
            "Nothing on file. The prototype records no security certifications, so this "
            "criterion reflects registration and past departmental delivery only.",
        )
    return (
        score,
        "On file: " + ", ".join(signals) + ". No security certifications are recorded by "
        "this prototype, so this is not a compliance audit.",
    )


def _proximity(challenge: Challenge, company: Company) -> tuple[float, dict]:
    """Proximity, which counts only when the work requires being there.

    It is additive and never subtractive, so a distant bidder is never excluded -
    only a local one is credited for the travel it saves.
    """
    if not challenge.requires_onsite:
        return (
            0.0,
            {
                "applied": False,
                "reason": (
                    "This challenge does not require work on site, so location has no "
                    "bearing on the ranking."
                ),
            },
        )

    same_district = bool(
        challenge.district and company.district and challenge.district == company.district
    )
    if same_district:
        return (
            ONSITE_PROXIMITY_BONUS,
            {
                "applied": True,
                "reason": (
                    f"On-site work is required and the bidder operates in "
                    f"{company.district}, so a proximity credit applies."
                ),
            },
        )
    return (
        0.0,
        {
            "applied": True,
            "reason": (
                f"On-site work is required and the bidder operates in "
                f"{company.district or 'an unrecorded district'} rather than "
                f"{challenge.district}. No credit applies, and no penalty either: "
                f"distance never excludes a bidder."
            ),
        },
    )


# ---------------------------------------------------------------------------
# The composite score
# ---------------------------------------------------------------------------


def score_company(
    db: Session,
    challenge: Challenge,
    company: Company,
    *,
    as_of: date | None = None,
) -> MatchResult:
    """Score one company against one challenge, with a reason for every criterion."""

    as_of = as_of or date.today()
    record = track_record(db, company.id)

    computed = {
        "technology_fit": _semantic_fit(challenge, company),
        "relevant_experience": _experience(record),
        "kpi_compatibility": _kpi_compatibility(db, challenge, record),
        "deployment_readiness": _deployment_readiness(company, record),
        "team_capability": _team_capability(company, as_of),
        "security_compliance": _security_compliance(company, record),
    }

    sub_scores = [
        SubScore(
            criterion=criterion,
            score=computed[criterion][0],
            weight=weight,
            reason=computed[criterion][1],
        )
        for criterion, weight in CRITERIA_WEIGHTS.items()
    ]

    weighted = sum(sub.score * sub.weight for sub in sub_scores)
    proximity_bonus, proximity = _proximity(challenge, company)
    total = min(weighted + proximity_bonus, SCORE_MAX)

    explanation = (
        f"{company.name} scores {total:.1f} out of 100. "
        + " ".join(f"{sub.criterion}: {sub.score:.0f}." for sub in sub_scores)
        + f" Track record evidence: {record['evidence']}."
    )

    return MatchResult(
        company_id=company.id,
        company_name=company.name,
        total_score=total,
        sub_scores=sub_scores,
        proximity=proximity,
        track_record=record,
        explanation=explanation,
    )


def rank(
    db: Session,
    challenge: Challenge,
    companies: list[Company],
    *,
    as_of: date | None = None,
) -> list[MatchResult]:
    """Rank a field. Everyone passed in is ranked; nobody is filtered out here."""
    results = [score_company(db, challenge, company, as_of=as_of) for company in companies]
    results.sort(key=lambda result: (-result.total_score, result.company_name))
    return results


def as_sub_scores_json(result: MatchResult) -> dict:
    """The shape stored on proposal.sub_scores."""
    return {
        "total_score": round(result.total_score, 2),
        "criteria": [sub.as_dict() for sub in result.sub_scores],
        "proximity": result.proximity,
        "track_record": result.track_record,
        "explanation": result.explanation,
        "disclaimer": "Prototype-generated score, not an official evaluation criterion.",
    }


def decimal_score(result: MatchResult) -> Decimal:
    return Decimal(f"{result.total_score:.2f}")
