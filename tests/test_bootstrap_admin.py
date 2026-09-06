"""Workspace-aware admin bootstrap CLI (Phase E Task 2)."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.security import hash_password, verify_password
from app.core.enums import UserRole, WorkspaceMembershipRole
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from scripts.bootstrap_admin import BootstrapError, bootstrap_admin


def _email() -> str:
    return f"admin-{uuid4().hex}@example.com"


async def _creator_workspaces(session, user_id) -> list[Workspace]:
    result = await session.execute(
        select(Workspace).where(Workspace.created_by_user_id == user_id)
    )
    return list(result.scalars().all())


async def _membership_count(session, user_id) -> int:
    result = await session.execute(
        select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id
        )
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_first_run_creates_admin_workspace_and_owner_membership(session):
    email = _email()
    result = await bootstrap_admin(
        session,
        email=email,
        password="bootstrap-secret",
        workspace_name="Default Workspace",
        full_name="Staging Admin",
    )

    user = await UserRepository(session).get_by_email(email)
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.full_name == "Staging Admin"
    assert result.user_id == str(user.id)

    workspaces = await _creator_workspaces(session, user.id)
    assert len(workspaces) == 1
    workspace = workspaces[0]
    assert workspace.name == "Default Workspace"
    assert workspace.created_by_user_id == user.id
    assert result.workspace_id == str(workspace.id)

    membership = await WorkspaceMembershipRepository(session).get_membership(
        workspace.id,
        user.id,
    )
    assert membership is not None
    assert membership.role == WorkspaceMembershipRole.OWNER
    assert await _membership_count(session, user.id) == 1


@pytest.mark.asyncio
async def test_rerun_is_idempotent_and_does_not_overwrite_password(session):
    email = _email()
    first = await bootstrap_admin(
        session,
        email=email,
        password="first-password",
        workspace_name="Default Workspace",
    )
    original = await UserRepository(session).get_by_email(email)
    assert original is not None
    original_hash = original.hashed_password

    second = await bootstrap_admin(
        session,
        email=email,
        password="second-password",
        workspace_name="Another Name",
    )

    user = await UserRepository(session).get_by_email(email)
    assert user is not None
    assert user.id == original.id
    assert user.hashed_password == original_hash
    assert verify_password("first-password", user.hashed_password)
    assert not verify_password("second-password", user.hashed_password)
    assert first.workspace_id == second.workspace_id
    assert len(await _creator_workspaces(session, user.id)) == 1
    assert await _membership_count(session, user.id) == 1


@pytest.mark.asyncio
async def test_generated_password_matches_existing_verifier(session):
    email = _email()
    password = "compatible-pass"
    await bootstrap_admin(
        session,
        email=email,
        password=password,
        workspace_name="Default Workspace",
    )
    user = await UserRepository(session).get_by_email(email)
    assert user is not None
    assert verify_password(password, user.hashed_password)


@pytest.mark.asyncio
async def test_existing_non_admin_is_not_promoted(session):
    email = _email()
    session.add(
        User(
            email=email,
            hashed_password=hash_password("user-pass"),
            full_name="Existing User",
            role=UserRole.USER,
        )
    )
    await session.flush()

    with pytest.raises(BootstrapError, match="not a platform admin"):
        await bootstrap_admin(
            session,
            email=email,
            password="bootstrap-secret",
            workspace_name="Default Workspace",
        )

    user = await UserRepository(session).get_by_email(email)
    assert user is not None
    assert user.role == UserRole.USER
    assert await _creator_workspaces(session, user.id) == []
    assert await _membership_count(session, user.id) == 0


@pytest.mark.asyncio
async def test_failure_during_membership_creation_rolls_back(session, monkeypatch):
    email = _email()

    async def fail_create(self, membership):
        raise RuntimeError("forced membership failure")

    monkeypatch.setattr(WorkspaceMembershipRepository, "create_membership", fail_create)

    with pytest.raises(RuntimeError, match="forced membership failure"):
        await bootstrap_admin(
            session,
            email=email,
            password="bootstrap-secret",
            workspace_name="Default Workspace",
        )
    await session.rollback()

    assert await UserRepository(session).get_by_email(email) is None
    workspaces = await session.execute(
        select(Workspace).where(Workspace.name == "Default Workspace")
    )
    assert list(workspaces.scalars().all()) == []


@pytest.mark.asyncio
async def test_existing_complete_bootstrap_is_noop(session):
    email = _email()
    user = User(
        email=email,
        hashed_password=hash_password("keep-this-password"),
        full_name="Pre-seeded Admin",
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.flush()
    workspace = await WorkspaceRepository(session).create_workspace(
        Workspace(name="Existing Workspace", created_by_user_id=user.id),
    )
    await WorkspaceMembershipRepository(session).create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.OWNER,
        ),
    )

    result = await bootstrap_admin(
        session,
        email=email,
        password="should-not-apply",
        workspace_name="Ignored Name",
    )

    loaded = await UserRepository(session).get_by_email(email)
    assert loaded is not None
    assert loaded.role == UserRole.ADMIN
    assert verify_password("keep-this-password", loaded.hashed_password)
    assert not verify_password("should-not-apply", loaded.hashed_password)
    assert result.workspace_id == str(workspace.id)
    workspaces = await _creator_workspaces(session, user.id)
    assert len(workspaces) == 1
    assert workspaces[0].name == "Existing Workspace"
    assert await _membership_count(session, user.id) == 1


@pytest.mark.asyncio
async def test_bootstrap_rejects_non_emailstr_localhost(session):
    with pytest.raises(BootstrapError, match="valid email"):
        await bootstrap_admin(
            session,
            email="admin@localhost",
            password="bootstrap-secret",
            workspace_name="Default Workspace",
        )
    assert await UserRepository(session).get_by_email("admin@localhost") is None


@pytest.mark.asyncio
async def test_bootstrap_rejects_malformed_email(session):
    with pytest.raises(BootstrapError, match="valid email"):
        await bootstrap_admin(
            session,
            email="not-an-email",
            password="bootstrap-secret",
            workspace_name="Default Workspace",
        )
