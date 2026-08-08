"""Phase B Task 3 — Flower observability configuration checks.

Flower is an external ops sidecar; these tests guard Compose/security wiring
and confirm Celery schedules remain unchanged.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.worker.celery_app import celery_app

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
REQUIREMENTS_PATH = ROOT / "requirements.txt"


def test_existing_beat_schedules_preserved():
    schedule = celery_app.conf.beat_schedule
    assert schedule["process-publish-queue"]["task"] == (
        "app.worker.tasks.publishing.process_publish_queue"
    )
    assert schedule["refresh-hot-products"]["task"] == (
        "app.worker.tasks.discovery.refresh_hot_products"
    )
    assert schedule["refresh-trending-products"]["task"] == (
        "app.worker.tasks.discovery.refresh_trending_products"
    )
    assert schedule["refresh-aliexpress-categories"]["task"] == (
        "app.worker.tasks.discovery.refresh_categories"
    )
    assert schedule["worker-heartbeat"]["task"] == (
        "app.worker.tasks.health.worker_heartbeat"
    )
    settings = get_settings()
    assert schedule["process-publish-queue"]["schedule"] == float(
        settings.celery_publish_interval_seconds
    )
    assert schedule["worker-heartbeat"]["schedule"] == float(
        settings.celery_heartbeat_interval_seconds
    )


def test_celery_emits_task_events_for_flower():
    assert celery_app.conf.worker_send_task_events is True
    assert celery_app.conf.task_send_sent_event is True


def test_flower_dependency_declared():
    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    assert "flower" in requirements
    assert "prometheus-client" not in requirements  # only as Flower transitive dep


def test_flower_compose_is_optional_and_localhost_bound():
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "flower:" in compose
    assert "profiles:" in compose
    assert "observability" in compose
    assert "127.0.0.1:5555:5555" in compose
    assert '"5555:5555"' not in compose
    assert "0.0.0.0:5555" not in compose
    assert "CELERY_BROKER_URL: redis://redis:6379/0" in compose
    assert "--basic-auth=" in compose
    assert "FLOWER_BASIC_AUTH" in compose


def test_flower_env_example_has_placeholder_not_real_secret():
    env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert "FLOWER_BASIC_AUTH=" in env_example
    assert "replace-with-a-local-flower-password" in env_example
    # No obvious hard-coded production-looking passwords in the placeholder line.
    auth_line = next(
        line for line in env_example.splitlines() if line.startswith("FLOWER_BASIC_AUTH=")
    )
    assert "replace-with" in auth_line
