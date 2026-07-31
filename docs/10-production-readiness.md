# Production Readiness and Release Runbook

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

Release gate supplement to documents 01–09. Defines security boundaries, environment configuration, CI/CD, deployment checklists, and **upcoming architectural requirements**.

---

## 1. Required Environment

### Backend

- PostgreSQL 16 and Redis 7 reachable from API and workers
- `JWT_SECRET_KEY` — generated production secret (never default)
- `CORS_ORIGINS` — deployed frontend origins only
- `TELEGRAM_BOT_TOKEN` — live bot for permission checks
- `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` — discovery/import
- `OPENAI_API_KEY` or `GEMINI_API_KEY` — AI generation
- Celery broker/backend URLs

### Frontend

- `NEXT_PUBLIC_API_URL` set at **build time**
- No secrets in client bundle

### Migrations

Run `alembic upgrade head` once before API/worker promotion.

See `.env.example` for full variable list (migrated from legacy handoff doc).

---

## 2. Docker Services

| Service | Port | Purpose |
| --- | --- | --- |
| `api` | 8000 | FastAPI + migrate on start |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Celery broker |
| `celery-worker` | — | Background tasks |
| `celery-beat` | — | Periodic publish + discovery refresh |

Startup: DB/Redis healthy → migrate → Uvicorn → worker/beat connect.

---

## 3. Automated CI Gate

GitHub Actions (Python 3.12, Node 22):

- Backend: full pytest suite; Ruff on production-readiness file set
- Frontend: typecheck, ESLint, Vitest, production build

Playwright (`npm run test:e2e`) — local/manual; **not** CI gate today.

Do not release from failing required checks.

---

## 4. Staging Deployment Checklist

1. Build immutable backend + frontend images
2. Apply Alembic migrations
3. Provision staging admin (DB/trusted process — not public register)
4. Start PostgreSQL, Redis, API, Celery worker, Celery beat
5. `GET /health` → 200
6. `GET /ready` → 200 (database + redis `up`)
7. **Separately** verify Celery worker consumes a test task
8. Frontend login → dashboard redirect
9. Security headers present; logs contain no secrets

---

## 5. MVP Acceptance Flow (Updated UI)

Execute with staging admin:

1. **Discovery** — Run hot/trending/deals/category searches; open score popover; open product inspector drawer; batch import
2. **Products** — Verify inventory grid density/columns; open `ProductDetailsDrawer`; admin delete; export CSV
3. **AI Studio** — Generate with tone/type/modifiers; compare variants; create queue draft
4. **Channels** — Register Telegram channel; verify permission badges
5. **Queue** — Verify KPI cards; schedule via dialog; bulk publish; confirm Telegram message; verify failure toast on simulated error
6. **Settings** — Readiness shows DB + Redis
7. Expired JWT clears session → login

---

## 6. Security Boundaries

| Topic | Rule |
| --- | --- |
| JWT storage | `sessionStorage` only; cookie is presence marker |
| Session validation | `AuthGuard` → `GET /auth/me` |
| Admin operations | Import, delete — backend + UI role check |
| Tenancy | Queue/channel data **not user-scoped** — not multi-tenant safe |
| Public endpoints | Discovery read, product list, `/conversions` POST |
| `/ready` | Dependency state only — no secrets |
| Auth service | No password/credential logging in `app/auth/service.py` or `app/auth/security.py` (verified 2026-07-29) |

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

## 9. Upcoming Architectural Requirements

### 9.1 Real-time status streaming (Phase A)

**Problem:** Queue KPIs and row status rely on manual refresh and client publish state.

**Target architecture:**

```text
Celery publish task → emit status event → Redis pub/sub or SSE endpoint → frontend subscription
```

**Requirements:**

- SSE endpoint `GET /queues/stream` or WebSocket `/ws/queue` (auth required)
- Events: `status_changed`, `publish_started`, `publish_succeeded`, `publish_failed`
- Frontend: `useQueueEventStream` hook; fallback polling 5s → 30s backoff
- Do not add `failed` to `QueueStatus` enum — use event payload + audit log

### 9.2 Background workers & queue execution

**Current:** Celery Beat + `process_publish_queue` every 60s.

**Enhancements:**

- Dead-letter queue for exhausted Telegram retries
- Publish task idempotency key (`queue_id` + content hash)
- Worker health endpoint or heartbeat key in Redis
- Separate queues: `publishing`, `discovery_refresh`, `ai_batch` (future)
- Monitor with Flower/Prometheus; alert on beat/worker absence

**Env vars:** `CELERY_PUBLISH_INTERVAL_SECONDS`, `CELERY_PUBLISH_BATCH_SIZE`, discovery refresh intervals (see `.env.example`)

### 9.3 Error handling & retries

| Integration | Policy |
| --- | --- |
| **Telegram Bot API** | 3 retries, exponential backoff (1s, 4s, 16s + jitter), respect 429 `retry_after` |
| **AliExpress IOP** | Existing client rate limit + `ALIEXPRESS_MAX_RETRIES` |
| **OpenAI / Gemini** | 2 retries on 502/503; timeout 60s; user-facing `AIProviderError` message |
| **Celery tasks** | `autoretry_for`, `max_retries=3`, `retry_backoff=True` |

Log structured failure records (queue_id, provider, attempt, error_code) — no token leakage.

### 9.4 Form & schema validation

- Zod schemas generated or manually synced with Pydantic (`features/*/lib/schemas.ts`)
- Drawer inline edits validated before mutation
- Shared `useValidatedMutation` pattern: parse → API call → toast on success/error
- Arabic validation messages

### 9.5 Observability & CI/CD (Phase 4)

- Structured JSON logging with request IDs
- GitHub Actions: expand Ruff to full codebase; add Playwright smoke to CI when stable
- Secret management: Vault/AWS Secrets Manager for production
- HTTPS termination, HSTS, CSP headers on frontend

---

## 10. Known Issues (Production Blockers)

| Issue | Severity | Action |
| --- | --- | --- |
| Default JWT secret | Critical | Rotate in all non-dev envs |
| Silent Celery publish skip | Medium | Add logging + retry |
| No refresh token | Medium | Document session expiry UX |
| Conversion POST public | Info | Rate limit when adding middleware |
| Single Celery beat instance | Info | Document ops constraint |

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
