# Production Readiness and Release Runbook

**Document Version:** 3.1  
**Last Updated:** 2026-09-04

**2026-09-04 revision (CI hardening):** GitHub Actions Ruff step is `ruff check .` on first-party Python (vendored `iop/` excluded). Playwright smoke is job `e2e` (API-mocked; not a required branch-protection check yet). See §3, §9.5.

**2026-09-04 revision (Phase E Tasks 9–11 closeout):** Workspace runtime, image search global scope, click tracking public endpoint, migration `014_add_clicks`, click rate limit, and live-verified Task 11 behavior. See §6, §9.7.

Release gate supplement to documents 01–09. Defines security boundaries, environment configuration, CI/CD, deployment checklists, and architectural requirements.

**2026-08-04 revision:** Phase A.1 is now complete end-to-end (backend Tasks 1–9 + frontend data-source swap). Three post-implementation bugs surfaced and were fixed during hardening — see §10 for details: scheduled publishing (Celery event-loop reuse), queue item deletion (attempt cascade), and Telegram long-message publishing (4096/1024-char limits).

**2026-08-08 revision:** Phase A.2 realtime queue streaming is COMPLETE. §9.1 updated to the shipped SSE + Redis EventConsumer/EventBroadcaster architecture, polling fallback, and ops notes. This does **not** claim the entire application is production-ready.

**2026-08-08 revision (Phase B closeout):** Phase B worker/Beat health + Flower observability is COMPLETE. §2 Docker services and §9.2 updated to the shipped heartbeat, `GET /worker/health`, and optional Flower profile. Automated paging/alerts remain future ops work.

**2026-08-13 revision (Phase D closeout):** Authentication & public-endpoint security COMPLETE. §6 / §9.6 / §10 updated for JWT validation, refresh tokens, route rate limits, and conversion authorization. Design: [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

**2026-08-14 revision (Form & schema validation closeout):** §9.4 updated to the shipped frontend Zod/RHF standardization. UX/input validation only — not a security boundary; backend contracts unchanged.

**2026-08-19 revision (Phase E Task 7):** Product remains a global shared catalog; Affiliate remains a global user-owned 1:1 profile. `POST /affiliates/join-campaign` requires `X-Workspace-Id`. See §6 tenancy row.

**2026-08-19 revision (Phase E Task 8):** Stage-1 nullable `workspace_id` on campaigns, queue items, and Telegram channels is closed (migration `013`: NOT NULL, `ON DELETE RESTRICT`, fail-closed if NULL rows remain). No automatic bootstrap-workspace backfill.

---

## 1. Required Environment

### Backend

- PostgreSQL 16 and Redis 7 reachable from API and workers
- `JWT_SECRET_KEY` — production/non-development secret must not be the repository default and must be at least **32** characters (`JWT_SECRET_MIN_LENGTH`); validation fails fast on Settings construction and does not echo the secret
- `refresh_token_expire_days` — refresh token TTL in days (default **7**)
- `CORS_ORIGINS` — deployed frontend origins only
- `TELEGRAM_BOT_TOKEN` — live bot for permission checks
- `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` — discovery/import
- `OPENAI_API_KEY` or `GEMINI_API_KEY` — AI generation
- Celery broker/backend URLs (Redis also backs Phase D route rate-limit counters)

### Frontend

- `NEXT_PUBLIC_API_URL` set at **build time**
- No secrets in client bundle

### Migrations

Run `alembic upgrade head` once before API/worker promotion. Current head includes migration **`016_add_workspace_settings`** (one `workspace_settings` row per workspace, `ON DELETE CASCADE`; revises `015`; no secret columns).

See `.env.example` for full variable list (migrated from legacy handoff doc).

---

## 2. Docker Services

| Service | Port | Purpose |
| --- | --- | --- |
| `api` | 8000 | FastAPI + migrate on start |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Celery broker + A.2/Phase B Redis keys |
| `celery-worker` | — | Background tasks |
| `celery-beat` | — | Periodic publish + discovery refresh + worker heartbeat |
| `flower` | `127.0.0.1:5555` | Optional Celery task UI (Compose profile `observability` only) |

Startup (default stack): DB/Redis healthy → migrate → Uvicorn → worker/beat connect.

Flower is **not** part of the default stack. Enable with:

```text
docker compose --profile observability up
```

Flower binds **localhost-only** (`127.0.0.1:5555:5555`), uses basic auth via `FLOWER_BASIC_AUTH` (`username:password`), and is not a dependency of `api` / worker / beat.

---

## 3. Automated CI Gate

GitHub Actions (Python 3.12, Node 22):

- Backend: full pytest suite; Ruff on the first-party Python tree (`python -m ruff check .`). The vendored AliExpress IOP SDK under `iop/` is excluded — it is third-party Python-2-era code, not a disabled Ruff rule.
- Frontend: typecheck, ESLint, Vitest, production build
- E2E: Playwright smoke job `e2e` (`npm run test:e2e`, Chromium). The job builds the Next.js app and Playwright `webServer` serves `npm run start`, waiting until `GET /login` is reachable. Specs stub FastAPI with Playwright `page.route` (login, workspace tenancy, discovery image search, import, AI generate, queue publish, queue schedule). They do not boot docker compose and do not call Telegram, AliExpress, OpenAI, or Gemini.

Playwright is a CI **job**, not a required GitHub branch-protection check. Promote it to required only after 2–3 consecutive green PRs without flake (**TODO**).

Do not release from failing required checks.

---

## 4. Staging Deployment Checklist

1. Build immutable backend + frontend images
2. Apply Alembic migrations
3. Provision staging admin with the trusted operator CLI (not public register):
   `docker compose exec -e BOOTSTRAP_ADMIN_PASSWORD api python -m scripts.bootstrap_admin --email <admin-email> --workspace-name "Default Workspace"`
   Creates one `ADMIN` user, one workspace, and one `OWNER` membership atomically. Safe to re-run; does not promote an existing non-admin account.
4. Start PostgreSQL, Redis, API, Celery worker, Celery beat
5. `GET /health` → 200
6. `GET /ready` → 200 (database + redis `up`)
7. `GET /worker/health` → 200 once Beat+worker have refreshed Redis heartbeat (or 503 degraded until then)
8. Optionally start Flower: `docker compose --profile observability up` and open `http://127.0.0.1:5555` with `FLOWER_BASIC_AUTH`
8. Frontend login → dashboard redirect
9. Security headers present; logs contain no secrets

---

## 5. MVP Acceptance Flow (Updated UI)

Execute with staging admin:

1. **Discovery** — Run hot/trending/deals/category searches; open score popover; open product inspector drawer; batch import
2. **Products** — Verify inventory grid density/columns; open `ProductDetailsDrawer`; admin delete; export CSV
3. **AI Studio** — Generate with tone/type/modifiers; compare variants; create queue draft
4. **Channels** — Register Telegram channel; verify permission badges
5. **Queue** — Verify KPI cards read backend attempt truth; schedule via dialog and confirm Celery beat actually publishes at the scheduled time (regression check for the event-loop bug below); bulk publish; confirm Telegram message, including a long post (>4096 chars, or >1024-char caption with an image) publishes as multiple sequential messages without truncation; on simulated Telegram failure verify a durable attempt via `GET /queues/{id}/attempts` and drawer attempt-history section (and toast); confirm `QueueStatus` stays without a `failed` value; duplicate publish of unchanged content returns 409; delete a queue item that has publish attempts and confirm it (and its attempt history) is removed without error
6. **Settings** — Readiness shows DB + Redis
7. Expired access JWT triggers one single-flight refresh when a refresh token exists; refresh failure clears session → login

---

## 6. Security Boundaries

| Topic | Rule |
| --- | --- |
| JWT storage | Access + refresh in `sessionStorage`; cookie is presence marker only |
| Access vs refresh | Bearer carries access JWT only; refresh sent as JSON to `/auth/refresh` and `/auth/logout` |
| Session validation | `AuthGuard` → `GET /auth/me` |
| JWT secret (non-dev) | Reject repository default; reject length &lt; 32; fail-fast; no secret in error text |
| Refresh tokens | Opaque; SHA-256 hash in PostgreSQL; rotate; single-use; reuse revocation; logout revoke; migration `009` |
| Rate limiting | Redis fixed-window via FastAPI route dependencies (not middleware); fail-open; policies below |
| Conversion create | Authenticated + affiliate ownership (or ADMIN); 401/403; amount integrity still client/PENDING review |
| Admin operations | Import, delete — backend + UI role check |
| Tenancy | Queue/channel HTTP APIs, dashboard queue/channel aggregates, **analytics**, **workspace settings**, and `GET /queues/stream` are **workspace-scoped** via `X-Workspace-Id`. Analytics derives click/conversion scope through `Campaign.workspace_id` (no `workspace_id` on `clicks` or `conversions`; migration `015` adds query indexes only). `workspace_settings.workspace_id` is **NOT NULL** with `ON DELETE CASCADE` (migration `016`). `campaigns.workspace_id`, `queue_items.workspace_id`, and `telegram_channels.workspace_id` are **NOT NULL** with `ON DELETE RESTRICT` (migration `013`). Product remains a **global shared catalog** (no `workspace_id`). Affiliate remains a **global user-owned 1:1 profile** (no `workspace_id`). `PATCH /auth/me` is user-global (no workspace header). `POST /affiliates/join-campaign` requires `X-Workspace-Id`. Public **`GET /clicks/{affiliate_campaign_id}`** is global — no JWT, no workspace header (Task 11). Discovery and **`POST /products/search/image`** remain global (Task 10). Frontend workspace init: `/auth/me` → `default_workspace_id` → `sessionStorage` (Task 9). |
| Public / unauthenticated | Discovery read, product list, public click redirect; `POST /conversions` is **no longer** anonymous |
| `/ready` | Dependency state only (database + redis) — no secrets; not Celery liveness |
| `/worker/health` | Celery Beat→worker pipeline heartbeat only — no secrets; not task-failure metrics |
| Auth service | No password/credential logging in `app/auth/service.py` or `app/auth/security.py` (verified 2026-07-29) |

**Rate-limit policies (configuration/code constants — not a global platform):**

| Route | Limit | Window | Identity |
| --- | --- | --- | --- |
| `POST /auth/login` | 10 | 5 minutes | client IP (`request.client.host`) |
| `POST /auth/refresh` | 20 | 5 minutes | client IP |
| `POST /conversions` | 30 | 1 minute | user id when valid access Bearer present; else IP |
| `GET /clicks/{affiliate_campaign_id}` | 30 | 60 seconds | client IP (`request.client.host`) |

429 includes `Retry-After`. No claim of `X-Forwarded-For` / trusted-proxy IP handling.

---

## 7. Non-Functional Checks

- Arabic RTL at mobile/tablet/desktop
- Keyboard focus on drawers, dialogs, tables
- Light/dark theme readability
- Slow network: skeletons, no broken layouts
- Product/queue lists at expected volume (200-item queue fetch limit documented)

---

## 8. Release & Rollback

- Record image digests, migration revision, acceptance owner
- Promote exact staging images — no rebuild between stages
- Monitor: API 5xx, Celery failures, queue age, publish success rate
- Rollback: application images first; DB via reviewed Alembic downgrade only

---

## 9. Architectural Requirements

### 9.1 Real-time status streaming (Phase A.2) ✅ COMPLETE

**Problem (historical):** Queue KPIs and row status relied on manual refresh and client publish state for cross-actor updates (Celery / other tabs).

**Shipped architecture (2026-08-08):**

```text
Queue mutation (API or Celery)
  → EventPublisher → Redis Pub/Sub channel `queue-events`
  → EventConsumer (one per API process) → EventBroadcaster
  → Authenticated SSE `GET /api/v1/queues/stream`
  → Frontend fetch-based SSE client → debounced TanStack Query invalidation
  → Authoritative REST refetch → Queue UI
```

**Implemented:**

- SSE endpoint `GET /api/v1/queues/stream` (Bearer JWT via `CurrentUser`; `text/event-stream`; `X-Accel-Buffering: no`; idle heartbeat comment every 30s; per-client queue bound 64)
- Canonical events: `queue.status_changed`, `queue.deleted`, `queue.attempt_started`, `queue.attempt_succeeded`, `queue.attempt_failed` — **no** `dashboard.stats_updated`
- Frontend: `useQueueEventStream` / `useQueueRealtimeInvalidation`; invalidate-never-patch; `QueueRealtimeStatusBadge`
- Fallback: TanStack Query `refetchInterval` while SSE unavailable (5s → 30s adaptive); reconnect disables polling and performs one authoritative `["queue"]` refresh
- Streaming-safe security headers middleware (pure ASGI; does not buffer SSE bodies)
- Redis publish failure does not roll back committed domain mutations (logged only)

**Ops note (post-A.2):** Verify reverse proxies in front of the API disable response buffering for the stream path (response already sends `X-Accel-Buffering: no`). Optional later: SSE connection cap, heartbeat/settings tuning — see design doc §18. Does **not** claim the whole application is production-ready.

### 9.2 Background workers & queue execution (Phase B) ✅ COMPLETE

**Existing Celery business schedules (pre–Phase B; unchanged):** Beat + `process_publish_queue` (default 60s), discovery refresh hot/trending (6h), categories (24h).

**Phase A.1 items already delivered (unchanged by Phase B):**

- Terminal Telegram attempts: `error_code=dead_letter` on `queue_publish_attempts`; `QueueStatus` unchanged
- Publish idempotency: shared claim/guard in `TelegramPublishingService`

**Phase B shipped:**

#### Worker/Beat pipeline heartbeat

- Task: `app.worker.tasks.health.worker_heartbeat` (Beat entry `worker-heartbeat`)
- Redis key: `celery:health:heartbeat` (string UTC ISO timestamp; not Pub/Sub; not `queue-events`)
- Default interval: **30s** (`celery_heartbeat_interval_seconds` → env `CELERY_HEARTBEAT_INTERVAL_SECONDS`)
- Default TTL: **90s** (`celery_heartbeat_ttl_seconds` → env `CELERY_HEARTBEAT_TTL_SECONDS`)
- Semantics: a fresh key means Beat recently scheduled the heartbeat task **and** a worker executed it **and** Redis accepted the write. If Beat stops scheduling **or** the worker stops consuming, the key expires and health degrades. The key alone does **not** isolate which half failed.
- No database writes; no A.2 queue events.

#### Worker health endpoint

- `GET /worker/health` (root app; unauthenticated; not under `/api/v1`)
- Response: `{ "status": "healthy" | "degraded" | "unknown", "last_heartbeat_at": <ISO UTC> | null }`
- HTTP: **200** healthy · **503** degraded/unknown
- Fresh (within TTL) → healthy; missing/stale → degraded; Redis unreadability / invalid timestamp → unknown
- Distinct from:
  - `/health` — API process liveness
  - `/ready` — PostgreSQL + Redis reachability only (unchanged; no `worker` check)

#### Flower (task failure observability)

- Package: Flower **2.0.1** (Celery 5.x compatible)
- Compose service: `affiliate-flower`, profile **`observability`** (not started by default `docker compose up`)
- Port: `127.0.0.1:5555:5555` (localhost-only; not `0.0.0.0`)
- Auth: `FLOWER_BASIC_AUTH` (`username:password`); basic-auth always configured in Compose
- Broker: same `CELERY_BROKER_URL` / Redis service as worker
- Celery events enabled for visibility: `worker_send_task_events=True`, `task_send_sent_event=True`
- Observes publishing, discovery, and heartbeat tasks; does **not** change retries or business logic
- **Prometheus:** deferred — no Prometheus service and no application `/metrics` endpoint
- **Automated alerting/paging:** not implemented; operators use `/worker/health` + Flower UI manually

**Still future (not Phase B):**

- Separate Celery queues: `publishing`, `discovery_refresh`, `ai_batch`
- Automated alert wiring on beat/worker absence

**Phase C' (COMPLETE 2026-08-09):** AliExpress HTTP retries remain client-owned (`_execute_with_retries`); discovery tasks do **not** add Celery HTTP `autoretry_for` for those failures. OpenAI/Gemini retries are provider-owned (`app/ai/retry.py`). See §9.3.
**Env vars (Phase B–relevant):**

| Settings field | Environment variable | Notes |
| --- | --- | --- |
| `celery_publish_interval_seconds` | `CELERY_PUBLISH_INTERVAL_SECONDS` | Existing; documented in `.env.example` |
| `celery_publish_batch_size` | `CELERY_PUBLISH_BATCH_SIZE` | Existing |
| discovery intervals | `CELERY_DISCOVERY_*_INTERVAL_SECONDS` | Existing |
| `celery_heartbeat_interval_seconds` | `CELERY_HEARTBEAT_INTERVAL_SECONDS` | Default **30**; Settings default if unset |
| `celery_heartbeat_ttl_seconds` | `CELERY_HEARTBEAT_TTL_SECONDS` | Default **90**; Settings default if unset |
| — | `FLOWER_BASIC_AUTH` | Compose/Flower only; placeholder in `.env.example` |

Also: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` as already used by API/worker.

### 9.3 Error handling & retries

| Integration | Policy | Status |
| --- | --- | --- |
| **Telegram Bot API** | In-process: up to 3 retries (1 initial + 3 = ≤4 HTTP attempts), exponential backoff from `0.5s` + jitter; honor 429 `parameters.retry_after`. Celery publish tasks: `autoretry_for=(TelegramPublishError,)`, `max_retries=3`, `retry_backoff=True`, `retry_jitter=True`. Non-retryable 4xx Telegram errors (excluding 429) are marked terminal immediately so the beat loop does not recreate failed attempts forever. Failures persist on `queue_publish_attempts`; terminal → `error_code=dead_letter` | ✅ Implemented (Phase A.1) |
| **AliExpress IOP** | Client-owned only: `_execute_with_retries` in `app/aliexpress/api_client.py`. Budget `aliexpress_max_retries + 1` (default **4**). Retryable: rate-limit errors; codes `{408,429,500,502,503,504}` or message `timeout`/`temporarily`. Credentials errors re-raise immediately. Backoff `0.5s * 2^attempt` + jitter `[0,0.25)`; inter-request gate default **0.2s**. Discovery Celery tasks: **no** AliExpress HTTP `autoretry_for` (nesting would multiply outbound calls). Canonical discovery exception: `app.aliexpress.exceptions.AliExpressAPIError` | ✅ Implemented (Phase C') |
| **OpenAI / Gemini** | Provider-owned via `app/ai/retry.py` (max **2** total attempts). Retryable: `httpx.TransportError`, HTTP 429, HTTP 5xx. Non-retryable: 400/401/403/404 and unexpected non-httpx errors. Malformed response parsing is **outside** the retry loop (1 call). Backoff base **1.0s** × `2^attempt` + jitter `[0,0.5)`; honor numeric `Retry-After` (cap **60s**). Timeout **60s**/attempt. Exhaustion → existing `AIProviderError` contract. **No** Celery path | ✅ Implemented (Phase C') |
| **Celery publish tasks** | As above for Telegram publishing | ✅ Publish path (Phase A.1) |
| **Celery discovery tasks** | No AliExpress HTTP autoretry; client budget is the sole HTTP retry owner | ✅ Confirmed (Phase C') |

Log structured failure records (queue_id, provider, attempt, error_code) — no token leakage. Attempt rows are the durable audit source for Telegram publishes. AI retry schedule logs (when emitted) include only provider/attempt/reason/delay — never API keys, prompts, or credential-bearing URLs.

**Phase C' validation:** offline pytest coverage for AliExpress client retries, discovery exception identity, no-nested-Celery guards, AI provider retries, and API regression (`tests/test_aliexpress_api_client_retries.py`, `tests/test_discovery_task_exceptions.py`, `tests/test_aliexpress_no_nested_retry.py`, `tests/test_ai_provider_retry.py`, `tests/test_phase_c_prime_api_regression.py`). Full backend suite after Task 4: **244** passed. No DB migration, no new API endpoints, no frontend/SSE changes.

**Batch resilience:** `_publish_items` (used by the Celery beat path) catches `TelegramPublishError` in addition to `ValidationError`/`ForbiddenError`/`ConflictError` per item and continues the batch — one item's failure (and its persisted attempt/dead-letter row) never blocks the rest of the due/queued batch for that tick. On success, the service commits immediately before returning so a later sibling failure in the same batch cannot roll back a Telegram message that already sent.

### 9.4 Form & schema validation ✅ COMPLETE

Frontend UX/input validation only. Does **not** replace backend Pydantic, authorization, or API behavior. Design: [planning/form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md).

- Feature-local Zod schemas: `features/queue/lib/schemas.ts` (`queueSchedulingSchema`, `channelAssignmentSchema`), `features/products/lib/schemas.ts` (`productStatusSchema`)
- `QueueSchedulingDialog` uses existing React Hook Form + `zodResolver` (already used by `LoginForm` / ChannelsView; not a new stack)
- Product status labels/options centralized; **no** status editor and **no** drawer inline-edit mutation
- Channel assignment is the scheduling dialog’s `channelId` UUID — **no** standalone assignment drawer
- Shared Arabic helpers in `lib/validation/messages.ts` — not an i18n system
- **Not shipped:** `useValidatedMutation`, Pydantic/API/DB changes, new dependencies

Frontend Zod must not be treated as a security control.

### 9.5 Observability & CI/CD (Phase 4)

- Structured JSON logging with request IDs
- GitHub Actions: Ruff on the first-party Python tree; Playwright smoke job `e2e` (not a required branch-protection check until proven stable — see §3)
- Secret management: Vault/AWS Secrets Manager for production
- HTTPS termination, HSTS, CSP headers on frontend

### 9.6 Authentication & public-endpoint security (Phase D) ✅ COMPLETE

Shipped 2026-08-13. Design: [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

| Area | Shipped behavior | Explicit non-claims |
| --- | --- | --- |
| JWT | Non-dev rejects default/short secrets; fail-fast; no secret in errors | No vault integration; no automated rotation infrastructure |
| Refresh tokens | Opaque; SHA-256 in DB; rotate; single-use; reuse revoke; logout; TTL default 7 days | No device dashboards; no HttpOnly cookie storage; no MFA |
| Rate limiting | Redis fixed-window; route `Depends` only; fail-open; policies in §6 | Not global middleware; not a distributed rate-limit platform; no XFF IP |
| Conversions | Auth + ownership (ADMIN bypass) | Amount not verified against external network; PENDING review remains residual control |
| Frontend | Single-flight refresh; retry-once; refresh never Bearer; logout clears local state | No CSRF beyond existing app behavior |

**Regression boundaries preserved:** A.1 publishing, A.2 SSE, Phase B `/worker/health`, Phase C' retry ownership — unchanged.

### 9.7 Phase E workspace runtime & click tracking (Tasks 9–11) ✅ COMPLETE

**Task 9 — Frontend workspace runtime (verified):**

- Login → `GET /auth/me` → store `default_workspace_id` when exactly one membership exists
- Workspace-scoped REST/SSE attach `X-Workspace-Id`; global catalog/discovery/image-search/click paths do not
- Missing workspace on tenant routes: client `missing_workspace` or backend **403**
- Logout clears tokens, workspace id, and query cache

**Task 10 — Image search UI (verified):** Discovery `ImageSearchPanel` calls global `POST /products/search/image` without workspace header; results reuse existing discovery table/inspector; gallery image can trigger a new image search.

**Task 11 — Click tracking (live-verified):**

| Check | Result |
| --- | --- |
| Valid enrollment click | **302** + `Click` persisted; `click_id` server-generated |
| Public access | Works without JWT or `X-Workspace-Id`; arbitrary workspace header ignored |
| Unsafe/blank `tracking_link` | **422**; no new click row |
| Conversion correlation | Valid enrollment **201**; cross-enrollment **422** |
| Rate limit | **429** + `Retry-After` after **30** requests / **60s** per IP |
| Schema | Migration `014_add_clicks`; no `clicks.workspace_id` |

**Open follow-up:** OpenAPI route metadata for click endpoint still documents primarily **302**; **404** and **429** belong in code-level OpenAPI when application metadata is next touched.

**Still out of scope:** Analytics, funnel metrics, payouts, Product↔Campaign redesign, workspace selector UI.

---

## 10. Known Issues (Production Blockers)

| Issue | Severity | Action |
| --- | --- | --- |
| Operators must still set a strong `JWT_SECRET_KEY` in every non-dev deploy | Critical (ops) | Fail-fast validation rejects default/short secrets; rotate/set before promote |
| Rate-limit identity uses `request.client.host` only | Info | Document reverse-proxy topology if shared egress IP collapses limits |
| Conversion amount integrity | Residual | PENDING + admin review; not Phase D Task 4 scope |
| Single Celery beat instance | Info | Document ops constraint |

**Closed by Phase D (historical):** “No refresh token”, anonymous `POST /conversions`, absence of auth route rate limits, unvalidated default JWT in non-dev (now rejected at startup).

---

### 10.1 Resolved Production Issues (Phase A.1 hardening, 2026-08-04)

Discovered and fixed after Phase A.1 backend Tasks 1–9 landed, before the milestone was considered fully closed:

| Issue | Root cause | Fix |
| --- | --- | --- |
| **Scheduled publishing stopped working** | Celery tasks run via `asyncio.run()`, which opens/closes a fresh event loop per invocation. The process-wide async SQLAlchemy engine (and its connection pool) stayed bound to the first loop, so the next beat tick raised `RuntimeError: ... attached to a different loop` and silently failed to publish due items | Added `dispose_async_engine()` (`app/core/database.py`); `run_async()` (`app/worker/async_utils.py`) now disposes the shared engine after every coroutine run so the next `asyncio.run()` starts clean |
| **Deleting a queue item with publish attempts failed** | `QueueItem.publish_attempts` had no ORM-level delete cascade, so SQLAlchemy tried to null out the child `queue_publish_attempts.queue_id` on parent delete, violating the `NOT NULL` constraint | Added `cascade="all, delete-orphan"` to the relationship in `app/models/queue.py`, matching the DB's `ON DELETE CASCADE` policy |
| **Long posts failed or were truncated on Telegram** | Telegram Bot API rejects text over 4096 characters and photo captions over 1024 characters; the publisher sent the full content unconditionally | `TelegramPublisher` now splits text/captions at paragraph → line → word boundaries (`split_telegram_text`), sending overflow as sequential follow-up messages; the inline button attaches only to the final chunk; content is never truncated |

Regression coverage: `tests/test_queue_delete.py` (delete-with-attempts across draft/queued/scheduled), `tests/test_telegram_long_messages.py` (chunking boundaries, caption overflow), and additions to `tests/test_queue_publishing_service.py` (batch persist-and-continue on `TelegramPublishError`, non-retryable-terminal marking, idempotency status-drift healing).

---

## 11. Quick Reference Commands

```bash
docker compose up --build
alembic upgrade head
pytest
cd frontend && npm ci && npm run typecheck && npm run lint && npm test && npm run build
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

---

## 12. Related Documents

- [06-api-integration.md](./06-api-integration.md)
- [08-implementation-roadmap.md](./08-implementation-roadmap.md)
