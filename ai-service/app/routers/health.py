from fastapi import APIRouter

from app.core.config import get_settings
from app.core.embeddings import get_embedding_provider
from app.core.text_generation import get_text_generation_provider

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {
        "service": "INNOVATE-GOV AI Service",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
def health():
    settings = get_settings()
    embedding_provider = get_embedding_provider()
    text_provider = get_text_generation_provider()
    return {
        "status": "ok",
        "embedding_provider": embedding_provider.name,
        "text_generation_provider": text_provider.name,
        "embedding_model": settings.embedding_model_name
        if embedding_provider.name == "local-fallback"
        else settings.llm_embedding_model,
        "matching_weights": {
            "semantic_similarity": settings.weight_semantic_similarity,
            "technology_match": settings.weight_technology_match,
            "domain_match": settings.weight_domain_match,
            "experience_score": settings.weight_experience,
            "readiness_score": settings.weight_readiness,
        },
    }
