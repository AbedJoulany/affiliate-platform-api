# Design System

**Document Version:** 2.2  
**Last Updated:** 2026-08-04

**2026-08-04 revision:** Phase A.1 frontend wiring is complete — "Failed today" and `QueueHealthBadge` now read backend attempt truth by default; the client failure map is a short-lived fallback only, not a rollout-in-progress state.

---

## 1. Purpose

Defines visual language, layout scales, density controls, status semantics, and feedback patterns for the AI Affiliate Automation Platform.

Design inspiration: Linear, Vercel, Stripe, Notion — clarity over decoration.

---

## 2. Core Principles

- **Minimalism** — subtle borders/shadows, generous whitespace
- **Consistency** — same badge/button/table patterns across workspaces
- **Hierarchy** — page purpose → primary actions → metrics → content
- **Efficiency** — bulk actions, drawer flows, keyboard-friendly controls

---

## 3. Color System (Semantic Tokens)

Implemented via CSS variables in `globals.css`:

| Token | Usage |
| --- | --- |
| `--background` / `--foreground` | Page canvas |
| `--surface` / `--surface-foreground` | Cards, drawers, panels |
| `--primary` / `--primary-foreground` | Primary actions, score meters |
| `--secondary` | Secondary buttons |
| `--muted` / `--muted-foreground` | Hints, metadata |
| `--border` | Dividers, table borders |

All components must use semantic tokens — no hardcoded hex in feature code.

---

## 4. Status Colors

### Product status (`ProductStatus`)

| Value | Badge tone | Label (AR) |
| --- | --- | --- |
| `draft` | neutral | مسودة |
| `active` | success | نشط |
| `inactive` | warning | غير نشط |
| `archived` | neutral | مؤرشف |

### Queue status (`QueueStatus`)

| Value | Badge tone | Notes |
| --- | --- | --- |
| `draft` | neutral | Editable pre-publish |
| `queued` | info | Ready for worker/API publish |
| `scheduled` | warning | Requires `scheduled_at` |
| `published` | success | Terminal success |

**Important:** `failed` is **not** a backend `QueueStatus` value. Publish failures are **backend-owned attempt data** on `queue_publish_attempts` (`status` = `started` \| `succeeded` \| `failed`; terminal exhaustion may set `error_code` = `dead_letter`). UI surfaces them via attempt history / failure reason (toasts and `QueueHealthBadge` resolve backend truth via `resolveQueueFailure`), never by inventing a queue status.

### Operational KPI tones (Queue workspace)

| KPI | Color intent | Notes |
| --- | --- | --- |
| Queued / Scheduled | neutral/info borders on stat cards | |
| Publishing (in-flight) | primary accent | Ephemeral client state |
| Published today | success (`emerald`) | |
| Failed today | error (`red`) | Backend-owned attempt failures via `getQueueOperationalStats`/`resolveQueueFailure`; client map is a short-lived fallback until per-item enrichment resolves |

### AI score quality bands

| Score range | Tone | Label |
| --- | --- | --- |
| ≥ 85 | success | ممتاز |
| ≥ 70 | info | إمكانية عالية |
| ≥ 55 | warning | متوسط |
| < 55 | neutral | يحتاج مراجعة |

### Channel permission status

`unknown` · `pending` · `granted` · `partial` · `denied` — map to neutral/warning/success/error respectively.

---

## 5. Typography

Current stack:

```css
Arial, "Noto Sans Arabic", sans-serif
```

| Level | Usage |
| --- | --- |
| Page title | `text-2xl font-semibold` (PageHeader) |
| Section title | `text-lg font-semibold` |
| Body | `text-sm` |
| Metadata | `text-xs text-muted-foreground` |
| KPI values | `text-xl font-semibold tabular-nums` |

---

## 6. Spacing & Layout Scale

Base unit: **4px**

Common gaps: `gap-2` (8px), `gap-3` (12px), `gap-4` (16px), `gap-5` (20px)

Page padding via `PageContainer`: responsive horizontal padding, max-width content.

Border radius: `rounded-lg` (cards, drawers), `rounded-md` (buttons, inputs), `rounded-xl` (dialogs).

---

## 7. Density Controls

Workspace tables support **`comfortable`** and **`compact`** density modes:

| Mode | Row padding | Use case |
| --- | --- | --- |
| `comfortable` | `py-3` / larger touch targets | Default, review workflows |
| `compact` | `py-1.5` / tighter text | High-volume scanning |

Implemented in:

- `ProductsToolbar` / `ProductsTable`
- `QueueToolbar` / `QueueTable`
- `DiscoveryResultsToolbar` (via `DiscoveryUiPrefs`)

Column visibility toggles persist in discovery UI prefs; products inventory uses in-session state.

---

## 8. Workspace Layout Pattern

```text
PageContainer
  PageHeader (title, description, actions)
  Optional KPI strip (QueueOperationalStats, DiscoveryStats)
  Toolbar (search, filters, density, export)
  Selection bar (bulk actions — when items selected)
  Primary content (table / workspace panels)
  Overlay layer (Drawer, Dialog, ToastOverlay, Popover)
```

---

## 9. Tables

Feature-local responsive tables (not yet a shared `DataTable`):

- Sticky header on scroll
- Checkbox column for bulk select
- Row hover + click → drawer
- Empty/loading via shared states
- Pagination: server (products API) or client slice (queue/discovery)

---

## 10. Drawer & Overlay Rules

**Drawer** (`Drawer` primitive):

- Width: `max-w-xl` typical; advanced filters may be wider
- Footer: primary + secondary actions, full-width on mobile
- Backdrop click closes; focus trap recommended (future a11y pass)

**Popover** (score breakdown):

- Anchored to score cell button
- Compact `ProductScoreBreakdown` variant
- Click outside closes

**Dialog** (`ConfirmDialog`, `QueueSchedulingDialog`, AI `ResetStudioDialog`):

- Centered modal, `z-50`
- Destructive actions use danger button variant

---

## 11. Toast Notification Rules

### Current implementation: `ToastOverlay`

Custom component at `components/common/ToastOverlay.tsx` — **not** `sonner` or `react-hot-toast` (neither is installed).

| Property | Value |
| --- | --- |
| Position | Fixed bottom-center (`bottom-5`, `z-[70]`) |
| Duration | 3500ms default, auto-dismiss |
| Tones | `success` (emerald border) · `error` (red border) |
| ARIA | `role="status"` or `role="alert"` |
| Dismiss | Manual close button |

**When to use toasts:**

- Bulk product delete success/failure
- Queue publish/schedule/delete outcomes
- Export completed

**When to use inline alerts:**

- Discovery run errors (persistent until next run)
- AI generation errors in studio
- Form validation messages

### Future: library toast

If adopting `sonner` or `react-hot-toast`:

- Single provider in `app/providers.tsx`
- Max 3 visible; queue subsequent
- Never duplicate inline + toast for the same error
- Match semantic success/error colors above

---

## 12. Forms & Validation

- Labels above inputs, helper text in `text-muted-foreground`
- Inline Zod errors in discovery filter panel
- Datetime inputs use `datetime-local` in scheduling dialog
- Loading state on submit buttons via `loading` prop

---

## 13. Loading & Empty States

Prefer **skeleton** loading (`Skeleton` primitive) over full-page spinners.

Every list workspace requires `EmptyState` with a primary action (e.g., "ابدأ الاكتشاف").

---

## 14. Dark Mode & RTL

- `next-themes` class strategy on `<html>`
- Mirror layout for RTL; icons that imply direction should flip where meaningful
- Score meters and badges must remain readable in both themes

---

## 15. Accessibility Targets

- Visible focus rings on interactive elements
- `aria-label` on icon-only buttons (Arabic labels)
- Drawer/dialog: `aria-modal`, labelled titles
- Table headers associated with sortable columns where applicable

---

## 16. Related Documents

- [04-component-library.md](./04-component-library.md) — Component inventory
- [07-development-guidelines.md](./07-development-guidelines.md) — Implementation rules
