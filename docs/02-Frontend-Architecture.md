# Frontend Architecture

**Document Version:** 2.1  
**Last Updated:** 2026-08-13

**2026-08-13 revision (Phase D):** Authentication lifecycle updated for opaque refresh tokens and single-flight 401 refresh. See §6 and [planning/phase-d-auth-security-design.md](./planning/phase-d-auth-security-design.md).

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
  discovery/    DiscoveryView, session + advanced filters
  products/     ProductsView, ProductDetailsDrawer, inventory hooks
  queue/        QueueView, scheduling, operational stats
  settings/     CapabilityView (read-only)

services/
  api-client.ts   # Axios + JWT interceptor
  session.ts      # Token storage

lib/
  utils.ts
  product-score.ts
```

Hooks and API types are **feature-local**. There is no top-level `hooks/` or `types/` directory.

---

## 4. Workspace Architecture

### 4.1 Discovery (`features/discovery`)

| Piece | Role |
| --- | --- |
| `DiscoveryView` | Orchestrates intent tabs, filter bar, results table, selection bar |
| `useDiscoverySession` | Persists draft/committed filters + UI prefs to `sessionStorage` |
| `useDiscoveryQuery` | TanStack Query → `GET /products/discover*` |
| `DiscoveryProductInspector` | Slide-over drawer: score, images, import/AI/queue actions |
| `DiscoveryAdvancedFiltersDrawer` | Extended filters (price, orders, shipping, sort) |
| `DiscoveryAiScoreCell` | Popover score breakdown in grid |

Data flow: user edits draft → commits search → API fetch → results rendered → row/inspector opens drawer.

### 4.2 Products inventory (`features/products`)

| Piece | Role |
| --- | --- |
| `ProductsView` | Grid workspace with toolbar, table, selection bar |
| `useProducts` | Server list via `GET /products` (skip/limit/status) |
| `useProductInventoryState` | Client density, columns, search, sort, bulk selection |
| `ProductDetailsDrawer` | Row-click slide-over with image preview, score, pipeline badges |
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
| `useQueue` | `GET /queues` (up to 200 items for workspace) |
| `useQueueWorkspaceState` | Filters, density, pagination (client-side on fetched set) |
| `useQueuePublishingOperations` | Sequential bulk publish + client failure map |
| `QueueOperationalStats` | Queued / scheduled / publishing / published today / failed today |
| `QueueDetailsDrawer` | Post preview, channel, schedule, actions |
| `QueueSchedulingDialog` | Channel picker + datetime + presets → `PATCH /queues/{id}` |

`publishing` and `failedToday` KPIs are **client-derived** during publish operations; they are not backend queue statuses.

---

## 5. State Management

### Server state (TanStack Query)

Products, discovery results, queue, channels, dashboard, auth `/me`, categories.

Query keys include all server-side filter parameters. Mutations invalidate the smallest relevant key prefix.

### Client / session state

| State | Storage | Examples |
| --- | --- | --- |
| Auth token | `sessionStorage` | JWT access token |
| Refresh token | `sessionStorage` | Opaque refresh (never Bearer) |
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
Protected API → Authorization: Bearer <access_token>
401 (non-auth-session) → single-flight POST /auth/refresh → store rotated pair → retry once
Refresh failure / missing refresh → clear session → redirect /login
403 → surface forbidden; no refresh; no auto-logout
Logout → best-effort POST /auth/logout { refresh_token } → clear session + query cache → /login
```

Phase D Task 5 (COMPLETE): refresh tokens are stored in `sessionStorage` only, sent only as JSON to `/auth/refresh` and `/auth/logout`, and never used as Bearer. Auth session paths (`/auth/login`, `/auth/refresh`, `/auth/logout`) are excluded from the refresh interceptor. A.2 SSE continues to use the access token from the existing session mechanism — unchanged by Phase D.

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
