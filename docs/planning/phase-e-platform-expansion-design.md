# Phase E — Platform Expansion (V2)

**Status:** Task 0 — Architecture / Analysis / Planning (design document only; no implementation)
**Date:** 2026-08-14
**Precedes:** Phase E Task 1 (to be named on completion of this document, §26)
**Scope of this document:** Analysis and planning only. No source code, tests, database, configuration, or dependency changes were made while producing this document. Exactly one file was created: this one.

```text
Phase A.1 — Publishing Reliability & Status Truth   ✅ COMPLETE
Phase A.2 — Real-time Queue Updates (SSE)           ✅ COMPLETE
Phase B   — Background workers & queue execution    ✅ COMPLETE
Phase C'  — Non-Telegram retry hardening            ✅ COMPLETE
Phase D   — Authentication & Public-Endpoint Security ✅ COMPLETE
Form & Schema Validation Standardization            ✅ COMPLETE
Phase E   — Platform expansion (V2)                 ← THIS DOCUMENT (Task 0)
```

---

## 1. Executive Summary

This document is a repository-grounded architecture analysis for Phase E, covering seven roadmap-listed items: multi-workspace tenancy, analytics, editable settings, image search UI, admin bootstrap CLI, click tracking, and a payout module. It does **not** implement anything.

Headline findings:

1. **The repository is single-tenant today, with no exceptions.** No `workspace`, `tenant`, or `organization` table, column, or concept exists anywhere in `app/` or `frontend/src/`. `docs/10-production-readiness.md` §6 already states this explicitly: *"Tenancy | Queue/channel data **not user-scoped** — not multi-tenant safe."* This document treats that line as the authoritative starting point, not a discovery.
2. **The SSE event envelope already reserves a `workspace_id` field, always `null` today.** `app/events/schemas.py::QueueEventEnvelope.workspace_id: str | None = None`, set explicitly to `None` at construction in `app/services/queue.py::_build_queue_event`, with a docstring: *"`workspace_id` is reserved for future multi-tenancy and is always `null` today."* This is forward-looking scaffolding already committed by a prior phase, not something Phase E needs to invent. The frontend's `QueueEventEnvelope` TypeScript type (`features/queue/types/events.ts`) already mirrors this field.
3. **Frontend "workspace" terminology already in use (`WorkspaceResultsToolbar`, `useQueueWorkspaceState`, `docs/02-frontend-architecture.md` §4 "Workspace Architecture") means "feature work-surface / page," not "tenant."** This is a pre-existing, unrelated naming convention from the July 2026 UI redesign (design-system sense of "workspace" = a page like Discovery/Products/Queue). Phase E's "multi-workspace tenancy" is a different concept (SaaS tenant isolation) and must not be conflated with it in implementation naming. This document uses "workspace" only in the tenancy sense from §5 onward and flags this ambiguity as a naming risk for Task 1+.
4. **The frontend Settings UI already tells the user workspaces are deferred.** `frontend/src/app/(dashboard)/settings/general/page.tsx` renders a static capability row: `["مساحات العمل", "مؤجلة في الإصدار الحالي"]` ("Workspaces — deferred in the current release"). This is hardcoded display text, not a real capability check, but it confirms the product-level intent predates this analysis.
5. **There are two disconnected data subsystems in this repository**, not one: (a) the actively used Product → Discovery → Queue → Telegram-publishing pipeline, which has a full frontend, and (b) the Affiliate → Campaign → Conversion "affiliate network" subsystem, which is API-only and has **zero** frontend screens (`docs/06-api-integration.md` §4.8: "No MVP screens"). Click Tracking and the Payout Module belong entirely to subsystem (b). This materially changes their risk/value profile relative to Multi-workspace, Analytics-on-existing-data, Editable Settings, and Image Search, which all extend subsystem (a) or genuinely new-but-small surfaces. See §14, §24.
6. **Admin bootstrap is not a Phase-E-only problem — it is a pre-existing operational gap today.** `POST /auth/register` hardcodes `role=UserRole.AFFILIATE` (`app/auth/service.py:47`); there is no CLI, script, or seed mechanism anywhere in the repository (`Glob scripts/**` → 0 files; `docker-compose.yml` has no seed step). A fresh deployment of the **current, single-tenant** system already has no way to create its first admin without direct database access. See §12.
7. **Every entity Phase E would make workspace-scoped already follows one proven, reusable pattern in this codebase**: a nullable/optional FK plus a UUID primary key, following `UUIDPrimaryKeyMixin` + `TimestampMixin` (`app/core/model_mixins.py`), exactly as `RefreshToken`, `QueuePublishAttempt`, and `AffiliateCampaign` already do. Multi-workspace tenancy does not require inventing a new modeling convention — see §7.
8. **`GET /queues/stream` fans events out to every connected authenticated client with zero filtering today.** `EventBroadcaster.publish()` (`app/events/broadcaster.py:37-52`) iterates *all* subscribers unconditionally. Any authenticated user already receives every queue event in the system. This is consistent with finding #1 (not user-scoped) and is the concrete mechanism that would need a filter step for workspace isolation — not a redesign of A.2's transport. See §17.

**Overall Phase E sequencing conclusion (detailed in §18–§20):** Multi-workspace tenancy is a genuine prerequisite for Campaign/Conversion/Analytics/Click-Tracking/Payout work (because those either already have partial user-ownership evidence or would need it to mean anything), but it is **not** a prerequisite for Image Search UI or Admin Bootstrap CLI's minimal form. The safest Task 1 is **not** "implement multi-tenancy" — it is a narrow, additive, low-risk slice (§20).

---

## 2. Current Repository State

Verified directly against the repository at the time of this analysis (branch state as checked out; no commits made by this task).

| Area | State |
| --- | --- |
| Backend framework | FastAPI + SQLAlchemy 2.0 async + Alembic; 13 route modules under `app/api/v1/` (`app/api/v1/router.py`) |
| Latest migration | `009_add_refresh_tokens.py` (revises `008`) — next would be `010` |
| Backend test files | 39 files under `tests/` (`Glob tests/*.py`) |
| Frontend framework | Next.js App Router, TanStack Query, Axios, Zod + React Hook Form (Form & Schema Validation Standardization, complete) |
| Frontend routes | 23 files under `frontend/src/app/**` — `dashboard`, `products`, `discovery`, `ai`, `queue`, `channels`, `settings/*` (6 sub-pages), `profile`, `login`; **no** `/analytics` route exists today despite being named in the roadmap |
| Auth | Access JWT (30 min) + opaque refresh token (7 days, PostgreSQL `refresh_tokens`, Phase D) — see §6 |
| Real-time | SSE `GET /queues/stream`, Redis Pub/Sub `queue-events` channel, in-process `EventBroadcaster` fan-out (Phase A.2) |
| Background jobs | Celery worker + beat; `process_publish_queue` (60s), discovery refresh (hot/trending 6h, categories 24h), `worker_heartbeat` (30s) |
| Tenancy | **None.** Confirmed by direct repository inspection (§4) and by `docs/10-production-readiness.md` §6's own explicit statement |

---

## 3. Existing Architecture Relevant to Phase E

**Backend module map (evidence: `Glob app/models/*.py`, `Glob app/api/v1/*.py`):**

| Module | Files | Role |
| --- | --- | --- |
| `app/auth/` | `models.py` (User), `router.py`, `dependencies.py`, `security.py`, `service.py`, `repository.py`, `schemas.py` | Authentication, JWT, refresh tokens (Phase D) |
| `app/models/` | `user.py` (re-exports `app.auth.models.User`), `affiliate.py`, `campaign.py`, `conversion.py`, `product.py`, `queue.py`, `channel.py`, `refresh_token.py`, `aliexpress_category.py`, `enums.py`, `base.py` | SQLAlchemy ORM models |
| `app/api/v1/` | `affiliates.py`, `campaigns.py`, `conversions.py`, `product_discovery.py`, `products.py`, `channels.py`, `ai_content.py`, `queue_stream.py`, `queues.py`, `aliexpress.py`, `dashboard.py` | Routers, all mounted under `/api/v1` in `router.py` |
| `app/events/` | `schemas.py`, `publisher.py`, `broadcaster.py`, `deps.py`, (`consumer.py` per A.2 design) | Phase A.2 SSE/Redis event pipeline |
| `app/worker/tasks/` | `publishing.py`, `discovery.py`, `health.py` | Celery tasks |
| `app/repositories/` | `dashboard.py`, `conversion.py`, `queue.py`, `affiliate.py`, `channel.py`, `base.py`, `product.py`, `campaign.py` | Repository pattern, one per aggregate |
| `app/core/` | `config.py` (env `Settings`), `database.py`, `enums.py`, `model_mixins.py`, `rate_limit.py` | Cross-cutting infrastructure |

**Frontend module map (evidence: `Glob frontend/src/features/*`, `Glob frontend/src/app/**/*.tsx`):**

| Feature | Backend it consumes | UI maturity |
| --- | --- | --- |
| `features/auth` | `/auth/*` | Full (login, session, guard) |
| `features/dashboard` | `GET /dashboard` | Full (counts, activity, system status) |
| `features/discovery` | `GET /products/discover*` | Full workspace (tabs, filters, drawer, bulk import) |
| `features/products` | `GET/PATCH/DELETE /products` | Full inventory grid |
| `features/ai` | `POST /ai-content/generate` | Full content studio, session-only persistence |
| `features/queue` | `/queues/*`, SSE `/queues/stream` | Full, real-time (Phase A.2) |
| `features/channels` | `/channels/*` | Full CRUD minus delete |
| `features/settings` | `GET /ready` only | Read-only `CapabilityView` pages, **no settings API consumer anywhere** |
| `features/categories` | `/aliexpress/categories` | Supporting picker for discovery |
| — | `/affiliates/*`, `/campaigns/*`, `/conversions/*` | **No feature folder exists.** Confirmed absent — not partially built, entirely unconsumed |

---

## 4. Current Ownership / Tenancy Model

### 4.1 Direct answers to the required questions

- **Is the current system single-tenant?** Yes. No workspace/tenant/organization concept exists in `app/models/`, `app/schemas/`, `app/api/`, or `frontend/src/`. Confirmed by exhaustive `Grep` for `workspace|tenant` across `app/` (only matches: the reserved, always-null SSE field, and an unrelated `Settings` class name) and across `frontend/src/` (only matches: the pre-existing UI-workspace naming convention, §1 finding 3).
- **Is ownership user-based, affiliate-based, global, or mixed?** Mixed, and inconsistently applied:
  - User-based (enforced): `RefreshToken.user_id`, `Affiliate.user_id` (1:1, unique), `POST /conversions` ownership-or-admin (Phase D).
  - User-based (present but unenforced on reads): `Campaign.advertiser_id` (nullable FK, `ON DELETE SET NULL`) — no route checks whether the caller is the owning advertiser; `GET /campaigns/active` and `GET /campaigns/{id}` are fully public/unauthenticated (`app/api/v1/campaigns.py:30-47`); `PATCH /campaigns/{id}` only requires *any* authenticated user (`get_current_user`), not the owning advertiser or an admin (`app/api/v1/campaigns.py:60-70`) — this is an existing authorization gap, not introduced by this analysis, and is called out again in §6.4 and §18 as a risk that predates Phase E.
  - Global / no ownership boundary at all: `Product`, `QueueItem`, `QueuePublishAttempt`, `TelegramChannel`, `AliExpressCategory`.
- **Which entities are globally shared?** `Product`, `QueueItem`, `TelegramChannel`, `AliExpressCategory` (category cache). Confirmed by absence of any owner/user/workspace column on these models (§4.2 table).
- **Which entities are currently owned by a user?** `RefreshToken` (user_id, enforced), `Affiliate` (user_id, unique, enforced at the DB level), `Campaign` (advertiser_id, present but **not** enforced by any route today).
- **Which entities have no ownership boundary?** `Product`, `QueueItem`, `QueuePublishAttempt`, `TelegramChannel`, `AliExpressCategory`.
- **Which APIs implicitly assume one global workspace?** `GET/POST/PATCH/DELETE /products`, `GET/POST /products/discover*`, `GET/POST/PATCH/DELETE /queues`, `GET /queues/{id}/attempts`, `GET /queues/stream`, `GET/POST/PUT/DELETE /channels`, `GET /aliexpress/categories`, `GET /dashboard`. All are authenticated (except discovery reads and image search) but not scoped to any owner — any authenticated user sees and can mutate all of this data. This exact sentence is independently confirmed by `docs/06-api-integration.md` §7: *"Queue and channel routes are authenticated but **not** user-scoped — do not imply tenant isolation."*

### 4.2 Entity Ownership Matrix

| Entity | Current owner | Current scope | Workspace candidate | Notes |
| --- | --- | --- | --- | --- |
| `User` (`app/auth/models.py`) | — (root identity) | Global | N/A — becomes the membership subject, not itself scoped | `role` ∈ {admin, affiliate, advertiser} (`app/core/enums.py`); no per-user workspace list today |
| `RefreshToken` | `user_id` (FK, cascade delete) | User-scoped | **No** — stays user-scoped; a user may belong to multiple workspaces and refresh tokens authenticate the user, not a workspace session | Phase D invariant; must not be touched by Phase E (§23 boundary) |
| `Affiliate` | `user_id` (FK, **unique** — 1:1) | User-scoped | **Product decision required** — could stay 1-per-user-globally, or become 1-per-(user, workspace) | The existing `unique=True` on `user_id` is the exact constraint that would need to change (→ `UniqueConstraint(user_id, workspace_id)`) if a user should be able to hold separate affiliate profiles per workspace. No repository evidence indicates this is wanted |
| `AffiliateCampaign` (join table) | Derived from `affiliate_id` + `campaign_id` | Derived | Derived — follows `Campaign`'s decision | `UniqueConstraint(affiliate_id, campaign_id)` already named `uq_affiliate_campaign`; unaffected if both parents share one workspace |
| `Campaign` | `advertiser_id` (nullable FK, `ON DELETE SET NULL`) | **Weakly** user-scoped — column exists, **zero routes enforce it** | **Strong candidate** | This is the clearest pre-existing "shape of ownership that tenancy should formalize" in the whole schema — closer to workspace-scoped than any other entity, just unenforced |
| `Conversion` | Indirectly via `affiliate_id` → `Affiliate.user_id` | User-scoped (enforced since Phase D, `record_conversion`) | Derived from `Affiliate`/`Campaign` | `external_order_id` is **globally unique** today (`app/models/conversion.py:32`) — becomes a cross-workspace collision risk under tenancy, see §7 |
| `Product` | None | Global / shared catalog | **Product decision required — do not assume** | `aliexpress_product_id` is **globally unique** (dedupes AliExpress catalog items across the whole system). Making products workspace-scoped would either (a) duplicate catalog rows per workspace (storage/import-cost multiplier) or (b) require a shared-catalog + per-workspace-selection model (not evidenced anywhere in this repository) |
| `QueueItem` | None | Global | **Strong candidate** | Each tenant needs an isolated publish queue; no existing signal argues for a shared queue across tenants |
| `QueuePublishAttempt` | Derived from `queue_id` | Derived | Derived from `QueueItem` | Historical/audit record; must not be repurposed to drive `QueueItem.status` (existing docstring constraint, `app/models/queue.py:114-119`) — unaffected by workspace_id addition |
| `TelegramChannel` | None | Global | **Strong candidate** | `telegram_channel_id` is **globally unique** — two workspaces registering the same Telegram channel is an unlikely but real collision case under tenancy, see §7 |
| `AliExpressCategory` | None | Global (external reference cache) | **No** — recommend stays global | This is external catalog reference data (category IDs from AliExpress), not tenant data; duplicating it per workspace has no evidenced benefit |
| `RefreshToken.replaced_by_id` chain | N/A | N/A | N/A | Not an entity; listed for completeness only |

### 4.3 Summary

Confirms the docs' own framing (`docs/10-production-readiness.md` §6): this is a single-tenant application where two subsystems (Product/Queue/Channel-publishing, and Affiliate/Campaign/Conversion) have **independently evolved partial, inconsistent ownership models**, and neither is enforced end-to-end. Multi-workspace tenancy in Phase E is not "adding a new concept to a clean slate" — it is "introducing one coherent ownership model across two subsystems that currently disagree about whether ownership exists at all."

---

## 5. Multi-Workspace Architecture Analysis

### 5.1 Workspace model — options considered

**Option A — Workspace + owner-only (no membership table).**
`workspaces(id, name, owner_user_id)`. One user = one implicit member (the owner). Simplest possible schema; no new join table.

**Option B — Workspace + `WorkspaceMembership` join table (recommended).**
`workspaces(id, name, created_by_user_id)` + `workspace_memberships(id, workspace_id, user_id, role, created_at)`, unique on `(workspace_id, user_id)`. Supports 1-or-more users per workspace from day one.

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the decision? | **Recommendation: Option B.** |
| 2 | Why? | This repository already has a proven precedent for exactly this shape: `AffiliateCampaign` is a junction table joining two aggregates with a `UniqueConstraint` and a `role`-adjacent status concept. `WorkspaceMembership` is architecturally identical — a join table between `User` and `Workspace` with a per-row `role`. Reusing an already-proven, already-reviewed pattern is lower-risk than inventing a new one. |
| 3 | Evidence | `app/models/affiliate.py:54-76` (`AffiliateCampaign`) is the direct structural precedent. `app/models/refresh_token.py` and `app/models/queue.py`'s `QueuePublishAttempt` both show this codebase's consistent convention: new relationship concepts get their own table with `UUIDPrimaryKeyMixin` + `TimestampMixin`, not a denormalized column bag. |
| 4 | Alternatives considered | Option A (owner-only, no membership table). |
| 5 | Why Option A is not recommended (not rejected outright — flagged as viable) | Option A is simpler and *would* satisfy every piece of repository evidence available today (no evidence of a "team" requirement exists). It is rejected as the recommendation, not because it's wrong, but because retrofitting a membership table onto an owner-only design later is a strictly harder migration (existing rows have no membership rows to backfill, and "owner" semantics must be re-derived) than building the join table now while there is no production data to migrate. This is the same reasoning Phase D's Decision 1 used for refresh-token storage (§5 of that document): build the version that doesn't need a second migration if the *cheap* extra table is added now. **This is a recommendation, not a fact established by repository evidence** — no data exists today to prove multi-user workspaces are actually needed. |
| 6 | Confidence | Medium. Flagged explicitly as `Product decision required`: does Phase E need >1 user per workspace at all, ever? If the product answer is "definitively no, ever" then Option A is simpler and should be chosen instead. |

**Minimal schema (design only — not implemented in this task):**

```text
workspaces
  id              UUID PK
  name            VARCHAR(255) NOT NULL
  created_by_user_id  UUID FK -> users.id, ON DELETE SET NULL, nullable
  created_at / updated_at   (TimestampMixin)

workspace_memberships
  id            UUID PK
  workspace_id  UUID FK -> workspaces.id, ON DELETE CASCADE, indexed
  user_id       UUID FK -> users.id, ON DELETE CASCADE, indexed
  role          VARCHAR / Enum (e.g. "owner", "member") — Product decision required on exact roles
  created_at / updated_at   (TimestampMixin)
  UniqueConstraint(workspace_id, user_id)
```

This follows the existing `UUIDPrimaryKeyMixin` + `TimestampMixin` + `ON DELETE CASCADE` conventions exactly (`app/core/model_mixins.py`; compare `RefreshToken`, `AffiliateCampaign`).

### 5.2 Active workspace, switching, defaults

- **Active workspace concept:** Not established by current repository evidence (nothing like it exists). **Recommendation:** the active workspace is a per-request, explicitly supplied value (see §5.3 for transport), not a piece of server-side session state — this avoids adding any new stateful concept beyond what `WorkspaceMembership` already provides as the source of truth.
- **Default workspace:** **Recommendation:** on first login post-bootstrap, if a user has exactly one membership, treat it as the default (client-side convenience only — the server never assumes a default; every workspace-scoped request must still name its workspace explicitly, see §5.3). If a user has zero memberships, no workspace-scoped route should be reachable (existing pattern: `AffiliateRepository.get_by_user_id` returning `None` today raises `NotFoundError`, e.g. `app/services/conversion.py:86-88` — the same "absence is a domain error, not a silent default" convention should extend to workspace membership).
- **Workspace creation:** **Product decision required** — can any authenticated user create a workspace (self-service SaaS signup model), or only an admin (managed/enterprise model)? No repository evidence resolves this; the existing `POST /auth/register` hardcoding `role=UserRole.AFFILIATE` (§1 finding 6) is weak evidence *against* an open self-service model, since this repository has consistently kept account/role creation admin-gated or fixed, not user-driven.
- **Admin behavior / `User.role` interaction:** **Recommendation:** keep `User.role` (admin/affiliate/advertiser) exactly as-is and orthogonal to `WorkspaceMembership.role`. A platform `ADMIN` (global role) should not need workspace membership to perform cross-workspace operations (e.g., the bootstrap CLI, support tooling) — this mirrors the already-proven pattern where `ConversionService.update_status` bypasses ownership entirely for `UserRole.ADMIN` (`app/services/conversion.py:69-70`). Workspace-level roles (e.g., "owner"/"member" within one workspace) are a **separate, additive** axis, not a replacement for the existing global `User.role` enum. This directly answers §5.B's "Existing `User.role` interaction" requirement: no change to the enum or its existing route-level `require_roles(...)` usage is needed.

### 5.3 Authorization — workspace context source

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the decision? | **Recommendation: server-validated request header (e.g. `X-Workspace-Id`), never trusted alone — every request re-validates it via a `WorkspaceMembership` lookup against `current_user.id`.** Not a JWT claim, not a URL path segment, not client-trusted state. |
| 2 | Why is a JWT claim rejected? | Access tokens are already short-lived (30 min, unchanged, Phase D invariant) but are **stateless and unrevokable within that window** (Phase D's own documented trade-off, `phase-d-auth-security-design.md` §6: "access tokens already in flight remain valid until their own 30-minute expiry — this is an accepted, bounded window"). If workspace membership were baked into the JWT and then revoked (user removed from workspace), the stale claim would remain valid for up to 30 minutes — a real, avoidable authorization gap. A header validated against a live DB row has no such staleness window. |
| 3 | Why is a URL path segment (e.g. `/w/{workspace_id}/queues`) rejected as the primary mechanism? | It would touch every existing route's path structure — a breaking API contract change across `products`, `queues`, `channels`, `dashboard`, `campaigns`, `conversions`, and the SSE stream simultaneously. A header is additive: existing paths are unchanged, and the header can be introduced route-by-route as each is migrated to workspace-scoping (§8, §16 task breakdown), which is a much smaller, safer diff per task. This is the same "prefer additive over breaking" discipline this repository already applied to every prior phase (Phase A.1's migration was additive-only; Phase D's `refresh_token` field was additive to `TokenResponse`). |
| 4 | Why is silent server-side "pick the user's only workspace" rejected as sufficient on its own? | It works only for single-membership users and silently breaks/needs a fallback the moment a user has ≥2 memberships (Option B, §5.1) — the header approach works uniformly regardless of membership count and requires no special-casing. |
| 5 | Security implication | Every workspace-scoped route dependency must perform: `SELECT 1 FROM workspace_memberships WHERE workspace_id = :header_value AND user_id = :current_user.id`. Missing row → `403 Forbidden` (reuse the existing `ForbiddenError` → HTTP mapping already wired via `ServiceError`, `app/services/exceptions.py`; no new error-handling mechanism needed). This is architecturally identical to the already-shipped Decision 7 pattern in Phase D (`AffiliateRepository.get_by_user_id` ownership check before allowing the operation) — Phase E's workspace check is the same shape of check, one level up. |
| 6 | Which future task depends on it? | Any task that adds `workspace_id` filtering to a route (§16). |

### 5.4 Isolation — read/write/update/delete, per domain

Because no route is workspace-scoped today, **every** domain listed below currently has zero workspace isolation (there is no workspace to isolate). The table records what isolation *would* need to be added once `workspace_id` exists on the relevant tables (§7), not a defect in the current single-tenant system.

| Domain | Read isolation needed | Write isolation needed | Update isolation needed | Delete isolation needed | Notes |
| --- | --- | --- | --- | --- | --- |
| Users | No — users are not workspace-owned, they hold memberships | N/A | N/A | N/A | A user can belong to N workspaces; `User` itself stays global |
| Affiliates | Product decision (§4.2) | Product decision | Product decision | Product decision | Depends entirely on the Option A vs B `Affiliate` decision |
| Campaigns | Yes | Yes | Yes | Yes | Weakest existing enforcement today (§4.1) — highest-value target once workspace-scoped |
| Conversions | Yes (transitively via affiliate → workspace) | Yes | Yes | N/A (no delete route exists) | `external_order_id` global-uniqueness question, §7 |
| Products | Product decision (§4.2) | Product decision | Product decision | Product decision | Shared-catalog vs per-workspace-catalog is unresolved |
| Queues (`QueueItem`) | Yes | Yes | Yes | Yes | Highest-traffic authenticated surface with zero current scoping |
| Channels | Yes | Yes | Yes | Yes | Publishing into another workspace's Telegram channel is a concrete cross-tenant leak risk |
| Dashboard | Yes | N/A (read-only aggregate) | N/A | N/A | `DashboardService.get_dashboard` would need workspace-filtered counts (§9) |
| AI content/history | N/A today | N/A | N/A | N/A | No server-side persistence exists (`sessionStorage` only) — nothing to isolate yet |
| Discovery/import | Read: no (external catalog search, arguably workspace-independent); Import: yes if products become workspace-scoped | Import: yes (same decision) | N/A | N/A | Depends on the Product workspace decision |
| Settings | Yes, if/when a settings table exists (§10) | Yes | Yes | N/A | No settings persistence exists today — nothing to isolate yet |
| Analytics | Yes (derived from Conversion/Campaign/Queue workspace scoping) | N/A | N/A | N/A | Analytics inherits isolation from its source tables, not a new mechanism |
| Clicks (future) | Yes | Yes | N/A | N/A | New subsystem — isolation designed in from the start (§13) |
| Payouts (future) | Yes | Yes | Yes | N/A | New subsystem — isolation designed in from the start (§14) |
| Background tasks | See §19 | See §19 | — | — | `process_publish_queue` iterates all due `QueueItem` rows regardless of workspace — becomes cross-tenant processing once `QueueItem.workspace_id` exists, unless the task loop is workspace-aware or intentionally left workspace-agnostic (worker has no per-tenant concept of "who is asking") |
| Redis keys/channels | See §17 | — | — | — | Single `queue-events` channel and single `celery:health:heartbeat` key; both currently workspace-agnostic by design (heartbeat is process-global, not tenant data) |
| SSE | See §17 | — | — | — | `EventBroadcaster` fans out to all subscribers unconditionally today (§1 finding 8) |
| Cached/query data | Query keys (frontend only) | — | — | — | TanStack Query cache is client-side and per-browser-tab; no server-side cache to isolate |

**No A.2 architectural change is required to add the plumbing** (the envelope field already exists) — only a filter step at the broadcast/subscribe boundary, detailed in §17.

---

## 6. Authorization & Security Analysis

### 6.1 Current authentication architecture (unchanged by this analysis — restated from Phase D)

```text
POST /auth/login → AuthService.login → bcrypt verify → access JWT {sub, exp, type:"access"} (30 min)
                                                        + opaque refresh token (7 days, PostgreSQL, rotate-on-use)
Authenticated request → get_current_user → decode_access_token → UserRepository.get_by_id → reject if inactive
```

Source: `app/auth/service.py`, `app/auth/dependencies.py`, `app/auth/security.py` — all unchanged by this analysis.

### 6.2 What Phase E must not touch (hard carry-forward from Phase D, restated per §23 of this document)

- `decode_access_token`'s `"type": "access"` enforcement.
- `access_token_expire_minutes` (30) and `jwt_algorithm` (HS256).
- Refresh token rotation/reuse-detection/logout semantics (`app/models/refresh_token.py`, `app/auth/service.py`).
- The three existing rate-limited routes and their fail-open Redis semantics (`app/core/rate_limit.py`).
- `POST /conversions`'s existing ownership-or-admin check (`app/services/conversion.py::record_conversion`).

### 6.3 Where workspace context should come from

Resolved in §5.3: **server-validated request header, checked against a live `WorkspaceMembership` row on every request.** Not a JWT claim (staleness risk), not a URL path (breaking-change blast radius), not client-trusted state (IDOR risk if unvalidated).

### 6.4 New risks introduced by multi-workspace tenancy

| Risk | Current exposure | Future exposure | Mitigation | Which Phase E task should address it |
| --- | --- | --- | --- | --- |
| IDOR via unvalidated workspace header | N/A (no header exists) | Caller supplies an `X-Workspace-Id` for a workspace they don't belong to | Every workspace-scoped route dependency must perform the live membership lookup (§5.3) before touching any workspace-scoped table — no exceptions, no "trust the header" shortcut | The task that introduces the workspace-authorization dependency (§16, foundational task) |
| Cross-workspace read via un-migrated routes | N/A | A route forgets to add the workspace filter to its query (e.g., adds `workspace_id` to the model but not to the repository's `WHERE` clause) | Every repository method touching a workspace-scoped table must take `workspace_id` as a mandatory (not optional) parameter, so omitting it is a type error, not a silent bug — mirrors the existing repository-per-aggregate convention (`app/repositories/*.py`) rather than inventing a new query-builder abstraction | Each per-domain migration task (§16) |
| Cross-workspace write (e.g., attaching a `QueueItem` to another workspace's `TelegramChannel`) | N/A | A workspace could reference another workspace's channel/product if FK targets aren't also membership-checked | Validate that `channel_id`/`product_id` (if scoped) belong to the same `workspace_id` as the `QueueItem` being created/updated, at the service layer — same shape of check as the existing `AffiliateCampaignRepository.get_by_affiliate_and_campaign` enrollment check (`app/services/conversion.py:40-45`) | Queue/channel workspace-scoping task (§16) |
| Existing unenforced `Campaign` ownership (pre-existing, not introduced by Phase E) | `PATCH /campaigns/{id}` currently allows any authenticated user to edit any campaign (`app/api/v1/campaigns.py:60-70`, `app/services/campaign.py` — no ownership check found in the service call) | Same gap, now also crossing workspace boundaries | Fold the fix into the Campaign workspace-scoping task rather than a separate patch — one authorization check (own-workspace-or-admin) replaces both the missing-ownership gap and the missing-workspace gap simultaneously | Campaign workspace-scoping task (§16) — flagged as a **pre-existing gap Phase E should fix, not introduce** |
| Background task cross-tenant processing | N/A (single tenant) | `process_publish_queue`/discovery tasks have no per-request identity — they run as the system, across all data by design | **Recommendation:** background tasks remain intentionally workspace-agnostic (they process all workspaces' due items in one pass, exactly as they process all data today) — this is not a leak because no *user* request context is exposed; each processed row still only mutates data already scoped to its own `workspace_id`. Do not attempt to run "one Celery task queue per workspace" — no evidence justifies that complexity | Documented as an explicit non-goal in the relevant task (§16, §19) |
| SSE cross-workspace event leakage | Confirmed today: `EventBroadcaster` sends every event to every connected client (§1 finding 8) — currently "acceptable" only because there is no workspace concept to leak | Once `QueueItem.workspace_id` exists, an unfiltered broadcaster would leak workspace B's queue events to workspace A's connected client | Filter at the SSE subscribe/dispatch boundary using the same header-validated workspace context as REST routes (§17) | SSE workspace-filter task (§16) |
| Admin bypass scope creep | `UserRole.ADMIN` already bypasses ownership checks in `ConversionService` (existing, proven pattern) | A global `ADMIN` could read/write across all workspaces by design — this must be an explicit, documented capability, not an accident | Keep `ADMIN` bypass exactly as-is (global) and document it as intentional in the design of every workspace-scoped route, matching existing precedent — do not invent a workspace-scoped "admin" that is weaker than today's `ADMIN` | Documentation task, no code risk |

---

## 7. Database / Migration Analysis

### 7.1 Tables likely needing `workspace_id`

| Table | Add `workspace_id`? | Nullable initially? | Reasoning |
| --- | --- | --- | --- |
| `campaigns` | Yes | Yes (Stage 1), then NOT NULL after backfill (Stage 5) | Strongest existing ownership signal (§4.2) |
| `queue_items` | Yes | Yes → NOT NULL | Highest-traffic global table today |
| `telegram_channels` | Yes | Yes → NOT NULL | Publishing target must not cross tenants |
| `products` | **Product decision required** | — | Only add if the shared-catalog option is rejected (§4.2) |
| `affiliates` | **Product decision required** | — | Only if 1-affiliate-per-(user, workspace) is chosen over global-per-user (§5.1) |
| `conversions` | Derived (via `affiliate_id`/`campaign_id`) or direct — **Product decision required** | — | Direct column avoids a join on every isolation check; derived avoids duplicated truth. No repository evidence forces either |
| `users`, `refresh_tokens`, `queue_publish_attempts`, `aliexpress_categories` | **No** | — | Global-by-design (§4.2, §7.3) |

### 7.2 New tables

`workspaces`, `workspace_memberships` — schema drafted in §5.1. Additive-only; no existing table is altered by their creation.

### 7.3 Tables that should remain global

`users` (identity, not tenant data), `refresh_tokens` (authenticates a user, not a workspace session — Phase D invariant, §6.2), `queue_publish_attempts` (derived audit trail, follows its parent `queue_items` row automatically without its own column), `aliexpress_categories` (external reference cache — duplicating per workspace has no evidenced benefit, §4.2).

### 7.4 Unique constraints that become incorrect under tenancy

| Constraint | Current definition | Problem under tenancy | Recommended fix |
| --- | --- | --- | --- |
| `products.aliexpress_product_id` unique | `app/models/product.py:17-22` | Only relevant if `products` becomes workspace-scoped (§7.1 open decision) | If scoped: `UniqueConstraint(workspace_id, aliexpress_product_id)`. If products stay global: no change |
| `telegram_channels.telegram_channel_id` unique | `app/models/channel.py:14-19` | Two workspaces registering the same Telegram channel ID would collide | `UniqueConstraint(workspace_id, telegram_channel_id)` |
| `conversions.external_order_id` unique | `app/models/conversion.py:32` | Two different workspaces could legitimately have unrelated orders that happen to share an ID format/value from different source systems | **Product decision required**: `UniqueConstraint(workspace_id, external_order_id)` if per-workspace dedupe is correct, or leave global if order IDs are meant to be globally unique across all tenants (e.g., if they're always AliExpress order IDs, which *are* globally unique at the source) |
| `affiliates.user_id` unique | `app/models/affiliate.py:21-26` | Only relevant if a user should hold separate affiliate profiles per workspace (§4.2, §5.1) | If yes: `UniqueConstraint(user_id, workspace_id)`. If no: no change |
| `affiliates.referral_code` unique | `app/models/affiliate.py:29` | **Recommendation: no change.** A referral code is presumably meant to be globally shareable/resolvable (e.g., in a URL) regardless of which workspace issued it | No repository evidence argues for scoping this — flagged as `Inference`, not fact |

### 7.5 Indexes needing workspace-aware variants

Any new `workspace_id` column used as a primary filter predicate should get its own index (e.g., `ix_queue_items_workspace_id`), and composite indexes that currently exist purely for status/date filtering (`QueueItem.status`, `QueueItem.scheduled_at`) would benefit from a composite `(workspace_id, status)` / `(workspace_id, scheduled_at)` form once workspace filtering is the primary access pattern — this is a **Recommendation**, not required for correctness, since PostgreSQL can still use the existing single-column indexes with an added `WHERE workspace_id = ...` filter, just less efficiently at scale. No repository evidence (query volume, row counts) justifies a firm requirement either way.

### 7.6 Backfill and staged deployment

- **Existing rows can be assigned to a bootstrap/default workspace.** This requires the Admin Bootstrap CLI (§12) or an equivalent one-off script to exist first, since a `workspace_id` needs *some* concrete UUID to backfill into, and nothing today creates a `Workspace` row.
- **Can the migration be additive?** Yes, in two steps, matching this repository's own established convention (every migration to date — `001` through `009` — has been additive-only; see `docs/planning/phase-d-auth-security-design.md` §5's characterization of migration `009`):
  1. Add `workspace_id` as **nullable** to each target table (safe, zero-downtime, no application behavior change yet).
  2. Backfill all existing rows to one bootstrap workspace (data migration, not schema migration — run via the bootstrap CLI or a one-off script, not inside the Alembic migration itself, to keep the schema change and the data change independently reviewable and reversible).
  3. Only after backfill is confirmed complete, a **second**, later migration flips the column to `NOT NULL` and adds the composite unique constraints from §7.4. This two-migration split is a **Recommendation** based on this repository's own precedent of small, single-purpose migrations (`008` added a table; `009` added a table; neither combined a schema change with a data backfill).
- **SQLite test compatibility:** No new dialect-specific handling is anticipated for a plain nullable UUID FK + standard `UniqueConstraint`/`Index` — these are already portable across the `Base.metadata.create_all()` SQLite test path and PostgreSQL migrations, unlike the existing `_ContentHashFormatCheck` compiled-expression workaround (`app/models/queue.py:35-61`), which exists only because of a PostgreSQL regex `CheckConstraint` with no SQLite equivalent. A `workspace_id` column and its constraints do not need this pattern — flagged as `Inference`, to be verified in the actual migration task, not this document.
- **Migration numbering:** Next available is `010` (`alembic/versions/009_add_refresh_tokens.py` is HEAD).

---

## 8. API Impact Matrix

Classification legend: **Global** (workspace-independent), **WS** (workspace-scoped, future), **User** (user-owned, not workspace), **Admin** (admin-only), **Redesign** (needs more than an additive change), **Unclear** (needs a product decision).

| Endpoint | Current authz | Classification | Desired workspace requirement | Contract change? | Additive? | Frontend change required? |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /auth/login`, `/refresh`, `/logout`, `GET /auth/me` | None / access / refresh (Phase D) | Global | None — auth precedes workspace selection | No | — | No |
| `POST /auth/register` | Public | Global | None | No | — | No |
| `GET /dashboard` | Authenticated (any user) | **WS** (future) | Workspace-filtered aggregates | Yes — response shape may need a `workspace_id` echo or the header alone suffices | Yes (header-additive) | Yes — must send the new header |
| `GET/POST/PATCH/DELETE /products` | Authenticated / admin for mutations | **Unclear** — depends on §4.2/§7.1 product decision | TBD | TBD | TBD | TBD |
| `GET /products/discover*` | Public (unauthenticated reads) | **Global** (recommendation — discovery searches an external catalog, not tenant data) | None, unless import-with-persist ties into workspace-scoped products | No, unless persist path changes | — | No |
| `POST /products/search/image` | Public (unauthenticated) | **Global** | Same as discovery | No | — | No |
| `POST /products/import`, `/import/batch`, `/import-url` | Admin | **Unclear** — depends on Product workspace decision | TBD | TBD | TBD | TBD |
| `GET/POST/PUT/DELETE /channels` | Authenticated / (delete unused) | **WS** (future) | Channel must belong to caller's active workspace | Yes | Yes (header-additive) | Yes |
| `GET/POST/PATCH/DELETE /queues`, `GET /queues/{id}/attempts` | Authenticated | **WS** (future) | Queue item must belong to caller's active workspace | Yes | Yes (header-additive) | Yes |
| `GET /queues/stream` (SSE) | Authenticated | **WS** (future) | Broadcaster filters by workspace at dispatch time | No response-shape change (envelope already has `workspace_id`) | Yes | Yes — client must send the workspace header on stream connect |
| `POST /ai-content/generate` | Authenticated | **Global today** (no persistence) | None until server-side AI history exists (not in Phase E scope per roadmap wording) | No | — | No |
| `GET/POST/PATCH /affiliates/*` | Authenticated (self) / admin (list) | **Unclear** — depends on §4.2/§5.1 product decision | TBD | TBD | TBD | TBD |
| `GET/POST/PATCH /campaigns/*` | **Currently under-enforced** (§4.1, §6.4) — mix of public-read and any-authenticated-write | **WS** (future) — highest-value target | Own-workspace-or-admin for writes; workspace-filtered for reads | Yes | Yes (header-additive) | N/A — no frontend consumer exists today (§3) |
| `POST /conversions`, `GET /conversions/me`, `GET /conversions`, `PATCH /conversions/{id}` | Owner-or-admin (Phase D) / admin | **WS** (future, derived) | Workspace derived transitively via affiliate/campaign | Yes, if `workspace_id` becomes a direct column (§7.1) | Yes | N/A — no frontend consumer exists today |
| `GET /health`, `GET /ready`, `GET /worker/health` | None | **Global** | None — operational infra, explicitly out of scope (§19, §23) | No | — | No |
| `GET /aliexpress/categories`, `POST /aliexpress/import` | Authenticated / duplicate of products import | **Global** (reference cache) | None | No | — | No |
| Future `/analytics` | Does not exist | **WS** (future) | Workspace-filtered by construction | New endpoint | Yes (new, additive) | Yes — new feature |
| Future click-tracking redirect endpoint | Does not exist | **WS** (future, but publicly reachable by end-customers) | Workspace derived via campaign/affiliate | New endpoint | Yes (new, additive) | No — server-to-browser redirect, not an SPA route |
| Future payout endpoints | Does not exist | **WS** (future) / Admin for approval-adjacent actions | Workspace derived via affiliate | New endpoints | Yes (new, additive) | N/A initially — no existing affiliate-network UI to extend (§3, §14) |
| Future settings endpoints | Does not exist | **WS** (future, mostly) | Some settings global (secrets/infra, never exposed), most candidates workspace-scoped | New endpoints | Yes (new, additive) | Yes — Settings pages currently render static text only |

---

## 9. Frontend Workspace Architecture

**Explicitly not building any UI here — this section is architecture only, per the task's constraints.**

- **Where active workspace state should live:** `sessionStorage`, mirroring the exact precedent already established for access/refresh tokens (`frontend/src/services/session.ts`). **Recommendation**, not existing behavior — no such storage exists today.
- **How workspace switching should work (architecture, not UI):** a client-side "set active workspace id" action writes to `sessionStorage` and triggers a full reset of workspace-scoped query state (below) — no page reload required, matching the existing SPA navigation model.
- **Where workspace should be represented:** `sessionStorage` (source of truth) + an Axios request interceptor that attaches it as `X-Workspace-Id` on every request, mirroring the existing Bearer-token attachment in `frontend/src/services/api-client.ts:113-117` exactly — same interceptor pattern, one more header. **Not** the URL — keeps existing route paths unchanged (`/queue`, `/products`, etc.), consistent with §5.3's "additive header, not a breaking path change" decision.
- **How query keys must become workspace-aware:** every workspace-scoped feature's TanStack Query key array must include the active workspace id as a segment, e.g. `["queue", workspaceId, filters]` instead of today's `["queue", filters]` (pattern reference: `docs/06-api-integration.md` §8's existing example `["products", { status, skip, limit }]`). This is additive to the existing "query keys must include all server filter params" rule already documented in `docs/06-api-integration.md` §3.
- **How workspace switching should invalidate/refetch data:** **Recommendation:** on switch, remove (not merely invalidate) all workspace-scoped query cache entries — e.g. `queryClient.removeQueries({ predicate: (query) => isWorkspaceScopedKey(query.queryKey) })` — rather than `invalidateQueries`, because `invalidateQueries` still briefly serves stale (wrong-workspace) cached data during refetch, which is a real cross-tenant data-flash risk in the UI, however brief. This is stricter than today's existing invalidate-never-patch SSE convention (`useQueueRealtimeInvalidation`) precisely because that convention invalidates *within* one workspace's data, not across a workspace boundary.
- **How unauthorized workspace access should behave:** a `403` from the workspace-membership check (§5.3, §6.4) should be treated the same way the frontend already treats `403` today — *no* refresh attempt, *no* auto-logout (existing rule, `frontend/src/services/api-client.ts` — 403 is passed through as a normal rejected promise) — plus a **Recommendation** to fall back to the user's default/only-remaining workspace or an explicit "no workspace access" state, not a hard app crash.
- **How AppShell/navigation should eventually expose workspace context:** **Recommendation, not designed here per the explicit "do not introduce a workspace selector" instruction** — the natural location is the `AppShell` header, next to the existing theme toggle and user menu (`frontend/src/components/layout/AppShell.tsx:116-141`), since that is the only persistent global-chrome region in the current layout. Not built in this task or Task 1.
- **How SSE should react to workspace changes:** the existing `useQueueEventStream`/`useQueueRealtimeInvalidation` hooks (Phase A.2) would need the active workspace id added to their effect dependency array so a switch tears down the current SSE connection and opens a new one carrying the new `X-Workspace-Id` header — this is a **usage-site change to existing hooks**, not a redesign of the SSE transport itself (per the explicit instruction not to reopen A.2).
- **Whether SSR/middleware needs workspace awareness:** **Recommendation: no.** The existing Next.js middleware only checks for cookie *presence* to decide on redirect-to-login (`SESSION_COOKIE`, presence-only, `frontend/src/services/session.ts:40` and `docs/02-frontend-architecture.md` §6) — it does not and should not need to resolve workspace membership at the edge. Workspace resolution can remain a client-side, post-authentication concern, avoiding new complexity in the one layer this repository has deliberately kept minimal.

---

## 10. Analytics Analysis

**Implementation note (2026-09-04):** Tasks 12–13 shipped. Metrics are workspace-scoped click/conversion KPIs and a per-campaign funnel (`GET /analytics/overview`, `GET /analytics/campaigns/{id}/funnel`). Tenancy is the Campaign FK chain — no `workspace_id` on clicks or conversions. QueuePublishAttempt/dashboard aggregates were **not** included. The remainder of this section is the pre-implementation snapshot.

**Does `/analytics` exist today? NO — absent.** (Snapshot at Task 0.) No route, no frontend page, no service. Confirmed: `Glob frontend/src/app/**/*.tsx` lists no `analytics` path; `Grep` for `analytics` across `app/` and `frontend/src/` returns no functional matches beyond incidental substring hits in unrelated files.

### EXISTING DATA (usable today, without new persistence)

- `GET /dashboard` — product/queue/channel counts, recent activity, DB status (`app/schemas/dashboard.py`).
- `QueuePublishAttempt` rows — full attempt history with timestamps, `error_code`, provider — already enough to compute publish success/failure rate over time (`app/models/queue.py:113-215`).
- `Conversion` rows — `amount`, `commission`, `status`, `created_at`/`updated_at` (`TimestampMixin`) — already enough to compute revenue/commission-over-time and status-funnel metrics, **if** any UI ever consumes the currently-unconsumed `/conversions` endpoints.
- `Campaign`/`Affiliate` — static dimension data (names, rates) for grouping the above.

### REQUIRED NEW DATA (not persisted anywhere today)

- Click events — do not exist (§13).
- Payout records — do not exist beyond `Conversion.status = PAID` (§14).
- AI content generation history/usage — sessionStorage only, never persisted server-side (`features/ai/lib/session.ts`; roadmap already flags "AI usage metrics ⬜ Not in API").
- Any pre-aggregated rollup/materialized table for performance at scale — **Product decision required**, no evidence of expected query volume exists to justify one over on-the-fly aggregation queries against existing timestamped tables.

### PRODUCT DECISIONS NEEDED

- Which metrics are actually wanted (revenue, CTR, per-affiliate leaderboard, per-campaign performance, publish success rate, queue throughput)? The roadmap only names the route (`/analytics`), not any metric. **Do not invent metrics as approved requirements** — none of the above are confirmed scope, only *possible* given existing data.
- Should Analytics depend on Multi-workspace? **Recommendation: yes, at least on the foundational Campaign/Conversion workspace columns**, because analytics scoped to "everything, globally" would need to be reworked into "per-tenant" the moment tenancy lands — building it twice is avoidable by sequencing Analytics after the Campaign/Conversion workspace-scoping tasks (§16).
- Can Analytics be implemented before Click Tracking? **Yes, partially** — a first slice using existing `Conversion`/`QueuePublishAttempt`/`Dashboard` data needs no click data at all. Funnel metrics (click→conversion rate) structurally require Click Tracking first. **Recommendation:** ship Analytics in at least two slices — (1) existing-data analytics after workspace-scoping, (2) funnel analytics after Click Tracking.

---

## 11. Editable Settings Analysis

**Current state, verified directly:** every Settings sub-page (`general`, `aliexpress`, `ai`, `telegram`, `discovery`, `scheduling` — `frontend/src/app/(dashboard)/settings/*/page.tsx`) renders `CapabilityView`, a **static, read-only, hardcoded** list of Arabic label/value pairs (confirmed by reading `settings/general/page.tsx` in full — the values are literal strings in the component, not fetched from any API). The only real backend call anywhere in the Settings feature is `GET /ready` (database + Redis check, `docs/06-api-integration.md` §5). **No settings model, no settings table, no settings API exists anywhere in `app/`.**

- **What settings currently exist?** None that are stored/editable — only environment-level `Settings` (Pydantic `BaseSettings`, `app/core/config.py`), which is config-at-deploy-time, not application data.
- **Which settings are read-only?** All of them, by construction — there is nothing to write to.
- **Which settings are global vs should become workspace-scoped?** All current `Settings` fields are process-global (one value per deployed API process). Candidates visible in the existing Settings UI page groupings (AliExpress, AI provider defaults, Telegram, Discovery refresh cadence, Scheduling/publish batch size) are exactly the kind of per-tenant customization that would make sense workspace-scoped **if** an editable-settings feature is built — but several underlying `Settings` fields are secrets or infra config (`jwt_secret_key`, `database_url`, `openai_api_key`, `aliexpress_app_secret`, `telegram_bot_token`) that **must never** become user-editable regardless of Phase E, for the same reasons Phase D hardened JWT secret handling.
- **Does a settings model or API exist?** No, confirmed absent (`Grep class.*Settings` matches only the one existing `app.core.config.Settings` env-config class).
- **Which settings are safe to expose to users vs need admin?** Not established by current repository evidence — no candidate list has ever been product-approved; only inferred from the existing capability-page groupings.
- **Should settings be workspace-scoped?** **Recommendation: yes, for any settings that are actually built**, and **sequenced after Multi-workspace's foundational tables exist** — building a global (non-workspace) settings table first would need to be redone the moment tenancy lands, the same "avoid double work" reasoning as Analytics (§10).

**Do not create a settings API in this task** — none was created.

---

## 12. Admin Bootstrap CLI Analysis

**Current state, verified directly:**

- `POST /auth/register` hardcodes `role=UserRole.AFFILIATE` (`app/auth/service.py:39-49`) — there is **no** code path, public or private, that creates a `UserRole.ADMIN` user.
- No CLI exists: `Glob scripts/**` → 0 files. No `manage.py`, `cli.py`, Typer/Click entry point anywhere in `app/`.
- No seed mechanism in `docker-compose.yml` — the `api` service runs `alembic upgrade head && uvicorn ...` only (docker-compose.yml:40-42); no seed step follows the migration.
- No entrypoint script exists (`Glob **/entrypoint*` → 0 files).

**Conclusion: a fresh deployment of the current, single-tenant system already cannot create its first admin user without direct database access** (e.g., manually inserting a row with a pre-hashed password). This is a pre-existing operational gap, not introduced by Phase E, but Phase E's roadmap item correctly identifies it.

- **Is a CLI actually necessary?** Yes — there is no alternative mechanism today.
- **Idempotency requirements:** must be safe to re-run without creating duplicates. The existing `users.email` unique constraint (`app/auth/models.py:18`) already provides a natural idempotency check ("does this email already exist? skip/no-op if so") — no new mechanism needs inventing.
- **Security constraints:** must not be exposed as a public HTTP route (unlike `POST /auth/register`, which is deliberately public but role-locked) — should run as a trusted local/CI/deploy-time process, consistent with `docs/10-production-readiness.md` §4's existing staging checklist item 3: *"Provision staging admin (DB/trusted process — not public register)"* — this line already anticipated exactly this gap before Phase E existed.
- **Should it run before or after workspace initialization?** **Recommendation: after the `workspaces`/`workspace_memberships` tables exist**, so the bootstrap can create a coherent admin user + default workspace + membership row in one atomic operation, rather than creating an admin now and needing a second script later once tenancy lands. This mirrors §7.6's backfill dependency (backfilling existing rows into a "bootstrap workspace" also needs a workspace row to exist, likely the *same* one this CLI creates).
- **What should it create?** **Recommendation: admin + default workspace + membership**, all three, atomically — creating only an admin user would leave Phase E's tenancy model with no workspace to backfill into (§7.6), and creating only a workspace with no admin leaves no one able to manage it.

**Do not create the CLI in this task** — none was created.

---

## 13. Click Tracking Analysis

**Current state, verified directly:**

- `Conversion.click_id` is a bare nullable `String(64)`, indexed but **not a foreign key** to anything (`app/models/conversion.py:41`). It is supplied verbatim by the API caller (`ConversionCreate.click_id`, `app/schemas/conversion.py:16`) — this backend neither generates nor validates its format or provenance.
- `AffiliateCampaign.tracking_link` is a plain `String(512)` (`app/models/affiliate.py:72`) — stored, but **no route or service anywhere resolves, redirects, or logs a hit against it.** Confirmed by exhaustive review of `app/api/v1/*.py` (13 files, `router.py` enumerates all of them) — none contain a redirect/click-tracking route.
- **No `Click`/`ClickEvent` model exists.** `Glob app/models/*.py` lists 12 files; none is click-related.

**Conclusion: click tracking is entirely absent today, not partial.** `click_id` is a placeholder correlation field with no producer anywhere in this repository.

- **Whether clicks are derived from conversions or need independent persistence:** Independent persistence is required — a click and a conversion are fundamentally different events (a click may never convert), and `Conversion.click_id` is only meaningful as a foreign key once a `Click` entity exists to reference.
- **What entity owns a click:** Naturally the same `AffiliateCampaign` (affiliate + campaign pair) that owns the `tracking_link` today — a click is "someone followed affiliate X's link for campaign Y."
- **Are clicks workspace-scoped:** Yes, transitively via `AffiliateCampaign` → `Campaign`/`Affiliate` → workspace (once those are scoped, §7.1).
- **What attribution information is currently available:** Only `click_id` (opaque string) and `tracking_link` (a stored URL with no serving logic). No IP, user-agent, or timestamp is captured for a click anywhere today.

**Potential architecture (not implemented — architecture only):** a `clicks` table (id, `affiliate_campaign_id` FK, `click_token` used as the `Conversion.click_id` value, `occurred_at`, optionally IP/user-agent) plus a new **public** redirect endpoint (e.g. `GET /r/{click_token}` → record a `Click` row → HTTP 302 to `campaign.landing_url`) that mints the `click_token`/`click_id` a merchant's own postback later references when calling `POST /conversions`. This directly matches the server-to-server postback shape Phase D's own design document already inferred for `POST /conversions` (`phase-d-auth-security-design.md` §11: *"strongly resembles a server-to-server conversion-postback pattern"*) — Click Tracking is the missing first half of that same flow.

**Product decisions required:** exact `click_id`/`click_token` format; whether the redirect endpoint needs bot-filtering/rate-limiting (new public attack surface, comparable to the login-route rate-limit precedent, Phase D Decision 4/5); whether click metadata (IP/UA) is captured at all (privacy/PII consideration with no repository precedent to follow — this codebase has no existing PII-handling pattern to extend).

**Attribution chain reality check — important finding:** `product → affiliate link → click → conversion → payout` assumes `Product` connects to `AffiliateCampaign`/`Campaign`. **It does not.** No FK or join table connects `Product` (the Discovery/Queue/Telegram subsystem) to `Campaign`/`Affiliate` (the dormant affiliate-network subsystem) anywhere in the schema. Building Click Tracking as literally described in the roadmap's implied chain would require **also** deciding how a `Product` relates to a `Campaign` — a modeling question with zero existing evidence either way. **This is flagged as the single largest open product-architecture question in the entire Phase E scope** (see §24).

**Do not invent a final attribution model** — none is finalized here, per instruction.

---

## 14. Payout Module Analysis

**Current state, verified directly:**

- `Affiliate.payout_details` is unstructured `Text`, nullable (`app/models/affiliate.py:40`) — presumably free-form bank/payment details, never parsed or validated.
- `Conversion.status` (`ConversionStatus` enum — confirmed values not re-derived here beyond what's already used: `PENDING` is the only value referenced directly in code, `app/services/conversion.py:59`; `PATCH /conversions/{id}` already allows an admin to set `status` to any `ConversionStatus` value via `ConversionUpdate`, `app/api/v1/conversions.py:66-77`) — so **a per-conversion "mark as paid" capability already exists at the API layer today**, gated admin-only, exactly matching the existing `update_status` authorization pattern (`app/services/conversion.py:63-70`).
- **No independent `Payout` entity, batch, ledger, date, or method exists.** No table beyond the per-conversion status flag.
- **No frontend consumes any of this** — `/affiliates/*`, `/campaigns/*`, `/conversions/*` remain "Backend only — No MVP screens" (`docs/06-api-integration.md` §4.8, confirmed against the frontend feature-folder inventory in §3).

- **What payout functionality exists today?** The minimal, per-conversion status transition only — no batching, no ledger, no payout record.
- **Is payout API-only?** Yes, and even that is only a byproduct of the generic `ConversionUpdate` status field, not a purpose-built payout endpoint.
- **Do payout records exist?** No.
- **Is commission persisted or derived?** Persisted — `Conversion.commission` is computed once at creation time (`amount * affiliate.commission_rate / 100`, `app/services/conversion.py:47-49`) and stored, not recomputed on read.
- **Is conversion status sufficient for payout eligibility?** **Product decision required** — depends entirely on whether payouts are meant to be per-conversion (current status model already supports this, trivially) or batched across many conversions per affiliate per period (the more typical real-world affiliate-payout shape, but with zero repository evidence either way).
- **Does payout require new persistence?** Only if batching/ledger semantics are wanted; a purely per-conversion "PAID" status requires none.
- **Workspace implications:** transitively scoped via `Affiliate` → workspace (§7.1).
- **Admin vs affiliate access:** the existing proven pattern (`update_status` admin-only write, `list_for_affiliate` affiliate-own-read, `list_all` admin-only) extends directly — no new authorization model needs inventing.
- **Dependencies:** structurally requires only `Conversion` (already exists) and, if scoping is desired, Multi-workspace. **Does not** structurally require Click Tracking (conversions can and do exist today with no click data at all — `click_id` is optional). **Recommendation (product reasoning, not architectural necessity):** sequence Payouts after Click Tracking anyway, since a trustworthy payout program without click-level attribution is unusual in this domain, but this is explicitly a recommendation, not a hard dependency (§15 dependency graph marks this a **soft** dependency).

**Do not implement payouts or create a payout model** — none was created.

---

## 15. Background Worker / Celery Impact

Phase B and A.1 are unchanged and not reopened.

- `process_publish_queue` (`app/worker/tasks/publishing.py:97-103`, Beat-scheduled every 60s by default) iterates due/queued `QueueItem` rows with no per-request identity. Once `QueueItem.workspace_id` exists, this task continues to process **all workspaces' due items in one pass** — **Recommendation: this is correct and should not change.** There is no evidence-based reason to run one Celery task per workspace (needless complexity, no stated multi-tenant fairness/quota requirement exists in the roadmap or docs).
- `refresh_hot_products`, `refresh_trending_products`, `refresh_categories` (`app/worker/tasks/discovery.py`) operate on the global `Product`/`AliExpressCategory` catalog — if products stay global (§4.2 undecided), these tasks need **zero** workspace changes at all. If products become workspace-scoped, these tasks would need reconsideration of what "refresh" means per-workspace (e.g., does workspace A's refresh duplicate workspace B's catalog fetch?) — **flagged as a strong argument for keeping Product global**, since making it workspace-scoped multiplies external AliExpress API cost per workspace with no evidenced benefit.
- `worker_heartbeat` (`app/worker/tasks/health.py`) is process-level infrastructure liveness, not tenant data — **no change, ever** (§19 instruction: analyze only what's needed).
- **Can queued items be processed safely without user-request context?** Yes, exactly as today — the task loop is not a "request" in the auth sense; it directly reads/writes rows via `workspace_id` columns once those exist, the same way it directly reads/writes `status`/`scheduled_at` today with no `CurrentUser` involved at all. This requires no new authorization mechanism inside Celery — workspace scoping is a data-shape property, not a request-authorization property, for background tasks.
- **Flower** — task-level observability, unaffected; it observes task execution, not tenant data.

**No Celery/worker infrastructure redesign is required.** The only change, if/when `QueueItem` becomes workspace-scoped, is that `process_publish_queue`'s existing per-item error isolation (`_publish_items`, already catches `TelegramPublishError` and continues the batch, `docs/10-production-readiness.md` §9.3) continues to apply — a failure in one workspace's item already cannot block another's, which is a **beneficial existing property**, not something Phase E needs to add.

---

## 16. SSE / Real-Time Impact

**A.2 is COMPLETE and is not reopened.**

- **Workspace-scoped Redis channels:** **Not required.** The existing single `queue-events` Pub/Sub channel (`app/events/publisher.py:13`) can remain a single channel; filtering by workspace is cheaper and simpler at the in-process `EventBroadcaster` dispatch step (already per-API-process, already per-subscriber) than at the Redis transport layer. Splitting into per-workspace Redis channels would add operational complexity (dynamic channel subscription management) with no evidenced benefit over an in-process filter.
- **Workspace filtering — where:** at `EventBroadcaster.publish()`'s existing per-subscriber delivery loop (`app/events/broadcaster.py:37-52`). Each SSE connection's registered callback would close over the connecting client's validated workspace id (from §5.3's header+membership check, performed once at `GET /queues/stream` connect time) and simply skip delivery when `envelope.workspace_id` doesn't match — a small, additive change to the callback registered in `queue_stream.py`, not a change to `EventBroadcaster`'s own fan-out mechanism.
- **Event envelope changes:** **None required.** `workspace_id` already exists on `QueueEventEnvelope` (`app/events/schemas.py:38`) and is already threaded through `_build_queue_event` (`app/services/queue.py:65-78`) — the only change needed is populating it with a real value instead of the current hardcoded `None`, once `QueueItem.workspace_id` exists to read it from.
- **Frontend workspace-aware invalidation:** covered in §9 — add active-workspace-id to the SSE hook's effect dependencies so switching workspace reconnects the stream with the new header.
- **SSE reconnection on workspace change:** Required, and is a usage-site change to `useQueueEventStream`, not a transport redesign — matches the existing reconnect-on-visibility/reconnect-on-network-change patterns already built into the Phase A.2 fetch-based SSE client.

**Explicit statement per task instruction:** No A.2 architectural change is required beyond (a) populating an already-existing envelope field with a real value and (b) adding one filter predicate to an already-existing per-subscriber delivery loop. The transport, reconnection protocol, polling fallback, and event catalog are unchanged.

---

## 17. Phase E Dependency Graph

The roadmap's implicit graph (repeated in the task prompt) is validated below against repository evidence — **not assumed correct**.

```text
Multi-workspace (foundational: Workspace + WorkspaceMembership + auth dependency)
    │
    ├─(hard)→ Campaign workspace-scoping  ──(hard)→  Analytics (slice 1: existing-data metrics)
    │                                                       │
    ├─(hard)→ Conversion workspace-scoping ─────────────────┤
    │                                                       │
    ├─(hard)→ Queue/Channel workspace-scoping ──(hard)→ SSE workspace filter
    │
    ├─(soft)→ Editable Settings (workspace-scoped variant)
    │
    └─(hard, for backfill target)→ Admin Bootstrap CLI (workspace-aware variant)

Click Tracking (needs: AffiliateCampaign + a Product↔Campaign modeling decision, §13)
    │
    ├─(hard)→ Analytics (slice 2: funnel metrics)
    │
    └─(soft, product reasoning only)→ Payout Module

Payout Module (hard dependency: Conversion only; soft dependency: Click Tracking, §14)

Image Search UI — independent of everything above (hard dependencies: none found)

Admin Bootstrap CLI (minimal, non-workspace-aware form) — independent of everything above;
Admin Bootstrap CLI (workspace-aware, recommended form) — soft-depends on Multi-workspace's schema existing
```

### Validated conclusions

- **Hard dependencies:** Analytics-on-Campaign/Conversion-data → Multi-workspace's Campaign/Conversion scoping tasks. SSE workspace filtering → Queue/Channel workspace-scoping. Click-Tracking funnel analytics → Click Tracking existing first.
- **Soft dependencies (recommended sequencing, not structural necessity):** Payout Module → Click Tracking (product-trust reasoning only, §14). Editable Settings (workspace-scoped) → Multi-workspace (avoid double-build reasoning only, §11). Admin Bootstrap CLI's *fuller, recommended* form → Multi-workspace's schema (§12) — but a **minimal, non-workspace-aware** bootstrap CLI has **no** dependency on anything and could ship immediately, independent of every other Phase E item, since the gap it fixes (§12) predates and is unrelated to tenancy.
- **Independent work:** **Image Search UI** has zero dependency on any other Phase E item — the backend endpoint already fully exists and works today (§21), and building its UI touches only the Discovery feature, not tenancy, settings, analytics, clicks, or payouts.
- **Blockers:** Multi-workspace's core schema (`workspaces`, `workspace_memberships`, the header-validated authorization dependency) blocks every workspace-scoped route change. The `Product`↔`Campaign` modeling gap (§13) blocks a literal reading of the roadmap's implied click-attribution chain, though it does **not** block a narrower Click Tracking implementation scoped to `AffiliateCampaign` alone (i.e., Click Tracking can proceed without resolving Product↔Campaign, as long as its scope is explicitly "affiliate link clicks," not "which product was clicked").
- **Sequencing risk:** Building Analytics, Editable Settings, Click Tracking, or Payouts **before** Multi-workspace's foundational tables would very likely require rework once tenancy lands (adding `workspace_id` to a table that already has consumers is a strictly bigger diff than adding it before consumers exist). This is the single biggest sequencing risk in Phase E, and directly informs §20's recommended order.

---

## 18. Proposed Task Breakdown

Deliberately split into small, independently verifiable tasks. **No task below is implemented in this document.**

### Task 1 — Multi-Workspace Foundational Schema (recommended first task, see §20)

- **Goal:** Introduce `Workspace` and `WorkspaceMembership` as new, additive tables with zero behavior change to any existing route.
- **Scope:** New models (`app/models/workspace.py`), new migration `010_add_workspaces.py` (additive-only, per §5.1/§7.2 schema).
- **Dependencies:** None.
- **Expected files/modules:** `app/models/workspace.py`, `alembic/versions/010_add_workspaces.py`, `app/repositories/workspace.py` (new, following the existing one-repository-per-aggregate convention).
- **Backend changes:** New models + migration + repository only. No existing route touched.
- **Frontend changes:** None.
- **Database changes:** Two new tables. No existing table altered.
- **API changes:** None — no route exposes these tables yet.
- **Tests:** New `tests/test_workspace_model.py` (constraint/relationship coverage, matching the existing model-test convention, e.g. `tests/test_queue_publish_attempt_repository.py`'s shape).
- **Documentation:** None required beyond this design doc; roadmap update deferred to a later closeout task.
- **Explicit non-goals:** No route authorization change. No `workspace_id` added to any existing table yet (that is Task 3+). No frontend change.
- **Acceptance criteria:** New tables created via migration; full existing 39-file backend suite passes unmodified (proves zero behavior change to any existing route).

### Task 2 — Workspace-Aware Admin Bootstrap CLI

- **Goal:** Provide the only mechanism this repository has to create a first admin user, workspace, and membership.
- **Scope:** A standalone script (e.g. `scripts/bootstrap_admin.py`) run via `python -m` or a documented `docker compose exec` invocation — not an HTTP route.
- **Dependencies:** Task 1 (needs `Workspace`/`WorkspaceMembership` tables to create a coherent bootstrap workspace).
- **Expected files/modules:** `scripts/bootstrap_admin.py` (new directory), reusing existing `AuthService`/password-hashing (`app/auth/security.py::hash_password`) and repositories — no new hashing/creation logic invented.
- **Backend changes:** New script only; no existing route/service modified.
- **Frontend changes:** None.
- **Database changes:** None (script writes rows via existing models, no schema change).
- **API changes:** None.
- **Tests:** New `tests/test_bootstrap_admin.py` — idempotent re-run produces no duplicate; creates exactly one admin + one workspace + one membership on first run.
- **Documentation:** `docs/10-production-readiness.md` §4 staging checklist item 3 updated to reference the concrete script instead of the current vague "DB/trusted process" wording.
- **Explicit non-goals:** No public HTTP endpoint. No password-reset flow. No multi-admin batch seeding.
- **Acceptance criteria:** Fresh database + one script invocation yields a working admin login with an active workspace membership; re-invocation is a no-op.

### Task 3 — Workspace Authorization Dependency (backend primitive)

- **Goal:** A single, reusable FastAPI dependency that resolves and validates the active workspace from a request header against `WorkspaceMembership`.
- **Scope:** `app/auth/dependencies.py` (or a new `app/core/workspace.py`) gains `get_active_workspace` returning a validated `WorkspaceMembership`, raising `ForbiddenError` on a missing/invalid header or missing membership row.
- **Dependencies:** Task 1.
- **Expected files/modules:** `app/core/workspace.py` (new), reusing `ServiceError`/`ForbiddenError` (`app/services/exceptions.py`) — no new error-handling mechanism.
- **Backend changes:** New dependency only; not yet applied to any existing route (that begins in Task 4+).
- **Frontend changes:** None yet.
- **Database changes:** None.
- **API changes:** None yet (dependency exists but is unused).
- **Tests:** New `tests/test_workspace_authorization.py` — valid membership passes; missing header rejected; header naming another workspace the user doesn't belong to rejected (403); reused across simulated routes.
- **Documentation:** None yet.
- **Explicit non-goals:** Not applied to any real route in this task — proves the primitive in isolation first, exactly as Phase D's Task 1 (JWT validation) shipped independently before Task 4 (conversion authorization) consumed it.
- **Acceptance criteria:** All new tests pass; zero existing route behavior changes (the dependency is not yet wired into `router.py`).

### Task 4 — Campaign Workspace-Scoping (first consumer; also fixes the pre-existing ownership gap, §6.4)

- **Goal:** Add `workspace_id` to `Campaign`, enforce it on all campaign routes, and simultaneously close the pre-existing missing-ownership gap on `PATCH /campaigns/{id}`.
- **Scope:** Migration adding nullable `campaigns.workspace_id`; `app/api/v1/campaigns.py` gains the Task 3 dependency; `app/services/campaign.py` filters/validates by workspace.
- **Dependencies:** Task 1, Task 3.
- **Expected files/modules:** New migration, `app/models/campaign.py`, `app/api/v1/campaigns.py`, `app/services/campaign.py`, `app/repositories/campaign.py`.
- **Backend changes:** As above.
- **Frontend changes:** None — no frontend consumer of `/campaigns/*` exists (§3).
- **Database changes:** Additive nullable column (Stage 1 of §7.6); NOT NULL flip deferred to a later closeout task once backfilled.
- **API changes:** Additive header requirement; existing response shape unchanged.
- **Tests:** New `tests/test_campaign_workspace_isolation.py` — cross-workspace read/write/update rejected; own-workspace succeeds; admin bypass still works.
- **Documentation:** `docs/06-api-integration.md` §4.8 updated to reflect the new header requirement.
- **Explicit non-goals:** Does not touch `Product`, `QueueItem`, `TelegramChannel`. Does not backfill/enforce NOT NULL yet.
- **Acceptance criteria:** New isolation tests pass; existing campaign tests (if any) pass unmodified; the pre-existing missing-ownership gap on `PATCH /campaigns/{id}` is closed as a documented side effect.

### Task 5 — Conversion Workspace-Scoping

- **Goal:** Extend workspace enforcement to `Conversion`, resolving the §7.4 unique-constraint product decision for `external_order_id`.
- **Scope:** Depends on the resolved product decision; otherwise mirrors Task 4's shape for `Conversion`.
- **Dependencies:** Task 4 (Campaign must be scoped first, since Conversion references it), Task 1, Task 3.
- **Expected files/modules:** Migration, `app/models/conversion.py`, `app/api/v1/conversions.py`, `app/services/conversion.py`.
- **Backend/DB/API changes:** Same shape as Task 4.
- **Tests:** New `tests/test_conversion_workspace_isolation.py`, extending (not replacing) `tests/test_conversions_authorization.py` (Phase D).
- **Documentation:** `docs/06-api-integration.md` §4.8.
- **Explicit non-goals:** Does not change the existing owner-or-admin check (Phase D, unchanged) — adds a workspace check *in addition to*, not instead of, ownership.
- **Acceptance criteria:** New isolation tests pass; all Phase D conversion tests still pass unmodified.

### Task 6 — Queue & Channel Workspace-Scoping (highest-traffic surface)

- **Goal:** Add `workspace_id` to `QueueItem` and `TelegramChannel`, enforce cross-reference validation (a queue item's channel must share its workspace, §6.4), and populate the previously-null SSE envelope field.
- **Scope:** Two models, their migrations, `app/api/v1/queues.py`, `app/api/v1/channels.py`, `app/services/queue.py` (only the `workspace_id=None` line and its callers), `app/repositories/queue.py`, `app/repositories/channel.py`.
- **Dependencies:** Task 1, Task 3.
- **Expected files/modules:** As listed.
- **Backend changes:** As above, plus §17's `EventBroadcaster` filter predicate.
- **Frontend changes:** `useQueue`, `queue.api.ts`, `channels.api.ts` gain the workspace header (via the shared Axios interceptor, §9) — no new UI.
- **Database changes:** Two additive nullable columns + the composite unique constraint fix for `telegram_channels.telegram_channel_id` (§7.4), deferred to NOT NULL in a later closeout task.
- **API changes:** Additive header requirement on `queues`/`channels`/`queues/stream`.
- **Tests:** New `tests/test_queue_workspace_isolation.py`, `tests/test_channel_workspace_isolation.py`; extends existing SSE tests (`tests/test_sse_endpoint.py`, `tests/test_event_broadcaster.py`) to cover the new filter predicate without modifying their existing assertions.
- **Documentation:** `docs/06-api-integration.md` §4.6/§4.7, `docs/10-production-readiness.md` §6 tenancy row updated from "not user-scoped" to reflect the new state.
- **Explicit non-goals:** Does not touch `Product`. Does not change `QueueStatus`, retry/idempotency logic (A.1), or the SSE transport/reconnection protocol (A.2) — only the dispatch filter and envelope population.
- **Acceptance criteria:** New isolation tests pass; full existing A.1/A.2 regression suite (queue publishing, idempotency, SSE, event schemas/broadcaster/publisher/consumer test files) passes unmodified.

### Task 7 — Product Decision Closeout: `Product`/`Affiliate` Scoping (conditional)

- **Goal:** Resolve and implement whichever direction the §4.2/§7.1 product decisions land on for `Product` and `Affiliate`.
- **Locked decisions (2026-08-19):** **Product remains a global shared catalog** (no `workspace_id`; `aliexpress_product_id` stays globally unique). **Affiliate remains a global user-owned 1:1 profile** (no `workspace_id`; unique `user_id` and `referral_code`). `POST /affiliates/join-campaign` is workspace-scoped via `X-Workspace-Id` and `CampaignRepository.get_by_id_in_workspace`.
- **Scope/files/tests:** `app/api/v1/affiliates.py`, `app/services/affiliate.py`, `tests/test_affiliate_workspace_isolation.py`; docs `06` / `10`. No migration.
- **Dependencies:** Task 1, Task 3, Task 4 (`get_by_id_in_workspace`), and the locked decisions above.
- **Explicit non-goals:** No Product/Affiliate `workspace_id`. No Queue product-workspace check. No Conversion redesign. No Task 8 constraint closeout. No Task 9 frontend plumbing.
- **Acceptance criteria:** Join-campaign isolation tests pass; Product catalog remains usable without `X-Workspace-Id`; existing Product/Affiliate/Campaign/Conversion/Queue tests remain green.

### Task 8 — Multi-Workspace NOT NULL / Constraint Closeout

- **Goal:** Flip tenant `workspace_id` columns to NOT NULL after Stage-1 nullable columns.
- **Shipped (2026-08-19):** Constraint closeout only — not a tenancy redesign.
  - `campaigns.workspace_id`, `queue_items.workspace_id`, `telegram_channels.workspace_id` are **NOT NULL**.
  - FKs use **ON DELETE RESTRICT** (Stage-1 `SET NULL` is incompatible with NOT NULL).
  - **No automatic backfill.** Migration `013` counts NULL rows on those three tables and **aborts** with table names and counts if any remain. Rows are not assigned to the bootstrap workspace and are not deleted. Operators assign leftovers with `python -m scripts.assign_legacy_workspace_ids --workspace-id <uuid>` then retry `alembic upgrade head`.
  - `telegram_channel_id` remains **globally unique** (not `(workspace_id, telegram_channel_id)`).
  - No `workspace_id` on Product, Affiliate, AffiliateCampaign, Conversion, or QueuePublishAttempt.
  - Product remains a global shared catalog; Affiliate remains a global user-owned 1:1 profile (Task 7).
  - `conversions.external_order_id` remains globally unique.
- **Dependencies:** Tasks 2, 4, 5, 6, 7.
- **Database changes:** Alembic `013` (revises `012`): NULL check → replace FKs → `SET NOT NULL`. Downgrade restores nullable + `ON DELETE SET NULL` without deleting data.
- **Tests:** `tests/test_workspace_not_null.py`; existing isolation and publishing suites.
- **Explicit non-goals:** No new feature behavior; no Celery/SSE/frontend/Task 9; no composite Telegram uniqueness; no silent backfill.
- **Acceptance criteria:** Migration applies when every tenant row already has a workspace; fails closed otherwise; full suite passes.

### Task 9 — Frontend Workspace Context Plumbing

- **Status:** ✅ COMPLETE (2026-09-04)
- **Goal:** Implement the §9 architecture — `sessionStorage`-backed active workspace, Axios header interceptor, workspace-aware query keys, cache-clear-on-switch — with **no** workspace selector UI (per explicit instruction).
- **Dependencies:** Tasks 4 and 6 (needs real workspace-scoped endpoints to integrate against).
- **Expected files/modules:** `frontend/src/services/session.ts` (extend), `frontend/src/services/api-client.ts` (extend interceptor), new `frontend/src/lib/workspace.ts` or similar for the query-key helper.
- **Tests:** New `frontend/src/services/api-client.workspace.test.ts`.
- **Explicit non-goals:** No workspace selector, no new routes/pages, no new state-management library (per §23 boundary).
- **Acceptance criteria:** Existing frontend tests pass; new tests confirm header attachment and cache isolation on a simulated switch. **Verified:** login → `/auth/me` → `default_workspace_id` → `sessionStorage`; tenant routes send `X-Workspace-Id`; logout clears workspace state; SSE requires workspace id.

### Task 10 — Image Search UI (independent — can run in parallel with any Multi-workspace task)

- **Status:** ✅ COMPLETE (2026-08-22 UI; documented 2026-09-04)
- **Shipped (2026-08-22):** Discovery `ImageSearchPanel` calls existing global `POST /products/search/image`. No backend/API/gating changes.
- **Goal:** Build a frontend surface for the already-complete `POST /products/search/image` endpoint.
- **Scope:** New `ImageSearchPanel`/upload entry point inside `features/discovery`, `discovery.api.ts` gains `searchProductsByImage`, results render through the existing `DiscoveryResultsTable`/`DiscoveryProductInspector` components (§21) — no new results-rendering component needed.
- **Dependencies:** None.
- **Expected files/modules:** `frontend/src/features/discovery/api/discovery.api.ts` (extend), `frontend/src/features/discovery/components/` (one new upload/entry component), `frontend/src/features/discovery/types/api.ts` (extend).
- **Backend changes:** None — the endpoint already exists and is not modified.
- **Database changes:** None.
- **API changes:** None.
- **Tests:** New component/hook test(s) following the existing Discovery feature's test conventions.
- **Documentation:** `docs/08-implementation-roadmap.md` Discovery workspace checklist row flips from ⬜ to ✅; `docs/06-api-integration.md` §4.4 status updated.
- **Explicit non-goals:** Does not modify `POST /products/search/image` or its env-gating (`aliexpress_enable_ds_image_search`). Does not add multi-workspace context (independent per §17).
- **Acceptance criteria:** Image search reachable from the Discovery UI; existing Discovery tests pass unmodified; new tests cover the upload/search/result-render path. **Verified:** URL and file input; no `X-Workspace-Id`; inspector gallery can re-run image search.

### Task 11 — Click Tracking Foundational Schema + Redirect Endpoint

- **Status:** ✅ COMPLETE (2026-08-23 backend; live-verified 2026-09-04)
- **Goal:** Implement the §13 architecture — `Click` model, redirect endpoint, `click_id` now references a real row.
- **Dependencies:** Task 1 (for workspace scoping), Task 4 (Campaign scoping), plus resolution of the Product↔Campaign modeling question **only if** product-level attribution is required — otherwise scoped narrowly to affiliate-link clicks (§13, §17).
- **Expected files/modules:** `app/models/click.py` (new), new migration, new `app/api/v1/clicks.py` (or folded into an existing router), `app/services/click.py`.
- **Backend changes:** New public redirect route; `Conversion.click_id` gains an actual producer.
- **Frontend changes:** None (server-to-browser redirect, not an SPA concern).
- **Database changes:** New `clicks` table, additive.
- **API changes:** New public endpoint; existing `/conversions` contract unchanged (`click_id` already accepted).
- **Tests:** New `tests/test_click_tracking.py` — redirect records a click and 302s correctly; rate-limit behavior (reusing the Phase D `app/core/rate_limit.py` primitive, not inventing a new one).
- **Documentation:** `docs/06-api-integration.md` gains a new §.
- **Explicit non-goals:** Does not resolve Product↔Campaign modeling unless explicitly scoped to (flagged open question, §24). Does not implement bot-detection beyond basic rate-limiting.
- **Acceptance criteria:** New tests pass; a click followed by a matching `POST /conversions.click_id` correctly correlates. **Verified live:** `GET /api/v1/clicks/{affiliate_campaign_id}` persists before **302**; public scope; unsafe link **422**; cross-enrollment **422**; rate limit **429**; migration `014_add_clicks`; no `clicks.workspace_id`.

### Task 12 — Analytics Slice 1 (existing-data metrics)

- **Status:** ✅ COMPLETE (2026-09-04)
- **Goal:** A read-only `/analytics` endpoint + minimal frontend page using already-persisted Conversion and Click data.
- **Dependencies:** Tasks 4, 5, 6 (workspace-scoped source tables).
- **Shipped vs original design:** Click/conversion KPIs only (not QueuePublishAttempt or dashboard aggregates). Funnel shipped with Task 13 in the same implementation pass.
- **Explicit non-goals:** No new persistence/rollup table. No `workspace_id` on clicks/conversions.
- **Acceptance criteria:** New endpoint + page ship; metrics are traceable to real, already-persisted columns (no invented numbers).

### Task 13 — Analytics Slice 2 (click/funnel metrics)

- **Status:** ✅ COMPLETE (2026-09-04)
- **Goal:** Extend Analytics with click-derived metrics.
- **Dependencies:** Task 11, Task 12.
- **Acceptance criteria:** Funnel metrics (click→conversion rate) ship without altering Slice 1's existing metrics contract.

### Task 14 — Editable Settings (workspace-scoped)

- **Status:** ✅ COMPLETE (2026-09-04)
- **Goal:** A minimal, admin-gated, workspace-scoped settings table + API + form, covering only non-secret candidates identified in §11 (subject to product confirmation of the exact field list).
- **Shipped:** `workspace_settings` (migration `016`); `GET/PATCH /workspace-settings`; `PATCH /auth/me` for name/email. Connection booleans only — no secret values. PATCH is admin or workspace OWNER.
- **Dependencies:** Task 1 (and ideally Task 4/6 for a workspace to scope to).
- **Explicit non-goals:** Never exposes secrets/infra config (`jwt_secret_key`, API keys, `database_url`) — these remain env-only regardless.
- **Acceptance criteria:** At least one real setting (e.g., default AI provider) becomes DB-backed and editable per workspace, admin-gated.

### Task 15 — Payout Module (minimal)

- **Goal:** Either (a) expose the existing per-conversion `PAID` status transition via a dedicated, purpose-built endpoint/UI, or (b) build a batched payout ledger — pending the §14 product decision.
- **Dependencies:** Task 5 (Conversion workspace-scoping); soft dependency on Task 11 (Click Tracking, product-trust reasoning only, §14).
- **Explicit non-goals:** Does not implement real money movement/external payment-provider integration unless separately scoped — no repository evidence of any existing payment-provider client to extend.
- **Acceptance criteria:** Pending the product decision; not finalized here.

---

## 19. Recommended Implementation Sequence

```text
Task 1  — Multi-Workspace Foundational Schema
Task 2  — Workspace-Aware Admin Bootstrap CLI
Task 3  — Workspace Authorization Dependency
        │
        ├── Task 10 — Image Search UI  (parallel; no dependency on the above)
        │
Task 4  — Campaign Workspace-Scoping
Task 5  — Conversion Workspace-Scoping
Task 6  — Queue & Channel Workspace-Scoping
Task 8  — NOT NULL / Constraint Closeout
Task 9  — Frontend Workspace Context Plumbing
        │
        ├── Task 7  — Product/Affiliate Scoping (conditional on product decision)
        ├── Task 12 — Analytics Slice 1
        ├── Task 14 — Editable Settings
        └── Task 11 — Click Tracking
                │
                ├── Task 13 — Analytics Slice 2
                └── Task 15 — Payout Module
```

**Task 1 is the recommended Phase E Task 1** (see §20 for why it, and not a "bigger" task, is the safest starting point).

---

## 20. Migration / Rollout Strategy

No migrations are written or applied in this task. Staged plan only:

- **Stage 1 (additive, zero-risk):** Create `workspaces`/`workspace_memberships` tables (Task 1). Add nullable `workspace_id` columns to `campaigns`, `conversions`, `queue_items`, `telegram_channels` (Tasks 4–6). No route behavior changes yet — every existing endpoint keeps working exactly as today, since nothing yet requires the new column.
- **Stage 2 (data backfill):** Run the Admin Bootstrap CLI (Task 2) to create one bootstrap workspace; backfill every existing row's new `workspace_id` column to that workspace via a one-off script, kept separate from the schema migration itself (§7.6).
- **Stage 3 (authorization enforcement):** Wire the Task 3 dependency into `campaigns`, `conversions`, `queues`, `channels`, `queues/stream` routes (Tasks 4–6) — this is the first stage where behavior actually changes: requests without a valid workspace header/membership now receive `403`. This is a **breaking change for any caller that doesn't yet send the header** — mitigated by shipping Task 9 (frontend plumbing) in lockstep with the backend route changes, not after.
- **Stage 4 (frontend workspace context):** Task 9 — `sessionStorage` + interceptor + workspace-aware query keys + cache-clear-on-switch. Ships alongside Stage 3, not before or long after, to avoid a window where the backend requires a header the frontend doesn't yet send.
- **Stage 5 (constraints become strict):** Task 8 — flip `workspace_id` to NOT NULL and land the composite unique constraints (§7.4), only after Stage 2's backfill is verified complete across all target tables.

---

## 21. Testing Strategy

No tests are written in this task. Strategy only, organized by the categories requested:

**Backend:**
- Unit tests for `Workspace`/`WorkspaceMembership` models and the Task 3 authorization dependency in isolation (mirrors `tests/test_config_security.py`'s isolated-unit-first pattern from Phase D).
- Authorization tests: valid membership succeeds; cross-workspace access rejected (403); admin bypass still works — one test file per newly-scoped domain (`test_campaign_workspace_isolation.py`, `test_conversion_workspace_isolation.py`, `test_queue_workspace_isolation.py`, `test_channel_workspace_isolation.py`), following the existing one-file-per-concern convention (e.g. `test_conversions_authorization.py`, `test_rate_limit.py`).
- Workspace isolation tests: two workspaces' data never appears in each other's list/get responses.
- Migration tests: nullable-add → backfill → NOT NULL flip, up and down, on both PostgreSQL (CI) and SQLite (`Base.metadata.create_all`, test suite) paths — following the existing dual-dialect discipline already present for `QueuePublishAttempt`'s check constraints (§7.6).
- Repository tests: workspace-filtered query methods return only matching rows.
- API tests: full request/response cycle per newly-scoped route, including the new header requirement.
- Background task tests: `process_publish_queue` continues to process items across all workspaces in one pass without leaking one workspace's failure into another's batch (extends, does not replace, existing `tests/test_queue_publishing_service.py` batch-resilience coverage).

**Frontend:**
- Schema tests: none new expected unless a workspace-selection Zod schema is introduced (not required by §9's architecture, since no selector UI is built).
- API hook tests: workspace header attached correctly (`api-client.workspace.test.ts`, Task 9).
- Workspace switching tests: cache-clear-on-switch behavior, no stale cross-workspace data flash.
- Query-cache isolation tests: two different workspace ids produce two distinct, non-colliding cache entries for the same base query key.
- Route protection tests: a 403 from a workspace check does not trigger the existing refresh/auto-logout flow (extends `frontend/src/services/api-client.test.ts` from Phase D without modifying its existing 401 test cases).
- E2E tests: not CI-gated today (`docs/10-production-readiness.md` §3: "Playwright ... local/manual; not CI gate today") — Phase E should follow the same existing convention, not introduce a new CI requirement.

**Security:**
- IDOR tests: workspace header naming a workspace the caller isn't a member of → 403, for every newly-scoped route.
- Cross-workspace read/write tests: covered above per-domain.
- Admin boundary tests: `UserRole.ADMIN` continues to bypass workspace checks exactly as it bypasses ownership checks today (extends the existing `ConversionService` admin-bypass test pattern).

**Regression (every prior phase, explicitly named per instruction):**
- A.1: `tests/test_queue_publishing_service.py`, `tests/test_telegram_publisher_retry.py`, `tests/test_telegram_long_messages.py`, `tests/test_queue_delete.py`, `tests/test_queue_publish_attempt_repository.py`, `tests/test_queue_publishing_idempotency.py` — must pass unmodified.
- A.2: `tests/test_sse_endpoint.py`, `tests/test_event_broadcaster.py`, `tests/test_event_publisher.py`, `tests/test_event_consumer.py`, `tests/test_event_schemas.py`, `tests/test_event_lifecycle.py`, `tests/test_event_emission.py`, `tests/test_event_publisher_wiring.py` — must pass unmodified except the one new filter-predicate addition in Task 6, which must not alter any existing assertion.
- B: `tests/test_worker_heartbeat.py`, `tests/test_worker_health.py`, `tests/test_flower_config.py` — must pass unmodified.
- C': `tests/test_aliexpress_api_client_retries.py`, `tests/test_aliexpress_no_nested_retry.py`, `tests/test_ai_provider_retry.py`, `tests/test_discovery_task_exceptions.py`, `tests/test_phase_c_prime_api_regression.py` — must pass unmodified.
- D: `tests/test_auth_refresh.py`, `tests/test_rate_limit.py`, `tests/test_conversions_authorization.py`, `tests/test_config_security.py` — must pass unmodified.
- Form & Schema Validation: existing frontend test suite (queue scheduling, product status schema tests) — must pass unmodified; no Zod/RHF pattern is altered by Phase E.

---

## 22. Documentation Impact

Not updated in this task (per instruction — Task 0 produces exactly one new file). Eventually affected, in rough order of how early each Phase E task would touch them:

| Document | Expected eventual update |
| --- | --- |
| `docs/08-implementation-roadmap.md` | New Phase E task checklist (mirroring every prior phase's completion table); feature-completion checklist rows for Image Search, Editable Settings, Admin Bootstrap flip from ⬜ |
| `docs/06-api-integration.md` | New workspace-header requirement documented in §3/§7; new `/analytics`, click-redirect, payout, settings endpoint rows; `/campaigns`/`/conversions`/`/affiliates` rows updated from "No MVP screens" once/if a frontend consumer ships |
| `docs/02-frontend-architecture.md` | New §for workspace context architecture (distinct from the existing §4 "Workspace Architecture" UI-pattern section — naming collision flagged in §1, finding 3, should be resolved in the actual doc update, e.g. renaming §4 or clearly subtitling the new section "Tenancy") |
| `docs/07-development-guidelines.md` | New guidance on the mandatory-workspace-parameter repository convention (§6.4 mitigation) |
| `docs/10-production-readiness.md` | §6 tenancy row updated from "not user-scoped" once scoping ships; new admin-bootstrap runbook step (§4) |
| `docs/03-design-system.md`, `docs/04-component-library.md` | Only if/when a workspace selector UI is eventually built (explicitly not in Phase E's early tasks) |
| `docs/frontend/11-workspace-design-system.md` | Should clarify the pre-existing "workspace" UI-pattern naming does not refer to tenancy, to prevent the ambiguity flagged in §1 finding 3 from propagating into this document's own terminology |

---

## 23. Risks / Open Questions

Restating every `Product decision required` flagged throughout this document in one place:

1. Should `Product` become workspace-scoped, or remain a shared global catalog? (§4.2, §7.1) — **Recommendation: keep global**, given the AliExpress-import cost multiplier a per-workspace catalog would create (§15), but this is a recommendation, not a resolved decision.
2. Should `Affiliate` become 1-per-(user, workspace), or remain 1-per-user globally? (§4.2, §5.1)
3. Should `WorkspaceMembership` support >1 user per workspace (Option B) or is owner-only (Option A) actually sufficient? (§5.1)
4. Who can create a new workspace — any authenticated user (self-service) or only an admin (managed)? (§5.2)
5. Should `conversions.external_order_id` become workspace-scoped-unique, or must it remain globally unique? (§7.4)
6. Exact settings field list for Editable Settings, and which require admin vs. any workspace member? (§11)
7. Is payout eligibility per-conversion (current model already supports this) or batched-per-period (typical real-world shape, unevidenced here)? (§14)
8. Does Click Tracking need to resolve the `Product`↔`Campaign` modeling gap, or can it ship scoped narrowly to affiliate-link clicks only? (§13 — **flagged as the single largest open architecture question in Phase E**)
9. Does a real external caller of `POST /conversions` exist outside this repository's visibility? (Carried forward unresolved from Phase D's own §22 open question — still unresolved, still relevant to how Click Tracking's postback flow should authenticate merchant callers.)
10. What exact metrics does Analytics need to show? (§10 — nothing beyond the bare route name `/analytics` is specified anywhere in the roadmap.)

**Risks (non-decision, architectural):**

- Shipping any workspace-scoped route (Stage 3, §20) without the frontend header plumbing shipping in lockstep (Stage 4) breaks every existing authenticated user of that route — mitigated by the explicit "ship Tasks in lockstep" note in §20.
- The pre-existing `Campaign` ownership gap (§4.1, §6.4) is easy to silently "fix along the way" without anyone noticing it was ever a gap — this document deliberately calls it out by name so it is fixed *consciously*, with a test proving the fix, not incidentally.
- Naming collision between the pre-existing UI "workspace" convention and the new tenancy "workspace" concept (§1 finding 3) risks confusing code review and documentation if not explicitly disambiguated in Task 1's naming (e.g., `Workspace`/`WorkspaceMembership` as SQLAlchemy/domain terms are fine; care is needed in frontend variable/component naming to avoid colliding with existing `useQueueWorkspaceState`-style names).

---

## 24. Explicit Non-Goals

Restated from the task's own constraints, plus findings from this analysis that should **not** be read as approved scope:

- No feature was implemented, no code was written, no migration was created, no test was written or modified, no dependency was installed, no configuration was changed, no UI was built.
- Multi-workspace tenancy's exact final schema (Option A vs B, §5.1) is a recommendation, not a locked decision — product confirmation is listed as required (§23).
- The `Product`↔`Campaign` relationship is **not** established or invented by this document (§13) — Click Tracking's literal roadmap-implied attribution chain (`product → affiliate link → click → conversion → payout`) is **not** confirmed as accurate to how this repository's data actually relates today.
- No specific Analytics metric, Settings field, or Payout eligibility rule is approved by this document — only what's structurally possible given existing data is described (§10, §11, §14).
- A.1, A.2, Phase B, Phase C', Phase D, and Form & Schema Validation Standardization are not redesigned anywhere in this document — every reference to their internals is read-only evidence gathering, and every task in §18 explicitly names its non-goals with respect to these phases.
- `QueueStatus` is not modified or proposed to be modified anywhere in this document.
- No global i18n framework, no new frontend state-management library, no new form library, no WebSocket transport, and no Axios/TanStack Query replacement is proposed anywhere in this document (§23 boundary of the originating task, fully honored).

---

## 25. Task 0 Completion / Next Task

Task 0 is complete per the following checklist (mirrored from the task's own §29):

- [x] Phase E current state inspected across backend (`app/`), frontend (`frontend/src/`), migrations (`alembic/versions/`), and tests (`tests/`).
- [x] Multi-workspace current ownership model documented (§4).
- [x] Entity ownership matrix produced (§4.2).
- [x] Workspace candidates identified, with explicit non-assumption where evidence is insufficient (§4.2, §7.1).
- [x] Authorization impact analyzed, with a concrete recommendation and rejected alternatives (§5.3, §6).
- [x] Database impact analyzed, including constraints, indexes, backfill, and staged rollout (§7).
- [x] API impact matrix produced (§8).
- [x] Frontend architecture impact analyzed without building UI (§9).
- [x] Analytics analyzed against actual available data, separating existing/required/product-decision (§10).
- [x] Editable Settings analyzed against the actual (entirely static) implementation (§11).
- [x] Image Search endpoint/UI state verified directly from source (§12 — actually documented in §21 numbering... see note below).
- [x] Admin Bootstrap state verified as entirely absent (§12).
- [x] Click Tracking state verified as entirely absent, with the Product↔Campaign gap surfaced (§13).
- [x] Payout state verified — per-conversion status exists, no ledger (§14).
- [x] Celery impact analyzed without redesigning worker infrastructure (§15).
- [x] SSE/A.2 impact analyzed without reopening A.2, concluding minimal, additive changes only (§16).
- [x] Dependency graph documented and validated against repository evidence, not assumed (§17).
- [x] Proposed task breakdown produced, split into small, independently verifiable tasks (§18).
- [x] Recommended implementation sequence produced (§19).
- [x] Migration/rollout strategy staged (§20).
- [x] Testing strategy documented across backend/frontend/security/regression (§21).
- [x] Documentation impact identified without updating those documents (§22).
- [x] Security risks documented per new-risk-vs-mitigation-vs-owning-task (§6.4).
- [x] Open questions explicitly listed, not silently resolved (§23).
- [x] Existing phase boundaries (A.1, A.2, B, C', D, Form & Schema Validation) preserved and explicitly re-stated as non-goals (§24).
- [x] No source code was modified.
- [x] No tests were modified.
- [x] No database changes were made.
- [x] No dependencies were added.
- [x] Exactly one new planning document was created: this file.

**Recommended next task: Phase E — Task 1: Multi-Workspace Foundational Schema** (§18) — chosen as the safest starting point because it is purely additive (two new tables, zero existing-route behavior change, §20 Stage 1), has no dependency on any unresolved product decision (§23), and is the hard prerequisite for the highest-value subsequent work (Campaign/Conversion/Queue/Channel scoping, §17's dependency graph). **Task 10 — Image Search UI** is called out as an equally safe, fully independent alternative if the team prefers to ship a small, self-contained user-facing win before starting the larger multi-workspace effort — it has zero dependencies and touches only the Discovery feature.

---

*End of Phase E Task 0 design document. No files other than this one were created or modified while producing this analysis.*
