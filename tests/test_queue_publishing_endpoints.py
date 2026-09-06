"""MVP API coverage for attempt history, publish conflict, and attempt summary."""

from uuid import UUID, uuid4

import pytest

from app.core.workspace import WORKSPACE_ID_HEADER
from tests.conftest import provision_test_user
from tests.factories.queue_publishing import create_attempt, create_publishable_queue_item
from tests.test_api_endpoints import workspace_auth_headers

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


async def register_and_login(client, role: str = "user") -> tuple[str, str]:
    email = f"pub-{role}-{uuid4().hex[:6]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name=f"Test {role.title()}",
        role=role,
    )
    login_resp = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login_resp.status_code == 200
    return email, login_resp.json()["access_token"]


async def _create_channel_via_api(client, headers: dict[str, str]) -> dict:
    suffix = uuid4().hex[:8]
    response = await client.post(
        f"{API_PREFIX}/channels",
        headers=headers,
        json={"telegram_channel_id": f"@pub{suffix}", "title": f"Pub {suffix}"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_get_queue_attempts_returns_history_newest_first(client, session):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = UUID(headers[WORKSPACE_ID_HEADER])
    item = await create_publishable_queue_item(
        session,
        content="Attempt history",
        workspace_id=workspace_id,
    )
    await create_attempt(session, item.id, attempt_number=1, status="failed")
    await create_attempt(session, item.id, attempt_number=2, status="succeeded")
    await session.commit()

    response = await client.get(
        f"{API_PREFIX}/queues/{item.id}/attempts",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["queue_id"] == str(item.id)
    assert body["total"] == 2
    assert [row["attempt_number"] for row in body["items"]] == [2, 1]
    assert body["items"][0]["status"] == "succeeded"
    assert body["items"][1]["status"] == "failed"


@pytest.mark.asyncio
async def test_publish_conflict_returns_409(
    client,
    mock_telegram_permissions,
    mock_telegram_publisher_success,
):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    channel = await _create_channel_via_api(client, headers)

    create_resp = await client.post(
        f"{API_PREFIX}/queues",
        headers=headers,
        json={
            "content": "Conflict publish content",
            "status": "queued",
            "channel_id": channel["id"],
        },
    )
    assert create_resp.status_code == 201
    queue_id = create_resp.json()["id"]

    first = await client.post(
        f"{API_PREFIX}/queues/{queue_id}/publish",
        headers=headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"{API_PREFIX}/queues/{queue_id}/publish",
        headers=headers,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_queue_exposes_attempt_summary(
    client,
    mock_telegram_permissions,
    mock_telegram_publisher_failure,
):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    channel = await _create_channel_via_api(client, headers)

    create_resp = await client.post(
        f"{API_PREFIX}/queues",
        headers=headers,
        json={
            "content": "Summary after failure",
            "status": "queued",
            "channel_id": channel["id"],
        },
    )
    assert create_resp.status_code == 201
    queue_id = create_resp.json()["id"]

    publish_resp = await client.post(
        f"{API_PREFIX}/queues/{queue_id}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 502

    get_resp = await client.get(
        f"{API_PREFIX}/queues/{queue_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["last_attempt"] is not None
    assert body["last_attempt"]["status"] == "failed"
    assert body["failure_reason"] is not None
    assert body["retry_count"] == 1
