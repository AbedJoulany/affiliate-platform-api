from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.enums import (
    BotPermissionStatus,
    FacebookPageValidationStatus,
    QueueStatus,
)
from app.models.channel import TelegramChannel
from app.models.facebook_page import FacebookPage
from app.models.queue import QueueItem, QueuePublishAttempt
from app.models.workspace import Workspace
from app.models.workspace_settings import WorkspaceSettings
from app.services.dashboard import DashboardService
from tests.conftest import SessionLocal


def _attempt(
    queue_id,
    *,
    attempt_number: int,
    provider: str,
    status: str,
    occurred_at: datetime,
) -> QueuePublishAttempt:
    is_outcome = status in {"failed", "ambiguous"}
    return QueuePublishAttempt(
        queue_id=queue_id,
        attempt_number=attempt_number,
        provider=provider,
        status=status,
        content_hash=(f"{attempt_number:064x}"),
        idempotency_expires_at=occurred_at + timedelta(hours=24),
        error_code="provider_error" if is_outcome else None,
        error_message="provider response was inconclusive" if is_outcome else None,
        occurred_at=occurred_at,
    )


def _queue_item(
    workspace_id,
    *,
    provider: str,
    status: QueueStatus,
    published_at: datetime | None = None,
) -> QueueItem:
    return QueueItem(
        title=f"Dashboard {provider} {uuid4().hex[:8]}",
        content="Dashboard test content",
        provider=provider,
        status=status,
        published_at=published_at,
        workspace_id=workspace_id,
    )


@pytest.mark.asyncio
async def test_dashboard_publishing_snapshot_is_scoped_and_dst_aware():
    async with SessionLocal() as session:
        workspace = Workspace(name="Dashboard snapshot workspace")
        other_workspace = Workspace(name="Other dashboard workspace")
        session.add_all([workspace, other_workspace])
        await session.flush()
        session.add(
            WorkspaceSettings(
                workspace_id=workspace.id,
                timezone="America/New_York",
            )
        )

        generated_at = datetime(2026, 3, 8, 16, 0, tzinfo=UTC)
        day_start = datetime(2026, 3, 8, 5, 0, tzinfo=UTC)
        day_end = datetime(2026, 3, 9, 4, 0, tzinfo=UTC)

        telegram_published = _queue_item(
            workspace.id,
            provider="telegram",
            status=QueueStatus.PUBLISHED,
            published_at=day_start + timedelta(hours=1),
        )
        facebook_published = _queue_item(
            workspace.id,
            provider="facebook",
            status=QueueStatus.PUBLISHED,
            published_at=day_end - timedelta(seconds=1),
        )
        old_published = _queue_item(
            workspace.id,
            provider="telegram",
            status=QueueStatus.PUBLISHED,
            published_at=day_start - timedelta(seconds=1),
        )
        telegram_failed = _queue_item(
            workspace.id,
            provider="telegram",
            status=QueueStatus.FAILED,
        )
        facebook_failed = _queue_item(
            workspace.id,
            provider="facebook",
            status=QueueStatus.FAILED,
        )
        unresolved_ambiguous = _queue_item(
            workspace.id,
            provider="facebook",
            status=QueueStatus.FAILED,
        )
        resolved_ambiguous = _queue_item(
            workspace.id,
            provider="facebook",
            status=QueueStatus.FAILED,
        )
        published_after_ambiguous = _queue_item(
            workspace.id,
            provider="facebook",
            status=QueueStatus.PUBLISHED,
            published_at=day_start + timedelta(hours=2),
        )
        boundary_failed = _queue_item(
            workspace.id,
            provider="telegram",
            status=QueueStatus.FAILED,
        )
        other_workspace_published = _queue_item(
            other_workspace.id,
            provider="facebook",
            status=QueueStatus.PUBLISHED,
            published_at=day_start + timedelta(hours=1),
        )
        other_workspace_failed = _queue_item(
            other_workspace.id,
            provider="telegram",
            status=QueueStatus.FAILED,
        )
        session.add_all(
            [
                telegram_published,
                facebook_published,
                old_published,
                telegram_failed,
                facebook_failed,
                unresolved_ambiguous,
                resolved_ambiguous,
                published_after_ambiguous,
                boundary_failed,
                other_workspace_published,
                other_workspace_failed,
            ]
        )
        await session.flush()
        session.add_all(
            [
                _attempt(
                    telegram_failed.id,
                    attempt_number=1,
                    provider="telegram",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=3),
                ),
                _attempt(
                    telegram_failed.id,
                    attempt_number=2,
                    provider="facebook",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=4),
                ),
                _attempt(
                    facebook_failed.id,
                    attempt_number=1,
                    provider="facebook",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=5),
                ),
                _attempt(
                    unresolved_ambiguous.id,
                    attempt_number=1,
                    provider="facebook",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=6),
                ),
                _attempt(
                    unresolved_ambiguous.id,
                    attempt_number=2,
                    provider="facebook",
                    status="ambiguous",
                    occurred_at=day_start + timedelta(hours=7),
                ),
                _attempt(
                    resolved_ambiguous.id,
                    attempt_number=1,
                    provider="facebook",
                    status="ambiguous",
                    occurred_at=day_start + timedelta(hours=8),
                ),
                _attempt(
                    resolved_ambiguous.id,
                    attempt_number=2,
                    provider="facebook",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=9),
                ),
                _attempt(
                    published_after_ambiguous.id,
                    attempt_number=1,
                    provider="facebook",
                    status="ambiguous",
                    occurred_at=day_start + timedelta(hours=10),
                ),
                _attempt(
                    boundary_failed.id,
                    attempt_number=1,
                    provider="telegram",
                    status="failed",
                    occurred_at=day_end,
                ),
                _attempt(
                    other_workspace_published.id,
                    attempt_number=1,
                    provider="facebook",
                    status="failed",
                    occurred_at=day_start + timedelta(hours=1),
                ),
            ]
        )
        await session.commit()

        response = await DashboardService(session).get_dashboard(
            workspace.id,
            now=generated_at,
        )

    assert response.reporting.timezone == "America/New_York"
    assert response.reporting.day_start_utc == day_start
    assert response.reporting.day_end_utc == day_end
    assert response.reporting.generated_at == generated_at
    assert response.publishing.published_today == 3
    assert response.publishing.failed_today == 4
    assert response.publishing.ambiguous_unresolved == 1
    assert response.publishing.by_provider.telegram.published == 1
    assert response.publishing.by_provider.telegram.failed == 1
    assert response.publishing.by_provider.facebook.published == 2
    assert response.publishing.by_provider.facebook.failed == 3
    attention_by_id = {item.queue_id: item for item in response.attention_items}
    assert attention_by_id[telegram_failed.id].issue == "failed"
    assert attention_by_id[facebook_failed.id].issue == "failed"
    assert attention_by_id[unresolved_ambiguous.id].issue == "ambiguous"
    assert resolved_ambiguous.id not in attention_by_id
    assert published_after_ambiguous.id not in attention_by_id
    assert other_workspace_failed.id not in attention_by_id


@pytest.mark.asyncio
async def test_dashboard_attention_is_bounded_and_destinations_are_workspace_scoped():
    async with SessionLocal() as session:
        workspace = Workspace(name="Dashboard readiness workspace")
        other_workspace = Workspace(name="Other readiness workspace")
        session.add_all([workspace, other_workspace])
        await session.flush()

        session.add_all(
            [
                TelegramChannel(
                    telegram_channel_id="@dashboard-granted",
                    title="Granted",
                    workspace_id=workspace.id,
                    bot_permission_status=BotPermissionStatus.GRANTED,
                    can_post_messages=True,
                    is_active=True,
                ),
                TelegramChannel(
                    telegram_channel_id="@dashboard-partial",
                    title="Partial",
                    workspace_id=workspace.id,
                    bot_permission_status=BotPermissionStatus.PARTIAL,
                    can_post_messages=True,
                    is_active=True,
                ),
                TelegramChannel(
                    telegram_channel_id="@dashboard-inactive",
                    title="Inactive",
                    workspace_id=workspace.id,
                    bot_permission_status=BotPermissionStatus.GRANTED,
                    can_post_messages=True,
                    is_active=False,
                ),
                TelegramChannel(
                    telegram_channel_id="@dashboard-other",
                    title="Other",
                    workspace_id=other_workspace.id,
                    bot_permission_status=BotPermissionStatus.GRANTED,
                    can_post_messages=True,
                    is_active=True,
                ),
                FacebookPage(
                    workspace_id=workspace.id,
                    facebook_page_id="1001",
                    page_name="Valid Page",
                    encrypted_access_token="encrypted",
                    is_active=True,
                    validation_status=FacebookPageValidationStatus.VALID,
                ),
                FacebookPage(
                    workspace_id=workspace.id,
                    facebook_page_id="1002",
                    page_name="Invalid Page",
                    encrypted_access_token="encrypted",
                    is_active=True,
                    validation_status=FacebookPageValidationStatus.INVALID,
                ),
                FacebookPage(
                    workspace_id=workspace.id,
                    facebook_page_id="1003",
                    page_name="Inactive Page",
                    encrypted_access_token="encrypted",
                    is_active=False,
                    validation_status=FacebookPageValidationStatus.VALID,
                ),
                FacebookPage(
                    workspace_id=other_workspace.id,
                    facebook_page_id="2001",
                    page_name="Other Page",
                    encrypted_access_token="encrypted",
                    is_active=True,
                    validation_status=FacebookPageValidationStatus.VALID,
                ),
            ]
        )
        attention_items = [
            _queue_item(
                workspace.id,
                provider="facebook",
                status=QueueStatus.FAILED,
            )
            for _ in range(12)
        ]
        session.add_all(attention_items)
        await session.flush()
        issue_time = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
        session.add_all(
            [
                _attempt(
                    item.id,
                    attempt_number=1,
                    provider="facebook",
                    status="failed",
                    occurred_at=issue_time,
                )
                for item in attention_items
            ]
        )
        await session.commit()

        response = await DashboardService(session).get_dashboard(
            workspace.id,
            now=datetime(2026, 11, 17, 9, 0, tzinfo=UTC),
        )

    assert len(response.attention_items) == 10
    assert [item.queue_id for item in response.attention_items] == sorted(
        (item.id for item in attention_items),
    )[:10]
    assert response.destination_readiness.telegram.total == 3
    assert response.destination_readiness.telegram.active == 2
    assert response.destination_readiness.telegram.permission_granted == 2
    assert response.destination_readiness.facebook.total == 3
    assert response.destination_readiness.facebook.active == 2
    assert response.destination_readiness.facebook.validated == 1
    assert response.destination_readiness.facebook.publishing_permission_verified is False


@pytest.mark.asyncio
@pytest.mark.parametrize("timezone", [None, "Invalid/Zone"])
async def test_dashboard_invalid_or_missing_timezone_falls_back_to_utc(timezone):
    async with SessionLocal() as session:
        workspace = Workspace(name="UTC fallback workspace")
        session.add(workspace)
        await session.flush()
        if timezone is not None:
            session.add(
                WorkspaceSettings(workspace_id=workspace.id, timezone=timezone)
            )
            await session.flush()

        generated_at = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
        response = await DashboardService(session).get_dashboard(
            workspace.id,
            now=generated_at,
        )

    assert response.reporting.timezone == "UTC"
    assert response.reporting.day_start_utc == datetime(
        2026, 11, 17, 0, 0, tzinfo=UTC
    )
    assert response.reporting.day_end_utc == datetime(
        2026, 11, 18, 0, 0, tzinfo=UTC
    )
