"""
Fixed-window rate limiting on the auth endpoints.

Direct port of `RateLimitFilter`: in-memory, per client IP, 15 requests per
60-second window, applied only to paths under ``/api/v1/auth/``. The 429 body
is byte-identical to the Java one — `{"error", "message"}` only, *not* the full
`ErrorResponse` shape — because that is what the Java filter wrote directly to
the response before Spring's exception handling could see it. The frontend
reads `.message`, so it renders correctly either way.

Same caveat as the original: single-instance, in-process state. A multi-replica
deployment would move this to Redis or the API gateway.

Two things the port adds, both of which the Java version needed anyway:

* a **reverse-proxy-aware client key** — the Vite dev server proxies every
  browser request, so `request.client.host` is the proxy for all users and the
  limit would otherwise be shared across the whole demo audience;
* **bounded memory** — the Java `ConcurrentHashMap` never evicts, so a long-run
  process accumulates one entry per client IP forever.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

#: Matches `RateLimitFilter.MAX_REQUESTS_PER_WINDOW` / `WINDOW_MS`.
DEFAULT_MAX_REQUESTS = 15
DEFAULT_WINDOW_SECONDS = 60

RATE_LIMITED_PATH_PREFIX = "/api/v1/auth/"

#: Buckets older than this many windows are dropped during a sweep.
_STALE_WINDOW_MULTIPLIER = 3


@dataclass
class _Window:
    started_at: float
    count: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_requests: int = DEFAULT_MAX_REQUESTS,
                 window_seconds: int = DEFAULT_WINDOW_SECONDS,
                 path_prefix: str = RATE_LIMITED_PATH_PREFIX):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.path_prefix = path_prefix
        self._buckets: dict[str, _Window] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith(self.path_prefix):
            return await call_next(request)

        if self._is_over_limit(self._client_key(request)):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMITED",
                    "message": "Too many auth requests, please wait a minute.",
                },
            )
        return await call_next(request)

    # ------------------------------------------------------------------

    @staticmethod
    def _client_key(request: Request) -> str:
        """
        Identify the caller, seeing through a single trusted reverse proxy.

        The Vite dev server proxies `/api`, so without this every browser shares
        one bucket and 15 total logins would lock out the whole demo. Only the
        first `X-Forwarded-For` hop is used, and it is a rate-limit key rather
        than an authorisation input, so a spoofed value can only shrink an
        attacker's own bucket.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        return request.client.host if request.client else "unknown"

    def _is_over_limit(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._maybe_sweep(now)
            window = self._buckets.get(key)
            if window is None or now - window.started_at > self.window_seconds:
                self._buckets[key] = _Window(started_at=now, count=1)
                return False
            window.count += 1
            return window.count > self.max_requests

    def _maybe_sweep(self, now: float) -> None:
        """Drop expired buckets so the map cannot grow without bound."""
        if now - self._last_sweep < self.window_seconds:
            return
        cutoff = self.window_seconds * _STALE_WINDOW_MULTIPLIER
        self._buckets = {
            key: window for key, window in self._buckets.items()
            if now - window.started_at <= cutoff
        }
        self._last_sweep = now

    def reset(self) -> None:
        """Clear all buckets. Used by tests to isolate cases."""
        with self._lock:
            self._buckets.clear()


__all__ = [
    "DEFAULT_MAX_REQUESTS",
    "DEFAULT_WINDOW_SECONDS",
    "RATE_LIMITED_PATH_PREFIX",
    "RateLimitMiddleware",
]
