"""The problem analyzer.

A department writes what is wrong in plain language.  The analyzer turns that
into a structure an officer can review: the problem restated, the capabilities a
solution needs, the outcomes expected, and measurable KPIs to judge a pilot by.

Three things it will not do:

* It never supplies a budget, a timeline or a location.  Those come from the
  department or they go into missing_fields and block publishing.  The model's
  output for those fields is discarded without being read.
* It never decides eligibility.  That is rule-based and lives elsewhere.
* It never invents its way past a schema failure.  One retry, then the
  deterministic template, which proposes what to measure but leaves every target
  blank for the officer to fill.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError

from app.enums import KpiDirection
from app.services import llm

# The three fields the department owns.  The analyzer echoes them or reports
# them missing; it never fills them.
DEPARTMENT_ONLY_FIELDS = ("budget", "timeline", "location")

# Named separately because the officer must fill these before KPIs can lock.
MISSING_KPI_TARGETS = "suggested_kpi_targets"


class SuggestedKpi(BaseModel):
    """A candidate KPI.

    target_value is optional because the template fallback proposes what to
    measure without inventing a number to hit.  The officer supplies targets
    before approval, and approval is what locks them.
    """

    name: str = Field(min_length=1)
    target_value: Decimal | None = None
    unit: str = Field(min_length=1)
    measurement_method: str = Field(min_length=1)
    # Required, so achievement can never be judged by a bare comparison.
    direction: KpiDirection


class AnalysisResult(BaseModel):
    """The strict schema every analyzer response is validated against."""

    problem_statement: str = Field(min_length=1)
    required_capabilities: list[str]
    expected_outcomes: list[str]
    suggested_kpis: list[SuggestedKpi]
    missing_fields: list[str]

    # Echoed back only when the department supplied them.
    budget: Decimal | None = None
    timeline: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class AnalysisOutcome:
    """The result, plus an honest account of how it was produced."""

    result: AnalysisResult
    source: str  # "llm" or "template"
    attempts: int
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            **self.result.model_dump(mode="json"),
            "source": self.source,
            "attempts": self.attempts,
            "notes": self.notes,
        }


SYSTEM_PROMPT = """You structure public-sector procurement problems for the Government of
Maharashtra. You return only JSON, matching this shape exactly:

{
  "problem_statement": "one clear sentence restating the problem",
  "required_capabilities": ["capability a solution must have", ...],
  "expected_outcomes": ["what success looks like in the field", ...],
  "suggested_kpis": [
    {
      "name": "what is measured",
      "target_value": 85,
      "unit": "percent",
      "measurement_method": "how the department will verify it",
      "direction": "HIGHER_IS_BETTER" or "LOWER_IS_BETTER"
    }
  ],
  "missing_fields": []
}

Rules you must follow:
- Never state a budget, a timeline, a deadline or a location. If the text mentions any,
  ignore it. Those come from the department through a separate field.
- Never state an eligibility criterion, a turnover requirement, or who may bid.
- direction says which way is good: LOWER_IS_BETTER for waiting times, delays, leakage,
  failures and costs; HIGHER_IS_BETTER for coverage, accuracy, uptime and adoption.
- Every KPI must be something a department can actually measure.
- Return JSON only, with no commentary."""


def _user_prompt(description: str) -> str:
    return f"Structure this problem:\n\n{description.strip()}"


def _retry_prompt(description: str, error: str) -> str:
    return (
        f"{_user_prompt(description)}\n\n"
        f"Your previous response did not match the schema. The validation error was:\n"
        f"{error}\n\nReturn corrected JSON only."
    )


def _missing_from(budget, timeline, location) -> list[str]:
    """Which of the department-owned fields were not supplied."""
    supplied = {"budget": budget, "timeline": timeline, "location": location}
    return [name for name in DEPARTMENT_ONLY_FIELDS if not supplied[name]]


def _apply_department_fields(
    result: AnalysisResult,
    budget: Decimal | None,
    timeline: str | None,
    location: str | None,
) -> AnalysisResult:
    """Overwrite the model's view of the department-owned fields with the truth.

    Whatever the model said about budget, timeline or location is discarded here.
    This is the guarantee that no constraint is ever invented.
    """
    missing = _missing_from(budget, timeline, location)
    if any(kpi.target_value is None for kpi in result.suggested_kpis):
        missing.append(MISSING_KPI_TARGETS)

    return result.model_copy(
        update={
            "budget": budget,
            "timeline": timeline,
            "location": location,
            "missing_fields": missing,
        }
    )


# ---------------------------------------------------------------------------
# The deterministic template fallback
# ---------------------------------------------------------------------------

# Verbs a department uses, and the capability each implies. Matching is literal:
# the capability is only claimed when the department's own words support it.
CAPABILITY_CUES = [
    (("detect", "detection", "identify", "spot"), "Detection of the reported condition"),
    (("monitor", "monitoring", "track", "tracking"), "Continuous monitoring and telemetry"),
    (("predict", "forecast", "early warning"), "Prediction or early warning"),
    (("map", "mapping", "survey", "census"), "Survey and mapping"),
    (("report", "reporting", "dashboard"), "Reporting to department staff"),
    (("alert", "notify", "notification"), "Alerting the responsible staff"),
    (("inspect", "inspection"), "Inspection support"),
    (("route", "routing", "schedule", "scheduling"), "Routing or scheduling"),
    (("verify", "verification", "validate"), "Verification of results in the field"),
    (("offline", "low connectivity", "no network"), "Operation with poor connectivity"),
]

# What to measure, given what the department is trying to do. Each entry names a
# unit and a direction but never a target: the template proposes measurement, and
# the officer supplies the number.
KPI_CUES = [
    (
        ("detect", "detection", "identify", "leak", "fault", "failure"),
        ("Detection accuracy", "percent", KpiDirection.HIGHER_IS_BETTER,
         "Field verification of flagged cases against what was actually found"),
    ),
    (
        ("delay", "time", "response", "wait", "late", "slow"),
        ("Response time", "hours", KpiDirection.LOWER_IS_BETTER,
         "Time from the event to the department acting on it, sampled weekly"),
    ),
    (
        ("cover", "coverage", "reach", "households", "citizens", "students", "farmers"),
        ("Coverage of the target population", "percent", KpiDirection.HIGHER_IS_BETTER,
         "Departmental records compared with the registered population"),
    ),
    (
        ("cost", "saving", "waste", "loss", "losses", "revenue"),
        ("Reduction against the current baseline", "percent", KpiDirection.HIGHER_IS_BETTER,
         "Departmental records for the pilot area against the preceding period"),
    ),
    (
        ("uptime", "reliable", "availability", "downtime"),
        ("System availability", "percent", KpiDirection.HIGHER_IS_BETTER,
         "Share of days the system reported valid data"),
    ),
    (
        ("adopt", "adoption", "use", "staff", "training", "teacher", "worker"),
        ("Staff adoption", "percent", KpiDirection.HIGHER_IS_BETTER,
         "Share of trained staff using the system in a normal week"),
    ),
]

FALLBACK_KPI = (
    "Departmental acceptance of the pilot result",
    "percent",
    KpiDirection.HIGHER_IS_BETTER,
    "Sign-off by the department against the agreed scope at pilot closure",
)


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    match = re.search(r"^(.{20,240}?[.!?])(\s|$)", cleaned)
    return match.group(1).strip() if match else cleaned[:240].strip()


def template_analysis(description: str) -> AnalysisResult:
    """A deterministic structuring of the department's own words.

    Same input, same output, every time, with no network.  It proposes what to
    measure and never how much: every target_value is left empty for the officer.
    """
    lowered = description.lower()

    capabilities = [
        capability for cues, capability in CAPABILITY_CUES if any(cue in lowered for cue in cues)
    ]
    if not capabilities:
        capabilities = ["Capabilities to be confirmed by the officer from the description"]

    kpis: list[SuggestedKpi] = []
    seen: set[str] = set()
    for cues, (name, unit, direction, method) in KPI_CUES:
        if any(cue in lowered for cue in cues) and name not in seen:
            seen.add(name)
            kpis.append(
                SuggestedKpi(
                    name=name,
                    target_value=None,
                    unit=unit,
                    measurement_method=method,
                    direction=direction,
                )
            )
    if not kpis:
        name, unit, direction, method = FALLBACK_KPI
        kpis.append(
            SuggestedKpi(
                name=name,
                target_value=None,
                unit=unit,
                measurement_method=method,
                direction=direction,
            )
        )

    statement = _first_sentence(description)
    return AnalysisResult(
        problem_statement=statement,
        required_capabilities=capabilities,
        expected_outcomes=[
            f"The department can show a measurable improvement on: {statement}",
            "The result is verified by someone other than the supplier.",
        ],
        suggested_kpis=kpis,
        missing_fields=[],
    )


# ---------------------------------------------------------------------------
# The analyzer itself
# ---------------------------------------------------------------------------


def analyze(
    description: str,
    *,
    budget: Decimal | None = None,
    timeline: str | None = None,
    location: str | None = None,
) -> AnalysisOutcome:
    """Structure a problem, from the LLM when configured and the template otherwise."""

    notes: list[str] = []

    if not llm.is_configured():
        notes.append(
            "No LLM provider configured, so the deterministic template was used. "
            "It proposes what to measure and leaves every target for the officer."
        )
        result = _apply_department_fields(
            template_analysis(description), budget, timeline, location
        )
        return AnalysisOutcome(result=result, source="template", attempts=0, notes=notes)

    prompts = [_user_prompt(description)]
    attempts = 0
    last_error = ""

    # One attempt, then exactly one retry that shows the model its own error.
    while attempts < 2:
        attempts += 1
        try:
            raw = llm.complete_json(SYSTEM_PROMPT, prompts[-1])
            parsed = llm.extract_json(raw)
            result = AnalysisResult.model_validate(parsed)
        except (ValidationError, json.JSONDecodeError) as error:
            last_error = str(error)
            notes.append(f"Attempt {attempts} did not match the schema.")
            prompts.append(_retry_prompt(description, last_error))
            continue
        except llm.LlmUnavailable as error:
            last_error = str(error)
            notes.append(f"Attempt {attempts} could not reach the provider: {error}")
            break

        result = _apply_department_fields(result, budget, timeline, location)
        return AnalysisOutcome(result=result, source="llm", attempts=attempts, notes=notes)

    notes.append(
        "Falling back to the deterministic template rather than inventing values. "
        f"Last error: {last_error}"
    )
    result = _apply_department_fields(template_analysis(description), budget, timeline, location)
    return AnalysisOutcome(result=result, source="template", attempts=attempts, notes=notes)
