"""Trusted operator CLI to provision the first platform admin and workspace."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from dataclasses import dataclass
from enum import StrEnum

from pydantic import EmailStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.security import hash_password
from app.core.database import dispose_async_engine, get_async_session_maker
from app.core.enums import UserRole, WorkspaceMembershipRole
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository

PASSWORD_ENV = "BOOTSTRAP_ADMIN_PASSWORD"
DEFAULT_FULL_NAME = "Administrator"
_EMAIL_ADAPTER = TypeAdapter(EmailStr)


class BootstrapStatus(StrEnum):
    CREATED = "created"
    ALREADY_COMPLETE = "already_complete"
    COMPLETED_EXISTING_ADMIN = "completed_existing_admin"


class BootstrapError(Exception):
    """Abort bootstrap without mutating unrelated or inconsistent state."""


def _validated_admin_email(email: str) -> str:
    """Reject non-EmailStr values such as admin@localhost; do not special-case localhost."""
    try:
        return str(_EMAIL_ADAPTER.validate_python(email.strip()))
    except PydanticValidationError as exc:
        raise BootstrapError(
            "Admin email must be a valid email address with a dotted domain."
        ) from exc


@dataclass(frozen=True)
class BootstrapResult:
    status: BootstrapStatus
    user_id: str
    workspace_id: str


async def _memberships_for_user(
    session: AsyncSession,
    user_id,
) -> list[WorkspaceMembership]:
    result = await session.execute(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user_id)
    )
    return list(result.scalars().all())


async def _workspaces_created_by(
    session: AsyncSession,
    user_id,
) -> list[Workspace]:
    result = await session.execute(
        select(Workspace).where(Workspace.created_by_user_id == user_id)
    )
    return list(result.scalars().all())


async def _create_workspace_and_owner_membership(
    session: AsyncSession,
    *,
    user: User,
    workspace_name: str,
) -> Workspace:
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    workspace = await workspace_repo.create_workspace(
        Workspace(name=workspace_name, created_by_user_id=user.id),
    )
    await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.OWNER,
        ),
    )
    return workspace


async def bootstrap_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    workspace_name: str,
    full_name: str = DEFAULT_FULL_NAME,
) -> BootstrapResult:
    email = _validated_admin_email(email)
    workspace_name = workspace_name.strip()
    full_name = full_name.strip()
    if not workspace_name:
        raise BootstrapError("Workspace name is required.")
    if not full_name:
        raise BootstrapError("Admin full name is required.")
    if len(password) < 8:
        raise BootstrapError("Admin password must be at least 8 characters.")

    users = UserRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    existing = await users.get_by_email(email)

    if existing is None:
        user = await users.create(
            User(
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        workspace = await _create_workspace_and_owner_membership(
            session,
            user=user,
            workspace_name=workspace_name,
        )
        return BootstrapResult(
            status=BootstrapStatus.CREATED,
            user_id=str(user.id),
            workspace_id=str(workspace.id),
        )

    if existing.role != UserRole.ADMIN:
        raise BootstrapError(
            "A user with this email already exists and is not a platform admin."
        )

    memberships = await _memberships_for_user(session, existing.id)
    created_workspaces = await _workspaces_created_by(session, existing.id)

    if len(memberships) == 1 and memberships[0].role == WorkspaceMembershipRole.OWNER:
        workspace = created_workspaces[0] if len(created_workspaces) == 1 else None
        if (
            workspace is not None
            and memberships[0].workspace_id == workspace.id
            and workspace.created_by_user_id == existing.id
        ):
            return BootstrapResult(
                status=BootstrapStatus.ALREADY_COMPLETE,
                user_id=str(existing.id),
                workspace_id=str(workspace.id),
            )
        raise BootstrapError(
            "Bootstrap admin exists but workspace membership state is inconsistent."
        )

    if len(memberships) == 0 and len(created_workspaces) == 0:
        workspace = await _create_workspace_and_owner_membership(
            session,
            user=existing,
            workspace_name=workspace_name,
        )
        return BootstrapResult(
            status=BootstrapStatus.COMPLETED_EXISTING_ADMIN,
            user_id=str(existing.id),
            workspace_id=str(workspace.id),
        )

    if len(memberships) == 0 and len(created_workspaces) == 1:
        workspace = created_workspaces[0]
        await membership_repo.create_membership(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=existing.id,
                role=WorkspaceMembershipRole.OWNER,
            ),
        )
        return BootstrapResult(
            status=BootstrapStatus.COMPLETED_EXISTING_ADMIN,
            user_id=str(existing.id),
            workspace_id=str(workspace.id),
        )

    raise BootstrapError(
        "Bootstrap admin exists but workspace membership state is inconsistent."
    )


def _read_password() -> str:
    password = os.environ.get(PASSWORD_ENV, "")
    if password:
        return password
    if sys.stdin.isatty():
        return getpass.getpass("Bootstrap admin password: ")
    raise BootstrapError(
        f"Admin password is required via {PASSWORD_ENV} or an interactive prompt."
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Provision the initial platform admin, default workspace, and owner membership. "
            "Trusted operator/deployment action - not a public registration route."
        )
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Admin email (must be a valid EmailStr, e.g. admin@example.com).",
    )
    parser.add_argument(
        "--workspace-name",
        required=True,
        help="Name of the bootstrap workspace.",
    )
    parser.add_argument(
        "--full-name",
        default=DEFAULT_FULL_NAME,
        help=f"Admin display name (default: {DEFAULT_FULL_NAME}).",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    password = _read_password()
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            result = await bootstrap_admin(
                session,
                email=args.email,
                password=password,
                workspace_name=args.workspace_name,
                full_name=args.full_name,
            )
            await session.commit()
        except BootstrapError as exc:
            await session.rollback()
            print(str(exc), file=sys.stderr)
            return 1
        except Exception:
            await session.rollback()
            raise
        finally:
            await dispose_async_engine()

    if result.status == BootstrapStatus.ALREADY_COMPLETE:
        print("Bootstrap already complete.")
    elif result.status == BootstrapStatus.COMPLETED_EXISTING_ADMIN:
        print("Bootstrap completed existing admin with workspace owner membership.")
    else:
        print("Created admin user, workspace, and owner membership.")
    print(f"Admin email: {args.email}")
    print(f"Workspace: {args.workspace_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
