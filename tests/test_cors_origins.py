"""Local frontend origins: localhost and 127.0.0.1 are distinct CORS origins."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
import pytest

from app.core.config import Settings

LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_default_cors_origins_allow_localhost_and_loopback(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = _settings()
    for origin in LOCAL_FRONTEND_ORIGINS:
        assert origin in settings.cors_origins


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", LOCAL_FRONTEND_ORIGINS)
async def test_login_preflight_allows_local_frontend_origins(origin: str):
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_FRONTEND_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
