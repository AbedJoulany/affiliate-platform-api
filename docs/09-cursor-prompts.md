# Cursor Development Prompts

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

Standard prompts for AI-assisted development. Cursor acts as implementer — architecture decisions live in `/docs`.

---

## 1. Working Rules

Before generating code:

1. Read relevant `/docs` files (especially `06-api-integration.md`)
2. Inspect existing feature code — extend, do not parallel-scaffold
3. Reuse `components/ui/primitives.tsx`, `components/common/*`, feature hooks
4. No new dependencies without approval (`sonner`, shadcn, Zustand, etc.)
5. Small incremental diffs
6. Thin App Router pages → client feature views
7. Use `ContentWorkspaceView` (not deleted `AIStudioView`)
8. Use `ToastOverlay` for transient feedback (not inline-only for bulk actions)
9. Drawer pattern for row detail — not new full pages unless requested

---

## 2. General Feature Template

```text
You are working on the AI Affiliate Automation Platform frontend.

Read before coding:
- docs/02-frontend-architecture.md
- docs/03-design-system.md
- docs/04-component-library.md
- docs/06-api-integration.md
- docs/07-development-guidelines.md

Task: [DESCRIBE FEATURE]

Requirements:
- Next.js 15 App Router, TypeScript
- Feature-based folders (components, api, hooks, types, lib)
- TanStack Query for server state
- Drawer for row inspection where applicable
- Zod validation for forms/filters
- Loading, empty, error states
- RTL + dark mode
- Match backend enum strings exactly

Before implementation, list:
1. Files to create/modify
2. Components to reuse
3. API endpoints + types
4. Data flow

Then implement.
```

---

## 3. Workspace-Specific Templates

### Discovery workspace

```text
Task: Extend Discovery workspace at features/discovery/

Reuse: DiscoveryView, DiscoveryResultsTable, DiscoveryProductInspector,
DiscoveryAiScoreCell → ProductAiScoreCell, DiscoveryAdvancedFiltersDrawer

API: GET /products/discover* via discovery.api.ts
Session: useDiscoverySession (sessionStorage)

Do not mock discovery results. Validate filters with Zod before run.
Score popover uses ProductScoreBreakdown — do not duplicate.
```

### Products inventory

```text
Task: Extend Products inventory at features/products/

Reuse: ProductsView, ProductsTable, ProductsToolbar, ProductDetailsDrawer,
ProductsSelectionBar, ToastOverlay, ConfirmDialog

API: GET/PATCH/DELETE /products via products.api.ts
Client state: useProductInventoryState (density, columns, selection)

Row click opens ProductDetailsDrawer — do not navigate away unless deep link requested.
Admin-only: delete, status change.
```

### Publishing queue

```text
Task: Extend Queue operations center at features/queue/

Reuse: QueueView, QueueOperationalStats, QueueTable, QueueDetailsDrawer,
QueueSchedulingDialog, QueueSelectionBar, ToastOverlay

API: GET/PATCH/POST publish/DELETE /queues via queue.api.ts

KPI "publishing" and "failed today" are client-derived — do not invent backend failed status.
Schedule via PATCH with scheduled_at + channel_id.
```

### AI Content Studio

```text
Task: Extend AI studio at features/ai/

Reuse: ContentWorkspaceView, useContentSession, ConfigControlBoard,
ToneMatrix, RichDocumentCanvas, VariantTabs, DistributionHub

API: POST /ai-content/generate with content_type, tone, language, length, instruction_modifiers

Variants persist in sessionStorage only — do not claim server history unless API exists.
Sync GenerateContentInput with app/schemas/ai_content.py.
```

---

## 4. Shared Component Template

```text
Task: Add shared component to components/common/

Check docs/04-component-library.md registry first — avoid duplicates.

Requirements:
- No API calls inside component
- Props explicit and typed
- Works in Drawer and table contexts
- Arabic aria-labels where icon-only
- Follow docs/03-design-system.md status colors
```

---

## 5. API Integration Template

```text
Task: Connect [feature] to backend

Contract source: docs/06-api-integration.md + OpenAPI /docs

Create/update:
- features/[feature]/types/api.ts
- features/[feature]/api/[feature].api.ts
- features/[feature]/hooks/use[Feature].ts

Rules:
- All HTTP via services/api-client.ts
- Query keys include all server filters
- Invalidate minimal keys on mutation
- Document integration status in 06 if adding new endpoint usage
```

---

## 6. Component Generation Guardrails

**Do:**

- Compose from `Button`, `Badge`, `Drawer`, `Popover`, `Skeleton`
- Stop propagation on table action cells
- Use `ConfirmDialog` for destructive bulk actions
- Keep components under ~200 lines; split if larger

**Do not:**

- Call `axios` in components
- Invent queue status `failed`
- Add `sonner` / `react-hot-toast` without approval
- Create second DataTable abstraction without explicit refactor task
- Imply multi-tenant isolation for queue/channels

---

## 7. Review Checklist Prompt

```text
Review the generated code against:

- docs/07-development-guidelines.md section 17 (code review checklist)
- docs/06-api-integration.md (connected vs client-side claims)
- docs/04-component-library.md (registry status accurate?)

List any architecture drift, missing states, or incorrect API status claims.
```

---

## 8. Historical Prompts

Sections for project initialization, design system bootstrap, auth, and API client from v1.0 remain valid for **greenfield evaluation only** — the project exists. See git history of `09-cursor-development-prompts.md` if needed.

---

## 9. Related Documents

- [07-development-guidelines.md](./07-development-guidelines.md)
- [08-implementation-roadmap.md](./08-implementation-roadmap.md)
