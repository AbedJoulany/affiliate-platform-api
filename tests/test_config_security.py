"""Phase D Task 1 — JWT secret configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEFAULT_JWT_SECRET_KEY,
    JWT_SECRET_MIN_LENGTH,
    Settings,
)


def _settings(**overrides) -> Settings:
    """Build Settings without reading .env, so tests stay deterministic."""
    return Settings(_env_file=None, **overrides)


def test_development_allows_default_jwt_secret():
    settings = _settings(app_env="development", jwt_secret_key=DEFAULT_JWT_SECRET_KEY)
    assert settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY
    assert settings.is_development is True


def test_development_allows_short_jwt_secret():
    settings = _settings(app_env="development", jwt_secret_key="short")
    assert settings.jwt_secret_key == "short"


@pytest.mark.parametrize("app_env", ["production", "staging", "test"])
def test_non_development_rejects_default_jwt_secret(app_env: str):
    with pytest.raises(ValidationError) as exc_info:
        _settings(app_env=app_env, jwt_secret_key=DEFAULT_JWT_SECRET_KEY)

    message = str(exc_info.value)
    assert "JWT_SECRET_KEY" in message
    assert "default" in message.lower()
    assert DEFAULT_JWT_SECRET_KEY not in message


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_non_development_rejects_short_jwt_secret(app_env: str):
    short_secret = "x" * (JWT_SECRET_MIN_LENGTH - 1)
    with pytest.raises(ValidationError) as exc_info:
        _settings(app_env=app_env, jwt_secret_key=short_secret)

    message = str(exc_info.value)
    assert "JWT_SECRET_KEY" in message
    assert str(JWT_SECRET_MIN_LENGTH) in message
    assert short_secret not in message


@pytest.mark.parametrize("app_env", ["production", "staging", "test"])
def test_non_development_accepts_valid_long_non_default_secret(app_env: str):
    secret = "a" * JWT_SECRET_MIN_LENGTH + "-not-the-default"
    settings = _settings(app_env=app_env, jwt_secret_key=secret)
    assert settings.jwt_secret_key == secret
    assert settings.app_env == app_env


def test_non_development_accepts_secret_exactly_at_minimum_length():
    secret = "b" * JWT_SECRET_MIN_LENGTH
    assert len(secret) == JWT_SECRET_MIN_LENGTH
    assert secret != DEFAULT_JWT_SECRET_KEY
    settings = _settings(app_env="production", jwt_secret_key=secret)
    assert settings.jwt_secret_key == secret


def test_non_development_rejects_secret_one_below_minimum_length():
    secret = "c" * (JWT_SECRET_MIN_LENGTH - 1)
    assert len(secret) == JWT_SECRET_MIN_LENGTH - 1
    with pytest.raises(ValidationError) as exc_info:
        _settings(app_env="production", jwt_secret_key=secret)

    assert secret not in str(exc_info.value)


def test_validation_error_never_includes_secret_value():
    secret = "must-not-leak-short"
    assert len(secret) < JWT_SECRET_MIN_LENGTH
    with pytest.raises(ValidationError) as exc_info:
        _settings(app_env="production", jwt_secret_key=secret)

    assert secret not in str(exc_info.value)
    assert secret not in repr(exc_info.value)

    with pytest.raises(ValidationError) as default_exc:
        _settings(app_env="production", jwt_secret_key=DEFAULT_JWT_SECRET_KEY)

    assert DEFAULT_JWT_SECRET_KEY not in str(default_exc.value)
    assert DEFAULT_JWT_SECRET_KEY not in repr(default_exc.value)
