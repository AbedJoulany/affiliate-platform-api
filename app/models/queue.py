from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.sqltypes import Boolean

from app.core.database import Base
from app.core.enums import QueueStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.channel import TelegramChannel
    from app.models.product import Product


class _ContentHashFormatCheck(ColumnElement[bool]):
    """Dialect-aware content_hash format predicate.

    PostgreSQL keeps the migration's ``~`` regex check. SQLite (used by
    ``Base.metadata.create_all`` in tests) has no ``~`` operator, so an
    equivalent length/case/GLOB form is compiled instead. Constraint name and
    PostgreSQL semantics stay aligned with migration 008.
    """

    inherit_cache = True
    type = Boolean()


@compiles(_ContentHashFormatCheck, "postgresql")
def _compile_content_hash_format_postgresql(element, compiler, **kw) -> str:
    return "content_hash ~ '^[0-9a-f]{64}$'"


@compiles(_ContentHashFormatCheck, "sqlite")
def _compile_content_hash_format_sqlite(element, compiler, **kw) -> str:
    # SQLite GLOB negation in character classes is ``[^...]`` (not ``[!...]``).
    # ``[!0-9a-f]`` inverts incorrectly on current SQLite and rejects valid hex.
    return (
        "length(content_hash) = 64 "
        "AND content_hash = lower(content_hash) "
        "AND content_hash NOT GLOB '*[^0-9a-f]*'"
    )


class QueueItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "queue_items"

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status", native_enum=False),
        default=QueueStatus.DRAFT,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    channel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    channel: Mapped["TelegramChannel | None"] = relationship("TelegramChannel")
    product: Mapped["Product | None"] = relationship("Product")
    publish_attempts: Mapped[list["QueuePublishAttempt"]] = relationship(
        "QueuePublishAttempt",
        back_populates="queue_item",
    )


class QueuePublishAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable record of a single Telegram publish try for a queue item.

    ``status`` is attempt-scoped (started/succeeded/failed) and independent of
    ``QueueStatus``. The relationship to ``QueueItem`` is historical and must not
    be used to drive ``QueueItem.status``.
    """

    __tablename__ = "queue_publish_attempts"
    __table_args__ = (
        CheckConstraint(
            "attempt_number > 0",
            name="ck_queue_publish_attempts_attempt_number_positive",
        ),
        CheckConstraint(
            "provider = 'telegram'",
            name="ck_queue_publish_attempts_provider_telegram",
        ),
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed')",
            name="ck_queue_publish_attempts_status",
        ),
        CheckConstraint(
            _ContentHashFormatCheck(),
            name="ck_queue_publish_attempts_content_hash_format",
        ),
        CheckConstraint(
            "("
            "status = 'started' "
            "AND error_code IS NULL "
            "AND error_message IS NULL "
            "AND provider_chat_id IS NULL "
            "AND provider_message_id IS NULL"
            ") OR ("
            "status = 'succeeded' "
            "AND error_code IS NULL "
            "AND error_message IS NULL "
            "AND provider_chat_id IS NOT NULL "
            "AND provider_message_id IS NOT NULL"
            ") OR ("
            "status = 'failed' "
            "AND error_code IS NOT NULL "
            "AND error_message IS NOT NULL "
            "AND provider_chat_id IS NULL "
            "AND provider_message_id IS NULL"
            ")",
            name="ck_queue_publish_attempts_outcome_consistency",
        ),
        UniqueConstraint(
            "queue_id",
            "attempt_number",
            name="uq_queue_publish_attempts_queue_id_attempt_number",
        ),
        Index(
            "ix_queue_publish_attempts_guard_lookup",
            "queue_id",
            "content_hash",
            "status",
            "idempotency_expires_at",
        ),
        Index(
            "ix_queue_publish_attempts_provider_status_occurred",
            "provider",
            "status",
            "occurred_at",
        ),
    )

    queue_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("queue_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'telegram'"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'started'"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    idempotency_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    queue_item: Mapped["QueueItem"] = relationship(
        "QueueItem",
        back_populates="publish_attempts",
    )
