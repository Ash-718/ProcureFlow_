"""Provider-agnostic LLM access.

One module, one interface, a key from the environment, and a deterministic
template fallback so the demo works with no network and no key at all.

What the LLM is allowed to do here is narrow on purpose.  It suggests
capabilities, outcomes and candidate KPIs.  It never decides eligibility, never
sets a threshold, and never supplies a budget, a timeline or a location - those
come from the department or they go into missing_fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import settings

# Each provider's chat-completions endpoint and the shape of its request.
# Adding a provider means adding an entry here, not changing any caller.
PROVIDERS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "auth_header": "x-api-key",
        "default_model": "claude-sonnet-5",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "auth_header": "Authorization",
        "default_model": "gpt-4o-mini",
    },
}


@dataclass(frozen=True)
class LlmResult:
    """What came back, and how."""

    text: str
    source: str  # "llm" or "template"
    provider: str | None
    model: str | None
    note: str

    @property
    def used_fallback(self) -> bool:
        return self.source == "template"


class LlmUnavailable(RuntimeError):
    """No provider is configured, or the call failed."""


def is_configured() -> bool:
    """True when a key and a known provider are both present."""
    return bool(settings.llm_api_key) and settings.llm_provider.lower() in PROVIDERS


def describe() -> dict:
    """What the API reports about its own AI configuration."""
    configured = is_configured()
    return {
        "configured": configured,
        "provider": settings.llm_provider.lower() if configured else None,
        "model": _model_name() if configured else None,
        "fallback": (
            "Deterministic template. Every output is still validated against the same "
            "schema, and no value is ever invented."
        ),
    }


def _model_name() -> str:
    provider = PROVIDERS[settings.llm_provider.lower()]
    return settings.llm_model or provider["default_model"]


def complete_json(system_prompt: str, user_prompt: str, *, timeout: float = 30.0) -> str:
    """Ask the configured provider for a JSON response, and return the raw text.

    Raises LlmUnavailable when no provider is configured or the call fails, so
    the caller can fall back deliberately rather than by accident.
    """
    if not is_configured():
        raise LlmUnavailable("No LLM provider configured (LLM_API_KEY is empty).")

    name = settings.llm_provider.lower()
    provider = PROVIDERS[name]
    model = _model_name()

    if name == "anthropic":
        headers = {
            provider["auth_header"]: settings.llm_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 2000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    else:
        headers = {
            provider["auth_header"]: f"Bearer {settings.llm_api_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    try:
        response = httpx.post(provider["url"], headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except Exception as error:  # network, auth, rate limit, malformed response
        raise LlmUnavailable(f"{name} call failed: {error}") from error

    try:
        if name == "anthropic":
            return body["content"][0]["text"]
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LlmUnavailable(f"{name} returned an unexpected response shape") from error


def extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response.

    Models wrap JSON in prose or fences often enough that this is worth doing
    properly rather than hoping.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[len("json") :]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])
