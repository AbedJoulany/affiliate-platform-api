import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    AFFILIATE = "affiliate"
    ADVERTISER = "advertiser"


class AffiliateStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ConversionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class BotPermissionStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    GRANTED = "granted"
    PARTIAL = "partial"
    DENIED = "denied"
