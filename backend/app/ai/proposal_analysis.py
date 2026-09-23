"""
Generates the "AI-assisted analysis summary" an expert sees alongside a proposal
(Section 11). Reuses the exact same scoring math as the matching pipeline — the
expert view is explicitly not a different, unaccountable model, just a narrated
version of the same component scores — then optionally polishes it into prose via
the TextGenerationProvider (falls back to the template paragraph with no network
call, per Section 6).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider, cosine_similarity
from app.ai.text_generation import TextGenerationProvider
from app.ai.embedding_service import (
    compute_and_store_challenge_embedding,
    compute_and_store_startup_embedding,
    fetch_challenge,
    fetch_startup,
    fetch_startup_capabilities,
    fetch_startup_projects,
)
from app.ai.explanations import build_match_explanation
from app.ai.matching import get_matching_weights
from app.ai.scoring import (
    compute_domain_match,
    compute_experience_score,
    compute_overall_score,
    compute_technology_match,
    normalize_readiness,
    split_technology_list,
)


def fetch_proposal(db: Session, proposal_id: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT id, challenge_id, startup_id, summary, proposed_approach,
                   cost_estimate, timeline_estimate_days, status
            FROM proposals WHERE id = :id
            """
        ),
        {"id": proposal_id},
    ).mappings().first()
    return dict(row) if row else None


def generate_proposal_analysis(
    db: Session,
    proposal_id: str,
    embedding_provider: EmbeddingProvider,
    text_provider: TextGenerationProvider,
) -> str:
    proposal = fetch_proposal(db, proposal_id)
    if not proposal:
        raise ValueError(f"Proposal {proposal_id} not found")

    challenge = fetch_challenge(db, str(proposal["challenge_id"]))
    startup = fetch_startup(db, str(proposal["startup_id"]))
    capabilities = fetch_startup_capabilities(db, str(proposal["startup_id"]))
    projects = fetch_startup_projects(db, str(proposal["startup_id"]))

    challenge_embedding = challenge["embedding"] or compute_and_store_challenge_embedding(
        db, str(challenge["id"]), embedding_provider
    )
    startup_embedding = startup["embedding"] or compute_and_store_startup_embedding(
        db, str(startup["id"]), embedding_provider
    )

    semantic_similarity = cosine_similarity(list(challenge_embedding), list(startup_embedding))
    desired_technologies = split_technology_list(challenge["desired_technology"])
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
        weights=get_matching_weights(),
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

    cost_note = ""
    if proposal["cost_estimate"] is not None:
        cost_note = f" The proposed cost estimate is INR {float(proposal['cost_estimate']):,.0f}"
        if proposal["timeline_estimate_days"]:
            cost_note += f" over {proposal['timeline_estimate_days']} days."
        else:
            cost_note += "."

    draft_lines = [
        f"Overall AI match score for {startup['company_name']} against this challenge: {scores.overall:.1f}/100.",
        *explanation["reasons"],
    ]
    if explanation["gaps"]:
        draft_lines.append("Potential gaps to probe during evaluation: " + " ".join(explanation["gaps"]))
    draft_lines.append(
        "This is an AI-generated aid based on the same scoring model used for challenge-wide matching; "
        "it does not replace the expert's own judgment." + cost_note
    )

    draft_text = " ".join(draft_lines)
    context = f"Proposal for challenge '{challenge['title']}' ({challenge['domain']}) from {startup['company_name']}."
    return text_provider.polish(draft_text, context)
