from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AliExpressCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "aliexpress_categories"

    category_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    category_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_category_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
