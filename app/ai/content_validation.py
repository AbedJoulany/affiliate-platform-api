from __future__ import annotations

import re

from app.core.enums import ContentType

_URL_RE = re.compile(r"(?i)(?:https?://|www\.)[^\s<>\]\[()\"']+")
_SECRET_RE = re.compile(
    r"(?i)(?:sk-[a-z0-9]{12,}|AIza[a-z0-9_-]{20,}|bearer\s+[a-z0-9._-]{16,}|"
    r"(?:OPENAI|GEMINI|JWT)_API_KEY|JWT_SECRET_KEY)"
)
_SENSITIVE_CLAIM_RE = re.compile(
    r"(?i)(?:guaranteed\s+(?:cure|returns?|results?)|100%\s+(?:guaranteed|effective)|"
    r"official(?:ly)?\s+(?:certified|approved)|"
    r"(?:يضمن|مضمون|يشفي|يعالج|معتمد\s+رسميًا|معتمد\s+رسميا|نتائج\s+مضمونة))"
)

_MAX_CHARS: dict[ContentType, int] = {
    ContentType.SOCIAL: 2_000,
    ContentType.DESCRIPTION: 3_000,
    ContentType.TELEGRAM: 3_000,
    ContentType.FACEBOOK: 5_000,
    ContentType.BLOG: 8_000,
    ContentType.EMAIL: 6_000,
}


def validate_generated_content(content: str, content_type: ContentType) -> list[str]:
    """Return deterministic validation categories for model output."""
    failures: list[str] = []
    normalized = content.strip() if isinstance(content, str) else ""
    if not normalized:
        failures.append("empty_content")
        return failures
    if len(normalized) > _MAX_CHARS[content_type]:
        failures.append("content_too_long")
    if _URL_RE.search(normalized):
        failures.append("unauthorized_url")
    if _SECRET_RE.search(normalized):
        failures.append("credential_like_content")
    if _SENSITIVE_CLAIM_RE.search(normalized):
        failures.append("sensitive_claim")
    return failures
