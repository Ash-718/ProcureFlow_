from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration, populated from environment variables (see .env.example).
    Every field has a sane local-dev default so the service runs with zero
    configuration in the fallback ("local") AI mode described in docs/ai-matching.md.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://innovategov:@127.0.0.1:5433/innovategov"
    )

    # "llm" uses an external OpenAI-compatible API for embeddings/text generation;
    # "local" (default) uses a local sentence-transformers model + template text —
    # fully offline, no API key required. See EmbeddingProvider / TextGenerationProvider.
    embedding_provider: str = "local"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    llm_api_key: str | None = None
    llm_api_base: str = "https://api.openai.com/v1"
    llm_embedding_model: str = "text-embedding-3-small"
    llm_chat_model: str = "gpt-4o-mini"

    # Weighted-scoring formula weights (Section 5). Overridable via env for quick
    # experimentation; the source of truth for the *documented* defaults also lives
    # in database/schema.sql (ai_matching_config table) for transparency in the UI.
    weight_semantic_similarity: float = 0.35
    weight_technology_match: float = 0.20
    weight_domain_match: float = 0.15
    weight_experience: float = 0.15
    weight_readiness: float = 0.15

    match_top_n: int = 8

    cors_allowed_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
