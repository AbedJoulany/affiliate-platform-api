# API Integration Guide

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

**Backend source of truth:** FastAPI routers + Pydantic schemas  
**Default API base:** `http://localhost:8000/api/v1`  
**Frontend env:** `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`

OpenAPI: `/docs` · ReDoc: `/redoc` · Health: `GET /health` · Readiness: `GET /ready`

---

## 1. Authentication

### Login

`POST /auth/login` — `application/x-www-form-urlencoded`

| Field | Value |
| --- | --- |
| `username` | Email address |
| `password` | Password |

Response: `{ "access_token", "token_type": "bearer" }`

Protected requests: `Authorization: Bearer <jwt>`

No refresh token endpoint. On `401`, clear session and redirect to login.

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
| `POST /auth/login` | `auth.api.ts` | Connected | `LoginInput` → `TokenResponse` |
| `GET /auth/me` | `auth.api.ts` | Connected | `User` — role gating for admin import/delete |
| `POST /auth/register` | — | Backend only | Public registration not in UI |

### 4.2 Dashboard

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /dashboard` | `dashboard.api.ts` | Connected | `DashboardOverview` — counts, activity, DB status |
| `GET /ready` | `categories.api.ts` | Connected | `ReadinessResponse` — settings capability views |
| `GET /health` | — | Backend only | Ops/monitoring |

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
| `GET /products/discover` | `discovery.api.ts` | Connected | General mode |
| `GET /products/discover/hot` | `discovery.api.ts` | Connected | |
| `GET /products/discover/deals` | `discovery.api.ts` | Connected | |
| `GET /products/discover/trending` | `discovery.api.ts` | Connected | |
| `GET /products/discover/category/{id}` | `discovery.api.ts` | Connected | Requires `category_id` |
| `GET /products/search` | — | Backend only | Keyword mode uses discover paths |
| `POST /products/search/image` | — | Backend only | DS image search; env-gated |
| `POST /products/import` | `discovery.api.ts` | Connected | Single import (admin) |
| `POST /products/import/batch` | `discovery.api.ts` | Connected | Bulk import from selection bar |
| `POST /products/import-url` | — | Backend only | URL import not in UI |
| `GET /aliexpress/categories` | `categories.api.ts` | Connected | Category picker |
| `POST /aliexpress/import` | — | Backend only | Duplicate of `/products/import` |
| Discovery session persistence | `discovery/lib/session.ts` | Client-side | Filters/UI prefs in `localStorage` |
| Score breakdown display | `lib/product-score.ts` | Partial | Uses server `score`; breakdown fallback if no `score_breakdown` |
| `persist=true` on discover | — | Pending backend UI | API supports; UI does not expose toggle |

### 4.5 AI content

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `POST /ai-content/generate` | `ai.api.ts` | Connected | Extended request: `content_type`, `tone`, `language`, `length`, `instruction_modifiers` |
| Variant session | `useContentSession` | Client-side | Variants, edits in `localStorage` — not persisted server-side |
| Content quality scores | `ai/lib/scores.ts` | Client-side | Heuristic scoring for UI badges |
| Prompt profiles / history API | — | Pending backend | No save/list endpoints |

**GenerateContentInput** (frontend) ↔ **GenerateContentRequest** (Pydantic) — keep enums in sync via `features/ai/types/api.ts` and `app/schemas/ai_content.py`.

### 4.6 Publishing queue

| Endpoint | Frontend module | Status | Types / notes |
| --- | --- | --- | --- |
| `GET /queues` | `queue.api.ts` | Connected | Fetches up to 200 items for workspace |
| `GET /queues/{id}` | `queue.api.ts` | Connected | Available; primary UX uses list payload |
| `POST /queues` | `queue.api.ts` | Connected | Draft/queued creation from AI, products, discovery |
| `PATCH /queues/{id}` | `queue.api.ts` | Connected | Schedule, channel assign, content edit via drawer |
| `POST /queues/{id}/publish` | `queue.api.ts` | Connected | Single + bulk via `useQueuePublishingOperations` |
| `DELETE /queues/{id}` | `queue.api.ts` | Connected | Bulk delete with confirmation |
| Publishing KPI "publishing" | `useQueuePublishingOperations` | Client-side | In-flight publish IDs |
| Failed today KPI | `lib/operations.ts` | Client-side | Derived from client failure map |
| Real-time status stream | — | Pending backend | No WebSocket/SSE yet |

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
| `GET/POST/PATCH /conversions/*` | Backend only | No MVP screens |

---

## 5. View → Contract Mapping

| View | Primary endpoints | Key response fields |
| --- | --- | --- |
| **Discovery grid** | `GET /products/discover*` | `items[].score`, `rating`, `sales`, `discount`, `commission_rate`, `gallery_images` |
| **Discovery inspector drawer** | Same + optional import | Score breakdown, shipping, affiliate URL |
| **Products inventory** | `GET /products`, `GET /queues` | `ProductRead`, pipeline via queue join |
| **Product details drawer** | `GET /products/{id}` (from list) | `image_url`, `gallery_images`, `score`, `affiliate_url` |
| **AI Studio** | `POST /ai-content/generate` | `content`, `provider`, `content_type`, `tone`, `language` |
| **Queue KPI cards** | `GET /queues` + client ops | Status counts + publish failures |
| **Queue table/drawer** | `GET /queues`, `PATCH`, `POST publish` | `content`, `scheduled_at`, `channel_id`, `status` |
| **Schedule dialog** | `PATCH /queues/{id}` | `scheduled_at`, `channel_id`, `status: scheduled` |
| **Channels** | `GET/POST/PUT /channels` | `bot_permission_status`, `can_post_messages`, `is_active` |
| **Dashboard** | `GET /dashboard` | Product/queue/channel aggregates |
| **Settings** | `GET /ready` | `checks.database`, `checks.redis` |

---

## 6. Enums (must match backend)

- **User role:** `admin`, `affiliate`, `advertiser`
- **Product status:** `draft`, `active`, `inactive`, `archived`
- **Queue status:** `draft`, `queued`, `scheduled`, `published`
- **AI provider:** `openai`, `gemini`
- **Content type:** `social`, `description`, `telegram`, `facebook`, `blog`, `email`
- **Tone:** `professional`, `friendly`, `luxury`, `technical`, `urgent`, `minimal`, `persuasive`, `funny`
- **Language:** `ar`, `en`, `fr`, `de`
- **Length:** `short`, `medium`, `long`
- **Discovery mode:** `general`, `hot`, `deals`, `trending`, `category`
- **Discovery sort:** `orders_desc`, `rating_desc`, `discount_desc`, `price_asc`, `price_desc`, `newest`, `commission_desc`

---

## 7. Security & Tenancy Notes

- JWT in `sessionStorage`; middleware cookie is presence-only
- Import/delete require admin role in UI; backend enforces on routes
- Queue and channel routes are authenticated but **not user-scoped** — do not imply tenant isolation
- `/ready` checks PostgreSQL + Redis only — not Celery worker liveness or provider credentials

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
- [08-implementation-roadmap.md](./08-implementation-roadmap.md) — Upcoming API work (SSE, retries)
