"""
Turns the component scores from scoring.py into the 2-4 "reasons" and 0-2 "gaps"
a government user sees on a match card (Section 5, step 5). Purely template-driven
so it is deterministic and reproducible given the same inputs — no LLM call needed
for this (see docs/ai-matching.md for why we keep this deterministic rather than
polishing it with an LLM).
"""
from __future__ import annotations

from app.ai.scoring import (
    DomainMatchResult,
    ExperienceResult,
    OverallScoreResult,
    TechnologyMatchResult,
)


def build_match_explanation(
    *,
    startup_name: str,
    challenge_domain: str,
    scores: OverallScoreResult,
    tech_result: TechnologyMatchResult,
    domain_result: DomainMatchResult,
    experience_result: ExperienceResult,
    readiness_raw: float,
) -> dict:
    reasons: list[str] = []
    gaps: list[str] = []

    if scores.semantic_similarity >= 65:
        reasons.append(
            "The startup's stated capabilities and past work closely match the problem statement "
            "in overall meaning, not just keywords."
        )

    if tech_result.matched:
        reasons.append(
            f"Covers {len(tech_result.matched)} of {len(tech_result.matched) + len(tech_result.unmatched)} "
            f"desired technologies: {', '.join(tech_result.matched)}."
        )
    if tech_result.unmatched:
        gaps.append(f"No demonstrated capability yet in: {', '.join(tech_result.unmatched)}.")

    if domain_result.matched_via == "capability":
        reasons.append(f"Core capability directly tagged in the '{challenge_domain}' domain.")
    elif domain_result.matched_via == "project":
        reasons.append(f"Has delivered a past project in the '{challenge_domain}' domain.")
    else:
        gaps.append(f"No prior capability or project specifically in '{challenge_domain}'.")

    if experience_result.has_relevant_government_experience:
        govt_titles = ", ".join(p["title"] for p in experience_result.government_projects)
        reasons.append(f"Prior government-sector deployment in this exact domain ({govt_titles}).")
    elif experience_result.relevant_projects:
        reasons.append(
            f"{len(experience_result.relevant_projects)} relevant past project(s) in this domain, "
            "though not yet with a government client."
        )
    else:
        gaps.append("Limited or no government-sector deployment experience in this domain.")

    if readiness_raw >= 75:
        reasons.append(f"High pilot-readiness score ({readiness_raw:.0f}/100) suggesting operational maturity.")
    elif readiness_raw < 50:
        gaps.append(f"Lower pilot-readiness score ({readiness_raw:.0f}/100) may need onboarding support.")

    # Keep within the 2-4 reasons / 0-2 gaps envelope the spec calls for.
    reasons = reasons[:4] if len(reasons) >= 2 else (reasons + ["Reasonable overall alignment with the challenge."])[:4]
    gaps = gaps[:2]

    return {
        "startup_name": startup_name,
        "reasons": reasons,
        "gaps": gaps,
        "component_scores": {
            "semantic_similarity": scores.semantic_similarity,
            "technology_match": scores.technology_match,
            "domain_match": scores.domain_match,
            "experience_score": scores.experience,
            "readiness_score": scores.readiness,
        },
    }
