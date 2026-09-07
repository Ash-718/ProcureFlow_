"""
The weighted matching formula (Section 5). Every function here is a pure function
over plain Python data — no DB, no network — so the scoring math itself is fully
unit-testable (see tests/test_scoring.py) independent of embeddings/DB wiring.

    overall_score =
        w1 * semantic_similarity
      + w2 * technology_match
      + w3 * domain_match
      + w4 * experience_score
      + w5 * readiness_score

All component scores and the overall score are on a 0-100 scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower()


def split_technology_list(desired_technology: str | None) -> list[str]:
    if not desired_technology:
        return []
    return [t.strip() for t in desired_technology.split(",") if t.strip()]


@dataclass
class TechnologyMatchResult:
    score: float  # 0-1
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def compute_technology_match(
    desired_technologies: list[str], capabilities: list[dict]
) -> TechnologyMatchResult:
    """
    For each desired technology, find the startup capability with the closest tag
    match (exact match, or one string containing the other) and credit its
    proficiency_level (1-5, normalized to 0-1). A desired technology with no match
    contributes 0. The overall score is the average across all desired technologies,
    so a startup covering every desired technology at top proficiency scores 1.0,
    and a startup covering none scores 0.0.
    """
    if not desired_technologies:
        return TechnologyMatchResult(score=0.5)  # neutral when challenge specifies none

    matched, unmatched = [], []
    total = 0.0
    for desired in desired_technologies:
        d_norm = _normalize_tag(desired)
        best_proficiency = 0
        for cap in capabilities:
            c_norm = _normalize_tag(cap["technology_tag"])
            if d_norm == c_norm or d_norm in c_norm or c_norm in d_norm:
                best_proficiency = max(best_proficiency, cap["proficiency_level"])
        if best_proficiency > 0:
            matched.append(desired)
            total += best_proficiency / 5.0
        else:
            unmatched.append(desired)

    score = total / len(desired_technologies)
    return TechnologyMatchResult(score=score, matched=matched, unmatched=unmatched)


@dataclass
class DomainMatchResult:
    score: float  # 0-1
    matched_via: str | None = None  # "capability" | "project" | None


def compute_domain_match(
    challenge_domain: str, capabilities: list[dict], projects: list[dict]
) -> DomainMatchResult:
    """
    Full credit (scaled by proficiency) if a capability is tagged with the
    challenge's domain; otherwise partial credit if a past project was delivered
    in that domain; otherwise zero.
    """
    d_norm = _normalize_tag(challenge_domain)

    domain_capabilities = [c for c in capabilities if _normalize_tag(c["domain_tag"]) == d_norm]
    if domain_capabilities:
        best = max(c["proficiency_level"] for c in domain_capabilities)
        return DomainMatchResult(score=best / 5.0, matched_via="capability")

    domain_projects = [p for p in projects if _normalize_tag(p["domain"]) == d_norm]
    if domain_projects:
        return DomainMatchResult(score=0.4, matched_via="project")

    return DomainMatchResult(score=0.0, matched_via=None)


@dataclass
class ExperienceResult:
    score: float  # 0-1
    relevant_projects: list[dict] = field(default_factory=list)
    government_projects: list[dict] = field(default_factory=list)
    has_relevant_government_experience: bool = False


def compute_experience_score(challenge_domain: str, projects: list[dict]) -> ExperienceResult:
    """
    - Up to 0.7 for relevant (same-domain) delivery history, capped at 3 projects.
    - +0.3 bonus if any same-domain project had a GOVERNMENT client (spec explicitly
      calls out government-sector experience as a differentiator).
    - Small credit (+0.1 cap) for general delivery experience in other domains, so a
      startup with zero relevant history isn't scored identically to a brand-new one.
    """
    d_norm = _normalize_tag(challenge_domain)
    relevant = [p for p in projects if _normalize_tag(p["domain"]) == d_norm]
    other = [p for p in projects if _normalize_tag(p["domain"]) != d_norm]
    relevant_govt = [p for p in relevant if p["client_type"] == "GOVERNMENT"]

    raw = min(len(relevant), 3) / 3 * 0.6
    govt_bonus = 0.3 if relevant_govt else (0.1 if any(p["client_type"] == "GOVERNMENT" for p in other) else 0.0)
    general_bonus = min(len(other), 2) / 2 * 0.1

    score = min(1.0, raw + govt_bonus + general_bonus)
    return ExperienceResult(
        score=score,
        relevant_projects=relevant,
        government_projects=relevant_govt,
        has_relevant_government_experience=bool(relevant_govt),
    )


def normalize_readiness(readiness_score: float) -> float:
    return max(0.0, min(1.0, readiness_score / 100.0))


@dataclass
class OverallScoreResult:
    overall: float  # 0-100
    semantic_similarity: float  # 0-100
    technology_match: float  # 0-100
    domain_match: float  # 0-100
    experience: float  # 0-100
    readiness: float  # 0-100


def compute_overall_score(
    semantic_similarity_0_1: float,
    technology_match_0_1: float,
    domain_match_0_1: float,
    experience_0_1: float,
    readiness_0_1: float,
    weights: dict[str, float],
) -> OverallScoreResult:
    semantic_clamped = max(0.0, min(1.0, semantic_similarity_0_1))

    overall = (
        weights["semantic_similarity"] * semantic_clamped
        + weights["technology_match"] * technology_match_0_1
        + weights["domain_match"] * domain_match_0_1
        + weights["experience_score"] * experience_0_1
        + weights["readiness_score"] * readiness_0_1
    )

    return OverallScoreResult(
        overall=round(overall * 100, 3),
        semantic_similarity=round(semantic_clamped * 100, 3),
        technology_match=round(technology_match_0_1 * 100, 3),
        domain_match=round(domain_match_0_1 * 100, 3),
        experience=round(experience_0_1 * 100, 3),
        readiness=round(readiness_0_1 * 100, 3),
    )
