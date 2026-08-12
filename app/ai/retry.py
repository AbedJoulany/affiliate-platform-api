"""Shared retry policy for AI provider HTTP calls (OpenAI / Gemini)."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Fixed policy — intentionally not Settings-driven (Phase C' Task 2).
AI_MAX_ATTEMPTS = 2
AI_BASE_BACKOFF_SECONDS = 1.0
AI_JITTER_SECONDS = 0.5
# Cap untrusted Retry-After values so a sync request cannot hang indefinitely.
AI_MAX_RETRY_AFTER_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retryable: bool
    retry_after: float | None = None
    reason: str = ""


def parse_retry_after(response: httpx.Response) -> float | None:
    """Return a trusted Retry-After delay in seconds, or None to use backoff."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return min(value, AI_MAX_RETRY_AFTER_SECONDS)


def classify_httpx_failure(exc: BaseException) -> RetryDecision:
    """Classify an httpx failure for the AI retry policy."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429 or 500 <= status < 600:
            return RetryDecision(
                retryable=True,
                retry_after=parse_retry_after(exc.response),
                reason=f"http_{status}",
            )
        return RetryDecision(retryable=False, reason=f"http_{status}")

    # Timeouts and network/transport failures are transient.
    if isinstance(exc, httpx.TransportError):
        return RetryDecision(retryable=True, reason="transport")

    return RetryDecision(retryable=False, reason="non_retryable")


def compute_backoff_seconds(
    attempt_index: int,
    *,
    retry_after: float | None = None,
) -> float:
    """Delay before the next attempt. Attempt index is 0-based (first retry = 0)."""
    if retry_after is not None:
        return float(retry_after) + random.uniform(0, AI_JITTER_SECONDS)
    return (AI_BASE_BACKOFF_SECONDS * (2**attempt_index)) + random.uniform(
        0,
        AI_JITTER_SECONDS,
    )


async def execute_with_retries[T](
    operation: Callable[[], Awaitable[T]],
    *,
    provider: str,
    max_attempts: int = AI_MAX_ATTEMPTS,
) -> T:
    """Run ``operation`` with at most ``max_attempts`` tries for transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_error: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            decision = classify_httpx_failure(exc)
            if not decision.retryable or attempt >= max_attempts - 1:
                raise

            delay = compute_backoff_seconds(attempt, retry_after=decision.retry_after)
            logger.info(
                "AI provider retry scheduled provider=%s attempt=%s/%s reason=%s delay=%.3fs",
                provider,
                attempt + 1,
                max_attempts,
                decision.reason,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_error is not None  # pragma: no cover
    raise last_error
