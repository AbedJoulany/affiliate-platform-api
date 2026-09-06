"""Tests for Phase A.2 SSE stream endpoint (Task B5).

HTTP ASGITransport buffers the full response body before returning, so infinite
SSE streams cannot be consumed via ``client.stream``. Lifecycle and framing are
covered by exercising ``_event_stream`` / ``StreamingResponse`` directly; HTTP
covers auth rejection only.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from starlette.responses import StreamingResponse

from app.api.v1.queue_stream import (
    SSE_HEARTBEAT_FRAME,
    _event_stream,
    format_sse_event,
    stream_queue_events,
)
from app.events.broadcaster import EventBroadcaster
from app.events.schemas import QUEUE_STATUS_CHANGED, QueueEventEnvelope

API_PREFIX = "/api/v1"
QUEUE_ID = UUID("6f9c2e34-2b1a-4b2e-9f0a-1234567890ab")
STREAM_WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_WORKSPACE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OCCURRED_AT = datetime(2026, 8, 7, 9, 40, 12, 483000, tzinfo=UTC)


class FakeRequest:
    def __init__(self, *, disconnected: bool = False) -> None:
        self._disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self._disconnected

    def disconnect(self) -> None:
        self._disconnected = True


def _sample_envelope(
    *,
    event_id: str = "01J9Z8H5F9T4S1R7D8P2K3M4N5",
    workspace_id: UUID | None = STREAM_WORKSPACE_ID,
) -> QueueEventEnvelope:
    return QueueEventEnvelope(
        event=QUEUE_STATUS_CHANGED,
        version=1,
        id=event_id,
        occurred_at=OCCURRED_AT,
        workspace_id=str(workspace_id) if workspace_id is not None else None,
        queue_id=QUEUE_ID,
        data={
            "queue_id": str(QUEUE_ID),
            "status": "published",
            "previous_status": "publishing",
            "scheduled_at": None,
            "published_at": OCCURRED_AT.isoformat(),
        },
    )


@pytest.fixture
def broadcaster() -> EventBroadcaster:
    return EventBroadcaster()


def test_format_sse_event_contains_event_id_and_full_envelope():
    envelope = _sample_envelope()
    frame = format_sse_event(envelope)

    assert f"event: {QUEUE_STATUS_CHANGED}\n" in frame
    assert f"id: {envelope.id}\n" in frame
    assert frame.endswith("\n\n")

    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload == json.loads(envelope.model_dump_json())
    assert payload["event"] == QUEUE_STATUS_CHANGED
    assert payload["id"] == envelope.id
    assert payload["queue_id"] == str(QUEUE_ID)
    assert "data" in payload


@pytest.mark.asyncio
async def test_endpoint_returns_sse_headers(broadcaster):
    response = await stream_queue_events(
        FakeRequest(),  # type: ignore[arg-type]
        STREAM_WORKSPACE_ID,
        broadcaster,
        0.05,
    )
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["connection"] == "keep-alive"
    assert response.headers["x-accel-buffering"] == "no"

    frame = await asyncio.wait_for(response.body_iterator.__anext__(), timeout=1.0)
    assert frame == SSE_HEARTBEAT_FRAME
    await response.body_iterator.aclose()
    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_stream_registers_and_delivers_full_envelope(broadcaster):
    request = FakeRequest()
    envelope = _sample_envelope()
    gen = _event_stream(
        request,
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=0.2,
    )

    assert broadcaster._subscribers == {}
    next_item = asyncio.create_task(gen.__anext__())
    for _ in range(50):
        if broadcaster._subscribers:
            break
        await asyncio.sleep(0.01)
    assert len(broadcaster._subscribers) == 1

    await broadcaster.publish(envelope)
    frame = await asyncio.wait_for(next_item, timeout=1.0)
    assert f"event: {envelope.event}" in frame
    assert f"id: {envelope.id}" in frame
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == json.loads(
        envelope.model_dump_json()
    )

    await gen.aclose()
    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_stream_emits_heartbeat(broadcaster):
    request = FakeRequest()
    gen = _event_stream(
        request,
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=0.05,
    )
    frame = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert frame == SSE_HEARTBEAT_FRAME
    await gen.aclose()
    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_multiple_stream_subscribers_receive_independently(broadcaster):
    envelope = _sample_envelope(event_id="01J9Z8H5F9T4S1R7D8P2K3M4N6")
    gen_a = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=1.0,
    )
    gen_b = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=1.0,
    )

    task_a = asyncio.create_task(gen_a.__anext__())
    task_b = asyncio.create_task(gen_b.__anext__())
    for _ in range(50):
        if len(broadcaster._subscribers) >= 2:
            break
        await asyncio.sleep(0.01)
    assert len(broadcaster._subscribers) == 2

    await broadcaster.publish(envelope)
    frame_a, frame_b = await asyncio.wait_for(
        asyncio.gather(task_a, task_b),
        timeout=1.0,
    )
    assert f"id: {envelope.id}" in frame_a
    assert f"id: {envelope.id}" in frame_b

    await gen_a.aclose()
    await gen_b.aclose()
    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_cancelled_stream_unsubscribes(broadcaster):
    gen = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=60.0,
    )
    anext_task = asyncio.create_task(gen.__anext__())
    for _ in range(50):
        if broadcaster._subscribers:
            break
        await asyncio.sleep(0.01)
    assert len(broadcaster._subscribers) == 1

    anext_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await anext_task

    await gen.aclose()
    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_disconnect_flag_unsubscribes(broadcaster):
    request = FakeRequest()
    gen = _event_stream(
        request,
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=0.05,
    )
    first = asyncio.create_task(gen.__anext__())
    for _ in range(50):
        if broadcaster._subscribers:
            break
        await asyncio.sleep(0.01)
    assert len(broadcaster._subscribers) == 1

    request.disconnect()
    try:
        await asyncio.wait_for(first, timeout=1.0)
    except StopAsyncIteration:
        pass
    with pytest.raises(StopAsyncIteration):
        while True:
            await asyncio.wait_for(gen.__anext__(), timeout=1.0)

    assert broadcaster._subscribers == {}


@pytest.mark.asyncio
async def test_sse_requires_authentication(client):
    response = await client.get(f"{API_PREFIX}/queues/stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_filters_events_to_active_workspace(broadcaster):
    own = _sample_envelope(event_id="01J9Z8H5F9T4S1R7D8P2K3M4N7")
    other = _sample_envelope(
        event_id="01J9Z8H5F9T4S1R7D8P2K3M4N8",
        workspace_id=OTHER_WORKSPACE_ID,
    )
    gen = _event_stream(
        FakeRequest(),
        broadcaster,
        workspace_id=STREAM_WORKSPACE_ID,
        heartbeat_interval_seconds=1.0,
    )
    next_item = asyncio.create_task(gen.__anext__())
    for _ in range(50):
        if broadcaster._subscribers:
            break
        await asyncio.sleep(0.01)

    await broadcaster.publish(other)
    await broadcaster.publish(own)
    frame = await asyncio.wait_for(next_item, timeout=1.0)
    assert f"id: {own.id}" in frame
    assert other.id not in frame
    await gen.aclose()

