from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.usage import parse_gemini_usage, parse_openai_usage
from app.core.config import Settings
from app.services.automation_ai_budget import (
    AutomationAIBudgetService,
    AutomationAIBudgetUnavailable,
)
from app.services.exceptions import AIProviderError


def _settings(**overrides: Any) -> Settings:
    values = {
        "_env_file": None,
        "automation_ai_budget_enabled": True,
        "automation_ai_workspace_daily_request_limit": 4,
        "automation_ai_global_daily_request_limit": 10,
        "automation_ai_workspace_daily_token_limit": 300_000,
        "automation_ai_global_daily_token_limit": 600_000,
        "automation_ai_max_output_tokens": 2048,
    }
    values.update(overrides)
    return Settings(**values)


def test_openai_usage_parses_actual_model_and_all_completion_tokens():
    usage = parse_openai_usage(
        {
            "model": "gpt-4o-mini-2024-07-18",
            "usage": {
                "prompt_tokens": 17,
                "completion_tokens": 11,
                "total_tokens": 28,
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        },
        "gpt-4o-mini-2024-07-18",
    )
    assert usage.provider == "openai"
    assert usage.actual_model == "gpt-4o-mini-2024-07-18"
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (17, 11, 28)
    assert usage.complete is True


def test_openai_missing_or_inconsistent_usage_is_untrusted():
    missing = parse_openai_usage({"model": "gpt-4o-mini"}, "gpt-4o-mini")
    inconsistent = parse_openai_usage(
        {
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 11},
        },
        "gpt-4o-mini",
    )
    assert missing.complete is False
    assert inconsistent.complete is False


def test_gemini_usage_includes_tool_prompt_and_thought_tokens():
    usage = parse_gemini_usage(
        {
            "modelVersion": "gemini-4-hydrogen",
            "usageMetadata": {
                "promptTokenCount": 20,
                "toolUsePromptTokenCount": 4,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 6,
                "totalTokenCount": 40,
            },
        },
        "gemini-4-hydrogen",
    )
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (24, 16, 40)
    assert usage.complete is True


def test_gemini_missing_or_inconsistent_usage_is_untrusted():
    missing = parse_gemini_usage(
        {"modelVersion": "gemini-4-hydrogen", "candidates": []}, "gemini-4-hydrogen"
    )
    inconsistent = parse_gemini_usage(
        {
            "modelVersion": "gemini-4-hydrogen",
            "usageMetadata": {
                "promptTokenCount": 20,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 2,
                "totalTokenCount": 40,
            },
        },
        "gemini-4-hydrogen",
    )
    assert missing.complete is False
    assert inconsistent.complete is False


@pytest.mark.asyncio
async def test_automation_provider_calls_enforce_output_limit_and_parse_usage(monkeypatch):
    openai_body = {
        "model": "gpt-4o-mini-2024-07-18",
        "choices": [{"message": {"content": "safe copy"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13},
    }
    gemini_body = {
        "modelVersion": "gemini-4-hydrogen",
        "candidates": [{"content": {"parts": [{"text": "safe copy"}]}}],
        "usageMetadata": {
            "promptTokenCount": 8,
            "candidatesTokenCount": 5,
            "thoughtsTokenCount": 1,
            "totalTokenCount": 14,
        },
    }
    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    response_body = openai_body

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, json, **kwargs):
            calls.append((str(url), json, kwargs))
            request = httpx.Request("POST", str(url))
            return httpx.Response(200, json=response_body, request=request)

    monkeypatch.setattr("app.ai.openai_provider.httpx.AsyncClient", Client)
    monkeypatch.setattr("app.ai.gemini_provider.httpx.AsyncClient", Client)
    openai = OpenAIProvider(api_key="test-key", model="gpt-4o-mini-2024-07-18")
    first = await openai.generate_content_with_usage("prompt", max_output_tokens=700)
    assert first.content == "safe copy"
    assert calls[-1][1]["max_completion_tokens"] == 700
    assert first.usage.complete is True

    response_body = gemini_body
    gemini = GeminiProvider(api_key="test-key", model="gemini-4-hydrogen")
    second = await gemini.generate_content_with_usage("prompt", max_output_tokens=600)
    assert second.content == "safe copy"
    assert calls[-1][1]["generationConfig"]["maxOutputTokens"] == 600
    assert calls[-1][2]["headers"]["x-goog-api-key"] == "test-key"
    assert "key=" not in calls[-1][0]
    assert second.usage.total_tokens == 14
    assert second.usage.complete is True


@pytest.mark.asyncio
async def test_gemini_automation_key_stays_out_of_url_and_provider_errors(monkeypatch):
    fake_key = "test-gemini-key"
    observed: dict[str, Any] = {}

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, **_kwargs):
            observed["url"] = str(url)
            observed["headers"] = headers
            request = httpx.Request("POST", str(url), headers=headers)
            response = httpx.Response(403, request=request)
            response.raise_for_status()

    monkeypatch.setattr("app.ai.gemini_provider.httpx.AsyncClient", Client)
    provider = GeminiProvider(api_key=fake_key, model="gemini-4-hydrogen")

    with pytest.raises(AIProviderError) as error:
        await provider.generate_content_with_usage("prompt", max_output_tokens=64)

    assert observed["headers"]["x-goog-api-key"] == fake_key
    assert "key=" not in observed["url"]
    assert fake_key not in observed["url"]
    assert fake_key not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_kind", ["openai", "gemini"])
@pytest.mark.parametrize("failure_kind", ["timeout", "rate_limit"])
async def test_accounted_provider_submission_is_single_attempt(
    monkeypatch,
    provider_kind,
    failure_kind,
):
    calls = 0

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **_kwargs):
            nonlocal calls
            calls += 1
            if failure_kind == "timeout":
                raise httpx.ReadTimeout("simulated provider timeout")
            request = httpx.Request("POST", str(url))
            return httpx.Response(429, request=request)

    if provider_kind == "openai":
        monkeypatch.setattr("app.ai.openai_provider.httpx.AsyncClient", Client)
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini-2024-07-18")
    else:
        monkeypatch.setattr("app.ai.gemini_provider.httpx.AsyncClient", Client)
        provider = GeminiProvider(api_key="test-key", model="gemini-4-hydrogen")

    with pytest.raises(AIProviderError) as error:
        await provider.generate_content_with_usage("prompt", max_output_tokens=64)
    assert calls == 1
    assert error.value.__suppress_context__ is True


def test_budget_configuration_and_model_bounds_fail_closed():
    plan = AutomationAIBudgetService(None, _settings()).plan(
        "openai", "gpt-4o-mini-2024-07-18"
    )
    assert plan.reservation_tokens == 128_000 + 2048
    gemini_plan = AutomationAIBudgetService(None, _settings()).plan(
        "gemini", "gemini-4-hydrogen"
    )
    assert gemini_plan.token_bounds.max_input_tokens == 1_048_576
    assert gemini_plan.reservation_tokens > 1_048_576

    for settings, provider, model in (
        (_settings(automation_ai_budget_enabled=False), "openai", "gpt-4o-mini-2024-07-18"),
        (
            _settings(automation_ai_global_daily_token_limit=None),
            "openai",
            "gpt-4o-mini-2024-07-18",
        ),
        (_settings(), "openai", "gpt-4o-mini"),
        (_settings(automation_ai_max_output_tokens=20_000), "openai", "gpt-4o-mini-2024-07-18"),
    ):
        with pytest.raises(AutomationAIBudgetUnavailable):
            AutomationAIBudgetService(None, settings).plan(provider, model)
