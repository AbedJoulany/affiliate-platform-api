"""Assign an explicit workspace to legacy NULL tenant rows, then retry alembic 013.

Migration 013 is fail-closed and does not backfill. Run this operator script
against a named workspace, then ``alembic upgrade head``.

  python -m scripts.assign_legacy_workspace_ids --workspace-id <uuid>
  python -m scripts.assign_legacy_workspace_ids --dry-run --workspace-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import dispose_async_engine, get_async_session_maker
from app.models.campaign import Campaign
from app.models.channel import TelegramChannel
from app.models.queue import QueueItem
from app.models.workspace import Workspace


@dataclass(frozen=True, slots=True)
class NullCounts:
    campaigns: int
    queue_items: int
    telegram_channels: int

    @property
    def total(self) -> int:
        return self.campaigns + self.queue_items + self.telegram_channels


async def count_null_workspace_rows(session: AsyncSession) -> NullCounts:
    async def _count(model) -> int:
        result = await session.execute(
            select(func.count()).select_from(model).where(model.workspace_id.is_(None))
        )
        return int(result.scalar_one())

    return NullCounts(
        campaigns=await _count(Campaign),
        queue_items=await _count(QueueItem),
        telegram_channels=await _count(TelegramChannel),
    )


async def assign_legacy_workspace_ids(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    dry_run: bool = False,
) -> NullCounts:
    """Assign NULL tenant rows to ``workspace_id``. Does not invent a workspace."""
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace {workspace_id} does not exist.")

    before = await count_null_workspace_rows(session)
    if before.total == 0 or dry_run:
        return before

    await session.execute(
        update(TelegramChannel)
        .where(TelegramChannel.workspace_id.is_(None))
        .values(workspace_id=workspace_id)
    )
    inherited = await session.execute(
        select(QueueItem.id, TelegramChannel.workspace_id)
        .join(TelegramChannel, QueueItem.channel_id == TelegramChannel.id)
        .where(
            QueueItem.workspace_id.is_(None),
            TelegramChannel.workspace_id.is_not(None),
        )
    )
    for queue_item_id, inherited_workspace_id in inherited.all():
        await session.execute(
            update(QueueItem)
            .where(QueueItem.id == queue_item_id)
            .values(workspace_id=inherited_workspace_id)
        )
    await session.execute(
        update(QueueItem)
        .where(QueueItem.workspace_id.is_(None))
        .values(workspace_id=workspace_id)
    )
    await session.execute(
        update(Campaign)
        .where(Campaign.workspace_id.is_(None))
        .values(workspace_id=workspace_id)
    )
    await session.flush()
    return await count_null_workspace_rows(session)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assign leftover NULL workspace_id values on campaigns, queue_items, "
            "and telegram_channels to one existing workspace. Required before "
            "alembic revision 013. Does not run inside the migration."
        )
    )
    parser.add_argument(
        "--workspace-id",
        required=True,
        help="Existing workspace UUID to assign to NULL tenant rows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print NULL counts only; do not UPDATE.",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    try:
        workspace_id = UUID(args.workspace_id.strip())
    except ValueError:
        print("Invalid --workspace-id; expected a UUID.", file=sys.stderr)
        return 1

    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            remaining = await assign_legacy_workspace_ids(
                session,
                workspace_id,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                print(
                    "Dry run — NULL rows: "
                    f"campaigns={remaining.campaigns}, "
                    f"queue_items={remaining.queue_items}, "
                    f"telegram_channels={remaining.telegram_channels}"
                )
            else:
                await session.commit()
                print(
                    "Assigned NULL tenant rows to workspace "
                    f"{workspace_id}. Remaining NULLs: "
                    f"campaigns={remaining.campaigns}, "
                    f"queue_items={remaining.queue_items}, "
                    f"telegram_channels={remaining.telegram_channels}"
                )
                if remaining.total == 0:
                    print("Safe to run: alembic upgrade head")
        except Exception:
            await session.rollback()
            raise
        finally:
            await dispose_async_engine()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
