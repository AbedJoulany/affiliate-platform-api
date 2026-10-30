from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import FacebookPageValidationStatus, UserRole, WorkspaceMembershipRole
from app.facebook.client import FacebookGraphClient, FacebookGraphError
from app.facebook.crypto import FacebookTokenCipher, FacebookTokenEncryptionError
from app.models.facebook_page import FacebookPage
from app.models.user import User
from app.repositories.facebook_page import FacebookPageRepository
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from app.schemas.facebook import (
    FacebookPageCreate,
    FacebookPageListResponse,
    FacebookPageRead,
    FacebookPageUpdate,
)
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError, ServiceError
from app.services.workspace_settings import _parse_workspace_header


class FacebookPageService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        graph_client: FacebookGraphClient | None = None,
        cipher: FacebookTokenCipher | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.pages = FacebookPageRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.memberships = WorkspaceMembershipRepository(session)
        self.graph = graph_client or FacebookGraphClient(self.settings)
        self.cipher = cipher

    async def resolve_workspace(
        self, user: User, raw_workspace_id: str | None
    ) -> tuple[UUID, bool]:
        workspace_id = _parse_workspace_header(raw_workspace_id)
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found")
        if user.role == UserRole.ADMIN:
            return workspace_id, True
        membership = await self.memberships.get_membership(workspace_id, user.id)
        if membership is None:
            raise NotFoundError("Workspace not found")
        return workspace_id, membership.role == WorkspaceMembershipRole.OWNER

    async def list(self, user: User, raw_workspace_id: str | None) -> FacebookPageListResponse:
        workspace_id, _ = await self.resolve_workspace(user, raw_workspace_id)
        items = await self.pages.list_in_workspace(workspace_id)
        return FacebookPageListResponse(
            items=[self._to_read(item) for item in items],
            total=len(items),
            skip=0,
            limit=len(items),
        )

    async def create(
        self, user: User, raw_workspace_id: str | None, payload: FacebookPageCreate
    ) -> FacebookPage:
        workspace_id, can_edit = await self.resolve_workspace(user, raw_workspace_id)
        self._require_edit(can_edit)
        cipher = self._get_cipher()
        if await self.pages.get_by_facebook_page_id(payload.facebook_page_id, workspace_id):
            raise ConflictError("Facebook Page already registered in this workspace")
        try:
            identity = await self._validate_token(payload.facebook_page_id, payload.access_token)
        except FacebookGraphError as exc:
            raise ServiceError(exc.message, exc.status_code) from exc
        page = FacebookPage(
            workspace_id=workspace_id,
            facebook_page_id=identity.page_id,
            page_name=identity.name,
            encrypted_access_token=cipher.encrypt(payload.access_token),
            token_expires_at=payload.token_expires_at,
            is_active=True,
            validation_status=FacebookPageValidationStatus.VALID,
            last_validated_at=datetime.now(UTC),
        )
        self.session.add(page)
        await self.session.flush()
        await self.session.refresh(page)
        return page

    async def validate(
        self, user: User, raw_workspace_id: str | None, page_id: UUID
    ) -> FacebookPage:
        workspace_id, _ = await self.resolve_workspace(user, raw_workspace_id)
        page = await self._get_or_404(page_id, workspace_id)
        try:
            cipher = self._get_cipher()
            token = cipher.decrypt(page.encrypted_access_token)
            identity = await self._validate_token(page.facebook_page_id, token)
        except FacebookTokenEncryptionError as exc:
            page.validation_status = FacebookPageValidationStatus.INVALID
            page.last_validated_at = datetime.now(UTC)
            page.last_error = "Stored Facebook credential is unavailable"
            await self.pages.update(page)
            raise ServiceError("Facebook credential configuration is unavailable", 503) from exc
        except FacebookGraphError as exc:
            page.validation_status = FacebookPageValidationStatus.INVALID
            page.last_validated_at = datetime.now(UTC)
            page.last_error = exc.message[:512]
            return await self.pages.update(page)
        page.page_name = identity.name
        page.validation_status = FacebookPageValidationStatus.VALID
        page.last_validated_at = datetime.now(UTC)
        page.last_error = None
        return await self.pages.update(page)

    async def update(
        self,
        user: User,
        raw_workspace_id: str | None,
        page_id: UUID,
        payload: FacebookPageUpdate,
    ) -> FacebookPage:
        workspace_id, can_edit = await self.resolve_workspace(user, raw_workspace_id)
        self._require_edit(can_edit)
        page = await self._get_or_404(page_id, workspace_id)
        values = payload.model_dump(exclude_unset=True)
        if "access_token" in values and values["access_token"] is not None:
            cipher = self._get_cipher()
            try:
                identity = await self._validate_token(page.facebook_page_id, values["access_token"])
            except FacebookGraphError as exc:
                raise ServiceError(exc.message, exc.status_code) from exc
            page.encrypted_access_token = cipher.encrypt(values["access_token"])
            page.page_name = identity.name
            page.validation_status = FacebookPageValidationStatus.VALID
            page.last_validated_at = datetime.now(UTC)
            page.last_error = None
        if "token_expires_at" in values:
            page.token_expires_at = values["token_expires_at"]
        if "is_active" in values and values["is_active"] is not None:
            page.is_active = values["is_active"]
        return await self.pages.update(page)

    async def delete(self, user: User, raw_workspace_id: str | None, page_id: UUID) -> None:
        workspace_id, can_edit = await self.resolve_workspace(user, raw_workspace_id)
        self._require_edit(can_edit)
        page = await self._get_or_404(page_id, workspace_id)
        await self.pages.delete(page)

    async def _validate_token(self, page_id: str, token: str):
        try:
            return await self.graph.validate_page(page_id, token)
        except FacebookGraphError:
            raise

    def _get_cipher(self) -> FacebookTokenCipher:
        if self.cipher is not None:
            return self.cipher
        try:
            return FacebookTokenCipher(self.settings.facebook_token_encryption_key)
        except FacebookTokenEncryptionError as exc:
            raise ServiceError("Facebook credential configuration is unavailable", 503) from exc

    async def _get_or_404(self, page_id: UUID, workspace_id: UUID) -> FacebookPage:
        page = await self.pages.get_in_workspace(page_id, workspace_id)
        if page is None:
            raise NotFoundError("Facebook Page not found")
        return page

    @staticmethod
    def _require_edit(can_edit: bool) -> None:
        if not can_edit:
            raise ForbiddenError()

    @staticmethod
    def _to_read(page: FacebookPage) -> FacebookPageRead:
        return FacebookPageRead(
            id=page.id,
            workspace_id=page.workspace_id,
            facebook_page_id=page.facebook_page_id,
            page_name=page.page_name,
            token_expires_at=page.token_expires_at,
            is_active=page.is_active,
            validation_status=page.validation_status,
            last_validated_at=page.last_validated_at,
            last_error=page.last_error,
            has_access_token=True,
            created_at=page.created_at,
            updated_at=page.updated_at,
        )
