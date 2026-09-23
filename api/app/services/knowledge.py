"""The cross-department knowledge base.

Every completed pilot leaves a record: what was tried, what it cost, whether it
was scaled, and what the department learned the hard way.  When an officer
drafts a new challenge, this searches those records semantically, so a problem
worded differently in a different district still surfaces the pilot that already
answered it.

Semantic, not lexical: "water pipeline losses in the distribution network" has
to find "non-revenue water", which shares no words with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ChallengeStatus, KpiStatus
from app.models import Challenge, Company, Kpi, Pilot
from app.services import embeddings


@dataclass(frozen=True)
class PriorPilot:
    challenge_id: int
    pilot_id: int
    title: str
    department: str
    district: str | None
    category: str | None
    startup: str
    outcome: str | None
    cost: str | None
    lessons_learned: str | None
    validated_kpis: list[dict]
    similarity: float

    def as_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "pilot_id": self.pilot_id,
            "title": self.title,
            "department": self.department,
            "district": self.district,
            "category": self.category,
            "startup": self.startup,
            "outcome": self.outcome,
            "cost": self.cost,
            "lessons_learned": self.lessons_learned,
            "validated_kpis": self.validated_kpis,
            "similarity": round(self.similarity, 4),
        }


@dataclass(frozen=True)
class KnowledgeSearch:
    query: str
    matches: list[PriorPilot]
    semantic: bool
    note: str

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "matches": [match.as_dict() for match in self.matches],
            "semantic": self.semantic,
            "note": self.note,
        }


def challenge_text(challenge: Challenge) -> str:
    """The text that represents a challenge for embedding purposes."""
    parts = [challenge.title, challenge.description_raw or ""]
    spec = challenge.structured_spec or {}
    if isinstance(spec, dict):
        parts.append(spec.get("problem_statement") or "")
        parts.extend(spec.get("required_capabilities") or [])
        parts.extend(spec.get("expected_outcomes") or [])
    if challenge.category:
        parts.append(challenge.category)
    return " ".join(part for part in parts if part)


def index_challenge(db: Session, challenge: Challenge) -> bool:
    """Store the challenge's embedding. False when the model is unavailable."""
    vector = embeddings.embed(challenge_text(challenge))
    if vector is None:
        return False
    challenge.embedding = vector
    return True


def index_company(db: Session, company: Company) -> bool:
    vector = embeddings.embed(f"{company.name}. {company.profile_text or ''}")
    if vector is None:
        return False
    company.embedding = vector
    return True


def reindex_all(db: Session) -> dict:
    """Embed every challenge and company that has no vector yet."""
    if not embeddings.is_available():
        return {"indexed_challenges": 0, "indexed_companies": 0, "available": False}

    challenges = db.scalars(select(Challenge).where(Challenge.embedding.is_(None))).all()
    for challenge in challenges:
        index_challenge(db, challenge)

    companies = db.scalars(select(Company).where(Company.embedding.is_(None))).all()
    for company in companies:
        index_company(db, company)

    return {
        "indexed_challenges": len(challenges),
        "indexed_companies": len(companies),
        "available": True,
    }


def validated_kpis_for(db: Session, challenge_id: int) -> list[dict]:
    kpis = db.scalars(
        select(Kpi).where(Kpi.challenge_id == challenge_id, Kpi.status == KpiStatus.VERIFIED)
    ).all()
    return [
        {
            "name": kpi.name,
            "target_value": str(kpi.target_value) if kpi.target_value is not None else None,
            "validated_value": str(kpi.validated_value)
            if kpi.validated_value is not None
            else None,
            "unit": kpi.unit,
            "direction": kpi.direction.value,
        }
        for kpi in kpis
    ]


def search(db: Session, query: str, *, limit: int = 3, minimum_similarity: float = 0.0):
    """Find past pilots similar to a draft challenge.

    minimum_similarity defaults to 0 so nothing is silently hidden; the caller
    decides what is close enough, and every match carries its score.
    """
    query_vector = embeddings.embed(query)
    if query_vector is None:
        return KnowledgeSearch(
            query=query,
            matches=[],
            semantic=False,
            note=(
                "The embedding model is unavailable, so no semantic search was run. "
                f"({embeddings.status().error})"
            ),
        )

    pilots = db.scalars(
        select(Pilot)
        .join(Challenge, Challenge.id == Pilot.challenge_id)
        .where(Challenge.status == ChallengeStatus.COMPLETED)
    ).all()

    scored: list[PriorPilot] = []
    for pilot in pilots:
        challenge = pilot.challenge
        if challenge.embedding is None:
            index_challenge(db, challenge)
        similarity = embeddings.cosine_similarity(query_vector, challenge.embedding)
        if similarity is None or similarity < minimum_similarity:
            continue

        scored.append(
            PriorPilot(
                challenge_id=challenge.id,
                pilot_id=pilot.id,
                title=challenge.title,
                department=challenge.department.name,
                district=challenge.district,
                category=challenge.category,
                startup=pilot.startup.name,
                outcome=pilot.outcome.value if pilot.outcome else None,
                cost=str(pilot.cost) if pilot.cost is not None else None,
                lessons_learned=pilot.lessons_learned,
                validated_kpis=validated_kpis_for(db, challenge.id),
                similarity=similarity,
            )
        )

    scored.sort(key=lambda match: match.similarity, reverse=True)
    return KnowledgeSearch(
        query=query,
        matches=scored[:limit],
        semantic=True,
        note=(
            "Similar solutions already piloted, ranked by semantic similarity. "
            "Outcome, cost and lessons learned are from the completed pilot."
        ),
    )
