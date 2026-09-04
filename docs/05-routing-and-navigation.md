# Routing and Navigation

**Document Version:** 2.1  
**Last Updated:** 2026-09-04

---

## 1. Purpose

Defines URL structure, sidebar navigation, page layouts, and **drawer vs route** boundaries after the 2026 workspace UI transformation.

---

## 2. Routing Principles

- **Feature-based URLs** — `/discovery`, not `/dashboard/discovery`
- **Clean deep links** — `/products/[id]`, `/ai?product=…`
- **Drawer for inspection** — row click opens slide-over; URL optional
- **SaaS-ready** — avoid patterns that block future `/workspace/{id}/…` prefix

---

## 3. Route Groups

```text
app/(auth)/          → Public (login)
app/(dashboard)/     → Protected (AuthGuard + middleware cookie)
```

---

## 4. Complete Route Map

```text
/
├── login
├── dashboard
├── products
│   └── [id]              ← deep link; primary UX is drawer on /products
├── discovery
├── ai                      ← ?product= | ?url= query params
├── queue
├── analytics
├── channels
├── settings
│   ├── general
│   ├── aliexpress
│   ├── ai
│   ├── telegram
│   ├── discovery
│   └── scheduling
└── profile                 ← header user menu only
```

**Deferred:** `/register`, workspace routes

---

## 5. Workspace Routes

### `/discovery`

Product discovery command center. Intent tabs drive API mode. Results grid with score popovers. **Drawer boundary:** `DiscoveryProductInspector` for product preview — does not change URL.

### `/products`

Inventory grid with layout controls. **Drawer boundary:** `ProductDetailsDrawer` on row click. `/products/[id]` remains for shareable deep links and legacy navigation from dashboard.

### `/ai`

AI Content Studio (`ContentWorkspaceView`). Accepts `?product={uuid}` or `?url=…` from discovery/products handoff. Session persisted in `sessionStorage`.

### `/queue`

Publishing Operations Center. KPI strip at top. **Drawer boundary:** `QueueDetailsDrawer` for post inspection. **Dialog boundary:** `QueueSchedulingDialog` for bulk/single schedule.

### `/analytics`

Workspace-scoped click and conversion KPIs. Date range controls, overview line chart, optional campaign funnel (`GET /campaigns/active` selector). Gated on active workspace id like Dashboard/Queue/Channels.

### `/channels`

Telegram channel registry. Full-page CRUD (no drawer).

### `/settings/*`

Workspace-scoped editable forms (`GET/PATCH /workspace-settings`). Secret/env status is read-only badges. Gated on active workspace id; PATCH requires admin or workspace OWNER (`can_edit`).

### `/profile`

User-global profile form (`GET/PATCH /auth/me`). Role and account status are read-only.

---

## 6. Sidebar Navigation

```text
Dashboard
Products
Discovery
AI Studio
Queue
Analytics
Channels
Settings
```

| Item | href | Notes |
| --- | --- | --- |
| Dashboard | `/dashboard` | |
| Products | `/products` | |
| Discovery | `/discovery` | |
| AI Studio | `/ai` | |
| Queue | `/queue` | |
| Analytics | `/analytics` | Workspace-scoped; between Queue and Channels |
| Channels | `/channels` | |
| Settings | `/settings/general` | Parent redirects to general |

**Not in sidebar:** Profile (header menu), Workspace switcher (hidden)

---

## 7. Navigation Item Shape

```typescript
{
  label: string;
  href: string;
  icon: LucideIcon;
  permissions?: ("admin")[];
}
```

Import actions and product delete are gated on `role === "admin"` in views, not route-level.

---

## 8. Drawer vs Dialog vs Page Boundaries

| Pattern | Use when | Examples |
| --- | --- | --- |
| **Drawer** | Inspect entity in context of list | Product details, discovery inspector, queue post |
| **Dialog** | Confirm destructive or short form | Delete, schedule, reset AI session |
| **Full page** | Shareable URL or multi-section detail | `/products/[id]`, settings sections |
| **Popover** | Compact secondary detail | AI score breakdown |

Drawers should not nest drawers. Esc closes top overlay (future standardization).

---

## 9. Cross-Workspace Handoffs

| From | Action | Target |
| --- | --- | --- |
| Discovery | Generate AI | `/ai?product={aliexpress_id}` or imported id |
| Discovery | Add to queue | Creates via API, optional `/queue` navigation |
| Products | Generate AI | `/ai?product={id}` |
| Products | Add to queue | Inline API create |
| AI Studio | Add to queue | `POST /queues` draft |
| Queue | Edit content | Opens drawer; links to `/ai` if re-generation needed |

---

## 10. Route Protection

```text
Request → middleware (session cookie present?)
       → AuthGuard (GET /auth/me valid?)
       → Feature view
```

401 → clear token → `/login`  
403 → inline error in feature (no dedicated `/unauthorized` route)

---

## 11. Error Routes

| File | Role |
| --- | --- |
| `app/global-error.tsx` | Framework error boundary |
| `app/not-found.tsx` | 404 |

---

## 12. Future Routing

```text
/workspace/[id]/products
/automation/workflows/[id]
/integrations
```

---

## 13. Related Documents

- [02-frontend-architecture.md](./02-frontend-architecture.md)
- [04-component-library.md](./04-component-library.md)
