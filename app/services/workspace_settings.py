from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import UserRole, WorkspaceMembershipRole
from app.models.user import User
from app.models.workspace_settings import WorkspaceSettings
from app.repositories.channel import ChannelRepository
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from app.repositories.workspace_settings import WorkspaceSettingsRepository
from app.schemas.workspace_settings import (
    ProviderConnectionStatus,
    WorkspaceDiscoveryMode,
    WorkspaceSettingsPatch,
    WorkspaceSettingsRead,
)
from app.services.exceptions import ForbiddenError, NotFoundError, ValidationError

_NOT_FOUND = "Workspace settings not found"


def _configured(value: str | None) -> bool:
    return bool(value and value.strip())


def _parse_workspace_header(raw_workspace_id: str | None) -> UUID:
    if raw_workspace_id is None or not raw_workspace_id.strip():
        raise ForbiddenError()
    try:
        return UUID(raw_workspace_id.strip())
    except ValueError as exc:
        raise ForbiddenError() from exc


def connection_status(settings: Settings) -> ProviderConnectionStatus:
    return ProviderConnectionStatus(
        aliexpress=_configured(settings.aliexpress_app_key)
        and _configured(settings.aliexpress_app_secret),
        telegram_bot=_configured(settings.telegram_bot_token),
        openai=_configured(settings.openai_api_key),
        gemini=_configured(settings.gemini_api_key),
        image_search=settings.aliexpress_enable_ds_image_search,
    )


class WorkspaceSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings_rows = WorkspaceSettingsRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.memberships = WorkspaceMembershipRepository(session)
        self.channels = ChannelRepository(session)

    async def resolve_workspace(
        self,
        user: User,
        x_workspace_id: str | None,
    ) -> tuple[UUID, bool]:
        """Return (workspace_id, can_edit). Missing header → 403; unknown/other → 404."""
        workspace_id = _parse_workspace_header(x_workspace_id)
        workspace = await self.workspaces.get_by_id(workspace_id)
        if user.role == UserRole.ADMIN:
            if workspace is None:
                raise NotFoundError(_NOT_FOUND)
            return workspace.id, True

        membership = await self.memberships.get_membership(workspace_id, user.id)
        if workspace is None or membership is None:
            raise NotFoundError(_NOT_FOUND)
        can_edit = membership.role == WorkspaceMembershipRole.OWNER
        return workspace.id, can_edit

    async def get(
        self,
        user: User,
        x_workspace_id: str | None,
    ) -> WorkspaceSettingsRead:
        workspace_id, can_edit = await self.resolve_workspace(user, x_workspace_id)
        row = await self.settings_rows.get_by_workspace_id(workspace_id)
        return self._to_read(workspace_id, can_edit, row)

    async def patch(
        self,
        user: User,
        x_workspace_id: str | None,
        payload: WorkspaceSettingsPatch,
    ) -> WorkspaceSettingsRead:
        workspace_id, can_edit = await self.resolve_workspace(user, x_workspace_id)
        if not can_edit:
            raise ForbiddenError()
        values = payload.model_dump(exclude_unset=True)
        if "default_telegram_channel_id" in values:
            channel_id = values["default_telegram_channel_id"]
            if channel_id is not None:
                channel = await self.channels.get_by_id_in_workspace(
                    channel_id,
                    workspace_id,
                )
                if channel is None:
                    raise ValidationError("Telegram channel not found")
        for key, value in list(values.items()):
            if hasattr(value, "value"):
                values[key] = value.value

        row = await self.settings_rows.get_by_workspace_id(workspace_id)
        if row is None:
            row = await self._create_with_defaults(workspace_id, values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row = await self.settings_rows.update(row)
        return self._to_read(workspace_id, True, row)

    async def _create_with_defaults(
        self,
        workspace_id: UUID,
        values: dict,
    ) -> WorkspaceSettings:
        env = get_settings()
        row = WorkspaceSettings(
            workspace_id=workspace_id,
            timezone=values.get("timezone", "UTC"),
            ui_language=values.get("ui_language", "ar"),
            aliexpress_target_currency=values.get(
                "aliexpress_target_currency",
                env.aliexpress_target_currency,
            ),
            aliexpress_ship_to_country=values.get(
                "aliexpress_ship_to_country",
                env.aliexpress_country,
            ),
            aliexpress_target_language=values.get(
                "aliexpress_target_language",
                env.aliexpress_target_language,
            ),
            default_ai_provider=values.get(
                "default_ai_provider",
                env.ai_default_provider.value,
            ),
            default_content_type=values.get("default_content_type", "telegram"),
            default_tone=values.get("default_tone", "persuasive"),
            default_content_language=values.get("default_content_language", "ar"),
            default_content_length=values.get("default_content_length", "medium"),
            discovery_default_mode=values.get("discovery_default_mode", "general"),
            discovery_page_size=values.get("discovery_page_size", 20),
            default_telegram_channel_id=values.get("default_telegram_channel_id"),
        )
        return await self.settings_rows.create(row)

    def _to_read(
        self,
        workspace_id: UUID,
        can_edit: bool,
        row: WorkspaceSettings | None,
    ) -> WorkspaceSettingsRead:
        env = get_settings()
        if row is None:
            return WorkspaceSettingsRead(
                workspace_id=workspace_id,
                can_edit=can_edit,
                timezone="UTC",
                ui_language="ar",
                aliexpress_target_currency=env.aliexpress_target_currency,
                aliexpress_ship_to_country=env.aliexpress_country,
                aliexpress_target_language=env.aliexpress_target_language,
                default_ai_provider=env.ai_default_provider,
                default_content_type="telegram",
                default_tone="persuasive",
                default_content_language="ar",
                default_content_length="medium",
                discovery_default_mode=WorkspaceDiscoveryMode.GENERAL,
                discovery_page_size=20,
                default_telegram_channel_id=None,
                connections=connection_status(env),
            )
        return WorkspaceSettingsRead(
            workspace_id=row.workspace_id,
            can_edit=can_edit,
            timezone=row.timezone,
            ui_language=row.ui_language,  # type: ignore[arg-type]
            aliexpress_target_currency=row.aliexpress_target_currency,
            aliexpress_ship_to_country=row.aliexpress_ship_to_country,
            aliexpress_target_language=row.aliexpress_target_language,
            default_ai_provider=row.default_ai_provider,  # type: ignore[arg-type]
            default_content_type=row.default_content_type,  # type: ignore[arg-type]
            default_tone=row.default_tone,  # type: ignore[arg-type]
            default_content_language=row.default_content_language,  # type: ignore[arg-type]
            default_content_length=row.default_content_length,  # type: ignore[arg-type]
            discovery_default_mode=row.discovery_default_mode,  # type: ignore[arg-type]
            discovery_page_size=row.discovery_page_size,
            default_telegram_channel_id=row.default_telegram_channel_id,
            connections=connection_status(env),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
