"""
EmbeddingProvider abstraction (Section 6 of the build spec).

Two implementations:
  - LocalEmbeddingProvider: sentence-transformers `all-MiniLM-L6-v2`, runs fully
    offline, no API key. This is the default and what the seeded demo data uses.
  - LLMEmbeddingProvider: calls an OpenAI-compatible `/embeddings` endpoint.

`get_embedding_provider()` picks based on config and NEVER raises just because an
API key is missing — it logs and silently falls back to local, per spec.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("ai-service.embeddings")


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    name = "local-fallback"

    def __init__(self, model_name: str):
        # Imported lazily: sentence-transformers/torch are heavy and only needed
        # for this code path, so a pure-LLM deployment need not pay the import cost.
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model '%s' (first load can take ~15-20s)...", model_name)
        self._model = SentenceTransformer(model_name)
        logger.info("Local embedding model loaded.")

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


class LLMEmbeddingProvider(EmbeddingProvider):
    name = "llm"

    def __init__(self, api_key: str, api_base: str, model: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=20.0)

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.post(
            f"{self._api_base}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [row["embedding"] for row in data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()

    if settings.embedding_provider == "llm":
        if settings.llm_api_key:
            logger.info("AI provider: LLM embeddings (%s)", settings.llm_embedding_model)
            return LLMEmbeddingProvider(
                api_key=settings.llm_api_key,
                api_base=settings.llm_api_base,
                model=settings.llm_embedding_model,
            )
        logger.warning(
            "EMBEDDING_PROVIDER=llm but no LLM_API_KEY is set — silently falling back "
            "to the local sentence-transformers provider."
        )

    logger.info("AI provider: local sentence-transformers (%s)", settings.embedding_model_name)
    return LocalEmbeddingProvider(settings.embedding_model_name)
