from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.embeddings import get_embedding_provider
from app.core.text_generation import get_text_generation_provider
from app.schemas.matching import (
    EmbeddingComputeResponse,
    KnowledgeBaseMatch,
    KnowledgeBaseSimilarResponse,
    MatchResponse,
    ProposalAnalysisResponse,
)
from app.services.embedding_service import (
    compute_and_store_challenge_embedding,
    compute_and_store_kb_embedding,
    compute_and_store_startup_embedding,
)
from app.services.knowledge_base_service import find_similar_pilots_for_challenge
from app.services.matching_service import run_matching_for_challenge
from app.services.proposal_analysis import generate_proposal_analysis

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/embeddings/challenge/{challenge_id}", response_model=EmbeddingComputeResponse)
def embed_challenge(challenge_id: str, db: Session = Depends(get_db)):
    provider = get_embedding_provider()
    try:
        embedding = compute_and_store_challenge_embedding(db, challenge_id, provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return EmbeddingComputeResponse(id=challenge_id, embedding_dimensions=len(embedding), ai_provider=provider.name)


@router.post("/embeddings/startup/{startup_id}", response_model=EmbeddingComputeResponse)
def embed_startup(startup_id: str, db: Session = Depends(get_db)):
    provider = get_embedding_provider()
    try:
        embedding = compute_and_store_startup_embedding(db, startup_id, provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return EmbeddingComputeResponse(id=startup_id, embedding_dimensions=len(embedding), ai_provider=provider.name)


@router.post("/embeddings/knowledge-base/{pilot_kb_id}", response_model=EmbeddingComputeResponse)
def embed_knowledge_base_entry(pilot_kb_id: str, db: Session = Depends(get_db)):
    provider = get_embedding_provider()
    try:
        embedding = compute_and_store_kb_embedding(db, pilot_kb_id, provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return EmbeddingComputeResponse(id=pilot_kb_id, embedding_dimensions=len(embedding), ai_provider=provider.name)


@router.post("/match/{challenge_id}", response_model=MatchResponse)
def match_challenge(challenge_id: str, db: Session = Depends(get_db)):
    provider = get_embedding_provider()
    settings = get_settings()
    try:
        result = run_matching_for_challenge(db, challenge_id, provider, top_n=settings.match_top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/analysis/proposal/{proposal_id}", response_model=ProposalAnalysisResponse)
def analyze_proposal(proposal_id: str, db: Session = Depends(get_db)):
    embedding_provider = get_embedding_provider()
    text_provider = get_text_generation_provider()
    try:
        summary = generate_proposal_analysis(db, proposal_id, embedding_provider, text_provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ProposalAnalysisResponse(proposal_id=proposal_id, ai_provider=embedding_provider.name, summary=summary)


class ChallengeDraft(BaseModel):
    title: str
    problem_statement: str
    desired_technology: str | None = None
    domain: str
    outcomes_expected: str | None = None


@router.post("/knowledge-base/similar", response_model=KnowledgeBaseSimilarResponse)
def similar_past_pilots(draft: ChallengeDraft, db: Session = Depends(get_db)):
    provider = get_embedding_provider()
    results = find_similar_pilots_for_challenge(
        db,
        provider,
        title=draft.title,
        problem_statement=draft.problem_statement,
        desired_technology=draft.desired_technology,
        domain=draft.domain,
        outcomes_expected=draft.outcomes_expected,
    )
    return KnowledgeBaseSimilarResponse(
        ai_provider=provider.name,
        results=[KnowledgeBaseMatch(**r) for r in results],
    )
