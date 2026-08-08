# Phase A.2 — Real-time Queue Updates

**Status:** COMPLETE  
**Completed:** 2026-08-08  
**Depends on:** Phase A.1 (Publishing Reliability Foundation) — complete  
**Scope authority:** `docs/08-implementation-roadmap.md` §3 "Phase A.2 — Real-time operations"

```text
Phase A.2 — Real-time Queue Updates
Status: COMPLETE
```

This document is the design record for Phase A.2. Where early draft proposals differ from the shipped code, **the implemented architecture below is the source of truth.**

**Revision (2026-08-07):** Incorporated two architectural decisions following design review: (1) the SSE client parsing core is **vendored** from `@microsoft/fetch-event-source` rather than hand-rolled or added as a live npm dependency — see §6, §12, §14 Risk 7, §15 Task F1; (2) the dedicated `dashboard.stats_updated` event is **removed** — Queue workspace KPI cards already refresh from the existing `queue.*` → `queueKey` invalidation, and Dashboard-page live updates are out of scope for Phase A.2 — see §2, §6, §9, §15, §16.

**Revision (2026-08-08 — closeout):** Phase A.2 marked COMPLETE. Documented the final EventConsumer + EventBroadcaster fan-out (evolved from the original per-SSE Redis subscription proposal), the shipped F1–F5 task set with polling fallback, F6 as optional/stretch (not required), verified resilience behavior, and post-A.2 improvements that do not block completion.

---

## 0. Executive Summary

Phase A.2 adds a **push notification layer on top of the existing REST API** — it does not change how data is written, validated, or stored. The database (via the Phase A.1 `queue_publish_attempts` table and `QueueItem.status`) remains the single source of truth. Real-time delivery is an **enhancement layer**: if it fails entirely, the app remains fully usable (mutation-triggered invalidation + manual refresh + TanStack Query polling fallback).

**Shipped solution:** Server-Sent Events (SSE) at `GET /api/v1/queues/stream`, backed by Redis Pub/Sub channel `queue-events`, consumed by one `EventConsumer` per API process and fanned out in-process via `EventBroadcaster` to authenticated SSE clients. The frontend uses a fetch-based SSE client with a **vendored** parsing core (not native `EventSource`; not an npm runtime dependency on `@microsoft/fetch-event-source`), drives **TanStack Query cache invalidation** (never manual cache mutation), and enables adaptive list/attempts polling (5s → 30s) when SSE is unavailable.

### Final implemented architecture

```text
Queue mutation (API or Celery)
    ↓
EventPublisher
    ↓
Redis Pub/Sub channel: queue-events
    ↓
EventConsumer (one per API process; lifespan-managed)
    ↓
EventBroadcaster (process-local fan-out)
    ↓
Authenticated SSE endpoint GET /api/v1/queues/stream
    ↓
Frontend SSE client (sse-client.ts)
    ↓
useQueueEventStream → useQueueRealtimeInvalidation
    ↓
TanStack Query invalidateQueries (debounced)
    ↓
Authoritative API refetch
    ↓
Queue UI (table, KPIs, drawer)
```

### Polling fallback (shipped)

```text
SSE connected
    → polling disabled

SSE disconnected (or reconnecting after a prior live session)
    → polling enabled (TanStack Query refetchInterval, 5s → 30s)

SSE reconnects successfully
    → one authoritative queue refresh (not on first connect)
    → polling disabled
```

There is **no** `dashboard.stats_updated` event. Queue KPI cards refresh from `queue.*` → `["queue"]` invalidation. Dashboard-page live updates remain out of scope.

---

## 1. Transport: SSE vs. WebSockets

### Decision: **Server-Sent Events (SSE)**

| Dimension | SSE | WebSockets | Why it matters here |
| --- | --- | --- | --- |
| Data direction | Server → client only | Bidirectional | Phase A.2's entire scope is server-pushed status/event notifications. No client→server realtime channel is needed — all mutations already go through `POST/PATCH/DELETE /queues*` (REST, unchanged). Bidirectionality would be unused capability. |
| Transport | Plain HTTP (chunked `text/event-stream`) | Own framing over an upgraded TCP connection | FastAPI/Starlette serve SSE natively via `StreamingResponse` — no new library, no protocol upgrade handling, no separate ASGI lifespan concerns. |
| Reconnection | Built into the spec (`EventSource` auto-reconnects; `Last-Event-ID` support) | Must be hand-rolled | The roadmap explicitly requires a reconnect + polling-fallback story (§7 below). SSE gives most of this "for free" at the protocol level even though we use a fetch-based client instead of `EventSource` (see §4/§6 — we still implement the same reconnect semantics ourselves, but the spec and prior art are unambiguous). |
| Infra compatibility | Works through existing `CORSMiddleware`, reverse proxies, and load balancers designed for HTTP; only requires disabling response buffering | Needs `Upgrade`/`Connection` header support at every hop (reverse proxy, LB) — not currently configured or documented anywhere in `10-production-readiness.md` | Introducing WS would add an undocumented infra requirement to every deployment target. SSE adds one documented header (`X-Accel-Buffering: no`). |
| Current auth model | Same Bearer JWT via `CurrentUser`/`get_current_user` — reusable if the client sends the header itself | Auth typically passed via subprotocol header or first-message handshake — a new pattern | SSE keeps authentication **identical** to every other route in `app/api/v1/queues.py`. No new auth code path. |
| Scalability primitive needed | Redis Pub/Sub (already a dependency — see `app/services/health.py`, already the Celery broker) | Same requirement — WS still needs Redis Pub/Sub (or similar) to fan out across multiple Uvicorn processes/replicas | Choosing WS would not remove the need for Redis fan-out; it only adds protocol complexity on top of the same requirement. |
| Future roadmap | Sufficient for all currently planned real-time features (queue status, attempt events, KPI refresh) | Would only be justified by a future bidirectional feature (e.g., live collaborative editing, chat) — nothing in the roadmap needs this | No forward-looking justification exists today. If such a feature appears later, it can be added as its own WS endpoint without touching this design. |

**Conclusion:** SSE is the better fit on every axis that matters for this project today: unidirectional data flow, zero new infrastructure, reuse of the existing auth dependency, and a simpler operational story. WebSockets would add complexity (framing, upgrade handling, proxy configuration) to solve a bidirectionality requirement that does not exist in Phase A.2's scope.

---

## 2. Event Architecture

### Naming convention

Use **domain-dot-action** names (`<domain>.<action>`), not the roadmap's flat names (`publish_started`, etc.) verbatim. Reasons:

- Matches the project's existing domain-first organization (`features/queue`, `features/dashboard`, backend `app/services/queue.py`, `app/services/health.py`, etc.).
- Leaves room for future domains (`product.*`, `channel.*`) without name collisions.
- A single `event` string discriminator (rather than one Redis channel per event type) keeps the transport layer trivial — see §5.

The roadmap's suggested names map 1:1 to the canonical names below; nothing conceptually changes, this is a naming normalization only.

### Do NOT add a separate `attempt.created` event

The roadmap listed `attempt.created` as a candidate alongside `publish_started`. These describe the **same moment** (the `started` attempt row is inserted and committed in `TelegramPublishingService._claim_publish`). Emitting both would mean two events for one state transition — the client would have to know they're duplicates. **`queue.attempt_started` is the single canonical event for that moment.**

### Canonical event catalog

| Event name | Emitted when | Producer (code location) | Primary consumer(s) | Payload `data` shape |
| --- | --- | --- | --- | --- |
| `queue.status_changed` | `QueueItem.status` changes via any path: `PATCH /queues/{id}` (`QueueService.update`), successful publish (`TelegramPublishingService.publish_queue_item` success branch), or status-drift healing (`_claim_publish` healing branch) | `QueueService.update`; `TelegramPublishingService` (success + heal branches) — **after** `session.commit()` | `QueueTable`, `QueueOperationalStats`, `QueueDetailsDrawer` (if open on that item) | `{ queue_id, status, previous_status, scheduled_at, published_at }` |
| `queue.deleted` | `DELETE /queues/{id}` completes | `QueueService.delete` — after commit | `QueueTable` (remove row), `QueueDetailsDrawer` (close if open on that id) | `{ queue_id }` |
| `queue.attempt_started` | A new `started` attempt row is committed (claim acquired, about to call Telegram) | `TelegramPublishingService._claim_publish` — after its commit | `QueueDetailsDrawer` attempt history, `QueueHealthBadge`/`QueueOperationalStats` ("publishing" signal, still allowed to be client-ephemeral per Phase A.1 rules — this event is an additional confirming signal, not a new source of truth) | `{ queue_id, attempt_number, provider }` |
| `queue.attempt_succeeded` | An attempt is marked `succeeded` (Telegram accepted the message) | `TelegramPublishingService._mark_attempt_succeeded` caller, i.e. the success branch of `publish_queue_item` — after commit | `QueueDetailsDrawer` attempt history, `QueueOperationalStats` ("published today") | `{ queue_id, attempt_number, provider_message_id }` |
| `queue.attempt_failed` | An attempt is marked `failed` (transient or terminal/`dead_letter`) | `TelegramPublishingService._mark_attempt_failed` — after its commit | `QueueDetailsDrawer` attempt history, `QueueHealthBadge` ("failed today" / error state) | `{ queue_id, attempt_number, error_code, is_terminal }` |

Notes:

- **No `queue.created` event.** `POST /queues` (draft/queued creation from AI/products/discovery) is out of scope per the roadmap's explicit list (queue status transitions + publish attempt events only). Adding it would be scope creep; it can be added additively later using the same envelope if needed.
- **`queue.deleted` is an addition beyond the roadmap's literal list**, justified because Phase A.1 already made deletion a first-class queue operation (cascade-delete fix, `tests/test_queue_delete.py`) and an open `QueueDetailsDrawer` on a deleted item is a real UX bug without this signal. This is additive and does not change any Phase A.1 contract.
- Every producer call site is a location that **already calls `session.commit()` today** (see `app/services/queue.py`) — event emission is added immediately after existing commits, never before, never replacing them.
- **No dedicated `dashboard.stats_updated` event exists in this catalog.** `QueueOperationalStats` (the Queue workspace's own KPI cards — queued/scheduled/publishing/published-today/failed-today) is computed **client-side from the `useQueue()` list query** (`getQueueOperationalStats(enrichedItems, ...)`), not from a separate backend aggregate call. The moment any `queue.*` event above triggers the existing `invalidateQueries({ queryKey: queueKey })` (§6), those KPI cards refresh automatically — no additional event, backend logic, or Redis traffic is needed to make them live. See §6 for the separate (out-of-scope) question of the `/dashboard` route's own page.

---

## 3. Event Payload — Versioned Envelope

All events share one envelope; `data` is event-specific (shapes above).

```json
{
  "event": "queue.attempt_failed",
  "version": 1,
  "id": "01J9Z8H5F9T4S1R7D8P2K3M4N5",
  "occurred_at": "2026-08-07T09:40:12.483Z",
  "workspace_id": null,
  "queue_id": "6f9c2e34-2b1a-4b2e-9f0a-1234567890ab",
  "data": {
    "attempt_number": 3,
    "error_code": "dead_letter",
    "is_terminal": true
  }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `event` | `str` | Canonical dot-namespaced name from §2. Doubles as the SSE `event:` frame field. |
| `version` | `int` | Envelope schema version, starts at `1`. Bump only on a breaking `data` shape change for a given `event`; additive fields never require a bump. |
| `id` | `str` | Stream cursor generated at publish time. **As shipped:** UUID4 string (used as the SSE `id:` field for `Last-Event-ID`). ULID was the original design preference and remains a post-A.2 improvement — see §18. Not a database primary key. |
| `occurred_at` | `datetime` (ISO 8601, UTC) | When the underlying DB commit happened — not when the event reaches a given client. |
| `workspace_id` | `str \| null` | **Reserved for future multi-tenancy. Always `null` today.** The current backend has no workspace/tenant concept (`10-production-readiness.md` §6: "Queue and channel routes are authenticated but not user-scoped"). Do not build filtering logic against this field now — see §10. |
| `queue_id` | `UUID` | Present on every event in this catalog (all are queue-scoped). If a future non-queue domain event is added, this field would be omitted for that event type. |
| `data` | `object` | Event-specific fields per §2. **Only fields already exposed by `QueueRead`/`QueuePublishAttemptRead`** — never raw exception objects, stack traces, SQLAlchemy model dumps, bot tokens, or channel credentials. |

**No internal leakage rule:** `data.error_code`/`data.error_message`-shaped fields must be sourced from the same values already serialized by `QueuePublishAttemptRead` (i.e., what `GET /queues/{id}/attempts` already returns publicly). The event stream must never expose more than the REST API already does for an authenticated user.

---

## 4. SSE Endpoint Design

| Property | Design |
| --- | --- |
| **URL** | `GET /api/v1/queues/stream` — lives under the existing `/queues` prefix (new module `app/api/v1/queue_stream.py`, registered in `app/api/v1/router.py`), consistent with `06-api-integration.md` §4.6 |
| **Authentication** | Same `CurrentUser` dependency as every other queue route (`app/auth/dependencies.py`). **Requires the client to send `Authorization: Bearer <jwt>` as a request header** — this is why native `EventSource` (which cannot set custom headers) is not used; see §6 for the fetch-based client. |
| **Authorization** | Any authenticated, active user (matches current `GET /queues` behavior — not role-gated, not tenant-scoped). No new authorization rule introduced. |
| **Connection lifecycle** | `StreamingResponse(generator(), media_type="text/event-stream")`. Response headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`. **As shipped:** the generator subscribes to the process-local `EventBroadcaster` (not a per-connection Redis `SUBSCRIBE`), loops emitting SSE frames, sends heartbeats on idle, and detects client disconnect via `request.is_disconnected()`. |
| **Heartbeat** | **As shipped:** every **30s**, emit an SSE comment (`: heartbeat\n\n`) when idle. (Original design proposed 15s — reducing to 15s is a post-A.2 improvement.) |
| **Disconnect behavior** | On client disconnect (detected via `is_disconnected()` or a broken pipe on write), the generator exits its loop. |
| **Cleanup strategy** | `try/finally` unsubscribes the broadcaster callback and cancels the disconnect watcher. Slow clients: per-connection `asyncio.Queue` maxsize **64**; overflow closes that client only. |
| **Connection cap** | **Not shipped in A.2.** A per-process SSE connection cap returning `503` remains a post-A.2 improvement. |

---

## 5. Backend Architecture

### Where connections are managed (as shipped)

**Final architecture:** one Redis Pub/Sub subscription per API process, not per SSE client.

| Component | Role |
| --- | --- |
| `EventPublisher` | Serializes a validated `QueueEventEnvelope` and `PUBLISH`es to channel `queue-events` |
| `EventConsumer` | Started in FastAPI lifespan (`app/main.py`); one instance per process; validates messages and forwards to the broadcaster; reconnects on Redis session failure |
| `EventBroadcaster` | Process-local async subscriber registry shared by the consumer and all SSE streams |
| `GET /queues/stream` | Subscribes a per-request callback to the broadcaster; frames envelopes as SSE; no direct Redis access |

This evolved from the original per-SSE Redis `SUBSCRIBE` proposal: the shared consumer + in-process broadcaster avoids N Redis subscriptions for N browsers on the same worker while preserving Redis fan-out across API replicas.

Security headers middleware is a pure ASGI wrapper (not `BaseHTTPMiddleware`) so SSE bodies are not buffered.

### How events are published — `EventPublisher`

`app/events/publisher.py`:

- Wraps a `redis.asyncio` client's `PUBLISH` to the fixed channel `queue-events` — not one channel per event type. The envelope `event` field is the discriminator.
- `NullEventPublisher` (no-op) is the constructor default for unit tests / missing lifespan Redis. Production API injects a real publisher via `get_event_publisher` (`app.state.event_redis`); Celery builds one per task with `create_event_publisher`.
- Domain emission uses `_publish_queue_event`: Redis failures are **logged** and must **not** roll back an already-committed mutation.

### How services emit events

Every emission call site is a place that **already commits today**:

| Service method | Existing commit | Emit after commit |
| --- | --- | --- |
| `QueueService.update` | status-changing update + commit | `queue.status_changed` (only if `status` actually changed) |
| `QueueService.delete` | delete + commit | `queue.deleted` |
| `TelegramPublishingService._claim_publish` | `await self.session.commit()` | `queue.attempt_started` |
| `TelegramPublishingService.publish_queue_item` (success branch) | `await self.session.commit()` | `queue.attempt_succeeded` then `queue.status_changed` when status changed |
| `TelegramPublishingService._claim_publish` (status-heal branch) | `await self.session.commit()` | `queue.status_changed` |
| `TelegramPublishingService._mark_attempt_failed` | `await self.session.commit()` | `queue.attempt_failed` |

**Hard rule:** publish only ever happens *after* a successful commit, never before, and never inside a `try` block that could still roll back.

### Does an event bus need to exist?

Yes — the minimal shipped bus is `EventPublisher` (write) + Redis Pub/Sub + `EventConsumer` / `EventBroadcaster` (read). No Kafka/RabbitMQ topic design, no persistent event log. Redis Pub/Sub is fire-and-forget with no history (accepted; reconnect invalidation closes gaps).

### How Celery workers communicate with SSE

```text
Celery task (TelegramPublishingService)
        │  commits attempt/status change
        ▼
EventPublisher.publish() → Redis PUBLISH "queue-events" <json>
        │
        ▼  (Redis fan-out across API processes)
EventConsumer (per API process) → EventBroadcaster
        │
        ▼
Open GET /queues/stream clients (SSE frames)
```

Instrumenting `TelegramPublishingService` once covers both manual `POST /queues/{id}/publish` and Celery tasks. Celery constructs a short-lived Redis client + `EventPublisher` per task invocation.

---

## 6. Frontend Architecture

### Subscription hook

New `useQueueEventStream()` in `frontend/src/features/queue/hooks/` (or `useQueueLiveSync` — naming TBD at implementation time), built on top of `frontend/src/features/queue/lib/sse-client.ts`. Responsibilities:

1. Open a **fetch-based** SSE connection (not native `EventSource`), sending `Authorization: Bearer <jwt>` exactly like `services/api-client.ts` does for every other request. Native `EventSource` cannot set custom headers, and this project's JWT lives in `sessionStorage` behind an Axios interceptor (not an `httpOnly` cookie), so `EventSource` is architecturally incompatible with the existing auth model without inventing a new token-in-URL mechanism — which the design explicitly avoids (see Risk table, §14).
2. **Frame parsing is delegated to a vendored parser, not implemented from scratch.** `sse-client.ts` copies and adapts the minimal, MIT-licensed SSE wire-format parsing logic from `@microsoft/fetch-event-source` (attribution comment retained) rather than (a) hand-writing a byte/line parser from first principles, or (b) adding `@microsoft/fetch-event-source` as a live npm dependency. Rationale:
   - Correctness: spec-compliant SSE parsing has several non-obvious pitfalls — UTF-8 decoding across chunk boundaries (relevant here given the app's Arabic-heavy content), `\n`/`\r\n`/`\r` line-ending handling, multi-line `data:` field joining, and comment-line (`: heartbeat`) skipping without disturbing in-progress event buffering. Getting any of these subtly wrong produces intermittent, hard-to-reproduce dropped/garbled events in production rather than a clean failure — a bad category of bug to author from scratch when a proven, spec-compliant reference implementation already exists.
   - Dependency posture: `@microsoft/fetch-event-source` (latest release `2.0.1`, April 2021; zero commits/issue activity in the last 90 days) is functionally stable — the SSE spec it implements hasn't changed — but is not actively maintained, and has zero runtime dependencies of its own. Rather than taking on a dormant package in `package.json`, its small, self-contained parsing core is copied directly into `sse-client.ts`. This keeps the proven, battle-tested logic (it is the de facto standard for this exact problem, at ~2.9M weekly npm downloads) without an ongoing external dependency on an inactive repository.
   - **The vendored code is responsible for SSE wire-format parsing only.** Everything else remains our own code in `sse-client.ts`: the `Authorization` header, reconnect strategy, exponential backoff with jitter (§7), `Last-Event-ID` handling (§8), `AbortController`-based cleanup, and fatal `401`/`403` stop-retry behavior.
   - The vendored parser is isolated entirely behind `sse-client.ts`'s module boundary — no other file depends on its internals.
3. Track connection `status`: **`'connecting' | 'connected' | 'disconnected' | 'error'`** (as shipped). Surface via `QueueRealtimeStatusBadge` (F4). Polling is an internal resilience flag (`pollingEnabled`), not a separate status string.
4. Domain reactions go through `useQueueRealtimeInvalidation` → debounced `invalidateQueries` — **not** component state or a new client store.

### Cache update strategy: invalidate, never patch

**Decision: on every event, call `queryClient.invalidateQueries(...)` (debounced), never `queryClient.setQueryData(...)` to hand-apply the event payload into the cache.**

Rationale — this is the most important frontend decision in this design:

- `QueueRead` has server-computed fields (`last_attempt`, `failure_reason`, `retry_count`) that the client would have to reconstruct correctly from a partial event payload to do manual patching — that logic would duplicate backend computation and risk drift, directly against the "no client-owned source of truth" constraint that Phase A.1 just finished eliminating for failure state.
- Invalidation-triggered refetches are **naturally idempotent and order-independent**: two duplicate events, or two events arriving out of order, both just mean "refetch the current DB truth" — the result is identical regardless of how many times or in what order the trigger fired. Manual payload-patching would not have this property (e.g., blindly incrementing a `retry_count` twice would be wrong).
- TanStack Query already de-dupes concurrent identical in-flight requests, so a burst of invalidations does not create a burst of network calls.

Concretely:

| Event(s) received | Action |
| --- | --- |
| `queue.status_changed`, `queue.deleted` | Debounced `invalidateQueries({ queryKey: queueKey })` (the list query `useQueue` reads) |
| `queue.attempt_started` \| `_succeeded` \| `_failed` | Debounced `invalidateQueries({ queryKey: queueAttemptsKey(queue_id) })` **and** `queueKey` (attempt summary fields live on `QueueRead` too) |

Debounce window: ~300ms, implemented as a small hand-rolled timer (consistent with the project's existing style of small local utilities in `lib/operations.ts` rather than adding a `lodash.debounce` dependency) — this coalesces a 50-item batch-publish burst (up to ~150 raw events) into a single refetch per affected query.

By default, TanStack Query's `invalidateQueries` only refetches **active** (mounted) queries — so invalidating `queueAttemptsKey(id)` for a drawer that isn't open performs no network call; it will simply refetch fresh next time that drawer opens. No extra guard logic is needed for this.

### Integration with TanStack Query

No new query client configuration is required. `useQueueEventStream` is called with `useQueryClient()` from the existing provider tree (`app/providers.tsx`), exactly like every other hook in `features/queue/hooks/useQueue.ts`.

### Optimistic updates

**None are introduced.** Mutations already get an immediate HTTP response today (`useQueuePublishingOperations`, `useUpdateQueueItem`, `useDeleteQueueItem` all call `invalidateQueries` on success already). SSE events are a **secondary, confirming signal** — useful for changes triggered by *other* actors (Celery beat publishing on a schedule, another operator's browser tab) — not a mechanism for predicting UI state ahead of the server. The one already-allowed exception, ephemeral `publishingIds` client state, is unaffected and unchanged by this design.

### Where it's mounted

`QueueView` mounts `useQueueRealtimeInvalidation()` once (which owns `useQueueEventStream`), provides `QueueRealtimePollingContext` for `useQueue` / open attempts queries, and threads realtime `status` into `QueueToolbar` via `QueueRealtimeStatusBadge`. Not mounted in `AppShell`/`providers.tsx` globally — Phase A.2 scope is the queue workspace.

**`DashboardView` live updates are out of scope for Phase A.2.** The Queue workspace's own KPI cards (`QueueOperationalStats`) already update live "for free" the moment `queue.*` events invalidate `queueKey` (§2), because those cards are computed client-side from the same `useQueue()` list query — no dashboard-specific event or backend logic is required for that. The separate `/dashboard` route's own aggregate (`GET /dashboard` → `DashboardOverview`) is a different page and is not named in the roadmap's Phase A.2 scope; it keeps its current fetch-on-mount/focus behavior. If live updates for that page are wanted in a future phase, the lightweight extension is: mount the same `useQueueEventStream()` hook on `DashboardView` and, on the client side, invalidate `['dashboard']` for any `queue.*` event received — no new backend event, channel, or emission logic required. This is documented as a non-goal for this phase in §16.

---

## 7. Polling Fallback (as shipped)

| Aspect | Shipped behavior |
| --- | --- |
| **When polling is disabled** | SSE `status === "connected"` (or fatal `error` / hook disabled). Initial `connecting` (never yet established) does **not** start aggressive polling. |
| **When polling is enabled** | After a live session is lost: `disconnected`, or `connecting` while reconnecting after a prior established connection. Driven by `pollingEnabled` from `useQueueRealtimeInvalidation` via `QueueRealtimePollingContext`. |
| **SSE reconnect backoff** | Exponential with jitter in `sse-client.ts`: ~1s, 2s, 4s, … capped at 30s. Continues while disconnected; polling runs in parallel as the authoritative refresh path. |
| **Polling cadence** | TanStack Query `refetchInterval` on `useQueue` and open `useQueuePublishAttempts`, via `createQueuePollIntervalSelector()`: starts at **5s**, doubles on consecutive unchanged poll results (**10s → 20s → 30s** cap). Resets to 5s when data changes. |
| **Returning to SSE** | On successful reconnect after a previously established connection: (1) one `invalidateQueries({ queryKey: ["queue"] })`, (2) `pollingEnabled = false`, (3) resume push-driven invalidation. **First successful connect does not trigger that reconnect refresh.** |
| **Unmount** | AbortController aborts the SSE stream; invalidator is disposed; context polling flag clears with the provider — no orphan timers/streams. |

---

## 8. Failure Handling (verified)

| Scenario | Behavior |
| --- | --- |
| **Redis unavailable at API startup** | API remains available; `EventConsumer` retries its Redis session in a background loop. |
| **Redis disconnect after startup** | Consumer logs, closes pub/sub, reconnects after a short delay. |
| **Redis publish fails** | Domain mutation already committed remains successful; `_publish_queue_event` logs the failure. |
| **Malformed Redis event** | Consumer skips invalid payloads; does not crash. |
| **Unknown event name** | May still be framed if envelope-valid; frontend mapping returns no query keys → no invalidation. |
| **Lost SSE connection** | Status becomes `disconnected` then `connecting` on reconnect sleep; polling enables after a prior live session; `QueueRealtimeStatusBadge` stays informational. |
| **Reconnect** | Client sends `Last-Event-ID` when known. Redis has no replay — correctness comes from the one-time reconnect `invalidateQueries(["queue"])` plus polling while down. |
| **Duplicate / out-of-order events** | Safe: invalidate + refetch only; never payload patching. |
| **SSE 401 / 403** | Fatal: stop reconnect loop; status `error`. **As shipped:** stream does not yet call the shared Axios `session.clear`/redirect helper (post-A.2 improvement); subsequent REST calls still clear session as today. |
| **Component unmount / StrictMode** | AbortController + invalidator dispose; no duplicate live streams; no late invalidation after unmount. |
| **Realtime unavailable** | Queue publish / retry / schedule / delete / refresh / filters remain usable. |

---

## 9. Performance

| Aspect | Assessment |
| --- | --- |
| **Expected simultaneous connections** | This is an internal operator tool (admin/affiliate roles), not a public consumer product. Expect **low tens** of concurrent SSE connections in production, not thousands. Nothing in this design requires a specialized connection-sharding architecture at this scale. |
| **Memory considerations** | **As shipped:** one Redis Pub/Sub subscription per API process (`EventConsumer`) plus a small in-process broadcaster and per-SSE bounded queues (max 64). At tens of connections this is negligible. |
| **Event frequency** | Bounded by publish activity: a single Celery beat tick (every 60s, up to `celery_publish_batch_size` = 50 items) can emit up to ~150 events in a short burst (`attempt_started` + `attempt_succeeded`/`attempt_failed` + `status_changed`, per item). This is the actual justification for the client-side debounce in §6, not a backend concern. This count already reflects the catalog in §2 — there is no separate `dashboard.stats_updated` fan-out event doubling this volume; Queue KPI cards refresh from the same `queue.*` events rather than a dedicated signal. |
| **Batching requirements** | None needed now. Server-side event coalescing (buffering multiple raw events into one before publishing) was considered and **rejected** for Phase A.2 — it would add a stateful buffering component for marginal benefit at current scale (~150 events/minute peak, tens of subscribers). Client-side debounce (§6) is simpler and sufficient. Revisit only if beat batch size grows well beyond ~500/tick. |
| **Scalability concerns** | Horizontally scaling the FastAPI/Uvicorn process (more replicas behind a load balancer) requires **zero changes** to this design — Redis Pub/Sub fans out to every subscribing process automatically. This is the core reason Redis Pub/Sub (over an in-process asyncio broadcaster) was chosen in §5. |

---

## 10. Security

| Aspect | Design |
| --- | --- |
| **Authentication** | Identical to every other `/queues/*` route: `CurrentUser` (JWT Bearer decode + active-user lookup via `app/auth/dependencies.py`). No new auth mechanism, no token-in-URL. |
| **Authorization** | Any authenticated, active user may open the stream — matching today's `GET /queues` behavior exactly (not role-gated). No new exposure is introduced: nothing in any event payload (§3) is data a user couldn't already fetch via `GET /queues`, `GET /queues/{id}`, or `GET /queues/{id}/attempts`. |
| **Workspace isolation** | **Not applicable today.** The backend has no workspace/tenant concept; `10-production-readiness.md` §6 already documents that queue/channel routes are "not user-scoped" and this is explicitly "not multi-tenant safe." The `workspace_id: null` field in the envelope (§3) is a forward-compatible placeholder only. Building tenant-filtering logic into the event layer now, ahead of the REST layer supporting it, would be speculative scope creep — explicitly out of scope per this design's constraints. When multi-tenancy is eventually added, the REST API and the event/channel scheme must be updated **together** in that future phase. |
| **Preventing event leakage** | No regression versus today: since there is no tenant boundary anywhere in the current system, there is nothing to "leak" beyond what any authenticated user already sees via existing GET endpoints. If role-gated fields are ever added to `QueueRead`, the event `data` builder must mirror the same Pydantic schema used for REST responses rather than duplicating field-visibility logic ad hoc. |
| **Denial-of-service considerations** | (1) Unauthenticated requests are rejected by `CurrentUser` before any broadcaster subscription is opened. (2) **SSE connection cap is not shipped in A.2** (post-A.2 improvement). (3) Heartbeats keep idle connections from being dropped by proxies. (4) General API rate limiting remains a documented project-wide gap (`10-production-readiness.md` §9.5). |

---

## 11. API Impact

| Category | Endpoints |
| --- | --- |
| **New** | `GET /api/v1/queues/stream` (SSE) |
| **Modified (behavior only, no schema/contract change)** | None of `QueueRead`, `PublishQueueResponse`, `QueuePublishAttemptListResponse`/`QueuePublishAttemptRead`, or any request schema changes shape. `QueueService.update`/`delete` and `TelegramPublishingService`'s commit points gain an internal side effect (event emission) that is invisible to REST callers. |
| **Unchanged** | `POST /queues`, `GET /queues`, `GET /queues/{id}`, `PATCH /queues/{id}`, `DELETE /queues/{id}`, `GET /queues/{id}/attempts`, `POST /queues/{id}/publish`, `GET /dashboard`, all auth/products/channels/discovery/AI-content endpoints. |

---

## 12. Frontend Impact (as shipped)

| File | Status |
| --- | --- |
| `frontend/src/features/queue/lib/sse-client.ts` | **Shipped.** Fetch-based reconnecting SSE client; vendored MIT parsing core from `@microsoft/fetch-event-source` (not an npm dependency; not hand-rolled). Wrapper owns Bearer auth, backoff+jitter, `Last-Event-ID`, AbortController, fatal 401/403. |
| `frontend/src/features/queue/lib/queue-event-invalidation.ts` | **Shipped.** Event → query-key mapping + 300ms debounced invalidator. |
| `frontend/src/features/queue/lib/queue-polling.ts` | **Shipped.** Adaptive `refetchInterval` selector (5s → 30s). |
| `frontend/src/features/queue/hooks/useQueueEventStream.ts` | **Shipped.** Status: `connecting` \| `connected` \| `disconnected` \| `error`. |
| `frontend/src/features/queue/hooks/useQueueRealtimeInvalidation.ts` | **Shipped.** Debounced invalidation + reconnect refresh + `pollingEnabled`. |
| `frontend/src/features/queue/hooks/QueueRealtimePollingContext.tsx` | **Shipped.** Provides polling flag to `useQueue` / attempts queries. |
| `frontend/src/features/queue/components/QueueView.tsx` | **Shipped.** Mounts realtime once; polling context provider; drawer close on remote delete. |
| `frontend/src/features/queue/components/QueueRealtimeStatusBadge.tsx` | **Shipped (F4).** Informational Arabic status badge in toolbar. |
| `frontend/src/features/queue/components/QueueToolbar.tsx` | **Shipped.** Optional `actions` slot for the badge. |
| `frontend/src/features/queue/hooks/useQueue.ts` | **Shipped (additive).** `refetchInterval` when polling context is true. |
| `frontend/src/services/api-client.ts` | **Unchanged in A.2.** Shared Axios 401 clear/redirect extraction was deferred (post-A.2). |
| `QueueTable` / `QueueDetailsDrawer` / `QueueHealthBadge` / `QueueOperationalStats` | **Unchanged contracts.** Continue reading TanStack Query cache; push/polling only change *when* refetch happens. |

---

## 13. Backend Impact (as shipped)

| File | Status |
| --- | --- |
| `app/events/schemas.py` | **Shipped.** Versioned envelope + per-event data models. |
| `app/events/publisher.py` | **Shipped.** `EventPublisher` + `NullEventPublisher`. |
| `app/events/consumer.py` | **Shipped.** Redis Pub/Sub consumer with reconnect. |
| `app/events/broadcaster.py` | **Shipped.** Process-local fan-out. |
| `app/events/deps.py` | **Shipped.** Broadcaster singleton + publisher factories. |
| `app/api/v1/queue_stream.py` | **Shipped.** Authenticated SSE; heartbeat 30s; per-client queue max 64; `X-Accel-Buffering: no`. |
| `app/api/v1/router.py` | **Shipped.** Stream router under `/queues`. |
| `app/main.py` | **Shipped.** Lifespan starts/stops consumer + event Redis client; streaming-safe security middleware. |
| `app/services/queue.py` | **Shipped.** Emission after commit at the six call sites; optional `events` (default `NullEventPublisher`). |
| `app/api/deps.py` | **Shipped.** `get_queue_service` injects production publisher. |
| `app/worker/tasks/publishing.py` | **Shipped.** Per-task `create_event_publisher`. |
| `app/core/config.py` | **No dedicated `sse_*` settings shipped in A.2** (hardcoded heartbeat/channel defaults). Config/cap remain post-A.2. |
| Repositories / models / schemas / Alembic / auth | **Unchanged.** |

---

## 14. Risks and Mitigations

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | Native `EventSource` cannot send the `Authorization` header used by this app's JWT model, so a naive implementation would break auth or force a token into the URL (logged in access/proxy logs). | Use a fetch-based SSE client (§6) that sends the header exactly like Axios does. No token ever appears in a URL or query string. |
| 2 | Reverse proxies (e.g., Nginx) buffer responses by default, which silently breaks streaming in production even though it works locally. | Explicit `X-Accel-Buffering: no` response header (§4); add a staging verification step to `10-production-readiness.md` before relying on live updates in any environment with a proxy in front of the API. |
| 3 | An event could be published for a change that is later rolled back if emission happens before/inside an uncommitted transaction. | Hard rule enforced at every call site: publish only immediately after a successful `session.commit()` (§5), matching the discipline already present in the codebase's own comments. Add this as an explicit acceptance-criterion/code-review checkpoint for every implementation task in §15. |
| 4 | Multiple API replicas each holding many Redis `SUBSCRIBE`s could add Redis load. | **Mitigated as shipped:** one `EventConsumer` subscription per API process + in-process `EventBroadcaster` fan-out to SSE clients. |
| 5 | A large batch publish (50 items × up to 3 events) could cause a client-side refetch storm if every event triggers an immediate, unbatched invalidation. | Client-side debounce (~300ms) coalesces bursts into a single refetch per affected query (§6); TanStack Query also de-dupes concurrent identical in-flight requests. |
| 6 | Redis Pub/Sub has no replay; a client disconnected for even a few seconds cannot receive events published during that gap. | Accepted trade-off (§8) because the client always does one full `invalidateQueries` immediately on reconnect, guaranteeing eventual correctness from the database, which remains the source of truth. If exact event replay is ever required, migrating to Redis Streams (`XADD`/`XREAD`) is a compatible future upgrade — not built now. |
| 7 | Hand-rolling an SSE parser from scratch risks subtle wire-format bugs (chunk-boundary UTF-8 decoding, line-ending handling, multi-line `data:` joining); adding `@microsoft/fetch-event-source` as a live npm dependency means depending on a package with no recent maintenance activity. | Neither: **vendor** (copy and adapt) the package's small, self-contained, MIT-licensed parsing core directly into `sse-client.ts` (§6, §12). This gets the proven, spec-compliant parsing logic without an ongoing external dependency on an inactive repository. The vendored code is scoped to parsing only — our own wrapper still owns auth, reconnect, backoff, and cleanup. It is kept fully isolated behind `sse-client.ts`'s module boundary so it can be swapped for a different implementation later without touching any consumer of `useQueueEventStream`. |
| 8 | Access tokens expire in 30 minutes by default and there is no refresh-token flow (documented gap); long-lived SSE connections eventually 401. | Stream treats 401/403 as fatal (stops reconnect). Unifying with Axios `session.clear`/redirect is a post-A.2 improvement; REST expiry UX is unchanged. |
| 9 | Emitting `queue.attempt_*` events even for guard-suppressed idempotent retries would cause UI churn for a "nothing actually happened" case. | Only emit from call sites that already write/update an attempt row. The idempotency-guard-suppressed path in `_claim_publish` raises `ConflictError` **before** any attempt row is created — no event is emitted there, matching the fact that no new attempt exists to report. |

---

## 15. Task Breakdown — Final Completion Status

Implementation task labels below reflect the **shipped** B1–B7 / F1–F5 sequence (evolved slightly from the original draft numbering during implementation). Early draft wording is historical; status is authoritative.

### Backend

| Task | Scope (as shipped) | Final status |
| ---- | ------------------ | ------------ |
| B1 | Event payload schemas (`app/events/schemas.py`) | COMPLETE |
| B2 | `EventPublisher` / `NullEventPublisher` | COMPLETE |
| B3 | Domain/service event emission after commit | COMPLETE |
| B4 | Redis `EventConsumer` + in-process `EventBroadcaster` | COMPLETE |
| B5 | Authenticated SSE endpoint `GET /queues/stream` | COMPLETE |
| B6 | Consumer lifecycle wiring (FastAPI lifespan) | COMPLETE |
| B7 | Production publisher wiring (API deps + Celery) | COMPLETE |

### Frontend

| Task | Scope (as shipped) | Final status |
| ---- | ------------------ | ------------ |
| F1 | SSE client foundation (`sse-client.ts`, vendored parser) | COMPLETE |
| F2 | Realtime invalidation (`queue-event-invalidation` + hook) | COMPLETE |
| F3 | Live Queue UI wiring (`QueueView`, table/stats/drawer via refetch) | COMPLETE |
| F4 | Realtime status/recovery UX (`QueueRealtimeStatusBadge`) | COMPLETE |
| F5 | Reliability hardening (StrictMode, abort, late-event, reconnect refresh rules) + polling fallback integration | COMPLETE |
| F6 | Extra live/polling indicator beyond F4 | **Optional / Stretch — not required for A.2 completion** |

F4 already provides `connecting` / `connected` / `disconnected` / `error` with accessible Arabic labels and does not gate Queue actions. F6 is **not** required to mark Phase A.2 complete and was not implemented as a separate deliverable.

There is no dashboard-specific backend or frontend task. Queue KPI cards refresh from `queue.*` invalidations client-side. No `dashboard.stats_updated`.

---

## 16. Explicit Non-Goals (Guardrails)

To keep future work scoped correctly:

- Do **not** add workspace/tenant filtering to events or the stream endpoint — the REST API doesn't have it either (§10).
- Do **not** replace any existing REST endpoint or change any existing response schema.
- Do **not** introduce client-side computation of `failure_reason`/`retry_count`/any attempt-derived field from event payloads — always refetch via `invalidateQueries` (§6).
- Do **not** add a message broker beyond Redis Pub/Sub, a persistent event log, or Redis Streams for this phase (§8, §14 Risk 6).
- Do **not** use native `EventSource` — incompatible with Bearer-token auth (§6).
- Do **not** implement optimistic UI updates driven by these events.
- Do **not** implement the SSE frame parser from scratch, and do **not** add `@microsoft/fetch-event-source` as a runtime dependency — vendor its minimal parsing core into `sse-client.ts` (§6, §12, F1).
- Do **not** add a `dashboard.stats_updated` event — Queue KPI cards refresh from existing `queue.*` invalidations (§2). `DashboardView` live updates remain out of scope; if added later, do it client-side only.

---

## 17. Related Documents

- [08-implementation-roadmap.md](../08-implementation-roadmap.md) — Phase A.2 marked COMPLETE.
- [06-api-integration.md](../06-api-integration.md) — REST + SSE stream contract notes.
- [02-frontend-architecture.md](../02-frontend-architecture.md) — Feature-folder conventions.
- [10-production-readiness.md](../10-production-readiness.md) — Infra checklist including SSE proxy buffering.
- [11-workspace-design-system.md](../frontend/11-workspace-design-system.md) — Queue workspace template.

---

## 18. Post-A.2 Improvements

These items were identified during the final audit. They are **future improvements, not A.2 blockers**, and are **not** acceptance criteria for Phase A.2:

- Reduce SSE heartbeat from 30s to 15s (or make it a settings value).
- Optionally switch stream event IDs from UUID4 to ULID if stronger time-sortability is desired.
- Add a per-process SSE connection cap (`503` when exceeded) and optional `sse_*` settings.
- Unify SSE 401 handling with the shared Axios `session.clear` + login redirect helper.
- Staging verification that reverse proxies honor `X-Accel-Buffering: no` / disable response buffering for `/api/v1/queues/stream`.
- Optional F6-style indicator refinements beyond the shipped F4 badge (only if product wants a distinct “polling” chrome — not required).

---

*Phase A.2 closeout: 2026-08-08. Implementation complete (B1–B7, F1–F5, polling fallback, clean-clone shippability). Adopted into `08-implementation-roadmap.md`.*
