"""
Computes and persists embeddings for challenges, startups and knowledge-base
entries (Section 5, steps 1-2). This is the "on save" half of the pipeline; the
matching itself lives in matching_service.py.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.text_builders import build_challenge_text, build_knowledge_base_text, build_startup_text


def fetch_challenge(db: Session, challenge_id: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT id, title, problem_statement, desired_technology, domain,
                   outcomes_expected, embedding, status
            FROM challenges WHERE id = :id
            """
        ),
        {"id": challenge_id},
    ).mappings().first()
    return dict(row) if row else None


def fetch_challenge_requirements(db: Session, challenge_id: str) -> list[str]:
    rows = db.execute(
        text("SELECT description FROM challenge_requirements WHERE challenge_id = :id"),
        {"id": challenge_id},
    ).all()
    return [r[0] for r in rows]


def fetch_startup(db: Session, startup_id: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT id, company_name, description, readiness_score, embedding
            FROM startups WHERE id = :id
            """
        ),
        {"id": startup_id},
    ).mappings().first()
    return dict(row) if row else None


def fetch_startup_capabilities(db: Session, startup_id: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT technology_tag, domain_tag, proficiency_level, description
            FROM startup_capabilities WHERE startup_id = :id
            """
        ),
        {"id": startup_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def fetch_startup_projects(db: Session, startup_id: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT title, domain, technology_stack, client_type, outcome_summary, year
            FROM startup_projects WHERE startup_id = :id
            ORDER BY year DESC NULLS LAST
            """
        ),
        {"id": startup_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def fetch_all_startup_ids(db: Session) -> list[str]:
    rows = db.execute(text("SELECT id FROM startups")).all()
    return [str(r[0]) for r in rows]


def compute_and_store_challenge_embedding(
    db: Session, challenge_id: str, provider: EmbeddingProvider
) -> list[float]:
    challenge = fetch_challenge(db, challenge_id)
    if not challenge:
        raise ValueError(f"Challenge {challenge_id} not found")

    requirements = fetch_challenge_requirements(db, challenge_id)
    text_repr = build_challenge_text(
        title=challenge["title"],
        problem_statement=challenge["problem_statement"],
        desired_technology=challenge["desired_technology"],
        domain=challenge["domain"],
        outcomes_expected=challenge["outcomes_expected"],
        requirements=requirements,
    )
    embedding = provider.embed(text_repr)

    db.execute(
        text(
            """
            UPDATE challenges
            SET embedding = :embedding, embedding_model = :model, embedding_updated_at = now()
            WHERE id = :id
            """
        ),
        {"embedding": embedding, "model": provider.name, "id": challenge_id},
    )
    db.commit()
    return embedding


def compute_and_store_startup_embedding(
    db: Session, startup_id: str, provider: EmbeddingProvider
) -> list[float]:
    startup = fetch_startup(db, startup_id)
    if not startup:
        raise ValueError(f"Startup {startup_id} not found")

    capabilities = fetch_startup_capabilities(db, startup_id)
    projects = fetch_startup_projects(db, startup_id)
    text_repr = build_startup_text(
        company_name=startup["company_name"],
        description=startup["description"],
        capabilities=capabilities,
        projects=projects,
        readiness_score=float(startup["readiness_score"]),
    )
    embedding = provider.embed(text_repr)

    db.execute(
        text(
            """
            UPDATE startups
            SET embedding = :embedding, embedding_model = :model, embedding_updated_at = now()
            WHERE id = :id
            """
        ),
        {"embedding": embedding, "model": provider.name, "id": startup_id},
    )
    db.commit()
    return embedding


def compute_and_store_kb_embedding(
    db: Session, pilot_kb_id: str, provider: EmbeddingProvider
) -> list[float]:
    row = db.execute(
        text(
            """
            SELECT pkb.id, pkb.domain, pkb.technology_tags, pkb.outcome_summary, pkb.success,
                   c.title AS challenge_title
            FROM pilot_knowledge_base pkb
            JOIN pilots p ON p.id = pkb.pilot_id
            JOIN challenges c ON c.id = p.challenge_id
            WHERE pkb.id = :id
            """
        ),
        {"id": pilot_kb_id},
    ).mappings().first()
    if not row:
        raise ValueError(f"Knowledge base entry {pilot_kb_id} not found")

    text_repr = build_knowledge_base_text(
        challenge_title=row["challenge_title"],
        domain=row["domain"],
        technology_tags=list(row["technology_tags"] or []),
        outcome_summary=row["outcome_summary"],
        success=row["success"],
    )
    embedding = provider.embed(text_repr)

    db.execute(
        text(
            "UPDATE pilot_knowledge_base SET embedding = :embedding, embedding_model = :model WHERE id = :id"
        ),
        {"embedding": embedding, "model": provider.name, "id": pilot_kb_id},
    )
    db.commit()
    return embedding
