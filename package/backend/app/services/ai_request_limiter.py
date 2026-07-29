"""Per-provider-key request concurrency and bounded 429 backoff."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, TypeVar

import httpx
from openai import RateLimitError

from app.config import settings


T = TypeVar("T")
MAX_RATE_LIMIT_ATTEMPTS = 3
MAX_RATE_LIMIT_DELAY_SECONDS = 8.0


def api_key_identity(api_key: str) -> str:
    """Return a stable, non-reversible process identity for a provider key."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def is_rate_limit_error(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None) or getattr(error, "status_code", None)
    if status_code == 429:
        return True
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429


def rate_limit_delay_seconds(error: Exception, attempt_index: int) -> float:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        raw_retry_after = headers.get("retry-after")
        try:
            retry_after = float(raw_retry_after)
        except (TypeError, ValueError):
            retry_after = 0.0
        if retry_after > 0:
            return min(MAX_RATE_LIMIT_DELAY_SECONDS, retry_after)
    return min(MAX_RATE_LIMIT_DELAY_SECONDS, float(2**attempt_index))


class ProviderRequestLimiter:
    """A process-local gate whose capacity is read dynamically per acquire.

    GankAIGC currently runs one Docker worker process with multiple logical
    slots. Keeping only the HMAC identity and active count avoids retaining or
    logging provider API keys. A future multi-VPS worker fleet must replace
    this process-local gate with a distributed primitive.
    """

    def __init__(self) -> None:
        self._active: dict[str, int] = {}

    @staticmethod
    def capacity() -> int:
        configured = int(settings.API_KEY_CONCURRENCY or 1)
        return configured if configured in {1, 2, 4} else max(1, min(4, configured))

    @asynccontextmanager
    async def slot(self, api_key: str) -> AsyncIterator[str]:
        identity = api_key_identity(api_key)
        while self._active.get(identity, 0) >= self.capacity():
            await asyncio.sleep(0.025)
        self._active[identity] = self._active.get(identity, 0) + 1
        try:
            yield identity
        finally:
            remaining = self._active.get(identity, 1) - 1
            if remaining > 0:
                self._active[identity] = remaining
            else:
                self._active.pop(identity, None)

    def active_count(self, api_key: str) -> int:
        return self._active.get(api_key_identity(api_key), 0)

    def reset(self) -> None:
        self._active.clear()


provider_request_limiter = ProviderRequestLimiter()


async def run_with_provider_limit(
    api_key: str,
    operation: Callable[[], Awaitable[T]],
) -> T:
    """Run one request with bounded 429 retries outside the occupied slot."""
    for attempt_index in range(MAX_RATE_LIMIT_ATTEMPTS):
        try:
            async with provider_request_limiter.slot(api_key):
                return await operation()
        except Exception as error:
            if not is_rate_limit_error(error) or attempt_index + 1 >= MAX_RATE_LIMIT_ATTEMPTS:
                raise
            await asyncio.sleep(rate_limit_delay_seconds(error, attempt_index))
    raise RuntimeError("provider retry loop exhausted")
