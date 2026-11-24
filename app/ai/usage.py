"""Internal provider response metadata used for conservative automation accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    provider: str
    requested_model: str
    actual_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    complete: bool


@dataclass(frozen=True, slots=True)
class ProviderGeneration:
    content: str
    usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class ModelTokenBounds:
    max_input_tokens: int
    max_output_tokens: int

    @property
    def reserved_total_tokens(self) -> int:
        # Separate maxima intentionally over-reserve when a provider defines a
        # combined context window. This avoids relying on tokenizer estimates.
        return self.max_input_tokens + self.max_output_tokens


# Only pinned, documented model identifiers have an automation hard bound.
# Update these values only after reviewing the provider's current model docs.
MODEL_TOKEN_BOUNDS: dict[tuple[str, str], ModelTokenBounds] = {
    # https://developers.openai.com/api/docs/models/gpt-4o-mini
    ("openai", "gpt-4o-mini-2024-07-18"): ModelTokenBounds(128_000, 16_384),
    # https://ai.google.dev/gemini-api/docs/models/gemini-4-hydrogen
    ("gemini", "gemini-4-hydrogen"): ModelTokenBounds(1_048_576, 65_536),
}


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_openai_usage(data: dict[str, Any], requested_model: str) -> ProviderUsage:
    model = data.get("model")
    model = model if isinstance(model, str) and model else None
    usage = data.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    prompt = _count(usage.get("prompt_tokens"))
    completion = _count(usage.get("completion_tokens"))
    total = _count(usage.get("total_tokens"))
    complete = (
        model is not None
        and prompt is not None
        and completion is not None
        and total is not None
        and total == prompt + completion
    )
    return ProviderUsage(
        provider="openai",
        requested_model=requested_model,
        actual_model=model,
        input_tokens=prompt,
        output_tokens=completion,
        total_tokens=total,
        complete=complete,
    )


def parse_gemini_usage(data: dict[str, Any], requested_model: str) -> ProviderUsage:
    model = data.get("modelVersion")
    model = model if isinstance(model, str) and model else None
    usage = data.get("usageMetadata")
    usage = usage if isinstance(usage, dict) else {}
    prompt = _count(usage.get("promptTokenCount"))
    tool_prompt = _count(usage.get("toolUsePromptTokenCount", 0))
    candidates = _count(usage.get("candidatesTokenCount"))
    thoughts = _count(usage.get("thoughtsTokenCount", 0))
    total = _count(usage.get("totalTokenCount"))
    known_input = prompt + tool_prompt if prompt is not None and tool_prompt is not None else None
    known_output = (
        candidates + thoughts
        if candidates is not None and thoughts is not None
        else None
    )
    complete = (
        model is not None
        and known_input is not None
        and known_output is not None
        and total is not None
        and total == known_input + known_output
    )
    return ProviderUsage(
        provider="gemini",
        requested_model=requested_model,
        actual_model=model,
        input_tokens=known_input,
        output_tokens=known_output,
        total_tokens=total,
        complete=complete,
    )
