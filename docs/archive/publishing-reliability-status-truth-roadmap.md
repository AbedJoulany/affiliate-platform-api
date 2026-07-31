# Milestone Roadmap: Publishing Reliability & Status Truth (Telegram Publishing Scope)

**Status:** ✅ **Approved and adopted 2026-07-29** — merged into [`08-implementation-roadmap.md`](../08-implementation-roadmap.md) §3 as Phase A.1. This copy is archived for historical reference only; treat `08-implementation-roadmap.md` as the source of truth going forward.
**Document Version:** 1.1 (final, archived)
**Created:** 2026-07-29
**Last Revised:** 2026-07-29 — scope narrowed to Telegram only; added idempotency decision requirements and milestone acceptance criteria
**Adopted:** 2026-07-29
**Derived from:** `01`–`11` documentation suite, post-synchronization audit (2026-07-29)

This was a **standalone planning artifact** prior to adoption. It proposed the next development milestone and a revised phase order for `08-implementation-roadmap.md`. No code was inspected to produce this document — it was based entirely on the verified, synchronized state of the docs suite at the time. It has now been folded into `08-implementation-roadmap.md` §3 (Phase A.1) and is kept here only as an archival record of the original proposal and rationale.

---

## 1. Recommended Next Milestone: Publishing Reliability & Status Truth

**Definition:** Give the backend ownership of publish attempts, failures, and retry outcomes **for Telegram publishing** — replacing the current client-only failure model — before any real-time transport is built on top of it.

### Scope (narrowed)

| In scope for A.1 | Out of scope for A.1 |
| --- | --- |
| Telegram publish attempt/event data model | AliExpress API retry hardening |
| Telegram-specific retry policy (429/5xx, backoff, jitter) | AI provider (OpenAI/Gemini) retry hardening |
| Telegram publish idempotency guard | Dead-letter queue infrastructure beyond attempt marking |
| Celery task-level retry for the publish task only | Worker health probe / Flower / Prometheus monitoring |
| Queue API surface for Telegram attempt/failure history | SSE/WebSocket transport (Phase A.2) |
| Frontend queue UI reading Telegram attempt/failure truth | Form/schema validation standardization (Phase D) |

**Rationale for narrowing:** `06-api-integration.md` and `10-production-readiness.md` document the reliability gap almost entirely in terms of the Telegram publish path (`TelegramPublishingService`, `process_publish_queue`, `QueueHealthBadge`). AliExpress and AI-provider retry policies in `10-production-readiness.md` §9.3 are separately scoped integrations with their own failure surfaces (discovery/import, content generation) that do not block Queue status truth. Bundling all three into one milestone risks scope creep and delays the highest-leverage fix. AliExpress and AI-provider retry hardening should be tracked as a follow-up, non-blocking phase (see Section 2).

### Success Metrics

This milestone is considered successful when all of the following outcomes are achieved:

- Backend becomes the single source of truth for Telegram publish attempts and failures.
- Publish failures persist across browser refreshes and user sessions.
- No Telegram publish failure can occur without a durable backend record.
- Queue operational KPIs are computed from backend data rather than transient client state.
- Retry attempts are visible and auditable.
- The existing QueueStatus enum remains unchanged.
- The milestone enables Phase A.2 (real-time streaming) without requiring changes to the event model.

### Why this has the highest priority

| Evidence from docs | Implication |
| --- | --- |
| `06-api-integration.md` §4.6: "Failed today KPI \| `lib/operations.ts` \| **Client-side** \| Derived from client failure map" | Publish failures exist only in transient React state (`useQueuePublishingOperations`) — lost on refresh, not shared across sessions/users, not auditable. |
| `10-production-readiness.md` §10: "Silent Celery publish skip \| Medium \| Add logging + retry" | The scheduled publisher (`process_publish_queue`) has no failure visibility at all — worse than the UI gap, since it runs unattended. |
| `10-production-readiness.md` §9.3: retry policy table is entirely **target-state**, not implemented | No integration (Telegram, AliExpress, AI providers) has a defined retry contract in code today. This milestone closes the gap for **Telegram only**; AliExpress and AI-provider rows remain target-state and are deferred (see Scope). |
| `08-implementation-roadmap.md` §3: Phase A (real-time streaming) is sequenced **before** Phase C (error handling/retries) | This is a dependency inversion. SSE/WebSocket would stream `publish_failed` events, but there is no structured failure record to stream — building transport first means rebuilding the event contract once Phase C lands. |
| `11-workspace-design-system.md` §12 (Queue template): "Client-derived 'publishing' and 'failed' counts are operational — **not backend statuses**" | The canonical UI contract already assumes this is a known gap, not a design goal — it's flagged as debt, not a feature. |

### Why it has the highest leverage

It is the single change that unblocks the most other roadmap items without rework:

- Real-time streaming (old Phase A) becomes meaningful only once there's a trustworthy event to stream.
- Worker health/dead-letter handling (old Phase B) needs the same attempt model.
- Production readiness's "publish success rate" monitoring (§8) has no data source without it.

### Why other roadmap items should wait

- **Real-time streaming (SSE/WebSocket)** — waiting is correct; streaming an unreliable client-side signal would need to be rebuilt once backend truth exists.
- **Form & schema validation standardization (Phase D)** — independent track, doesn't block or get blocked by this; can run in parallel with a different contributor if resourcing allows, but shouldn't precede it in priority.
- **Platform expansion / V2 (Phase E)** — explicitly deferred in `08`, no dependency either way.
- **Registration UI, admin create-product form, analytics** — low-impact, no reliability risk, correctly low priority.
- **AliExpress and AI-provider retry hardening** — deferred out of A.1 by design (see Scope above); these are separate failure surfaces (discovery/import, content generation) and do not block Queue status truth. Track as a follow-up phase once A.1 ships.

---

## 2. Ordered Implementation Phases (proposed revision to `08-implementation-roadmap.md` §3)

```text
Phase A.1 — Publishing Reliability & Status Truth   ← START HERE
   (Telegram publishing only: attempt model, Telegram retry
    policy, idempotency guard, dead-letter marking)
        │
        ▼
Phase A.2 — Real-time Operations (SSE/WebSocket)     ← old Phase A, now unblocked
        │
        ▼
Phase B — Background Worker Hardening (remainder)     ← worker health probe,
        │                                                 Flower/Prometheus monitoring
        ▼
Phase C' — Non-Telegram Retry Hardening               ← AliExpress + AI provider
        │                                                 retry policies (deferred from A.1)
        ▼
Phase D — Form & Schema Validation Standardization    ← independent; may run
        │                                                 in parallel with A.2/B/C'
        ▼
Phase E — Platform Expansion (V2)                      ← unchanged, last
```

| Phase | Depends on | Blocks |
| --- | --- | --- |
| **A.1 Publishing Reliability & Status Truth (Telegram)** | Nothing (current state is the baseline) | A.2, B (dead-letter/idempotency parts), production "publish success rate" monitoring |
| **A.2 Real-time Operations** | A.1 (needs `status_changed`/`publish_failed` event contract) | Nothing further downstream |
| **B Worker Hardening (remainder)** | A.1 (health signal needs attempt data) | Nothing |
| **C' Non-Telegram Retry Hardening** | Independent of A.1 (separate failure surfaces) | Nothing; can run parallel to A.2/B/D |
| **D Form/Schema Validation** | Independent | Nothing |
| **E Platform Expansion** | A.1–B substantially complete (per `08` §3) | — |

Old "Phase C — Error handling & retries" is split: the Telegram-specific portion is absorbed into A.1; the AliExpress/AI-provider portion becomes the new **Phase C'**, deferred and non-blocking.

---

## 3. Backend Tasks (Phase A.1, in execution order — Telegram scope only)

1. **Design the publish-event/attempt data model** (design doc only, no code) — define the entity (e.g. `QueuePublishAttempt`): `queue_id`, `attempt_number`, `provider` (fixed to `telegram` for this milestone), `status` (started/succeeded/failed), `error_code`, `error_message`, `occurred_at`. Explicitly preserve the existing rule from `03-design-system.md`: **`failed` remains an attempt-level fact, never a new `QueueStatus` enum value.**
2. **Alembic migration** for the new table(s) — additive only, no changes to `QueueItem` schema/enum.
3. **Repository layer** — `QueuePublishAttemptRepository`: create attempt, list by `queue_id`, fetch latest attempt.
4. **Service instrumentation** — `TelegramPublishingService.publish_queue_item` records attempt start/success/failure; `_publish_items` stops silently `continue`-ing on failure and instead persists a structured failure record (queue_id, provider, attempt, error_code) — closes the "Silent Celery publish skip" known issue.
5. **Telegram retry policy implementation**:
   - Telegram Bot API calls: 3 retries, exponential backoff + jitter, respect `retry_after` on 429 — inside `TelegramPublisher`/service, before task-level retry.
   - Celery tasks: `autoretry_for`, `max_retries=3`, `retry_backoff=True` on `process_publish_queue` / `publish_queue_item_task`.
   - **AliExpress and AI-provider retry policies are explicitly out of scope for A.1** — tracked separately under Phase C' (Section 2).
6. **Idempotency guard** — see Section 3a for the decisions that must be resolved before implementation; then implement the agreed dedup mechanism on the publish task.
7. **API surface** — extend `QueueRead` (or add `GET /queues/{id}/attempts`) so the frontend can read backend-owned failure/attempt data instead of deriving it client-side.
8. **Dead-letter marking** — after retries exhaust, mark the terminal attempt as failed; queue status stays unchanged (`queued`/`scheduled`) so operators filter "needs attention" via attempts, not a fake status.
9. **Tests** — pytest coverage for retry paths, attempt persistence, idempotency guard, and the previously-silent failure path.

---

## 3a. Idempotency Decision Requirements (must be resolved before task 6 is implemented)

Telegram's `sendMessage`/`sendPhoto` APIs have no native idempotency key — a retried call after an ambiguous failure (e.g. network timeout after Telegram accepted the message) can produce a duplicate post. The following decisions must be made explicitly in the design doc (task 1) before the idempotency guard (task 6) is built:

| Decision | Question to resolve | Notes |
| --- | --- | --- |
| **Idempotency key definition** | Is the dedup key `queue_id` alone, or `queue_id + content hash`? | `queue_id` alone is simpler but blocks legitimate re-publish after a content edit; `queue_id + content hash` allows re-publish after edit but requires hash invalidation logic. |
| **Ambiguous-failure handling** | If the Celery task times out or crashes *after* calling Telegram but *before* persisting the attempt/success record, how do we avoid a duplicate on retry? | Must decide: (a) query Telegram for message existence before retrying (not reliably supported), or (b) treat this as an accepted at-least-once risk documented as a known limitation, or (c) persist attempt as "started" *before* calling Telegram so a crash leaves a detectable in-flight marker the next run can check. |
| **Concurrency guard** | Can two workers (or a manual retry + the scheduled beat task) pick up the same `queue_id` simultaneously? | Must decide locking strategy: DB row lock (`SELECT ... FOR UPDATE`) vs. an application-level "claimed" attempt state before publish begins. |
| **Idempotency key lifetime** | How long does a dedup key remain valid — per attempt, per queue item lifetime, or time-boxed (e.g. 24h)? | Must be bounded; unbounded keys complicate replays/testing. |
| **Manual retry vs. automatic retry** | Does a user-triggered "Retry publish" (via `POST /queues/{id}/publish`) bypass or respect the same idempotency guard as the automatic Celery retry? | Recommendation: both paths must go through the same guard — no separate "trusted" manual path that skips dedup logic. |
| **Content-changed-mid-retry** | If a user edits queue item content between a failed attempt and a retry, does the idempotency key invalidate? | Recommendation: yes — content hash change should always allow a fresh publish attempt. |

The design doc produced in task 1 must document the chosen answer to each row above, with rationale, before migration/implementation work begins.

---

## 4. Frontend Tasks (Phase A.1, in execution order — starts only after backend step 7 ships)

1. Update `features/queue/types/api.ts` to add backend-sourced fields (`last_attempt`, `failure_reason`, `retry_count`), mirroring the new Pydantic contract — sync per `06-api-integration.md` and `07-development-guidelines.md` §4.
2. Update `queue.api.ts` to fetch attempt/failure data from the new/extended endpoint.
3. Replace the failure-tracking half of `useQueuePublishingOperations` with backend-sourced state; keep the in-flight `publishing` set as client `useState` (that part is legitimately ephemeral UI state, not a truth gap).
4. Update `QueueHealthBadge` and `QueueOperationalStats` to read the backend failure reason, with the existing client message kept only as a fallback during rollout (zero-downtime transition, no big-bang cutover).
5. Wire a **retry action** to the existing `POST /queues/{id}/publish` endpoint (no new endpoint needed), surfaced from `QueueDetailsDrawer`.
6. Add a read-only attempt-history section to `QueueDetailsDrawer` per the drawer anatomy in `11-workspace-design-system.md` §8 (no new drawer, no new overlay pattern).
7. **No new routes, libraries, or overlay patterns** — this milestone is a data-source swap inside existing components, per the architecture rules in `11-workspace-design-system.md` §14.

---

## 5. Execution Order Summary (Backend ↔ Frontend)

```text
Backend 1–2   Design + migration                     (no frontend dependency)
Backend 3–6   Repository, service, retries, idempotency (no frontend dependency)
Backend 7     API surface ships                       ── unlocks ──▶ Frontend 1–2
Backend 8–9   Dead-letter marking + tests              (parallel with frontend work)
Frontend 1–4  Contract sync + backend-sourced state
Frontend 5–6  Retry action + attempt history UI
Frontend 7    Verification against 11-workspace-design-system.md (no drift)
```

Frontend work must not start before backend step 7 (API surface) ships, to avoid building against a contract that hasn't stabilized.

---

## 6. Milestone Acceptance Criteria

Phase A.1 (Telegram Publishing Reliability & Status Truth) is **done** only when all of the following are true. These are the gate for calling the milestone complete — not individual task completion.

### Data & backend truth

- [ ] Every Telegram publish attempt (success or failure), whether triggered by the Celery beat schedule or a manual `POST /queues/{id}/publish`, produces a persisted `QueuePublishAttempt` record with `attempt_number`, `status`, `error_code`/`error_message` (on failure), and `occurred_at`.
- [ ] Zero silent failures: no code path in `TelegramPublishingService._publish_items` (or its replacement) can fail without either persisting an attempt record or raising — the pre-existing `continue`-and-drop behavior is fully removed.
- [ ] No new value is added to the `QueueStatus` enum; `failed` remains attempt-level only.

### Retry behavior

- [ ] Telegram Bot API calls retry up to 3 times with exponential backoff and jitter, and correctly respect a `429` response's `retry_after` value — verified by a test that simulates a 429 and asserts the wait behavior.
- [ ] The Celery publish task(s) are configured with `autoretry_for`, `max_retries=3`, `retry_backoff=True`, verified by a test that simulates a transient failure and asserts a retry occurs.
- [ ] After retries are exhausted, the terminal attempt is marked failed and is queryable via the new API surface; the queue item's `status` field is unchanged by this terminal failure.

### Idempotency

- [ ] All decisions in Section 3a are documented with rationale in the Task-1 design doc before implementation, and the chosen answers are reflected in the shipped code.
- [ ] A test demonstrates that retrying a publish attempt for the same `queue_id` (unchanged content) does not produce a second Telegram message.
- [ ] A test demonstrates that editing queue item content between attempts correctly allows a fresh publish (per the Section 3a "content-changed-mid-retry" decision).
- [ ] Manual retry (`POST /queues/{id}/publish`) and automatic Celery retry are verified to go through the same idempotency guard.

### API & frontend

- [ ] The queue API surface (extended `QueueRead` or `GET /queues/{id}/attempts`) returns attempt/failure history and is documented in `06-api-integration.md`.
- [ ] `QueueHealthBadge` and `QueueOperationalStats` (`failedToday`) read the backend-sourced failure reason for Telegram publishes, with the prior client-only failure map retained only as a fallback during rollout, per Frontend task 4.
- [ ] `QueueDetailsDrawer` displays a read-only attempt-history section sourced from the backend, per Frontend task 6.
- [ ] No new routes, drawers, dialogs, or UI libraries were introduced (verified against `11-workspace-design-system.md` §14 architecture rules).

### Quality gates

- [ ] All new/changed backend code has pytest coverage (retry paths, attempt persistence, idempotency guard, previously-silent failure path).
- [ ] Frontend changes pass `npm run typecheck`, `npm run lint`, and `npm test`.
- [ ] All documentation updates listed in Section 7 are applied before the milestone is marked complete in `08-implementation-roadmap.md`.

---

## 7. Documentation Updates Required After Completion

| Document | Update |
| --- | --- |
| `06-api-integration.md` | Move "Failed today KPI" from **Client-side** to **Connected/Partial**; add the new attempt endpoint/schema to §4.6 and §6 (enums, if any). |
| `03-design-system.md` | Clarify that publish failure is now backend-owned attempt data, not just a client toast — keep the "`failed` is not a `QueueStatus`" rule intact. |
| `08-implementation-roadmap.md` | Mark Phase A.1 tasks done in the Feature Completion Checklist ("Publish failure tracking" → backend-tracked); promote old Phase A to A.2 as now unblocked; split old Phase C into the completed Telegram portion (A.1) and the new deferred **Phase C'** (AliExpress/AI-provider retry hardening). |
| `10-production-readiness.md` | Remove "Silent Celery publish skip" from Known Issues; move retry policy table in §9.3 from target to implemented; update the MVP Acceptance Flow queue step to include verifying attempt history. |
| `04-component-library.md` | Update `QueueHealthBadge` / `QueueDetailsDrawer` rows to note the new attempt-history section and backend data source. |
| `11-workspace-design-system.md` | Update the Queue template's layout note (§12) — "failed" counts are now backend-verified, not purely client-derived. |

Phase A.2 (real-time streaming) planning should not begin until this documentation pass is complete, since its event contract depends directly on the attempt model defined here.

---

## 8. Review & Adoption

**Adopted 2026-07-29.** Sections 1–6 were folded into `08-implementation-roadmap.md` §3, replacing the previous Phase A/B/C ordering with `A.1 → A.2 → B → C' → D → E`. This file was moved to `docs/archive/` and is retained only as a historical record of the proposal.

Original adoption checklist (completed):

1. ~~Review and approve (or amend) the phase re-sequencing in Section 2, the scope narrowing in Section 1, the idempotency decisions in Section 3a, and the acceptance criteria in Section 6.~~ ✅
2. ~~On approval, fold Sections 1–6 into `08-implementation-roadmap.md` §3 (replacing the current Phase A/B/C ordering) and delete or archive this file.~~ ✅
3. Implementation may now begin against `08-implementation-roadmap.md` §3 (Phase A.1) — this archived copy is a reference only, not the execution source.
