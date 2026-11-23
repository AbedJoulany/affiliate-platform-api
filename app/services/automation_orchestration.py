from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.automation_policy import AutomationPolicy
from app.models.automation_run import AutomationRun, AutomationRunItem
from app.repositories.automation_policy import AutomationPolicyRepository
from app.repositories.automation_run import AutomationRunRepository
from app.repositories.workspace_settings import WorkspaceSettingsRepository
from app.schemas.automation_content import AutomationContentPreviewRequest
from app.schemas.automation_policy import AutomationDestinationRead
from app.services.automation_content import AutomationContentGenerationService
from app.services.automation_queue import AutomationQueueService
from app.services.automation_scheduling import SchedulingError, resolve_local_time, resolve_timezone

# These implementation gates intentionally remain closed in Phase 8C.3. A later
# approved phase must add workspace owner/admin activation and budget enforcement.
WORKSPACE_ACTIVATION_IMPLEMENTED = False
AI_BUDGET_ENFORCEMENT_IMPLEMENTED = False
MAX_PRODUCTS_PER_RUN = 2
MAX_DISPATCH_LATENESS = timedelta(minutes=5)
RUN_LEASE = timedelta(minutes=10)


def automation_execution_available(settings: Settings | None = None) -> bool:
    current = settings or get_settings()
    return bool(
        current.automation_execution_enabled
        and not current.automation_emergency_stop
        and WORKSPACE_ACTIVATION_IMPLEMENTED
        and AI_BUDGET_ENFORCEMENT_IMPLEMENTED
    )


def daily_slot(
    now_utc: datetime,
    timezone_name: str,
    preferred_time: time,
) -> tuple[date, datetime]:
    """Resolve today's policy slot; timezone conversion is DST deterministic."""
    if now_utc.tzinfo is None:
        raise SchedulingError("Dispatcher timestamp must include timezone information")
    timezone = resolve_timezone(timezone_name)
    local_now = now_utc.astimezone(timezone)
    local_slot = datetime.combine(local_now.date(), preferred_time)
    resolved = resolve_local_time(local_slot, timezone).astimezone(UTC)
    return local_now.date(), resolved


class AutomationOrchestrationService:
    """Internal durable-run coordinator; the dispatcher remains gated off."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policies = AutomationPolicyRepository(session)
        self.settings = WorkspaceSettingsRepository(session)
        self.runs = AutomationRunRepository(session)
        self.queue = AutomationQueueService(session)

    async def dispatch_due(self, *, now_utc: datetime | None = None) -> dict[str, int | str]:
        # This is deliberately before any repository access or transaction.
        if not automation_execution_available():
            return {"status": "disabled", "claimed": 0, "missed": 0}
        return await self._dispatch_enabled(now_utc=now_utc or datetime.now(UTC))

    async def _dispatch_enabled(self, *, now_utc: datetime) -> dict[str, int | str]:
        now_utc = now_utc.astimezone(UTC)
        resumable = await self._recover_expired(now_utc)
        for run_id in resumable:
            owner = f"recovery:{uuid4()}"
            if await self.runs.resume_expired_claim(
                run_id,
                now=now_utc,
                lease_owner=owner,
                lease_expires_at=now_utc + RUN_LEASE,
            ):
                await self.session.commit()
                await self.execute_claimed_run(run_id)
        policies = await self.policies.list_enabled(limit=100)
        claimed = missed = 0
        for policy in policies:
            settings_row = await self.settings.get_by_workspace_id(policy.workspace_id)
            timezone_name = settings_row.timezone if settings_row else "UTC"
            try:
                local_date, scheduled_for = daily_slot(
                    now_utc, timezone_name, policy.preferred_time_local
                )
            except SchedulingError:
                continue
            if now_utc < scheduled_for:
                continue
            is_missed = now_utc - scheduled_for > MAX_DISPATCH_LATENESS
            owner = f"dispatcher:{uuid4()}"
            run = await self.runs.claim_daily_run(
                workspace_id=policy.workspace_id,
                policy_id=policy.id,
                policy_revision=policy.revision,
                local_date=local_date,
                scheduled_for=scheduled_for,
                lease_owner=None if is_missed else owner,
                lease_expires_at=now_utc if is_missed else now_utc + RUN_LEASE,
                initial_status="missed" if is_missed else "claimed",
            )
            if run is None:
                continue
            if is_missed:
                run.completed_at = now_utc
                run.error_category = "missed_schedule"
                run.error_summary = "Daily execution window was missed; no catch-up was run"
                missed += 1
                await self.session.commit()
                continue
            claimed += 1
            await self.session.commit()
            await self.execute_claimed_run(run.id)
        return {"status": "dispatched", "claimed": claimed, "missed": missed}

    async def execute_claimed_run(self, run_id: UUID) -> dict[str, str]:
        # A second gate protects direct/internal callers as well as Celery.
        if not automation_execution_available():
            return {"status": "disabled"}
        run = await self.runs.get(run_id, for_update=True)
        if run is None:
            return {"status": "not_found"}
        if run.status not in {"claimed", "running"}:
            return {"status": run.status}

        policy = await self.policies.get_by_workspace_id(run.workspace_id, for_update=True)
        if policy is None or not policy.enabled or policy.revision != run.policy_revision:
            run.status = "cancelled"
            run.completed_at = datetime.now(UTC)
            run.error_category = "policy_changed"
            run.error_summary = "Policy is missing, disabled, or changed since this run was claimed"
            await self.session.commit()
            return {"status": run.status}

        try:
            policy, destination, timezone_name = await self.queue._preflight(
                run.workspace_id,
                run.policy_revision,
                require_enabled=True,
            )
            await self._execute_pipeline(run, policy, destination, timezone_name)
        except Exception:
            await self.session.rollback()
            failed_run = await self.runs.get(run_id, for_update=True)
            if failed_run is not None:
                items = await self.runs.items_for_run(run_id)
                has_uncertain_generation = any(
                    item.generation_state in {"started", "uncertain"} for item in items
                )
                failed_run.status = (
                    "needs_operator_review" if has_uncertain_generation else "failed"
                )
                failed_run.completed_at = datetime.now(UTC)
                failed_run.error_category = (
                    "generation_outcome_uncertain"
                    if has_uncertain_generation
                    else "orchestration_failed"
                )
                failed_run.error_summary = (
                    "AI outcome may be uncertain; automatic regeneration is blocked"
                    if has_uncertain_generation
                    else "Run stopped after a safe internal processing error"
                )
                if has_uncertain_generation:
                    for item in items:
                        if item.generation_state == "started":
                            item.status = "uncertain"
                            item.generation_state = "uncertain"
                            item.failure_category = "worker_error_during_generation"
                            item.failure_summary = (
                                "AI request may have started; operator review is required"
                            )
                await self.session.commit()
            return {"status": "failed"}
        return {"status": "completed"}

    async def _execute_pipeline(
        self,
        run: AutomationRun,
        policy: AutomationPolicy,
        destination: AutomationDestinationRead,
        timezone_name: str,
    ) -> None:
        now = datetime.now(UTC)
        run.status = "running"
        run.started_at = run.started_at or now
        run.heartbeat_at = now
        run.lease_expires_at = now + RUN_LEASE
        if not run.lease_owner:
            run.lease_owner = f"worker:{uuid4()}"
        await self.session.commit()

        async def record_selection(selections: list) -> None:
            for selection in selections:
                existing = await self.runs.get_item(run.id, selection.product_id)
                if existing is None:
                    await self.runs.create_item(
                        run_id=run.id,
                        product_id=selection.product_id,
                        selection_rank=selection.rank,
                    )
            run.selected_count = len(selections)
            run.heartbeat_at = datetime.now(UTC)
            await self.session.commit()

        async def record_generation_started(product_id: UUID) -> None:
            item = await self.runs.get_item(run.id, product_id)
            if item is None:
                raise RuntimeError("Selected product checkpoint is missing")
            item.status = "generating"
            item.generation_state = "started"
            item.generation_started_at = datetime.now(UTC)
            run.heartbeat_at = datetime.now(UTC)
            run.lease_expires_at = datetime.now(UTC) + RUN_LEASE
            await self.session.commit()

        async def record_generation_succeeded(generated) -> None:
            item = await self.runs.get_item(run.id, generated.product_id)
            if item is None:
                raise RuntimeError("Selected product checkpoint is missing")
            item.status = "generated"
            item.generation_state = "succeeded"
            item.generation_completed_at = datetime.now(UTC)
            item.generated_content = generated.content
            item.affiliate_url_snapshot = generated.affiliate_url
            run.heartbeat_at = datetime.now(UTC)
            await self.session.commit()

        existing_items = await self.runs.items_for_run(run.id)
        if any(item.generation_state in {"started", "uncertain"} for item in existing_items):
            run.status = "needs_operator_review"
            run.completed_at = datetime.now(UTC)
            run.lease_owner = None
            run.lease_expires_at = None
            run.error_category = "generation_outcome_uncertain"
            run.error_summary = (
                "A previous AI request may have completed; automatic regeneration is blocked"
            )
            await self.session.commit()
            return

        persisted_generated = any(
            item.status == "generated" and item.generated_content for item in existing_items
        )
        generation_already_attempted = any(
            item.generation_state in {"succeeded", "failed"} for item in existing_items
        )
        if not persisted_generated and not generation_already_attempted:
            content = await AutomationContentGenerationService(self.session).preview_for_run(
                run.workspace_id,
                AutomationContentPreviewRequest(
                    expected_policy_revision=run.policy_revision,
                    max_products=min(policy.products_per_run, MAX_PRODUCTS_PER_RUN),
                    acknowledge_ai_cost=True,
                    idempotency_key=f"run:{run.id}",
                ),
                run.id,
                on_selected=record_selection,
                on_generation_started=record_generation_started,
                on_generation_succeeded=record_generation_succeeded,
            )
            for generated in content.results:
                item = await self.runs.get_item(run.id, generated.product_id)
                if item is None:
                    continue
                if generated.status == "generated":
                    # Successes were durably checkpointed before the next
                    # provider call; do not defer their only persistence here.
                    continue
                item.generation_completed_at = datetime.now(UTC)
                if generated.status in {"failed_timeout", "failed_provider"}:
                    item.status = "uncertain"
                    item.generation_state = "uncertain"
                    item.failure_category = generated.error_category or "provider_outcome_uncertain"
                    item.failure_summary = (
                        "AI outcome may be uncertain; automatic regeneration is blocked"
                    )
                elif generated.status.startswith("skipped"):
                    item.status = "skipped"
                    item.generation_state = "not_started"
                    item.failure_category = generated.error_category
                else:
                    item.status = "failed"
                    item.generation_state = "failed"
                    item.failure_category = generated.error_category
                    item.failure_summary = "Content generation or validation failed"
            await self.session.commit()
        elif generation_already_attempted:
            # A crash after a completed product must not replay the discovery
            # batch and spend on products whose generation had not started.
            for item in existing_items:
                if item.status == "selected" and item.generation_state == "not_started":
                    item.status = "skipped"
                    item.failure_category = "recovery_generation_not_repeated"
                    item.failure_summary = (
                        "Unstarted product generation was not repeated during recovery"
                    )
            await self.session.commit()

        # A persisted generation can resume at Queue creation. A started or
        # uncertain generation is never automatically submitted to AI again.
        items = await self.runs.items_for_run(run.id)
        for run_item in items:
            if run_item.status != "generated" or not run_item.generated_content:
                continue
            if run_item.product_id is None:
                run_item.status = "skipped"
                run_item.failure_category = "product_deleted"
                run_item.failure_summary = "Product was removed before Queue creation"
                await self.session.commit()
                continue
            result = self._content_result(run_item)

            # Re-read policy/destination immediately before every Queue write.
            policy, destination, timezone_name = await self.queue._preflight(
                run.workspace_id,
                run.policy_revision,
                require_enabled=True,
            )

            async def persist_queue(queue_item, target=run_item) -> None:
                target.status = "queued"
                target.queue_item_id = queue_item.id
                target.queue_created_at = datetime.now(UTC)
                target.failure_category = None
                target.failure_summary = None
                await self.session.flush()

            queue_result = await self.queue._create_one(
                workspace_id=run.workspace_id,
                policy=policy,
                destination=destination,
                item=result,
                timezone_name=timezone_name,
                before_commit=persist_queue,
            )
            if queue_result.status != "scheduled":
                run_item.status = (
                    "skipped"
                    if queue_result.status.startswith("skipped")
                    else "failed"
                )
                run_item.failure_category = queue_result.error_category
                run_item.failure_summary = "Queue scheduling did not complete"
                await self.session.commit()

        items = await self.runs.items_for_run(run.id)
        run.generated_count = sum(item.generation_state == "succeeded" for item in items)
        run.queued_count = sum(item.status == "queued" for item in items)
        run.skipped_count = sum(item.status == "skipped" for item in items)
        run.failed_count = sum(item.status in {"failed", "uncertain"} for item in items)
        run.completed_at = datetime.now(UTC)
        run.lease_expires_at = None
        run.lease_owner = None
        if any(item.generation_state == "uncertain" for item in items):
            run.status = "needs_operator_review"
        elif run.failed_count or run.skipped_count:
            run.status = "completed_with_errors"
        else:
            run.status = "completed"
        await self.session.commit()

    @staticmethod
    def _content_result(item: AutomationRunItem):
        from app.schemas.automation_content import AutomationContentProductResult

        return AutomationContentProductResult(
            product_id=item.product_id,
            selection_rank=item.selection_rank,
            recommendation_score=None,
            status="generated",
            content=item.generated_content,
            affiliate_url=item.affiliate_url_snapshot,
            requires_human_review=True,
        )

    async def _recover_expired(self, now_utc: datetime) -> list[UUID]:
        expired = await self.runs.expired_runs(now=now_utc)
        resumable: list[UUID] = []
        for run in expired:
            expired_lease_at = run.lease_expires_at
            if expired_lease_at is not None and expired_lease_at.tzinfo is None:
                expired_lease_at = expired_lease_at.replace(tzinfo=UTC)
            items = await self.runs.items_for_run(run.id)
            uncertain = [
                item for item in items if item.generation_state in {"started", "uncertain"}
            ]
            if uncertain:
                for item in uncertain:
                    item.status = "uncertain"
                    item.generation_state = "uncertain"
                    item.failure_category = item.failure_category or "worker_lost_during_generation"
                    item.failure_summary = (
                        "Worker lease expired during a possibly billable AI request"
                    )
                run.status = "needs_operator_review"
                run.error_category = "generation_outcome_uncertain"
                run.error_summary = "AI outcome requires operator review; it will not be retried"
                run.completed_at = now_utc
                run.lease_owner = None
                run.lease_expires_at = None
            elif (
                expired_lease_at is not None
                and now_utc - expired_lease_at > MAX_DISPATCH_LATENESS
            ):
                run.status = "missed"
                run.error_category = "recovery_window_expired"
                run.error_summary = "Run recovery window expired; no catch-up execution was started"
                run.completed_at = now_utc
                run.lease_owner = None
                run.lease_expires_at = None
            elif any(item.status == "generated" and item.generated_content for item in items):
                # This bounded queue-only recovery path reuses persisted content
                # and never calls AI again.
                run.status = "claimed"
                run.lease_owner = ""
                run.lease_expires_at = now_utc
                resumable.append(run.id)
            else:
                # No provider call was durably started; retrying the run is safe.
                run.status = "claimed"
                run.lease_owner = ""
                run.lease_expires_at = now_utc
                resumable.append(run.id)
            run.heartbeat_at = now_utc
        if expired:
            await self.session.commit()
        return resumable
