"""
TextGenerationProvider abstraction (Section 6).

TemplateTextGenerationProvider is fully deterministic — it fills sentences from the
component scores, no network call, so match explanations are reproducible offline.
LLMTextGenerationProvider optionally polishes that same template output into more
natural prose via a chat completion call; if it fails or no key is configured we
just keep the template text (never crash, never block the response).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import get_settings

logger = logging.getLogger("ai-service.text_generation")


class TextGenerationProvider(ABC):
    name: str

    @abstractmethod
    def polish(self, draft_text: str, context: str) -> str:
        ...


class TemplateTextGenerationProvider(TextGenerationProvider):
    name = "local-fallback"

    def polish(self, draft_text: str, context: str) -> str:
        return draft_text


class LLMTextGenerationProvider(TextGenerationProvider):
    name = "llm"

    def __init__(self, api_key: str, api_base: str, model: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=15.0)

    def polish(self, draft_text: str, context: str) -> str:
        try:
            resp = self._client.post(
                f"{self._api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Rewrite the following bullet-point analysis as 2-4 tight, "
                                "concrete sentences for a government procurement officer. "
                                "Keep every factual claim, do not invent new facts, no fluff."
                            ),
                        },
                        {"role": "user", "content": f"Context: {context}\n\nDraft:\n{draft_text}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("LLM text polish failed — falling back to template text.")
            return draft_text


@lru_cache
def get_text_generation_provider() -> TextGenerationProvider:
    settings = get_settings()

    if settings.embedding_provider == "llm" and settings.llm_api_key:
        logger.info("Text generation provider: LLM (%s)", settings.llm_chat_model)
        return LLMTextGenerationProvider(
            api_key=settings.llm_api_key,
            api_base=settings.llm_api_base,
            model=settings.llm_chat_model,
        )

    logger.info("Text generation provider: local template-based")
    return TemplateTextGenerationProvider()
