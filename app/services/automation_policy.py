from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.enums import (
    AutomationExecutionState,
    AutomationFrequency,
    AutomationProvider,
    BotPermissionStatus,
    FacebookPageValidationStatus,
    UserRole,
    WorkspaceMembershipRole,
)
from app.models.automation_policy import AutomationPolicy
from app.models.workspace_settings import WorkspaceSettings
from app.repositories.automation_policy import AutomationPolicyRepository
from app.repositories.channel import ChannelRepository
from app.repositories.facebook_page import FacebookPageRepository
from app.repositories.workspace import WorkspaceMembershipRepository
from app.repositories.workspace_settings import WorkspaceSettingsRepository
from app.schemas.automation_policy import (
    AutomationContentRead,
    AutomationDestinationRead,
    AutomationDiscoveryRead,
    AutomationPolicyPatch,
    AutomationPolicyRead,
    AutomationScheduleRead,
)
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class DestinationEvaluation:
    response: AutomationDestinationRead | None
    ready: bool
    warning: str | None


class AutomationPolicyService:
    """Persistence and validation only; never starts automation work."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policies = AutomationPolicyRepository(session)
        self.settings = WorkspaceSettingsRepository(session)
        self.memberships = WorkspaceMembershipRepository(session)
        self.channels = ChannelRepository(session)
        self.pages = FacebookPageRepository(session)

    async def get(self, user: User, workspace_id: UUID) -> AutomationPolicyRead:
        await self._can_edit(user, workspace_id)
        policy = await self.policies.get_by_workspace_id(workspace_id)
        return await self._to_read(workspace_id, policy)

    async def patch(
        self,
        user: User,
        workspace_id: UUID,
        payload: AutomationPolicyPatch,
    ) -> AutomationPolicyRead:
        if not await self._can_edit(user, workspace_id):
            raise ForbiddenError()

        # Lock the parent workspace so PostgreSQL serializes first writes and
        # revision updates without relying on an unprotected read-check-write.
        if await self.policies.lock_workspace(workspace_id) is None:
            raise NotFoundError("Workspace not found")
        policy = await self.policies.get_by_workspace_id(workspace_id, for_update=True)
        values = payload.model_dump(exclude_unset=True)
        expected_revision = values.pop("expected_revision", None)
        destination_changed = "destination" in values

        if policy is None:
            if expected_revision not in (None, 0):
                raise ConflictError("Automation policy does not exist at this revision")
            policy = AutomationPolicy(workspace_id=workspace_id)
            is_new = True
        else:
            is_new = False
            if expected_revision is None:
                raise ValidationError("expected_revision is required for an existing policy")
            if expected_revision != policy.revision:
                raise ConflictError("Automation policy revision is stale")

        try:
            if is_new:
                self.session.add(policy)
                await self.session.flush()
            await self._apply_values(policy, values, workspace_id)
            self._validate_merged_policy(policy)
            await self._validate_enabled_transition(
                policy,
                values,
                workspace_id,
                is_new,
                destination_changed=destination_changed,
            )
            if not is_new:
                policy.revision += 1
            await self.session.flush()
            await self.session.refresh(policy)
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Automation policy could not be updated concurrently") from exc

        return await self._to_read(workspace_id, policy)

    @staticmethod
    def _validate_merged_policy(policy: AutomationPolicy) -> None:
        if (
            policy.min_price is not None
            and policy.max_price is not None
            and policy.min_price > policy.max_price
        ):
            raise ValidationError("min_price must be less than or equal to max_price")
        if (
            policy.min_commission is not None
            and policy.max_commission is not None
            and policy.min_commission > policy.max_commission
        ):
            raise ValidationError(
                "min_commission must be less than or equal to max_commission"
            )

    async def _can_edit(self, user: User, workspace_id: UUID) -> bool:
        if user.role == UserRole.ADMIN:
            return True
        membership = await self.memberships.get_membership(workspace_id, user.id)
        if membership is None:
            raise NotFoundError("Automation policy not found")
        return membership.role == WorkspaceMembershipRole.OWNER

    async def _apply_values(
        self,
        policy: AutomationPolicy,
        values: dict[str, Any],
        workspace_id: UUID,
    ) -> None:
        destination_supplied = "destination" in values
        if destination_supplied:
            destination = values.pop("destination")
            await self._apply_destination(policy, destination, workspace_id)

        discovery = values.pop("discovery", None)
        if discovery is not None:
            for key, value in discovery.items():
                if key == "keywords":
                    value = _normalize_keywords(value)
                setattr(policy, key, value)

        schedule = values.pop("schedule", None)
        if schedule is not None:
            for key, value in schedule.items():
                if key == "preferred_time_local" and value is not None:
                    value = _parse_time(value)
                if hasattr(value, "value"):
                    value = value.value
                setattr(policy, key, value)

        content = values.pop("content", None)
        if content is not None:
            for key, value in content.items():
                if key == "language":
                    key = "content_language"
                elif key == "length":
                    key = "content_length"
                if hasattr(value, "value"):
                    value = value.value
                setattr(policy, key, value)

        for key, value in values.items():
            setattr(policy, key, value)

    async def _apply_destination(
        self,
        policy: AutomationPolicy,
        destination: dict[str, Any] | None,
        workspace_id: UUID,
    ) -> None:
        if destination is None:
            policy.telegram_channel_id = None
            policy.facebook_page_id = None
            return

        provider = destination["provider"]
        if hasattr(provider, "value"):
            provider = provider.value
        if provider == AutomationProvider.TELEGRAM.value:
            channel_id = destination["channel_id"]
            channel = await self.channels.get_by_id_in_workspace(channel_id, workspace_id)
            if channel is None:
                raise NotFoundError("Telegram destination not found")
            policy.provider = provider
            policy.telegram_channel_id = channel.id
            policy.facebook_page_id = None
        else:
            page_id = destination["page_id"]
            page = await self.pages.get_in_workspace(page_id, workspace_id)
            if page is None:
                raise NotFoundError("Facebook destination not found")
            policy.provider = provider
            policy.facebook_page_id = page.id
            policy.telegram_channel_id = None

    async def _validate_enabled_transition(
        self,
        policy: AutomationPolicy,
        values: dict[str, Any],
        workspace_id: UUID,
        is_new: bool,
        *,
        destination_changed: bool,
    ) -> None:
        if not policy.enabled:
            return
        evaluation = await self._evaluate_destination(policy, workspace_id)
        enabling = values.get("enabled") is True
        if not evaluation.ready and (is_new or enabling or destination_changed):
            raise ValidationError(
                "An enabled automation policy requires an active, eligible destination"
            )

    async def _evaluate_destination(
        self,
        policy: AutomationPolicy,
        workspace_id: UUID,
    ) -> DestinationEvaluation:
        provider = AutomationProvider(policy.provider)
        if provider == AutomationProvider.TELEGRAM:
            if policy.telegram_channel_id is None:
                return DestinationEvaluation(
                    response=None,
                    ready=False,
                    warning="Select an active Telegram channel with posting permission",
                )
            channel = await self.channels.get_by_id_in_workspace(
                policy.telegram_channel_id,
                workspace_id,
            )
            if channel is None:
                return DestinationEvaluation(
                    response=None,
                    ready=False,
                    warning="The saved Telegram destination is no longer available",
                )
            if not channel.is_active:
                status = "inactive"
                warning = "The selected Telegram channel is inactive"
            elif (
                not channel.can_post_messages
                or channel.bot_permission_status
                not in {BotPermissionStatus.GRANTED, BotPermissionStatus.PARTIAL}
            ):
                status = "permission_missing"
                warning = "Telegram posting permission has not been granted"
            else:
                status = "ready"
                warning = None
            return DestinationEvaluation(
                response=AutomationDestinationRead(
                    provider=provider,
                    channel_id=channel.id,
                    label=channel.title or channel.username,
                    active=channel.is_active,
                    ready=status == "ready",
                    status=status,
                ),
                ready=status == "ready",
                warning=warning,
            )

        if policy.facebook_page_id is None:
            return DestinationEvaluation(
                response=None,
                ready=False,
                warning="Select an active, validated Facebook Page",
            )
        page = await self.pages.get_in_workspace(policy.facebook_page_id, workspace_id)
        if page is None:
            return DestinationEvaluation(
                response=None,
                ready=False,
                warning="The saved Facebook destination is no longer available",
            )
        if not page.is_active:
            status = "inactive"
            warning = "The selected Facebook Page is inactive"
        elif page.validation_status != FacebookPageValidationStatus.VALID:
            status = "not_validated"
            warning = "The selected Facebook Page has not been validated"
        else:
            status = "ready"
            warning = None
        return DestinationEvaluation(
            response=AutomationDestinationRead(
                provider=provider,
                page_id=page.id,
                label=page.page_name,
                active=page.is_active,
                ready=status == "ready",
                status=status,
            ),
            ready=status == "ready",
            warning=warning,
        )

    async def _to_read(
        self,
        workspace_id: UUID,
        policy: AutomationPolicy | None,
    ) -> AutomationPolicyRead:
        workspace_settings = await self.settings.get_by_workspace_id(workspace_id)
        timezone = _resolve_timezone(workspace_settings)
        if policy is None:
            return AutomationPolicyRead(
                id=None,
                workspace_id=workspace_id,
                revision=0,
                enabled=False,
                configuration_ready=False,
                execution_available=False,
                execution_state=AutomationExecutionState.DISABLED,
                destination=None,
                discovery=AutomationDiscoveryRead(
                    keywords=None,
                    min_price=None,
                    max_price=None,
                    min_rating=None,
                    min_orders=None,
                    min_discount=None,
                    min_commission=None,
                    max_commission=None,
                    products_per_run=5,
                ),
                schedule=AutomationScheduleRead(
                    frequency=AutomationFrequency.DAILY,
                    preferred_time_local="09:00",
                    timezone=timezone,
                    posts_per_day=1,
                ),
                content=AutomationContentRead(
                    ai_provider=None,
                    language=None,
                    tone=None,
                    content_type=None,
                    length=None,
                ),
                warnings=[],
                created_at=None,
                updated_at=None,
            )

        evaluation = await self._evaluate_destination(policy, workspace_id)
        warnings = [evaluation.warning] if evaluation.warning else []
        configuration_ready = evaluation.ready
        if not policy.enabled:
            state = AutomationExecutionState.DISABLED
        elif not configuration_ready:
            state = AutomationExecutionState.CONFIGURED_NOT_READY
        else:
            state = AutomationExecutionState.CONFIGURED_READY_NOT_ACTIVE

        return AutomationPolicyRead(
            id=policy.id,
            workspace_id=policy.workspace_id,
            revision=policy.revision,
            enabled=policy.enabled,
            configuration_ready=configuration_ready,
            execution_available=False,
            execution_state=state,
            destination=evaluation.response,
            discovery=AutomationDiscoveryRead(
                keywords=policy.keywords,
                min_price=policy.min_price,
                max_price=policy.max_price,
                min_rating=policy.min_rating,
                min_orders=policy.min_orders,
                min_discount=policy.min_discount,
                min_commission=policy.min_commission,
                max_commission=policy.max_commission,
                products_per_run=policy.products_per_run,
            ),
            schedule=AutomationScheduleRead(
                frequency=AutomationFrequency(policy.frequency),
                preferred_time_local=policy.preferred_time_local.strftime("%H:%M"),
                timezone=timezone,
                posts_per_day=policy.posts_per_day,
            ),
            content=AutomationContentRead(
                ai_provider=policy.ai_provider,
                language=policy.content_language,
                tone=policy.tone,
                content_type=policy.content_type,
                length=policy.content_length,
            ),
            warnings=warnings,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )


def _normalize_keywords(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("preferred_time_local must use HH:MM format") from exc


def _resolve_timezone(row: WorkspaceSettings | None) -> str:
    candidate = row.timezone if row is not None else "UTC"
    try:
        ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return candidate
