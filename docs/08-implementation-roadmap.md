# Implementation Roadmap

**Document Version:** 3.3  
**Last Updated:** 2026-09-06

**2026-09-06 revision (Product B removal):** Affiliate, Campaign, AffiliateCampaign, Click, Conversion, and campaign analytics were removed. Product A MEASURE is the operational dashboard. Historical Phase D/E notes below that describe those APIs are superseded.

**2026-09-04 revision (CI hardening):** Platform foundation — Ruff CI gate is the full first-party Python tree; Playwright smoke runs as GitHub Actions job `e2e` (not a required branch-protection check yet). See [10-production-readiness.md](./10-production-readiness.md) §3.

**2026-09-04 revision (Phase E Task 14):** Editable workspace settings + `PATCH /auth/me`. See Phase E Task 14 below.

**2026-09-04 revision (Phase E Tasks 12–13):** Analytics slice 1 + click/funnel metrics complete. See Phase E Tasks 12–13 below.

**2026-09-04 revision (Phase E Tasks 9–11 closeout):** Frontend workspace runtime (Task 9), Discovery image search UI (Task 10), and public click tracking backend (Task 11) marked complete. Phase E remains open for payouts and remaining design items.

Consolidated feature tracker (replaces empty `PROJECT_STATUS.md`). See [06-api-integration.md](./06-api-integration.md) for endpoint-level status.

**2026-07-29 revision:** Adopted the **Publishing Reliability & Status Truth (Telegram)** milestone as the next phase (formerly `docs/planning/publishing-reliability-status-truth-roadmap.md`, approved and merged; archived under `docs/archive/`). This re-sequences §3 to fix a dependency inversion — real-time streaming was previously ordered before the backend had any structured publish-failure data to stream.

**2026-07-30 revision:** Inserted **Backend Task 2.5 — create the** `QueuePublishAttempt` **SQLAlchemy model** — into Phase A.1's backend task sequence, between Task 2 (migration) and Task 3 (repository). A dependency review during implementation found that Task 3 and Task 9 (pytest, which builds the test database via `Base.metadata.create_all`, independent of whether the Alembic migration has been applied) both require a mapped SQLAlchemy entity that no existing task produced — Task 2 is migration-only by design, and Task 1 is a design doc only. This is a sequencing clarification, not a scope change: Tasks 3–9 keep their original numbers and content; Phase A.1's success metrics, acceptance criteria, and total deliverables are unchanged. Task 3's description is also expanded to enumerate the repository methods `create_attempt()`, `list_attempts()`, `latest_attempt()`, and `active_guard_lookup()`, since the last of these is a direct prerequisite for Task 6 (idempotency guard) that was previously left implicit.

**2026-08-01 revision:** Phase A.1 **backend Tasks 1–9 are complete** (design, migration `008`, model, repository, service instrumentation, Telegram retry, idempotency guard, API surface, dead-letter marking, MVP pytest). Documentation files listed under Phase A.1 completion updates are synchronized to the implementation. **Frontend Phase A.1 tasks remain open** (types, hooks, KPI/drawer wiring). Next backend-facing milestone for streaming is Phase A.2 once FE consumes attempt truth.

**2026-08-04 revision:** Phase A.1 is now **fully complete — backend and frontend.** All 7 frontend tasks shipped: `types/api.ts` and `queue.api.ts` extended, `useQueue.ts` wires attempt-summary enrichment (`useQueueAttemptSummaryEnrichment`) and attempt history (`useQueuePublishAttempts`), `lib/operations.ts` resolves failures backend-first (`resolveQueueFailure`) with the client map as a short-lived fallback, `QueueHealthBadge`/`QueueOperationalStats`/`QueueTable` consume backend truth, and `QueueDetailsDrawer` renders read-only attempt history and doubles its primary action as "Retry publish" against the existing publish endpoint. Three post-implementation bugs were also found and fixed during hardening: scheduled publishing (Celery async-engine/event-loop reuse), queue item deletion with existing attempts (missing ORM cascade), and Telegram long-message/caption publishing (missing 4096/1024-char splitting) — see [10-production-readiness.md](./10-production-readiness.md) §10.1. The milestone acceptance criteria in this section are now fully met.

**2026-08-08 revision:** Phase A.2 — Real-time Queue Updates is **COMPLETE** (backend B1–B7, frontend F1–F5, SSE end-to-end path, TanStack Query polling fallback 5s→30s, clean-clone shippability). Design record: [phase-a2-realtime-operations-design.md](./planning/phase-a2-realtime-operations-design.md). F6 is **COMPLETE** (optional/stretch badge work shipped; not required historically for A.2 completion).

**2026-08-08 revision (Phase B closeout):** Phase B — Background workers & queue execution (remainder) is **COMPLETE** (Tasks 0–4). Design record: [phase-b-worker-observability-design.md](./planning/phase-b-worker-observability-design.md). Shipped: Redis pipeline heartbeat, `GET /worker/health`, optional Flower under Compose profile `observability`.

**2026-08-09 revision (Phase C' closeout):** Phase C' — Non-Telegram retry hardening is **COMPLETE** (Tasks 0–5). Design record: [phase-c-prime-retry-hardening-design.md](./planning/phase-c-prime-retry-hardening-design.md). Shipped: AliExpress client-retry coverage + discovery exception hygiene; OpenAI/Gemini provider-layer retry (`app/ai/retry.py`); no-nested-Celery-HTTP-retry regression guards; API/integration regression validation. **No** Celery HTTP autoretry for AliExpress discovery, **no** Celery path for AI generation, **no** DB/SSE/frontend changes.

**2026-08-13 revision (Phase D closeout):** Phase D — Authentication & Public-Endpoint Security is **COMPLETE** (Tasks 0–6). Design record: [phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md). Shipped: JWT secret validation (non-dev), refresh tokens (`refresh_tokens` / migration `009`), route-scoped Redis rate limits (login/refresh/conversions; fail-open; not middleware), `POST /conversions` ownership authorization, frontend refresh + single-flight 401 handling. **No** A.1/A.2/B/C' behavior changes.

**2026-08-14 revision (Form & schema validation closeout):** Form & Schema Validation Standardization is **COMPLETE** (Tasks 0–6). Design record: [form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md). Shipped: queue scheduling Zod discriminated union + RHF dialog; product status schema/label consolidation; `channelAssignmentSchema` (no standalone assignment UI); shared Arabic Zod message helpers. **No** API/backend/DB/dependency changes. **Next milestone: Phase E — Platform expansion (V2).**

---



## 1. Executive Summary

The frontend has completed a **workspace UI transformation** (July 2026): drawer-based inspection, operational queue center, inventory grid controls, AI content studio overhaul, and shared score/toast components. Backend integration is **live-first** — no mock API layers in production paths. **Phase A.1 — Publishing Reliability & Status Truth** (2026-08-04) closed the last major reliability gap: Telegram publish attempts, retries, idempotency, and dead-letter handling are now backend-owned and fully consumed by the queue UI. **Phase A.2 — Real-time Queue Updates** (2026-08-08) adds SSE push + polling fallback so the queue workspace stays authoritative without redesigning REST or inventing client-owned state. **Phase B — Background workers & queue execution** (2026-08-08) adds Worker/Beat pipeline liveness (`GET /worker/health`) and optional Flower task observability without changing A.1/A.2 business behavior. **Phase C' — Non-Telegram retry hardening** (2026-08-09) preserves AliExpress client-owned HTTP retries, adds provider-owned OpenAI/Gemini retries, and explicitly forbids nested Celery HTTP retries for those same failures — without new APIs, migrations, or frontend work. **Phase D — Authentication & Public-Endpoint Security** (2026-08-13) hardens JWT configuration, adds opaque refresh tokens, route-scoped rate limits, and conversion ownership checks — without disrupting A.1/A.2/B/C'. **Form & Schema Validation Standardization** (2026-08-14) extends the existing React Hook Form + Zod pattern to queue scheduling and consolidates product-status / channel-assignment schemas — frontend UX validation only; backend contracts unchanged.

---



## 2. Feature Completion Checklist

Legend: ✅ Done · 🟡 Partial · ⬜ Planned

### Platform foundation


| Feature                              | Status | Notes                |
| ------------------------------------ | ------ | -------------------- |
| Next.js App Router + feature folders | ✅      |                      |
| TanStack Query + Axios client        | ✅      |                      |
| Auth login + JWT session             | ✅      | Access + refresh; single-flight refresh |
| Active workspace runtime (Task 9)    | ✅      | `/auth/me` → `default_workspace_id` → `sessionStorage`; Axios `X-Workspace-Id` on tenant paths |
| AppShell + sidebar navigation        | ✅      |                      |
| RTL + dark mode                      | ✅      |                      |
| Shared loading/empty/error states    | ✅      |                      |
| Drawer + Popover primitives          | ✅      |                      |
| ToastOverlay feedback                | ✅      | Custom; not sonner   |
| CI: Ruff first-party Python tree     | ✅      | `ruff check .`; vendored `iop/` excluded |
| CI: Playwright smoke job             | ✅      | Job `e2e`; not a required branch-protection check yet |
| Shared DataTable extraction          | ⬜      | Feature-local tables |
| Registration UI                      | ⬜      | API exists           |




### Dashboard


| Feature                      | Status | Notes            |
| ---------------------------- | ------ | ---------------- |
| Product/queue/channel counts | ✅      | `GET /dashboard` |
| Recent activity feed         | ✅      |                  |
| System status (DB)           | ✅      |                  |
| AI usage metrics             | ⬜      | Not in API       |




### Discovery workspace (`/discovery`)


| Feature                                                 | Status | Notes                                 |
| ------------------------------------------------------- | ------ | ------------------------------------- |
| Intent tabs (hot/deals/trending/category/general)       | ✅      |                                       |
| Filter bar (keywords, rating, discount, category)       | ✅      |                                       |
| Advanced filters drawer (price, orders, shipping, sort) | ✅      |                                       |
| Interactive results grid                                | ✅      |                                       |
| AI Score Breakdown Popover (`ProductAiScoreCell`)       | ✅      |                                       |
| Slide-over product inspector drawer                     | ✅      | Score, images, commission, actions    |
| Bulk selection + batch import                           | ✅      | Admin only                            |
| CSV export                                              | ✅      |                                       |
| Session persistence (filters/UI prefs)                  | ✅      | sessionStorage                        |
| Image search UI                                         | ✅      | Global `POST /products/search/image`; no workspace header |
| Persist toggle (`persist=true`)                         | ⬜      | API only                              |
| Full paging UI for all modes                            | 🟡     | page/page_size in advanced drawer     |




### Products inventory (`/products`)


| Feature                                | Status | Notes                               |
| -------------------------------------- | ------ | ----------------------------------- |
| Server-paginated inventory grid        | ✅      |                                     |
| Density controls (comfortable/compact) | ✅      |                                     |
| Column visibility toggles              | ✅      |                                     |
| Client search + sort on page           | ✅      |                                     |
| Bulk selection bar                     | ✅      |                                     |
| Row-click `ProductDetailsDrawer`       | ✅      | Aspect-ratio image, score breakdown |
| Image hover preview                    | ✅      |                                     |
| Pipeline/health badges                 | ✅      | Joins queue data                    |
| Admin status update                    | ✅      | `PATCH /products/{id}`              |
| Admin bulk delete                      | ✅      |                                     |
| Add to queue / AI handoff              | ✅      |                                     |
| CSV export                             | ✅      |                                     |
| Admin create product form              | ⬜      |                                     |
| Server-side search/sort                | ⬜      | Client-only today                   |




### AI Content Studio (`/ai`)


| Feature                                   | Status | Notes                      |
| ----------------------------------------- | ------ | -------------------------- |
| Content workspace (replaces AIStudioView) | ✅      |                            |
| Multi-variant generation + tabs           | ✅      |                            |
| Tone / type / language / length config    | ✅      | Synced with backend schema |
| Instruction modifiers                     | ✅      |                            |
| Local session persistence                 | ✅      | sessionStorage             |
| Client content quality scores             | ✅      | Display only               |
| Variant compare dialog                    | ✅      |                            |
| Queue draft + distribution hub            | ✅      |                            |
| Server-side variant/history persistence   | ⬜      |                            |
| Dedicated regenerate API                  | ⬜      | Re-submit generate         |




### Publishing queue (`/queue`)


| Feature                                 | Status | Notes                                                                                                 |
| --------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------- |
| KPI summary cards                       | ✅      | Queued, scheduled, publishing, published today, failed today                                          |
| Filterable/sortable table               | ✅      |                                                                                                       |
| Channel routing indicators              | ✅      |                                                                                                       |
| Pipeline readiness badges               | ✅      |                                                                                                       |
| Post content preview                    | ✅      |                                                                                                       |
| Queue details drawer                    | ✅      |                                                                                                       |
| Inline + dialog schedule picker         | ✅      | `PATCH` with `scheduled_at`                                                                           |
| Bulk publish / schedule / delete        | ✅      |                                                                                                       |
| Publish failure tracking                | ✅      | Backend owns `queue_publish_attempts` + dead-letter codes; UI resolves via `resolveQueueFailure` (backend-first, client map only as short-lived fallback) |
| Publish attempt/event history            | ✅      | `GET /queues/{id}/attempts` wired in `QueueDetailsDrawer` via `useQueuePublishAttempts`; `QueueRead` summary on `GET /queues/{id}`                     |
| Telegram retry policy                    | ✅      | In-process retries + Celery `autoretry_for` / `max_retries=3`; non-retryable 4xx marked terminal immediately |
| Real-time status updates                | ✅      | Phase A.2 + Task 9 — SSE `GET /queues/stream` with workspace header; polling fallback 5s→30s when SSE unavailable |
| Dedicated retry orchestration           | ✅      | Shared claim/idempotency guard; manual + Celery share path; terminal → `dead_letter`; status-drift healing on guard-suppressed success |




### Channels


| Feature                       | Status | Notes      |
| ----------------------------- | ------ | ---------- |
| List + create + active toggle | ✅      |            |
| Bot permission display        | ✅      |            |
| Delete channel                | ⬜      | API exists |
| Connection test action        | ⬜      |            |




### Settings


| Feature                           | Status | Notes           |
| --------------------------------- | ------ | --------------- |
| Read-only capability sections     | ✅      |                 |
| `/ready` database + Redis display | ✅      |                 |
| Editable settings forms           | ⬜      | No settings API |


---



## 3. Upcoming Implementation Phases

```text
Phase A.1 — Publishing Reliability & Status Truth (Telegram)   ✅ COMPLETE (backend + frontend)
        │
        ▼
Phase A.2 — Real-time Queue Updates (SSE)   ✅ COMPLETE
        │
        ▼
Phase B — Background workers & queue execution (remainder)   ✅ COMPLETE
        │
        ▼
Phase C' — Non-Telegram retry hardening (AliExpress, AI providers)   ✅ COMPLETE
        │
        ▼
Phase D — Authentication & Public-Endpoint Security   ✅ COMPLETE
        │
        ▼
Form & schema validation standardization   ✅ COMPLETE
        │
        ▼
Phase E — Platform expansion (V2)   ← IN PROGRESS (Tasks 9–13 complete)
        │
        ▼
Phase E remainder — Editable settings · Payouts   ← OPEN
```



### Phase A.1 — Publishing Reliability & Status Truth (Telegram) ✅ COMPLETE

**Approved:** 2026-07-29. **Completed:** 2026-08-04 (backend Tasks 1–9 on 2026-08-01; frontend tasks + post-implementation hardening on 2026-08-04). Highest priority was publish failures existing only in transient client state and silent batch skips — both addressed on the backend, then surfaced end-to-end in the UI.

**Scope — Telegram only.** AliExpress and AI-provider retry hardening are explicitly deferred to Phase C' to avoid scope creep on the highest-leverage fix.

**Success metrics:**

- Backend becomes the single source of truth for Telegram publish attempts and failures. ✅
- Publish failures persist across browser refreshes and user sessions. ✅
- No Telegram publish failure can occur without a durable backend record. ✅
- Queue operational KPIs are computed from backend data rather than transient client state. ✅
- Retry attempts are visible and auditable. ✅ (API + `QueueDetailsDrawer` attempt-history UI)
- The existing `QueueStatus` enum remains unchanged. ✅
- This milestone enables Phase A.2 (real-time streaming) without requiring changes to the event model. ✅ (backend event contract exists)

**Backend tasks (in order):**

**Task 1.** ✅ Design `QueuePublishAttempt` data model — `docs/backend/queue-publish-attempt-design.md`

**Task 2.** ✅ Alembic migration `008_add_queue_publish_attempts.py` — additive only, no changes to `QueueItem` table schema

**Task 2.5.** ✅ Create the `QueuePublishAttempt` SQLAlchemy model in `app/models/queue.py` (constraints mirrored for SQLite `create_all`)

**Task 3.** ✅ `QueuePublishAttemptRepository` — `create_attempt()`, `list_attempts()`, `latest_attempt()`, `active_guard_lookup()`

**Task 4.** ✅ Instrument `TelegramPublishingService` to persist every attempt; batch path no longer silently drops failures without a record

**Task 5.** ✅ Telegram retry policy: in-process 3 retries, exponential backoff + jitter, respect `retry_after` on 429; Celery `autoretry_for` / `max_retries=3` / `retry_backoff=True` on publish tasks

**Task 6.** ✅ Idempotency guard — claim lock + `(queue_id, content_hash)` + 24h window; shared by manual and Celery paths

**Task 7.** ✅ API surface — `GET /queues/{id}/attempts`; `QueueRead` summary fields on `GET /queues/{id}` (`last_attempt`, `failure_reason`, `retry_count`)

**Task 8.** ✅ Dead-letter marking after retries exhaust (`error_code=dead_letter`; queue status unchanged)

**Task 9.** ✅ Pytest coverage (MVP): repository, successful/failed publish persistence, idempotency, retry/dead-letter, attempts API

**Idempotency decisions (resolved in Task 1 design doc; implemented in Task 6):**

- Dedup key: `queue_id` + content hash (effective outbound payload)
- Ambiguous-failure handling: persist `started` before Telegram call
- Concurrency guard: `FOR UPDATE` claim on queue row; commit started attempt before network I/O
- Key lifetime: 24 hours from `occurred_at` for blocking `started`/`succeeded`
- Manual retry (`POST /queues/{id}/publish`) and automatic Celery retry share the same guard
- Content edited between attempts invalidates the dedup key and allows a fresh publish

**Frontend tasks — ✅ all complete (2026-08-04):**

1. ✅ Extended `features/queue/types/api.ts` with backend-sourced fields (`last_attempt`, `failure_reason`, `retry_count`) and attempt types.
2. ✅ Updated `queue.api.ts` to fetch attempt/failure data (`GET /queues/{id}`, `getQueuePublishAttempts` → `GET /queues/{id}/attempts`).
3. ✅ `useQueue.ts` adds `useQueueAttemptSummaryEnrichment` (backfills non-published rows via bounded-concurrency `GET /queues/{id}`) and `resolveQueueFailure`/`failureFromQueueItem` (`lib/operations.ts`) to prefer backend data; in-flight `publishing` stays client state (legitimately ephemeral); `syncFailuresFromBackend` drops the client fallback once backend data is present.
4. ✅ `QueueHealthBadge` / `QueueOperationalStats` / `QueueTable` read backend failure reason via `resolveQueueFailure` (client message as fallback only until enrichment resolves).
5. ✅ "Retry publish" wired to the existing `POST /queues/{id}/publish` from `QueueDetailsDrawer` — no new endpoint; button relabels to "إعادة المحاولة" when a failure is present.
6. ✅ Read-only attempt-history section added to `QueueDetailsDrawer` (`useQueuePublishAttempts`).
7. ✅ No new routes, drawers, dialogs, or libraries — data-source swap inside existing components per [11-workspace-design-system.md](./frontend/11-workspace-design-system.md).

**Milestone acceptance criteria — all met:**

- Every Telegram publish attempt (manual or scheduled) persists with attempt number, status, error detail, timestamp — zero silent failures. ✅ Backend
- No new `QueueStatus` enum value introduced. ✅
- Retry behavior verified by tests (429/`retry_after` handling, Celery autoretry on transient failure, batch persist-and-continue on `TelegramPublishError`). ✅ MVP pytest
- Idempotency verified by tests (no duplicate send on retry; fresh publish allowed after content edit; manual and automatic retry share the guard; status-drift healing on guard-suppressed success). ✅ MVP pytest
- API surface documented in `06-api-integration.md`; `QueueHealthBadge`/`QueueOperationalStats`/`QueueDetailsDrawer` read backend truth with client fallback only as a short-lived gap-filler. ✅ Docs + FE wiring complete
- No new UI routes/drawers/dialogs/libraries introduced. ✅
- Backend pytest and frontend typecheck/lint/test all pass. ✅
- Documentation updates below are applied before this phase is marked done. ✅ (this revision)
- Post-implementation bugs (scheduled publishing, item deletion, long-message publishing) found during hardening are fixed and regression-tested. ✅ `tests/test_queue_delete.py`, `tests/test_telegram_long_messages.py`, additions to `tests/test_queue_publishing_service.py`

**Documentation updates required on completion — all applied:**

- `06-api-integration.md` — ✅ "Failed today KPI" and attempts endpoint → Connected; retry-via-existing-endpoint and status-heal-on-409 documented
- `03-design-system.md` — ✅ publish failure is backend-owned attempt data; rollout language removed
- `10-production-readiness.md` — ✅ Telegram retry row implemented; §10.1 records the three resolved post-implementation bugs
- `04-component-library.md` — ✅ `QueueHealthBadge` / `QueueOperationalStats` / `QueueDetailsDrawer` notes updated from planned to implemented
- `11-workspace-design-system.md` — ✅ Queue template layout note updated to drop rollout-fallback framing
- This document (`08`) — ✅ feature checklist, frontend task list, and success metrics flipped to complete; Phase A.2 was the next milestone and is now also complete (2026-08-08)



### Phase A.2 — Real-time Queue Updates ✅ COMPLETE

**Completed:** 2026-08-08. Design record: [phase-a2-realtime-operations-design.md](./planning/phase-a2-realtime-operations-design.md).

**Transport:** Server-Sent Events (not WebSockets). Authenticated `GET /api/v1/queues/stream`.

**Architecture (as shipped):**

```text
Queue mutation → EventPublisher → Redis queue-events
  → EventConsumer → EventBroadcaster → SSE clients
  → frontend invalidation → TanStack Query refetch → Queue UI
```

**Events (canonical):** `queue.status_changed`, `queue.deleted`, `queue.attempt_started`, `queue.attempt_succeeded`, `queue.attempt_failed`.  
**No** `dashboard.stats_updated`. Queue KPI cards refresh from `["queue"]` invalidation. Dashboard-page live updates remain out of scope.

**Frontend:** Fetch-based SSE client with vendored `@microsoft/fetch-event-source` parsing core (not an npm dependency; not browser `EventSource`). Debounced invalidate-never-patch. `QueueRealtimeStatusBadge` for connection UX. Adaptive TanStack Query polling fallback **5s → 30s** while SSE is unavailable; reconnect performs one authoritative refresh and disables polling.

**Task completion:**

| Task | Final status |
| ---- | ------------ |
| B1–B7 | COMPLETE |
| F1–F5 | COMPLETE |
| F6 | COMPLETE |

**Deliverables met:** Backend SSE + Redis fan-out; frontend subscription + invalidation; live Queue table/KPIs/drawer via authoritative refetch; polling fallback when SSE is down.

**Out of scope / post-A.2:** heartbeat 15s tuning, ULID event IDs, SSE connection cap, shared Axios 401 helper for the stream, reverse-proxy staging verification — see design doc §18.

### Phase B — Background workers & queue execution (remainder) ✅ COMPLETE

**Completed:** 2026-08-08. Design record: [phase-b-worker-observability-design.md](./planning/phase-b-worker-observability-design.md).

Phase B **did not rebuild** the Celery business schedules. Those tasks already existed before Phase B and remain infrastructure Phase B observes/hardens around:

**Existing infrastructure (pre–Phase B; unchanged schedules):**

| Task | Schedule | Role |
| ---- | -------- | ---- |
| `process_publish_queue` | 60s (configurable) | Publish due scheduled + queued items |
| `refresh_hot_products` | 6h | Catalog sync |
| `refresh_trending_products` | 6h | Catalog sync |
| `refresh_categories` | 24h | Category cache |

**Phase B deliverables (shipped):**

| Concern | Shipped mechanism |
| ------- | ----------------- |
| Worker/Beat **pipeline liveness** | Beat schedules `worker_heartbeat` → worker SET Redis `celery:health:heartbeat` (TTL) → `GET /worker/health` |
| Task **execution observability** | Optional Flower (`docker compose --profile observability`) reading Celery broker/events |

These are separate operational concerns. Flower is **not** a health probe. `/worker/health` does **not** provide task-failure metrics. Prometheus is **deferred** (not shipped). Discovery Celery HTTP `autoretry_for` for AliExpress failures was **not** added in Phase B; Phase C' confirmed client-owned AliExpress HTTP retries and explicitly forbids nesting Celery HTTP retries on the same failures (see Phase C' below).

**Architecture (liveness):**

```text
Celery Beat
    ↓
worker_heartbeat
    ↓
Redis key celery:health:heartbeat (+ TTL)
    ↓
GET /worker/health
```

**Architecture (task observability):**

```text
Celery tasks (publishing / discovery / heartbeat)
    ↓
Celery task events (worker_send_task_events / task_send_sent_event)
    ↓
Flower (optional Compose profile: observability)
    ↓
operator UI
```

**Completion checklist:**

- [x] Task 0 — Worker/Beat health & observability architecture
- [x] Task 1 — Redis worker/beat heartbeat
- [x] Task 2 — Worker health API (`GET /worker/health`)
- [x] Task 3 — Flower task failure observability
- [x] Task 4 — Documentation closeout

Publish-task idempotency for Telegram remains Phase A.1 work; Phase B does not duplicate it. A.1 and A.2 behavior is unchanged.

### Phase C' — Non-Telegram retry hardening ✅ COMPLETE

**Completed:** 2026-08-09. Design record: [phase-c-prime-retry-hardening-design.md](./planning/phase-c-prime-retry-hardening-design.md).

**Scope — AliExpress + OpenAI/Gemini only.** Telegram retry/idempotency remains Phase A.1 and was not reimplemented. A.1 publishing reliability, A.2 SSE/`queue-events`, Flower, heartbeat, and `/worker/health` were not modified.

**Retry ownership (authoritative):**

```text
AliExpress HTTP failures
        ↓
app/aliexpress/api_client.py::_execute_with_retries
        ↓
client-owned retry (budget / backoff / jitter / rate-limit gate)
        ↓
discovery task or discovery API
        ↓
existing error/response contract

AI provider failures
        ↓
OpenAIProvider / GeminiProvider → app/ai/retry.py
        ↓
provider-owned retry (max 2 attempts)
        ↓
AIProviderError
        ↓
existing POST /ai-content/generate contract
```

```text
Celery HTTP retry for AliExpress: NOT USED
Celery retry for AI generation: NOT USED
```

**AliExpress (preserved client policy + hygiene/tests):**

| Property | Shipped behavior |
| --- | --- |
| Owner | `AliExpressAPIClient._execute_with_retries` only |
| Attempt budget | `aliexpress_max_retries + 1` (default **4** total; Settings `aliexpress_max_retries=3`) |
| Retryable | `AliExpressRateLimitError`; `AliExpressAPIError` when `code ∈ {408,429,500,502,503,504}` or message contains `timeout`/`temporarily` |
| Non-retryable | `AliExpressCredentialsError` (immediate re-raise); other unclassified `AliExpressAPIError` (e.g. 400/401/403/404) |
| Backoff | `aliexpress_retry_backoff_seconds * (2 ** attempt)` (default base **0.5s**) + `random.uniform(0, 0.25)` jitter |
| Rate-limit gate | `_apply_rate_limit` enforces `aliexpress_rate_limit_interval_seconds` (default **0.2s**) before every attempt |
| Celery | Discovery tasks (`refresh_hot_products`, `refresh_trending_products`, `refresh_categories`) have **no** AliExpress HTTP `autoretry_for` — nesting would multiply outbound calls |
| Exception hygiene | Discovery refresh path propagates canonical `app.aliexpress.exceptions.AliExpressAPIError`; service-layer `app.services.exceptions.AliExpressAPIError` remains for existing API/import contracts |

**AI providers (new provider-layer policy):**

| Property | Shipped behavior |
| --- | --- |
| Owner | Shared helper `app/ai/retry.py`, used by `OpenAIProvider` and `GeminiProvider` |
| Attempt budget | **2** total attempts (1 initial + 1 retry) — not Settings-driven |
| Retryable | `httpx.TransportError`; HTTP **429**; HTTP **5xx** (`500 ≤ status < 600`) |
| Non-retryable | HTTP **400/401/403/404**; other non-transport errors; unexpected non-httpx errors |
| Malformed response | Parsed **outside** the retry loop → **no retry** (1 provider call) |
| Backoff | Base **1.0s** × `2 ** attempt` + `uniform(0, 0.5)` jitter |
| Retry-After | Honored when a valid non-negative numeric header is present; capped at **60s**; malformed/missing → normal backoff |
| Timeout | Existing **60s** per attempt unchanged |
| Logging | Concise retry schedule logs (provider, attempt, reason, delay) — no API keys, prompts, or credential-bearing URLs |
| API contract | Exhaustion still raises `AIProviderError` → existing `ServiceError` → HTTP mapping; no new endpoints/fields |

**Tasks completed:**

- [x] Task 0 — Architecture decision (retry ownership; no nested AliExpress Celery HTTP retry; AI provider-layer retry; no DB/SSE/FE)
- [x] Task 1 — AliExpress retry test coverage + discovery exception hygiene
- [x] Task 2 — AI provider retry hardening (OpenAI + Gemini via shared helper)
- [x] Task 3 — AliExpress no-nested-retry regression protection
- [x] Task 4 — Integration/API regression validation
- [x] Task 5 — Documentation closeout

**Validation (backend):** Task 1 full suite **154** passed; Task 3 focused **14** passed; Task 4 focused **28** passed; full suite after Task 4 **244** passed. Ruff passed on changed files. No backend typecheck is configured. Tests are offline (no real AliExpress/OpenAI/Gemini calls; retry sleeps mocked).

**Explicit non-goals (verified):** no database migration/tables; no new queue/SSE events; no frontend changes; no Telegram retry changes; no Prometheus; no new API endpoints; no Celery task for AI generation. Future Celery retry for AliExpress, if ever considered, may only target failures **outside** the HTTP client budget (e.g. DB/session) and is **not** part of this completed phase.

### Phase D — Authentication & Public-Endpoint Security ✅ COMPLETE

**Status:** COMPLETE  
**Completed:** 2026-08-13 (Tasks 0–6). Design record: [phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

Hardens authentication and public endpoints without disrupting A.1 publishing reliability, A.2 SSE/queue realtime, Phase B worker observability, or Phase C' retry ownership.

**Dependency sequence:** Task 0 → Tasks 1 / 3 / 4 → Task 2 → Task 5 → Task 6.

| Task | Scope | Status |
| ---- | ----- | ------ |
| D.0 | Architecture decision | ✅ COMPLETE |
| D.1 | JWT secret validation | ✅ COMPLETE |
| D.2 | Refresh token infrastructure | ✅ COMPLETE |
| D.3 | Rate limiting | ✅ COMPLETE |
| D.4 | Conversion authorization | ✅ COMPLETE |
| D.5 | Frontend authentication integration | ✅ COMPLETE |
| D.6 | Documentation closeout | ✅ COMPLETE |

**Shipped summary:**

| Area | Behavior |
| --- | --- |
| JWT secrets | Non-dev rejects repository default and secrets &lt; 32 chars; fail-fast on Settings; no secret echo |
| Refresh tokens | Opaque tokens; SHA-256 hashes in PostgreSQL `refresh_tokens` (migration `009`); rotate + single-use + reuse revocation; logout revoke; TTL `refresh_token_expire_days` default 7 |
| Rate limits | Redis fixed-window via route `Depends` (not middleware); login 10/5m IP; refresh 20/5m IP; conversions 30/1m user-or-IP; fail-open; 429 + `Retry-After`; IP from `request.client.host` only |
| Conversions | `POST /conversions` requires access JWT; affiliate owner or ADMIN; 401/403; amount still client-supplied / PENDING unchanged |
| Frontend | sessionStorage access + refresh; Bearer = access only; single-flight refresh; retry-once; 403 does not refresh; logout clears local state |

**ADDITIVE:** `refresh_token` on login/refresh responses; `POST /auth/refresh`; `POST /auth/logout`; `refresh_tokens` table.

**SECURITY-BEHAVIOR:** JWT validation outside development; rate limiting; conversion authz.

**UNCHANGED:** access JWT mechanism; `/health`, `/ready`, `/worker/health`, `/queues/stream`; A.1/A.2/B/C'; `QueueStatus`; Telegram publishing; AliExpress/AI retry ownership.

**Explicit non-goals:** MFA, password reset, device dashboards, HttpOnly refresh cookies, proxy-aware client IP, conversion amount fraud verification, global rate-limit middleware.

### Form & Schema Validation Standardization ✅ COMPLETE

**Status:** COMPLETE  
**Completed:** 2026-08-14 (Tasks 0–6). Design record: [form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md).

This is **not** Phase D and **not** Phase E. It sits between completed Phase D (auth/security) and Phase E (platform expansion). Formerly listed as the mechanical “Phase D” before auth-security Phase D was selected.

React Hook Form, Zod, and `@hookform/resolvers` were **already** in the project (`LoginForm`, ChannelsView add-channel). This milestone extended that pattern; it did not introduce a new form stack.

| Task | Scope | Status |
| ---- | ----- | ------ |
| 0 | Architecture / analysis / planning | ✅ COMPLETE |
| 1 | Queue Scheduling Zod schema (`queueSchedulingSchema`) | ✅ COMPLETE |
| 2 | React Hook Form + `zodResolver` for `QueueSchedulingDialog` | ✅ COMPLETE |
| 3 | Product Status schema / label consolidation | ✅ COMPLETE |
| 4 | Channel Assignment schema (`channelAssignmentSchema`; no standalone UI) | ✅ COMPLETE |
| 5 | Shared Arabic Zod validation message helper | ✅ COMPLETE |
| 6 | Documentation closeout | ✅ COMPLETE |

**Shipped (schema standardization, not new business capabilities):**

| Area | Behavior |
| --- | --- |
| Queue scheduling | Discriminated union `schedule` / `publish_now`; `channelId` always required; `scheduledAt` only for `schedule`; form-domain `datetime-local` string; API map in existing submit path |
| Scheduling dialog | RHF + `zodResolver`; `register()`; presets `setValue(..., { shouldValidate: true })`; `handleSubmit`; `scheduledAt` → `scheduled_at`, `channelId` → `channel_id` |
| Product status | Canonical `PRODUCT_STATUSES` (`draft`/`active`/`inactive`/`archived`); `productStatusSchema`; centralized Arabic labels. **No status editor.** |
| Channel assignment | UUID schema used by the scheduling dialog. **No assignment drawer.** Queue items may still have `channel_id: null` at rest. Telegram `@handle` is not an assignment UUID. |
| Arabic messages | `frontend/src/lib/validation/messages.ts`: `requiredField`, `invalidUuid`, `invalidDateTime`. Queue schemas adopted it; product status did not need it; Login/Channels not retrofitted. Not i18n. |

**UNCHANGED:** `PATCH /queues/{id}` and `PATCH /products/{id}` contracts; Pydantic; database; dependencies; authentication; rate limiting; A.2 SSE / F4 / F6; Phase B; Phase C'.

**Explicit non-goals:** independent Channel Assignment UI; product status mutation UI; backend validation framework; global i18n; `useValidatedMutation`. Frontend Zod is UX/input validation, not a security control.

**Task 5 validation (that task’s run):** focused tests **36** passed; full frontend tests **136** passed; typecheck PASS; lint PASS (pre-existing warnings only); build PASS.

### Phase E — Platform expansion (V2)   ← IN PROGRESS

Multi-workspace tenancy · Analytics `/analytics` · Editable settings · Image search UI · Admin bootstrap CLI · Click tracking · Payout module

Depends on Phases A.1–D being substantially complete. JWT refresh tokens are **done in Phase D** (not deferred here).

#### Phase E Task 9 — Frontend workspace context plumbing ✅ COMPLETE

**Completed:** 2026-09-04. Design: [planning/phase-e-platform-expansion-design.md](./planning/phase-e-platform-expansion-design.md) §18 Task 9.

**Shipped:**

| Area | Behavior |
| --- | --- |
| Workspace init | `GET /auth/me` → `default_workspace_id` (single membership) → `affiliate_active_workspace_id` in `sessionStorage` |
| Axios interceptor | Attaches `X-Workspace-Id` only on workspace-scoped paths (`/dashboard`, `/queues`, `/channels`, `/campaigns`, `/conversions`, `/affiliates/join-campaign`, `/analytics`, `/workspace-settings`); strips header elsewhere |
| Query keys | `workspaceScopedQueryKey` for `dashboard`, `queue`, `channels`, `analytics`, `workspace-settings`; cache cleared on logout |
| SSE | `useQueueEventStream` sends JWT + workspace header; no stream without both |
| UI gating | Dashboard, queue, channels, analytics views show no-workspace state when id absent |
| Logout | Clears tokens, workspace id, cookie, query cache → `/login` |

**Explicit non-goals (unchanged):** workspace selector UI; new routes/pages; workspace-scoping of Products, Discovery, or Image Search.

**Tests:** `api-client.workspace.test.ts`, dashboard/queue/SSE workspace gating tests.

#### Phase E Task 10 — Image search UI ✅ COMPLETE

**Completed:** 2026-08-22 (UI); documented 2026-09-04. Independent of workspace tenancy.

**Shipped:**

| Area | Behavior |
| --- | --- |
| UI | `ImageSearchPanel` inside Discovery — image URL input or file upload (≤5MB, `image/*`) |
| API | `POST /products/search/image` via `discovery.api.ts`; **no** `X-Workspace-Id` |
| Results | Reuses `DiscoveryResultsTable`, pagination, and `DiscoveryProductInspector` |
| Gallery handoff | Inspector `onSearchByImage` re-runs image search from a product image URL |
| Gating | Backend env `ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH` (unchanged) |

**Explicit non-goals:** workspace-scoped product catalog; backend/API changes to the image search endpoint.

#### Phase E Task 11 — Click tracking ✅ COMPLETE

**Completed:** 2026-08-23 (backend); live-verified 2026-09-04. Design: [planning/phase-e-platform-expansion-design.md](./planning/phase-e-platform-expansion-design.md) §18 Task 11.

**Shipped:**

| Area | Behavior |
| --- | --- |
| Model | `Click` → `AffiliateCampaign`; unique server `click_id`; no `workspace_id` |
| Migration | `014_add_clicks.py` (revises `013`; `010`–`013` unchanged) |
| Public route | `GET /api/v1/clicks/{affiliate_campaign_id}` → persist click, **302** to `tracking_link` |
| Security | Redirect from stored link only; blank/unsafe schemes rejected (**422**, no row) |
| Rate limit | Phase D primitive — **30** / **60s** per IP → **429** + `Retry-After` |
| Conversions | Optional `click_id`; enrollment match enforced when Click exists |
| Frontend | None (server-to-browser redirect) |

**Verified live:** 302 + persistence; public scope; unsafe link rejection; conversion correlation; tenant/SSE regression intact.

**Explicit non-goals:** analytics/funnel metrics shipped in Tasks 12–13; bot filtering beyond rate limit; Product↔Campaign redesign.

**Still open in Phase E:** Task 15 payout module · workspace selector UI.

#### Phase E Task 12 — Analytics slice 1 (aggregate KPIs) ✅ COMPLETE

**Completed:** 2026-09-04.

**Shipped:** `GET /api/v1/analytics/overview?from=&to=` — workspace-scoped totals (`total_clicks`, `total_conversions`, `conversion_rate`, `total_revenue` from `Conversion.amount`, `by_day`). Auth + `X-Workspace-Id`. Default last 30 days; max 1 year. Frontend `/analytics` KPI strip + line chart (`recharts`).

**Tenancy:** derived via Campaign FK chain. No `workspace_id` on clicks/conversions.

#### Phase E Task 13 — Click/funnel analytics ✅ COMPLETE

**Completed:** 2026-09-04.

**Shipped:** `GET /api/v1/analytics/campaigns/{campaign_id}/funnel` — per-campaign click→conversion series + `attributed_conversions`. Cross-workspace campaign id → **404**. Migration `015_add_analytics_indexes` (revises `014`). Campaign selector uses `GET /campaigns/active`.

**Explicit non-goals:** payouts; Product↔Campaign redesign.

#### Phase E Task 14 — Editable settings ✅ COMPLETE

**Completed:** 2026-09-04.

**Shipped:** `GET/PATCH /api/v1/workspace-settings` (Bearer + `X-Workspace-Id`; PATCH admin or workspace OWNER). `PATCH /auth/me` for `full_name`/`email` only (no workspace header; cannot change `role`/`is_active`). Table `workspace_settings` (migration `016`, revises `015`, `ON DELETE CASCADE`). Connection booleans only — no secret values. Frontend section forms in `features/settings/` with feature-local Zod + RHF; profile form in `features/auth/`.

**Explicit non-goals:** exposing JWT/Telegram/AliExpress/OpenAI/Gemini secrets; editing `QueueStatus`/`ProductStatus`; celery worker cadence.

---



## 4. Backend Completeness (from legacy architecture audit)


| Module                                    | Status                |
| ----------------------------------------- | --------------------- |
| Auth (register/login/me/refresh/logout)   | ✅ Phase D             |
| Products CRUD + discovery/import          | ✅                     |
| AI content (extended generate)            | ✅                     |
| Queue CRUD + publish                      | ✅                     |
| Channels CRUD                             | ✅                     |
| Dashboard + readiness                     | ✅                     |
| Celery publishing                         | ✅                     |
| Celery worker/Beat health + Flower ops    | ✅ Phase B             |
| Affiliates/campaigns/conversions          | ❌ Removed (Product B) |
| Refresh tokens                            | ✅ Phase D (migration 009) |
| Rate limiting (route dependencies)        | ✅ Phase D + E (login/refresh/conversions/clicks) |
| Public click tracking                     | ✅ Phase E Task 11 (migration 014) |
| Analytics (overview + campaign funnel)    | ❌ Removed (Product B). Product A MEASURE is the dashboard |
| Workspace settings + profile PATCH        | ✅ Phase E Task 14 (migration 016) |
| CI/CD full lint gate                      | ✅ Ruff `check .` (iop vendor excluded) |
| Publish attempt/event tracking (Telegram) | ✅ Phase A.1 backend   |
| Telegram retry + idempotency policy       | ✅ Phase A.1 backend   |
| Real-time queue SSE + polling fallback    | ✅ Phase A.2           |
| AliExpress client retry + discovery hygiene | ✅ Phase C'          |
| OpenAI/Gemini provider retry              | ✅ Phase C'            |


---



## 5. Definition of Done (unchanged)

A feature is complete when: correct folder structure · reusable components · loading/empty/error states · TypeScript clean · design system compliance · API contract documented in `06-api-integration.md`

---



## 6. Related Documents

- [06-api-integration.md](./06-api-integration.md) — Integration matrix
- [10-production-readiness.md](./10-production-readiness.md) — Release gates & infra
- [09-cursor-prompts.md](./09-cursor-prompts.md) — AI development templates
- [archive/publishing-reliability-status-truth-roadmap.md](./archive/publishing-reliability-status-truth-roadmap.md) — Original Phase A.1 milestone proposal (adopted 2026-07-29; historical record only)
- [planning/phase-a2-realtime-operations-design.md](./planning/phase-a2-realtime-operations-design.md) — Phase A.2 design + closeout (COMPLETE 2026-08-08)
- [planning/phase-b-worker-observability-design.md](./planning/phase-b-worker-observability-design.md) — Phase B Task 0 design + Tasks 1–4 closeout (COMPLETE 2026-08-08)
- [planning/phase-c-prime-retry-hardening-design.md](./planning/phase-c-prime-retry-hardening-design.md) — Phase C' design + Tasks 0–5 closeout (COMPLETE 2026-08-09)
- [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md) — Phase D auth/security design + Tasks 0–6 closeout (COMPLETE 2026-08-13)
- [planning/form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md) — Form & schema validation design + Tasks 0–6 closeout (COMPLETE 2026-08-14)

