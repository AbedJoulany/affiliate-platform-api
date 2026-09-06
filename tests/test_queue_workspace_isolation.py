"""Phase E Task 6 — queue workspace isolation and queue/channel pairing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.api.deps import get_http_workspace_id
from app.api.v1.queue_stream import _event_stream
from app.auth.security import decode_access_token
from app.core.enums import ProductStatus, QueueStatus, WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.events.broadcaster import EventBroadcaster
from app.events.schemas import QUEUE_STATUS_CHANGED, QueueEventEnvelope
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.queue import QueueRepository
from tests.conftest import SessionLocal
from tests.factories.queue_publishing import create_attempt, create_publishable_queue_item
from tests.test_api_endpoints import API_PREFIX, auth_headers, register_and_login
from tests.test_sse_endpoint import FakeRequest

QUEUES = f"{API_PREFIX}/queues"
CHANNELS = f"{API_PREFIX}/channels"
DASHBOARD = f"{API_PREFIX}/dashboard"
STREAM = f"{API_PREFIX}/queues/stream"


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


async def _user_id_from_token(token: str) -> UUID:
    return UUID(decode_access_token(token)["sub"])


async def _create_workspace_for_user(token: str, *, name: str) -> str:
    owner_id = await _user_id_from_token(token)
    async with SessionLocal() as session:
        workspace = Workspace(name=name, created_by_user_id=owner_id)
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=owner_id,
                role=WorkspaceMembershipRole.OWNER,
            )
        )
        await session.commit()
        await session.refresh(workspace)
        return str(workspace.id)


async def _create_channel(client, token: str, workspace_id: str, suffix: str | None = None) -> dict:
    tag = suffix or uuid4().hex[:10]
    response = await client.post(
        CHANNELS,
        headers=_headers(token, workspace_id),
        json={"telegram_channel_id": f"@qchannel{tag}", "title": f"Queue channel {tag}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_queue(
    client,
    token: str,
    workspace_id: str,
    **payload,
) -> dict:
    body = {"content": payload.pop("content", "Queue content")}
    body.update(payload)
    response = await client.post(
        QUEUES,
        headers=_headers(token, workspace_id),
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_unauthenticated_queue_request_is_401(client):
    response = await client.get(QUEUES)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="user")
    response = await client.get(QUEUES, headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_malformed_and_unknown_workspace_are_rejected(client):
    _, token = await register_and_login(client, role="user")
    malformed = await client.get(QUEUES, headers=_headers(token, "not-a-uuid"))
    unknown = await client.get(QUEUES, headers=_headers(token, str(uuid4())))
    assert malformed.status_code == 403
    assert unknown.status_code == 403


@pytest.mark.asyncio
async def test_non_member_workspace_is_rejected(client):
    _, owner_token = await register_and_login(client, role="user")
    _, stranger_token = await register_and_login(client, role="user")
    workspace_id = await _create_workspace_for_user(owner_token, name="Private queues")
    response = await client.get(QUEUES, headers=_headers(stranger_token, workspace_id))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_and_get_are_workspace_scoped(client):
    _, token = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token, name="Queue A")
    workspace_b = await _create_workspace_for_user(token, name="Queue B")
    item_a = await _create_queue(client, token, workspace_a, content="A item")
    item_b = await _create_queue(client, token, workspace_b, content="B item")

    listed_a = await client.get(QUEUES, headers=_headers(token, workspace_a))
    listed_b = await client.get(QUEUES, headers=_headers(token, workspace_b))
    ids_a = {item["id"] for item in listed_a.json()["items"]}
    ids_b = {item["id"] for item in listed_b.json()["items"]}
    assert item_a["id"] in ids_a
    assert item_b["id"] not in ids_a
    assert item_b["id"] in ids_b
    assert item_a["id"] not in ids_b

    own = await client.get(f"{QUEUES}/{item_a['id']}", headers=_headers(token, workspace_a))
    other = await client.get(f"{QUEUES}/{item_a['id']}", headers=_headers(token, workspace_b))
    assert own.status_code == 200
    assert other.status_code == 404
    assert other.json() == {"detail": "Queue item not found"}


@pytest.mark.asyncio
async def test_cross_workspace_patch_delete_and_publish_are_404(client):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token_a, name="Patch A")
    workspace_b = await _create_workspace_for_user(token_b, name="Patch B")
    item = await _create_queue(client, token_a, workspace_a)

    patched = await client.patch(
        f"{QUEUES}/{item['id']}",
        headers=_headers(token_b, workspace_b),
        json={"title": "Hijack"},
    )
    published = await client.post(
        f"{QUEUES}/{item['id']}/publish",
        headers=_headers(token_b, workspace_b),
    )
    deleted = await client.delete(
        f"{QUEUES}/{item['id']}",
        headers=_headers(token_b, workspace_b),
    )
    assert patched.status_code == 404
    assert published.status_code == 404
    assert deleted.status_code == 404
    assert patched.json() == {"detail": "Queue item not found"}


@pytest.mark.asyncio
async def test_create_assigns_workspace_from_header_not_body(client):
    _, token = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token, name="Create A")
    workspace_b = await _create_workspace_for_user(token, name="Create B")

    created = await client.post(
        QUEUES,
        headers=_headers(token, workspace_a),
        json={"content": "Owned by header", "workspace_id": workspace_b},
    )
    assert created.status_code == 201
    queue_id = UUID(created.json()["id"])

    async with SessionLocal() as session:
        item = await session.get(QueueItem, queue_id)
        assert item is not None
        assert str(item.workspace_id) == workspace_a

    leaked = await client.get(
        f"{QUEUES}/{created.json()['id']}",
        headers=_headers(token, workspace_b),
    )
    assert leaked.status_code == 404


@pytest.mark.asyncio
async def test_queue_without_channel_remains_valid(client):
    _, token = await register_and_login(client, role="user")
    workspace_id = await _create_workspace_for_user(token, name="No channel")
    created = await _create_queue(client, token, workspace_id, content="Draft only")
    assert created["channel_id"] is None


@pytest.mark.asyncio
async def test_queue_channel_attachment_must_share_workspace(
    client,
    mock_telegram_permissions,
):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token_a, name="Pair A")
    workspace_b = await _create_workspace_for_user(token_b, name="Pair B")
    channel_a = await _create_channel(client, token_a, workspace_a, suffix="pa")
    channel_b = await _create_channel(client, token_b, workspace_b, suffix="pb")

    ok_a = await client.post(
        QUEUES,
        headers=_headers(token_a, workspace_a),
        json={"content": "A with A", "channel_id": channel_a["id"]},
    )
    ok_b = await client.post(
        QUEUES,
        headers=_headers(token_b, workspace_b),
        json={"content": "B with B", "channel_id": channel_b["id"]},
    )
    assert ok_a.status_code == 201
    assert ok_b.status_code == 201

    cross_create = await client.post(
        QUEUES,
        headers=_headers(token_a, workspace_a),
        json={"content": "A with B", "channel_id": channel_b["id"]},
    )
    assert cross_create.status_code == 404
    assert cross_create.json() == {"detail": "Channel not found"}

    reverse_create = await client.post(
        QUEUES,
        headers=_headers(token_b, workspace_b),
        json={"content": "B with A", "channel_id": channel_a["id"]},
    )
    assert reverse_create.status_code == 404

    patched = await client.patch(
        f"{QUEUES}/{ok_a.json()['id']}",
        headers=_headers(token_a, workspace_a),
        json={"channel_id": channel_b["id"]},
    )
    assert patched.status_code == 404
    assert patched.json() == {"detail": "Channel not found"}

    reverse_patch = await client.patch(
        f"{QUEUES}/{ok_b.json()['id']}",
        headers=_headers(token_b, workspace_b),
        json={"channel_id": channel_a["id"]},
    )
    assert reverse_patch.status_code == 404

    publish_cross = await client.post(
        f"{QUEUES}/{ok_a.json()['id']}/publish",
        headers=_headers(token_b, workspace_b),
    )
    assert publish_cross.status_code == 404


@pytest.mark.asyncio
async def test_publish_attempts_require_parent_queue_authorization(client, session):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token_a, name="Attempts A")
    workspace_b = await _create_workspace_for_user(token_b, name="Attempts B")
    item = await create_publishable_queue_item(
        session,
        content="Attempt isolation",
        workspace_id=UUID(workspace_a),
    )
    await create_attempt(session, item.id, attempt_number=1, status="failed")
    await session.commit()

    own = await client.get(
        f"{QUEUES}/{item.id}/attempts",
        headers=_headers(token_a, workspace_a),
    )
    hidden = await client.get(
        f"{QUEUES}/{item.id}/attempts",
        headers=_headers(token_b, workspace_b),
    )
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Queue item not found"}


@pytest.mark.asyncio
async def test_admin_can_operate_without_membership_but_stays_scoped(client):
    _, owner_token = await register_and_login(client, role="user")
    _, other_token = await register_and_login(client, role="user")
    _, admin_token = await register_and_login(client, role="admin")
    workspace_a = await _create_workspace_for_user(owner_token, name="Admin queues")
    workspace_b = await _create_workspace_for_user(other_token, name="Other queues")
    item_a = await _create_queue(client, owner_token, workspace_a, content="Admin visible")
    item_b = await _create_queue(client, other_token, workspace_b, content="Hidden from admin A")

    missing = await client.get(QUEUES, headers=auth_headers(admin_token))
    assert missing.status_code == 403

    listed = await client.get(QUEUES, headers=_headers(admin_token, workspace_a))
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert item_a["id"] in ids
    assert item_b["id"] not in ids

    leaked = await client.get(
        f"{QUEUES}/{item_b['id']}",
        headers=_headers(admin_token, workspace_a),
    )
    assert leaked.status_code == 404


@pytest.mark.asyncio
async def test_worker_scans_remain_global(session):
    workspace_a = Workspace(name="Worker A")
    workspace_b = Workspace(name="Worker B")
    session.add_all([workspace_a, workspace_b])
    await session.flush()

    due = datetime.now(UTC) - timedelta(minutes=1)
    item_a = await create_publishable_queue_item(
        session,
        status=QueueStatus.SCHEDULED,
        workspace_id=workspace_a.id,
        content="Due A",
    )
    item_a.scheduled_at = due
    item_b = await create_publishable_queue_item(
        session,
        status=QueueStatus.SCHEDULED,
        workspace_id=workspace_b.id,
        content="Due B",
    )
    item_b.scheduled_at = due
    queued_a = await create_publishable_queue_item(
        session,
        status=QueueStatus.QUEUED,
        workspace_id=workspace_a.id,
        content="Queued A",
    )
    queued_b = await create_publishable_queue_item(
        session,
        status=QueueStatus.QUEUED,
        workspace_id=workspace_b.id,
        content="Queued B",
    )
    await session.flush()

    repo = QueueRepository(session)
    due_items = await repo.list_scheduled_due(due_before=datetime.now(UTC), limit=50)
    ready_items = await repo.list_queued_ready(limit=50)
    due_ids = {item.id for item in due_items}
    ready_ids = {item.id for item in ready_items}
    assert item_a.id in due_ids
    assert item_b.id in due_ids
    assert queued_a.id in ready_ids
    assert queued_b.id in ready_ids


@pytest.mark.asyncio
async def test_sse_workspace_auth_and_admin_resolution(client, session):
    _, member_token = await register_and_login(client, role="user")
    _, stranger_token = await register_and_login(client, role="user")
    _, admin_token = await register_and_login(client, role="admin")
    workspace_id = await _create_workspace_for_user(member_token, name="SSE workspace")

    unauthenticated = await client.get(STREAM)
    assert unauthenticated.status_code == 401

    missing = await client.get(STREAM, headers=auth_headers(member_token))
    assert missing.status_code == 403

    invalid = await client.get(STREAM, headers=_headers(member_token, "not-a-uuid"))
    assert invalid.status_code == 403

    unknown = await client.get(STREAM, headers=_headers(member_token, str(uuid4())))
    assert unknown.status_code == 403

    non_member = await client.get(STREAM, headers=_headers(stranger_token, workspace_id))
    assert non_member.status_code == 403

    admin_id = await _user_id_from_token(admin_token)
    admin = await session.get(User, admin_id)
    assert admin is not None
    resolved = await get_http_workspace_id(admin, session, workspace_id)
    assert str(resolved) == workspace_id


@pytest.mark.asyncio
async def test_sse_subscribers_are_isolated_by_workspace():
    workspace_a = uuid4()
    workspace_b = uuid4()
    occurred_at = datetime.now(UTC)
    event_a = QueueEventEnvelope(
        event=QUEUE_STATUS_CHANGED,
        version=1,
        id="01J9Z8H5F9T4S1R7D8P2K3M4AA",
        occurred_at=occurred_at,
        workspace_id=str(workspace_a),
        queue_id=uuid4(),
        data={"queue_id": "a", "status": "queued", "previous_status": "draft"},
    )
    event_b = QueueEventEnvelope(
        event=QUEUE_STATUS_CHANGED,
        version=1,
        id="01J9Z8H5F9T4S1R7D8P2K3M4BB",
        occurred_at=occurred_at,
        workspace_id=str(workspace_b),
        queue_id=uuid4(),
        data={"queue_id": "b", "status": "queued", "previous_status": "draft"},
    )
    broadcaster = EventBroadcaster()
    gen_a = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=workspace_a,
        heartbeat_interval_seconds=1.0,
    )
    gen_b = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=workspace_b,
        heartbeat_interval_seconds=1.0,
    )
    task_a = asyncio.create_task(gen_a.__anext__())
    task_b = asyncio.create_task(gen_b.__anext__())
    for _ in range(50):
        if len(broadcaster._subscribers) >= 2:
            break
        await asyncio.sleep(0.01)

    await broadcaster.publish(event_a)
    await broadcaster.publish(event_b)
    frame_a, frame_b = await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)
    assert event_a.id in frame_a
    assert event_b.id not in frame_a
    assert event_b.id in frame_b
    assert event_a.id not in frame_b
    await gen_a.aclose()
    await gen_b.aclose()


@pytest.mark.asyncio
async def test_dashboard_scopes_queue_and_channel_but_not_products(client, session):
    _, token = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token, name="Dash A")
    workspace_b = await _create_workspace_for_user(token, name="Dash B")

    session.add(
        Product(
            title="Global product",
            price=Decimal("10.00"),
            image_url="https://example.com/p.png",
            product_url="https://example.com/p",
            status=ProductStatus.ACTIVE,
        )
    )
    session.add_all(
        [
            TelegramChannel(
                telegram_channel_id="@dasha",
                title="A",
                is_active=True,
                workspace_id=UUID(workspace_a),
            ),
            TelegramChannel(
                telegram_channel_id="@dashb",
                title="B",
                is_active=True,
                workspace_id=UUID(workspace_b),
            ),
            QueueItem(
                title="A queue",
                content="a",
                status=QueueStatus.QUEUED,
                workspace_id=UUID(workspace_a),
            ),
            QueueItem(
                title="B queue",
                content="b",
                status=QueueStatus.DRAFT,
                workspace_id=UUID(workspace_b),
            ),
        ]
    )
    await session.commit()

    dash_a = await client.get(DASHBOARD, headers=_headers(token, workspace_a))
    dash_b = await client.get(DASHBOARD, headers=_headers(token, workspace_b))
    assert dash_a.status_code == 200
    assert dash_b.status_code == 200
    body_a = dash_a.json()
    body_b = dash_b.json()

    assert body_a["products"]["total"] == body_b["products"]["total"]
    assert body_a["products"]["total"] >= 1
    assert body_a["queue"]["total"] == 1
    assert body_a["queue"]["by_status"]["queued"] == 1
    assert body_b["queue"]["total"] == 1
    assert body_b["queue"]["by_status"]["draft"] == 1
    assert body_a["channels"]["total"] == 1
    assert body_b["channels"]["total"] == 1
    assert all(
        item["resource_type"] != "queue" or item["title"] == "A queue"
        for item in body_a["recent_activity"]
        if item["resource_type"] == "queue"
    )
