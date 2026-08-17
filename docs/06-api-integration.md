# API Integration Guide

**Document Version:** 2.5  
**Last Updated:** 2026-08-13

**2026-08-04 revision:** Phase A.1 **frontend tasks are complete** — queue KPIs, `QueueHealthBadge`, and `QueueTable` now resolve failures from backend attempt data (`resolveQueueFailure`) with the client failure map only as a short-lived gap-filler until per-item enrichment resolves; `QueueDetailsDrawer` renders read-only publish attempt history from `GET /queues/{id}/attempts` and retries via the existing `POST /queues/{id}/publish`. Statuses below for §4.6 and §5 are updated accordingly. Also reflects three post-implementation bug fixes (scheduled publishing, queue item deletion, Telegram long-message publishing) — see [10-production-readiness.md](./10-production-readiness.md) §10.

**2026-08-08 revision (Phase B closeout):** Documented root operational endpoint `GET /worker/health` (Phase B Task 2). `/ready` semantics unchanged (database + Redis only).

**2026-08-13 revision (Phase D closeout):** Auth refresh tokens, route rate limits, and `POST /conversions` authorization. See §1 and §4.8. Design: [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

**Backend source of truth:** FastAPI routers + Pydantic schemas  
**Default API base:** `http://localhost:8000/api/v1`  
**Frontend env:** `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`

OpenAPI: `/docs` · ReDoc: `/redoc` · Health: `GET /health` · Readiness: `GET /ready` · Worker health: `GET /worker/health`

---

## 1. Authentication

### Login

`POST /auth/login` — `application/x-www-form-urlencoded`

| Field | Value |
| --- | --- |
| `username` | Email address |
| `password` | Password |

Response (additive `refresh_token`):

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "refresh_token": "<opaque-token>"
}
```

Protected requests: `Authorization: Bearer <access_token>` only. Refresh tokens must **not** be sent as Bearer.

Rate limit (policy): **10** requests / **5 minutes** per client IP (`request.client.host`). HTTP **429** + `Retry-After` when exceeded. Redis failure **fail-open**.

### Refresh

`POST /auth/refresh` — JSON

```json
{ "refresh_token": "<opaque-token>" }
```

Response: `{ "access_token", "token_type": "bearer", "refresh_token" }` (rotated pair).

- Refresh tokens expire per `refresh_token_expire_days` (default **7**).
- Each refresh token is single-use; successful refresh rotates.
- Reuse of a consumed/revoked token revokes the user’s active refresh tokens.
- Rate limit (policy): **20** / **5 minutes** per client IP.

### Logout

`POST /auth/logout` — JSON `{ "refresh_token": "<opaque-token>" }` → HTTP **204**. Idempotent revocation of the supplied refresh token.

### Frontend session behavior

- Access + refresh tokens stored in `sessionStorage`; middleware cookie remains presence-only.
- On **401** (excluding `/auth/login`, `/auth/refresh`, `/auth/logout`): one single-flight refresh, then retry the original request once; refresh failure clears session → `/login`.
- **403** does not trigger refresh or auto-logout.

### Register

`POST /auth/register` — public, creates `affiliate` only. Not exposed in frontend UI.

### Current user

`GET /auth/me` → `UserRead` (`id`, `email`, `full_name`, `role`, `is_active`, timestamps)

---

## 2. Errors & Pagination

Errors: `{ "detail": "..." }` or validation array for `422`.

**Standard pagination** (`products`, `channels`, `queues`): `skip`, `limit` → `{ items, total, skip, limit }`

**Discovery pagination**: `page`, `page_size` → includes `total_pages`, `mode`, `sort`, `persisted_count`

---

## 3. Frontend Integration Pattern

```typescript
// services/api-client.ts — shared Axios instance
// features/*/api/*.api.ts — feature contracts
// features/*/hooks/*.ts — TanStack Query wrappers
```

Query keys must include all server filter params. Mutations invalidate minimal key prefixes.

---

## 4. API Integration Status Matrix

Status definitions:

| Status | Meaning |
| --- | --- |
| **Connected** | Frontend calls live backend route in production UI |
| **Partial** | Connected with UI gaps or client-side augmentation |
| **Backend only** | Route exists; no frontend consumer |
| **Client-side** | No backend route; local state / derived UI |
| **Pending backend** | UI stub or future capability waiting on API |

### 4.1 Authentication & account

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `POST /auth/login` | `auth.api.ts` | Connected | `LoginInput` → `TokenResponse` (includes `refresh_token`) |
| `POST /auth/refresh` | `api-client.ts` | Connected | Rotates access + refresh; not called from UI hooks directly |
| `POST /auth/logout` | `useAuth.ts` | Connected | Best-effort revoke; local clear always |
| `GET /auth/me` | `auth.api.ts` | Connected | `User` — role gating for admin import/delete |
| `POST /auth/register` | — | Backend only | Public registration not in UI |

### 4.2 Dashboard

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /dashboard` | `dashboard.api.ts` | Connected | `DashboardOverview` — counts, activity, DB status |
| `GET /ready` | `categories.api.ts` | Connected | `ReadinessResponse` — settings capability views; **database + redis only** |
| `GET /health` | — | Backend only | API process liveness (ops) |
| `GET /worker/health` | — | Backend only | Celery Beat→worker pipeline heartbeat (ops; root path, not under `/api/v1`) |

### 4.3 Products catalog

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /products` | `products.api.ts` | Connected | `ProductListParams` → `ProductListResponse`; server pagination |
| `GET /products/{id}` | `products.api.ts` | Connected | `Product` — detail page + drawer context |
| `PATCH /products/{id}` | `products.api.ts` | Connected | Admin status updates from inventory |
| `DELETE /products/{id}` | `products.api.ts` | Connected | Admin bulk delete dialog |
| `POST /products` | — | Backend only | No create-product form in UI |
| Client search/sort/density | `useProductInventoryState` | Client-side | Operates on fetched page |
| Pipeline badges | `lib/inventory.ts` | Partial | Joins product list + `GET /queues` client-side |

### 4.4 Product discovery & import

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /products/discover` | `discovery.api.ts` | Connected | General mode. Transient AliExpress HTTP failures are retried only inside `api_client._execute_with_retries`; API maps domain `AliExpressAPIError` → **502** (existing contract; Phase C' did not change the surface) |
| `GET /products/discover/hot` | `discovery.api.ts` | Connected | Same client-owned retry boundary |
| `GET /products/discover/deals` | `discovery.api.ts` | Connected | |
| `GET /products/discover/trending` | `discovery.api.ts` | Connected | Same client-owned retry boundary |
| `GET /products/discover/category/{id}` | `discovery.api.ts` | Connected | Requires `category_id` |
| `GET /products/search` | — | Backend only | Keyword mode uses discover paths |
| `POST /products/search/image` | — | Backend only | DS image search; env-gated |
| `POST /products/import` | `discovery.api.ts` | Connected | Single import (admin) |
| `POST /products/import/batch` | `discovery.api.ts` | Connected | Bulk import from selection bar |
| `POST /products/import-url` | — | Backend only | URL import not in UI |
| `GET /aliexpress/categories` | `categories.api.ts` | Connected | Category picker |
| `POST /aliexpress/import` | — | Backend only | Duplicate of `/products/import` |
| Discovery session persistence | `discovery/lib/session.ts` | Client-side | Filters/UI prefs in `sessionStorage` |
| Score breakdown display | `lib/product-score.ts` | Partial | Uses server `score`; breakdown fallback if no `score_breakdown` |
| `persist=true` on discover | — | Pending backend UI | API supports; UI does not expose toggle |

### 4.5 AI content

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `POST /ai-content/generate` | `ai.api.ts` | Connected | Extended request: `content_type`, `tone`, `language`, `length`, `instruction_modifiers`. Provider-owned retries (OpenAI/Gemini via `app/ai/retry.py`, max **2** attempts) are transparent to the HTTP contract. Exhaustion / permanent failures still surface as existing `AIProviderError` → **502** `detail` string. Malformed provider JSON shape does **not** retry. No Celery involvement. Phase C' added **no** new fields/endpoints |
| Variant session | `useContentSession` | Client-side | Variants, edits in `sessionStorage` — not persisted server-side |
| Content quality scores | `ai/lib/scores.ts` | Client-side | Heuristic scoring for UI badges |
| Prompt profiles / history API | — | Pending backend | No save/list endpoints |

**GenerateContentInput** (frontend) ↔ **GenerateContentRequest** (Pydantic) — keep enums in sync via `features/ai/types/api.ts` and `app/schemas/ai_content.py`.

**Provider selection:** request `provider` (`openai` \| `gemini`) selects exactly one configured provider — no cross-provider fallback (Phase C' preserved).
### 4.6 Publishing queue

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /queues` | `queue.api.ts` | Connected | Fetches up to 200 items for workspace. List items do **not** populate attempt summary fields (defaults: `last_attempt=null`, `failure_reason=null`, `retry_count=0`); `useQueueAttemptSummaryEnrichment` backfills non-published rows via `GET /queues/{id}` with bounded concurrency (5) |
| `GET /queues/{id}` | `queue.api.ts` | Connected | Returns `QueueRead` with attempt summary: `last_attempt`, `failure_reason`, `retry_count`. Used both for drawer detail and list enrichment |
| `GET /queues/{id}/attempts` | `queue.api.ts` (`getQueuePublishAttempts`) | Connected | `QueuePublishAttemptListResponse` — attempt history newest-first. Wired via `useQueuePublishAttempts`, rendered read-only in `QueueDetailsDrawer` while the drawer is open |
| `POST /queues` | `queue.api.ts` | Connected | Draft/queued creation from AI, products, discovery |
| `PATCH /queues/{id}` | `queue.api.ts` | Connected | Schedule, channel assign, content edit via drawer |
| `POST /queues/{id}/publish` | `queue.api.ts` | Connected | Single + bulk via `useQueuePublishingOperations`. Idempotency guard returns **409** when an unexpired `started`/`succeeded` attempt blocks the same content hash (no attempt row created on suppression); if the blocking attempt already `succeeded` but the queue row had not reached `published` (e.g. a batch rollback), the service heals the row to `published` server-side before returning 409. `QueueDetailsDrawer`'s primary action also serves as "Retry publish" (relabelled "إعادة المحاولة") — same endpoint, no new route |
| `DELETE /queues/{id}` | `queue.api.ts` | Connected | Bulk delete with confirmation; ORM cascade (`cascade="all, delete-orphan"` on `QueueItem.publish_attempts`) deletes attempt history — fixes a prior bug where deleting an item with attempts raised a `NOT NULL` violation instead of cascading |
| Publishing KPI "publishing" | `useQueuePublishingOperations` | Client-side | In-flight publish IDs (legitimately ephemeral) |
| Failed today KPI | `lib/operations.ts` (`resolveQueueFailure`, `getQueueOperationalStats`) | Connected | Backend-owned via `queue_publish_attempts` (`error_code`, including `dead_letter`); `resolveQueueFailure` prefers `item.last_attempt` / `item.failure_reason` and falls back to the client failure map only until enrichment for that row resolves |
| Real-time status stream | `queue` feature SSE client + `useQueueRealtimeInvalidation` | Connected (Phase A.2) | Authenticated `GET /api/v1/queues/stream` (SSE). Events: `queue.status_changed`, `queue.deleted`, `queue.attempt_*`. Debounced TanStack Query invalidation (never cache patch). Adaptive polling fallback 5s→30s when SSE unavailable. No `dashboard.stats_updated`. |

#### Publish attempt schemas (Phase A.1 backend)

**`QueuePublishAttemptRead`** — attempt-scoped only; `status` is **not** a `QueueStatus` value:

| Field | Type | Notes |
| --- | --- | --- |
| `attempt_number` | `int` | Per-queue, one-based |
| `status` | `str` | `started` \| `succeeded` \| `failed` |
| `provider` | `str` | `telegram` for this milestone |
| `occurred_at` | `datetime` | Attempt start time |
| `error_code` | `str \| null` | Set on failure; terminal exhaustion uses `dead_letter` |
| `error_message` | `str \| null` | Human-readable detail |
| `provider_chat_id` | `str \| null` | Set on success |
| `provider_message_id` | `int \| null` | Set on success |

**`QueuePublishAttemptListResponse`:** `{ queue_id, items: QueuePublishAttemptRead[], total }`

**Long content handling (transparent to the API contract):** `TelegramPublisher` splits outbound text exceeding Telegram's limits (4096 chars per message, 1024 chars per photo caption) into sequential messages at paragraph/line/word boundaries, never truncating content. `provider_message_id` on the attempt always refers to the first outbound message (the photo, or the first text chunk); the inline button (if any) attaches only to the final chunk. No schema or endpoint changes — this only affects what is posted to Telegram for long queue items.

**`QueueRead` additive fields** (populated on `GET /queues/{id}` via `QueueService.get_read`):

| Field | Type | Notes |
| --- | --- | --- |
| `last_attempt` | `QueuePublishAttemptRead \| null` | Latest attempt row |
| `failure_reason` | `str \| null` | Latest attempt `error_message` when status is `failed` |
| `retry_count` | `int` | Latest `attempt_number` (0 when never attempted) |

### 4.7 Telegram channels

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /channels` | `channels.api.ts` | Connected | Paginated list |
| `POST /channels` | `channels.api.ts` | Connected | Register channel |
| `PUT /channels/{id}` | `channels.api.ts` | Connected | Active toggle + metadata |
| `DELETE /channels/{id}` | — | Backend only | Not exposed in Channels UI |

### 4.8 Affiliates, campaigns, conversions

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET/POST/PATCH /affiliates/*` | Backend only | No MVP screens |
| `GET/POST/PATCH /campaigns/*` | Backend only | No MVP screens |
| `POST /conversions` | Backend only | **Requires** `Authorization: Bearer <access_token>`. Owner of `affiliate_id` or `ADMIN`. Non-owner **403**; anonymous **401**. Rate limit (policy): **30** / **1 minute** per user id (when valid access Bearer present) else client IP. Amount remains client-supplied; commission and `PENDING` status unchanged (access control only — not amount fraud verification). |
| `GET/PATCH /conversions/*` | Backend only | Existing admin / affiliate list & status update routes; no MVP screens |

---

## 5. View → Contract Mapping

| View | Primary endpoints | Key response fields |
| --- | --- | --- |
| **Discovery grid** | `GET /products/discover*` | `items[].score`, `rating`, `sales`, `discount`, `commission_rate`, `gallery_images` |
| **Discovery inspector drawer** | Same + optional import | Score breakdown, shipping, affiliate URL |
| **Products inventory** | `GET /products`, `GET /queues` | `ProductRead`, pipeline via queue join |
| **Product details drawer** | `GET /products/{id}` (from list) | `image_url`, `gallery_images`, `score`, `affiliate_url` |
| **AI Studio** | `POST /ai-content/generate` | `content`, `provider`, `content_type`, `tone`, `language` |
| **Queue KPI cards** | `GET /queues` + enrichment `GET /queues/{id}` + client ops | Status counts; failed-today resolves from backend attempt data first, client map as short-lived fallback |
| **Queue table/drawer** | `GET /queues`, `GET /queues/{id}`, `GET /queues/{id}/attempts`, `PATCH`, `POST publish` | `content`, `scheduled_at`, `channel_id`, `status`; attempt summary/history read from backend truth; drawer includes read-only attempt-history list |
| **Schedule dialog** | `PATCH /queues/{id}` | `scheduled_at`, `channel_id`, `status: scheduled` |
| **Channels** | `GET/POST/PUT /channels` | `bot_permission_status`, `can_post_messages`, `is_active` |
| **Dashboard** | `GET /dashboard` | Product/queue/channel aggregates |
| **Settings** | `GET /ready` | `checks.database`, `checks.redis` |

---

## 6. Enums (must match backend)

- **User role:** `admin`, `affiliate`, `advertiser`
- **Product status:** `draft`, `active`, `inactive`, `archived`
- **Queue status:** `draft`, `queued`, `scheduled`, `published` — **no `failed` value**
- **Publish attempt status** (attempt-scoped only): `started`, `succeeded`, `failed`
- **AI provider:** `openai`, `gemini`
- **Content type:** `social`, `description`, `telegram`, `facebook`, `blog`, `email`
- **Tone:** `professional`, `friendly`, `luxury`, `technical`, `urgent`, `minimal`, `persuasive`, `funny`
- **Language:** `ar`, `en`, `fr`, `de`
- **Length:** `short`, `medium`, `long`
- **Discovery mode:** `general`, `hot`, `deals`, `trending`, `category`
- **Discovery sort:** `orders_desc`, `rating_desc`, `discount_desc`, `price_asc`, `price_desc`, `newest`, `commission_desc`

---

## 7. Security & Tenancy Notes

- JWT **access** token in `sessionStorage`; opaque **refresh** token also in `sessionStorage` (never as Bearer); middleware cookie is presence-only
- Non-development environments reject the repository default JWT secret and secrets shorter than 32 characters (`JWT_SECRET_MIN_LENGTH`)
- Refresh tokens: SHA-256 hashes in PostgreSQL `refresh_tokens` (migration `009`); rotate on refresh; single-use; reuse detection; logout revocation
- Rate limits: Redis fixed-window on login / refresh / conversions via route dependencies (not global middleware); fail-open on Redis errors; IP from `request.client.host` only (no `X-Forwarded-For` claim)
- `POST /conversions` requires authentication + affiliate ownership (ADMIN bypass); request-body identity is not an authorization source
- Import/delete require admin role in UI; backend enforces on routes
- Queue and channel routes are authenticated but **not user-scoped** — do not imply tenant isolation
- `/ready` checks PostgreSQL + Redis only — not Celery worker liveness or provider credentials
- `/worker/health` is an **unauthenticated operational infrastructure** endpoint at the app root (sibling to `/health` and `/ready`). It is **not** part of the authenticated `/api/v1` application API surface. It reports Beat→worker pipeline heartbeat freshness only — not task-failure metrics and not Flower status.

### 7.1 `GET /worker/health` (Phase B)

| Item | Value |
| --- | --- |
| Method / path | `GET /worker/health` |
| Auth | None |
| Success | HTTP **200** — `{ "status": "healthy", "last_heartbeat_at": "<ISO UTC>" }` |
| Pipeline stopped / stale | HTTP **503** — `{ "status": "degraded", "last_heartbeat_at": "<ISO UTC>" \| null }` |
| Cannot check Redis / invalid value | HTTP **503** — `{ "status": "unknown", "last_heartbeat_at": null }` |

Semantics: fresh Redis key `celery:health:heartbeat` (within `celery_heartbeat_ttl_seconds`, default 90s) → `healthy`; missing or older than TTL → `degraded`; Redis read failure or malformed timestamp → `unknown`.

---

## 8. Axios Reference

```typescript
const body = new URLSearchParams({ username: email, password });
await apiClient.post("/auth/login", body, {
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
});

useQuery({
  queryKey: ["products", { status, skip, limit }],
  queryFn: () => getProducts({ status, skip, limit }),
});
```

---

## 9. Related Documents

- [02-frontend-architecture.md](./02-frontend-architecture.md)
- [08-implementation-roadmap.md](./08-implementation-roadmap.md) — Phase roadmap (A.1, A.2, B, and C' complete; next is Phase D)
- [planning/phase-a2-realtime-operations-design.md](./planning/phase-a2-realtime-operations-design.md) — Phase A.2 SSE design + closeout
- [planning/phase-c-prime-retry-hardening-design.md](./planning/phase-c-prime-retry-hardening-design.md) — Phase C' retry ownership + closeout
