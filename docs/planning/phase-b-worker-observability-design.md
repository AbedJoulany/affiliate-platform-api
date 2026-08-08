# Phase B — Worker Health & Observability Design

**Status:** Adopted — Phase B Tasks 0–4 **COMPLETE** (2026-08-08). Historical Task 0 ADR retained; implementation follows this document with Task 2 response-shape finalization noted below.
**Author role:** Senior Staff Backend Architect / Technical Design Review
**Date:** 2026-08-08
**Depends on:** Phase A.1 (Publishing Reliability Foundation) — complete; Phase A.2 (Real-time Queue Updates, F1–F6) — complete
**Scope authority:** `docs/08-implementation-roadmap.md` §3 "Phase B — Background workers & queue execution (remainder)"

This document began as a documentation-only architectural decision record (Task 0). Phase B Tasks 1–4 have since shipped; treat the repository implementation as the runtime source of truth. Where Task 2 finalized field names differently from the illustrative §6 sketch, the **shipped** contract is authoritative: `{ "status": "healthy"|"degraded"|"unknown", "last_heartbeat_at": <ISO datetime>|null }` with no `control.ping()` / `worker_reachable` field on the endpoint.

---

## 1. Status

**COMPLETE (Tasks 0–4).** Task 0 decisions below remain the architectural rationale. Do not re-implement Tasks 1–3. A.1 and A.2 (including F1–F6) remain stable and must not be modified by Phase B follow-ups.

---

## 2. Scope

**In scope for this document:** four architectural decisions required before any Phase B code is written —

- **Decision A** — worker/Beat liveness detection mechanism
- **Decision B** — worker health API contract
- **Decision C** — Flower vs. Prometheus vs. deferred failure observability
- **Decision D** — whether Celery-level retry hardening for the discovery tasks belongs to Phase B or Phase C'

**Out of scope for this document (and for Phase B generally):** rebuilding or modifying `process_publish_queue`, `refresh_hot_products`, `refresh_trending_products`, `refresh_categories` (all four already exist, are already scheduled, and are already `COMPLETE`); any change to `TelegramPublishingService`, `QueuePublishAttempt`, the idempotency guard, or dead-letter marking (A.1, must not be duplicated); any change to `EventPublisher`, `EventConsumer`, `EventBroadcaster`, `QueueEventEnvelope`, the `queue-events` Redis channel, the SSE endpoint, or frontend realtime invalidation (A.2, must not be modified); any frontend work (§13); any database migration (§11).

---

## 3. Current Architecture (verified from source, not assumed from docs)

### Celery configuration — `app/worker/celery_app.py`

```python
celery_app = Celery(
    "affiliate_platform",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=["app.worker.tasks.publishing", "app.worker.tasks.discovery"],
)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="UTC", enable_utc=True, task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "process-publish-queue": {...},      # every settings.celery_publish_interval_seconds (default 60s)
        "refresh-hot-products": {...},       # every 6h
        "refresh-trending-products": {...},  # every 6h
        "refresh-aliexpress-categories": {...},  # every 24h
    },
)
```

- Single default queue — no queue routing exists today (confirmed: no `task_routes`/`task_queues` config; `docker-compose.yml`'s `celery-worker` service starts with a bare `celery ... worker --loglevel=info`, no `-Q` flag).
- `task_track_started=True` is already set (worker reports a `STARTED` state, not just `PENDING`/`SUCCESS`/`FAILURE` — relevant to §7 as a pre-existing primitive).
- Broker and result backend are both Redis (`settings.broker_url`, defaulting to `redis://{redis_host}:{redis_port}/{redis_db}`, i.e. **the same Redis instance A.2's `EventPublisher`/`EventConsumer` already use** — see §10).

### Worker task files

- `app/worker/tasks/publishing.py` — both Celery tasks (`process_publish_queue`, `publish_queue_item_task`) are decorated with `autoretry_for=(TelegramPublishError,), max_retries=3, retry_backoff=True, retry_jitter=True` (A.1 Task 5). Each task body constructs its own short-lived `redis.asyncio` client and an `EventPublisher` (A.2 reuse pattern), runs via `run_async(...)`.
- `app/worker/tasks/discovery.py` — all three tasks (`refresh_hot_products`, `refresh_trending_products`, `refresh_categories`) are plain `@celery_app.task(name=...)` with **no `autoretry_for`, no `max_retries`, no backoff**. Confirmed by direct read — this is a genuine, verified gap, not an assumption (relevant to Decision D, §9).
- `app/worker/async_utils.py` — `run_async()` wraps `asyncio.run(...)` and unconditionally calls `dispose_async_engine()` in a `finally` block after every coroutine (the A.1 hardening fix for the event-loop/connection-pool bug). Any new Celery task that touches the async SQLAlchemy engine must go through this same wrapper.

### Events (A.2) — `app/events/`

- `publisher.py` — `EventPublisher` wraps a Redis client's `PUBLISH` to one fixed channel (`DEFAULT_EVENT_STREAM_CHANNEL`, i.e. `queue-events`); `NullEventPublisher` no-op fallback.
- `consumer.py` — `EventConsumer` subscribes to `queue-events`, validates each message as a `QueueEventEnvelope`, forwards to `EventBroadcaster`. Runs as a background `asyncio.Task` started in `app/main.py`'s `lifespan()`.
- `broadcaster.py` — in-process fan-out only; no Redis/HTTP knowledge.
- `deps.py` — `get_event_broadcaster()` (process-wide singleton), `create_event_publisher()` (used identically by API deps and Celery tasks around a Redis client).
- `app/api/v1/queue_stream.py` — the SSE endpoint. It subscribes to the **in-process `EventBroadcaster` only**, never touches Redis directly. It has its own `SSE_HEARTBEAT_INTERVAL_SECONDS = 30.0` constant — **this is an SSE connection keep-alive comment (`: heartbeat\n\n`) sent to browser clients to defeat proxy idle timeouts. It has nothing to do with Celery worker/Beat liveness** and must not be confused with, or reused for, the mechanism proposed in §5. They are different concerns with different consumers (browser vs. ops).

### Health — `app/main.py`, `app/services/health.py`, `app/schemas/health.py`

- `GET /health` — registered directly on `app` (root, no `/api/v1` prefix): returns a static `{"status": "ok"}`. No dependency checks at all.
- `GET /ready` — also registered directly on `app` at root. Delegates to `ReadinessService.check()`, which runs `_check_database()` (SQL `SELECT 1`, 2s timeout) and `_check_redis()` (`PING`, 2s timeout) concurrently via `asyncio.gather`. Sets HTTP 503 when not ready (`app/main.py`: `if readiness.status == "not_ready": response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE`).
- `ReadinessResponse.checks` is typed **`dict[Literal["database", "redis"], DependencyStatus]`** in `app/schemas/health.py` — a closed, two-key literal type. This is a hard piece of evidence for Decision B (§6): silently adding a third key would not type-check against the existing Pydantic model as written.
- `06-api-integration.md` §7 already documents this boundary in prose: **"`/ready` checks PostgreSQL + Redis only — not Celery worker liveness or provider credentials."** This is a pre-existing, deliberate, documented scope line, not an oversight.
- Neither `/health` nor `/ready` requires authentication (`app/main.py` — no `Depends(CurrentUser)` on either route).

### Docker / dependencies / env

- `docker-compose.yml` defines exactly five services: `frontend`, `api`, `db`, `redis`, `celery-worker`, `celery-beat` (six, counting `frontend`). **No monitoring service of any kind exists** (no Flower, no Prometheus, no Grafana, no exporter).
- `requirements.txt` has no `flower`, `prometheus-client`, `prometheus_client`, or any metrics/observability package.
- `.env.example` already documents `CELERY_PUBLISH_INTERVAL_SECONDS`, `CELERY_PUBLISH_BATCH_SIZE`, and the three discovery-interval vars (`CELERY_DISCOVERY_*_INTERVAL_SECONDS`) — i.e., Phase B requirement #3 ("document Redis/Celery env") is **already substantially done**; only whatever new vars this design introduces remain undocumented until Task 4.
- Repository-wide search for `heartbeat`, `worker health`, `celery health`, `flower`, `prometheus`, `metrics`, `task_failure`, `task_success`, and Celery signal imports (`task_prerun`, `task_postrun`, `celery.signals`) returned **zero matches**. There is no existing health/heartbeat/metrics abstraction of any kind to reuse or conflict with — this design starts from a clean slate.

---

## 4. Architectural Goals

1. Detect when the scheduled-task pipeline (Beat + at least one worker) has stopped functioning, independently of `/ready`.
2. Give operators visibility into background-task *failures* specifically (not just liveness), using the least infrastructure necessary.
3. Do so with the smallest possible footprint: reuse existing Redis infrastructure, avoid new abstractions, avoid new dependencies unless a named roadmap requirement genuinely needs one — matching the same minimalism the A.2 design doc already established for this codebase ("smallest possible" event bus, no `ConnectionManager`, accepted trade-offs over speculative complexity).
4. Never let an observability signal be mistaken for more than it actually proves (§15 — no overclaiming).
5. Leave `/ready`, the A.2 event/SSE architecture, and A.1's publishing reliability model completely untouched.

---

## 5. Worker/Beat Health Strategy — **Decision A**

### Options compared

| Option | What it actually proves | What it does *not* prove | Redis dependency | Celery dependency | Complexity | Operational behavior |
| --- | --- | --- | --- | --- | --- | --- |
| **(1) Redis heartbeat key with TTL, written by a Beat-scheduled task executed by a worker** | The *entire pipeline* is functioning: Beat scheduled a task recently, a worker picked it up and ran it, and that worker could reach Redis to write the result. | Which specific half (Beat vs. worker) is broken if the key goes stale — see below. | Yes (already present; reuses the existing broker Redis instance) | Yes (a new, trivial task + one new `beat_schedule` entry) | Low | Passive: a health check is a cheap async `GET`; no network round-trip to Celery at request time. Self-healing — the very next successful tick refreshes the key. |
| **(2) Request-time `celery_app.control.ping()`** | At least one worker process is currently connected to the broker and its control-command consumer is responsive. | Whether Beat is alive at all (Beat does not respond to control commands — it only schedules); whether the worker is actually processing its task queue in a timely way (a worker can, in principle, still answer a control ping while backlogged or partially stuck, since Celery's control mailbox is handled separately from task execution). | Yes (via the broker) | Yes (synchronous, blocking Celery API) | Low-Medium — must be offloaded to a thread pool to avoid blocking the async FastAPI event loop, and needs an explicit short timeout | Active: a real network round-trip to every online worker on *every* health-check request; no caching benefit; adds latency proportional to worker responsiveness. |
| **(3) Beat-internal custom scheduler hook** (Beat itself writes a key on every scheduler tick, independent of any task executing) | Beat's scheduler loop specifically is alive, decoupled from worker health entirely. | Nothing about worker liveness. | Yes | Yes — requires subclassing `celery.beat.Scheduler` (`celery_app.py` currently uses Celery's default scheduler; no custom scheduler exists today) | **High** relative to Phase B's stated scope | Would need its own packaging/startup wiring in `docker-compose.yml`'s `celery-beat` command. |

### Recommendation

**Primary signal — Option 1: a Redis key with TTL, written by a lightweight Celery task that is itself scheduled via the existing Celery Beat `beat_schedule` dict.**

Reasoning:

- **Reliability / meaningfulness:** this is the *only* option of the three that validates the full chain the roadmap actually cares about — the same chain that broke silently during the A.1-era "scheduled publishing stopped working" bug (Beat schedules → worker executes → result is durable somewhere). A stale key means "the scheduled-task pipeline is not confirmed running," which is exactly the operationally meaningful failure mode.
- **Complexity / compatibility:** zero new dependencies, no new service, reuses the exact per-task async pattern already established in `publishing.py`/`discovery.py` (`run_async`, short-lived Redis client) — or, more simply, a plain synchronous Redis `SET` if the task body needs no DB session at all (an implementation-level choice for Task 1, not decided here).
- **Operational behavior:** read side is a single async Redis `GET` — cheap, cacheable in principle, no blocking calls on the FastAPI event loop.
- **Rejected as primary — Option 2 (`control.ping()`):** rejected as the *primary* mechanism because (a) it cannot detect Beat failure at all — a live, responsive worker with a dead Beat would falsely report "healthy" — which fails to satisfy the roadmap's explicit "Worker/Beat health probe" wording; (b) it is a synchronous, blocking, per-request network operation, a poor fit for a health endpoint that may be polled frequently by infra; (c) it has no persistence/TTL semantics of its own, so every request pays the full round-trip cost.
- **Rejected — Option 3 (Beat scheduler subclass):** rejected as disproportionate. Phase B's own text is "document and harden," not "extend Celery's scheduler machinery." No roadmap line asks for Beat-only isolation at this level of engineering investment.

### Secondary, on-demand diagnostic — `control.ping()` reused, not rejected outright

`control.ping()` is **not discarded** — it is demoted to an optional, best-effort field computed at request time inside the same new health endpoint (§6), used only to help a human operator disambiguate *which* half of the pipeline is broken once the primary heartbeat has already been observed stale. It must use a short timeout (e.g., ≤1–2s) and must never be allowed to make the endpoint itself slow or fail if Celery's control channel is slow/unavailable — a failed or timed-out ping simply reports `worker_reachable: null` (unknown), never blocks the primary `pipeline_heartbeat` result.

This directly answers §12 (Beat vs. Worker liveness): **they are architecturally distinct concerns, and this design explicitly does not claim one signal proves both in the strong sense** — but it also does not require two separately-scheduled, separately-implemented primitives. One scheduled primitive (the combined pipeline heartbeat) plus one cheap on-demand diagnostic (`control.ping()`) is judged sufficient for Phase B's stated scope. A fully independent Beat-only liveness signal (Option 3) is documented as available future work (§21) if operational experience ever shows the combined signal's ambiguity is a real problem in practice.

---

## 6. Health API Contract — **Decision B**

### `/ready`: unchanged

**`/ready` must not be modified.** Three independent pieces of evidence converge on this:

1. The roadmap requirement is phrased as "independent of `/ready`" — not "extend `/ready`."
2. `ReadinessResponse.checks` (`app/schemas/health.py`) is a closed `Literal["database", "redis"]` type — adding a third key is a breaking-flavored schema change to an existing, documented contract, not an additive one.
3. `06-api-integration.md` §7 already documents `/ready`'s scope in prose as DB+Redis only. Changing that boundary purely for the convenience of co-locating a check would contradict already-published, user-facing documentation with no roadmap requirement forcing it.

### New endpoint

| Property | Recommendation |
| --- | --- |
| **Path** | `GET /worker/health` |
| **Registration point** | Registered directly on the root `app` object in `app/main.py`, **at the same tier as `/health` and `/ready`** (not under `app.include_router(api_router, prefix=settings.api_v1_prefix)`) — because worker liveness, like `/health`/`/ready`, is platform infrastructure, not a versioned domain API under `/api/v1`. |
| **HTTP method** | `GET` only. No body, no request parameters for v1. |
| **Authentication** | **Unauthenticated**, matching `/health` and `/ready` exactly (both currently have no `Depends(CurrentUser)`), and matching the documented "no secrets" tier in `06-api-integration.md` §7. |
| **Response shape (illustrative only — exact field names finalized at implementation time)** | `{"status": "healthy" \| "degraded" \| "unknown", "pipeline_heartbeat": {"status": "fresh" \| "stale" \| "missing", "last_seen_at": "<ISO datetime> \| null"}, "worker_reachable": true \| false \| null}` |
| **`healthy`** | `pipeline_heartbeat.status == "fresh"` (last write within the TTL window). |
| **`degraded`** | `pipeline_heartbeat.status` is `"stale"` (key existed but expired/aged past the freshness threshold — practically indistinguishable from `"missing"` once Redis TTL has evicted it; both collapse to `degraded`). |
| **`unknown`** | Redis itself could not be reached to even perform the check — distinct from `degraded`, because `degraded` means "we checked, and the pipeline looks stopped," while `unknown` means "we could not check at all." |
| **HTTP status behavior** | `200` for `healthy`; `503` for `degraded` or `unknown` — mirroring `/ready`'s existing `not_ready → 503` convention exactly, so the same infra/uptime-check patterns already used for `/ready` work unchanged for this new endpoint. |
| **Behavior when Redis is unavailable** | Caught and reported as `unknown` + `503`, never a raw `500` — mirroring `ReadinessService._check_redis()`'s existing try/except/timeout pattern (`CHECK_TIMEOUT_SECONDS = 2.0`, catch broad `Exception`, always close the client in `finally`). |
| **Detail level** | **Aggregate only.** No per-worker hostnames, no queue depth, no task names, no counts. Exposing Celery worker hostnames/topology on an unauthenticated endpoint is unnecessary infrastructure detail for a health check and belongs (if ever needed) to an authenticated ops surface or Flower/Prometheus, not this endpoint. |
| **Explicitly must never expose** | Broker/result-backend URLs, Redis connection details, task arguments/payloads, queue contents, stack traces, or any credential — consistent with the existing `/ready` contract's "no secrets" rule. |

This is additive: no existing route, schema, or response shape changes. `DependencyStatus`/`ReadinessResponse` in `app/schemas/health.py` are untouched; a new, separate Pydantic model is introduced for the new endpoint only (naming/exact shape finalized in Task 2, not fixed here).

---

## 7. Task Failure Observability — **Decision C** (see also §8)

Two distinct observability needs exist and must not be conflated:

- **Liveness** ("is the pipeline running at all") — solved by §5/§6.
- **Failure visibility** ("are the actual scheduled business tasks — `process_publish_queue`, `refresh_hot_products`, etc. — succeeding, and if not, why") — **not** solved by the heartbeat. A heartbeat task can succeed every tick while a *different* scheduled task (e.g., `refresh_categories`) fails every single run; the heartbeat's "healthy" status is a proxy for "the machinery works," not a guarantee that every specific business task is succeeding. This gap is precisely what Decision C addresses.

Today, task failures are visible only via each container's stdout logs (`docker compose logs celery-worker`), with no aggregation, no history beyond log retention, and — critically — **no structured failure record at all for the three discovery tasks** (only Telegram publishing has a durable, queryable failure trail, via A.1's `queue_publish_attempts`).

See §8 for the tool decision.

---

## 8. Flower vs. Prometheus Decision — **Decision C, finalized**

| Criterion | Flower | Prometheus (`prometheus-client` + `/metrics`) | Defer entirely (logs/health primitives only) |
| --- | --- | --- | --- |
| New pip dependency | `flower` | `prometheus-client` | None |
| Docker/service changes | One new `docker-compose.yml` service (own container, own port), no code changes needed — Flower reads the broker/result-backend directly | New `/metrics` route + Celery signal handlers (`task_failure`, `task_success`) — application code changes required; no new *service*, but assumes an external Prometheus server to scrape it | None |
| Operational complexity | Low — point it at the existing broker URL, done | Medium — requires an actual Prometheus server + scrape config, **neither of which exists anywhere in this repository's infra today** (`docker-compose.yml` confirmed to have no such service) | Lowest |
| Security implications | Its web UI has no strong default auth; can display task names/args to anyone who reaches the port — **must** be gated with `--basic-auth` and must not be given a public port mapping (unlike, e.g., Redis's current public `6379:6379` mapping in `docker-compose.yml`, which this design explicitly does not want to replicate for a second service) | `/metrics` is conventionally unauthenticated but must be network-restricted; must avoid high-cardinality labels (e.g., never label by `queue_id`) | No new attack surface at all |
| Failure visibility | Immediate — task list, per-task state (`task_track_started=True` is already set, so Flower can show `STARTED` too), retries, tracebacks, worker status, all out of the box | Requires deliberate instrumentation (signal handlers) before any metric exists; more powerful for trend/alerting once built | Only what's already in container logs — no structured query, no history beyond log retention |
| Task-level visibility | Per-task, real-time, zero app code | Per-task, but only for whatever is explicitly instrumented | None beyond logs |
| Production usefulness *today* | Real, immediate value with the infra that exists right now | **Zero realized value until a Prometheus server exists to scrape it** — installing the client library alone produces an endpoint nobody is reading | Real but weak (raw logs only) |
| Compatible with current repo | Yes — fits the existing "one service per concern" `docker-compose.yml` pattern already used for `db`/`redis`/`celery-worker`/`celery-beat` | Partially — the `/metrics` endpoint itself fits, but the consuming half of the system (a Prometheus server) is a genuinely new infra commitment this repo has not made | Fully compatible (no change) |
| External stack already present? | Not required — Flower is self-contained | **No** — verified, no monitoring stack exists in `docker-compose.yml` | N/A |
| Maintenance cost | Low — one more container to keep running/updated | Medium — must maintain instrumentation *and* (eventually) a scrape target/dashboarding | Lowest |

```text
Recommended: Flower — deployed as an optional, gated docker-compose service
  (basic-auth required whenever reachable beyond a developer's own machine;
  never given a public port mapping by default).

Why: It is the only option that provides real, immediate failure visibility
  for all four scheduled tasks with zero application code changes, using
  infrastructure that already exists (the same broker Redis instance). It
  matches this repository's established pattern of one small, self-contained
  service per concern, and it satisfies Phase B requirement #2 as literally
  written ("Flower or Prometheus") without requiring a new external system
  (a Prometheus server) that does not currently exist anywhere in this
  project's infrastructure.

Rejected alternatives:
  - Prometheus: not rejected forever, but explicitly deferred. Concretely,
    adding `prometheus-client` and a `/metrics` endpoint today would produce
    metrics with no scraper — zero realized observability value — while still
    costing new application code (signal handlers) and a new dependency. It
    remains the architecturally "correct" long-term choice once this project
    actually operates a Prometheus/Grafana stack; that is a Post-Phase-B /
    future decision (§21), not a rejection of Prometheus as a concept.
  - Defer entirely (Option 3, logs only): rejected as the primary answer
    because it would not satisfy the roadmap's explicit requirement #2
    without a stronger justification than "it's simpler." Flower has no
    comparable blocking objection (no missing infra, no unrealized-value
    problem), so there is no good reason to fall back to logs-only when a
    low-cost, zero-app-code option is directly available.

Does deferring Prometheus still satisfy the Phase B roadmap requirement?
  Yes — the roadmap names "Flower OR Prometheus," an explicit choice between
  two named tools, not a mandate for both. Adopting Flower fully discharges
  requirement #2 as written.
```

---

## 9. Phase B vs Phase C' Retry Boundary — **Decision D**

**Verified from code:** `app/worker/tasks/discovery.py`'s three tasks (`refresh_hot_products`, `refresh_trending_products`, `refresh_categories`) carry no `autoretry_for`, `max_retries`, `retry_backoff`, or `retry_jitter` — in direct contrast to `app/worker/tasks/publishing.py`'s two tasks, which carry all four (A.1 Task 5). This is a real, confirmed gap, not a hypothetical one.

**Verified from roadmap:** `docs/08-implementation-roadmap.md`'s Phase C' section already claims a related but distinct piece of this space: *"AliExpress IOP — Existing rate limit + exponential backoff in `api_client.py`; add `ALIEXPRESS_MAX_RETRIES` enforcement review."* That is about the **AliExpress HTTP client's** internal retry behavior (config already has `aliexpress_max_retries`, `aliexpress_retry_backoff_seconds`), not about **Celery task-level** `autoretry_for` on the scheduled discovery tasks. These are two different layers of the same reliability question.

**Decision: adding Celery-level `autoretry_for`/`max_retries` to the three discovery tasks belongs to Phase C', not Phase B.**

Reasoning:

- Phase B's three named requirements (§2 of the parent analysis; repeated in `10-production-readiness.md` §9.2) are entirely about **observability** (probe, metrics, docs) — none of them describe changing a task's execution/retry *behavior*. Adding `autoretry_for` is a behavior change, not an observability addition.
- A.1 already established the canonical pattern for exactly this kind of change (`autoretry_for=(TelegramPublishError,), max_retries=3, retry_backoff=True, retry_jitter=True` on the publishing tasks). Applying that same pattern to the AliExpress-backed discovery tasks is a natural extension of **Phase C's** already-declared AliExpress-hardening mandate, not a new invention that needs to be split across two phases.
- This avoids exactly the duplication the parent task instructed against: keeping all "add Celery-task-level retry policy" work in one phase family (Telegram → done in A.1; AliExpress → Phase C') rather than partially reproducing it in Phase B for one provider while Phase C' handles the client-level retry for the same provider.
- Keeping this out of Phase B preserves Phase B's narrow, already-small scope and prevents it from re-inflating into a second reliability-hardening milestone alongside A.1.

**Explicit boundary statement:** Phase B Tasks 0–4 (this document and its successors) must not modify `app/worker/tasks/discovery.py`'s retry behavior. Any Celery-level retry decorator changes to the discovery tasks are Phase C' work.

---

## 10. A.1/A.2 Reuse

| Existing capability | Reused by Phase B? | How |
| --- | --- | --- |
| Redis instance (`settings.broker_url`) | **Yes** | The heartbeat key (§5) and the health endpoint's read (§6) use the same Redis connection the Celery broker and A.2's `EventPublisher`/`EventConsumer` already depend on. No new Redis instance, no new connection pattern. |
| `run_async` / `dispose_async_engine` pattern (`app/worker/async_utils.py`) | **Reusable if needed** | If the heartbeat task ends up touching the async SQLAlchemy engine (it likely will not — a bare Redis `SET` needs no DB session), it must go through this exact wrapper, per A.1's hardening fix. |
| `queue_publish_attempts` / dead-letter data (A.1) | **Read-only awareness only, not reuse.** | Per the parent analysis, Flower/task-failure visibility (§8) is a separate, general-purpose surface. Telegram-specific failure data already has its own durable, queryable home (A.1); Phase B must not build a second failure-tracking mechanism for Telegram specifically, and must not require Flower/Prometheus to duplicate what `GET /queues/{id}/attempts` already provides. |
| `EventPublisher`, `queue-events` Redis channel, `QueueEventEnvelope`, `EventConsumer`, `EventBroadcaster` | **Not reused, and explicitly must not be.** | A worker/Beat heartbeat is not a queue-domain event — it has no `queue_id`, does not belong in `QueueEventEnvelope`'s schema, and has no relationship to the SSE-consuming frontend. Publishing heartbeat pings onto `queue-events` would force every SSE client (and the `QueueEventEnvelope` schema itself) to understand a payload shape that has nothing to do with the queue domain, and would pollute the debounced invalidation model described in the Phase A.2 design doc. **The preferred approach — confirmed correct by this analysis — is a dedicated Redis key/mechanism, entirely separate from the `queue-events` Pub/Sub channel.** |
| SSE endpoint's own `SSE_HEARTBEAT_INTERVAL_SECONDS` (`app/api/v1/queue_stream.py`) | **Not reused — different concern.** | That constant governs a keep-alive *comment* sent to already-connected browser SSE clients to defeat proxy idle timeouts. It shares a name with this document's subject matter by coincidence only; it has a different consumer (browsers, not ops tooling), a different transport (SSE frames, not a Redis key), and a different failure mode. No code or naming should conflate the two. |
| `QueueRealtimeStatusBadge`, F4/F6 polling fallback, frontend invalidation architecture | **Not reused, not modified.** | No frontend work is in scope for Phase B (§13). |
| `task_track_started=True` (already set in `celery_app.py`) | **Available as a pre-existing primitive** | Not required by this design's primary recommendation, but noted as already-present infrastructure that Flower (§8) will automatically take advantage of (Flower can show `STARTED` state, not just terminal states) with zero additional configuration. |

---

## 11. Database Impact

**No migration, no new table, no new column, no index, no foreign key, no constraint, no backfill, no new persistent/durable model of any kind is required for Phase B.**

The parent analysis's proposed direction is **validated** by this design:

```text
Worker/Beat liveness            → Redis (TTL'd key) — ephemeral by nature; a
                                    liveness fact is only meaningful "as of
                                    now," and TTL expiry gives correct-by-
                                    construction staleness detection for free.
Operational task-failure metrics → Flower (reads the broker/result-backend
                                    directly) — no new storage of its own is
                                    introduced by this repository.
Business publish history         → Already solved by A.1's
                                    `queue_publish_attempts` table — durable,
                                    queryable, and correctly the *only* place
                                    in this system that needed real database
                                    durability, because Telegram publish
                                    outcomes are user-facing and auditable.
                                    Worker liveness/task failures are ops
                                    signals, not user-facing audit data, and
                                    do not warrant the same treatment.
```

A database-backed heartbeat/failure table was considered and rejected: it would require its own retention/cleanup logic that Redis TTL already provides natively, and would blur the line between "durable business record" (A.1's correct use of Postgres) and "transient liveness signal" (this design's correct use of Redis).

```text
Does Phase B require a migration before its first implementation task?
NO
```

---

## 12. API Impact

| Category | Detail |
| --- | --- |
| **New endpoints** | `GET /worker/health` (§6). If Flower is adopted (§8), Flower exposes its own separate web UI/port — not a FastAPI route in this codebase at all, so it has no entry in `06-api-integration.md`'s API matrix. |
| **Modified endpoints** | None. |
| **Unchanged** | `/health`, `/ready` (and its `ReadinessResponse`/`DependencyStatus` schemas), every `/api/v1/*` route, the SSE endpoint (`/api/v1/queues/stream`). |
| **Backwards compatibility** | Fully additive — no existing consumer of `/health` or `/ready` is affected. |

---

## 13. Frontend Impact

**None required. No frontend page, component, hook, query key, mutation, realtime event, or navigation change is part of Phase B**, confirmed by the parent roadmap analysis (Phase B's roadmap text has no "Frontend tasks" subsection at all, unlike A.1 and A.2).

A future Settings-workspace card surfacing `GET /worker/health` (reusing the existing `CapabilityView`/`usePlatformReadiness` pattern in `frontend/src/features/settings/`) is architecturally straightforward once §6's endpoint exists, but is explicitly classified as:

```text
Future / Optional — not part of Phase B.
```

It must not be designed or implemented as part of Task 0 or any Phase B task unless separately requested and scoped.

---

## 14. Security Considerations

### `GET /worker/health`

- **Public, unauthenticated**, matching `/health`/`/ready` exactly — this is a deliberate consistency choice, not an oversight (§6).
- Response is limited to an aggregate status + a timestamp + an optional boolean — no worker hostnames, no queue names, no task arguments, no broker/result-backend connection strings, no credentials, no stack traces on failure.
- Failure path (Redis unreachable) must degrade to `unknown`/`503`, never leak an exception message to the client (mirrors `ReadinessService`'s existing catch-broad-exception-and-report pattern).

### Flower (if adopted per §8)

- **Authentication:** must be started with `--basic-auth=<user>:<password>` (or equivalent reverse-proxy auth) whenever it is reachable from anywhere beyond a single developer's own machine. Flower has no meaningful default authentication.
- **Task argument exposure:** Flower's UI can display task names and arguments. Discovery/publishing task arguments in this codebase are low-sensitivity (queue IDs, batch sizes) but must still not be publicly reachable without auth as a matter of general hygiene — Celery task metadata is still internal operational data.
- **Port exposure:** must **not** be given a public `ports:` mapping in `docker-compose.yml` by default (in explicit contrast to the existing `redis` service's public `6379:6379` mapping, which this design does not want to replicate for a second, UI-bearing service). Recommend binding to localhost/internal network only, or behind the existing reverse proxy with its own auth layer, if deployed to any shared environment.
- **Docker networking / production risk:** should be added as an optional service (e.g., gated by a Compose profile) so it is not started unconditionally in every environment, keeping the default footprint identical to today's for anyone who doesn't need it.

### Prometheus (deferred, §8) — addressed for completeness even though not adopted now

- If ever implemented: `/metrics` should be unauthenticated but network-restricted (not exposed on a public port), consistent with common Prometheus scraping practice.
- Metric **cardinality** must stay low — label by `task_name` and `status` only; never by `queue_id`, user, or any other high-cardinality/potentially-identifying value.
- No sensitive labels (tokens, emails, content) under any circumstance.

No security mechanism beyond the above is introduced — no new auth scheme, no new secret, no new role.

---

## 15. Reliability and Failure Semantics

### What exactly does "worker healthy" mean? (explicit, non-overclaiming definitions)

| Claim | Proven by pipeline heartbeat fresh? | Proven by `control.ping()` success? | Notes |
| --- | --- | --- | --- |
| Worker process exists | Implied, but not directly | **Yes, directly** | A worker could exist yet be wedged on a hung task; `control.ping()` proves the control-mailbox path is responsive, which is a weaker claim than "fully healthy," but the strongest available single check for raw process existence. |
| Worker can consume Celery tasks | **Yes** | Not directly (ping uses a separate control path, not the task-execution path) | The heartbeat task itself had to be dequeued and executed for the key to be fresh — this is the strongest available proof of actual task consumption. |
| Celery Beat is alive | **Yes, as a necessary condition** — nothing schedules the heartbeat task without Beat running | No | If the heartbeat is stale, Beat *or* the worker could be the cause; this design does not claim to distinguish which without the secondary `control.ping()` heuristic (§5), and even that heuristic is not conclusive (see next row). |
| Redis is reachable | Proven by the very act of successfully reading/writing the key | N/A | If Redis is unreachable, the endpoint reports `unknown`, which is itself a meaningful, distinct signal (§6). |
| Scheduled *business* tasks (`process_publish_queue`, `refresh_*`) are actually executing successfully | **Not proven** | **Not proven** | This is the critical, explicitly-acknowledged limitation of a dedicated heartbeat task: it proves the *pipeline machinery* works, not that every specific scheduled task is succeeding. A `process_publish_queue` that silently raises every tick while the separate heartbeat task keeps succeeding would still report `healthy`. **This gap is exactly what Flower (§8) is for** — task-level success/failure visibility is a different signal than pipeline liveness, and both are needed for complete Phase B observability. |

### Normal / failure / detection / recovery table

| Aspect | Behavior |
| --- | --- |
| **Normal path** | Beat schedules the heartbeat task every N seconds (recommended default: 30s — see §22 Open Questions); a worker executes it; the task writes a Redis key with value = current timestamp and TTL = a multiple of N (recommended default: 90s, i.e. 3× the interval). |
| **Failure path — Beat down** | No task is ever enqueued; the key ages past its TTL and is evicted by Redis; the endpoint reports `degraded`. |
| **Failure path — worker down (Beat still up)** | Task is enqueued but never executed; same observable outcome as Beat-down (key expires); endpoint reports `degraded`. `control.ping()` in this case would report no responding workers (`worker_reachable: false`), which is the operator's clue that the worker side, specifically, is implicated. |
| **Failure path — Redis down** | Neither the write (from the task) nor the read (from the endpoint) can succeed; endpoint reports `unknown` + `503`, not `degraded` — these are deliberately distinct states (§6). |
| **Detection behavior** | Passive and continuous from the endpoint's perspective — every request re-evaluates current key freshness; no polling loop needs to run inside the API process itself. |
| **Recovery behavior** | Fully automatic: the very next successful heartbeat tick (once Beat and the worker are both back) refreshes the key and the endpoint immediately reports `healthy` again on the next request — no manual reset, no stuck state. |
| **False-positive risk** ("healthy" when something is actually wrong) | Real and explicitly acknowledged: a specific business task can be failing every tick while the heartbeat task itself succeeds (see table above). Mitigated only by adding Flower (§8) as a separate, complementary signal — not eliminated by the heartbeat alone. |
| **False-negative risk** ("degraded" when the pipeline is actually fine) | Low but non-zero: a single transient Redis write hiccup, or a worker busy with a long-running batch (`celery_publish_batch_size` up to 50 items) that delays picking up the heartbeat task, could cause one missed tick. Mitigated by setting TTL to a multiple of the interval (e.g., 3×) so one missed tick does not immediately flip the status — this is a deliberate anti-flapping choice, not an oversight. |
| **TTL behavior** | TTL is the entire mechanism for staleness detection — no manual timestamp-comparison logic is needed in the read path; Redis's native expiry does the work, keeping the read side trivially simple (`EXISTS`/`GET`, not `GET` + compute age). |
| **Expected failure semantics** | `degraded` (not a hard error) is the expected response shape when the pipeline stops — same spirit as `/ready`'s `not_ready` (503, structured, not a crash). Nothing in this design should ever produce an unhandled exception or a raw 500 from `/worker/health`. |

---

## 16. Performance Considerations

- **Redis load:** one additional `SET` per heartbeat interval (e.g., every 30s) plus occasional `GET`s from health-check callers — negligible next to the existing SSE Pub/Sub traffic already analyzed and accepted in the Phase A.2 design doc (which tolerates bursts of ~150 events/minute at current scale).
- **Celery load:** one more `beat_schedule` entry alongside the existing four — same order of magnitude, no scaling concern at this project's documented scale ("low tens" of everything, per the A.2 design doc's own framing).
- **API request cost:** a single async Redis `GET` (plus an optional, short-timeout `control.ping()`) — no database query, no N+1 risk, no large payload.
- **Flower overhead (if adopted):** continuously observes broker/result-backend events — a small, constant background load proportional to task volume, which is low here (~4 periodic tasks plus ad hoc manual publish triggers). Not a concern at current scale.
- **Forward-looking note, not a current concern:** if Prometheus is adopted later (§8, deferred) and the deployment ever scales to multiple API/worker processes, in-process counters from `prometheus-client`'s default registry would not aggregate correctly across processes without `multiprocess` mode or a push-gateway. Irrelevant today (single API + single worker + single beat per `docker-compose.yml`), but worth remembering if the topology changes.

---

## 17. Testing Strategy

No tests are written as part of Task 0. Categories for future tasks:

| Task | Test type | What to verify |
| --- | --- | --- |
| Heartbeat task (Task 1) | Worker / Unit | Task writes the expected Redis key with the expected TTL, using a mocked/fake Redis client (same style already used in `tests/test_event_publisher.py`). |
| Health endpoint (Task 2) | API | Fresh key → `healthy`/200; stale/missing key → `degraded`/503; Redis exception → `unknown`/503, never a raw 500 (mirrors the existing style of `tests/test_health.py`). |
| `control.ping()` diagnostic (Task 2) | Unit | Timeout/failure path returns `worker_reachable: null` without affecting the primary `pipeline_heartbeat` result or raising. |
| Flower (Task 3) | Manual/smoke | Not meaningfully unit-testable (external tool) — verify manually that a deliberately-failed task appears in its UI after deployment. |
| Discovery-task retry (explicitly **not** Phase B, per Decision D) | N/A here | Belongs to whichever Phase C' task eventually adds `autoretry_for` to `app/worker/tasks/discovery.py`. |

**Minimum meaningful acceptance tests for Phase B's "core complete" bar:** (1) heartbeat task writes a correctly-TTL'd key; (2) endpoint reports `healthy` on a fresh key; (3) endpoint reports `degraded` on an absent/expired key; (4) endpoint reports `unknown`/503 (never 500) when Redis is unreachable.

---

## 18. Implementation Dependencies

```text
Task 1 (heartbeat primitive) depends on: Task 0 (this document) only.
Task 2 (health endpoint)     depends on: Task 1 (nothing to read otherwise).
Task 3 (Flower)              depends on: Task 0 only — no code dependency on
                                Task 1/2 at all (Flower reads the broker
                                directly; it is pure docker-compose/requirements
                                configuration, not application code that touches
                                the heartbeat key or the new endpoint).
Task 4 (documentation)       depends on: Task 1, Task 2, Task 3 (documents
                                shipped reality, not intent — same pattern used
                                to close out A.1 and A.2).
```

Worker and Beat health are **not** split into two separate implementation tasks (see §5's conclusion): a single combined heartbeat primitive, with `control.ping()` folded in as an inline diagnostic field on the same endpoint, satisfies the roadmap's "Worker/Beat health probe" wording without the disproportionate cost of a custom Beat scheduler (Option 3, rejected in §5). Splitting them into two tasks would create an implementation dependency that does not need to exist.

---

## 19. Recommended Implementation Order

```text
Phase B
│
├── Task 0 — Worker Health & Observability Architecture Decision   [THIS DOCUMENT — COMPLETE]
│
├── Task 1 — Worker/Beat pipeline heartbeat primitive
│     One new Celery Beat schedule entry + one new lightweight task that writes
│     a TTL'd timestamp key to Redis. No API surface yet.
│
├── Task 2 — Worker health API endpoint
│     New GET /worker/health reading Task 1's key, plus the optional
│     control.ping() diagnostic field. Independent of /ready.
│
├── Task 3 — Flower deployment  (parallelizable with Task 1/2 — no shared code;
│     pure docker-compose + requirements.txt + ops config, per §18)
│
└── Task 4 — Documentation closeout
      Updates docs/10-production-readiness.md §9.2 and .env.example to describe
      what Tasks 1–3 actually shipped, following the same closeout pattern used
      for A.1 and A.2. (Not performed now — out of scope for Task 0, which may
      only create this one planning document.)
```

This deliberately deviates from a strictly linear 0→1→2→3→4 chain in one place: **Task 3 has no code dependency on Tasks 1/2** and may be implemented before, after, or concurrently with them — it is sequenced last in the diagram purely for documentation-closeout clarity (Task 4 needs all three finished to document accurately), not because Flower's own implementation requires anything from Task 1/2.

---

## 20. Explicit Decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Worker heartbeat mechanism | Redis key with TTL, written by a Celery-Beat-scheduled task executed by a worker | Validates the full Beat→worker→Redis chain with zero new dependencies; async-friendly; self-healing via TTL |
| Beat liveness | Not a separate scheduled signal/task. Inferred as a necessary condition of the combined heartbeat; `control.ping()` offered as an on-demand diagnostic to help disambiguate worker-vs-Beat when the heartbeat goes stale | A dedicated Beat-only signal requires subclassing Celery's scheduler — disproportionate complexity for Phase B's stated scope; the combined signal already satisfies the roadmap's literal "Worker/Beat health probe" wording |
| Worker health endpoint | New `GET /worker/health`, registered at root (sibling to `/health`/`/ready`), unauthenticated, aggregate-only response | Additive; matches the existing root-level, no-secrets health-check tier; no impact on `/ready` |
| `/ready` modification | NO | Roadmap requires independence; `ReadinessResponse.checks` is a closed `Literal["database","redis"]` type; `06-api-integration.md` already documents `/ready`'s DB+Redis-only scope |
| Failure observability | Flower | Satisfies roadmap requirement #2 today with zero application code changes, using only infrastructure that already exists |
| Flower | ADOPT, as an optional/gated docker-compose service with mandatory basic-auth beyond localhost, no public port mapping by default | Self-contained, reads the broker directly, fits the existing one-service-per-concern `docker-compose.yml` pattern |
| Prometheus | DEFER (not rejected as a concept) | No Prometheus server exists anywhere in this repository's infrastructure to scrape `/metrics`; adopting it today would add a dependency and application code for zero realized observability value |
| Database migration | NO | Liveness is inherently ephemeral (Redis TTL is the correct mechanism); durable business history already exists via A.1's `queue_publish_attempts`; a DB-backed heartbeat/failure table would duplicate what Redis already does for free |
| Frontend work | NO | Roadmap defines no Phase B frontend scope; any future Settings-page surface is classified Future/Optional only |
| Discovery retry ownership | Phase C' | Adding `autoretry_for`/`max_retries` to discovery tasks is a behavior change, not observability; mirrors A.1's Telegram-retry pattern and Phase C's own already-declared "AliExpress IOP retry" bullet — keeps Phase B scoped purely to observability and avoids splitting one provider's retry-hardening work across two phases |

---

## 21. Non-Goals

Explicit guardrails for every Phase B implementation task that follows this document:

- Do **not** rebuild, modify, or re-schedule `process_publish_queue`, `refresh_hot_products`, `refresh_trending_products`, or `refresh_categories` — all four are complete, pre-existing infrastructure.
- Do **not** modify `TelegramPublishingService`, `QueuePublishAttempt`, the idempotency guard, retry policy, or dead-letter marking (A.1) — do not duplicate that work.
- Do **not** modify `EventPublisher`, `EventConsumer`, `EventBroadcaster`, `QueueEventEnvelope`, the `queue-events` Redis channel, the SSE endpoint, or any frontend realtime-invalidation code (A.2/F1–F6).
- Do **not** publish worker/Beat heartbeat data onto the `queue-events` channel or into `QueueEventEnvelope` — it is architecturally a different concern with a different consumer (§10).
- Do **not** modify `/health` or `/ready`, or `ReadinessResponse`/`DependencyStatus` (§6).
- Do **not** add Celery-level `autoretry_for`/`max_retries` to the discovery tasks as part of Phase B (§9, Decision D) — that is Phase C' work.
- Do **not** implement separate Celery queues (`publishing`/`discovery_refresh`/`ai_batch`) — already explicitly marked "(future)" in `10-production-readiness.md` §9.2.
- Do **not** adopt Prometheus in this phase (§8) — deferred, not part of Phase B's implementation tasks.
- Do **not** build any frontend page, component, hook, or navigation change (§13).
- Do **not** expose per-worker hostnames, task arguments, queue contents, or any credential/connection string on the new public endpoint (§6, §14).
- Do **not** build alerting/paging integration (e.g., PagerDuty/Slack) — "alert on beat/worker absence" from `10-production-readiness.md` §9.2 is satisfied at the *capability* level (Flower's UI + the new health endpoint make absence observable); wiring actual alerts is a separate, later concern not implied by Phase B's own three bullets.

---

## 22. Open Questions

Items that cannot be fully fixed from repository evidence alone; each includes a safe default so implementation is not blocked.

| Question | Why it's open | Safe default (to be finalized in Task 1/2) |
| --- | --- | --- |
| Exact heartbeat interval and TTL values | No roadmap text specifies a number; must balance detection speed against noise/flapping | Interval: 30s (more sensitive than the 60s `process_publish_queue` interval it exists to protect); TTL: 90s (3× interval, tolerates one missed tick) |
| Exact endpoint path naming (`/worker/health` vs. `/health/worker` vs. `/ready/worker`) | A naming preference, not a technical constraint | `/worker/health`, for symmetry with `/health`/`/ready` both being short root-level nouns; easily renamed before Task 2 ships if reviewers prefer otherwise |
| Whether `worker_reachable` (the `control.ping()` field) ships in v1 of the endpoint or is added later | Cheap to include, but adds one more moving part to Task 2 | Include from v1 — it is low-cost and directly serves §11/§12's own request for Beat-vs-worker disambiguation; may be dropped from Task 2's first cut if it proves noisy in practice |
| Flower's exact deployment gating mechanism (Compose `profiles:`, a separate `docker-compose.monitoring.yml`, or an env-var-conditional service) | A Compose-authoring detail, not an architectural one | Use a Compose `profiles:` entry (not started by `docker compose up` by default) — finalized in Task 3, since Task 0 must not modify `docker-compose.yml` |

---

## Related Documents

- [08-implementation-roadmap.md](../08-implementation-roadmap.md) — Phase B scope authority (§3); this document elaborates it without altering its acceptance criteria or task list.
- [06-api-integration.md](../06-api-integration.md) — existing `/ready` contract this design must not break.
- [10-production-readiness.md](../10-production-readiness.md) §9.2 — the three literal Phase B requirements this design resolves the architecture for.
- [phase-a2-realtime-operations-design.md](./phase-a2-realtime-operations-design.md) — precedent for this project's minimalism principles (no unnecessary abstractions, accepted trade-offs) and the source of the `EventPublisher`/`queue-events` infrastructure this design deliberately does **not** reuse for heartbeats (§10).

*This document is the Phase B Task 0 ADR. Tasks 1–4 are implemented; do not re-open Tasks 0–3 as unfinished work. Runtime source of truth is the repository.*
