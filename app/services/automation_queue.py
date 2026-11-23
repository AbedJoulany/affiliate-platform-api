from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.enums import AutomationFrequency, AutomationProvider, UserRole
from app.models.automation_policy import AutomationPolicy
from app.models.queue import QueueItem
from app.repositories.automation_policy import AutomationPolicyRepository
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from app.repositories.workspace_settings import WorkspaceSettingsRepository
from app.schemas.automation_content import (
    AutomationContentPreviewRequest,
    AutomationContentPreviewResponse,
    AutomationContentProductResult,
)
from app.schemas.automation_policy import AutomationDestinationRead
from app.schemas.automation_queue import (
    AutomationQueuePrepareRequest,
    AutomationQueuePrepareResponse,
    AutomationQueueProductResult,
)
from app.schemas.queue import QueueCreate
from app.services.automation_content import AutomationContentGenerationService
from app.services.automation_policy import AutomationPolicyService
from app.services.automation_scheduling import (
    SchedulingError,
    resolve_timezone,
)
from app.services.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from app.services.queue import DEFAULT_AFFILIATE_BUTTON_TEXT, QueueService


class AutomationQueueService:
    """Explicit, member-authorized automation-to-scheduled-Queue operation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policies = AutomationPolicyRepository(session)
        self.settings = WorkspaceSettingsRepository(session)
        self.memberships = WorkspaceMembershipRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.queue_service = QueueService(session)

    async def prepare(
        self,
        user: User,
        workspace_id: UUID,
        payload: AutomationQueuePrepareRequest,
    ) -> AutomationQueuePrepareResponse:
        await self._authorize_member(user, workspace_id)
        policy, destination, timezone_name = await self._preflight(
            workspace_id,
            payload.expected_policy_revision,
        )
        effective_max_products = min(payload.max_products, policy.products_per_run, 2)
        content_payload = AutomationContentPreviewRequest(
            expected_policy_revision=payload.expected_policy_revision,
            max_products=effective_max_products,
            acknowledge_ai_cost=payload.acknowledge_ai_cost,
            idempotency_key=payload.idempotency_key,
        )

        content = await AutomationContentGenerationService(self.session).preview(
            user,
            workspace_id,
            content_payload,
            authorize_policy=False,
        )

        # Do not create Queue records using stale policy, destination, or
        # timezone state after a potentially slow paid generation operation.
        policy, destination, timezone_name = await self._preflight(
            workspace_id,
            payload.expected_policy_revision,
        )
        return await self._schedule_generated(
            workspace_id=workspace_id,
            policy=policy,
            destination=destination,
            timezone_name=timezone_name,
            content=content,
        )

    async def _authorize_member(self, user: User, workspace_id: UUID) -> None:
        if user.role == UserRole.ADMIN:
            if await self.workspaces.get_by_id(workspace_id) is None:
                raise ForbiddenError()
            return
        if await self.memberships.get_membership(workspace_id, user.id) is None:
            raise ForbiddenError()

    async def _preflight(
        self,
        workspace_id: UUID,
        expected_revision: int,
        *,
        require_enabled: bool = False,
    ) -> tuple[AutomationPolicy, AutomationDestinationRead, str]:
        policy = await self.policies.get_by_workspace_id(workspace_id)
        if policy is None:
            raise NotFoundError("Automation policy not found; save an automation policy first")
        if policy.revision != expected_revision:
            raise ConflictError("Automation policy changed; reload before scheduling")
        if require_enabled and not policy.enabled:
            raise ConflictError("Automation policy is disabled")
        if AutomationFrequency(policy.frequency) != AutomationFrequency.DAILY:
            raise ValidationError("Only daily automation scheduling is supported")

        evaluation = await AutomationPolicyService(self.session)._evaluate_destination(
            policy,
            workspace_id,
        )
        if not evaluation.ready or evaluation.response is None:
            raise ValidationError(evaluation.warning or "Automation destination is not ready")

        settings = await self.settings.get_by_workspace_id(workspace_id)
        timezone_name = settings.timezone if settings is not None else "UTC"
        resolve_timezone(timezone_name)
        return policy, evaluation.response, timezone_name

    async def _schedule_generated(
        self,
        *,
        workspace_id: UUID,
        policy: AutomationPolicy,
        destination: AutomationDestinationRead,
        timezone_name: str,
        content: AutomationContentPreviewResponse,
    ) -> AutomationQueuePrepareResponse:
        generated = [item for item in content.results if item.status == "generated"]
        results: list[AutomationQueueProductResult] = []
        for item in content.results:
            if item.status != "generated":
                results.append(self._map_non_generated(item))
                continue
            result = await self._create_one(
                workspace_id=workspace_id,
                policy=policy,
                destination=destination,
                item=item,
                timezone_name=timezone_name,
            )
            results.append(result)

        scheduled_count = sum(item.status == "scheduled" for item in results)
        skipped_count = sum(item.status.startswith("skipped") for item in results)
        failed_count = sum(item.status.startswith("failed") for item in results)
        warnings = list(content.warnings)
        warnings.append(
            "Scheduled items may be published automatically by the existing Queue "
            "scheduler when due."
        )
        return AutomationQueuePrepareResponse(
            workspace_id=workspace_id,
            policy_id=policy.id,
            policy_revision=policy.revision,
            prepared_at=datetime.now(UTC),
            provider=AutomationProvider(policy.provider),
            destination=destination,
            selected_count=content.selected_count,
            generated_count=len(generated),
            scheduled_count=scheduled_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            results=results,
            warnings=warnings,
        )

    async def _create_one(
        self,
        *,
        workspace_id: UUID,
        policy: AutomationPolicy,
        destination: AutomationDestinationRead,
        item: AutomationContentProductResult,
        timezone_name: str,
        before_commit: Callable[[QueueItem], Awaitable[None]] | None = None,
    ) -> AutomationQueueProductResult:
        if not item.content or not item.affiliate_url:
            return self._queue_result(
                item,
                status="failed_validation",
                error_category="missing_canonical_affiliate_url",
            )
        payload = QueueCreate(
            title=None,
            content=item.content,
            status="scheduled",
            # QueueCreate requires a provisional future value. QueueService
            # replaces it with the authoritative slot after locking and
            # re-reading destination occupancy.
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            provider=policy.provider,
            channel_id=destination.channel_id,
            facebook_page_id=destination.page_id,
            product_id=item.product_id,
            button_text=DEFAULT_AFFILIATE_BUTTON_TEXT,
            button_url=item.affiliate_url,
        )
        try:
            queue_item = await self.queue_service.create_automation_scheduled(
                payload,
                workspace_id,
                expected_affiliate_url=item.affiliate_url,
                timezone_name=timezone_name,
                preferred_time_local=policy.preferred_time_local,
                daily_limit=policy.posts_per_day,
            )
            if before_commit is not None:
                await before_commit(queue_item)
            await self.session.commit()
        except SchedulingError:
            await self.session.rollback()
            return self._queue_result(
                item,
                status="skipped_no_available_slot",
                error_category="no_available_slot",
            )
        except ConflictError:
            await self.session.rollback()
            return self._queue_result(
                item,
                status="skipped_duplicate",
                error_category="product_history_conflict",
            )
        except (NotFoundError, ValidationError):
            await self.session.rollback()
            return self._queue_result(
                item,
                status="skipped_ineligible",
                error_category="product_revalidation_failed",
            )
        except ServiceError:
            await self.session.rollback()
            return self._queue_result(
                item,
                status="failed_queue",
                error_category="queue_validation_failed",
            )
        except Exception:
            await self.session.rollback()
            return self._queue_result(
                item,
                status="failed_queue",
                error_category="queue_persistence_failed",
            )
        return self._queue_result(
            item,
            status="scheduled",
            queue_item_id=queue_item.id,
            scheduled_at=queue_item.scheduled_at,
        )

    @staticmethod
    def _map_non_generated(
        item: AutomationContentProductResult,
    ) -> AutomationQueueProductResult:
        if item.status == "failed_validation":
            status = "failed_validation"
        elif item.status in {"skipped_ineligible", "failed_not_found"}:
            status = "skipped_ineligible"
        elif item.status == "skipped_after_global_failure":
            status = "skipped_after_global_failure"
        else:
            status = "failed_generation"
        return AutomationQueueProductResult(
            product_id=item.product_id,
            selection_rank=item.selection_rank,
            recommendation_score=item.recommendation_score,
            status=status,
            warnings=item.warnings,
            error_category=item.error_category,
        )

    @staticmethod
    def _queue_result(
        item: AutomationContentProductResult,
        *,
        status: str,
        queue_item_id: UUID | None = None,
        scheduled_at: datetime | None = None,
        error_category: str | None = None,
    ) -> AutomationQueueProductResult:
        return AutomationQueueProductResult(
            product_id=item.product_id,
            selection_rank=item.selection_rank,
            recommendation_score=item.recommendation_score,
            status=status,  # type: ignore[arg-type]
            queue_item_id=queue_item_id,
            scheduled_at=scheduled_at,
            warnings=item.warnings,
            error_category=error_category or item.error_category,
        )
