"""
AI matching, embeddings and explanations.

Migrated from the standalone `ai-service` FastAPI process. The modules are the
**same code**: `scoring.py` and `text_builders.py` are byte-identical to their
originals, and every other file differs only in its import paths and logger
name. The weighted formula, the `all-MiniLM-L6-v2` embeddings and the
deterministic template explanations are unchanged.

What changed is the *call mechanism*. The Spring backend reached this logic over
HTTP via `AiServiceClient`; the six former endpoints are now direct function
calls sharing the caller's SQLAlchemy session:

===================================================  ==========================
former endpoint                                      function
===================================================  ==========================
``POST /api/v1/ai/embeddings/challenge/{id}``        `compute_and_store_challenge_embedding`
``POST /api/v1/ai/embeddings/startup/{id}``          `compute_and_store_startup_embedding`
``POST /api/v1/ai/embeddings/knowledge-base/{id}``   `compute_and_store_kb_embedding`
``POST /api/v1/ai/match/{challenge_id}``             `run_matching_for_challenge`
``GET  /api/v1/ai/analysis/proposal/{id}``           `generate_proposal_analysis`
``POST /api/v1/ai/knowledge-base/similar``           `find_similar_pilots_for_challenge`
===================================================  ==========================

That removes a process, a port, a serialisation round-trip and the "is the AI
service running?" failure mode — without touching a line of the maths.

Configuration comes from `app.core.config.Settings`, which already carries the
same field names the standalone service used (`embedding_provider`,
`embedding_model_name`, the five `weight_*` values, `match_top_n`), so those
imports needed no rewrite at all.
"""
from app.ai.embedding_service import (
    compute_and_store_challenge_embedding,
    compute_and_store_kb_embedding,
    compute_and_store_startup_embedding,
    fetch_all_startup_ids,
    fetch_challenge,
    fetch_startup,
    fetch_startup_capabilities,
    fetch_startup_projects,
)
from app.ai.embeddings import (
    EmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
)
from app.ai.explanations import build_match_explanation
from app.ai.knowledge_base import find_similar_pilots_for_challenge
from app.ai.matching import get_matching_weights, run_matching_for_challenge
from app.ai.proposal_analysis import generate_proposal_analysis
from app.ai.scoring import (
    compute_domain_match,
    compute_experience_score,
    compute_overall_score,
    compute_technology_match,
    normalize_readiness,
    split_technology_list,
)
from app.ai.text_builders import (
    build_challenge_text,
    build_knowledge_base_text,
    build_startup_text,
)
from app.ai.text_generation import (
    TextGenerationProvider,
    get_text_generation_provider,
)

__all__ = [
    # providers
    "EmbeddingProvider", "TextGenerationProvider",
    "get_embedding_provider", "get_text_generation_provider",
    "cosine_similarity",
    # embeddings
    "compute_and_store_challenge_embedding",
    "compute_and_store_startup_embedding",
    "compute_and_store_kb_embedding",
    "fetch_challenge", "fetch_startup", "fetch_all_startup_ids",
    "fetch_startup_capabilities", "fetch_startup_projects",
    # scoring
    "compute_technology_match", "compute_domain_match", "compute_experience_score",
    "compute_overall_score", "normalize_readiness", "split_technology_list",
    # pipeline
    "run_matching_for_challenge", "get_matching_weights",
    "build_match_explanation",
    "find_similar_pilots_for_challenge",
    "generate_proposal_analysis",
    # text
    "build_challenge_text", "build_startup_text", "build_knowledge_base_text",
]
