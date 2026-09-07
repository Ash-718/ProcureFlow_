"""
Surfaces relevant past pilots for a given (draft or published) challenge, or for
free-text domain/technology filters (Section 13: "3 similar past pilots in this
domain — 2 scaled, 1 rejected").
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingProvider, cosine_similarity
from app.services.embedding_service import compute_and_store_kb_embedding
from app.services.text_builders import build_challenge_text


def _fetch_all_kb_entries(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT pkb.id, pkb.domain, pkb.technology_tags, pkb.outcome_summary,
                   pkb.success, pkb.embedding, c.title AS challenge_title
            FROM pilot_knowledge_base pkb
            JOIN pilots p ON p.id = pkb.pilot_id
            JOIN challenges c ON c.id = p.challenge_id
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def find_similar_pilots_for_challenge(
    db: Session,
    provider: EmbeddingProvider,
    *,
    title: str,
    problem_statement: str,
    desired_technology: str | None,
    domain: str,
    outcomes_expected: str | None,
    top_n: int = 5,
) -> list[dict]:
    query_text = build_challenge_text(
        title=title,
        problem_statement=problem_statement,
        desired_technology=desired_technology,
        domain=domain,
        outcomes_expected=outcomes_expected,
        requirements=[],
    )
    query_embedding = provider.embed(query_text)

    entries = _fetch_all_kb_entries(db)
    scored = []
    for e in entries:
        if not e["embedding"]:
            e["embedding"] = compute_and_store_kb_embedding(db, str(e["id"]), provider)
        similarity = cosine_similarity(query_embedding, list(e["embedding"]))
        scored.append(
            {
                "pilot_id": str(e["id"]),
                "challenge_title": e["challenge_title"],
                "domain": e["domain"],
                "technology_tags": list(e["technology_tags"] or []),
                "outcome_summary": e["outcome_summary"],
                "success": e["success"],
                "similarity": round(max(0.0, similarity) * 100, 2),
            }
        )

    scored.sort(key=lambda s: s["similarity"], reverse=True)
    return scored[:top_n]
