"""
Orchestrates the full matching pipeline (Section 5, steps 3-6):
  1. Ensure the challenge has an embedding (compute on the fly if missing).
  2. For every startup, ensure it has an embedding (compute on the fly if missing).
  3. Compute the 5 component scores + weighted overall score.
  4. Persist ranked results into match_results.
  5. Return the ranked list with explanations to the caller (Spring Boot backend).
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embeddings import EmbeddingProvider, cosine_similarity
from app.services.embedding_service import (
    compute_and_store_challenge_embedding,
    compute_and_store_startup_embedding,
    fetch_all_startup_ids,
    fetch_challenge,
    fetch_startup,
    fetch_startup_capabilities,
    fetch_startup_projects,
)
from app.services.explanations import build_match_explanation
from app.services.scoring import (
    compute_domain_match,
    compute_experience_score,
    compute_overall_score,
    compute_technology_match,
    normalize_readiness,
    split_technology_list,
)

logger = logging.getLogger("ai-service.matching")


def get_matching_weights() -> dict[str, float]:
    settings = get_settings()
    return {
        "semantic_similarity": settings.weight_semantic_similarity,
        "technology_match": settings.weight_technology_match,
        "domain_match": settings.weight_domain_match,
        "experience_score": settings.weight_experience,
        "readiness_score": settings.weight_readiness,
    }


def run_matching_for_challenge(
    db: Session, challenge_id: str, provider: EmbeddingProvider, top_n: int
) -> dict:
    challenge = fetch_challenge(db, challenge_id)
    if not challenge:
        raise ValueError(f"Challenge {challenge_id} not found")

    if not challenge["embedding"]:
        logger.info("Challenge %s has no embedding yet — computing now.", challenge_id)
        challenge_embedding = compute_and_store_challenge_embedding(db, challenge_id, provider)
    else:
        challenge_embedding = list(challenge["embedding"])

    desired_technologies = split_technology_list(challenge["desired_technology"])
    weights = get_matching_weights()

    candidates = []
    for startup_id in fetch_all_startup_ids(db):
        startup = fetch_startup(db, startup_id)
        capabilities = fetch_startup_capabilities(db, startup_id)
        projects = fetch_startup_projects(db, startup_id)

        if not startup["embedding"]:
            startup_embedding = compute_and_store_startup_embedding(db, startup_id, provider)
        else:
            startup_embedding = list(startup["embedding"])

        semantic_similarity = cosine_similarity(challenge_embedding, startup_embedding)
        tech_result = compute_technology_match(desired_technologies, capabilities)
        domain_result = compute_domain_match(challenge["domain"], capabilities, projects)
        experience_result = compute_experience_score(challenge["domain"], projects)
        readiness_norm = normalize_readiness(float(startup["readiness_score"]))

        scores = compute_overall_score(
            semantic_similarity_0_1=semantic_similarity,
            technology_match_0_1=tech_result.score,
            domain_match_0_1=domain_result.score,
            experience_0_1=experience_result.score,
            readiness_0_1=readiness_norm,
            weights=weights,
        )

        explanation = build_match_explanation(
            startup_name=startup["company_name"],
            challenge_domain=challenge["domain"],
            scores=scores,
            tech_result=tech_result,
            domain_result=domain_result,
            experience_result=experience_result,
            readiness_raw=float(startup["readiness_score"]),
        )

        candidates.append(
            {
                "startup_id": startup_id,
                "company_name": startup["company_name"],
                "scores": scores,
                "explanation": explanation,
            }
        )

    candidates.sort(key=lambda c: c["scores"].overall, reverse=True)
    top_candidates = candidates[:top_n]

    db.execute(text("DELETE FROM match_results WHERE challenge_id = :cid"), {"cid": challenge_id})
    for rank, c in enumerate(top_candidates, start=1):
        s = c["scores"]
        db.execute(
            text(
                """
                INSERT INTO match_results (
                    challenge_id, startup_id, overall_score, semantic_similarity_score,
                    technology_match_score, domain_match_score, experience_score,
                    readiness_score, explanation_json, rank, ai_provider
                ) VALUES (
                    :challenge_id, :startup_id, :overall, :semantic, :tech, :domain,
                    :experience, :readiness, :explanation, :rank, :provider
                )
                """
            ),
            {
                "challenge_id": challenge_id,
                "startup_id": c["startup_id"],
                "overall": s.overall,
                "semantic": s.semantic_similarity,
                "tech": s.technology_match,
                "domain": s.domain_match,
                "experience": s.experience,
                "readiness": s.readiness,
                "explanation": _to_json(c["explanation"]),
                "rank": rank,
                "provider": provider.name,
            },
        )

    db.execute(
        text("UPDATE challenges SET status = 'MATCHING' WHERE id = :id AND status = 'PUBLISHED'"),
        {"id": challenge_id},
    )
    db.commit()

    return {
        "challenge_id": challenge_id,
        "ai_provider": provider.name,
        "weights": weights,
        "total_candidates_considered": len(candidates),
        "results": [
            {
                "startup_id": c["startup_id"],
                "company_name": c["company_name"],
                "rank": rank,
                "overall_score": c["scores"].overall,
                "component_scores": {
                    "semantic_similarity": c["scores"].semantic_similarity,
                    "technology_match": c["scores"].technology_match,
                    "domain_match": c["scores"].domain_match,
                    "experience_score": c["scores"].experience,
                    "readiness_score": c["scores"].readiness,
                },
                "reasons": c["explanation"]["reasons"],
                "gaps": c["explanation"]["gaps"],
            }
            for rank, c in enumerate(top_candidates, start=1)
        ],
    }


def _to_json(obj: dict) -> str:
    import json

    return json.dumps(obj)
