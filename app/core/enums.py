from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    AFFILIATE = "affiliate"
    ADVERTISER = "advertiser"


class AffiliateStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ConversionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


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


class QueueStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
