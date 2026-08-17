"""Foundational Workspace / WorkspaceMembership model and repository coverage."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.auth.security import hash_password
from app.core.enums import UserRole, WorkspaceMembershipRole
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository


async def _create_user(session, *, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("test-password"),
        full_name="Workspace Tester",
        role=UserRole.AFFILIATE,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _enable_sqlite_foreign_keys(session) -> None:
    await session.execute(text("PRAGMA foreign_keys=ON"))


@pytest.mark.asyncio
async def test_create_workspace_with_name_and_optional_creator(session):
    creator = await _create_user(session, email="creator@example.com")
    repo = WorkspaceRepository(session)

    with_creator = await repo.create_workspace(
        Workspace(name="Primary workspace", created_by_user_id=creator.id),
    )
    without_creator = await repo.create_workspace(Workspace(name="Orphan workspace"))

    assert with_creator.id is not None
    assert with_creator.name == "Primary workspace"
    assert with_creator.created_by_user_id == creator.id
    assert without_creator.created_by_user_id is None


@pytest.mark.asyncio
async def test_created_by_user_id_set_null_when_creator_deleted(session):
    await _enable_sqlite_foreign_keys(session)
    creator = await _create_user(session, email="creator-delete@example.com")
    repo = WorkspaceRepository(session)
    workspace = await repo.create_workspace(
        Workspace(name="Survives creator delete", created_by_user_id=creator.id),
    )

    await session.delete(creator)
    await session.flush()
    await session.refresh(workspace)

    assert workspace.created_by_user_id is None
    loaded = await repo.get_by_id(workspace.id)
    assert loaded is not None
    assert loaded.created_by_user_id is None


@pytest.mark.asyncio
async def test_create_membership_and_relationships(session):
    user = await _create_user(session, email="member@example.com")
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    workspace = await workspace_repo.create_workspace(Workspace(name="Team workspace"))

    membership = await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.OWNER,
        ),
    )

    await session.refresh(membership, attribute_names=["workspace", "user"])

    assert membership.workspace_id == workspace.id
    assert membership.user_id == user.id
    assert membership.role == WorkspaceMembershipRole.OWNER
    assert membership.workspace.id == workspace.id
    assert membership.user.id == user.id
    found = await membership_repo.get_membership(workspace.id, user.id)
    assert found is not None
    assert found.id == membership.id


@pytest.mark.asyncio
async def test_duplicate_membership_violates_unique_constraint(session):
    user = await _create_user(session, email="dup@example.com")
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    workspace = await workspace_repo.create_workspace(Workspace(name="Unique membership"))
    await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.OWNER,
        ),
    )

    with pytest.raises(IntegrityError):
        await membership_repo.create_membership(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceMembershipRole.MEMBER,
            ),
        )


@pytest.mark.asyncio
async def test_deleting_workspace_cascades_memberships(session):
    await _enable_sqlite_foreign_keys(session)
    user = await _create_user(session, email="cascade-workspace@example.com")
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    workspace = await workspace_repo.create_workspace(Workspace(name="To delete"))
    membership = await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.MEMBER,
        ),
    )
    membership_id = membership.id
    workspace_id = workspace.id

    await workspace_repo.delete(workspace)
    session.expire_all()

    remaining = await session.get(WorkspaceMembership, membership_id)
    assert remaining is None
    assert await workspace_repo.get_by_id(workspace_id) is None


@pytest.mark.asyncio
async def test_deleting_user_cascades_memberships(session):
    await _enable_sqlite_foreign_keys(session)
    user = await _create_user(session, email="cascade-user@example.com")
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    workspace = await workspace_repo.create_workspace(Workspace(name="Keeps existing"))
    membership = await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMembershipRole.MEMBER,
        ),
    )
    membership_id = membership.id
    workspace_id = workspace.id

    await session.delete(user)
    await session.flush()
    session.expire_all()

    remaining = await session.get(WorkspaceMembership, membership_id)
    assert remaining is None
    loaded_workspace = await workspace_repo.get_by_id(workspace_id)
    assert loaded_workspace is not None


@pytest.mark.asyncio
async def test_list_for_user_returns_only_membership_workspaces(session):
    owner = await _create_user(session, email="list-owner@example.com")
    other = await _create_user(session, email="list-other@example.com")
    workspace_repo = WorkspaceRepository(session)
    membership_repo = WorkspaceMembershipRepository(session)
    mine = await workspace_repo.create_workspace(Workspace(name="Mine"))
    await workspace_repo.create_workspace(Workspace(name="Not mine"))
    await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=mine.id,
            user_id=owner.id,
            role=WorkspaceMembershipRole.OWNER,
        ),
    )
    other_workspace = await workspace_repo.create_workspace(Workspace(name="Other"))
    await membership_repo.create_membership(
        WorkspaceMembership(
            workspace_id=other_workspace.id,
            user_id=other.id,
            role=WorkspaceMembershipRole.MEMBER,
        ),
    )

    listed = await workspace_repo.list_for_user(owner.id)

    assert [workspace.id for workspace in listed] == [mine.id]
