"""
Builds the structured text representations that get embedded (Section 5, steps 1-2).
Kept as plain string templates — deliberately simple and inspectable, since the
whole point of the pipeline is that a judge can read this and see exactly what
goes into the embedding, no hidden magic.
"""
from __future__ import annotations


def build_challenge_text(
    title: str,
    problem_statement: str,
    desired_technology: str | None,
    domain: str,
    outcomes_expected: str | None,
    requirements: list[str],
) -> str:
    parts = [
        f"Challenge: {title}",
        f"Domain: {domain}",
        f"Problem statement: {problem_statement}",
    ]
    if desired_technology:
        parts.append(f"Desired technology: {desired_technology}")
    if outcomes_expected:
        parts.append(f"Expected outcomes: {outcomes_expected}")
    if requirements:
        parts.append("Requirements: " + "; ".join(requirements))
    return "\n".join(parts)


def build_startup_text(
    company_name: str,
    description: str | None,
    capabilities: list[dict],
    projects: list[dict],
    readiness_score: float,
) -> str:
    parts = [f"Startup: {company_name}"]
    if description:
        parts.append(f"Description: {description}")

    if capabilities:
        cap_lines = [
            f"{c['technology_tag']} ({c['domain_tag']}, proficiency {c['proficiency_level']}/5)"
            for c in capabilities
        ]
        parts.append("Capabilities: " + "; ".join(cap_lines))

    if projects:
        proj_lines = [
            f"{p['title']} — {p['domain']} sector, tech: {p['technology_stack']}, "
            f"client: {p['client_type']}, outcome: {p['outcome_summary']}"
            for p in projects
        ]
        parts.append("Past projects: " + "; ".join(proj_lines))

    parts.append(f"Pilot readiness score: {readiness_score}/100")
    return "\n".join(parts)


def build_knowledge_base_text(
    challenge_title: str,
    domain: str,
    technology_tags: list[str],
    outcome_summary: str | None,
    success: bool | None,
) -> str:
    outcome_word = "successful" if success else "unsuccessful" if success is False else "unresolved"
    parts = [
        f"Past pilot: {challenge_title}",
        f"Domain: {domain}",
        f"Technologies: {', '.join(technology_tags)}",
        f"Outcome ({outcome_word}): {outcome_summary or 'n/a'}",
    ]
    return "\n".join(parts)
