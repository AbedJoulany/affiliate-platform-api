# Implementation Roadmap

**Document Version:** 2.2  
**Last Updated:** 2026-07-30

Consolidated feature tracker (replaces empty `PROJECT_STATUS.md`). See [06-api-integration.md](./06-api-integration.md) for endpoint-level status.

**2026-07-29 revision:** Adopted the **Publishing Reliability & Status Truth (Telegram)** milestone as the next phase (formerly `docs/planning/publishing-reliability-status-truth-roadmap.md`, approved and merged; archived under `docs/archive/`). This re-sequences §3 to fix a dependency inversion — real-time streaming was previously ordered before the backend had any structured publish-failure data to stream.

**2026-07-30 revision:** Inserted **Backend Task 2.5 — create the `QueuePublishAttempt` SQLAlchemy model** — into Phase A.1's backend task sequence, between Task 2 (migration) and Task 3 (repository). A dependency review during implementation found that Task 3 and Task 9 (pytest, which builds the test database via `Base.metadata.create_all`, independent of whether the Alembic migration has been applied) both require a mapped SQLAlchemy entity that no existing task produced — Task 2 is migration-only by design, and Task 1 is a design doc only. This is a sequencing clarification, not a scope change: Tasks 3–9 keep their original numbers and content; Phase A.1's success metrics, acceptance criteria, and total deliverables are unchanged. Task 3's description is also expanded to enumerate the repository methods `create_attempt()`, `list_attempts()`, `latest_attempt()`, and `active_guard_lookup()`, since the last of these is a direct prerequisite for Task 6 (idempotency guard) that was previously left implicit.

---

## 1. Executive Summary

The frontend has completed a **workspace UI transformation** (July 2026): drawer-based inspection, operational queue center, inventory grid controls, AI content studio overhaul, and shared score/toast components. Backend integration is **live-first** — no mock API layers in production paths.

---

## 2. Feature Completion Checklist

Legend: ✅ Done · 🟡 Partial · ⬜ Planned

### Platform foundation

| Feature | Status | Notes |
| --- | --- | --- |
| Next.js App Router + feature folders | ✅ | |
| TanStack Query + Axios client | ✅ | |
| Auth login + JWT session | ✅ | No refresh token |
| AppShell + sidebar navigation | ✅ | |
| RTL + dark mode | ✅ | |
| Shared loading/empty/error states | ✅ | |
| Drawer + Popover primitives | ✅ | |
| ToastOverlay feedback | ✅ | Custom; not sonner |
| Shared DataTable extraction | ⬜ | Feature-local tables |
| Registration UI | ⬜ | API exists |

### Dashboard

| Feature | Status | Notes |
| --- | --- | --- |
| Product/queue/channel counts | ✅ | `GET /dashboard` |
| Recent activity feed | ✅ | |
| System status (DB) | ✅ | |
| AI usage metrics | ⬜ | Not in API |

### Discovery workspace (`/discovery`)

| Feature | Status | Notes |
| --- | --- | --- |
| Intent tabs (hot/deals/trending/category/general) | ✅ | |
| Filter bar (keywords, rating, discount, category) | ✅ | |
| Advanced filters drawer (price, orders, shipping, sort) | ✅ | |
| Interactive results grid | ✅ | |
| AI Score Breakdown Popover (`ProductAiScoreCell`) | ✅ | |
| Slide-over product inspector drawer | ✅ | Score, images, commission, actions |
| Bulk selection + batch import | ✅ | Admin only |
| CSV export | ✅ | |
| Session persistence (filters/UI prefs) | ✅ | sessionStorage |
| Image search UI | ⬜ | Backend `POST /products/search/image` |
| Persist toggle (`persist=true`) | ⬜ | API only |
| Full paging UI for all modes | 🟡 | page/page_size in advanced drawer |

### Products inventory (`/products`)

| Feature | Status | Notes |
| --- | --- | --- |
| Server-paginated inventory grid | ✅ | |
| Density controls (comfortable/compact) | ✅ | |
| Column visibility toggles | ✅ | |
| Client search + sort on page | ✅ | |
| Bulk selection bar | ✅ | |
| Row-click `ProductDetailsDrawer` | ✅ | Aspect-ratio image, score breakdown |
| Image hover preview | ✅ | |
| Pipeline/health badges | ✅ | Joins queue data |
| Admin status update | ✅ | `PATCH /products/{id}` |
| Admin bulk delete | ✅ | |
| Add to queue / AI handoff | ✅ | |
| CSV export | ✅ | |
| Admin create product form | ⬜ | |
| Server-side search/sort | ⬜ | Client-only today |

### AI Content Studio (`/ai`)

| Feature | Status | Notes |
| --- | --- | --- |
| Content workspace (replaces AIStudioView) | ✅ | |
| Multi-variant generation + tabs | ✅ | |
| Tone / type / language / length config | ✅ | Synced with backend schema |
| Instruction modifiers | ✅ | |
| Local session persistence | ✅ | sessionStorage |
| Client content quality scores | ✅ | Display only |
| Variant compare dialog | ✅ | |
| Queue draft + distribution hub | ✅ | |
| Server-side variant/history persistence | ⬜ | |
| Dedicated regenerate API | ⬜ | Re-submit generate |

### Publishing queue (`/queue`)

| Feature | Status | Notes |
| --- | --- | --- |
| KPI summary cards | ✅ | Queued, scheduled, publishing, published today, failed today |
| Filterable/sortable table | ✅ | |
| Channel routing indicators | ✅ | |
| Pipeline readiness badges | ✅ | |
| Post content preview | ✅ | |
| Queue details drawer | ✅ | |
| Inline + dialog schedule picker | ✅ | `PATCH` with `scheduled_at` |
| Bulk publish / schedule / delete | ✅ | |
| Publish failure tracking | 🟡 | Client-side today; backend attempt truth planned Phase A.1 |
| Publish attempt/event history (backend) | ⬜ | Planned Phase A.1 |
| Telegram retry policy (backend) | ⬜ | Planned Phase A.1 |
| Real-time status updates | ⬜ | See Phase A.2 below |
| Dedicated retry orchestration | ⬜ | Manual re-publish only; backend retry in Phase A.1 |

### Channels

| Feature | Status | Notes |
| --- | --- | --- |
| List + create + active toggle | ✅ | |
| Bot permission display | ✅ | |
| Delete channel | ⬜ | API exists |
| Connection test action | ⬜ | |

### Settings

| Feature | Status | Notes |
| --- | --- | --- |
| Read-only capability sections | ✅ | |
| `/ready` database + Redis display | ✅ | |
| Editable settings forms | ⬜ | No settings API |

---

## 3. Upcoming Implementation Phases

```text
Phase A.1 — Publishing Reliability & Status Truth (Telegram)   ← NEXT MILESTONE
        │
        ▼
Phase A.2 — Real-time operations (SSE/WebSocket)
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

### Phase A.1 — Publishing Reliability & Status Truth (Telegram) — next milestone

**Approved:** 2026-07-29. Highest priority: publish failures currently exist only in transient client state (`useQueuePublishingOperations`) and the scheduled publisher fails silently (`_publish_items` drops errors with `continue`). Building real-time streaming (Phase A.2) before this exists would mean streaming data that doesn't exist yet.

**Scope — Telegram only.** AliExpress and AI-provider retry hardening are explicitly deferred to Phase C' to avoid scope creep on the highest-leverage fix.

**Success metrics:**

- Backend becomes the single source of truth for Telegram publish attempts and failures.
- Publish failures persist across browser refreshes and user sessions.
- No Telegram publish failure can occur without a durable backend record.
- Queue operational KPIs are computed from backend data rather than transient client state.
- Retry attempts are visible and auditable.
- The existing `QueueStatus` enum remains unchanged.
- This milestone enables Phase A.2 (real-time streaming) without requiring changes to the event model.

**Backend tasks (in order):**

**Task 1.** Design `QueuePublishAttempt` data model (design doc only, no migration): `queue_id`, `attempt_number`, `provider` (`telegram`), `status`, `error_code`, `error_message`, `occurred_at`. `failed` stays attempt-level — **no new `QueueStatus` enum value.**

**Task 2.** Alembic migration — additive only, no changes to `QueueItem`.

**Task 2.5.** Create the `QueuePublishAttempt` SQLAlchemy model. Model only — no repository logic, no service instrumentation, no API changes, no retry logic.

- Mapped entity matching the approved Task 1 design document, following existing project conventions (`UUIDPrimaryKeyMixin`, `TimestampMixin`, `Base` model style as used in `app/models/queue.py`).
- Must match migration `008_add_queue_publish_attempts.py` exactly — same columns, types, and nullability.
- Mirror every constraint the migration requires, where appropriate, in `__table_args__` (status-value check, content-hash format check, outcome-consistency check, the unique `(queue_id, attempt_number)` constraint, and both composite indexes). This matters independently of Alembic: `tests/conftest.py` builds the test database via `Base.metadata.create_all(...)`, so any constraint not mirrored on the model is untested and can silently drift from production.
- Decide and document whether `QueueItem` receives a read-side ORM `relationship(...)` to `QueuePublishAttempt`. This is an ORM-mapping decision only — it does not add, remove, or alter any column on the `queue_items` table and does not conflict with Task 2's "no changes to `QueueItem`" constraint (which refers to the table schema, not the ORM mapping layer).
- `QueueStatus` remains unchanged; the new model's own status field is separate and attempt-scoped.

**Task 3.** `QueuePublishAttemptRepository` — assumes the Task 2.5 model already exists. Implements:

- `create_attempt()` — persist a new attempt row.
- `list_attempts()` — list attempts for a `queue_id`.
- `latest_attempt()` — most recent attempt for a `queue_id`.
- `active_guard_lookup(queue_id, content_hash)` — find a non-expired matching attempt for the idempotency guard; required by Task 6 (idempotency guard) and aligned with the migration's `ix_queue_publish_attempts_guard_lookup` index.

**Task 4.** Instrument `TelegramPublishingService` to persist every attempt; remove the silent `continue` in `_publish_items`.

**Task 5.** Telegram retry policy: 3 retries, exponential backoff + jitter, respect `retry_after` on 429; Celery `autoretry_for` / `max_retries=3` / `retry_backoff=True` on publish tasks.

**Task 6.** Idempotency guard — resolve the decisions below in the Task 1 design doc, then implement.

**Task 7.** API surface — extend `QueueRead` or add `GET /queues/{id}/attempts`.

**Task 8.** Dead-letter marking after retries exhaust (queue status unchanged — filter by attempts, not a fake status).

**Task 9.** Pytest coverage: retry paths, attempt persistence, idempotency guard, previously-silent failure path.

**Idempotency decisions (resolve before Task 6):**

- Dedup key: `queue_id` alone vs. `queue_id` + content hash (latter recommended — allows re-publish after edits)
- Ambiguous-failure handling: persist a "started" attempt *before* calling Telegram so a mid-call crash is detectable on the next run
- Concurrency guard: DB row lock or "claimed" attempt state so two workers can't publish the same item
- Key lifetime: bounded, not indefinite
- Manual retry (`POST /queues/{id}/publish`) and automatic Celery retry must share the same guard
- Content edited between attempts must invalidate the dedup key and allow a fresh publish

**Frontend tasks (start only after backend Task 7 ships):**

1. Extend `features/queue/types/api.ts` with backend-sourced fields (`last_attempt`, `failure_reason`, `retry_count`).
2. Update `queue.api.ts` to fetch attempt/failure data.
3. Replace the failure half of `useQueuePublishingOperations` with backend-sourced state; keep in-flight `publishing` as client state (legitimately ephemeral).
4. `QueueHealthBadge` / `QueueOperationalStats` read backend failure reason (client message as fallback during rollout only).
5. Wire "Retry publish" to the existing `POST /queues/{id}/publish` from `QueueDetailsDrawer` — no new endpoint.
6. Add a read-only attempt-history section to `QueueDetailsDrawer`.
7. No new routes, drawers, dialogs, or libraries — data-source swap inside existing components per [11-workspace-design-system.md](./frontend/11-workspace-design-system.md).

**Milestone acceptance criteria:**

- Every Telegram publish attempt (manual or scheduled) persists with attempt number, status, error detail, timestamp — zero silent failures.
- No new `QueueStatus` enum value introduced.
- Retry behavior verified by tests (429/`retry_after` handling, Celery autoretry on transient failure).
- Idempotency verified by tests (no duplicate send on retry; fresh publish allowed after content edit; manual and automatic retry share the guard).
- API surface documented in `06-api-integration.md`; `QueueHealthBadge`/`QueueOperationalStats`/`QueueDetailsDrawer` read backend truth with client fallback during rollout.
- No new UI routes/drawers/dialogs/libraries introduced.
- Backend pytest and frontend typecheck/lint/test all pass.
- Documentation updates below are applied before this phase is marked done.

**Documentation updates required on completion:**

- `06-api-integration.md` — "Failed today KPI" Client-side → Connected/Partial; document the attempt endpoint/schema.
- `03-design-system.md` — clarify publish failure is now backend-owned attempt data.
- `10-production-readiness.md` — remove "Silent Celery publish skip" from Known Issues; move the Telegram row in §9.3 retry table to implemented.
- `04-component-library.md` — update `QueueHealthBadge` / `QueueDetailsDrawer` notes for the attempt-history section.
- `11-workspace-design-system.md` — update the Queue template layout note (§12).
- This document (`08`) — flip "Publish failure tracking" to backend-tracked in §2 above.

### Phase A.2 — Real-time operations (depends on Phase A.1)

**WebSockets / SSE for publishing queue**

- Stream queue item status transitions: `queued` → `scheduled` → `published`
- Surface the Phase A.1 attempt events (`publish_started`, `publish_succeeded`, `publish_failed`) — not a client-only failure map
- Fallback: TanStack Query polling with exponential backoff when SSE unavailable

**Deliverables:** Backend SSE endpoint or WebSocket channel; frontend subscription hook; KPI cards update live

**Do not start before Phase A.1 ships** — there is no trustworthy event to stream until then.

### Phase B — Background workers & queue execution (remainder; depends on Phase A.1 for health signal)

Document and harden existing Celery setup:

| Task | Schedule | Action |
| --- | --- | --- |
| `process_publish_queue` | 60s (configurable) | Publish due scheduled + queued items |
| `refresh_hot_products` | 6h | Catalog sync |
| `refresh_trending_products` | 6h | Catalog sync |
| `refresh_categories` | 24h | Category cache |

**Requirements:**

- Worker health probe independent of `/ready`
- Flower or Prometheus metrics for task failures
- Document Redis/Celery env in [10-production-readiness.md](./10-production-readiness.md)

Publish-task idempotency for Telegram is delivered in Phase A.1; do not duplicate that work here.

### Phase C' — Non-Telegram retry hardening (independent; may run parallel to A.2/B/D)

Deferred from the original Phase C scope — Telegram retry policy ships in Phase A.1. This phase covers the remaining integrations:

| Provider | Strategy |
| --- | --- |
| AliExpress IOP | Existing rate limit + exponential backoff in `api_client.py`; add `ALIEXPRESS_MAX_RETRIES` enforcement review |
| AI providers (OpenAI/Gemini) | Retry transient 502/503; surface `AIProviderError` to UI |

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

| Module | Status |
| --- | --- |
| Auth (register/login/me) | ✅ |
| Products CRUD + discovery/import | ✅ |
| AI content (extended generate) | ✅ |
| Queue CRUD + publish | ✅ |
| Channels CRUD | ✅ |
| Dashboard + readiness | ✅ |
| Celery publishing | ✅ |
| Affiliates/campaigns/conversions | ✅ API, no UI |
| Refresh tokens | ⬜ Config only |
| Rate limiting middleware | ⬜ |
| CI/CD full lint gate | 🟡 Partial Ruff scope |
| Publish attempt/event tracking (Telegram) | ⬜ Planned Phase A.1 |
| Telegram retry + idempotency policy | ⬜ Planned Phase A.1 |

---

## 5. Definition of Done (unchanged)

A feature is complete when: correct folder structure · reusable components · loading/empty/error states · TypeScript clean · design system compliance · API contract documented in `06-api-integration.md`

---

## 6. Related Documents

- [06-api-integration.md](./06-api-integration.md) — Integration matrix
- [10-production-readiness.md](./10-production-readiness.md) — Release gates & infra
- [09-cursor-prompts.md](./09-cursor-prompts.md) — AI development templates
- [archive/publishing-reliability-status-truth-roadmap.md](./archive/publishing-reliability-status-truth-roadmap.md) — Original Phase A.1 milestone proposal (adopted 2026-07-29; historical record only)
