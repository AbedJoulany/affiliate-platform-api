"""Shared API dependencies — auth dependencies are re-exported from app.auth."""

from app.auth.dependencies import get_current_user, oauth2_scheme, require_roles

__all__ = ["get_current_user", "oauth2_scheme", "require_roles"]
