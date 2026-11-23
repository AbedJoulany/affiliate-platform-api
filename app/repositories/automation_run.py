from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation_run import AutomationRun, AutomationRunItem


class AutomationRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_daily_run(
        self,
        *,
        workspace_id: UUID,
        policy_id: UUID,
        policy_revision: int,
        local_date: date,
        scheduled_for: datetime,
        lease_owner: str | None,
        lease_expires_at: datetime,
        initial_status: str = "claimed",
    ) -> AutomationRun | None:
        """Atomically reserve one logical workspace/policy/local-day run."""
        values = {
            "id": uuid4(),
            "workspace_id": workspace_id,
            "policy_id": policy_id,
            "policy_revision": policy_revision,
            "local_date": local_date,
            "scheduled_for": scheduled_for,
            "status": initial_status,
            "lease_owner": lease_owner,
            "lease_expires_at": lease_expires_at,
            "heartbeat_at": datetime.now(UTC),
        }
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = pg_insert(AutomationRun).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(AutomationRun).values(**values)
        else:
            raise RuntimeError("Durable automation claims require PostgreSQL or SQLite")
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                AutomationRun.workspace_id,
                AutomationRun.policy_id,
                AutomationRun.local_date,
            ]
        ).returning(AutomationRun.id)
        claimed_id = (await self.session.execute(statement)).scalar_one_or_none()
        if claimed_id is None:
            return None
        await self.session.flush()
        return await self.session.get(AutomationRun, claimed_id)

    async def get(self, run_id: UUID, *, for_update: bool = False) -> AutomationRun | None:
        statement = select(AutomationRun).where(AutomationRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def resume_expired_claim(
        self,
        run_id: UUID,
        *,
        now: datetime,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> bool:
        result = await self.session.execute(
            update(AutomationRun)
            .where(
                AutomationRun.id == run_id,
                AutomationRun.status == "claimed",
                AutomationRun.lease_expires_at <= now,
            )
            .values(
                lease_owner=lease_owner,
                lease_expires_at=lease_expires_at,
                heartbeat_at=now,
            )
        )
        return result.rowcount == 1

    async def get_item(self, run_id: UUID, product_id: UUID) -> AutomationRunItem | None:
        result = await self.session.execute(
            select(AutomationRunItem).where(
                AutomationRunItem.run_id == run_id,
                AutomationRunItem.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_item(
        self,
        *,
        run_id: UUID,
        product_id: UUID,
        selection_rank: int,
    ) -> AutomationRunItem:
        item = AutomationRunItem(
            run_id=run_id,
            product_id=product_id,
            selection_rank=selection_rank,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def expired_runs(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[AutomationRun]:
        result = await self.session.execute(
            select(AutomationRun)
            .where(
                AutomationRun.status.in_(("claimed", "running")),
                AutomationRun.lease_expires_at.is_not(None),
                AutomationRun.lease_expires_at <= now,
            )
            .order_by(AutomationRun.lease_expires_at, AutomationRun.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def items_for_run(self, run_id: UUID) -> list[AutomationRunItem]:
        result = await self.session.execute(
            select(AutomationRunItem)
            .where(AutomationRunItem.run_id == run_id)
            .order_by(AutomationRunItem.selection_rank, AutomationRunItem.id)
        )
        return list(result.scalars().all())
