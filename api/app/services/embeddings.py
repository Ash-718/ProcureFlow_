"""Embeddings and cosine similarity.

sentence-transformers all-MiniLM-L6-v2 on CPU, with similarity computed in
Python.  At demo scale - tens of companies and challenges - comparing a few
hundred 384-dimension vectors in a loop costs nothing, so there is no vector
database and no pgvector extension.

The model is loaded once, lazily, on first use.  Loading it takes a few seconds
and downloads about 90 MB the first time, which is why it does not happen at
import time and block the API from starting.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

from app.config import settings

_model = None
_model_lock = threading.Lock()
_load_error: str | None = None


@dataclass(frozen=True)
class EmbeddingStatus:
    available: bool
    model: str
    error: str | None

    def as_dict(self) -> dict:
        return {"available": self.available, "model": self.model, "error": self.error}


def _load_model():
    """Load the sentence-transformers model, once, behind a lock."""
    global _model, _load_error

    if _model is not None or _load_error is not None:
        return _model

    with _model_lock:
        if _model is not None or _load_error is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embedding_model, device="cpu")
        except Exception as error:  # not installed, or no network for the download
            _load_error = str(error)
            _model = None
    return _model


def status() -> EmbeddingStatus:
    _load_model()
    return EmbeddingStatus(
        available=_model is not None, model=settings.embedding_model, error=_load_error
    )


def is_available() -> bool:
    return _load_model() is not None


def embed(text: str) -> list[float] | None:
    """Embed one piece of text, or None when the model is unavailable."""
    model = _load_model()
    if model is None:
        return None
    return [float(value) for value in model.encode(text, normalize_embeddings=False)]


def embed_many(texts: list[str]) -> list[list[float]] | None:
    model = _load_model()
    if model is None:
        return None
    return [[float(value) for value in vector] for vector in model.encode(texts)]


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float | None:
    """Cosine similarity in plain Python. None when either side has no vector."""
    if not left or not right or len(left) != len(right):
        return None

    dot = sum(a * b for a, b in zip(left, right))
    left_magnitude = math.sqrt(sum(a * a for a in left))
    right_magnitude = math.sqrt(sum(b * b for b in right))
    if not left_magnitude or not right_magnitude:
        return None
    return dot / (left_magnitude * right_magnitude)
