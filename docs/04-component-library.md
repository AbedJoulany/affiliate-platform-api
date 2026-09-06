# Component Library

**Document Version:** 2.3  
**Last Updated:** 2026-09-04

**2026-09-06 revision:** Product B analytics components (`AnalyticsView`, campaign funnel, click/conversion charts) were removed. The dashboard remains the Product A operational MEASURE surface.

**2026-08-04 revision:** Phase A.1 frontend wiring shipped — `QueueOperationalStats`, `QueueHealthBadge`, and `QueueDetailsDrawer` notes below updated from "planned" to implemented backend-truth behavior.

---

## 1. Purpose

Registry of shared and feature components across the platform. Status labels:

| Label | Meaning |
| --- | --- |
| **Implemented** | Exists and is used in production screens |
| **Partial** | Implemented with known gaps |
| **Planned** | Designed but not built |
| **Future** | Roadmap only |

Follow [03-design-system.md](./03-design-system.md) for visual rules.

---

## 2. Directory Layout

```text
components/ui/          → App-agnostic primitives
components/layout/        → Shell, page wrappers
components/common/        → Cross-feature patterns
features/*/components/  → Workspace-specific UI
```

---

## 3. UI Primitives (`components/ui/primitives.tsx`)

| Component | Status | Notes |
| --- | --- | --- |
| `Button` | Implemented | primary, secondary, outline, ghost, danger; loading |
| `Input` | Implemented | Text, datetime |
| `Select` | Implemented | Native select wrapper |
| `Textarea` | Implemented | AI content editing |
| `Card` | Implemented | Dashboard, settings |
| `Badge` | Implemented | Status + score quality tones |
| `Skeleton` | Implemented | Loading placeholders |
| `Drawer` | Implemented | Slide-over panels |
| `Popover` | Implemented | Score breakdown overlay |
| `Checkbox` | Planned | Bulk select uses native `<input type="checkbox">` |
| `Switch` | Planned | Channel active toggle uses button pattern |
| `Dialog` | Partial | `ConfirmDialog` + custom scheduling modal |
| `Dropdown Menu` | Partial | `ProductActionsMenu`, `QueueActionsMenu` |
| `Tooltip` | Planned | — |
| `Toast` | Partial | `ToastOverlay` (custom, not sonner) |

---

## 4. Layout Components

| Component | Status | Location |
| --- | --- | --- |
| `AppShell` | Implemented | `components/layout/AppShell.tsx` — sidebar, header, mobile drawer, nav, theme, user menu |
| `PageContainer` | Implemented | `components/layout/page.tsx` |
| `PageHeader` | Implemented | `components/layout/page.tsx` |
| `Sidebar` | Partial | Embedded in AppShell; extraction planned |
| `Header` | Partial | Embedded in AppShell |

---

## 5. Common / Shared Components

| Component | Status | Used by |
| --- | --- | --- |
| `EmptyState` | Implemented | All list workspaces |
| `LoadingState` | Implemented | All list workspaces |
| `ErrorState` | Implemented | All list workspaces |
| `ConfirmDialog` | Implemented | Products delete, queue delete, AI reset |
| `ToastOverlay` | Implemented | Products, Queue |
| `ProductAiScoreCell` | Implemented | Discovery + Products score columns (**AIScorePopover**) |
| `ProductScoreBreakdown` | Implemented | Popover + drawers |
| `ProductImageHoverPreview` | Implemented | Products table image column |
| `WorkspaceResultsToolbar` | Implemented | Shared toolbar pattern (density, columns, export) |
| `DataTable` | Planned | Feature-local HTML tables today |
| `SearchBar` | Partial | Inline search in workspace toolbars |
| `FilterPanel` | Partial | `DiscoveryFilterBar` + `DiscoveryAdvancedFiltersDrawer` |

### ProductAiScoreCell (AIScorePopover)

Interactive score cell with:

- Numeric score + quality badge + mini meter
- Click → `Popover` with `ProductScoreBreakdown`
- Uses server `score` + optional `score_breakdown`; falls back to documented weight explanation

---

## 6. Discovery Workspace Components

| Component | Status | Description |
| --- | --- | --- |
| `DiscoveryView` | Implemented | Main orchestrator |
| `DiscoveryHeader` | Implemented | Title + run controls |
| `DiscoveryIntentTabs` | Implemented | hot / deals / trending / category / general |
| `DiscoveryFilterBar` | Implemented | Keywords, rating, discount, category chips |
| `DiscoveryAdvancedFiltersDrawer` | Implemented | Price, orders, shipping, sort, page size |
| `DiscoveryFilterChip` | Implemented | Active filter display |
| `DiscoveryFilterPanel` | Implemented | Zod validation for draft params |
| `DiscoveryResultsTable` | Implemented | Grid with score cells, selection |
| `DiscoveryResultsToolbar` | Implemented | Density, columns, export CSV |
| `DiscoverySelectionBar` | Implemented | Bulk import, AI, queue handoff |
| `DiscoveryAiScoreCell` | Implemented | Thin wrapper → `ProductAiScoreCell` |
| `DiscoveryScoreBreakdown` | Implemented | Drawer-specific breakdown copy |
| `DiscoveryProductInspector` | Implemented | **Slide-over drawer** — images, score, commission, marketing triggers |
| `DiscoveryEmptyState` | Implemented | First-run / no-results states |
| `DiscoveryStats` | Implemented | Result count summary |

---

## 7. Products Inventory Components

| Component | Status | Description |
| --- | --- | --- |
| `ProductsView` | Implemented | Inventory workspace shell |
| `ProductsTable` | Implemented | Density, columns, row click, bulk select |
| `ProductsToolbar` | Implemented | Status filter, search, density, columns, export |
| `ProductsSelectionBar` | Implemented | Bulk delete, queue, AI, export |
| `ProductDetailsDrawer` | Implemented | **Slide-over** — aspect-ratio image, score breakdown, health badges, pipeline state, AI/queue CTAs |
| `ProductScoreCell` | Implemented | Inventory score display |
| `ProductHealthBadges` | Implemented | Data completeness indicators |
| `ProductActionsMenu` | Implemented | Row-level actions |
| `DeleteProductsDialog` | Implemented | Admin confirmation |
| `ProductDetailView` | Implemented | `/products/[id]` full page (deep link) |

---

## 8. AI Content Studio Components

| Component | Status | Description |
| --- | --- | --- |
| `ContentWorkspaceView` | Implemented | Replaces deleted `AIStudioView` |
| `ConfigControlBoard` | Implemented | Provider, language, length |
| `ContentTypeScroller` | Implemented | Platform/format selection |
| `ToneMatrix` | Implemented | Tone profile grid |
| `ProductSourcePicker` | Implemented | Product ID vs URL source |
| `PromptPipelinePreview` | Implemented | Prompt assembly preview |
| `AiSuggestionsPanel` | Implemented | Instruction modifiers |
| `RichDocumentCanvas` | Implemented | Editable generated content |
| `PerformanceScoreBadges` | Implemented | Client-side content quality scores |
| `VariantTabs` | Implemented | Multi-variant navigation |
| `VariantCompareDialog` | Implemented | Side-by-side variant diff |
| `DistributionHub` | Implemented | Queue draft + publish shortcuts |
| `ResetStudioDialog` | Implemented | Clear session confirmation |

`ToneMatrix` and `ContentTypeScroller` cover tone/type profile selection; there is no separate `PromptProfileSelector` component and no server-side profile persistence. Generation pending/error feedback is inline state in `ContentWorkspaceView` (`generation.isPending` / `generation.isError`), not a dedicated `GenerationStatus` component.

---

## 9. Queue / Publishing Components

| Component | Status | Description |
| --- | --- | --- |
| `QueueView` | Implemented | Operations center shell |
| `QueueOperationalStats` | Implemented | **KPI cards**: queued, scheduled, publishing, published today, failed today. Failed-today reads backend attempt truth via `getQueueOperationalStats`/`resolveQueueFailure`; client failure map is a short-lived fallback until per-item enrichment resolves |
| `QueueTable` | Implemented | Status, channel, schedule, content preview, actions. Row failure state resolved via `resolveQueueFailure` (backend-first) |
| `QueueToolbar` | Implemented | Search, status/channel filters, sort, density |
| `QueueSelectionBar` | Implemented | Bulk publish, schedule, delete |
| `QueueDetailsDrawer` | Implemented | Post preview, product/channel context, inline actions, read-only publish attempt history section (`useQueuePublishAttempts` → `GET /queues/{id}/attempts`). Primary action relabels to "إعادة المحاولة" (retry) when a failure is present and calls the existing `POST /queues/{id}/publish` — no new endpoint |
| `QueueSchedulingDialog` | Implemented | Channel picker, datetime, presets, publish-now |
| `QueueHealthBadge` | Implemented | Pipeline readiness (channel missing, etc.); surfaces backend `failure_reason` / latest failed attempt via `resolveQueueFailure`, with client fallback only until enrichment resolves |
| `QueueActionsMenu` | Implemented | Row actions menu |
| `SchedulePicker` | Partial | Inline in table + dialog; no calendar widget library |

---

## 10. Channels & Dashboard

| Component | Status |
| --- | --- |
| `ChannelsView` | Implemented — list, create, permission badges, active toggle |
| `DashboardView` | Implemented — stat cards, activity, system status |
| `CapabilityView` | Implemented — re-exports `WorkspaceSettingsView`; per-section editable forms |

## 10.1 Settings

| Component | Status | Description |
| --- | --- | --- |
| `WorkspaceSettingsView` | Implemented | Section forms (general, AliExpress, AI, Telegram, discovery, scheduling); workspace gating; admin/OWNER `can_edit` |
| `ConnectionStatusBadges` | Implemented | Env-derived connected/not-connected only — never secret values |
| `CapabilityView` | Implemented | Alias of `WorkspaceSettingsView` used by `/settings/*` pages |

Submit uses `ToastOverlay`. 422 field errors map onto RHF. Shared `Input`/`Select` primitives only.

---

## 11. Component Checklist (New Components)

Before adding a component:

- [ ] Reusable across features? → `components/common/`
- [ ] Primitive without business logic? → `components/ui/`
- [ ] Feature-specific? → `features/<name>/components/`
- [ ] Supports loading, empty, error states?
- [ ] Works RTL + dark mode?
- [ ] Drawer vs page boundary documented?

---

## 12. Planned Extractions

| Target | From |
| --- | --- |
| `DataTable` | ProductsTable, QueueTable, DiscoveryResultsTable |
| `Sidebar` / `Header` | AppShell |
| `ToastProvider` | ToastOverlay call sites |
| `SchedulePicker` | QueueSchedulingDialog + inline editors |

---

## 13. Future Components

`WorkspaceSwitcher` · `CommandPalette` · `NotificationCenter` · `WorkflowBuilder` · `AIChatAssistant`

Do not render `WorkspaceSwitcher` until multi-workspace backend exists.
