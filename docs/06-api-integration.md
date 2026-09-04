# API Integration Guide

**Document Version:** 2.13  
**Last Updated:** 2026-09-04

**2026-09-04 revision (Phase E Task 14):** Editable workspace settings (`GET/PATCH /workspace-settings`) and self-service `PATCH /auth/me`. Secrets stay env-only; responses expose connection booleans. See §4.11.

**2026-09-04 revision (Phase E Tasks 12–13):** Workspace-scoped analytics — `GET /analytics/overview` and `GET /analytics/campaigns/{campaign_id}/funnel`. Tenancy via Campaign FK chain; no `workspace_id` on clicks/conversions. See §4.10.

**2026-09-04 revision (Phase E Tasks 9–11 closeout):** Frontend workspace runtime (Task 9), Discovery image search UI (Task 10), and public click tracking (Task 11) documented with global vs workspace-scoped boundaries, migration `014_add_clicks`, live-verified click behavior, and conversion correlation. See §1.1, §4.9, §7.2.

**2026-08-04 revision:** Phase A.1 **frontend tasks are complete** — queue KPIs, `QueueHealthBadge`, and `QueueTable` now resolve failures from backend attempt data (`resolveQueueFailure`) with the client failure map only as a short-lived gap-filler until per-item enrichment resolves; `QueueDetailsDrawer` renders read-only publish attempt history from `GET /queues/{id}/attempts` and retries via the existing `POST /queues/{id}/publish`. Statuses below for §4.6 and §5 are updated accordingly. Also reflects three post-implementation bug fixes (scheduled publishing, queue item deletion, Telegram long-message publishing) — see [10-production-readiness.md](./10-production-readiness.md) §10.

**2026-08-08 revision (Phase B closeout):** Documented root operational endpoint `GET /worker/health` (Phase B Task 2). `/ready` semantics unchanged (database + Redis only).

**2026-08-13 revision (Phase D closeout):** Auth refresh tokens, route rate limits, and `POST /conversions` authorization. See §1 and §4.8. Design: [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

**2026-08-23 revision (Phase E Task 11):** Public `GET /clicks/{affiliate_campaign_id}` records a `Click` and 302-redirects to `AffiliateCampaign.tracking_link`. No JWT and no `X-Workspace-Id`. Server-generated `click_id` can be sent later as `POST /conversions.click_id`.

**2026-08-22 revision (Phase E Task 10):** Discovery UI now calls global `POST /products/search/image`. No `X-Workspace-Id`. Results reuse the existing discovery table/inspector.

**2026-08-19 revision (Phase E Task 6):** Queue, channel, dashboard, and `GET /queues/stream` HTTP APIs require `X-Workspace-Id`. Queue/channel rows store `workspace_id` (migration `012`, closed to NOT NULL in Task 8 / migration `013`). Product aggregates remain global. Frontend workspace header plumbing shipped in Task 9 (2026-09-04).

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
- Logout (`useLogout`): best-effort `POST /auth/logout`, then clears access + refresh tokens, active workspace id, middleware cookie, and TanStack Query cache → redirect `/login`. Tenant-protected routes are unreachable afterward until the user signs in again.

### Workspace initialization (Phase E Task 9)

After login, the frontend resolves the active workspace from the authenticated user — not from client guesswork alone:

```text
Login → POST /auth/login
  ↓
GET /auth/me
  ↓
default_workspace_id (when exactly one membership)
  ↓
sessionStorage key affiliate_active_workspace_id
  ↓
Axios interceptor attaches X-Workspace-Id on workspace-scoped paths only
```

`default_workspace_id` is returned when the caller has **exactly one** workspace membership; otherwise `null`. The client stores a usable UUID in `sessionStorage` when present (`frontend/src/lib/workspace.ts`, `frontend/src/services/session.ts`). Workspace-scoped API calls without a stored id fail client-side with `missing_workspace` before the network request is sent.

There is **no workspace selector UI** in this milestone. `NEXT_PUBLIC_WORKSPACE_ID` may seed development only; production flow relies on `/auth/me`.

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
| `PATCH /auth/me` | `auth.api.ts` | Connected | Self-service `full_name` / `email` only. **No** `X-Workspace-Id`. `role` and `is_active` rejected (**422** extra forbid). |
| `POST /auth/register` | — | Backend only | Public registration not in UI |

### 4.2 Dashboard

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /dashboard` | `dashboard.api.ts` | Connected | `DashboardOverview` — counts, activity, DB status. **Requires** `X-Workspace-Id`. Queue and channel aggregates/activity are scoped to the header workspace; **product** counts remain global (shared catalog). |
| `GET /ready` | `categories.api.ts` | Connected | `ReadinessResponse` — settings pages still use this for **database + redis** badges only |
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
| Real-time status stream | `queue` feature SSE client + `useQueueRealtimeInvalidation` | Connected (Phase A.2 + Task 9) | Authenticated `GET /api/v1/queues/stream` (SSE) **requires** JWT and `X-Workspace-Id`. Events: `queue.status_changed`, `queue.deleted`, `queue.attempt_*`. The subscriber callback delivers only events whose `workspace_id` matches the active workspace. Redis channel remains `queue-events`. Debounced TanStack Query invalidation (never cache patch). Adaptive polling fallback 5s→30s when SSE unavailable. No `dashboard.stats_updated`. Frontend sends workspace header via fetch-based SSE client (`useQueueEventStream`). Unauthenticated or missing workspace → **401** / client-side error (no stream). |

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
| `POST /affiliates/join-campaign` | Backend only | **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Enrolls the caller's Affiliate into a campaign that belongs to the header workspace (`CampaignRepository.get_by_id_in_workspace`). Missing/invalid/unknown/non-member workspace → **403**. Campaign in another workspace or unknown id → **404** (`Campaign not found`). Inactive campaign → **409**. Duplicate enrollment → **409**. Tracking-link format unchanged. `UserRole.ADMIN` may name any existing workspace without membership, still scoped to that header (no all-workspaces bypass). Frontend attaches header via Task 9 interceptor when integrated. |
| `GET/POST/PATCH /campaigns/*` | Backend only | No MVP screens. **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Workspace members see/update only campaigns in the active workspace; missing/invalid/unknown/non-member workspace → **403**. Cross-workspace campaign ids → **404** (`Campaign not found`). `GET /campaigns/active` and `GET /campaigns/{id}` are no longer public. `POST /campaigns` remains admin/advertiser; `workspace_id` is taken from the header, not the body. `UserRole.ADMIN` may use any existing workspace without a membership row (global admin), still scoped to the header workspace. |
| `POST /conversions` | Backend only | **Requires** `Authorization: Bearer <access_token>` and `X-Workspace-Id`. Owner of `affiliate_id` or `ADMIN`. Non-owner **403**; anonymous **401**; missing/invalid/unknown/non-member workspace → **403**. Campaign must belong to the active workspace (**404** if not). The affiliate's user must be a workspace member (**404** if not), which blocks cross-workspace affiliate/campaign pairing. Workspace is derived from `Campaign.workspace_id` (no `conversions.workspace_id` column). `external_order_id` remains **globally unique**. Rate limit (policy): **30** / **1 minute** per user id (when valid access Bearer present) else client IP. Amount remains client-supplied; commission and `PENDING` status unchanged (access control only — not amount fraud verification). |
| `GET/PATCH /conversions/*` | Backend only | `GET /conversions/me` lists the caller's conversions whose campaign is in the active workspace. `GET /conversions` and `PATCH /conversions/{id}` remain admin-only and are workspace-scoped via the campaign relationship. No conversion delete route. `UserRole.ADMIN` may name any existing workspace without membership (global admin), still scoped to that header. No MVP screens. |

### 4.9 Click tracking

Public redirect that records a durable `Click` and produces the optional `Conversion.click_id` attribution token. **No frontend.** A click does not necessarily result in a conversion — clicks are persisted independently.

**Data model** (`app/models/click.py`, migration `014_add_clicks.py` — revises `013`; migrations `010`–`013` unchanged):

```text
AffiliateCampaign
       │
       └── Click (affiliate_campaign_id FK, ON DELETE CASCADE)
             │
             └── click_id (unique, server-generated)
```

| Field | Notes |
| --- | --- |
| `id` | UUID primary key |
| `affiliate_campaign_id` | FK → `affiliate_campaigns.id`, indexed |
| `click_id` | Unique `String(64)`; default `uuid4().hex` (32 chars); compatible with nullable `Conversion.click_id` |
| `created_at`, `updated_at` | Timestamps |

There is **no** `workspace_id` column on `clicks`. Campaign tenancy is transitive: `Click → AffiliateCampaign → Campaign.workspace_id`.

**Public endpoint**

| Item | Value |
| --- | --- |
| Method / path | `GET /clicks/{affiliate_campaign_id}` (mounted at `/api/v1/clicks/{affiliate_campaign_id}`) |
| Auth | **None.** JWT is not required. Missing/invalid Bearer does not change the outcome. |
| Workspace header | **`X-Workspace-Id` is NOT required** and does not change behavior if sent. |
| Path parameter | `affiliate_campaign_id` — UUID of the `AffiliateCampaign` row (the join-campaign enrollment). |
| Success | **302** `Location` = stored `AffiliateCampaign.tracking_link`. |
| Persistence | One `Click` row is committed **before** the redirect response is returned. Clients cannot supply a `click_id`. |
| Rate limit | Existing Phase D Redis fixed-window primitive (`limit_clicks` in `app/core/rate_limit.py`); identity = client IP. Policy: **30** / **60 seconds**. **429** + `Retry-After` when exceeded. Redis failure fail-open. |
| Errors | Unknown enrollment id → **404**. Malformed UUID → **422** (path validation). Missing/blank or unsafe `tracking_link` → **422**. No `Click` row is created on error. |

**Processing order** (behavioral guarantee):

```text
Incoming GET
  → resolve AffiliateCampaign by id
  → validate tracking_link (http/https, host present, no userinfo, no control chars)
  → generate server-side click_id
  → persist Click + commit
  → HTTP 302 redirect to stored tracking_link
```

**Redirect security:** The endpoint is not an open redirect. Destination comes only from persisted `AffiliateCampaign.tracking_link`. Blank links, non-http(s) schemes (e.g. `javascript:`), missing hosts, embedded credentials, and client-supplied redirect URLs are rejected. Verified live: blank and `javascript:` tracking links return **422** with no new click row.

**Conversion correlation:** `POST /conversions.click_id` remains **optional** — conversions may omit click attribution. Unknown/opaque values (legacy `"click123"`) are still accepted when no matching `Click` row exists. When the value matches a stored `Click`, it must belong to the same affiliate+campaign enrollment or the conversion is **422** (`click_id does not match this affiliate campaign`). Cross-enrollment correlation is rejected.

**OpenAPI gap (code follow-up):** Runtime responses include **302**, **404**, **422**, and **429**, but route metadata documents primarily **302**. Markdown here is authoritative for integrators until OpenAPI metadata is extended in application code.

**Verified (live runtime, Task 11):** valid click **302** + persistence; public access without auth/workspace header; arbitrary workspace header ignored; unsafe/blank tracking links **422** without insert; conversion correlation **201** / cross-enrollment **422**; rate limit **429** + `Retry-After`; migration **014** applies; no `workspace_id` on `clicks`.

### 4.10 Analytics

Read-only workspace metrics over persisted clicks and conversions. **Connected** (`features/analytics`). A click does not require a conversion; analytics count both independently, then correlate when `Conversion.click_id` matches a `Click` on the same enrollment.

**Tenancy:** No `clicks.workspace_id` or `conversions.workspace_id`. Scope is `Click → AffiliateCampaign → Campaign.workspace_id` and `Conversion → Campaign.workspace_id` (same chain as conversion authorization). Cross-workspace campaign ids return **404** (`Campaign not found`) — existence is not leaked.

| Item | Value |
| --- | --- |
| Auth | `Authorization: Bearer` **and** `X-Workspace-Id` (same `HttpWorkspaceId` dependency as `/dashboard` / `/queues`). Missing JWT → **401**. Missing/invalid/non-member workspace → **403**. |
| Date range | Query `from` and `to` (ISO-8601). Default: last **30 days** ending now (UTC). Inclusive both ends. Inverted range or span **> 366 days** → **422**. `by_day` is filled per calendar day in the window (cap **366** points). |
| Indexes | Migration `015_add_analytics_indexes` (revises `014`): composite `(affiliate_campaign_id, created_at)` on `clicks`; `(campaign_id, created_at, status)` on `conversions`. Additive indexes only. |

**`GET /analytics/overview`**

```json
{
  "from": "2026-08-05T12:00:00Z",
  "to": "2026-09-04T12:00:00Z",
  "total_clicks": 0,
  "total_conversions": 0,
  "conversion_rate": 0.0,
  "total_revenue": "0.00",
  "by_day": [{ "date": "2026-08-05", "clicks": 0, "conversions": 0 }]
}
```

`conversion_rate` is `total_conversions / total_clicks` rounded to 4 decimals, or **0** when `total_clicks` is 0 (no division by zero). `total_revenue` is the sum of `Conversion.amount` in the window (all conversion statuses). Product catalog metrics are **not** included.

**`GET /analytics/campaigns/{campaign_id}/funnel`**

Per-campaign click→conversion funnel for a campaign in the active workspace.

```json
{
  "campaign_id": "<uuid>",
  "campaign_name": "…",
  "from": "…",
  "to": "…",
  "total_clicks": 0,
  "total_conversions": 0,
  "attributed_conversions": 0,
  "conversion_rate": 0.0,
  "total_revenue": "0.00",
  "by_day": [{ "date": "2026-08-05", "clicks": 0, "conversions": 0 }]
}
```

`attributed_conversions` counts conversions whose `click_id` matches a `Click` on an enrollment of that campaign. Unknown campaign or campaign in another workspace → **404**.

**Frontend:** `/analytics` — `useAnalyticsOverview` / `useCampaignFunnel`; query keys include workspace id and `from`/`to`. Campaign selector uses existing `GET /campaigns/active`. Charts: `recharts`.

**Not in this slice:** payouts, Product↔Campaign redesign, funnel metrics beyond click/conversion counts.

---

### 4.11 Workspace settings

**Connected** (`features/settings`). One `workspace_settings` row per workspace (`workspace_id` UNIQUE, `ON DELETE CASCADE`). Upserted on first `PATCH`. Missing header → **403**. Unknown workspace or non-member (non-admin) → **404** (`Workspace settings not found`). `GET` is allowed for members; `PATCH` requires `User.role = admin` or membership `OWNER`.

**Secrets never appear in any response.** Connection flags are booleans derived from “is this env var set” — not the value, not last-4 masking:

| Flag | Source |
| --- | --- |
| `connections.aliexpress` | `ALIEXPRESS_APP_KEY` **and** `ALIEXPRESS_APP_SECRET` set |
| `connections.telegram_bot` | `TELEGRAM_BOT_TOKEN` set |
| `connections.openai` | `OPENAI_API_KEY` set |
| `connections.gemini` | `GEMINI_API_KEY` set |
| `connections.image_search` | `ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH` |

`JWT_SECRET_KEY` and other infra secrets are not readable or writable. `QueueStatus` / `ProductStatus` are not settings fields.

**`GET/PATCH /workspace-settings`** — Bearer + `X-Workspace-Id`.

`PATCH` body is an allow-list (`extra=forbid`); unknown keys including secret names → **422**.

| Field | Section | Notes |
| --- | --- | --- |
| `timezone` | general, scheduling | IANA or `UTC` |
| `ui_language` | general | `ar` \| `en` |
| `aliexpress_target_currency` | AliExpress | 3-letter display pref |
| `aliexpress_ship_to_country` | AliExpress | 2-letter display pref |
| `aliexpress_target_language` | AliExpress | display pref |
| `default_ai_provider` | AI | `openai` \| `gemini` |
| `default_content_type` / `default_tone` / `default_content_language` / `default_content_length` | AI | existing content enums |
| `discovery_default_mode` | discovery | `general` \| `hot` \| `deals` \| `trending` \| `category` |
| `discovery_page_size` | discovery | 1–50 |
| `default_telegram_channel_id` | Telegram | UUID of a channel in this workspace, or null |

Response also includes `workspace_id`, `can_edit`, `connections`, timestamps (null until first PATCH).

Migration **`016_add_workspace_settings`** revises **`015`**. Additive table only.

**Profile (user-global):** `PATCH /auth/me` — no workspace header, matching `/affiliates*` (except join-campaign).

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
| **Analytics** | `GET /analytics/overview`, `GET /analytics/campaigns/{id}/funnel` | Workspace-scoped click/conversion KPIs and `by_day`; funnel uses `GET /campaigns/active` for the selector |
| **Settings** | `GET/PATCH /workspace-settings`, `GET /ready` | Workspace prefs + connection booleans; `/ready` is db/redis only |
| **Profile** | `GET/PATCH /auth/me` | `full_name`, `email`; role/`is_active` read-only |

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
- Rate limits: Redis fixed-window on login / refresh / conversions / public click redirect via route dependencies (not global middleware); fail-open on Redis errors; IP from `request.client.host` only (no `X-Forwarded-For` claim). Click policy: **30** / **60s** per IP → **429** + `Retry-After`
- `GET /clicks/{affiliate_campaign_id}` is public (no JWT, **no `X-Workspace-Id`**). Redirect targets come only from stored `AffiliateCampaign.tracking_link` after http(s) validation.
- `POST /conversions` requires authentication + affiliate ownership (ADMIN bypass); request-body identity is not an authorization source
- Import/delete require admin role in UI; backend enforces on routes
- Queue, channel, dashboard, analytics, workspace settings, and `GET /queues/stream` require `X-Workspace-Id`. Isolation is per named workspace (ADMIN included). Product is a **global shared catalog** (no `workspace_id`; AliExpress upsert/uniqueness stay global). Affiliate is a **global user-owned 1:1 profile** (no `workspace_id`; unique `user_id` and `referral_code`). `POST /affiliates/join-campaign` requires `X-Workspace-Id` and is scoped to the named campaign workspace. `PATCH /auth/me` is user-global (no workspace header). Frontend attaches the header on workspace-scoped paths only (Task 9). Public click tracking, discovery, and image search remain global.

### 7.2 Phase E tenancy boundary (Tasks 9–14)

Not all `/api/v1` routes are workspace-scoped. The implemented split:

| Workspace-scoped (require `X-Workspace-Id` when called from the SPA) | Global (no workspace header) |
| --- | --- |
| `GET /dashboard` | `GET/POST/PATCH/DELETE /products*` (catalog) |
| `GET /analytics/overview`, `GET /analytics/campaigns/{id}/funnel` | `GET /products/discover*`, `POST /products/search/image` |
| `GET/POST/PATCH/DELETE /queues*` | `GET /clicks/{affiliate_campaign_id}` (public) |
| `GET/POST/PUT/DELETE /channels*` | Affiliate profile routes (`GET/POST/PATCH /affiliates*`) except join-campaign |
| `GET /queues/stream` (SSE) | Discovery reads, auth session routes |
| `GET/POST/PATCH /campaigns*` | |
| `POST /affiliates/join-campaign`, `POST/GET/PATCH /conversions*` | |
| `GET/PATCH /workspace-settings` | `GET/PATCH /auth/me` (profile; no workspace header) |

Development CORS defaults allow `http://localhost:3000` and `http://127.0.0.1:3000` (`settings.cors_origins`) so the SPA can send `Authorization` and `X-Workspace-Id` cross-origin during local development.
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
- [08-implementation-roadmap.md](./08-implementation-roadmap.md) — Phase roadmap (Phase E Tasks 9–14 complete; payouts remain open)
- [planning/phase-a2-realtime-operations-design.md](./planning/phase-a2-realtime-operations-design.md) — Phase A.2 SSE design + closeout
- [planning/phase-c-prime-retry-hardening-design.md](./planning/phase-c-prime-retry-hardening-design.md) — Phase C' retry ownership + closeout
