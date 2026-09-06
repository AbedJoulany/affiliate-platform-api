from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.refresh_token_repository import RefreshTokenRepository
from app.auth.repository import UserRepository
from app.auth.schemas import TokenResponse, UserLogin, UserProfileUpdate, UserRegister
from app.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import get_settings
from app.core.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.services.exceptions import ConflictError, UnauthorizedError

_INVALID_REFRESH = "Invalid refresh token"


def _as_utc(value: datetime) -> datetime:
    """Normalize DB datetimes for comparison (SQLite may return naive UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, payload: UserRegister) -> User:
        if await self.users.get_by_email(payload.email):
            raise ConflictError("Email already registered")

        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=UserRole.USER,
        )
        return await self.users.create(user)

    async def login(self, payload: UserLogin) -> TokenResponse:
        user = await self.users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("User account is inactive")

        raw_refresh = await self._issue_refresh_token(user.id)
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=raw_refresh,
        )

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)
        now = datetime.now(UTC)
        record = await self.refresh_tokens.get_by_token_hash_for_update(token_hash)

        if record is None:
            raise UnauthorizedError(_INVALID_REFRESH)

        if record.revoked_at is not None or record.replaced_by_id is not None:
            await self._handle_reuse(record.user_id, now=now)
            raise UnauthorizedError(_INVALID_REFRESH)

        if _as_utc(record.expires_at) <= now:
            raise UnauthorizedError(_INVALID_REFRESH)

        user = await self.users.get_by_id(record.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError(_INVALID_REFRESH)

        # Atomic single-use consume: at most one concurrent rotator wins.
        consume = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.id == record.id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.replaced_by_id.is_(None),
            )
            .values(revoked_at=now)
        )
        if (consume.rowcount or 0) != 1:
            await self._handle_reuse(record.user_id, now=now)
            raise UnauthorizedError(_INVALID_REFRESH)

        new_raw = await self._issue_refresh_token(user.id, now=now)
        new_hash = hash_refresh_token(new_raw)
        replacement = await self.refresh_tokens.get_by_token_hash(new_hash)
        if replacement is None:
            raise UnauthorizedError(_INVALID_REFRESH)

        record.replaced_by_id = replacement.id
        await self.session.flush()

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=new_raw,
        )

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        record = await self.refresh_tokens.get_by_token_hash_for_update(token_hash)
        if record is None:
            return
        if record.revoked_at is None:
            record.revoked_at = datetime.now(UTC)
            await self.session.flush()

    async def _handle_reuse(self, user_id: UUID, *, now: datetime) -> None:
        """Revoke all active tokens and commit so the HTTP error path cannot roll it back."""
        await self.refresh_tokens.revoke_all_active_for_user(user_id, revoked_at=now)
        await self.session.commit()

    async def _issue_refresh_token(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> str:
        settings = get_settings()
        created_at = now or datetime.now(UTC)
        raw_token = generate_refresh_token()
        entity = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=created_at
            + timedelta(days=settings.refresh_token_expire_days),
        )
        await self.refresh_tokens.create(entity)
        return raw_token

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await self.users.get_by_id(user_id)

    async def update_profile(self, user: User, payload: UserProfileUpdate) -> User:
        data = payload.model_dump(exclude_unset=True)
        if "email" in data and data["email"] != user.email:
            existing = await self.users.get_by_email(data["email"])
            if existing is not None and existing.id != user.id:
                raise ConflictError("Email already registered")
            user.email = data["email"]
        if "full_name" in data:
            user.full_name = data["full_name"]
        await self.session.flush()
        await self.session.refresh(user)
        return user
