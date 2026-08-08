"""Tests for Phase B Task 1 — worker/Beat pipeline heartbeat."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.worker.celery_app import celery_app
from app.worker.tasks.health import (
    WORKER_HEARTBEAT_REDIS_KEY,
    worker_heartbeat,
    write_worker_heartbeat,
)


def test_write_worker_heartbeat_sets_key_value_and_ttl():
    redis_client = MagicMock()
    redis_client.set.return_value = True
    written_at = datetime(2026, 8, 8, 14, 30, 0, tzinfo=UTC)

    result = write_worker_heartbeat(redis_client=redis_client, written_at=written_at)

    redis_client.set.assert_called_once_with(
        WORKER_HEARTBEAT_REDIS_KEY,
        "2026-08-08T14:30:00+00:00",
        ex=get_settings().celery_heartbeat_ttl_seconds,
    )
    assert result == {
        "key": WORKER_HEARTBEAT_REDIS_KEY,
        "written_at": "2026-08-08T14:30:00+00:00",
        "ttl_seconds": get_settings().celery_heartbeat_ttl_seconds,
    }
    redis_client.close.assert_not_called()


def test_repeated_heartbeat_overwrites_value_and_refreshes_ttl():
    redis_client = MagicMock()
    redis_client.set.return_value = True
    first = datetime(2026, 8, 8, 14, 30, 0, tzinfo=UTC)
    second = datetime(2026, 8, 8, 14, 30, 30, tzinfo=UTC)

    write_worker_heartbeat(redis_client=redis_client, written_at=first)
    write_worker_heartbeat(redis_client=redis_client, written_at=second)

    assert redis_client.set.call_count == 2
    first_call = redis_client.set.call_args_list[0]
    second_call = redis_client.set.call_args_list[1]
    assert first_call.args[0] == WORKER_HEARTBEAT_REDIS_KEY
    assert second_call.args[0] == WORKER_HEARTBEAT_REDIS_KEY
    assert first_call.args[1] == "2026-08-08T14:30:00+00:00"
    assert second_call.args[1] == "2026-08-08T14:30:30+00:00"
    assert first_call.kwargs["ex"] == get_settings().celery_heartbeat_ttl_seconds
    assert second_call.kwargs["ex"] == get_settings().celery_heartbeat_ttl_seconds


def test_redis_write_failure_is_not_swallowed():
    redis_client = MagicMock()
    redis_client.set.return_value = False

    with pytest.raises(RuntimeError, match="Failed to write worker heartbeat"):
        write_worker_heartbeat(redis_client=redis_client)

    redis_client = MagicMock()
    redis_client.set.side_effect = ConnectionError("redis unavailable")

    with pytest.raises(ConnectionError, match="redis unavailable"):
        write_worker_heartbeat(redis_client=redis_client)


def test_celery_task_delegates_to_write_helper(monkeypatch):
    sentinel = {"key": WORKER_HEARTBEAT_REDIS_KEY, "written_at": "x", "ttl_seconds": 90}
    monkeypatch.setattr(
        "app.worker.tasks.health.write_worker_heartbeat",
        lambda: sentinel,
    )
    assert worker_heartbeat() == sentinel


def test_heartbeat_is_registered_in_beat_schedule():
    schedule = celery_app.conf.beat_schedule
    assert "worker-heartbeat" in schedule
    entry = schedule["worker-heartbeat"]
    assert entry["task"] == "app.worker.tasks.health.worker_heartbeat"
    assert entry["schedule"] == float(get_settings().celery_heartbeat_interval_seconds)

    # Existing business schedules must remain present and unchanged in name.
    assert "process-publish-queue" in schedule
    assert "refresh-hot-products" in schedule
    assert "refresh-trending-products" in schedule
    assert "refresh-aliexpress-categories" in schedule
