# Form & Schema Validation Standardization
## Task 0 — Analysis & Architecture Decision

**Status:** Analysis only. No implementation performed.
**Independent of:** Phase D (Authentication & Public-Endpoint Security) — no overlapping files, confirmed in §15.

---

### 1. Executive Summary

The roadmap (`docs/08-implementation-roadmap.md` §3, Phase D — "Form & schema validation standardization") frames this milestone as if it were introducing React Hook Form and Zod into the project for the first time. **That framing does not match the repository.** Direct inspection found:

- `zod` (4.4.3), `react-hook-form` (7.81.0), and `@hookform/resolvers` (5.4.0) are **already installed** (`frontend/package.json`).
- The exact target pattern — `useForm` + `zodResolver` + a colocated `z.object()` schema + `register()` + inline Arabic error `<p>` elements — is **already implemented and working in production** in two forms: `frontend/src/features/auth/components/LoginForm.tsx` and the "add channel" form inside `frontend/src/features/channels/components/ChannelsView.tsx`.
- The design-system primitives this pattern depends on (`Input`, `Select`, `Textarea` in `components/ui/primitives.tsx`) already use `React.forwardRef`, so they are already `register()`-compatible with zero changes needed.

This milestone is therefore **not** "introduce RHF + Zod." It is: *extend an already-proven, two-instance-strong pattern to three more surfaces named by the roadmap* — the queue scheduling dialog, product status editing, and channel assignment — while correcting three scope assumptions the roadmap's phrasing gets wrong relative to the actual UI:

1. **"Drawer inline edits: product status" does not exist as a drawer feature today.** `ProductDetailsDrawer.tsx` renders `product.status` as a read-only `Badge`. The only place a user can actually change a product's status is a bulk-action `<select>` in `ProductsSelectionBar.tsx` (the selection bar, not the drawer), which fires the mutation immediately on `onChange`. There is no form, no submit step, and — because it is a closed, browser-rendered 4-option `<select>` — no reachable invalid input state to validate against. Building new drawer UI to match the roadmap's literal wording would be unjustified scope expansion; standardizing the *existing* status-change mechanism is the correct, evidence-grounded target (§6, §8, Task 3).
2. **"Channel assignment" has no separate UI surface outside the scheduling dialog.** `QueueDetailsDrawer.tsx` shows the assigned channel read-only; there is no independent "reassign channel" affordance anywhere else. Channel assignment happens exclusively inside `QueueSchedulingDialog`'s channel `<Select>`. This should be validated as part of the scheduling dialog's schema, not as a separate task/UI (§8, folded into Task 2).
3. **The scheduling dialog (`QueueSchedulingDialog.tsx`) is the one genuinely under-validated surface**, and is the correct, primary target for the roadmap's "React Hook Form + zodResolver for the scheduling dialog" item. It is currently a fully controlled, prop-driven component with **zero validation library involvement** — its only "validation" is a `disabled={!channelId || !scheduledAt || busy}` button guard and a silent (no visible error message) `if (!channelId || !scheduledAt) return;` guard in the parent's submit handler (`QueueView.tsx::saveSchedule`). A user who somehow reaches an invalid combination gets no explanation, only an inert button. This is the one real, user-facing gap this milestone should close (§7, Task 2).

A second, independent finding: `docs/07-development-guidelines.md` §4 currently states Discovery's filter validation (`validateDiscoveryDraft`) is Zod-based. It is not — it is a hand-written function returning `string | null` (`frontend/src/features/discovery/components/DiscoveryFilterPanel.tsx`). This is a pre-existing, minor documentation-vs-code mismatch, noted for completeness (§2) and left for Task 7 (documentation closeout) to correct — it is not a defect in the current implementation, only in its description.

A third finding, relevant to §9/§11 (Arabic error strategy): backend validation and business-error messages (`ServiceError.message`, Pydantic `detail` strings) are **in English** (e.g. `"scheduled_at is required when status is scheduled"`, `"Insufficient permissions"`), and are displayed to users verbatim today (e.g. `login.error.message`, `create.error.message` in the existing forms) inside an otherwise Arabic-RTL UI. This is a genuine, pre-existing inconsistency, but per this task's own instruction ("must not incorrectly translate or hide business/domain failures"), **translating backend messages is explicitly out of this milestone's charter** — it would require either backend changes (out of scope) or a speculative frontend translation-mapping layer (not currently justified by repository evidence of a defined message catalog). This is documented as an accepted, named limitation, not silently ignored (§11, §18).

---

### 2. Current Validation Architecture

```text
Frontend request type (features/*/types/api.ts)
        ↓
API client (features/*/api/*.api.ts → services/api-client.ts)
        ↓
FastAPI endpoint (app/api/v1/*.py)
        ↓
Pydantic request schema (app/schemas/*.py) — field constraints + model_validators
        ↓
Service layer (app/services/*.py) — role/ownership checks, no extra field validation found for the three targets
        ↓
Database — no CHECK constraints found on products/queue_items/channels beyond FK/enum-shape (unlike A.1's queue_publish_attempts)
```

For the three roadmap targets, validation today is concentrated almost entirely at the Pydantic layer, with the frontend doing little to nothing before the request is sent — **except** the two already-modernized forms (login, add-channel), which validate client-side first via the existing RHF+Zod pattern, then still rely on the backend as the authority (the service layer's `ConflictError`/`UnauthorizedError` paths are unreachable from Zod and correctly remain server-only).

Documentation-vs-code check: `docs/07-development-guidelines.md` §4's claim that Discovery uses "Zod schemas" for `validateDiscoveryDraft` does not match the code (it's a manual function, no Zod import) — noted above, corrected in Task 7, not a code defect.

---

### 3. Backend Schema Inventory

#### `app/schemas/product.py`

| Schema | Field | Type | Constraint |
| --- | --- | --- | --- |
| `ProductUpdate` | `status` | `ProductStatus \| None` | Any of the 4 enum values; **no transition rule** — confirmed in `app/services/product.py::update`, which does an unconditional `setattr` for every field present in `payload.model_dump(exclude_unset=True)`. No "can't go from `archived` back to `draft`"-type rule exists anywhere. |
| `ProductUpdate` | (all other fields) | — | Present in the schema (`title`, `price`, `discount`, etc.) but **not exposed by any current frontend mutation** — `useUpdateProduct` (`frontend/src/features/products/hooks/useProducts.ts`) only ever sends `{ status }`. Out of scope for this milestone (no UI calls these fields). |

`ProductStatus` enum (`app/core/enums.py`): `draft | active | inactive | archived` — exactly 4 values, exactly matching the frontend's `ProductStatus` union (`frontend/src/features/products/types/api.ts:1`) and the two independent hardcoded Arabic label maps described in §6/§8.

#### `app/schemas/queue.py`

| Schema | Field | Type | Constraint |
| --- | --- | --- | --- |
| `QueueUpdate` | `status` | `QueueStatus \| None` | 4 values: `draft \| queued \| scheduled \| published` |
| `QueueUpdate` | `scheduled_at` | `datetime \| None` | No format/range constraint beyond `datetime` parsing |
| `QueueUpdate` | `channel_id` | `UUID \| None` | No existence check at the schema layer (checked by FK/service, not inspected further — out of scope, no evidence of a problem) |
| `QueueUpdate` | `button_text` / `button_url` | `str \| None` | max length 128 / `HttpUrl \| str \| None` |
| **Cross-field rule 1** | `validate_scheduling` (`model_validator(mode="after")`) | — | **If `status == "scheduled"`, `scheduled_at` is required** (raises `ValueError` otherwise). This is the one business rule directly relevant to the scheduling dialog. |
| **Cross-field rule 2** | `validate_button` (`model_validator(mode="after")`) | — | `button_text` and `button_url` must be provided together (XOR-forbidden). **Not relevant to any of the three roadmap targets** — no current UI edits these two fields together; noted for completeness only, explicitly out of scope (§13). |

Note: unlike `QueueCreate`'s equivalent validator, `QueueUpdate.validate_scheduling` does **not** null out `scheduled_at` when status isn't `scheduled` — a minor asymmetry between the two schemas, not evidenced to cause any current problem (no UI path triggers it), noted as a non-blocking observation, not a task.

#### `app/schemas/channel.py`

| Schema | Field | Type | Constraint |
| --- | --- | --- | --- |
| `ChannelUpdate` | `telegram_channel_id` | `str \| None` | `field_validator` calls `normalize_telegram_channel_id` (Telegram-specific format normalization — e.g. `@handle` vs. numeric `-100...` id forms) |
| `ChannelUpdate` | `is_active` | `bool \| None` | — |
| `ChannelUpdate` | `title` | `str \| None` | max length 255 |

`normalize_telegram_channel_id` is Telegram-domain logic (`app/telegram/validators.py`) — this is exactly the kind of backend rule that must **not** be mirrored in the frontend (principle #3), and it is not relevant to "channel assignment" as scoped by this milestone in any case: the queue's "channel assignment" is *selecting an existing, already-normalized* `Channel.id` (a UUID) from a `<Select>` populated by `GET /channels`, never typing a raw Telegram identifier. The only two channel-creation forms that touch `telegram_channel_id` directly (`ChannelsView.tsx`'s add-channel form) already validate it client-side today, independently of this milestone's three named targets.

---

### 4. Frontend Validation Inventory

| Form / surface | Library used | Validation today | Error display |
| --- | --- | --- | --- |
| `LoginForm.tsx` | RHF + Zod + `zodResolver` | Full — email format, required password | Inline `<p>` per field (`errors.field.message`) + form-level `login.isError` alert |
| `ChannelsView.tsx` "add channel" | RHF + Zod + `zodResolver` | Full — required `telegram_channel_id` (1–64 chars), optional `title` (≤255) | Same pattern |
| `ChannelsView.tsx` active-toggle button | None | N/A — boolean toggle, no invalid state possible | N/A |
| `ProductsSelectionBar.tsx` bulk status `<select>` | None | **None** — relies entirely on the browser rendering only the 4 valid `<option>` values | N/A (no invalid state reachable) |
| `ProductsToolbar.tsx` status filter `<select>` | None | Same as above — filter, not a mutation, but shares the identical enum/label duplication problem (§6) | N/A |
| `QueueSchedulingDialog.tsx` | **None** | **None** — plain controlled `<Select>` + `<Input type="datetime-local">`; only guard is a `disabled` boolean on the Apply/Publish-Now buttons in the parent (`QueueView.tsx`) | **None** — no error message is ever shown for an incomplete form; the button is simply inert |
| `QueueView.tsx::saveSchedule` | None | A second, redundant `if (!channelId || !scheduledAt) return;` guard, silently mirroring the disabled-button condition | None |
| `ProductDetailsDrawer.tsx` | N/A | No edit UI at all for status (read-only badge) | N/A |
| `QueueDetailsDrawer.tsx` | N/A | No edit UI at all for channel (read-only "Info" block); scheduling is delegated entirely to `QueueSchedulingDialog` via the `onSchedule` callback | N/A |
| Discovery filter draft (`DiscoveryFilterPanel.tsx`) | Manual function (`validateDiscoveryDraft`), **not Zod** despite `docs/07`'s claim | Returns a single `string | null` error message for the whole draft | Single inline alert, not per-field |

**Conclusion:** exactly one surface among the three roadmap targets (the scheduling dialog) has a real, user-facing validation gap. The other two ("product status," "channel assignment") are closed-enum `<select>` inputs with no reachable invalid state — their "standardization" opportunity is about eliminating duplicated hardcoded label/option lists (a DRY/consistency win), not adding validation UX that doesn't currently need to exist.

---

### 5. Backend ↔ Frontend Contract Mapping

| Frontend request type | API client | Endpoint | Pydantic schema | Service validation | DB constraint |
| --- | --- | --- | --- | --- | --- |
| `ProductUpdate` (`{ status }` only, `frontend/src/features/products/types/api.ts:44-46`) | `updateProduct` (`products.api.ts`) | `PATCH /products/{id}` | `ProductUpdate` (`app/schemas/product.py`) | Admin-role check only (`_ensure_admin`); no transition rule | `Enum(ProductStatus, native_enum=False)` column — DB rejects any string outside the 4 values, but this can only be reached by bypassing the frontend entirely (not a gap) |
| `QueueUpdate` (`channel_id`, `status`, `scheduled_at` subset, `frontend/src/features/queue/types/api.ts:60-72`) | `updateQueueItem` (`queue.api.ts`) | `PATCH /queues/{id}` | `QueueUpdate` (`app/schemas/queue.py`) | None beyond the schema's own `model_validator`s | `Enum(QueueStatus, native_enum=False)`; no CHECK constraint tying `scheduled_at` to `status` at the DB layer (enforced only in Pydantic) |
| `ChannelUpdate` (not touched by this milestone's 3 targets, listed for completeness) | `updateChannel` (`channels.api.ts`) | `PUT /channels/{id}` | `ChannelUpdate` | None beyond `_ensure_admin`-equivalent (not re-verified here, out of scope) | `Enum`/`unique` constraints not relevant to the fields this milestone touches |

**Frontend request type field name (`ProductUpdate` on the frontend, `frontend/src/features/products/types/api.ts:44-46`) is intentionally narrower than the backend schema** — this is not a mismatch/bug, it is a deliberate, already-correct minimal contract (the frontend only ever needs to send `status`), and this milestone should **preserve** that narrowness rather than widen it to mirror every backend field (per principle #4 — do not change API contracts without a justified mismatch, and none was found here).

**Discrepancy found and explicitly documented (per the task's own instruction):** `QueueUpdate`'s backend schema only requires `scheduled_at` when `status == "scheduled"` — it does **not** require `channel_id` at all for scheduling. The frontend's `QueueSchedulingDialog`/`QueueView.saveSchedule`, however, already requires **both** `channelId` and `scheduledAt` before allowing "Apply" (`disabled={!channelId || !scheduledAt || busy}`). This is a **frontend-is-stricter-than-backend** discrepancy. It is evaluated as **intentional and correct product behavior, not a bug** — scheduling a post with no destination channel would be operationally meaningless (nothing to publish to) even though the backend's schema doesn't forbid it — but it means the future Zod schema for this dialog must **encode a UX rule that has no backend-schema counterpart**, which is worth flagging explicitly rather than assuming Zod should simply "mirror Pydantic" 1:1 here (§9, Task 1).

---

### 6. Product Status Validation Analysis

| Attribute | Value |
| --- | --- |
| Frontend field name | `status` (via `useUpdateProduct({ id, status })`) |
| Backend field name | `status` (`ProductUpdate.status`) |
| TypeScript type | `ProductStatus = "draft" \| "active" \| "inactive" \| "archived"` (`features/products/types/api.ts:1`) |
| Pydantic type | `ProductStatus` (`StrEnum`, identical 4 values) |
| Enum values | Identical on both sides — no drift found |
| Allowed transitions | **None enforced anywhere** (backend confirmed via `app/services/product.py::update`) — any status can move to any other status |
| Current frontend validation | None — native `<select>` in `ProductsSelectionBar.tsx`, browser-constrained to the 4 rendered `<option>`s |
| Current backend validation | Enum membership only (Pydantic + DB column enum) |
| Proposed Zod representation | `z.enum(["draft", "active", "inactive", "archived"])` — **not for runtime form validation** (no invalid state is reachable through the existing `<select>`), but as the **single source of truth** for the option list + Arabic labels, replacing the two independently hardcoded label objects found in `ProductsToolbar.tsx` (`STATUS_LABELS`-equivalent inline object at lines 13-21) and `ProductDetailsDrawer.tsx` (`STATUS_LABELS` at lines 14-19) and the raw `<option>` list in `ProductsSelectionBar.tsx` (lines 58-62). |

**Finding:** there is no "product status validation" gap to close in the sense of catching bad user input — the real, evidence-grounded improvement available here is **eliminating three independently duplicated Arabic status-label maps** by centralizing them alongside a `z.enum` in one shared file, which also happens to satisfy the roadmap's "Zod schemas mirroring Pydantic" instruction for this domain. See Task 3.

---

### 7. Queue Scheduling Validation Analysis

| Attribute | Value |
| --- | --- |
| Scheduling fields | `channel_id` (UUID), `scheduled_at` (ISO datetime string), `status` (set to `"scheduled"` or `"queued"` depending on which action is taken) |
| Date/time representation | Frontend: `datetime-local` input value (`YYYY-MM-DDTHH:mm`, local time, no timezone suffix) converted via `new Date(value).toISOString()` before sending (`QueueView.tsx::saveSchedule`). Backend: `datetime` (Pydantic parses the ISO 8601 string; PostgreSQL stores timezone-aware). No timezone-selection UI exists — the browser's local timezone is implicit throughout, consistent on both ends, not a gap. |
| Required/optional semantics | Backend: `scheduled_at` required **only if** `status == "scheduled"` (not required for the "publish now" / `status: "queued"` path, confirmed in `QueueView.tsx::publishFromDialog`, which never sends `scheduled_at`). Frontend today: the Apply button requires both fields unconditionally; the "Publish Now" preset buttons only require `channelId` (`disabled={!channelId \|\| busy}` on that specific button, line 103 of `QueueSchedulingDialog.tsx`) — meaning the frontend **already correctly branches this exact conditional-requirement rule at the UI level**, just without any Zod/RHF backing it. |
| Nullability | `scheduled_at`/`channel_id` are both nullable at the schema level; not nullable in practice for this dialog's two action paths (Apply always needs both; Publish Now always needs `channel_id`). |
| Minimum/maximum constraints | Frontend already sets `min={toDateTimeLocal(new Date())}` on the native date input (no past dates selectable via the picker UI) — but this is only a UI affordance, not enforced on manual typing or on the disabled-button logic, and has **no backend-side equivalent** (Pydantic does not reject a past `scheduled_at`). This is a legitimate, additive UX rule to formalize in Zod (§5's documented discrepancy). |
| Current dialog behavior | Fully controlled component (props in, callbacks out); zero internal validation state; schedule presets (`hour`, `tomorrow_morning`, `tomorrow_evening`) call `onScheduledAtChange` directly with a computed value, bypassing any validation path entirely (they're always valid by construction, so this is fine and needs no schema involvement). |
| Backend schema | `QueueUpdate` cross-field rule 1 (§3) — the only backend rule this dialog should mirror. |
| Proposed Zod representation | A single schema in a new `features/queue/lib/schemas.ts`, most naturally expressed as a `z.discriminatedUnion` (or an equivalent `z.object({...}).refine(...)`) over the dialog's two real actions: `{ intent: "schedule", channelId: <uuid>, scheduledAt: <datetime, not in the past> }` and `{ intent: "publish_now", channelId: <uuid> }` — directly mirroring the backend's conditional-requirement rule (mirror the rule, not duplicate arbitrary complexity) while adding the frontend-only "not in the past" refinement that already exists as an HTML `min` attribute today but has no enforced/error-surfaced equivalent. |

This is the milestone's primary, evidence-justified target. See Task 1 (schema) and Task 2 (RHF migration).

---

### 8. Channel Assignment Validation Analysis

| Attribute | Value |
| --- | --- |
| Channel identifier | `channel_id: UUID` — selected from a `<Select>` populated by the already-fetched, already-validated `GET /channels` list (`Channel[]`) |
| Required/optional semantics | Required for both of the scheduling dialog's action paths (§7) — there is no queue-editing UI where `channel_id` is optional in practice, even though the backend schema allows `null` |
| Nullability | Nullable at the schema/DB level (a queue item can exist in `draft`/`queued` with no channel yet) — this milestone does not touch that state, only the moment of active scheduling/publishing, where a channel is always required |
| Valid values | Constrained to `channels.filter(c => c.is_active && c.can_post_messages)` — **this filter is itself a form of validation already present today**, ensuring a user cannot select a channel that couldn't actually receive a publish. This must be preserved exactly, not weakened, when the dialog is migrated to RHF (Task 2). |
| Current frontend behavior | Same controlled `<Select>` as described in §7 — no separate UI surface exists for "channel assignment" outside this dialog (confirmed by reading `QueueDetailsDrawer.tsx` in full: it renders the assigned channel as read-only text, with no edit affordance). |
| Backend schema | `QueueUpdate.channel_id: UUID | None` — no existence/ownership check found in the schema itself (service/DB-level FK is the actual authority; not modified by this milestone). |
| Proposed Zod representation | Folded into the same schema as §7 (`channelId: z.string().uuid()` as the shared field across both discriminated-union branches) — **not a separate schema or task**, since there is no independent "channel assignment" surface to validate. |

**Scope correction (stated plainly):** the roadmap lists "channel assignment" as if it were a third, independent inline-edit target. Repository evidence shows it is not — it is one field of the scheduling dialog's single form. Task 4 (below) exists only to make this explicit and confirm no additional UI work is needed, not to build new functionality.

---

### 9. Zod Architecture Decision

**Schema ownership and file locations:**

| Domain | Proposed file | Status |
| --- | --- | --- |
| Queue scheduling | `features/queue/lib/schemas.ts` (**new file**) | Matches the roadmap's stated target location exactly; justified here because the schema needs to sit next to `features/queue/lib/operations.ts` (which already owns `getSchedulePreset` and other scheduling-adjacent pure logic) and because the schema's two-branch shape is non-trivial enough to warrant its own file rather than living inline in the dialog component. |
| Product status | `features/products/lib/schemas.ts` (**new file**, small — a single `z.enum` plus a shared label map) | Extracted specifically because the same enum/label pair is currently duplicated three times (§6) — this is exactly the "two-workspace/multiple-consumer rule" from `docs/frontend/11-workspace-design-system.md` §5 firing correctly, not premature extraction. |
| Channel assignment | No new schema file — folded into `features/queue/lib/schemas.ts` per §8. | — |
| Login / add-channel (existing, unchanged) | Remain **inline in their component files**, exactly as today. | Explicitly **not** refactored by this milestone — they are not broken, not duplicated elsewhere, and moving them would be change for its own sake, contradicting principle #5 (incremental adoption) and the "no premature extraction" rule. |

**Derivation direction:** existing API types in `features/*/types/api.ts` remain authoritative and are **not** replaced by Zod-inferred types. New schemas should `import type` the existing `ProductStatus`/`QueueStatus` unions and validate *against* them (e.g. `z.enum(QUEUE_STATUSES)` reusing the existing `QUEUE_STATUSES as const` array already exported from `features/queue/types/api.ts:1`), rather than the reverse (`ProductStatus`/`QueueStatus` being redefined via `z.infer`). This preserves the existing, working type-authority direction described in `docs/07-development-guidelines.md` §4.3 ("Feature API contracts currently live in `features/[feature]/types/api.ts`") and avoids a project-wide type-origin migration that is not evidenced as necessary.

**Enum representation:** `z.enum(...)` reusing the existing exported `as const` arrays (`QUEUE_STATUSES` already exists exactly for this; no equivalent `PRODUCT_STATUSES` const currently exists in `features/products/types/api.ts` and should be added as part of Task 3, mirroring the pattern already established in the queue feature).

**Nullable/optional representation:** standard Zod `.optional()`/`.nullable()` — no unusual pattern needed; the two schemas in scope (§7/§8's combined schema, §6's enum) have no deeply nested optional structures.

**Dates/times:** represented as plain strings validated with `z.string().refine(...)` against `Date` parseability and the "not in the past" rule (§7) — **not** `z.date()`, since the underlying HTML input (`type="datetime-local"`) and the existing `toDateTimeLocal`/`new Date(...).toISOString()` conversion helpers already operate on strings; introducing `z.date()` would require an extra conversion layer with no evidenced benefit.

**Numeric constraints:** not applicable — none of the three targets involve numeric fields.

**Backend validation that must remain server-authoritative, not mirrored:**

- `normalize_telegram_channel_id` (Telegram-format normalization) — domain-specific parsing logic, not a simple constraint; already correctly un-mirrored today even in the existing `ChannelsView.tsx` Zod schema (which only checks length, not format).
- Product status "admin-only" authorization (`_ensure_admin`) — an authorization concern, not a validation concern; Zod cannot and should not attempt this (the UI already gates the bulk-status control behind `canManage` in `ProductsSelectionBar`, which is the correct, existing mechanism).
- `QueueUpdate.validate_button` (button_text/button_url XOR) — not touched by any of the three targets; left server-only, no frontend UI currently edits these fields.
- Channel active/postable filtering — already implemented as a plain array `.filter()`, not a "validation" concern in the Zod sense; must be preserved as-is (§8).

---

### 10. React Hook Form Architecture Decision

**Current component:** `QueueSchedulingDialog.tsx` — a fully controlled, presentational component. State (`channelId`, `scheduledAt`, and the enclosing `itemIds`/dialog-open flag) lives in the parent, `QueueView.tsx`, as a single `schedulingDialog: SchedulingState | null` `useState`.

**Current input handling:** plain `onChange` handlers calling parent-supplied callbacks (`onChannelChange`, `onScheduledAtChange`) — fully uncontrolled-by-RHF, fully controlled-by-React-state today.

**Current submit flow:** two distinct "submit" actions map to two different parent functions — `onApply` → `QueueView.saveSchedule` (sequential `updateQueueItem` calls per selected item, status → `"scheduled"`) and `onPublishNow` → `QueueView.publishFromDialog` (status → `"queued"`, then immediately calls the existing publish flow). Both are already wired to the existing `useUpdateQueueItem`/publish mutation hooks — **no mutation hook changes are needed**, only how their inputs are validated before being called.

**Current error display:** none (§4, §7).

**Minimal migration architecture (recommended):**

- Convert `QueueSchedulingDialog` from prop-driven `channelId`/`scheduledAt`/`onChannelChange`/`onScheduledAtChange` to owning its own `useForm` instance internally, using `zodResolver(queueSchedulingSchema)` (§9's schema).
- **Preserve the external contract as much as possible**: keep `open`, `itemCount`, `channels`, `busy`, `onClose` as props; replace `channelId`/`scheduledAt`/`onChannelChange`/`onScheduledAtChange`/`onApply`/`onPublishNow` with a single `defaultValues` prop (populated by `QueueView`'s existing `openSchedule` logic, unchanged) and two submit callbacks that now receive **validated** `{ channelId, scheduledAt }` / `{ channelId }` payloads instead of being called with no arguments and reading closed-over state.
- Preset buttons (`hour`, `tomorrow_morning`, `tomorrow_evening`) switch from `onScheduledAtChange(...)` to RHF's `setValue("scheduledAt", ..., { shouldValidate: true })` — same computed values, same `getSchedulePreset` helper, no behavior change to the presets themselves.
- **Form default values:** the item's current `channel_id`/`scheduled_at` when rescheduling an already-scheduled item (exactly what `QueueView.openSchedule` already computes today — this logic moves into the `defaultValues` prop unchanged, not reimplemented).
- **Validation mode:** `onChange` or `onBlur` (not `onSubmit`-only) recommended, so the Apply/Publish-Now buttons can be disabled via `formState.isValid` exactly as they are disabled today via manual booleans — preserving the existing UX of "button is inert until the form is complete" while *adding* the currently-missing inline error messages for the case where a user interacts with a field and leaves it invalid.
- **Field-level errors:** `formState.errors.channelId`/`errors.scheduledAt`, rendered as the same inline `<p className="text-destructive">` pattern already used in `LoginForm`/`ChannelsView` — no new error-display component needed.
- **Server/mutation errors:** unchanged — `QueueView`'s existing `getApiErrorMessage`/`setToast` handling for `updateQueue`/publish failures remains exactly as-is; RHF/Zod only gate the client-side submit, they do not touch how a server-side failure (e.g. a 409 conflict) is surfaced.
- **Reset behavior:** RHF's `reset(defaultValues)` on dialog open/item change, replacing the current manual `setSchedulingDialog({...})` object construction — same data, cleaner ownership.
- **Cancel behavior:** unchanged — `onClose` prop, no form-state cleanup concerns beyond what `open`-gated unmounting/remounting (or an explicit `reset()` on close) already handles.
- **Interaction with the existing Dialog architecture:** `QueueSchedulingDialog` is a hand-rolled centered-dialog `<div>` (not the shared `Drawer` primitive) — this migration does not touch its structure, backdrop, or `role="dialog"` semantics at all, only its internal state management.

**Explicitly not recommended:** rewriting `QueueSchedulingDialog` as a new component, moving it into the `Drawer` primitive, or changing its visual layout. The existing `docs/07-development-guidelines.md` guardrail #3 ("Do not allow architecture drift... duplicate components") and this milestone's own principle #7 both argue for an in-place, isolated migration.

---

### 11. Arabic Validation Error Strategy

**Current state:** Zod messages are already Arabic, hand-written per-schema (`"معرّف القناة مطلوب"`, `"أدخل بريدًا إلكترونيًا صحيحًا"`, etc.) directly inside the two existing `z.object()` calls — there is no shared message catalog or utility today; each schema repeats its own strings.

**Backend/API errors** are in English (§1) and are displayed as-is via `error.message` from the shared `ApiError` type (`services/api-client.ts`) — this is a pre-existing condition, not something this milestone is chartered to fix (§1, restated in §18 as an open item).

**Proposed strategy (design only, not implemented in Task 0):**

- **A. Client-side validation errors** (required field, invalid format, invalid date, invalid range): keep them **inside the Zod schema definitions** (as today), but introduce a small, optional shared helper module — `frontend/src/lib/validation-messages.ts` — exporting a handful of reusable Arabic message builders for the patterns that will otherwise be re-typed slightly differently in each new schema (e.g. `requiredField(label: string)`, `notInThePast()`). This is a **thin convenience layer**, not a new abstraction that schemas are forced to use — existing inline messages in `LoginForm`/`ChannelsView` are **not** required to be retrofitted onto it (avoids unnecessary churn to already-working code, per principle #5).
- **B. Backend/API errors**: continue to be displayed verbatim via the existing `ApiError.message` → toast/inline-alert pattern already used everywhere (`login.isError`, `create.isError`, `QueueView`'s `setToast`). This milestone does **not** introduce a backend-message translation layer — doing so would require either a maintained English→Arabic dictionary (speculative, unbounded maintenance surface, no repository evidence of a defined message catalog to translate) or backend changes (explicitly out of scope, §2's prohibition on modifying backend schemas/behavior). This is a deliberate, named non-goal (§18), not an oversight.
- **Where messages live:** inside each Zod schema's own `.min()`/`.refine()` message arguments (as today), optionally drawing short, generic phrases from the new shared helper for genuinely repeated patterns only.
- **Field-level → UI mapping:** unchanged from the existing pattern — `formState.errors.<fieldName>.message` rendered directly beneath the corresponding input, exactly as `LoginForm`/`ChannelsView` already do.
- **Distinguishing the two error classes in the UI:** client-side errors render inline, beneath the specific field, the instant the field becomes invalid (per §10's `onChange`/`onBlur` mode) — before any network request. Server-side errors continue to render as a form-level alert/toast **after** a submit attempt, exactly as today — this separation already exists implicitly in the two working forms and simply needs to be preserved, not redesigned, in the three new/updated surfaces.

---

### 12. Dependency Analysis

| Dependency | Present? | Version | Evidence |
| --- | --- | --- | --- |
| `zod` | **Yes** | `4.4.3` | `frontend/package.json` dependencies |
| `react-hook-form` | **Yes** | `7.81.0` | `frontend/package.json` dependencies |
| `@hookform/resolvers` | **Yes** | `5.4.0` | `frontend/package.json` dependencies |

**No new dependency is required for this milestone.** All three packages are already installed, already used correctly in two production forms, and already exercised against the exact design-system primitives (`Input`, `Select`) this milestone needs (`components/ui/primitives.tsx`'s `React.forwardRef` usage, confirmed in §1).

**Conflict check:**

- **Existing React architecture:** no conflict — RHF is already mounted twice with no reported or observed interaction problems with Next.js App Router `"use client"` components (both existing usages are `"use client"` components, matching what `QueueSchedulingDialog`/`ProductsSelectionBar` already are).
- **TanStack Query:** no conflict — RHF governs only client-side form state; the existing mutation hooks (`useUpdateQueueItem`, `useUpdateProduct`) are called from submit handlers exactly as `useLogin`/`useCreateChannel` are called today from the two existing RHF forms. No overlap in responsibility.
- **Component library:** no conflict — `Input`/`Select` already forward refs (§1); no primitive needs modification.
- **TypeScript configuration:** no conflict — `zod@4.4.3` and the existing `tsconfig` are already compatible today (proven by the two existing forms compiling and running).
- **Build/test configuration:** no conflict — `vitest.config.ts` already exists and already presumably exercises code paths importing `zod`/`react-hook-form` indirectly via the app; no new Vitest configuration is anticipated (new test files will use the exact same `@testing-library/react` + `vitest` setup already used by the 16 existing frontend test files).

---

### 13. Proposed Task Breakdown

Derived strictly from the repository findings above — **not** a blind copy of the roadmap's illustrative structure. Three of the roadmap's four originally-implied surfaces collapse into fewer, more precisely-scoped tasks once the actual UI is accounted for (§1's three scope corrections).

#### Task 1 — Queue Scheduling Zod Schema Foundation

- **Objective:** create `features/queue/lib/schemas.ts` with the discriminated-union scheduling schema described in §7/§9, plus an exported `QUEUE_STATUSES`-style reuse of existing constants where applicable.
- **Scope:** one new file; no changes to any existing component in this task (schema only, unit-testable in isolation before any UI wiring).
- **Files/components:** `frontend/src/features/queue/lib/schemas.ts` (new).
- **Tests:** `frontend/src/features/queue/lib/schemas.test.ts` (new) — valid "schedule" payload passes; missing `scheduledAt` on "schedule" intent fails with the expected message; past `scheduledAt` fails; valid "publish_now" payload (no `scheduledAt` required) passes; missing `channelId` fails on both intents; malformed UUID for `channelId` fails.
- **Dependencies:** none (Task 0 only).
- **Out of scope:** no component changes; no `button_text`/`button_url` schema (§3's cross-field rule 2 — not used by any current UI).
- **Acceptance criteria:** all new schema unit tests pass; `zod@4.4.3` API usage (e.g. `z.discriminatedUnion` availability) verified against the installed version during implementation, not assumed.

#### Task 2 — Queue Scheduling Dialog: React Hook Form Migration

- **Objective:** migrate `QueueSchedulingDialog.tsx` to `useForm` + `zodResolver(queueSchedulingSchema)` per §10's architecture, with `QueueView.tsx` updated to supply `defaultValues` and receive validated submit payloads instead of owning raw field state.
- **Scope:** the dialog component's internals + the specific `schedulingDialog` state/handlers in `QueueView.tsx` (`openSchedule`, `saveSchedule`, `publishFromDialog`, and the `<QueueSchedulingDialog>` JSX props). No other `QueueView.tsx` logic (publishing batch results, realtime invalidation, toasts) is touched.
- **Files/components:** `frontend/src/features/queue/components/QueueSchedulingDialog.tsx`, `frontend/src/features/queue/components/QueueView.tsx`.
- **Tests:** new `QueueSchedulingDialog.test.tsx` — renders with default values; shows an inline error when Apply is attempted with an empty date; shows an inline error for a past date; enables Apply once both fields are valid; preset buttons correctly populate `scheduledAt` via `setValue` and clear any prior error; Publish Now path does not require `scheduledAt`. Additionally, **run the full existing 16-file frontend suite** (particularly the 11 Queue-realtime files) to confirm no regression — none of them currently import `QueueSchedulingDialog` (confirmed via repository search), so risk is assessed as low, but this must still be an explicit verification step, not an assumption.
- **Dependencies:** Task 1 (schema must exist first).
- **Out of scope:** no visual/layout redesign of the dialog; no change to the shared `Drawer`/`Dialog` primitives; no change to `useUpdateQueueItem`/publish mutation hooks themselves.
- **Acceptance criteria:** new dialog tests pass; full existing frontend suite (16 files) passes unmodified; manual behavior parity confirmed for both the "Apply" (schedule) and "Publish Now" flows against the currently-documented MVP acceptance flow (`docs/10-production-readiness.md` §5, item 5).

#### Task 3 — Product Status Shared Schema & Label Consolidation

- **Objective:** create `features/products/lib/schemas.ts` exporting a `PRODUCT_STATUSES` const array (mirroring the existing `QUEUE_STATUSES` pattern), a `z.enum(PRODUCT_STATUSES)` schema, and a single shared Arabic label map; update `ProductsToolbar.tsx`, `ProductsSelectionBar.tsx`, and `ProductDetailsDrawer.tsx` to import the shared label map instead of each maintaining its own copy.
- **Scope:** consolidation only — **no new interactive validation UX is added**, per §6's finding that no invalid state is reachable through the existing `<select>` inputs. The `<select>` markup itself is unchanged; only the source of its `<option>` list/labels changes.
- **Files/components:** `frontend/src/features/products/lib/schemas.ts` (new), `frontend/src/features/products/types/api.ts` (add `PRODUCT_STATUSES as const`, mirroring `QUEUE_STATUSES`), `ProductsToolbar.tsx`, `ProductsSelectionBar.tsx`, `ProductDetailsDrawer.tsx` (import-only changes, each file's existing label object deleted and replaced with the shared import).
- **Tests:** `frontend/src/features/products/lib/schemas.test.ts` (new) — the four expected values parse; an arbitrary invalid string is rejected. No new component test is strictly required since no new interactive behavior is introduced, but a lightweight snapshot/render check that all three consuming components still render the same four Arabic labels is recommended to catch a copy-paste mistake during the consolidation.
- **Dependencies:** none (independent of Task 1/2 — can run in parallel).
- **Out of scope:** no status-transition rule (none exists to add, §6); no change to `ProductDetailsDrawer.tsx`'s read-only presentation (adding an inline editable status control there would be new UI, explicitly out of this task's scope per §1's finding).
- **Acceptance criteria:** all three consuming components render identical labels/options to before the change (behavior-preserving refactor); new schema unit tests pass; no duplicate label object remains in the three files.

#### Task 4 — Channel Assignment: Scope Confirmation (no new code)

- **Objective:** formally confirm, as a documentation/verification step, that "channel assignment" validation is fully satisfied by Task 2's scheduling schema (§8) and that no separate UI or schema is needed.
- **Scope:** verification only — read `QueueDetailsDrawer.tsx` and `QueueSchedulingDialog.tsx` after Task 2 lands, confirm the channel `<Select>`'s active/postable filter (§8) was preserved unchanged, and record the confirmation in the milestone's closeout notes (Task 7).
- **Files/components:** none modified.
- **Tests:** none new — covered by Task 2's own test suite.
- **Dependencies:** Task 2 complete.
- **Out of scope:** any new "reassign channel" UI in `QueueDetailsDrawer` — not evidenced as needed, would be new product scope beyond this milestone's charter.
- **Acceptance criteria:** a short confirmation note (not a code change) is added to the Task 7 documentation closeout stating this was verified.

#### Task 5 — Arabic Validation Message Helper (optional, low-risk)

- **Objective:** add the small, optional `frontend/src/lib/validation-messages.ts` helper described in §11, and use it in Task 1's and Task 3's new schemas only (existing `LoginForm`/`ChannelsView` schemas are not retrofitted).
- **Scope:** one new small utility file + its use in the two new schema files from Tasks 1/3.
- **Files/components:** `frontend/src/lib/validation-messages.ts` (new); minor edits to `features/queue/lib/schemas.ts` and `features/products/lib/schemas.ts` (from Tasks 1/3) to use it instead of fully inline strings, if by this point those tasks did not already write equivalent inline strings — sequencing note in §14.
- **Tests:** `frontend/src/lib/validation-messages.test.ts` (new) — each exported builder returns the expected Arabic string for representative inputs.
- **Dependencies:** should land **before or alongside** Task 1 and Task 3 (not after) so those tasks can consume it directly rather than being refactored a second time — see corrected ordering in §14.
- **Out of scope:** retrofitting `LoginForm.tsx`/`ChannelsView.tsx` (§11 — deliberately not touched); any backend-message translation (§1, §11, §18).
- **Acceptance criteria:** helper unit tests pass; Task 1/Task 3 schemas use it for at least the "required field" and "invalid date" message classes without duplicating string literals.

#### Task 6 — Integration & Regression Validation

- **Objective:** run the full verification surface once Tasks 1–5 are complete: `npm run typecheck`, `npm run lint`, `npm test` (full Vitest suite, all 16 existing files + new ones), `npm run build`, and the backend's full `pytest` suite (to confirm, per §2/§15, that nothing on the backend was touched or regressed, since this milestone is frontend-only).
- **Scope:** verification only, no new source files.
- **Files/components:** none.
- **Tests:** none new — this task *runs* the tests written by Tasks 1, 3, and 5, plus the full pre-existing suite.
- **Dependencies:** Tasks 1–5 complete.
- **Out of scope:** fixing any *unrelated* pre-existing failing test discovered during this pass (document and report only, per the analysis-only discipline this project has consistently applied in every prior phase's closeout).
- **Acceptance criteria:** all of `typecheck`, `lint`, `test`, `build` (frontend) and `pytest` (backend) pass; the specific Playwright smoke scenario touching scheduling (if any exists in `frontend/e2e/smoke.spec.ts` — to be checked at Task 6 time, not assumed here) is confirmed unaffected.

#### Task 7 — Documentation Closeout

- **Objective:** update the authoritative docs to reflect the shipped state, and correct the pre-existing `docs/07-development-guidelines.md` §4 inaccuracy about Discovery's validation (§1/§2).
- **Scope:** documentation only.
- **Files/components:** `docs/08-implementation-roadmap.md` (mark this milestone complete; correct its own framing per §1's finding that RHF/Zod already existed rather than being newly introduced), `docs/02-frontend-architecture.md` (if it references form patterns — verify at Task 7 time), `docs/07-development-guidelines.md` §4 (correct the `validateDiscoveryDraft`-is-Zod claim; document the new `features/*/lib/schemas.ts` convention now that two real instances exist), `docs/06-api-integration.md` (only if any contract-relevant note is warranted — expected: none, since no API contract changes in this milestone).
- **Tests:** none.
- **Dependencies:** Task 6 complete (all tests green).
- **Out of scope:** any further roadmap milestone planning (a separate, future analysis task, consistent with how this project has always separated "close this phase" from "define the next one").
- **Acceptance criteria:** all listed docs updated; no other documentation file touched; the roadmap's Phase D entry no longer implies RHF/Zod were absent beforehand.

---

### 14. Task Dependency Graph

```text
Task 0 (this document)
  │
  ├──→ Task 5 (Arabic message helper) ─────────────┐
  │                                                  │
  ├──→ Task 1 (Queue scheduling schema) ◄───────────┤ (Task 1 consumes Task 5's helper if sequenced first)
  │       │                                          │
  │       ▼                                          │
  │    Task 2 (Scheduling dialog RHF migration)      │
  │       │                                          │
  │       ▼                                          │
  │    Task 4 (Channel assignment scope confirmation)│
  │                                                   │
  └──→ Task 3 (Product status schema/label consolidation) ◄──┘
          │
          ▼ (all of the above complete)
       Task 6 (Integration & regression validation)
          │
          ▼
       Task 7 (Documentation closeout)
```

**Corrected sequencing note:** §13's Task 5 description above states it "should land before or alongside Task 1 and Task 3" — the graph reflects that recommendation: **Task 5 first (or in the same work session as Task 1/3), not after.** This differs from the illustrative roadmap-style ordering (which numbers the message-strategy task later) because sequencing it last would force Tasks 1/3 to be revisited to adopt the helper, which is wasted rework. Task 5 is small enough (§13) to front-load at negligible cost.

**Parallelizable:** Task 1 and Task 3 have no dependency on each other (different features, different files) and can be implemented simultaneously once Task 5 (or its equivalent inline strings, if the helper is skipped — see §18) is available. Task 4 has no code of its own and is a lightweight verification gate after Task 2. **Sequential, hard dependencies:** Task 2 requires Task 1; Task 6 requires everything; Task 7 requires Task 6.

---

### 15. Regression Boundaries

This milestone is frontend-only for its actual code changes (Tasks 1–5); no backend file is modified by any task above. Verified non-overlap with every completed/in-flight phase:

- **Phase D (Authentication & Public-Endpoint Security):** zero file overlap. Phase D's Task 1–6 files (`app/core/config.py`, `app/auth/*`, `app/api/v1/conversions.py`, `frontend/src/services/session.ts`, `frontend/src/services/api-client.ts`) are entirely disjoint from this milestone's files (`features/queue/*`, `features/products/*`, `frontend/src/lib/validation-messages.ts`). No task in this document touches `services/api-client.ts` or `services/session.ts`.
- **Refresh-token lifecycle / rate limiting / conversion authorization:** not applicable — this milestone never calls `/auth/*` or `/conversions`.
- **A.1 publishing reliability:** `QueueUpdate`'s Pydantic schema and `TelegramPublishingService` are read-only inspected, never modified. `useUpdateQueueItem`/publish mutation hooks are called with the same shapes as today, just gated by client-side validation first.
- **A.2 SSE/realtime, polling fallback, F4/F6:** no file in `app/events/`, `app/api/v1/queue_stream.py`, or the frontend's realtime hooks (`useQueueEventStream`, `useQueueRealtimeInvalidation`, `useQueuePollingFallback`, `QueueRealtimeStatusBadge`, `QueueRealtimePollingContext`) is touched by any task above. Task 2's regression test pass explicitly includes re-running the 11 realtime-adjacent test files to confirm this boundary holds in practice, not just on paper.
- **Phase B worker heartbeat / `/worker/health`:** not applicable — no Celery/worker file is touched.
- **Phase C' retry ownership (AliExpress/AI):** not applicable — no file in `app/aliexpress/`, `app/ai/`, or Celery task modules is touched.
- **`QueueStatus` semantics:** unchanged — Task 1's schema *validates against* the existing `QueueStatus`/`QUEUE_STATUSES` values, it does not add, remove, or reinterpret any status value. The scheduling dialog continues to set exactly `"scheduled"` or `"queued"`, exactly as today.
- **Backend API contracts:** unchanged — no Pydantic schema, router, or service file is modified by any task. `PATCH /products/{id}` and `PATCH /queues/{id}` continue to receive exactly the payload shapes they receive today (§5 — the frontend request types are preserved, not widened).

---

### 16. Test Strategy

**Frontend (all new tests use the existing Vitest + `@testing-library/react` + `jsdom` setup already configured in `vitest.config.ts` — no new test infrastructure needed):**

| Area | Test file (new) | Coverage |
| --- | --- | --- |
| Zod schema unit tests | `features/queue/lib/schemas.test.ts`, `features/products/lib/schemas.test.ts` | Valid/invalid payloads per §13 Task 1/3 |
| Form validation (component) | `features/queue/components/QueueSchedulingDialog.test.tsx` | Field-level errors, preset interaction, Apply/Publish-Now gating |
| Arabic error-message tests | `lib/validation-messages.test.ts` | Builder output strings |
| API mutation regression | Full existing suite (16 files), re-run, not rewritten | Confirms `useUpdateQueueItem`/`useUpdateProduct` call shapes unaffected |

**Backend:** no new backend tests — per this task's own instruction ("Do not modify backend behavior merely to create symmetry with frontend schemas"), and because §3's inspection found the backend already has correct, existing coverage of the two `model_validator` rules relevant here (`QueueUpdate.validate_scheduling` — verify at Task 6 time whether `tests/test_queue_publishing_service.py` or an equivalent already covers this; if a genuine backend test gap is found, it is a **pre-existing gap unrelated to this frontend milestone** and should be logged as a follow-up, not folded into this milestone's scope).

**Existing test patterns to reuse:** the exact `@testing-library/react` + `userEvent` pattern already used by `QueueRealtimeStatusBadge.test.tsx`/`QueueToolbar.f6.test.tsx` for component tests; no mock server is needed for the Zod unit tests (pure functions); component tests for `QueueSchedulingDialog` can render it directly with mock props/`onSubmit` spies, consistent with how other Queue component tests already avoid hitting real network calls (TanStack Query mutations are typically mocked or the component is tested at the "calls this callback with these values" boundary, matching the proposed `defaultValues`/validated-payload-callback design in §10).

**Can tests run without external services?** Yes — all proposed new tests are pure unit/component tests with no database, Redis, or network dependency, consistent with the existing frontend suite's own pattern (none of the 16 existing files require a running backend).

---

### 17. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Migrating `QueueSchedulingDialog` to RHF subtly changes the Apply/Publish-Now button-disabled timing (e.g. `formState.isValid` updates asynchronously on first render, unlike the current synchronous boolean check) | Task 2's acceptance criteria explicitly require manual parity verification against the current disabled-state behavior, plus dedicated tests for the enabled/disabled transition, not just the error-message content |
| Extracting `ProductStatus` labels into a shared file (Task 3) accidentally changes a label's exact wording during the copy | Task 3's acceptance criteria require the three consuming components to render byte-identical labels before/after; a snapshot-style render check is recommended specifically to catch this |
| RHF's internal re-render behavior interacts unexpectedly with `QueueView`'s existing `schedulingDialog` state closure (e.g. stale `itemIds` if `defaultValues` isn't correctly re-derived on dialog reopen for a different selection) | Task 2 must explicitly test reopening the dialog for a second, different selection without a full unmount, verifying `reset(defaultValues)` fires correctly — this exact class of bug (stale closure state across dialog reopens) is a known general risk pattern for controlled→RHF migrations and is called out here specifically so Task 2's implementer tests for it deliberately |
| Scope creep — building new UI for "product status in the drawer" or "channel reassignment" because the roadmap's wording implies it | §1's explicit scope corrections, restated in Tasks 3/4's "out of scope" sections, are the mitigation — this design document itself is the guardrail |
| The optional Task 5 helper becomes unused boilerplate if Tasks 1/3's authors just write inline strings anyway | Task 5 is explicitly marked "optional, low-risk" (§13) — if it is skipped, Tasks 1/3 simply keep fully inline Arabic strings exactly as `LoginForm`/`ChannelsView` already do today, which is also an acceptable, already-proven outcome, not a fallback failure |

---

### 18. Open Questions / Unknowns

```text
1. Should Task 6 also formally re-verify whether an existing backend test
   (e.g. within tests/test_queue_publishing_service.py or a schema-level
   test file) already covers QueueUpdate.validate_scheduling? This document
   did not exhaustively enumerate every one of the 35 backend test files to
   confirm line-by-line coverage of that specific validator. Not blocking —
   Task 6 explicitly includes running the full backend suite, and this
   document already establishes that no backend behavior change is planned
   regardless of the answer.

2. Backend/API error messages remain in English while the UI is Arabic-first
   (§1, §11). This is explicitly out of this milestone's charter (translating
   them would require backend changes or a speculative dictionary), but it is
   a real, user-visible inconsistency. Recommend logging it as a named,
   separate future consideration (not a Phase D+1 candidate list item today —
   simply an acknowledged, deliberately deferred gap) rather than silently
   dropping it.

3. Whether frontend/e2e/smoke.spec.ts (Playwright) currently exercises the
   scheduling dialog at all. Not verified in this analysis (out of the
   required inspection list's explicit file set); Task 6 should check this
   directly before claiming full regression coverage.
```

None of these block Task 0's completion or the start of Task 1/3/5 — all three are scoped narrowly to later-task verification steps.

---

### 19. Final Recommendation

**Start with Task 5 (Arabic message helper, optional but cheap) and Task 1 (queue scheduling schema) together**, since Task 1 is the schema underpinning the milestone's one genuine validation gap (§7) and has no dependency on anything else. **Task 3 (product status consolidation) can run fully in parallel** — different feature folder, zero shared files. **Task 2 (RHF migration) follows Task 1 directly.** **Task 4 is a lightweight confirmation gate after Task 2**, not independent implementation work. **Tasks 6 and 7 close the milestone**, in that order, exactly matching this project's established closeout convention from every prior phase (A.1, A.2, B, C').

The single most important framing correction this analysis makes: **this is a small, low-risk, mostly-additive milestone**, not a new-architecture-introduction milestone — because the architecture (RHF + Zod + `zodResolver`, forwarded-ref primitives) was already built and proven twice before this task began. The work here is extension and consolidation, not invention.

---

### Related Documents

- [phase-d-analysis-and-roadmap.md](./phase-d-analysis-and-roadmap.md) — prior milestone analysis (independent, no file overlap, §15)
- [phase-d-auth-security-design.md](./phase-d-auth-security-design.md) — prior milestone design (independent, no file overlap, §15)
- [../08-implementation-roadmap.md](../08-implementation-roadmap.md) — this milestone's charter (§3)
- [../02-frontend-architecture.md](../02-frontend-architecture.md), [../07-development-guidelines.md](../07-development-guidelines.md) §4, §4.3 — existing frontend conventions this design extends
- [../frontend/11-workspace-design-system.md](../frontend/11-workspace-design-system.md) §5 — component/schema extraction rules applied in §9
