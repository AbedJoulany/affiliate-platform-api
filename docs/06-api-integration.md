# API Integration Guide

**Document Version:** 2.9  
**Last Updated:** 2026-08-22

**2026-08-04 revision:** Phase A.1 **frontend tasks are complete** — queue KPIs, `QueueHealthBadge`, and `QueueTable` now resolve failures from backend attempt data (`resolveQueueFailure`) with the client failure map only as a short-lived gap-filler until per-item enrichment resolves; `QueueDetailsDrawer` renders read-only publish attempt history from `GET /queues/{id}/attempts` and retries via the existing `POST /queues/{id}/publish`. Statuses below for §4.6 and §5 are updated accordingly. Also reflects three post-implementation bug fixes (scheduled publishing, queue item deletion, Telegram long-message publishing) — see [10-production-readiness.md](./10-production-readiness.md) §10.

**2026-08-08 revision (Phase B closeout):** Documented root operational endpoint `GET /worker/health` (Phase B Task 2). `/ready` semantics unchanged (database + Redis only).

**2026-08-13 revision (Phase D closeout):** Auth refresh tokens, route rate limits, and `POST /conversions` authorization. See §1 and §4.8. Design: [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

**2026-08-22 revision (Phase E Task 10):** Discovery UI now calls global `POST /products/search/image`. No `X-Workspace-Id`. Results reuse the existing discovery table/inspector.

**2026-08-19 revision (Phase E Task 6):** Queue, channel, dashboard, and `GET /queues/stream` HTTP APIs require `X-Workspace-Id`. Queue/channel rows store `workspace_id` (migration `012`, closed to NOT NULL in Task 8 / migration `013`). Product aggregates remain global. Frontend workspace header plumbing is Task 9.

**2026-08-19 revision (Phase E Task 7):** Product remains a **global shared catalog** (no `workspace_id`). Affiliate remains a **global user-owned 1:1 profile** (no `workspace_id`). `POST /affiliates/join-campaign` now requires `X-Workspace-Id` and enrolls only into a campaign in that workspace.

**2026-08-19 revision (Phase E Task 8):** `Campaign.workspace_id`, `QueueItem.workspace_id`, and `TelegramChannel.workspace_id` are **NOT NULL** with `ON DELETE RESTRICT` (migration `013`). Upgrade **fails closed** if any of those columns are still NULL — no automatic backfill. `telegram_channel_id` remains **globally unique**.

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

`GET /auth/me` → `UserRead` (`id`, `email`, `full_name`, `role`, `is_active`, timestamps, additive `default_workspace_id`)

`default_workspace_id` is the caller's workspace UUID when they have **exactly one** membership; otherwise `null` (zero or multiple memberships). It does not invent a workspace for `ADMIN`. Tenant routes still require `X-Workspace-Id`.

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
| `GET /dashboard` | `dashboard.api.ts` | Connected | `DashboardOverview` — counts, activity, DB status. **Requires** `X-Workspace-Id`. Queue and channel aggregates/activity are scoped to the header workspace; **product** counts remain global (shared catalog). |
| `GET /ready` | `categories.api.ts` | Connected | `ReadinessResponse` — settings capability views; **database + redis only** |
| `GET /health` | — | Backend only | API process liveness (ops) |
| `GET /worker/health` | — | Backend only | Celery Beat→worker pipeline heartbeat (ops; root path, not under `/api/v1`) |

### 4.3 Products catalog

Product is a **global shared catalog**. There is no `products.workspace_id`, `user_id`, `campaign_id`, or `affiliate_id`. AliExpress identity (`aliexpress_product_id`) is globally unique; discovery, import, and Celery persistence upsert into the same table. Reads do **not** require `X-Workspace-Id`. ADMIN mutations are global catalog writes, not workspace-scoped. Queue items may attach the same Product from any workspace (`product_id` is existence-only).

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
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
| `POST /products/search/image` | `discovery.api.ts` | Connected | DS image search; env-gated (`ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH`). Global — no `X-Workspace-Id`. UI: `ImageSearchPanel` |
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
| `GET /queues` | `queue.api.ts` | Connected | Fetches up to 200 items for the `X-Workspace-Id` workspace. List items do **not** populate attempt summary fields (defaults: `last_attempt=null`, `failure_reason=null`, `retry_count=0`); `useQueueAttemptSummaryEnrichment` backfills non-published rows via `GET /queues/{id}` with bounded concurrency (5) |
| `GET /queues/{id}` | `queue.api.ts` | Connected | Returns `QueueRead` with attempt summary: `last_attempt`, `failure_reason`, `retry_count`. Used both for drawer detail and list enrichment |
| `GET /queues/{id}/attempts` | `queue.api.ts` (`getQueuePublishAttempts`) | Connected | `QueuePublishAttemptListResponse` — attempt history newest-first. Wired via `useQueuePublishAttempts`, rendered read-only in `QueueDetailsDrawer` while the drawer is open |
| `POST /queues` | `queue.api.ts` | Connected | Draft/queued creation from AI, products, discovery |
| `PATCH /queues/{id}` | `queue.api.ts` | Connected | Schedule, channel assign, content edit via drawer |
| `POST /queues/{id}/publish` | `queue.api.ts` | Connected | Single + bulk via `useQueuePublishingOperations`. Idempotency guard returns **409** when an unexpired `started`/`succeeded` attempt blocks the same content hash (no attempt row created on suppression); if the blocking attempt already `succeeded` but the queue row had not reached `published` (e.g. a batch rollback), the service heals the row to `published` server-side before returning 409. `QueueDetailsDrawer`'s primary action also serves as "Retry publish" (relabelled "إعادة المحاولة") — same endpoint, no new route |
| `DELETE /queues/{id}` | `queue.api.ts` | Connected | Bulk delete with confirmation; ORM cascade (`cascade="all, delete-orphan"` on `QueueItem.publish_attempts`) deletes attempt history — fixes a prior bug where deleting an item with attempts raised a `NOT NULL` violation instead of cascading |
| Publishing KPI "publishing" | `useQueuePublishingOperations` | Client-side | In-flight publish IDs (legitimately ephemeral) |
| Failed today KPI | `lib/operations.ts` (`resolveQueueFailure`, `getQueueOperationalStats`) | Connected | Backend-owned via `queue_publish_attempts` (`error_code`, including `dead_letter`); `resolveQueueFailure` prefers `item.last_attempt` / `item.failure_reason` and falls back to the client failure map only until enrichment for that row resolves |
| Real-time status stream | `queue` feature SSE client + `useQueueRealtimeInvalidation` | Connected (Phase A.2) | Authenticated `GET /api/v1/queues/stream` (SSE) **requires** `X-Workspace-Id`. Events: `queue.status_changed`, `queue.deleted`, `queue.attempt_*`. The subscriber callback delivers only events whose `workspace_id` matches the active workspace. Redis channel remains `queue-events`. Debounced TanStack Query invalidation (never cache patch). Adaptive polling fallback 5s→30s when SSE unavailable. No `dashboard.stats_updated`. Frontend SSE header support is Task 9. |

Queue and channel HTTP routes require `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Missing/invalid/unknown/non-member workspace → **403**. Unauthenticated → **401**. Cross-workspace queue or channel ids → **404** (existence is not leaked). `workspace_id` is taken from the header, never from the JSON body. `Campaign.workspace_id`, `QueueItem.workspace_id`, and `TelegramChannel.workspace_id` are **NOT NULL** with `ON DELETE RESTRICT` (migration `013`; upgrade aborts if NULL tenant rows remain). Attaching or publishing a queue item to a channel in another workspace → **404** (`Channel not found`). `GET /queues/{id}/attempts` authorizes the parent `QueueItem` in the active workspace first; attempts have no `workspace_id` column. `UserRole.ADMIN` may name any existing workspace without membership, still scoped to that header. Celery `process_publish_queue` / `publish_queue_item_task` remain workspace-agnostic.

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

Channel routes require `X-Workspace-Id` with the same membership/ADMIN rules as queues. Create assigns `TelegramChannel.workspace_id` from the header. `workspace_id` is **NOT NULL** (`ON DELETE RESTRICT`, migration `013`). `telegram_channel_id` remains **globally unique**.

### 4.8 Affiliates, campaigns, conversions

Affiliate is a **global user-owned 1:1 profile** (`affiliates.user_id` unique; `referral_code` globally unique). There is no `affiliates.workspace_id`. Workspace participation is `User → WorkspaceMembership → Workspace`. Profile routes stay Phase D owner-or-admin and do **not** require `X-Workspace-Id`. ADMIN profile mutation does not require a workspace header.

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET /affiliates/me`, `POST /affiliates`, `PATCH /affiliates/{id}`, `GET /affiliates` | Backend only | No MVP screens. User-owned profile (ADMIN list is global). No workspace header. |
| `POST /affiliates/join-campaign` | Backend only | **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Enrolls the caller's Affiliate into a campaign that belongs to the header workspace (`CampaignRepository.get_by_id_in_workspace`). Missing/invalid/unknown/non-member workspace → **403**. Campaign in another workspace or unknown id → **404** (`Campaign not found`). Inactive campaign → **409**. Duplicate enrollment → **409**. Tracking-link format unchanged. `UserRole.ADMIN` may name any existing workspace without membership, still scoped to that header (no all-workspaces bypass). Frontend header plumbing is Task 9. |
| `GET/POST/PATCH /campaigns/*` | Backend only | No MVP screens. **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Workspace members see/update only campaigns in the active workspace; missing/invalid/unknown/non-member workspace → **403**. Cross-workspace campaign ids → **404** (`Campaign not found`). `GET /campaigns/active` and `GET /campaigns/{id}` are no longer public. `POST /campaigns` remains admin/advertiser; `workspace_id` is taken from the header, not the body. `UserRole.ADMIN` may use any existing workspace without a membership row (global admin), still scoped to the header workspace. |
| `POST /conversions` | Backend only | **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Owner of `affiliate_id` or `ADMIN`. Non-owner **403**; anonymous **401**; missing/invalid/unknown/non-member workspace → **403**. Campaign must belong to the active workspace (**404** if not). The affiliate's user must be a workspace member (**404** if not), which blocks cross-workspace affiliate/campaign pairing. Workspace is derived from `Campaign.workspace_id` (no `conversions.workspace_id` column). `external_order_id` remains **globally unique**. Rate limit (policy): **30** / **1 minute** per user id (when valid access Bearer present) else client IP. Amount remains client-supplied; commission and `PENDING` status unchanged (access control only — not amount fraud verification). |
| `GET/PATCH /conversions/*` | Backend only | `GET /conversions/me` lists the caller's conversions whose campaign is in the active workspace. `GET /conversions` and `PATCH /conversions/{id}` remain admin-only and are workspace-scoped via the campaign relationship. No conversion delete route. `UserRole.ADMIN` may name any existing workspace without membership (global admin), still scoped to that header. No MVP screens. |

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
| **Dashboard** | `GET /dashboard` | Product counts remain global (shared catalog); queue/channel aggregates and queue activity are workspace-scoped via `X-Workspace-Id` |
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
- Queue, channel, dashboard, and `GET /queues/stream` require `X-Workspace-Id`. Isolation is per named workspace (ADMIN included). Product is a **global shared catalog** (no `workspace_id`; AliExpress upsert/uniqueness stay global). Affiliate is a **global user-owned 1:1 profile** (no `workspace_id`; unique `user_id` and `referral_code`). `POST /affiliates/join-campaign` requires `X-Workspace-Id` and is scoped to the named campaign workspace. Frontend workspace interceptor/header support is Task 9.
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
