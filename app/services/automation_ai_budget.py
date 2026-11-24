from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy import case, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.usage import MODEL_TOKEN_BOUNDS, ModelTokenBounds, ProviderUsage
from app.core.config import Settings, get_settings
from app.models.automation_ai_usage import AutomationAIUsageReservation
from app.services.automation_scheduling import SchedulingError, resolve_timezone


class AutomationAIBudgetError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class AutomationAIBudgetUnavailable(AutomationAIBudgetError):
    pass


class AutomationAIBudgetExhausted(AutomationAIBudgetError):
    pass


class DuplicateAutomationAISubmission(AutomationAIBudgetError):
    pass


@dataclass(frozen=True, slots=True)
class AutomationAIBudgetPlan:
    provider: str
    model: str
    output_token_limit: int
    token_bounds: ModelTokenBounds
    workspace_daily_requests: int
    global_daily_requests: int
    workspace_daily_tokens: int
    global_daily_tokens: int

    @property
    def reservation_tokens(self) -> int:
        return self.token_bounds.max_input_tokens + self.output_token_limit


class AutomationAIBudgetService:
    """PostgreSQL-serialized durable admission, reservation, and settlement."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def plan(self, provider: str, model: str) -> AutomationAIBudgetPlan:
        settings = self.settings
        values = (
            settings.automation_ai_workspace_daily_request_limit,
            settings.automation_ai_global_daily_request_limit,
            settings.automation_ai_workspace_daily_token_limit,
            settings.automation_ai_global_daily_token_limit,
            settings.automation_ai_max_output_tokens,
        )
        if not settings.automation_ai_budget_enabled or any(
            value is None or value <= 0 for value in values
        ):
            raise AutomationAIBudgetUnavailable("ai_budget_not_configured")
        bounds = MODEL_TOKEN_BOUNDS.get((provider, model))
        if bounds is None:
            raise AutomationAIBudgetUnavailable("ai_model_has_no_verified_token_bound")
        output_limit = settings.automation_ai_max_output_tokens
        if output_limit is None or output_limit > bounds.max_output_tokens:
            raise AutomationAIBudgetUnavailable("ai_output_limit_is_unsupported")
        return AutomationAIBudgetPlan(
            provider=provider,
            model=model,
            output_token_limit=output_limit,
            token_bounds=bounds,
            workspace_daily_requests=settings.automation_ai_workspace_daily_request_limit,
            global_daily_requests=settings.automation_ai_global_daily_request_limit,
            workspace_daily_tokens=settings.automation_ai_workspace_daily_token_limit,
            global_daily_tokens=settings.automation_ai_global_daily_token_limit,
        )

    async def reserve(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        run_item_id: UUID,
        timezone_name: str | None,
        plan: AutomationAIBudgetPlan,
        now: datetime | None = None,
    ) -> UUID:
        if self.session.bind is None or self.session.bind.dialect.name != "postgresql":
            raise AutomationAIBudgetUnavailable("postgresql_budget_store_required")
        moment = (now or datetime.now(UTC)).astimezone(UTC)
        try:
            workspace_day = moment.astimezone(resolve_timezone(timezone_name)).date()
        except (SchedulingError, ZoneInfoNotFoundError, ValueError) as exc:
            raise AutomationAIBudgetUnavailable("workspace_timezone_invalid") from exc
        global_day = moment.date()

        # Every admission acquires the global bucket first, then its workspace
        # bucket. The locks are transaction-scoped and released at commit; none
        # are held while awaiting a provider.
        await self._advisory_lock(f"automation-ai:global:{global_day.isoformat()}")
        await self._advisory_lock(
            f"automation-ai:workspace:{workspace_id}:{workspace_day.isoformat()}"
        )
        existing = await self.session.scalar(
            select(AutomationAIUsageReservation)
            .where(AutomationAIUsageReservation.run_item_id == run_item_id)
            .with_for_update()
        )
        if existing is not None and existing.status != "released":
            await self.session.rollback()
            raise DuplicateAutomationAISubmission("ai_submission_already_reserved")

        global_count, global_tokens = await self._usage_for_global_day(global_day)
        workspace_count, workspace_tokens = await self._usage_for_workspace_day(
            workspace_id, workspace_day
        )
        if (
            global_count + 1 > plan.global_daily_requests
            or workspace_count + 1 > plan.workspace_daily_requests
            or global_tokens + plan.reservation_tokens > plan.global_daily_tokens
            or workspace_tokens + plan.reservation_tokens > plan.workspace_daily_tokens
        ):
            await self.session.rollback()
            raise AutomationAIBudgetExhausted("ai_daily_budget_exhausted")

        reservation_id = uuid4()
        if existing is None:
            reservation = AutomationAIUsageReservation(
                workspace_id=workspace_id,
                run_id=run_id,
                run_item_id=run_item_id,
                provider_submission_id=reservation_id,
                provider=plan.provider,
                requested_model=plan.model,
                workspace_usage_date=workspace_day,
                global_usage_date=global_day,
                status="reserved",
                reserved_tokens=plan.reservation_tokens,
            )
            self.session.add(reservation)
        else:
            existing.provider_submission_id = reservation_id
            existing.provider = plan.provider
            existing.requested_model = plan.model
            existing.workspace_usage_date = workspace_day
            existing.global_usage_date = global_day
            existing.status = "reserved"
            existing.reserved_tokens = plan.reservation_tokens
            existing.actual_model = None
            existing.actual_input_tokens = None
            existing.actual_output_tokens = None
            existing.actual_total_tokens = None
            existing.usage_complete = False
            existing.submitted_at = None
            existing.settled_at = None
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateAutomationAISubmission("ai_submission_already_reserved") from exc
        return reservation_id

    async def mark_submitted(self, reservation_id: UUID) -> bool:
        reservation = await self.session.scalar(
            select(AutomationAIUsageReservation)
            .where(AutomationAIUsageReservation.provider_submission_id == reservation_id)
            .with_for_update()
        )
        if reservation is None or reservation.status != "reserved":
            await self.session.rollback()
            return False
        reservation.status = "submitted"
        reservation.submitted_at = datetime.now(UTC)
        await self.session.commit()
        return True

    async def settle(
        self,
        reservation_id: UUID,
        usage: ProviderUsage,
    ) -> str:
        reservation = await self.session.scalar(
            select(AutomationAIUsageReservation)
            .where(AutomationAIUsageReservation.provider_submission_id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            await self.session.rollback()
            raise AutomationAIBudgetUnavailable("ai_reservation_not_found")
        if reservation.status in {"settled", "uncertain", "released"}:
            await self.session.rollback()
            return reservation.status

        reservation.actual_model = usage.actual_model
        reservation.actual_input_tokens = usage.input_tokens
        reservation.actual_output_tokens = usage.output_tokens
        reservation.actual_total_tokens = usage.total_tokens
        trusted = (
            reservation.status == "submitted"
            and usage.complete
            and usage.provider == reservation.provider
            and usage.requested_model == reservation.requested_model
            and usage.actual_model == reservation.requested_model
            and usage.total_tokens is not None
            and usage.total_tokens <= reservation.reserved_tokens
        )
        reservation.usage_complete = trusted
        reservation.status = "settled" if trusted else "uncertain"
        reservation.settled_at = datetime.now(UTC) if trusted else None
        await self.session.commit()
        return reservation.status

    async def mark_uncertain(self, reservation_id: UUID) -> None:
        await self.session.execute(
            update(AutomationAIUsageReservation)
            .where(
                AutomationAIUsageReservation.provider_submission_id == reservation_id,
                AutomationAIUsageReservation.status == "submitted",
            )
            .values(status="uncertain")
        )
        await self.session.commit()

    async def release_before_submission(self, reservation_id: UUID) -> bool:
        result = await self.session.execute(
            update(AutomationAIUsageReservation)
            .where(
                AutomationAIUsageReservation.provider_submission_id == reservation_id,
                AutomationAIUsageReservation.status == "reserved",
            )
            .values(status="released")
        )
        await self.session.commit()
        return result.rowcount == 1

    async def recover_interrupted_run(
        self,
        run_id: UUID,
        *,
        commit: bool = True,
    ) -> None:
        # 'reserved' is committed before submission and can be released safely;
        # 'submitted' may have reached a billable provider and is retained.
        await self.session.execute(
            update(AutomationAIUsageReservation)
            .where(
                AutomationAIUsageReservation.run_id == run_id,
                AutomationAIUsageReservation.status == "reserved",
            )
            .values(status="released")
        )
        await self.session.execute(
            update(AutomationAIUsageReservation)
            .where(
                AutomationAIUsageReservation.run_id == run_id,
                AutomationAIUsageReservation.status == "submitted",
            )
            .values(status="uncertain")
        )
        if commit:
            await self.session.commit()

    async def _advisory_lock(self, key: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": key},
        )

    async def _usage_for_global_day(self, usage_day) -> tuple[int, int]:
        return await self._usage(
            AutomationAIUsageReservation.global_usage_date == usage_day
        )

    async def _usage_for_workspace_day(self, workspace_id: UUID, usage_day) -> tuple[int, int]:
        return await self._usage(
            AutomationAIUsageReservation.workspace_id == workspace_id,
            AutomationAIUsageReservation.workspace_usage_date == usage_day,
        )

    async def _usage(self, *criteria) -> tuple[int, int]:
        charged_tokens = case(
            (
                AutomationAIUsageReservation.status == "settled",
                func.coalesce(AutomationAIUsageReservation.actual_total_tokens, 0),
            ),
            (
                AutomationAIUsageReservation.actual_total_tokens
                > AutomationAIUsageReservation.reserved_tokens,
                AutomationAIUsageReservation.actual_total_tokens,
            ),
            else_=AutomationAIUsageReservation.reserved_tokens,
        )
        row = (
            await self.session.execute(
                select(
                    func.count(AutomationAIUsageReservation.id),
                    func.coalesce(func.sum(charged_tokens), 0),
                ).where(
                    *criteria,
                    AutomationAIUsageReservation.status != "released",
                )
            )
        ).one()
        return int(row[0]), int(row[1])
