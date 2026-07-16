from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import ProductStatus


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "products"

    aliexpress_product_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    gallery_images: Mapped[list[str] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    product_url: Mapped[str] = mapped_column(String(512), nullable=False)
    affiliate_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    shipping_info: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    score: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0000"), nullable=False)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status", native_enum=False),
        default=ProductStatus.DRAFT,
        nullable=False,
        index=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
