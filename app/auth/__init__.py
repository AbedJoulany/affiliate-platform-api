"""Authentication module: user model, JWT, password hashing, and auth endpoints."""

from app.auth.dependencies import get_current_user, require_roles
from app.auth.models import User
from app.auth.router import router

__all__ = [
    "User",
    "get_current_user",
    "require_roles",
    "router",
]
