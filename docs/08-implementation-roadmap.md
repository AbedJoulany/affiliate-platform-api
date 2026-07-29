# Implementation Roadmap

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

Consolidated feature tracker (replaces empty `PROJECT_STATUS.md`). See [06-api-integration.md](./06-api-integration.md) for endpoint-level status.

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
| Session persistence (filters/UI prefs) | ✅ | localStorage |
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
| Local session persistence | ✅ | localStorage |
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
| Publish failure tracking | ✅ | Client-side |
| Real-time status updates | ⬜ | See Phase A below |
| Dedicated retry orchestration | ⬜ | Manual re-publish only |

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

### Phase A — Real-time operations (Q3 2026)

**WebSockets / SSE for publishing queue**

- Stream queue item status transitions: `queued` → `scheduled` → `published`
- Surface Celery worker publish failures as events (today: client-only failure map)
- Fallback: TanStack Query polling with exponential backoff when SSE unavailable

**Deliverables:** Backend SSE endpoint or WebSocket channel; frontend subscription hook; KPI cards update live

### Phase B — Background workers & queue execution

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
- Idempotent publish tasks with deduplication keys
- Document Redis/Celery env in [10-production-readiness.md](./10-production-readiness.md)

### Phase C — Error handling & retries

**External API retry policy** (Telegram, AliExpress, OpenAI/Gemini):

| Provider | Strategy |
| --- | --- |
| AliExpress IOP | Existing rate limit + exponential backoff in `api_client.py` |
| Telegram | Retry 429/5xx with jitter; max 3 attempts; dead-letter queue item flag |
| AI providers | Retry transient 502/503; surface `AIProviderError` to UI |

**Queue publish failures:**

- Optional `failed` metadata table or audit log (without changing `QueueStatus` enum)
- UI retry button wired to `POST /queues/{id}/publish`
- Celery task retry with `countdown` for scheduled recovery

### Phase D — Form & schema validation standardization

- Shared Zod schemas in `features/*/lib/schemas.ts` mirroring Pydantic
- Drawer inline edits: product status, queue schedule, channel assignment
- React Hook Form + zodResolver for scheduling dialog
- Validation error copy in Arabic

### Phase E — Platform expansion (V2)

Multi-workspace tenancy · JWT refresh · Analytics `/analytics` · Editable settings · Image search UI · Admin bootstrap CLI · Click tracking · Payout module

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

---

## 5. Definition of Done (unchanged)

A feature is complete when: correct folder structure · reusable components · loading/empty/error states · TypeScript clean · design system compliance · API contract documented in `06-api-integration.md`

---

## 6. Related Documents

- [06-api-integration.md](./06-api-integration.md) — Integration matrix
- [10-production-readiness.md](./10-production-readiness.md) — Release gates & infra
- [09-cursor-prompts.md](./09-cursor-prompts.md) — AI development templates
