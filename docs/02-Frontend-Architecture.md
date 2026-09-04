# Frontend Architecture

**Document Version:** 2.3  
**Last Updated:** 2026-09-04

**2026-09-04 revision (Phase E Task 14):** Editable workspace settings forms. See §4.5.

**2026-09-04 revision (Phase E Tasks 12–13):** Workspace-scoped Analytics (`features/analytics`, `/analytics`). See §3, §4.6, §4.7.

**2026-09-04 revision (Phase E Tasks 9–11):** Workspace tenancy runtime (Task 9), Discovery image search UI (Task 10). Click tracking is backend-only (Task 11). See §4.1, §4.6, §5, §6.

**2026-08-13 revision (Phase D):** Authentication lifecycle updated for opaque refresh tokens and single-flight 401 refresh. See §6 and [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

**2026-08-14 revision (Form & schema validation):** Feature-local Zod schemas and scheduling-dialog React Hook Form wiring. See §4.5. Milestone design: [planning/form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md).

---

## 1. Purpose

The frontend delivers a modern, workspace-oriented SaaS experience for affiliate automation. It is a **client application** — business logic stays in the FastAPI backend.

Responsibilities:

- Render data and workspace UI
- Manage interaction state (drawers, selection, density)
- Validate forms (Zod)
- Communicate with `/api/v1` via TanStack Query

---

## 2. Architecture Principles

| Principle | Rule |
| --- | --- |
| **API first** | No business rules in components; use feature API modules + hooks |
| **Feature-based** | Each domain owns `components/`, `api/`, `hooks/`, `types/`, `lib/` |
| **Thin routes** | App Router `page.tsx` files render one client feature view |
| **Composition** | Shared patterns in `components/common/`; primitives in `components/ui/` |
| **Drawer-first detail** | Row clicks open slide-over drawers; full pages for deep links only |

---

## 3. Project Structure

```text
frontend/src/

app/
  (auth)/login/
  (dashboard)/
    dashboard/
    discovery/
    products/ + [id]/
    ai/
    queue/
    channels/
    settings/*/
    profile/
  layout.tsx, providers.tsx

components/
  ui/primitives.tsx       # Button, Drawer, Popover, …
  layout/AppShell.tsx       # Sidebar, header, mobile nav
  layout/page.tsx           # PageContainer, PageHeader
  common/                   # ToastOverlay, ConfirmDialog, score cells, …

features/
  ai/           ContentWorkspaceView, useContentSession
  auth/         LoginForm, AuthGuard, useAuth
  categories/   AliExpress category fetch
  channels/     ChannelsView
  dashboard/    DashboardView
  analytics/    AnalyticsView, overview cards, charts
  discovery/    DiscoveryView, session + advanced filters
  products/     ProductsView, ProductDetailsDrawer, inventory hooks
  queue/        QueueView, scheduling, operational stats
  settings/     WorkspaceSettingsView (editable sections)

services/
  api-client.ts   # Axios + JWT interceptor
  session.ts      # Token storage

lib/
  workspace.ts    # Active workspace id, scoped path detection, query keys
  utils.ts
  product-score.ts
  validation/messages.ts  # Shared Arabic Zod message helpers (not i18n)
```

Hooks and API types are **feature-local**. There is no top-level `hooks/` or `types/` directory.

---

## 4. Workspace Architecture

### 4.1 Discovery (`features/discovery`)

| Piece | Role |
| --- | --- |
| `DiscoveryView` | Orchestrates intent tabs, filter bar, results table, selection bar, **ImageSearchPanel** |
| `useDiscoverySession` | Persists draft/committed filters + UI prefs to `sessionStorage` |
| `useDiscoveryQuery` | TanStack Query → `GET /products/discover*` |
| `useImageSearchQuery` | TanStack Query → global `POST /products/search/image` (no workspace header) |
| `ImageSearchPanel` | Image URL or file upload (≤5MB); switches Discovery into image-search mode |
| `DiscoveryProductInspector` | Slide-over drawer: score, images, import/AI/queue actions; **Search by image** from gallery URL |
| `DiscoveryAdvancedFiltersDrawer` | Extended filters (price, orders, shipping, sort) |
| `DiscoveryAiScoreCell` | Popover score breakdown in grid |

Data flow: user edits draft → commits search → API fetch → results rendered → row/inspector opens drawer. Image search bypasses intent tabs and renders through the same results table/inspector; it remains **global** (no `X-Workspace-Id`).

### 4.2 Products inventory (`features/products`)

| Piece | Role |
| --- | --- |
| `ProductsView` | Grid workspace with toolbar, table, selection bar |
| `useProducts` | Server list via `GET /products` (skip/limit/status) |
| `useProductInventoryState` | Client density, columns, search, sort, bulk selection |
| `ProductDetailsDrawer` | Row-click slide-over with image preview, score, pipeline badges |
| `products/lib/schemas.ts` | Shared `productStatusSchema` + Arabic labels/options (no status editor) |
| `DeleteProductsDialog` | Admin bulk/single delete confirmation |

Server pagination + client-side search/sort on the current page set. Queue index derived from `useQueue` for pipeline state badges.

### 4.3 AI Content Studio (`features/ai`)

| Piece | Role |
| --- | --- |
| `ContentWorkspaceView` | Replaces legacy `AIStudioView`; full workspace layout |
| `useContentSession` | Variants, config, product context in `sessionStorage` |
| `useGenerateContent` | Mutation → `POST /ai-content/generate` |
| `ConfigControlBoard`, `ToneMatrix`, `ContentTypeScroller` | Generation config UI |
| `RichDocumentCanvas`, `VariantTabs`, `VariantCompareDialog` | Edit/compare variants |
| `DistributionHub` | Queue draft creation, optional publish |

Generation payload includes `content_type`, `tone`, `language`, `length`, `instruction_modifiers` (synced with backend Pydantic schema).

### 4.4 Publishing queue (`features/queue`)

| Piece | Role |
| --- | --- |
| `QueueView` | KPI cards, toolbar, table, drawers, bulk actions |
| `useQueue` | `GET /queues` (up to 200 items for active workspace) |
| `useQueueEventStream` | Authenticated SSE; requires access token + active workspace id |
| `useQueueWorkspaceState` | Filters, density, pagination (client-side on fetched set) |
| `useQueuePublishingOperations` | Sequential bulk publish + client failure map |
| `QueueOperationalStats` | Queued / scheduled / publishing / published today / failed today |
| `QueueDetailsDrawer` | Post preview, channel, schedule, actions |
| `QueueSchedulingDialog` | Channel picker + datetime + presets → `PATCH /queues/{id}` |
| `queue/lib/schemas.ts` | Form-domain Zod: `queueSchedulingSchema`, `channelAssignmentSchema` |

`publishing` and `failedToday` KPIs are **client-derived** during publish operations; they are not backend queue statuses.

### 4.5 Form & schema validation

Extends the existing React Hook Form + Zod + `zodResolver` pattern (`LoginForm`, ChannelsView add-channel). Design-system `Input`/`Select` already forward refs. This is not a new form stack.

| Schema | Owner | Role |
| --- | --- | --- |
| `queueSchedulingSchema` | `features/queue/lib/schemas.ts` | Discriminated union `schedule` / `publish_now`; `channelId` required both paths; `scheduledAt` only for `schedule` |
| `channelAssignmentSchema` | same file | UUID string for the scheduling dialog’s `channelId`. No standalone assignment editor. |
| `productStatusSchema` | `features/products/lib/schemas.ts` | Canonical `draft`/`active`/`inactive`/`archived` + shared Arabic labels/options. No status editor. |
| `workspaceGeneralSchema` / `aliexpressDisplaySchema` / `aiDefaultsSchema` / `telegramDefaultsSchema` / `discoveryDefaultsSchema` / `schedulingDefaultsSchema` | `features/settings/lib/schemas.ts` | Per-section workspace settings; submit → `PATCH /workspace-settings` |
| `profileSchema` | `features/auth/lib/schemas.ts` | Self-service `full_name` / `email`; submit → `PATCH /auth/me` |
| Message helpers | `lib/validation/messages.ts` | `requiredField`, `invalidUuid`, `invalidDateTime` — not i18n. Queue and settings schemas use them; Login/Channels not retrofitted. |

`QueueSchedulingDialog` uses `register()`, preset `setValue(..., { shouldValidate: true })`, and `handleSubmit`. Submit mapping remains `channelId` → `channel_id`, `scheduledAt` → `scheduled_at` in `QueueView`. Frontend Zod is UX/input validation; backend Pydantic remains authoritative.

Discovery filter drafts still use the hand-written `validateDiscoveryDraft` (not Zod).

### 4.6 Multi-workspace tenancy runtime (Phase E Task 9)

The SPA distinguishes **tenant workspace context** (SaaS isolation for queue/channel/dashboard) from **feature workspaces** (page-level UI shells such as Discovery or Products). Task 9 implements tenant context only.

```text
Login → POST /auth/login
  ↓
GET /auth/me (AuthGuard / useCurrentUser)
  ↓
default_workspace_id when exactly one membership
  ↓
sessionStorage affiliate_active_workspace_id
  ↓
api-client attaches X-Workspace-Id on tenant paths only
```

| Module | Role |
| --- | --- |
| `lib/workspace.ts` | Read/write active workspace id; `isWorkspaceScopedPath`; `workspaceScopedQueryKey` |
| `services/session.ts` | Stores `affiliate_active_workspace_id`; cleared on logout |
| `services/api-client.ts` | Interceptor: attach header on `/dashboard`, `/queues`, `/channels`, `/campaigns`, `/conversions`, `/affiliates/join-campaign`, `/analytics`, `/workspace-settings`; strip elsewhere |
| `features/*/hooks` | Dashboard, queue, channels, analytics, settings hooks gate on `useActiveWorkspaceId()` |

**Workspace-scoped in the frontend:** Dashboard, queue list/detail/SSE, channels, analytics, settings.

**Global in the frontend:** Products catalog, Discovery (including image search), affiliate profile (`/profile`, `PATCH /auth/me`), public click redirects (no SPA).

Logout clears tokens, workspace id, middleware cookie, and TanStack Query cache, then redirects to `/login`. There is **no workspace selector UI** in this milestone.

### 4.7 Analytics (`features/analytics`)

| Piece | Role |
| --- | --- |
| `AnalyticsView` | Date range, KPI strip, overview chart, campaign funnel selector |
| `useAnalyticsOverview` / `useCampaignFunnel` | TanStack Query; keys include workspace id + `from`/`to` |
| `AnalyticsOverviewCards` | Clicks, conversions, rate, revenue |
| `ClickConversionChart` / `CampaignFunnelChart` | `recharts`; SVG `dir="ltr"` for axis geometry |

Workspace-scoped. Missing workspace id shows `NoActiveWorkspaceState`; charts are not rendered without an active workspace.

---

## 5. State Management

### Server state (TanStack Query)

Products, discovery results, queue, channels, dashboard, analytics, auth `/me`, categories.

Query keys include all server-side filter parameters. Mutations invalidate the smallest relevant key prefix.

### Client / session state

| State | Storage | Examples |
| --- | --- | --- |
| Auth token | `sessionStorage` | JWT access token |
| Refresh token | `sessionStorage` | Opaque refresh (never Bearer) |
| Active workspace id | `sessionStorage` | `affiliate_active_workspace_id` (from `/auth/me.default_workspace_id`) |
| Session marker | Cookie (`1`) | Middleware redirect only |
| Discovery session | `sessionStorage` | Filters, UI prefs, last response |
| AI content session | `sessionStorage` | Variants, config, active variant |
| Workspace UI | React `useState` | Drawer open, selection, density, toasts |

No global Zustand/Context auth provider — `AuthGuard` validates via `GET /auth/me`.

---

## 6. Authentication

```text
Login → POST /auth/login (form) → store access_token + refresh_token in sessionStorage
Protected route → middleware cookie check → AuthGuard → GET /auth/me
  → apply default_workspace_id to sessionStorage when present
Protected API → Authorization: Bearer <access_token>
  → X-Workspace-Id on tenant-scoped paths only (dashboard, queues, channels, campaigns, conversions, join-campaign)
401 (non-auth-session) → single-flight POST /auth/refresh → store rotated pair → retry once
Refresh failure / missing refresh → clear session → redirect /login
403 → surface forbidden; no refresh; no auto-logout
Logout → best-effort POST /auth/logout { refresh_token } → clear tokens + workspace id + query cache → /login
```

Phase D Task 5 (COMPLETE): refresh tokens are stored in `sessionStorage` only, sent only as JSON to `/auth/refresh` and `/auth/logout`, and never used as Bearer. Auth session paths (`/auth/login`, `/auth/refresh`, `/auth/logout`) are excluded from the refresh interceptor. A.2 SSE uses the access token plus active workspace id from Task 9 (`useQueueEventStream`).

---

## 7. Slide-Over Drawer Pattern

Shared `Drawer` primitive (`components/ui/primitives.tsx`):

- Fixed right panel, backdrop, title, footer actions
- Used by `ProductDetailsDrawer`, `DiscoveryProductInspector`, `QueueDetailsDrawer`, `DiscoveryAdvancedFiltersDrawer`
- Row click opens drawer; checkbox/actions use `stopPropagation`
- Drawer boundaries: read-only inspection + primary CTAs; destructive confirm uses `ConfirmDialog`

`Popover` used for compact overlays (`ProductAiScoreCell` score breakdown).

---

## 8. Error & Feedback

| Pattern | Location |
| --- | --- |
| `LoadingState`, `EmptyState`, `ErrorState` | `components/common/states.tsx` |
| `ToastOverlay` | Floating success/error toasts (Products, Queue) |
| Inline alerts | Discovery, AI Studio mutations |
| `ConfirmDialog` | Delete products, delete queue items, reset AI session |

---

## 9. Performance Guidelines

- Prefer server components for static shells; feature views are `"use client"`
- `keepPreviousData` on product list queries
- Lazy-load heavy dialogs only when open
- Client-side filter/sort on fetched slices — revisit server-side when catalog scale grows

---

## 10. RTL & Theming

- Root layout sets Arabic RTL (`dir="rtl"`)
- Semantic CSS variables for light/dark (`--background`, `--surface`, `--primary`, …)
- All new components must work in both themes without hardcoded colors

---

## 11. Related Documents

- [03-design-system.md](./03-design-system.md) — Visual tokens
- [04-component-library.md](./04-component-library.md) — Component registry
- [05-routing-and-navigation.md](./05-routing-and-navigation.md) — Route map
- [06-api-integration.md](./06-api-integration.md) — API contracts
- [planning/form-schema-validation-standardization-design.md](./planning/form-schema-validation-standardization-design.md) — Form & schema validation closeout
