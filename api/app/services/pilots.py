"""Pilot planning and the Scale / Modify / Reject recommendation.

The LLM drafts milestones from the approved KPIs, and an officer edits and
approves them.  The recommendation at the end is not an LLM output at all: it is
computed from validated KPI results and schedule adherence, so the same pilot
always produces the same recommendation.

And a recommendation is only ever a recommendation.  It has no effect until an
officer records a decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import KpiStatus, PilotOutcome
from app.models import Challenge, Kpi, Pilot
from app.services import llm
from app.services.matching import kpi_met


# ---------------------------------------------------------------------------
# Milestone drafting
# ---------------------------------------------------------------------------

MILESTONE_SYSTEM_PROMPT = """You draft pilot milestones for a government department.
Return JSON only, shaped exactly like this:

{"milestones": [
  {"name": "short milestone name",
   "purpose": "what this milestone establishes",
   "kpi_checkpoint": "which KPI is measured here, or 'none' for setup milestones"}
]}

Rules:
- Never invent a date, a duration, a budget or a payment amount. The officer sets those.
- Every KPI named must be one of the KPIs you were given.
- The last milestone must measure every KPI for closure.
- Return JSON only."""


@dataclass(frozen=True)
class MilestoneDraft:
    milestones: list[dict]
    source: str
    notes: list[str]

    def as_dict(self) -> dict:
        return {"milestones": self.milestones, "source": self.source, "notes": self.notes}


def template_milestones(kpis: list[Kpi]) -> list[dict]:
    """A deterministic plan built from the approved KPIs and nothing else.

    It carries no dates and no amounts: those are the officer's to set, and
    inventing them would be inventing a constraint.
    """
    names = [kpi.name for kpi in kpis]
    plan = [
        {
            "name": "Baseline and site readiness",
            "purpose": (
                "Record the current position for every KPI before anything changes, so "
                "the pilot has something to be measured against."
            ),
            "kpi_checkpoint": "Baseline reading for: " + ", ".join(names)
            if names
            else "none",
        },
        {
            "name": "Deployment in the pilot area",
            "purpose": "Install and configure the solution in the agreed pilot scope.",
            "kpi_checkpoint": "none",
        },
    ]
    for kpi in kpis:
        plan.append(
            {
                "name": f"Mid-pilot checkpoint: {kpi.name}",
                "purpose": (
                    f"Check progress towards the target of {kpi.target_value} "
                    f"{kpi.unit or ''}".strip()
                    + f", measured by: {kpi.measurement_method}"
                ),
                "kpi_checkpoint": kpi.name,
            }
        )
    plan.append(
        {
            "name": "Pilot closure and independent validation",
            "purpose": (
                "Submit evidence for every KPI. Validation is done by someone other "
                "than the supplier."
            ),
            "kpi_checkpoint": ", ".join(names) if names else "none",
        }
    )
    return plan


def draft_milestones(kpis: list[Kpi]) -> MilestoneDraft:
    """Draft a milestone plan: from the LLM when configured, the template otherwise."""
    notes: list[str] = []

    if not llm.is_configured():
        notes.append(
            "No LLM provider configured, so the deterministic template was used. The "
            "plan carries no dates or amounts: the officer sets those."
        )
        return MilestoneDraft(template_milestones(kpis), "template", notes)

    listing = "\n".join(
        f"- {kpi.name}: target {kpi.target_value} {kpi.unit or ''} "
        f"({kpi.direction.value}), measured by {kpi.measurement_method}"
        for kpi in kpis
    )
    try:
        raw = llm.complete_json(
            MILESTONE_SYSTEM_PROMPT, f"Approved KPIs for this pilot:\n{listing}"
        )
        parsed = llm.extract_json(raw)
        milestones = parsed["milestones"]
        if not isinstance(milestones, list) or not milestones:
            raise ValueError("no milestones returned")
        return MilestoneDraft(milestones, "llm", notes)
    except Exception as error:
        notes.append(f"LLM drafting failed ({error}); used the deterministic template.")
        return MilestoneDraft(template_milestones(kpis), "template", notes)


# ---------------------------------------------------------------------------
# The recommendation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    outcome: PilotOutcome
    kpis_total: int
    kpis_met: int
    kpis_missed: int
    on_schedule: bool | None
    reasoning: list[str]
    kpi_detail: list[dict]

    def as_dict(self) -> dict:
        return {
            "recommended_outcome": self.outcome.value,
            "kpis_total": self.kpis_total,
            "kpis_met": self.kpis_met,
            "kpis_missed": self.kpis_missed,
            "on_schedule": self.on_schedule,
            "reasoning": self.reasoning,
            "kpi_detail": self.kpi_detail,
            "status": (
                "Recommendation only. It has no effect until an officer records a decision."
            ),
        }


class RecommendationNotReady(ValueError):
    """Every KPI has to be validated before a pilot can be judged."""


def schedule_adherence(pilot: Pilot) -> tuple[bool | None, str]:
    """Did the pilot finish by the date the officer planned?"""
    if pilot.completed_on is None or pilot.planned_end_on is None:
        return (
            None,
            "Schedule adherence is unknown: the pilot has no recorded completion date, "
            "or no planned end date to compare it with.",
        )
    if pilot.completed_on <= pilot.planned_end_on:
        return (
            True,
            f"Completed {pilot.completed_on} against a planned end of "
            f"{pilot.planned_end_on}: on schedule.",
        )
    return (
        False,
        f"Completed {pilot.completed_on} against a planned end of "
        f"{pilot.planned_end_on}: behind schedule.",
    )


def recommend(db: Session, pilot: Pilot) -> Recommendation:
    """Compute Scale, Modify or Reject from validated results alone.

    Deterministic by construction: the same validated values and the same dates
    always give the same answer, because nothing here is sampled, weighted or
    asked of a model.

    The rule is structural rather than proportional - every target met, some met,
    or none met - so it introduces no threshold of its own.
    """
    kpis = db.scalars(
        select(Kpi).where(Kpi.challenge_id == pilot.challenge_id, Kpi.startup_id == pilot.startup_id)
    ).all()

    if not kpis:
        raise RecommendationNotReady(
            "This pilot has no KPIs recorded against the supplier, so there is nothing to judge."
        )

    unvalidated = [kpi for kpi in kpis if kpi.status is not KpiStatus.VERIFIED]
    if unvalidated:
        raise RecommendationNotReady(
            "Every KPI must be independently validated first. Still outstanding: "
            + ", ".join(f"{kpi.name} ({kpi.status.value})" for kpi in unvalidated)
        )

    detail = []
    met_count = 0
    for kpi in kpis:
        met = kpi_met(kpi)
        met_count += met
        comparison = "at or below" if kpi.direction.value == "LOWER_IS_BETTER" else "at or above"
        detail.append(
            {
                "name": kpi.name,
                "target_value": str(kpi.target_value),
                "validated_value": str(kpi.validated_value),
                "unit": kpi.unit,
                "direction": kpi.direction.value,
                "met": met,
                "reason": (
                    f"Validated {kpi.validated_value} {kpi.unit or ''} against a target of "
                    f"{kpi.target_value}, which this KPI meets by being {comparison} target: "
                    f"{'met' if met else 'not met'}."
                ).strip(),
            }
        )

    on_schedule, schedule_reason = schedule_adherence(pilot)
    all_met = met_count == len(kpis)
    none_met = met_count == 0

    reasoning = [
        f"{met_count} of {len(kpis)} validated KPIs met their target.",
        schedule_reason,
    ]

    if none_met:
        outcome = PilotOutcome.REJECT
        reasoning.append(
            "No validated KPI met its target, so the pilot does not support scaling."
        )
    elif all_met and on_schedule is True:
        outcome = PilotOutcome.SCALE
        reasoning.append(
            "Every validated KPI met its target and the pilot finished on schedule."
        )
    elif all_met and on_schedule is False:
        outcome = PilotOutcome.MODIFY
        reasoning.append(
            "Every validated KPI met its target, but the pilot did not finish on schedule, "
            "so the delivery plan needs revisiting before scaling."
        )
    elif all_met:
        # Unknown is not the same as late, and saying so would be wrong.
        outcome = PilotOutcome.MODIFY
        reasoning.append(
            "Every validated KPI met its target, but schedule adherence could not be "
            "confirmed from the record, so scaling is not recommended on this evidence "
            "alone. Record the completion date to resolve it."
        )
    else:
        outcome = PilotOutcome.MODIFY
        reasoning.append(
            "Some targets were met and some were not, so the scope is worth revising "
            "rather than scaling or abandoning."
        )

    return Recommendation(
        outcome=outcome,
        kpis_total=len(kpis),
        kpis_met=met_count,
        kpis_missed=len(kpis) - met_count,
        on_schedule=on_schedule,
        reasoning=reasoning,
        kpi_detail=detail,
    )


# ---------------------------------------------------------------------------
# Expert briefing
# ---------------------------------------------------------------------------


def evaluation_summary(challenge: Challenge, company, match_explanation: str) -> dict:
    """An AI-assisted summary for the expert, sat next to the manual rubric.

    It summarises; it does not score. The expert's own marks are recorded
    separately from anything computed.
    """
    if not llm.is_configured():
        return {
            "source": "template",
            "summary": (
                f"{company.name} has bid on '{challenge.title}'. "
                f"Their stated capability: {(company.profile_text or '').strip()} "
                f"Computed match: {match_explanation}"
            ),
            "note": (
                "Assembled from the record without an LLM. It is a summary for the "
                "evaluator to read, not a score."
            ),
        }

    try:
        text = llm.complete_json(
            "You summarise a supplier's bid for a government evaluator. Return JSON: "
            '{"summary": "...", "questions_for_the_evaluator": ["..."]}. '
            "Never score the bid, never recommend an outcome, and never state eligibility.",
            f"Challenge: {challenge.title}\n{challenge.description_raw}\n\n"
            f"Bidder: {company.name}\nProfile: {company.profile_text}\n\n"
            f"Computed match: {match_explanation}",
        )
        parsed = llm.extract_json(text)
        return {
            "source": "llm",
            "summary": parsed.get("summary", ""),
            "questions_for_the_evaluator": parsed.get("questions_for_the_evaluator", []),
            "note": "AI-assisted summary. The score below is the evaluator's own.",
        }
    except Exception as error:
        return {
            "source": "template",
            "summary": (
                f"{company.name} has bid on '{challenge.title}'. "
                f"Computed match: {match_explanation}"
            ),
            "note": f"LLM unavailable ({error}); summary assembled from the record.",
        }
