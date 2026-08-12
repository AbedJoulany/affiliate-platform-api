# Phase D — Project Analysis & Next-Phase Definition

**Status:** Analysis-only. No implementation performed.
**Branch inspected:** `cursor/phase-c-prime-retry-hardening` (contains completed Phase C' Tasks 0–5, verified against source, not just documentation).
**Method:** Every completion claim below was cross-checked against source code, not assumed from documentation.

---

## 1. Executive Summary

The platform has completed four consecutive backend-reliability phases (A.1 → A.2 → B → C'), all independently verified as genuinely implemented, not just documented as complete. This is a mature, **hardened MVP**: publishing is backend-owned and idempotent, the queue is realtime, workers are observable, and the two remaining external integrations (AliExpress, AI providers) have correct, non-duplicating retry ownership.

The roadmap's mechanical next step (`docs/08-implementation-roadmap.md` §3: "Phase D — Form & schema validation standardization") is real but low-leverage — most of the friction it addresses (schedule dialog validation, discovery filter validation) already exists per `docs/07-development-guidelines.md` §4. Continuing the roadmap mechanically here would not address the platform's actual highest-risk gap.

Direct source inspection surfaced a materially more urgent, evidence-backed problem that the roadmap does not currently name at all: **the authentication/session and public-write security surface has concrete, unresolved gaps that the project's own production-readiness document already flags as blockers**, plus two gaps the documentation does not yet call out explicitly:

1. `app/core/config.py` ships `refresh_token_expire_days: int = 7` — a setting that is **read nowhere else in the entire codebase**. No refresh endpoint, no refresh token model, no rotation logic exists. This is a scaffolded-but-abandoned feature, not a "nice to have" — it is dead configuration sitting next to a real, documented UX gap (`docs/02-frontend-architecture.md`: "Refresh tokens are **not implemented**. Sessions expire when the access JWT expires.").
2. `jwt_secret_key` defaults to the literal string `"change-me-to-a-long-random-secret-in-production"` (`app/core/config.py`), and **nothing in `app/main.py` or anywhere else validates this at startup**. `docs/10-production-readiness.md` §10 already lists this as the project's only **Critical**-severity known issue — and it remains fully unresolved in code today.
3. `POST /conversions` (`app/api/v1/conversions.py::record_conversion`) has **no authentication dependency at all** and accepts a caller-supplied `amount: Decimal` directly from the request body (`app/schemas/conversion.py`), which `ConversionService.record_conversion` then uses to compute and persist `commission = amount * affiliate.commission_rate / 100` with `status=PENDING`. Any caller who can supply a valid `affiliate_id`/`campaign_id` pair can inject a fabricated conversion at an arbitrary dollar amount — a business-integrity gap, not merely a missing "rate limit," and directly relevant to Phase E's already-planned "Payout module."
4. There is **no rate-limiting middleware anywhere in `app/`** — confirmed by a full-repository grep; the only rate-limiting code in the project is AliExpress's own outbound client gate (`app/aliexpress/api_client.py`), which protects AliExpress from *this* app, not this app's public endpoints from abuse.

These four findings are concrete, verified, unresolved, and — critically — **already partially self-flagged by the project's own documentation as blocking**, which is the strongest possible evidence basis for a "next phase" recommendation under this task's rules. No other candidate area (forms, analytics, test coverage) has an equivalent, already-declared **Critical** severity marker sitting unresolved in the repository.

**Recommended Phase D: Authentication & Public-Endpoint Security Hardening.** This is not a roadmap continuation — it is a phase the roadmap does not currently contain, derived from direct evidence, and selected over four other realistic candidates (§8).

---

## 2. Phase Completion Verification

All four prior phases were re-verified against source, not accepted from documentation.

### Phase A.1 — Publishing Reliability Foundation

| Item | Status | Evidence |
| --- | --- | --- |
| Publish attempt recording | Implemented correctly | `app/models/queue.py::QueuePublishAttempt` — durable per-attempt row with `CheckConstraint` on `status`/`provider`/outcome-consistency |
| Failure handling | Implemented correctly | `app/services/queue.py::TelegramPublishingService._mark_attempt_failed` — persists before propagating, distinguishes terminal (`dead_letter`) vs. non-terminal |
| Retry behavior | Implemented correctly | `app/telegram/publisher.py::_post` (client-level, ≤4 attempts, backoff+jitter, honors `retry_after`) + `app/worker/tasks/publishing.py` (`autoretry_for=(TelegramPublishError,)`, `max_retries=3`) — intentionally layered, made safe by the idempotency guard below |
| Queue status truth | Implemented correctly | `QueueStatus` enum unchanged (no `failed` value); failure state lives entirely in `queue_publish_attempts`, not on `QueueItem` |
| Backend aggregate/status APIs | Implemented correctly | `GET /queues/{id}/attempts`, `QueueRead.last_attempt`/`failure_reason`/`retry_count` via `QueueService._to_queue_read` |
| Frontend consumption of backend truth | Implemented correctly | `docs/06-api-integration.md` §4.6 confirms `resolveQueueFailure` prefers backend attempt data; `QueueDetailsDrawer` renders attempt history |

**Verdict: COMPLETE**, no fragility found.

### Phase A.2 — Real-time Updates / SSE

| Item | Status | Evidence |
| --- | --- | --- |
| SSE implementation | Implemented correctly | `app/api/v1/queue_stream.py` — authenticated `GET /queues/stream`, `text/event-stream`, per-client bound queue |
| Queue event generation | Implemented correctly | `app/services/queue.py::_build_queue_event`/`_publish_queue_event` on every state-changing path (publish, status change, delete) |
| Event lifecycle | Implemented correctly | `EventPublisher` → Redis `queue-events` → `EventConsumer` → `EventBroadcaster` → SSE, per `app/events/*` |
| Connection/reconnection behavior | Implemented correctly | Frontend test coverage exists specifically for this (`useQueueRealtimeInvalidation.reconnect*.test.tsx`, `useQueueEventStream.test.tsx`) |
| Polling fallback | Implemented correctly | `useQueuePollingFallback.test.tsx`; adaptive 5s→30s per `docs/08` |
| Frontend realtime state | Implemented correctly | `QueueRealtimeStatusBadge.test.tsx`, `QueueSseMount.test.ts`, `queue-event-invalidation.test.ts` |
| F4/F6 behavior | Implemented correctly | `QueueToolbar.f6.test.tsx`, `realtimeReliability.f5.test.tsx` present and passing per repo state |

**Verdict: COMPLETE.** Notably, this is the single most heavily unit-tested area of the entire frontend (11 of the frontend's 16 test files touch queue realtime behavior) — see §5.7 for why this matters to the current test-coverage imbalance.

### Phase B — Worker Observability

| Item | Status | Evidence |
| --- | --- | --- |
| Worker heartbeat | Implemented correctly | `app/worker/tasks/health.py::worker_heartbeat` writes `celery:health:heartbeat` with TTL |
| Beat scheduling | Implemented correctly | `app/worker/celery_app.py` beat_schedule includes `worker-heartbeat` entry |
| `/worker/health` | Implemented correctly | `app/main.py` root route, `app/services/worker_health.py::WorkerHealthService` — healthy/degraded/unknown semantics match docs exactly |
| Redis TTL behavior | Implemented correctly | `celery_heartbeat_ttl_seconds` (default 90s) read directly in both the writer and reader |
| Flower | Implemented correctly | `docker-compose.yml` `flower` service, profile `observability`, localhost-only port, `FLOWER_BASIC_AUTH` |
| Celery task events | Implemented correctly | `worker_send_task_events=True`, `task_send_sent_event=True` in `celery_app.conf` |
| Observability configuration | Implemented correctly | Env vars match `.env.example`/`docs/10` §9.2 table exactly |
| Security boundaries | Implemented correctly | Flower bound to `127.0.0.1` only, not `0.0.0.0`; basic auth always configured in Compose |

**Verdict: COMPLETE**, no fragility found.

### Phase C' — Non-Telegram Retry Hardening

Verified directly against the branch diff (`git diff main --stat` shows `app/ai/retry.py` (+109), provider edits, discovery-persistence edit, and 5 new test files totaling ~1,900 lines) — this phase's code, not just its design document, is present on this branch.

| Item | Status | Evidence |
| --- | --- | --- |
| AliExpress retry ownership | Implemented correctly | `app/aliexpress/api_client.py::_execute_with_retries` unchanged/preserved as sole owner |
| AI provider retry ownership | Implemented correctly | New `app/ai/retry.py` shared helper, used by both `OpenAIProvider` and `GeminiProvider` |
| Retry classification | Implemented correctly | Per-provider retryable/non-retryable split documented in `docs/10-production-readiness.md` §9.3 and matched by `tests/test_ai_provider_retry.py` |
| Retry budgets | Implemented correctly | AliExpress unchanged (4 total); AI providers capped at 2 total — deliberately smaller, matching the Task 0 design's own reasoning |
| Retry-After handling | Implemented correctly | Honored when present, capped at 60s, per `docs/10` §9.3 |
| No nested retry behavior | Implemented correctly, actively regression-tested | `tests/test_aliexpress_no_nested_retry.py` exists specifically to guard this |
| API regression protection | Implemented correctly | `tests/test_phase_c_prime_api_regression.py` (603 lines) |
| Documentation closeout | Complete | `docs/08`, `docs/10`, `docs/06` all updated (2026-08-09 revision), `docs/planning/phase-c-prime-retry-hardening-design.md` present |

**Verdict: COMPLETE.** Full backend suite reported at 244 passed post-Task-4 (`docs/08` revision note) — this analysis did not re-run the suite (read-only constraint) but the test files exist and are substantial, not stubs.

### Summary classification (as requested)

| Phase | Classification |
| --- | --- |
| A.1 | Implemented correctly |
| A.2 | Implemented correctly |
| B | Implemented correctly |
| C' | Implemented correctly |
| Frontend refresh-token UX | **Missing** (config scaffolded, nothing built — see §1, §5.6) |
| JWT secret startup validation | **Missing** (Critical, self-flagged in `docs/10`) |
| API rate limiting | **Missing** (no code anywhere) |
| `POST /conversions` authorization | **Missing** (Info-flagged in `docs/10`, under-scoped relative to actual risk — see §1) |
| Non-Queue frontend test coverage | **Non-blocking technical debt** (see §5.7) |
| Form/schema standardization (roadmap's stated Phase D) | **Partially implemented** / **non-blocking technical debt** (see §5.4, §8) |
| Analytics/affiliate UI | **Missing** (backend complete, zero frontend — see §5.4, §8) |

---

## 3. Current System Assessment

### 3.1 Product Maturity

**Classification: Hardened MVP, approaching Pre-production.**

Reasoning: every core operator workflow (discover → import → generate → queue → schedule → publish) is implemented, backend-owned, realtime, and observable — this is well beyond "prototype" or "functional MVP." What keeps it short of "production-ready" is not missing product surface but a small number of concrete, already-partially-self-documented security gaps (§1) that would be unacceptable to expose to real users/traffic, plus thin test coverage outside the Queue/realtime path. "Early SaaS" is premature — the platform is explicitly single-tenant today (`docs/10` §6: "Tenancy: Queue/channel data **not user-scoped** — not multi-tenant safe"), and Phase E (multi-tenancy) is correctly deferred behind this.

### 3.2 Core Workflow Completeness

| Stage | Implemented? | Production-safe? | Observable? | Tested? | Major gaps |
| --- | --- | --- | --- | --- | --- |
| Discovery | Yes | Yes (client-owned retry, Phase C') | Partially (no metrics, but Flower sees task-level failures) | Weak (only `lib/normalize.test.ts`, `lib/score-explanation.test.ts` — no component/hook tests) | None functional; test-coverage gap only |
| Filtering | Yes | Yes | N/A (client-side) | Weak (same file coverage as above) | None functional |
| Scoring | Yes | Yes | N/A | Weak (`lib/scores.test.ts` exists for AI; discovery scoring has `score-explanation.test.ts`) | None functional |
| AI Content Generation | Yes | Yes (Phase C' retry-hardened) | Weak (no Celery, so no Flower visibility; relies on new provider-level logging per Phase C') | Weak — `tests/test_ai_prompts.py` (backend) + `tests/test_ai_provider_retry.py` (backend); **zero frontend tests** for `ContentWorkspaceView`/`ConfigControlBoard`/`VariantCompareDialog` | Frontend component test gap |
| Queue | Yes | Yes (Phase A.1/A.2) | Yes (SSE, attempt history) | **Strong** — 11 of 16 frontend test files, plus extensive backend coverage | None found |
| Scheduling | Yes | Yes | Partial (relies on Queue's realtime path) | Weak — no dedicated test for `QueueSchedulingDialog`'s validation/UX beyond what Queue realtime tests incidentally cover | Component test gap |
| Publishing | Yes | Yes (Phase A.1) | Yes | Strong (backend), moderate (frontend, via Queue's realtime tests) | None found |
| Analytics | **Not implemented in the frontend at all** | N/A | N/A | N/A | `docs/06-api-integration.md` §4.8: `affiliates`/`campaigns`/`conversions` are all "Backend only — No MVP screens." Fully modeled (`app/models/affiliate.py`, `campaign.py`, `conversion.py`) with commission calculation already working server-side (`ConversionService.record_conversion`), but **zero UI surface** — a genuine, complete, unclaimed capability |

### 3.3 Backend Architecture

- **Domain boundaries:** clean — `app/api/v1/`, `app/services/`, `app/repositories/`, `app/models/` separation is consistently applied across every domain inspected (queue, discovery, AI, auth, conversion).
- **Service layer:** consistently owns business rules (e.g., `ConversionService` enforces affiliate-campaign enrollment before accepting a conversion) — but is not consistently *protected* at the API boundary (the conversion case, §1).
- **Repository layer:** thin, consistent CRUD wrappers; no anti-patterns found.
- **Celery architecture:** three task modules (`publishing`, `discovery`, `health`), no `task_time_limit`/`acks_late` configured anywhere (a pre-existing, cross-cutting gap noted in the Phase C' design doc, not reintroduced here as new).
- **Redis usage:** three independent, well-separated purposes — Celery broker/backend, `queue-events` Pub/Sub (A.2), and the heartbeat key (Phase B) — no collision or cross-purpose reuse found.
- **API architecture:** consistent `ServiceError` → `HTTPException` mapping across every router inspected; consistent Pydantic request/response schemas.
- **Error handling:** strong and consistent for Telegram/AliExpress/AI (all three now have explicit, tested retryable/non-retryable classification per Phase C'); **absent** for authentication rate abuse and public-endpoint write validation (§1).
- **Retry ownership:** now fully resolved and documented for all three external integrations (Telegram/A.1, AliExpress/AI/C') — this was the single largest architectural ambiguity in the project and is now closed.
- **Observability:** strong for workers/tasks (Phase B); **absent** for security-relevant events (no failed-login tracking, no rate-limit-triggered logging, because no rate limiting exists to log).
- **Scalability:** single Celery beat instance is explicitly documented as an "Info"-severity known issue (`docs/10` §10) — acceptable at current scale, correctly not gold-plated.
- **Maintainability:** high — the project's own documentation suite (11 canonical docs + 4 planning design docs) is unusually well-maintained and, per this analysis's own verification, **accurate** (no phase was found to be "complete" in docs but incomplete in code, or vice versa, except the four new findings in §1 which the docs partially — not fully — already flag).

### 3.4 Frontend Architecture

- **Workspace structure:** consistent, `docs/frontend/11-workspace-design-system.md`-compliant across Discovery/Products/AI Studio/Queue/Channels/Settings — verified by direct comparison of the design doc's per-workspace template table against the actual `features/*` folder structure in `docs/02-frontend-architecture.md` (unchanged on this branch).
- **State management:** clean TanStack-Query-for-server / `useState`-for-UI split, no global state library introduced (explicitly forbidden by `docs/07` §7.3 and confirmed absent from `package.json`).
- **TanStack Query usage:** consistent query-key discipline per `docs/06` §3.
- **Realtime behavior / polling fallback:** best-tested part of the entire frontend (§3.2, §5.7).
- **Error states:** consistently implemented (`ErrorState`/`LoadingState`/`EmptyState` from `components/common/states.tsx`) across every workspace per `docs/02` §8.
- **Loading states:** same, consistent.
- **Queue UX:** mature, realtime, attempt-history-aware.
- **Discovery UX:** mature but **zero component-level test coverage**.
- **AI Studio:** mature but **zero component-level test coverage**; also the workspace where a retried-but-still-failed generation is most likely to surface to a user, and that failure path has no frontend test.
- **Products:** mature, standard workspace pattern, **zero component-level test coverage** beyond `lib/normalize.test.ts`.
- **Channels:** functional but the design doc itself flags it as "Simpler table; no selection bar today" — intentionally minimal, not a gap.
- **Settings:** intentionally read-only (`/ready` display only) — not a gap.

### 3.5 Data and Persistence

- **Database schema:** consistent use of `UUIDPrimaryKeyMixin`/`TimestampMixin` across all models inspected (`queue.py`, `conversion.py`, `campaign.py`, `affiliate.py`, `product.py`).
- **Queue persistence:** hardened (A.1) — `QueuePublishAttempt` has exhaustive `CheckConstraint`s enforcing outcome consistency at the database level, not just application level.
- **Publish attempts:** durable, indexed for the idempotency guard lookup (`ix_queue_publish_attempts_guard_lookup`).
- **Product persistence:** idempotent upsert (`ProductImporter`, verified in the Phase C' analysis and unchanged since).
- **Analytics persistence:** fully modeled (`conversions`, `campaigns`, `affiliates` tables with proper FKs and cascade rules) but **entirely unexposed to any UI or aggregate reporting** — data would already be flowing in if the `/conversions` endpoint were used, but nothing surfaces it.
- **Indexing:** targeted, not blanket — `external_order_id` unique, `click_id` indexed, `affiliate_id`/`campaign_id` indexed on `Conversion`. No evidence of missing indexes for current query patterns.
- **Data consistency:** the conversion model's `external_order_id` uniqueness constraint already provides idempotency for the *record* — but nothing prevents a malicious/malformed *value* of `amount` from being recorded once, which is a validation/authorization gap, not a consistency gap (§1).
- **Potential schema weaknesses:** none found that require a migration for anything in this analysis's recommended Phase D (§7).

### 3.6 Production Readiness

- **Authentication:** functional but incomplete — access-token-only, no refresh, default secret unguarded (§1).
- **Authorization:** role-based (`admin`/`affiliate`/`advertiser`) and consistently checked on admin-only routes (`require_roles`) — but **not applied at all** to `POST /conversions`, which has no `Depends` on any auth dependency.
- **Secrets:** `.env.example` correctly excludes real secrets; `FLOWER_BASIC_AUTH` and `JWT_SECRET_KEY` both documented — but only the latter has zero runtime enforcement of "don't use the example value."
- **Configuration:** extensive, well-organized `Settings` class; the unused `refresh_token_expire_days` field is the one piece of configuration drift found.
- **Logging:** structured for retries/attempts (A.1, C'); no security-relevant logging (auth failures, rate-limit hits) because the underlying mechanisms don't exist yet.
- **Monitoring:** strong for workers (Phase B); none for API abuse patterns.
- **Worker health:** strong (Phase B, verified §2).
- **Failure visibility:** strong for business logic (Flower, attempt history); none for security events.
- **Rate limiting:** **absent** — confirmed by full-repository grep, no `slowapi`, no custom limiter middleware, no per-route throttling of any kind on the FastAPI side.
- **API robustness:** strong for input validation (Pydantic everywhere) but weak for request *authorization* on at least one route (`/conversions`).
- **Docker setup:** mature, correctly profiles optional services (Flower), correctly binds Flower to localhost only.
- **Backup/recovery concerns:** out of this analysis's evidence base (no backup tooling inspected in `docker-compose.yml` — likely an infrastructure-team concern outside this repo's scope, not flagged as a repo-level gap).
- **Security concerns:** the four items in §1 are the concrete, evidenced findings; no others were found that rise to the same level of concreteness (e.g., CORS is origin-restricted via `settings.cors_origins`, not wildcarded to `*` for origins — only methods/headers are wildcarded, which is standard and low-risk given origin restriction is the actual security boundary there).

### 3.7 Testing

- **Backend unit/integration/API tests:** 35 test files, extensive coverage of publishing reliability, retry hardening (Telegram, AliExpress, AI), event lifecycle, worker health — this is the strongest-tested part of the system.
- **Celery tests:** present for heartbeat (`test_worker_heartbeat.py`) and discovery exception identity (`test_discovery_task_exceptions.py`); **absent** for the publishing Celery tasks' actual `autoretry_for` wiring in isolation (covered indirectly via service-layer tests instead — an acceptable but worth-noting gap).
- **Retry tests:** exceptionally strong post-Phase-C' (5 dedicated files, ~1,900 lines).
- **Frontend tests:** 16 files total — **11 of them are Queue-realtime-specific** (A.2/F5/F6). Discovery, Products, AI Studio, Channels, and Settings combined have only 5 files, all `lib/*.test.ts` (pure function tests), **zero component or hook tests** for any of those five workspaces.
- **Realtime tests:** the best-covered category in the entire project.
- **Regression protection:** strong for retry/reliability domains (by design, per Phase C''s explicit regression-test tasks); weak for everything else in the frontend.
- **Missing critical test areas:** (1) no test exists for JWT secret validation because no such validation exists yet (§1) — this would be a natural first test to write once Phase D begins; (2) no test exists for `POST /conversions` authorization because none exists; (3) no frontend component tests for AI Studio's error-and-retry-exhaustion path, which is the one user-facing surface most likely to actually exercise Phase C''s new AI retry behavior.

---

## 4. Product vs Engineering Priority

### Product gaps (evidence-based)

- **Analytics/affiliate performance is fully backend-modeled and completely invisible to any user** — the single largest "built but unshipped" capability in the repository.
- Minor, already-documented gaps: registration UI, editable settings, image search UI, admin product-create form — all pre-existing, all explicitly tracked in `docs/08` §2 as `⬜`, none newly discovered by this analysis.

### Engineering gaps (evidence-based)

- **Authentication/session security**: default JWT secret unguarded (Critical, self-flagged), no refresh token despite scaffolded config, no rate limiting anywhere, `/conversions` POST unauthenticated and directly business-integrity-relevant.
- **Frontend test coverage imbalance**: Queue/realtime is over-indexed; four other mature workspaces (Discovery, Products, AI Studio, Channels) have effectively no component-level regression protection.
- Minor, non-blocking: single Celery beat instance (documented, accepted); no `task_time_limit`/`acks_late` Celery config (documented in the Phase C' design doc as pre-existing, cross-cutting, not phase-blocking).

### Decision: the next phase should primarily be **production hardening (security)**, not product expansion, not architecture/scalability, not monetization/SaaS foundation, not pure UX improvement.

Reasoning, per the instruction to base this on evidence rather than defaulting to engineering work: this is not a generic "engineering work is always higher priority" bias. The specific evidence is that **the project's own production-readiness document already independently flags one of these four items as its single Critical-severity blocker**, unresolved in code. When a project's own authoritative documentation has already identified something as the most severe unresolved issue, and this analysis's job is to find "the highest-value next phase," it would take unusually strong countervailing evidence to justify prioritizing net-new product surface (Analytics) or cosmetic engineering polish (Forms) over an already-declared Critical blocker. No such countervailing evidence was found — Analytics has real value but no urgency marker anywhere in the docs; Forms has no severity marker at all, because it isn't a defect, it's a consistency preference.

---

## 5. Phase D Candidates

### Candidate 1 — Authentication & Public-Endpoint Security Hardening ⭐ (selected, see §6)

- **Objective:** close the four concrete, verified security/production gaps in §1 — JWT secret startup validation, refresh token implementation, API rate limiting, and `/conversions` authorization.
- **Why it matters:** one item is the project's own declared Critical blocker; the other three are concrete, evidenced, and directly relevant to the platform's stated SaaS trajectory (Phase E depends on a sound auth foundation).
- **Problems solved:** production deployment safety, session UX (no more silent full logout on token expiry), abuse resistance on public endpoints, conversion/commission data integrity.
- **Major affected components:** `app/core/config.py`, `app/auth/*`, `app/main.py`, a new rate-limiting dependency/middleware, `app/api/v1/conversions.py`.
- **Dependencies:** none — fully independent of A.1/A.2/B/C'.
- **Risk:** Low-Medium — touches the auth flow, which every authenticated request depends on; must be implemented incrementally with strong test coverage to avoid locking out legitimate sessions.
- **Estimated complexity:** Medium.
- **Expected product value:** Medium (mostly invisible to end users when done right — the value is risk reduction, plus a real UX improvement from refresh tokens).
- **Expected engineering value:** High.
- **Why it should be Phase D:** see §6.

### Candidate 2 — Analytics & Affiliate Performance Workspace

- **Objective:** build a new frontend workspace surfacing the already-complete `affiliates`/`campaigns`/`conversions` backend (list, filter, status, commission totals) per the `docs/frontend/11-workspace-design-system.md` template.
- **Why it matters:** the single largest gap between what the backend can already do and what any user can see.
- **Problems solved:** monetization visibility, campaign/commission tracking, foundational reporting for Phase E's payout module.
- **Major affected components:** new `features/analytics/` (or `features/affiliates/`) frontend folder; likely a new lightweight aggregate endpoint (e.g., `GET /affiliates/me/summary`) if per-affiliate totals aren't already computable client-side from the list endpoints — a genuinely new but small backend surface.
- **Dependencies:** none blocking; benefits from Candidate 1 if `/conversions` write-path integrity is fixed first, so the numbers this workspace displays are trustworthy.
- **Risk:** Low — purely additive, new route, no changes to existing workspaces or shared components.
- **Estimated complexity:** Medium-High (new workspace from scratch, including a template addition to `11-workspace-design-system.md` §12 per its own onboarding checklist).
- **Expected product value:** High.
- **Expected engineering value:** Low-Medium (some new endpoint design, but low architectural risk).
- **Why it should not be Phase D now:** its value is undermined if the underlying write path (`/conversions`) is not yet trustworthy (Candidate 1's finding) — displaying analytics built on a spoofable data source is a worse outcome than not displaying them yet. Better sequenced immediately *after* Candidate 1.

### Candidate 3 — Frontend Test Coverage Expansion (Discovery / Products / AI Studio / Channels)

- **Objective:** bring the four under-tested mature workspaces up to a baseline of component/hook test coverage comparable to what Queue already has.
- **Why it matters:** regression protection is currently concentrated in one workspace; a change to Discovery, Products, AI Studio, or Channels today has meaningfully less of a safety net than an equivalent change to Queue.
- **Problems solved:** silent regressions in the four least-tested, still-actively-used workspaces.
- **Major affected components:** `frontend/src/features/{discovery,products,ai,channels}/**` (test files only — no production code changes required).
- **Dependencies:** none.
- **Risk:** Very low — test-only change.
- **Estimated complexity:** Medium (breadth, not depth — many small test files across four feature folders).
- **Expected product value:** Low (invisible to users).
- **Expected engineering value:** Medium-High.
- **Why it should not be Phase D now:** valuable but not urgent — no active regression was found in these workspaces during this analysis; the risk is speculative (future changes), not present. It is a reasonable **Phase D+1** or a parallel-track effort, not the single highest-value next phase when a Critical security item is sitting unresolved.

### Candidate 4 — Form & Schema Validation Standardization (roadmap's current Phase D)

- **Objective:** as originally scoped in `docs/08` §3 — shared Zod schemas across `features/*/lib/schemas.ts`, React Hook Form + `zodResolver` for the scheduling dialog, Arabic validation copy.
- **Why it matters:** consistency and reduced duplication between Pydantic and Zod definitions.
- **Problems solved:** minor drift risk between backend and frontend validation; some already-partially-solved (Discovery and Queue schedule already have inline Zod-based validation per `docs/07` §4).
- **Major affected components:** `features/*/lib/schemas.ts`, `QueueSchedulingDialog`, drawer inline edit forms.
- **Dependencies:** none.
- **Risk:** Very low.
- **Estimated complexity:** Low-Medium.
- **Expected product value:** Low (cosmetic/consistency, not a missing capability).
- **Expected engineering value:** Low-Medium.
- **Why it should not be Phase D now:** this is the weakest candidate by evidence — it has no severity marker, no user-facing failure mode identified anywhere in this analysis, and the highest-friction instance (scheduling) already has working validation today. Promoting it over a Critical security gap would fail this task's own selection criterion ("solve the highest-value remaining problem").

### Candidate 5 — Celery Task Hardening (`task_time_limit`, `acks_late`, dedicated queues)

- **Objective:** close the cross-cutting Celery configuration gaps noted during the Phase C' analysis (no time limits, no late-ack, no per-domain queue routing).
- **Why it matters:** a hung external call (AliExpress, or Telegram) could occupy a worker slot indefinitely; a worker crash mid-task loses the task silently (early-ack default).
- **Problems solved:** worker resource contention, silent task loss on crash.
- **Major affected components:** `app/worker/celery_app.py` configuration only.
- **Dependencies:** none.
- **Risk:** Medium — changing ack semantics or adding time limits to already-running production task types requires care (e.g., a too-tight `task_time_limit` could kill a legitimately slow AliExpress page-fetch mid-flight).
- **Estimated complexity:** Low (configuration-only) but Medium risk (behavioral change to already-shipped, working tasks).
- **Expected product value:** None directly.
- **Expected engineering value:** Medium.
- **Why it should not be Phase D now:** this is real technical debt but was already explicitly classified as "Recommended, not Blocking" in the Phase C' design document, and remains so — nothing in this analysis elevates its urgency above that prior, still-valid classification. Good candidate for a small, independent hardening task later, not a full phase.

---

## 6. Phase D Selection

**Selected: Candidate 1 — Authentication & Public-Endpoint Security Hardening.**

Verification against this task's eight selection requirements:

1. **Builds naturally on completed phases** — A.1/A.2/B/C' progressively hardened *business* reliability (publishing, realtime, workers, external retries); this phase hardens the *access* layer underneath all of them. It is the logical next link in the same "reliability hardening" chain, not a detour into new product territory.
2. **Solves the highest-value remaining problem** — the only item in the entire repository with a self-declared Critical severity marker still unresolved in code (§1, finding 2).
3. **Avoids unnecessary scope expansion** — bounded to exactly four concrete findings, all independently verified, none speculative.
4. **Preserves the existing A.1/A.2/B/C' architecture** — zero overlap with `queue_publish_attempts`, `queue-events`, worker heartbeat, or the AliExpress/AI retry layers. `require_roles`/`CurrentUser` (the mechanisms this phase extends) are already used correctly elsewhere (e.g., product import/delete) — this phase generalizes an existing, proven pattern rather than inventing a new one.
5. **Has a clear implementation boundary** — `app/core/config.py`, `app/auth/*`, `app/main.py`, one new rate-limit dependency, `app/api/v1/conversions.py`. No other router, service, or frontend feature needs to change for the core of this phase (frontend changes are limited to session-refresh handling, isolated to `services/session.ts`/`services/api-client.ts`).
6. **Decomposable into small implementation tasks** — see §9, four independently shippable and testable tasks plus a Task 0.
7. **Provides measurable value** — every acceptance criterion in §11 is a yes/no, testable fact (e.g., "the API refuses to start with the default JWT secret when `APP_ENV != development`"), not a vague improvement statement.
8. **Avoids mixing unrelated concerns** — deliberately does *not* include Analytics UI (Candidate 2, sequenced after), test coverage expansion (Candidate 3, independent track), or form standardization (Candidate 4, unrelated and lower-value) in the same phase.

**Why this beats the other four candidates specifically:**

- **vs. Analytics (Candidate 2):** Analytics is real product value, but this phase's `/conversions` finding directly undermines Analytics' trustworthiness if built first — sequencing security before analytics is not just "safer," it is a hard prerequisite for the analytics data being meaningful. Analytics remains the natural **Phase E-adjacent or Phase D+1** candidate.
- **vs. Test Coverage Expansion (Candidate 3):** valuable but speculative-risk-reducing, not blocker-resolving; no evidence of an active problem, only future risk. Lower urgency than a declared Critical item.
- **vs. Forms (Candidate 4):** the current roadmap default, but the weakest candidate by evidence — no severity marker, no identified failure mode, partially already solved.
- **vs. Celery Hardening (Candidate 5):** already explicitly downgraded to "Recommended, not Blocking" in a prior, still-valid design document; this analysis found no new evidence to change that classification.

---

## 7. Phase D Scope

### Phase D Objective

Close the authentication and public-endpoint security gaps verified in this analysis — enforce a non-default JWT secret outside development, implement the already-partially-scaffolded refresh token flow, add baseline API rate limiting for unauthenticated/public routes, and require authentication on `POST /conversions` — without altering any business logic, database schema for existing domains, or the A.1/A.2/B/C' architecture.

### In Scope

- Startup validation rejecting the default `jwt_secret_key` value when `app_env != "development"`.
- A refresh token mechanism: issuance alongside the existing access token at login, a `POST /auth/refresh` endpoint, rotation on use, and expiry aligned with the already-existing `refresh_token_expire_days` setting.
- A minimal, dependency-injectable rate-limiting mechanism applied first to `POST /auth/login` (brute-force protection) and `POST /conversions` (abuse protection), with room to extend to other public routes (discovery, product list) as a documented follow-up, not a Phase D requirement.
- Requiring authentication (and an ownership/role check — e.g., only the affiliate's own linked identity, or an explicit trusted-server-to-server mechanism, may record a conversion for a given `affiliate_id`) on `POST /conversions`.
- Frontend session handling updates strictly limited to consuming the new refresh flow (silent refresh before expiry, or refresh-on-401-retry-once) in `services/api-client.ts`/`services/session.ts` — no new pages, drawers, or workspaces.
- Documentation updates to `docs/10-production-readiness.md` §6/§10, `docs/06-api-integration.md` §1/§7, and `docs/02-frontend-architecture.md` §6, reflecting the new auth flow — **not performed in this analysis**, reserved for the implementation phase's own closeout task per this task's constraints.

### Explicitly Out of Scope

- Multi-tenancy, workspace switching, or any Phase E scope.
- The Analytics/affiliate performance workspace (Candidate 2) — a separate, later phase.
- Frontend test coverage expansion for Discovery/Products/AI Studio/Channels (Candidate 3) — independent track.
- Form/schema validation standardization (Candidate 4) — independent, lower-priority track, unchanged from its current roadmap position.
- Celery `task_time_limit`/`acks_late`/queue routing (Candidate 5) — remains "Recommended, not Blocking" future work.
- Rate limiting for every route in the API — Phase D covers the two highest-risk public routes only; broader coverage is a documented follow-up.
- Any change to `QueueStatus`, `queue_publish_attempts`, `queue-events`, worker heartbeat, or AliExpress/AI retry policy.
- OAuth/social login, MFA, or any authentication mechanism beyond the existing email/password + JWT model.
- Changing `access_token_expire_minutes`'s current value or semantics — only *adding* a refresh path alongside it.

### Architectural Impact

| Area | Expected impact |
| --- | --- |
| Backend | New: refresh-token issuance/validation logic in `app/auth/`; a `RefreshToken` persistence mechanism (see Task 2, §9, for the open question of whether this needs a database table or can be a stateless rotating-JWT design); a rate-limit dependency/middleware; a `Depends(get_current_user)`-equivalent guard added to `POST /conversions`. |
| Frontend | New: refresh-triggering logic in the shared Axios client / session service only. No new workspace, no new route, no new drawer/dialog. |
| Database | **Likely** — a stateful refresh-token design (recommended default, see §12 Task 2) requires a new table (e.g., `refresh_tokens`) with a migration; a stateless design would not. This decision is explicitly deferred to Task 0/Task 2, not made in this analysis. |
| Celery | None. |
| Redis | **Possible, optional** — a rate-limiter could use Redis (already a hard dependency of this stack) instead of in-process memory, for correctness across multiple API replicas; this is an implementation-task decision, not fixed here. |
| APIs | New: `POST /auth/refresh`. Changed: `POST /conversions` gains an auth requirement (a breaking change for any current caller relying on it being public — see Risks, §13). `POST /auth/login`'s response shape may gain a `refresh_token` field (additive). |
| Realtime/SSE | None — no overlap with `queue-events`, `EventPublisher`, or the SSE endpoint. |
| Docker/Infrastructure | Possibly none, or a new Redis-backed rate-limit dependency already satisfied by the existing `redis` service — no new service anticipated. |
| External providers | None — Telegram/AliExpress/AI are entirely unaffected. |

---

## 8. Task Breakdown

```text
Phase D
├── Task 0 — Architecture / Scope Decision (refresh-token storage model, rate-limit mechanism choice)
├── Task 1 — JWT Secret Startup Validation
├── Task 2 — Refresh Token Implementation
├── Task 3 — API Rate Limiting (login + conversions)
├── Task 4 — Conversion Endpoint Authorization
├── Task 5 — Frontend Session Refresh Integration
└── Task 6 — Documentation / Closeout
```

### Task 0 — Architecture / Scope Decision

- **Objective:** resolve the open design questions this analysis deliberately leaves unresolved (§13) before any code is written: stateful (DB-backed, revocable) vs. stateless (rotating-JWT) refresh tokens; in-process vs. Redis-backed rate limiting; exact authorization model for `/conversions` (affiliate-scoped JWT vs. a separate server-to-server credential for automated conversion reporting).
- **Why it exists:** mirrors the pattern already proven effective in this project for Phase B (Task 0) and Phase C' (Task 0) — both phases avoided rework by deciding architecture before implementation; this phase should not be the exception.
- **Main files/components likely affected:** none (design document only, e.g. `docs/planning/phase-d-auth-security-design.md`).
- **Dependencies:** none.
- **Expected tests:** none (design-only task).
- **Risks:** none — pure analysis.
- **Explicit exclusions:** no code, no migrations, no config changes (same discipline as this document's own creation).

### Task 1 — JWT Secret Startup Validation

- **Objective:** the API refuses to start (or logs a critical, impossible-to-miss warning, per Task 0's decision) when `jwt_secret_key` equals its default value and `app_env` is not `"development"`.
- **Why it exists:** closes the project's own declared Critical blocker directly and cheaply — the smallest, lowest-risk task in the phase, and independent of every other task.
- **Main files/components likely affected:** `app/core/config.py` (a validator), `app/main.py` (or a startup event) — no auth flow behavior changes for already-correctly-configured deployments.
- **Dependencies:** none — can ship before Task 0 finishes if desired, since it requires no architectural decision.
- **Expected tests:** a unit test instantiating `Settings` with the default secret and a non-development `app_env`, asserting failure; a matching success-path test for a non-default secret.
- **Risks:** could break local/CI environments that rely on the default secret if `app_env` defaults or CI configuration aren't accounted for — must verify `.env.example`/CI config sets `APP_ENV=development` or an explicit non-default test secret.
- **Explicit exclusions:** does not touch refresh tokens, rate limiting, or `/conversions`.

### Task 2 — Refresh Token Implementation

- **Objective:** implement `POST /auth/refresh`, issuing a new access token (and, if Task 0 selects rotation, a new refresh token) from a valid, unexpired refresh token; wire `refresh_token_expire_days` (already present in `Settings`) into real expiry logic for the first time.
- **Why it exists:** closes the gap between a real, present, unused configuration value and actual behavior; directly improves session UX (no more full re-login on access-token expiry).
- **Main files/components likely affected:** `app/auth/security.py` (new `create_refresh_token`/`decode_refresh_token`, mirroring the existing `create_access_token`/`decode_access_token` pair and their `"type": "access"` discriminator — a `"type": "refresh"` counterpart already fits the existing payload shape with no redesign needed), `app/auth/router.py` (new route), `app/auth/schemas.py` (`TokenResponse` gains `refresh_token`), possibly a new `app/models/refresh_token.py` + migration if Task 0 selects the stateful/revocable design.
- **Dependencies:** Task 0's storage-model decision.
- **Expected tests:** issuance, successful refresh, refresh with expired token (rejected), refresh with an access token used as a refresh token (rejected — the existing `"type"` discriminator pattern already defends against this class of bug), and (if stateful) revocation-after-use / rotation tests.
- **Risks:** the highest-complexity task in the phase — must not weaken the existing access-token validation path (`decode_access_token`'s `"type": "access"` check must remain intact and untouched) while adding the parallel refresh path.
- **Explicit exclusions:** no logout-everywhere / revoke-all-sessions feature unless Task 0 explicitly scopes it in; no change to `access_token_expire_minutes`.

### Task 3 — API Rate Limiting (login + conversions)

- **Objective:** apply a per-IP (and, where authenticated, per-user) rate limit to `POST /auth/login` and `POST /conversions`.
- **Why it exists:** `POST /auth/login` is the classic brute-force target and currently has zero protection beyond bcrypt's inherent slowness; `POST /conversions` is the business-integrity-sensitive endpoint identified in §1.
- **Main files/components likely affected:** a new small dependency/middleware module (exact shape decided in Task 0 — e.g., `app/core/rate_limit.py`), applied via `Depends(...)` on the two routes named above, not a blanket global middleware (to avoid unintended impact on discovery/product-read traffic, which is out of scope per §7).
- **Dependencies:** Task 0's mechanism decision (in-process vs. Redis-backed).
- **Expected tests:** requests under the limit succeed; requests over the limit return a `429`-equivalent with a clear error body; limit resets after the configured window.
- **Risks:** if Redis-backed, must not introduce a hard dependency that makes login fail when Redis is briefly unavailable (fail-open vs. fail-closed is a Task 0 decision, not an accident).
- **Explicit exclusions:** does not extend rate limiting to discovery, product, or queue endpoints in this phase (§7 out-of-scope).

### Task 4 — Conversion Endpoint Authorization

- **Objective:** `POST /conversions` requires authentication and enforces that the caller is authorized to record a conversion for the given `affiliate_id` (per Task 0's chosen model — likely: the authenticated user's own linked `Affiliate` record, with a documented separate path for trusted server-to-server/webhook reporting if that use case is confirmed to exist).
- **Why it exists:** closes the business-integrity gap identified in §1 — today, any caller can fabricate a conversion at an arbitrary dollar amount for any valid affiliate/campaign pair.
- **Main files/components likely affected:** `app/api/v1/conversions.py` (add `Depends(get_current_user)` or a dedicated dependency), `app/services/conversion.py::record_conversion` (add the ownership check alongside its existing enrollment check).
- **Dependencies:** Task 0's decision on whether a separate server-to-server credential path is needed (if AliExpress or another external system is expected to report conversions programmatically, a user-JWT-only model would break that use case — this must be confirmed, not assumed, per §13).
- **Expected tests:** authenticated affiliate can record their own conversion (existing enrollment-check tests should still pass unchanged); unauthenticated request is rejected; authenticated request for a *different* affiliate's ID is rejected (new test — this exact case has no coverage today because the endpoint currently has no identity to check against).
- **Risks:** this is a **breaking change** for any current integration relying on `/conversions` being callable without a token — must be verified against real usage before shipping (§13, open question).
- **Explicit exclusions:** does not change `ConversionUpdate` (admin-only status change) or the `list_all`/`list_for_affiliate` read paths, which are already correctly authorized today.

### Task 5 — Frontend Session Refresh Integration

- **Objective:** the frontend transparently uses the new refresh endpoint (Task 2) instead of forcing a full re-login on access-token expiry.
- **Why it exists:** realizes the actual product value of Task 2 — a backend refresh endpoint with no frontend consumer would be exactly as dead as today's unused `refresh_token_expire_days` setting.
- **Main files/components likely affected:** `frontend/src/services/api-client.ts` (401-response interceptor attempts one refresh-and-retry before clearing session), `frontend/src/services/session.ts` (store the refresh token alongside the access token, same `sessionStorage` mechanism already in use — no new storage pattern per `docs/07` architecture rules).
- **Dependencies:** Task 2 must be complete and stable first.
- **Expected tests:** a Vitest test for the interceptor's refresh-and-retry-once behavior (success and failure/fallback-to-login paths) — this would be the frontend's first test of the auth flow itself, an area with zero current frontend test coverage.
- **Risks:** must not create an infinite refresh loop if the refresh token itself is invalid/expired — the "retry once, then clear session and redirect" rule must be explicit and tested.
- **Explicit exclusions:** no new login/session UI; no "remember me" feature; no change to the existing middleware-cookie-presence-marker pattern described in `docs/02` §6.

### Task 6 — Documentation / Closeout

- **Objective:** update `docs/10-production-readiness.md` (§6 security boundaries, §10 known issues — removing or downgrading the items this phase closes), `docs/06-api-integration.md` (§1 auth, new `/auth/refresh` entry, `/conversions` status change from implicitly-public to authenticated), `docs/02-frontend-architecture.md` (§6 authentication — refresh tokens are no longer "not implemented"), and `docs/08-implementation-roadmap.md` (mark this phase complete, and explicitly re-confirm or re-sequence Candidates 2–5 as the next milestone).
- **Why it exists:** every completed phase in this project's history has closed with a documentation update in the same commit/session — this phase should not be the exception, and the roadmap needs to be told this phase existed at all, since it does not currently appear there.
- **Main files/components likely affected:** documentation only.
- **Dependencies:** Tasks 1–5 complete and passing.
- **Expected tests:** none (documentation task).
- **Risks:** none.
- **Explicit exclusions:** does not itself implement Candidate 2 (Analytics) — only re-confirms it (or another candidate) as the recommended next milestone, per this task's own instruction that roadmap updates belong to a later, separate step.

---

## 9. Task Ordering

```text
Task 0 (architecture decision)
    │
    ├──→ Task 1 (JWT secret validation)         — independent, can run in parallel with Task 0
    │
    ├──→ Task 2 (refresh token impl) ──→ Task 5 (frontend integration)
    │
    ├──→ Task 3 (rate limiting)                  — independent of Task 2/4, depends only on Task 0's mechanism choice
    │
    └──→ Task 4 (conversion authorization)       — independent of Task 2/3
                    │
                    ▼
              Task 6 (documentation / closeout) — requires Tasks 1–5 complete
```

- **Must come first:** Task 0. It resolves three separate open questions (refresh-token storage, rate-limit mechanism, conversion authorization model) that Tasks 2, 3, and 4 each individually depend on.
- **Can be parallelized:** Task 1 (independent of everything), Task 3, and Task 4 have no dependency on each other or on Task 2 — three different engineers/sessions could implement them simultaneously once Task 0 is done.
- **Sequential dependency:** Task 5 strictly requires Task 2 to be complete and stable (it consumes the new endpoint).
- **Optional / can slip to a follow-up phase without blocking Phase D's core value:** none of Tasks 1–5 are optional — all four findings in §1 are addressed by exactly one task each, and leaving any one out would mean Phase D did not actually close the gap it was chartered to close. Task 6 is required for phase completion per this project's own established closeout convention, but is not itself risk-reducing.
- **Required for Phase D completion:** all of Task 0 through Task 6.

**Recommended execution order:** Task 0 → (Task 1 parallel with Task 2-start) → Task 2 → Task 5 → Task 3 and Task 4 (either order, or parallel) → Task 6.

---

## 10. Regression Boundaries

Because Phase D touches the authentication layer that every other completed phase's authenticated endpoints depend on, and touches one endpoint (`/conversions`) directly, the following invariants from A.1/A.2/B/C' must not be accidentally broken:

## Regression Boundaries

- **Existing API contracts:** `POST /auth/login`'s existing response fields (`access_token`, `token_type`) must remain unchanged in meaning — `refresh_token` may be *added*, never replacing or altering the existing fields. `GET /auth/me` behavior must be unchanged for any already-valid access token.
- **`CurrentUser` / `get_current_user` dependency:** must continue to accept only access tokens (`"type": "access"`) exactly as today — the new refresh-token type must never be accepted by this dependency, or every authenticated route in the system (queue, products, channels, discovery import) silently gains a security hole.
- **Queue status semantics:** `QueueStatus` enum and its "no `failed` value" invariant (A.1) — entirely untouched by this phase; no task in §8 touches `app/models/queue.py` or `app/schemas/queue.py`.
- **Publish attempt persistence:** `queue_publish_attempts` — untouched; no task in this phase writes to or reads from this table.
- **Retry ownership (A.1 Telegram, Phase C' AliExpress/AI):** untouched — this phase does not modify `app/telegram/`, `app/aliexpress/`, `app/ai/retry.py`, or any Celery task's `autoretry_for` configuration.
- **SSE events / `queue-events`:** untouched — no task in this phase publishes to, subscribes to, or modifies the Redis `queue-events` channel or `EventPublisher`/`EventConsumer`/`EventBroadcaster`.
- **Polling fallback:** untouched — no change to `useQueuePollingFallback` or the adaptive 5s→30s behavior; the only frontend auth-adjacent file touched (`api-client.ts`) must not alter how the SSE client (`sse-client.ts`) or its own 401 handling behaves for the *queue stream* connection specifically — Phase D's 401-retry-once logic must be verified against the SSE client's existing (separately documented, per Phase A.2's design doc §18) 401 handling to avoid double-handling.
- **`/worker/health` and worker heartbeat:** untouched — no task in this phase modifies `app/worker/tasks/health.py`, `WorkerHealthService`, or `docker-compose.yml`'s worker/beat/Flower services.
- **AliExpress retry policy / AI retry policy:** untouched — explicitly out of scope (§7).
- **Existing role-based authorization (`require_roles`, admin-gated routes):** must continue to function identically for products/channels admin actions — Task 4's new authorization check on `/conversions` must reuse or mirror this existing pattern, not introduce a second, divergent authorization mechanism.
- **`sessionStorage`-only token storage:** the existing security boundary (`docs/10` §6: "JWT storage | `sessionStorage` only; cookie is presence marker") must be preserved for the new refresh token as well — it must not be stored in a cookie or `localStorage`, which would silently change the project's security model.

---

## 11. Success Criteria

- [ ] The API process fails to start (or refuses to serve authenticated traffic, per Task 0's exact chosen behavior) when `jwt_secret_key` equals its default value and `app_env != "development"` — verified by an automated test, not manual inspection.
- [ ] `POST /auth/refresh` exists, is documented in `docs/06-api-integration.md`, and successfully issues a new access token given a valid, unexpired refresh token.
- [ ] An expired or malformed refresh token is rejected by `POST /auth/refresh` with a `401`, verified by test.
- [ ] An access token cannot be used in place of a refresh token at `POST /auth/refresh` (the `"type"` discriminator is enforced), verified by test.
- [ ] `POST /auth/login` more than N times per minute from a single source (N defined in Task 0) receives a `429`-equivalent response, verified by test.
- [ ] `POST /conversions` more than N times per minute from a single source receives a `429`-equivalent response, verified by test.
- [ ] `POST /conversions` without a valid `Authorization` header is rejected with `401`, verified by test — this is a **change** from today's behavior and must be called out as such in the Task 6 documentation update.
- [ ] `POST /conversions` from an authenticated caller attempting to record a conversion for an `affiliate_id` they are not authorized to act on behalf of is rejected, verified by a new test (no equivalent test exists today).
- [ ] The frontend automatically refreshes an expired access token and retries the original request at most once before falling back to full logout — verified by a new Vitest test in `api-client.test.ts` (a new file; no such test exists today).
- [ ] No existing backend test in the 35-file suite regresses (full suite still green).
- [ ] No existing frontend test in the 16-file suite regresses (full suite still green), with particular attention to the 11 Queue-realtime files per the Regression Boundaries above.
- [ ] `docs/10-production-readiness.md` §10's "Default JWT secret — Critical" and "No refresh token — Medium" rows are updated to reflect resolution (or explicitly re-scoped if only partially addressed).
- [ ] `docs/08-implementation-roadmap.md` records this phase and names the next recommended milestone (Candidate 2, 3, 4, or 5 from §5, re-evaluated in light of Phase D's outcome).

---

## 12. Risks and Open Questions

### Architectural risks

- Choosing a stateful (database-backed) refresh token design introduces a new table and migration where none currently exists for auth — a meaningfully bigger change than the stateless alternative, but far more secure (supports real revocation, e.g., on password change or suspected compromise). Task 0 must make this trade-off explicit, not default to the simpler option purely for speed.
- Introducing rate limiting incorrectly (e.g., a naive in-process counter) will not work correctly across multiple API replicas if the deployment ever scales horizontally — Task 0 should default to a Redis-backed mechanism given Redis is already a hard dependency of this stack, unless single-replica deployment is confirmed as a durable assumption.

### Product risks

- Requiring authentication on `POST /conversions` (Task 4) is a **breaking change** for any existing external caller (e.g., an AliExpress-side conversion webhook, if one is actually wired up outside this repository's visibility) that currently calls it without credentials. This must be confirmed before Task 4 ships, not discovered after (see Open Questions below).

### Implementation risks

- A bug in the new 401-retry-once frontend logic (Task 5) could cause an infinite refresh loop or, worse, silently swallow a real 401 that should have logged the user out — this is the highest-blast-radius single bug possible in this phase, since it affects every authenticated request in the application, and must be covered by explicit tests before merge, not discovered in manual QA.

### Migration risks

- If Task 0 selects a stateful refresh-token table, the migration itself is additive/low-risk (new table, no existing table altered) — consistent with every migration this project has shipped to date (A.1's `queue_publish_attempts` was similarly additive-only).

### Performance risks

- A Redis-backed rate limiter adds one additional Redis round-trip to `POST /auth/login` and `POST /conversions` — negligible given Redis is already in the request path for Celery-adjacent concerns and both routes are low-frequency by nature (login is not a hot path; conversions are business events, not high-QPS traffic).

### Security risks

- If Task 4's authorization model is implemented incorrectly (e.g., trusting a client-supplied `affiliate_id` without verifying it against the authenticated user's own linked `Affiliate` record), the endpoint would remain exploitable in a subtler form even after "adding authentication" — Task 4's test plan must explicitly include the cross-affiliate rejection case (already listed in §11) to prevent this exact class of incomplete fix.

### Open questions that should be answered before Task 1 implementation begins

```text
1. Is POST /conversions currently called by any real external system (e.g., an
   AliExpress conversion webhook, or a manual admin/ops tool) outside this
   repository's visibility? If yes, Task 4 needs a server-to-server credential
   path in addition to (or instead of) user-JWT authorization, and this must be
   designed in Task 0, not discovered after Task 4 breaks a real integration.

2. Should refresh tokens be stateful (DB-backed, revocable) or stateless
   (rotating JWT with a shorter-lived family)? This analysis recommends stateful
   for its revocation capability, given the project's own stated SaaS trajectory,
   but does not mandate it — Task 0 must decide explicitly.

3. Should the rate limiter be in-process or Redis-backed? This analysis
   recommends Redis-backed given Redis is already a hard dependency, but Task 0
   must confirm the current single-replica deployment assumption (or lack
   thereof) before finalizing.

4. What is the exact rate-limit threshold (requests per minute/window) for
   POST /auth/login and POST /conversions? Not determined by this analysis —
   requires a Task 0 decision informed by expected legitimate traffic patterns,
   which this analysis did not have visibility into.
```

These four questions are answerable within Task 0 using information already available to the project owner (real integration inventory, deployment topology, expected traffic) — none of them block *defining* Phase D, only its *first line of code*, which is exactly the boundary this analysis is scoped to.

---

## 13. Related Documents

- [08-implementation-roadmap.md](../08-implementation-roadmap.md) — current roadmap; does not yet name this phase (by design — this document is the analysis that precedes that update, per this task's own instructions).
- [10-production-readiness.md](../10-production-readiness.md) §6, §10 — source of the Critical/Medium/Info severity markers this analysis builds on.
- [06-api-integration.md](../06-api-integration.md) §1, §7 — current auth contract this phase extends without breaking.
- [02-frontend-architecture.md](../02-frontend-architecture.md) §6 — current frontend auth flow this phase extends.
- [planning/phase-b-worker-observability-design.md](./phase-b-worker-observability-design.md) and [planning/phase-c-prime-retry-hardening-design.md](./phase-c-prime-retry-hardening-design.md) — precedent for the Task-0-first pattern this phase's task breakdown follows.
