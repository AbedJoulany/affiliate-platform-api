from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.schemas import TokenResponse, UserLogin, UserRegister
from app.auth.security import create_access_token, hash_password, verify_password
from app.services.exceptions import ConflictError, UnauthorizedError


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: UserRegister) -> User:

        print("PASSWORD LENGTH:", len(payload.password.encode("utf-8")))
        print("PASSWORD VALUE:", payload.password)

        if await self.users.get_by_email(payload.email):
            raise ConflictError("Email already registered")

        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
        )
        return await self.users.create(user)

    async def login(self, payload: UserLogin) -> TokenResponse:
        user = await self.users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("User account is inactive")

        return TokenResponse(access_token=create_access_token(user.id))

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await self.users.get_by_id(user_id)
