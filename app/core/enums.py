from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class BotPermissionStatus(StrEnum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    GRANTED = "granted"
    PARTIAL = "partial"
    DENIED = "denied"


class AIProviderType(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"


class ContentType(StrEnum):
    SOCIAL = "social"
    DESCRIPTION = "description"
    TELEGRAM = "telegram"
    FACEBOOK = "facebook"
    BLOG = "blog"
    EMAIL = "email"


class ToneProfile(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    LUXURY = "luxury"
    TECHNICAL = "technical"
    URGENT = "urgent"
    MINIMAL = "minimal"
    PERSUASIVE = "persuasive"
    FUNNY = "funny"


class ContentLanguage(StrEnum):
    AR = "ar"
    EN = "en"
    FR = "fr"
    DE = "de"


class ContentLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class QueueStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
