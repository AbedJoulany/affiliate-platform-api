# Implementation Roadmap

**Document Version:** 2.4  
**Last Updated:** 2026-08-04

Consolidated feature tracker (replaces empty `PROJECT_STATUS.md`). See [06-api-integration.md](./06-api-integration.md) for endpoint-level status.

**2026-07-29 revision:** Adopted the **Publishing Reliability & Status Truth (Telegram)** milestone as the next phase (formerly `docs/planning/publishing-reliability-status-truth-roadmap.md`, approved and merged; archived under `docs/archive/`). This re-sequences §3 to fix a dependency inversion — real-time streaming was previously ordered before the backend had any structured publish-failure data to stream.

**2026-07-30 revision:** Inserted **Backend Task 2.5 — create the** `QueuePublishAttempt` **SQLAlchemy model** — into Phase A.1's backend task sequence, between Task 2 (migration) and Task 3 (repository). A dependency review during implementation found that Task 3 and Task 9 (pytest, which builds the test database via `Base.metadata.create_all`, independent of whether the Alembic migration has been applied) both require a mapped SQLAlchemy entity that no existing task produced — Task 2 is migration-only by design, and Task 1 is a design doc only. This is a sequencing clarification, not a scope change: Tasks 3–9 keep their original numbers and content; Phase A.1's success metrics, acceptance criteria, and total deliverables are unchanged. Task 3's description is also expanded to enumerate the repository methods `create_attempt()`, `list_attempts()`, `latest_attempt()`, and `active_guard_lookup()`, since the last of these is a direct prerequisite for Task 6 (idempotency guard) that was previously left implicit.

**2026-08-01 revision:** Phase A.1 **backend Tasks 1–9 are complete** (design, migration `008`, model, repository, service instrumentation, Telegram retry, idempotency guard, API surface, dead-letter marking, MVP pytest). Documentation files listed under Phase A.1 completion updates are synchronized to the implementation. **Frontend Phase A.1 tasks remain open** (types, hooks, KPI/drawer wiring). Next backend-facing milestone for streaming is Phase A.2 once FE consumes attempt truth.

**2026-08-04 revision:** Phase A.1 is now **fully complete — backend and frontend.** All 7 frontend tasks shipped: `types/api.ts` and `queue.api.ts` extended, `useQueue.ts` wires attempt-summary enrichment (`useQueueAttemptSummaryEnrichment`) and attempt history (`useQueuePublishAttempts`), `lib/operations.ts` resolves failures backend-first (`resolveQueueFailure`) with the client map as a short-lived fallback, `QueueHealthBadge`/`QueueOperationalStats`/`QueueTable` consume backend truth, and `QueueDetailsDrawer` renders read-only attempt history and doubles its primary action as "Retry publish" against the existing publish endpoint. Three post-implementation bugs were also found and fixed during hardening: scheduled publishing (Celery async-engine/event-loop reuse), queue item deletion with existing attempts (missing ORM cascade), and Telegram long-message/caption publishing (missing 4096/1024-char splitting) — see [10-production-readiness.md](./10-production-readiness.md) §10.1. The milestone acceptance criteria in this section are now fully met. **Next milestone: Phase A.2 (real-time streaming) only.**

---



## 1. Executive Summary

The frontend has completed a **workspace UI transformation** (July 2026): drawer-based inspection, operational queue center, inventory grid controls, AI content studio overhaul, and shared score/toast components. Backend integration is **live-first** — no mock API layers in production paths. **Phase A.1 — Publishing Reliability & Status Truth** (2026-08-04) closed the last major reliability gap: Telegram publish attempts, retries, idempotency, and dead-letter handling are now backend-owned and fully consumed by the queue UI, with scheduled-publishing, delete-cascade, and long-message bugs fixed during hardening.

---



## 2. Feature Completion Checklist

Legend: ✅ Done · 🟡 Partial · ⬜ Planned

### Platform foundation


| Feature                              | Status | Notes                |
| ------------------------------------ | ------ | -------------------- |
| Next.js App Router + feature folders | ✅      |                      |
| TanStack Query + Axios client        | ✅      |                      |
| Auth login + JWT session             | ✅      | No refresh token     |
| AppShell + sidebar navigation        | ✅      |                      |
| RTL + dark mode                      | ✅      |                      |
| Shared loading/empty/error states    | ✅      |                      |
| Drawer + Popover primitives          | ✅      |                      |
| ToastOverlay feedback                | ✅      | Custom; not sonner   |
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
| Image search UI                                         | ⬜      | Backend `POST /products/search/image` |
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
| Real-time status updates                | ⬜      | See Phase A.2 below                                                                                   |
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
Phase A.2 — Real-time operations (SSE/WebSocket)   ← NEXT MILESTONE
        │
        ▼
Phase B — Background workers & queue execution (remainder)
        │
        ▼
Phase C' — Non-Telegram retry hardening (AliExpress, AI providers)
        │
        ▼
Phase D — Form & schema validation standardization   (independent; may run parallel to A.2/B/C')
        │
        ▼
Phase E — Platform expansion (V2)
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
- This document (`08`) — ✅ feature checklist, frontend task list, and success metrics flipped to complete; Phase A.2 confirmed as the sole next milestone



### Phase A.2 — Real-time operations (depends on Phase A.1)

**WebSockets / SSE for publishing queue**

- Stream queue item status transitions: `queued` → `scheduled` → `published`
- Surface the Phase A.1 attempt events (`publish_started`, `publish_succeeded`, `publish_failed`) — not a client-only failure map
- Fallback: TanStack Query polling with exponential backoff when SSE unavailable

**Deliverables:** Backend SSE endpoint or WebSocket channel; frontend subscription hook; KPI cards update live

**Ready to start.** Phase A.1 is complete end-to-end (backend attempt events since 2026-08-01; frontend data-source swap since 2026-08-04) — the UI already reads backend attempt truth, so streaming can layer on top without mixing in a client failure map.

### Phase B — Background workers & queue execution (remainder; depends on Phase A.1 for health signal)

Document and harden existing Celery setup:


| Task                        | Schedule           | Action                               |
| --------------------------- | ------------------ | ------------------------------------ |
| `process_publish_queue`     | 60s (configurable) | Publish due scheduled + queued items |
| `refresh_hot_products`      | 6h                 | Catalog sync                         |
| `refresh_trending_products` | 6h                 | Catalog sync                         |
| `refresh_categories`        | 24h                | Category cache                       |


**Requirements:**

- Worker health probe independent of `/ready`
- Flower or Prometheus metrics for task failures
- Document Redis/Celery env in [10-production-readiness.md](./10-production-readiness.md)

Publish-task idempotency for Telegram is delivered in Phase A.1; do not duplicate that work here.

### Phase C' — Non-Telegram retry hardening (independent; may run parallel to A.2/B/D)

Deferred from the original Phase C scope — Telegram retry policy ships in Phase A.1. This phase covers the remaining integrations:


| Provider                     | Strategy                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| AliExpress IOP               | Existing rate limit + exponential backoff in `api_client.py`; add `ALIEXPRESS_MAX_RETRIES` enforcement review |
| AI providers (OpenAI/Gemini) | Retry transient 502/503; surface `AIProviderError` to UI                                                      |




### Phase D — Form & schema validation standardization

- Shared Zod schemas in `features/*/lib/schemas.ts` mirroring Pydantic
- Drawer inline edits: product status, queue schedule, channel assignment
- React Hook Form + zodResolver for scheduling dialog
- Validation error copy in Arabic



### Phase E — Platform expansion (V2)

Multi-workspace tenancy · JWT refresh · Analytics `/analytics` · Editable settings · Image search UI · Admin bootstrap CLI · Click tracking · Payout module

Depends on Phases A.1–B being substantially complete.

---



## 4. Backend Completeness (from legacy architecture audit)


| Module                                    | Status                |
| ----------------------------------------- | --------------------- |
| Auth (register/login/me)                  | ✅                     |
| Products CRUD + discovery/import          | ✅                     |
| AI content (extended generate)            | ✅                     |
| Queue CRUD + publish                      | ✅                     |
| Channels CRUD                             | ✅                     |
| Dashboard + readiness                     | ✅                     |
| Celery publishing                         | ✅                     |
| Affiliates/campaigns/conversions          | ✅ API, no UI          |
| Refresh tokens                            | ⬜ Config only         |
| Rate limiting middleware                  | ⬜                     |
| CI/CD full lint gate                      | 🟡 Partial Ruff scope |
| Publish attempt/event tracking (Telegram) | ✅ Phase A.1 backend   |
| Telegram retry + idempotency policy       | ✅ Phase A.1 backend   |


---



## 5. Definition of Done (unchanged)

A feature is complete when: correct folder structure · reusable components · loading/empty/error states · TypeScript clean · design system compliance · API contract documented in `06-api-integration.md`

---



## 6. Related Documents

- [06-api-integration.md](./06-api-integration.md) — Integration matrix
- [10-production-readiness.md](./10-production-readiness.md) — Release gates & infra
- [09-cursor-prompts.md](./09-cursor-prompts.md) — AI development templates
- [archive/publishing-reliability-status-truth-roadmap.md](./archive/publishing-reliability-status-truth-roadmap.md) — Original Phase A.1 milestone proposal (adopted 2026-07-29; historical record only)

