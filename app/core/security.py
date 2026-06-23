"""Re-export auth security helpers for backward compatibility."""

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# Legacy aliases
get_password_hash = hash_password
decode_token = decode_access_token

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "get_password_hash",
    "decode_token",
]
