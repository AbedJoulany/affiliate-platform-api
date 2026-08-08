# Phase A.2 — Real-time Operations: Technical Design

**Status:** Draft — for review. Not yet adopted into `08-implementation-roadmap.md`.
**Author role:** Senior Staff Backend Architect / Technical Design Review
**Date:** 2026-08-07
**Depends on:** Phase A.1 (Publishing Reliability Foundation) — complete
**Scope authority:** `docs/08-implementation-roadmap.md` §3 "Phase A.2 — Real-time operations"

This is a design document only. No code, migrations, or configuration were changed while producing it. All file/module references below are read-only observations of the current codebase used to ground the design.

**Revision (2026-08-07):** Incorporated two architectural decisions following design review: (1) the SSE client parsing core is **vendored** from `@microsoft/fetch-event-source` rather than hand-rolled or added as a live npm dependency — see §6, §12, §14 Risk 7, §15 Task F1; (2) the dedicated `dashboard.stats_updated` event is **removed** — Queue workspace KPI cards already refresh from the existing `queue.*` → `queueKey` invalidation, and Dashboard-page live updates are out of scope for Phase A.2 — see §2, §6, §9, §15, §16.

---

## 0. Executive Summary

Phase A.2 adds a **push notification layer on top of the existing REST API** — it does not change how data is written, validated, or stored. The database (via the Phase A.1 `queue_publish_attempts` table and `QueueItem.status`) remains the single source of truth. Real-time delivery is an **enhancement layer**: if it fails entirely, the app must behave exactly as it does today (poll-on-mutation + manual refresh).

**Recommendation in one line:** Server-Sent Events (SSE) over a new `GET /api/v1/queues/stream` endpoint, backed by Redis Pub/Sub (already-present infrastructure), consumed on the frontend via a fetch-based SSE client built on a **vendored** parsing core (not the native `EventSource`, because it cannot carry the existing Bearer JWT; not a live dependency on `@microsoft/fetch-event-source`, because that package is unmaintained — see §6), driving **TanStack Query cache invalidation** (never manual cache mutation), with an automatic polling fallback that reuses the backoff pattern already established in `app/telegram/publisher.py`.

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
| `id` | `str` | ULID (time-sortable, unlike UUID4) generated at publish time. Used as the SSE `id:` field for `Last-Event-ID` support (see §8). Not a database primary key — purely a stream cursor. |
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
| **Connection lifecycle** | `StreamingResponse(generator(), media_type="text/event-stream")`. Response headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no` (disables Nginx proxy buffering — **must be verified in any reverse-proxy config**, flagged as a `10-production-readiness.md` follow-up). The generator: (1) subscribes to the Redis channel, (2) loops emitting any published message as an SSE frame, (3) checks `await request.is_disconnected()` on each idle tick to detect client-side closure. |
| **Heartbeat** | Every 15s, emit an SSE **comment** line (`: heartbeat\n\n`) if no real event was sent in that window. Comments are ignored by SSE parsers' `onmessage`/event dispatch but keep intermediary proxies/load balancers from treating the connection as idle (typical LB idle timeouts are 60s+; 15s gives comfortable margin). |
| **Disconnect behavior** | On client disconnect (detected via `is_disconnected()` or a broken pipe on write), the generator exits its loop. |
| **Cleanup strategy** | `try/finally` around the subscribe loop: `finally` always unsubscribes from the Redis channel and closes the Redis connection, regardless of whether the generator exited via disconnect, exception, or (in future) server shutdown. No connection-tracking singleton is needed server-side beyond this per-request Redis subscription — see §5 for why. |

---

## 5. Backend Architecture

### Where connections are managed

**Nowhere centrally.** Each open `GET /queues/stream` request is an independent async generator holding its own Redis Pub/Sub subscription for its lifetime. There is intentionally **no in-process `ConnectionManager`/registry class** — Redis Pub/Sub already performs the fan-out (one `PUBLISH` reaches every `SUBSCRIBE`ing process), so a custom in-memory broadcaster would be a redundant abstraction layered on top of infrastructure that already solves the problem. This directly satisfies the "avoid unnecessary abstractions" constraint.

### How events are published — a minimal `EventPublisher`

Add `app/events/publisher.py` with a small class:

- Wraps a `redis.asyncio` client's `PUBLISH` call to **one** fixed channel name (e.g. `queue-events`) — not one channel per event type. The `event` field inside the JSON envelope is the discriminator; the SSE endpoint relays every message on the channel and lets the client filter/dispatch by `event`.
- A `NullEventPublisher` (no-op) variant exists for tests and for any environment without Redis configured, so event emission is never a hard dependency for core CRUD to function — if Redis is briefly unavailable, publishing a queue item or running a Telegram publish must still succeed; only the live-update signal is lost (fallback polling covers this, see §7).

### How services emit events

Every emission call site is a place that **already commits today**:

| Service method | Existing commit | New: emit after commit |
| --- | --- | --- |
| `QueueService.update` | `queue_repo.update(item)` (commit happens in repository/session flow) | `queue.status_changed` (only if `status` actually changed) |
| `QueueService.delete` | `queue_repo.delete(item)` | `queue.deleted` |
| `TelegramPublishingService._claim_publish` | `await self.session.commit()` | `queue.attempt_started` |
| `TelegramPublishingService.publish_queue_item` (success branch) | `await self.session.commit()` | `queue.status_changed` + `queue.attempt_succeeded` |
| `TelegramPublishingService._claim_publish` (status-heal branch) | `await self.session.commit()` | `queue.status_changed` |
| `TelegramPublishingService._mark_attempt_failed` | `await self.session.commit()` | `queue.attempt_failed` |

`EventPublisher` is injected into `QueueService`/`TelegramPublishingService` constructors as an optional parameter (default: a real Redis-backed instance), the same dependency-injection shape these services already use for repositories. This keeps emission testable (inject a fake/spy publisher in unit tests) without touching call sites in `app/api/v1/queues.py` beyond passing the dependency through.

**Hard rule:** publish only ever happens *after* a successful commit, never before, and never inside a `try` block that could still roll back. This mirrors the discipline already visible in the codebase (see the existing comment `# Commit success before returning so a later sibling failure...` in `app/services/queue.py`).

### Does an event bus need to exist?

Yes, but the smallest possible one: `EventPublisher` (write side, described above) and the SSE endpoint's Redis subscriber (read side). There is no message broker beyond Redis Pub/Sub, no Kafka/RabbitMQ topic design, no persistent event log. This is intentionally minimal — Redis Pub/Sub is fire-and-forget with no history, which is an accepted trade-off (see §8, "no replay").

### How Celery workers communicate with SSE

Celery tasks (`app/worker/tasks/publishing.py`) run in a **separate OS process** from the FastAPI/Uvicorn process(es) holding open SSE connections (confirmed by the existing `run_async`/`dispose_async_engine` pattern, which exists precisely because Celery tasks get their own event loop per invocation). The bridge is Redis itself:

```
Celery task (TelegramPublishingService, same code as manual path)
        │  commits attempt/status change
        ▼
EventPublisher.publish() → Redis PUBLISH "queue-events" <json>
        │
        ▼  (fan-out, Redis-native)
Any FastAPI/Uvicorn process(es) with open GET /queues/stream connections
        │  each has its own SUBSCRIBE "queue-events"
        ▼
Browser clients (SSE frames)
```

Because `TelegramPublishingService` is the **same class** used by both the manual `POST /queues/{id}/publish` route and the Celery tasks (`process_publish_queue`, `publish_queue_item_task`), instrumenting it once in §5's table automatically covers both triggers — no duplicated emission logic in the Celery task functions themselves. The Celery task path constructs its own short-lived `EventPublisher`/Redis client per task invocation, mirroring the existing per-task session-maker pattern in `app/worker/async_utils.py`.

---

## 6. Frontend Architecture

### Subscription hook

New `useQueueEventStream()` in `frontend/src/features/queue/hooks/` (or `useQueueLiveSync` — naming TBD at implementation time), built on top of `frontend/src/features/queue/lib/sse-client.ts`. Responsibilities:

1. Open a **fetch-based** SSE connection (not native `EventSource`), sending `Authorization: Bearer <jwt>` exactly like `services/api-client.ts` does for every other request. Native `EventSource` cannot set custom headers, and this project's JWT lives in `sessionStorage` behind an Axios interceptor (not an `httpOnly` cookie), so `EventSource` is architecturally incompatible with the existing auth model without inventing a new token-in-URL mechanism — which the design explicitly avoids (see Risk table, §14).
2. **Frame parsing is delegated to a vendored parser, not implemented from scratch.** `sse-client.ts` copies and adapts the minimal, MIT-licensed SSE wire-format parsing logic from `@microsoft/fetch-event-source` (attribution comment retained) rather than (a) hand-writing a byte/line parser from first principles, or (b) adding `@microsoft/fetch-event-source` as a live npm dependency. Rationale:
   - Correctness: spec-compliant SSE parsing has several non-obvious pitfalls — UTF-8 decoding across chunk boundaries (relevant here given the app's Arabic-heavy content), `\n`/`\r\n`/`\r` line-ending handling, multi-line `data:` field joining, and comment-line (`: heartbeat`) skipping without disturbing in-progress event buffering. Getting any of these subtly wrong produces intermittent, hard-to-reproduce dropped/garbled events in production rather than a clean failure — a bad category of bug to author from scratch when a proven, spec-compliant reference implementation already exists.
   - Dependency posture: `@microsoft/fetch-event-source` (latest release `2.0.1`, April 2021; zero commits/issue activity in the last 90 days) is functionally stable — the SSE spec it implements hasn't changed — but is not actively maintained, and has zero runtime dependencies of its own. Rather than taking on a dormant package in `package.json`, its small, self-contained parsing core is copied directly into `sse-client.ts`. This keeps the proven, battle-tested logic (it is the de facto standard for this exact problem, at ~2.9M weekly npm downloads) without an ongoing external dependency on an inactive repository.
   - **The vendored code is responsible for SSE wire-format parsing only.** Everything else in this design remains our own code, layered on top in `sse-client.ts`: the `Authorization` header, the reconnect strategy, exponential backoff with jitter (§7), `Last-Event-ID` handling (§8), `AbortController`-based cleanup, and `401` handling (§8, via the shared helper from Task F5).
   - The vendored parser is isolated entirely behind `sse-client.ts`'s module boundary — no other file (`useQueueEventStream`, `QueueView`, etc.) depends on its internals, so it can be swapped for a different implementation later (e.g., if the underlying reference implementation is ever superseded) without touching any consumer.
3. Track connection `status`: `'connecting' | 'live' | 'reconnecting' | 'polling'`.
4. Dispatch each parsed event to a small set of TanStack Query cache actions (below) — **not** to component state or a new client store.

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

`QueueView` mounts `useQueueEventStream()` once (workspace-scoped, matching how `useQueue`/`useQueuePublishingOperations` are already composed there). Not mounted in `AppShell`/`providers.tsx` globally — Phase A.2's roadmap scope is the queue workspace.

**`DashboardView` live updates are out of scope for Phase A.2.** The Queue workspace's own KPI cards (`QueueOperationalStats`) already update live "for free" the moment `queue.*` events invalidate `queueKey` (§2), because those cards are computed client-side from the same `useQueue()` list query — no dashboard-specific event or backend logic is required for that. The separate `/dashboard` route's own aggregate (`GET /dashboard` → `DashboardOverview`) is a different page and is not named in the roadmap's Phase A.2 scope; it keeps its current fetch-on-mount/focus behavior. If live updates for that page are wanted in a future phase, the lightweight extension is: mount the same `useQueueEventStream()` hook on `DashboardView` and, on the client side, invalidate `['dashboard']` for any `queue.*` event received — no new backend event, channel, or emission logic required. This is documented as a non-goal for this phase in §16.

---

## 7. Polling Fallback

| Aspect | Design |
| --- | --- |
| **When it starts** | (a) Initial SSE connection fails to establish within 5s, or (b) an established connection drops and reconnection attempts are exhausted (see below), or (c) the browser/runtime cannot support the fetch+stream approach at all (rare). |
| **Reconnect backoff (before falling back)** | Exponential with jitter, matching the existing pattern in `app/telegram/publisher.py` (`TELEGRAM_BASE_BACKOFF_SECONDS` + jitter): attempts at 1s, 2s, 4s, 8s, 16s, capped at 30s. After 5 consecutive failures (~1 minute elapsed), switch to polling mode rather than continuing to retry at the cap indefinitely in the foreground. |
| **Polling behavior once active** | Enable TanStack Query `refetchInterval` on the `useQueue` list query (and the open attempts query, if any) starting at 5s, backing off to 30s if repeated polls return unchanged data — this reuses the exact cadence the roadmap already specified ("polling with exponential backoff… 5s → 30s"). |
| **Continued reconnect attempts while polling** | A low-frequency background retry (every 30–60s) keeps attempting to re-establish the SSE connection without blocking or interfering with the active polling. |
| **Returning to SSE** | On a successful reconnect: (1) immediately fire one `invalidateQueries` for all queue-related keys to close any gap that occurred while disconnected, (2) disable `refetchInterval`, (3) resume push-driven invalidation as the primary update mechanism. |

---

## 8. Failure Handling

| Scenario | Behavior |
| --- | --- |
| **Lost connection** | Detected by the fetch stream erroring/closing; triggers the reconnect-then-poll sequence in §7. A small, non-blocking UI indicator (extending the existing `refreshing` prop already passed into `QueueToolbar`, not a new component) reflects "live" vs. "refreshing periodically." |
| **Reconnect** | Uses the SSE `id:` field (the ULID from §3) as `Last-Event-ID`, sent back by the client on reconnect — captured for forward-compatibility, but see next row for the actual guarantee. |
| **No event replay (accepted limitation)** | Redis Pub/Sub has no history/replay buffer, so a client that reconnects **cannot** actually receive events it missed while disconnected, even though it sends `Last-Event-ID`. This is explicitly accepted: because the database remains the source of truth and every reconnect triggers one immediate `invalidateQueries` (§7), the client is guaranteed to be correct after reconnect — it just doesn't get a blow-by-blow replay of what it missed. Building true replay (e.g., switching to Redis Streams with `XADD`/`XREAD`) is called out as a possible **future** enhancement, not required for Phase A.2 (see §14, Risk 6). |
| **Duplicate events** | Safe by construction: because the client only ever treats an event as "invalidate and refetch," receiving the same event twice produces the same (idempotent) refetch, not a double-applied state change. |
| **Out-of-order events** | Also safe by construction for the same reason — the client never applies event payload deltas to its own state; it always re-reads current truth from the REST API. |
| **Browser refresh** | No special handling needed: TanStack Query's normal query-on-mount plus `useQueueEventStream`'s connect-on-mount re-establish full state and the live connection from scratch. |
| **Expired authentication** | The SSE fetch will receive a `401` like any other API call. Because this request does not go through the shared Axios instance, `useQueueEventStream`'s error handling must call the **same** session-clear/redirect logic that `services/api-client.ts`'s response interceptor already runs on 401 — this requires extracting that logic into a small shared function both call (a refactor of ~10 lines, not a redesign; listed as Task F5 in §15). Until refresh tokens exist (already a documented gap in `10-production-readiness.md`), users will need to re-authenticate roughly every `access_token_expire_minutes` (30 min default) and the stream reconnects fresh after login — this matches, and does not worsen, today's existing session-expiry UX. |

---

## 9. Performance

| Aspect | Assessment |
| --- | --- |
| **Expected simultaneous connections** | This is an internal operator tool (admin/affiliate roles), not a public consumer product. Expect **low tens** of concurrent SSE connections in production, not thousands. Nothing in this design requires a specialized connection-sharding architecture at this scale. |
| **Memory considerations** | Each open SSE connection costs one async generator frame + one Redis Pub/Sub subscription object on the FastAPI side (a few KB each). At tens of connections this is negligible. If connection count ever grows by an order of magnitude, the mitigation is a per-process shared subscription fanned out in-memory to many client generators (avoiding N separate `SUBSCRIBE`s to Redis) — explicitly **not needed for Phase A.2**, documented as a future optimization threshold. |
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
| **Denial-of-service considerations** | (1) Unauthenticated requests are rejected by the `CurrentUser` dependency before any Redis subscription is opened — cheap rejection, no resource cost. (2) Add a simple per-process connection cap (new setting, e.g. `sse_max_connections_per_worker`, default 500) that returns `503` once exceeded, protecting against file-descriptor exhaustion from a buggy/malicious client opening many connections. (3) Heartbeats (§4) prevent idle-connection accumulation past proxy timeouts but do not limit legitimate-looking connection floods — the cap in (2) is the actual mitigation. (4) General API rate limiting is already a documented gap (`10-production-readiness.md` §9.5); this design does not build a bespoke limiter just for this endpoint — when generic rate-limiting middleware is added project-wide, it should cover this route too. |

---

## 11. API Impact

| Category | Endpoints |
| --- | --- |
| **New** | `GET /api/v1/queues/stream` (SSE) |
| **Modified (behavior only, no schema/contract change)** | None of `QueueRead`, `PublishQueueResponse`, `QueuePublishAttemptListResponse`/`QueuePublishAttemptRead`, or any request schema changes shape. `QueueService.update`/`delete` and `TelegramPublishingService`'s commit points gain an internal side effect (event emission) that is invisible to REST callers. |
| **Unchanged** | `POST /queues`, `GET /queues`, `GET /queues/{id}`, `PATCH /queues/{id}`, `DELETE /queues/{id}`, `GET /queues/{id}/attempts`, `POST /queues/{id}/publish`, `GET /dashboard`, all auth/products/channels/discovery/AI-content endpoints. |

---

## 12. Frontend Impact

| File | Change |
| --- | --- |
| `frontend/src/features/queue/lib/sse-client.ts` **(new)** | Fetch-based reconnecting SSE client. Vendors (copies and adapts) the minimal MIT-licensed frame-parsing core from `@microsoft/fetch-event-source` — **not** added as a runtime dependency in `package.json`, and **not** hand-rolled from scratch (see §6). Our own wrapper code around that vendored core owns: `Authorization` header, reconnect strategy, exponential backoff with jitter, `Last-Event-ID` handling, `AbortController`-based cleanup, and `401` handling. The parser is isolated behind this file's module boundary for easy future replacement. |
| `frontend/src/features/queue/hooks/useQueueEventStream.ts` **(new)** | Wraps the client above; exposes connection `status`; dispatches parsed events to debounced `invalidateQueries` calls per §6. |
| `frontend/src/features/queue/components/QueueView.tsx` **(modified)** | Mounts `useQueueEventStream()`; optionally threads `status` down to `QueueToolbar` for the live/polling indicator. |
| `frontend/src/features/queue/hooks/useQueue.ts` **(modified, additive)** | May export the debounce helper / `queueKey`-adjacent invalidation function for reuse by the new hook — no changes to existing exported hooks' behavior. |
| `frontend/src/services/api-client.ts` **(modified, extraction only)** | Extract the existing inline 401 session-clear/redirect logic (lines in the response interceptor) into a small exported function so `sse-client.ts` can call the identical logic — no behavior change for existing Axios-based calls. |
| `frontend/src/features/queue/components/QueueToolbar.tsx` **(modified, optional/stretch)** | Reuse the existing `refreshing` prop pattern to reflect "live" vs. "polling" using the existing `Badge` primitive — no new component. |
| `frontend/src/features/queue/components/QueueTable.tsx`, `QueueDetailsDrawer.tsx`, `QueueHealthBadge.tsx`, `QueueOperationalStats.tsx` | **Unchanged.** They continue reading from the TanStack Query cache exactly as today; the only difference is *what triggers* a refetch (push instead of only mutation-triggered). |

---

## 13. Backend Impact

| File | Change |
| --- | --- |
| `app/events/schemas.py` **(new)** | Versioned Pydantic envelope + one `data` model per event type from §2. |
| `app/events/publisher.py` **(new)** | `EventPublisher` (Redis `PUBLISH` wrapper) + `NullEventPublisher` (no-op, for tests / Redis-unavailable environments). |
| `app/api/v1/queue_stream.py` **(new)** | `GET /queues/stream` SSE route: subscribes to the Redis channel, relays as SSE frames, heartbeat, disconnect cleanup, connection cap. |
| `app/api/v1/router.py` **(modified)** | Register the new stream router alongside the existing `queues` router. |
| `app/services/queue.py` **(modified)** | `QueueService.__init__`/`TelegramPublishingService.__init__` accept an optional `EventPublisher` (default: real instance). Emit calls added at the six commit points listed in §5's table. |
| `app/api/v1/queues.py` **(modified, small)** | Thread the publisher dependency through to `QueueService(db, events=...)` construction (mirrors how `db` is already injected). |
| `app/worker/tasks/publishing.py` **(modified, small)** | Construct a per-task `EventPublisher`/Redis client (mirrors the existing per-task resource pattern in `app/worker/async_utils.py`) and pass it into `TelegramPublishingService`. |
| `app/core/config.py` **(modified, additive settings)** | `sse_heartbeat_seconds` (default 15), `sse_max_connections_per_worker` (default 500), `event_stream_channel_name` (default `"queue-events"`). |
| `app/repositories/queue.py`, `app/models/queue.py`, `app/schemas/queue.py`, Alembic migrations, `app/telegram/publisher.py`, `app/core/database.py`, `app/auth/*` | **Unchanged.** No schema/table changes — this is a pure streaming/event layer on top of existing data. |

---

## 14. Risks and Mitigations

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | Native `EventSource` cannot send the `Authorization` header used by this app's JWT model, so a naive implementation would break auth or force a token into the URL (logged in access/proxy logs). | Use a fetch-based SSE client (§6) that sends the header exactly like Axios does. No token ever appears in a URL or query string. |
| 2 | Reverse proxies (e.g., Nginx) buffer responses by default, which silently breaks streaming in production even though it works locally. | Explicit `X-Accel-Buffering: no` response header (§4); add a staging verification step to `10-production-readiness.md` before relying on live updates in any environment with a proxy in front of the API. |
| 3 | An event could be published for a change that is later rolled back if emission happens before/inside an uncommitted transaction. | Hard rule enforced at every call site: publish only immediately after a successful `session.commit()` (§5), matching the discipline already present in the codebase's own comments. Add this as an explicit acceptance-criterion/code-review checkpoint for every implementation task in §15. |
| 4 | Multiple API replicas each holding their own Redis `SUBSCRIBE` per open SSE connection could add Redis load if connection counts grow very large. | Acceptable at current scale (§9). Documented as a future optimization (shared in-process fan-out) if connections grow ~10x; not built now (avoid speculative complexity). |
| 5 | A large batch publish (50 items × up to 3 events) could cause a client-side refetch storm if every event triggers an immediate, unbatched invalidation. | Client-side debounce (~300ms) coalesces bursts into a single refetch per affected query (§6); TanStack Query also de-dupes concurrent identical in-flight requests. |
| 6 | Redis Pub/Sub has no replay; a client disconnected for even a few seconds cannot receive events published during that gap. | Accepted trade-off (§8) because the client always does one full `invalidateQueries` immediately on reconnect, guaranteeing eventual correctness from the database, which remains the source of truth. If exact event replay is ever required, migrating to Redis Streams (`XADD`/`XREAD`) is a compatible future upgrade — not built now. |
| 7 | Hand-rolling an SSE parser from scratch risks subtle wire-format bugs (chunk-boundary UTF-8 decoding, line-ending handling, multi-line `data:` joining); adding `@microsoft/fetch-event-source` as a live npm dependency means depending on a package with no recent maintenance activity. | Neither: **vendor** (copy and adapt) the package's small, self-contained, MIT-licensed parsing core directly into `sse-client.ts` (§6, §12). This gets the proven, spec-compliant parsing logic without an ongoing external dependency on an inactive repository. The vendored code is scoped to parsing only — our own wrapper still owns auth, reconnect, backoff, and cleanup. It is kept fully isolated behind `sse-client.ts`'s module boundary so it can be swapped for a different implementation later without touching any consumer of `useQueueEventStream`. |
| 8 | Access tokens expire in 30 minutes by default and there is no refresh-token flow (documented gap); most long-lived SSE connections will eventually 401. | Reuse the exact session-expiry UX that already exists today (§8) — clear session, redirect to login, reconnect fresh after re-auth. This design does not attempt to solve the pre-existing refresh-token gap; it only ensures the stream fails the same way the rest of the app already does. |
| 9 | Emitting `queue.attempt_*` events even for guard-suppressed idempotent retries would cause UI churn for a "nothing actually happened" case. | Only emit from call sites that already write/update an attempt row. The idempotency-guard-suppressed path in `_claim_publish` raises `ConflictError` **before** any attempt row is created — no event is emitted there, matching the fact that no new attempt exists to report. |

---

## 15. Task Breakdown for Cursor Sessions

Each task below is scoped to one file or one tightly-related file group, has a single responsibility, and is independently testable without requiring the later tasks to exist (later tasks build on earlier ones, but earlier ones are valid and mergeable on their own).

### Backend

1. **B1 — Event payload schemas.** Add `app/events/schemas.py`: the versioned envelope model and one `data` model per event type in §2. No emission or transport logic. *Acceptance:* models `model_validate`/`model_dump` round-trip correctly in a unit test; no other file is touched.
2. **B2 — Event publisher.** Add `app/events/publisher.py`: `EventPublisher` (wraps `redis.asyncio` `PUBLISH` to one configurable channel) and `NullEventPublisher`. No service wiring yet. *Acceptance:* unit test with a fake Redis client asserts `publish()` is called with the expected channel and JSON body.
3. **B3 — SSE endpoint (no producers yet).** Add `app/api/v1/queue_stream.py` (`GET /queues/stream`): subscribes to the Redis channel, relays messages as SSE frames, heartbeat every `sse_heartbeat_seconds`, disconnect-cleanup, connection cap; register in `app/api/v1/router.py`. Testable by manually publishing a message (e.g., via a test fixture calling `redis.publish` directly) and asserting the test client receives an SSE frame. *Acceptance:* manual publish → visible frame; connection closes cleanly and unsubscribes on client disconnect; a request beyond the connection cap gets `503`.
4. **B4 — Wire `queue.status_changed` / `queue.deleted`.** Add optional `EventPublisher` param to `QueueService.__init__`; emit after `update`'s status-changing commits and after `delete`'s commit. *Acceptance:* existing queue CRUD tests pass unchanged; new tests (with an injected fake publisher) assert the right event/payload fires exactly once per status change and per delete, and does not fire when `update` doesn't change `status`.
5. **B5 — Wire attempt events.** Add the same optional `EventPublisher` param to `TelegramPublishingService.__init__`; emit `queue.attempt_started` in `_claim_publish`, `queue.attempt_succeeded` + `queue.status_changed` in the `publish_queue_item` success branch, `queue.attempt_failed` in `_mark_attempt_failed`, and `queue.status_changed` in the status-heal branch. *Acceptance:* all existing `tests/test_queue_publishing_service.py` cases pass unmodified in outcome; new tests assert correct emission (and non-emission on guard-suppression) for: success, transient failure, terminal/dead-letter failure, status-heal-on-409.
6. **B6 — Celery task wiring.** In `app/worker/tasks/publishing.py`, construct a per-task `EventPublisher` (mirroring the existing per-task resource lifecycle pattern) and pass it to `TelegramPublishingService` in both `_process_publish_queue` and `_publish_single_queue_item`. *Acceptance:* a Celery-task-level test (via `run_async`, matching existing test patterns) confirms events are published for a due-scheduled item processed through the beat path.
7. **B7 — Config and connection cap.** Add `sse_heartbeat_seconds`, `sse_max_connections_per_worker`, `event_stream_channel_name` to `app/core/config.py`; enforce the cap in the B3 endpoint (may require revisiting B3 with the real setting instead of a hardcoded value). Document the required `X-Accel-Buffering: no` / no-proxy-buffering note in `10-production-readiness.md`. *Acceptance:* settings have tested defaults; overriding the cap to a low value in a test causes the next connection attempt to receive `503`.

There is no dashboard-specific backend task. Queue KPI cards already refresh from `queue.*` invalidations client-side (§2, §6); no backend event, channel, or emission logic is needed for them.

### Frontend

8. **F1 — SSE client primitive.** Add `frontend/src/features/queue/lib/sse-client.ts`: a fetch + `ReadableStream`-based reconnecting client whose frame parsing is a **vendored** adaptation of the minimal MIT-licensed parsing core from `@microsoft/fetch-event-source` (copied in, not installed as a dependency, not written from scratch — see §6). Our own wrapper code adds Bearer header support, `Last-Event-ID` tracking, exponential backoff with jitter, and `AbortController` cleanup around the vendored parsing core. No React integration. *Acceptance:* exercised against the B3 endpoint in isolation (script or test) and correctly yields parsed frames; backoff timing covered by a unit test with fake timers; a code comment attributes the vendored portion to its source and license.
9. **F2 — Subscription hook.** Add `useQueueEventStream()` using F1; exposes `status: 'connecting' | 'live' | 'reconnecting' | 'polling'` and calls a provided per-event-type callback. No cache wiring yet (callback is a parameter). *Acceptance:* hook test (mocked stream) invokes the correct callback for each event type in §2 and transitions `status` correctly on simulated disconnect/reconnect.
10. **F3 — Cache wiring in `QueueView`.** Mount `useQueueEventStream` in `QueueView`; wire its callbacks to the debounced `invalidateQueries` calls from §6. *Acceptance:* integration test (or manual verification) — triggering a publish (via existing mutation) causes the drawer/table to reflect the new attempt/status without a manual page refresh, using the live channel rather than the mutation's own `invalidateQueries` (i.e., verifiable from a *second* browser tab/session).
11. **F4 — Polling fallback.** When `useQueueEventStream` status is `'polling'`, enable `refetchInterval` (5s → 30s backoff) on the `useQueue` query (and open attempts query); disable it when status returns to `'live'`. *Acceptance:* simulated persistent SSE failure causes polling to engage; simulated recovery stops polling and performs the one-time reconnect invalidation from §7.
12. **F5 — Shared 401 handling.** Extract the inline 401 session-clear/redirect logic from `services/api-client.ts`'s response interceptor into a small exported function; call it from `sse-client.ts`'s error path on a `401` response. *Acceptance:* existing Axios 401 behavior is covered by a regression test and remains unchanged; a simulated `401` from the stream endpoint triggers the identical session-clear/redirect.
13. **F6 — Live/polling indicator (optional/stretch).** Surface `useQueueEventStream`'s `status` in `QueueToolbar` via the existing `refreshing`-style prop and the existing `Badge` primitive — no new UI primitive. *Acceptance:* visually reflects live vs. polling state; no change to `QueueToolbar`'s existing props' default behavior when the feature is not wired in (backward compatible).

---

## 16. Explicit Non-Goals (Guardrails for Implementation Sessions)

To keep every future Cursor session scoped correctly without needing to re-derive architectural intent:

- Do **not** add workspace/tenant filtering to events or the stream endpoint — the REST API doesn't have it either (§10).
- Do **not** replace any existing REST endpoint or change any existing response schema.
- Do **not** introduce client-side computation of `failure_reason`/`retry_count`/any attempt-derived field from event payloads — always refetch via `invalidateQueries` (§6).
- Do **not** add a message broker beyond Redis Pub/Sub, a persistent event log, or Redis Streams for this phase (§8, §14 Risk 6) — call it out as a follow-up idea only if reconnection-gap correctness ever proves insufficient in practice.
- Do **not** use native `EventSource` — it is architecturally incompatible with this project's Bearer-token auth model (§6).
- Do **not** implement optimistic UI updates driven by these events.
- Do **not** implement the SSE frame parser from scratch, and do **not** add `@microsoft/fetch-event-source` as a runtime dependency in `package.json` — vendor its minimal parsing core into `sse-client.ts` instead (§6, §12, §15 Task F1).
- Do **not** add a `dashboard.stats_updated` event or any backend logic that automatically emits dashboard-specific events — Queue KPI cards already refresh from existing `queue.*` invalidations (§2). `DashboardView` live updates are out of scope for Phase A.2; if added later, do it client-side only (mount the existing stream hook, invalidate `['dashboard']` on `queue.*` events) rather than introducing a new backend event.

---

## 17. Related Documents

- [08-implementation-roadmap.md](../08-implementation-roadmap.md) — Phase A.2 scope authority; this document elaborates it without altering its acceptance criteria.
- [06-api-integration.md](../06-api-integration.md) — Existing REST contracts this design must not break.
- [02-frontend-architecture.md](../02-frontend-architecture.md) — Feature-folder conventions followed for all new frontend files.
- [10-production-readiness.md](../10-production-readiness.md) — Infra checklist to extend once implemented (proxy buffering, connection caps).
- [11-workspace-design-system.md](../frontend/11-workspace-design-system.md) — Queue workspace template; no layout changes required by this design (push updates land in existing components).

*This document is a draft planning artifact pending review. It is not yet merged into `08-implementation-roadmap.md`; do so only after explicit approval, following the same adoption pattern used for the Phase A.1 milestone (`docs/archive/publishing-reliability-status-truth-roadmap.md`).*
