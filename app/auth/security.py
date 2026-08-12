import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt


def hash_password(password: str) -> str:
    """Hashes a plain text password using native bcrypt."""
    pwd_bytes = password.encode("utf-8")
    # Using 12 rounds to match your original configuration
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a stored hashed password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def generate_refresh_token() -> str:
    """Generate a high-entropy opaque refresh token for the client."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    """Return a deterministic SHA-256 hex digest for database lookup."""
    return sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    subject: UUID | str,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    # 🚀 Inline import to break circular initialization chain
    from app.core.config import get_settings
    settings = get_settings()

    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    # 🚀 Inline import to break circular initialization chain
    from app.core.config import get_settings
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Could not validate credentials") from exc

    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    return payload
