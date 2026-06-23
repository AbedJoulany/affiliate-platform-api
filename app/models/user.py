"""Re-export User model from the auth module for backward compatibility."""

from app.auth.models import User

__all__ = ["User"]
