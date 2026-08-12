from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RefreshToken)

    async def get_by_token_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> list[RefreshToken]:
        current = now or datetime.now(UTC)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.replaced_by_id.is_(None),
                RefreshToken.expires_at > current,
            )
        )
        return list(result.scalars().all())

    async def revoke_all_active_for_user(
        self,
        user_id: UUID,
        *,
        revoked_at: datetime | None = None,
    ) -> int:
        current = revoked_at or datetime.now(UTC)
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.replaced_by_id.is_(None),
            )
            .values(revoked_at=current)
        )
        return result.rowcount or 0
