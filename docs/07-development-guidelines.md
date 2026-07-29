# Development Guidelines

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

---

# 1. Purpose

This document defines the development standards and coding practices for the frontend application.

The goal is to maintain:

* High code quality.
* Consistent architecture.
* Easy maintenance.
* Predictable development workflow.
* Effective collaboration between developers and AI coding assistants.

These guidelines apply to all frontend development activities.

---

# 2. General Development Principles

## 2.1 Quality Over Speed

The goal is not only to implement features quickly.

Every implementation should consider:

* Maintainability.
* Readability.
* Scalability.
* Reusability.

Short-term shortcuts that create long-term technical debt should be avoided.

---

## 2.2 Simplicity First

Prefer simple solutions.

Avoid:

* Over-engineering.
* Complex abstractions without need.
* Premature optimization.

A feature should start simple and evolve when requirements become clear.

---

## 2.3 Consistency Matters

Existing patterns should always be preferred over creating new approaches.

Before adding new code:

Ask:

* Does a similar solution already exist?
* Can an existing component be reused?
* Does this follow the architecture rules?

---

# 3. Drawer & Overlay Guidelines

Workspace detail flows use the shared `Drawer` primitive — do not create parallel slide-over implementations.

Rules:

- Row click opens drawer; action buttons/checkboxes call `stopPropagation`
- Drawer receives entity from list query when possible; refetch single resource only when stale
- Destructive actions use `ConfirmDialog`, not drawer footers alone
- One drawer open at a time per workspace view
- Score detail uses `Popover` (`ProductAiScoreCell`), not a drawer

Scheduling and delete flows use centered dialogs (`QueueSchedulingDialog`, `DeleteProductsDialog`).

---

# 4. Form & Schema Validation

Inline edits in drawers and filter panels must use Zod schemas colocated with the feature:

- Discovery: `validateDiscoveryDraft` in `DiscoveryFilterPanel`
- Queue schedule: validate `scheduled_at` + `channel_id` before `PATCH /queues/{id}`
- AI generation: build payload via `useContentSession.buildGeneratePayload()` — enums must match `app/schemas/ai_content.py`

Synchronize frontend unions in `features/*/types/api.ts` when backend enums change.

Use React Hook Form for multi-field forms; Zod `.safeParse` for toolbar/filter drafts.

---

# 5. AI Agent Guardrails (Cursor)

AI coding assistants must:

1. Read `/docs` before generating code — especially `06-api-integration.md`
2. Extend existing feature components; never recreate deleted views (e.g., `AIStudioView` → `ContentWorkspaceView`)
3. Not install libraries (`sonner`, shadcn, Zustand) without explicit approval
4. Not claim features are connected unless the API module + hook exist
5. Keep Arabic RTL labels on user-facing controls
6. Use `ToastOverlay` for transient success/error — do not add duplicate toast libraries
7. Match backend queue/product status strings exactly — no invented `failed` queue status

---

# 6. AI-Assisted Development Guidelines

Because Cursor is part of the development workflow, the project must remain AI-friendly.

---

## 3.1 Give Small Focused Tasks

Avoid prompts like:

```
Build the entire dashboard
```

Prefer:

```
Create a reusable StatCard component following the design system.
```

Small tasks produce:

* Better code quality.
* Easier review.
* Fewer architectural mistakes.

---

## 3.2 Review All Generated Code

AI-generated code must always be reviewed.

Check:

* Folder location.
* Naming.
* Reusability.
* Types.
* Performance.
* Security.

Generated code is considered a first draft, not final code.

---

## 3.3 Do Not Allow Architecture Drift

Cursor should not introduce:

* New libraries without approval.
* Different folder structures.
* Alternative state management.
* Duplicate components.

The architecture documents are the source of truth.

---

# 4. TypeScript Guidelines

TypeScript should be used strictly.

---

## 4.1 Avoid Any

Forbidden:

```typescript
const data: any
```

Prefer:

```typescript
const data: Product
```

or:

```typescript
unknown
```

with proper validation.

---

## 4.2 Define Explicit Types

All important data structures require types.

Example:

```typescript
interface Product {
    id: string;
    title: string;
    score: number;
}
```

---

## 4.3 Current Type Organization

Feature API contracts currently live in `features/[feature]/types/api.ts`. Views use those
contracts directly, with small local form/view types where needed. Introduce a separate
`models.ts` only when a real UI-domain mapping is required; do not create parallel types
preemptively.

---

# 5. Component Guidelines

## 5.1 Component Size

Components should remain focused.

Avoid components larger than necessary.

If a component becomes difficult to understand:

Consider splitting it.

---

## 5.2 Component Responsibilities

A component should:

* Render UI.
* Handle user interaction.
* Receive data through props.

A component should not:

* Call APIs directly.
* Manage unrelated state.
* Contain business logic.

---

## 5.3 Props Guidelines

Prefer explicit props.

Good:

```typescript
<ProductCard
    product={product}
    onPublish={handlePublish}
/>
```

Avoid:

```typescript
<ProductCard {...everything}/>
```

---

## 5.4 Component Naming

Components use PascalCase.

Examples:

```
ProductCard.tsx

QueueTable.tsx

AIEditor.tsx
```

---

# 6. Hooks Guidelines

Hooks contain reusable logic.

Location:

```
features/[feature]/hooks/
```

---

## 6.1 Custom Hooks Naming

All hooks start with:

```
use
```

Examples:

```
useProducts()

useQueue()

useGenerateContent()
```

---

## 6.2 Hooks Responsibilities

Good:

```
useProducts()

- Fetch products
- Manage query
- Return data
```

Bad:

```
useProducts()

- Fetch products
- Format UI
- Render components
- Control dialogs
```

---

# 7. State Management Rules

## 7.1 Server State

Use:

```
TanStack Query
```

For:

* API data.
* Caching.
* Synchronization.

---

## 7.2 Client State

Use React state for local UI.

Examples:

```
Modal open state

Selected tab

Sidebar state
```

---

## 7.3 Avoid Global State

Do not introduce global state unless necessary.

Before using Zustand or another library:

Confirm that React state or TanStack Query cannot solve the problem.

---

# 8. API Development Rules

## 8.1 No API Calls in Components

Forbidden:

```typescript
axios.get()
```

inside components.

This is a current invariant: components call feature hooks, hooks call feature API modules,
and API modules use `services/api-client.ts`. The categories feature follows the same
pattern for both categories and platform readiness.

---

Correct:

```
Component

↓

Hook

↓

API Function

↓

Backend
```

---

## 8.2 API Naming

Use clear action names.

Examples:

```
getProducts()

createProduct()

updateProduct()

deleteProduct()

generateContent()
```

---

# 9. Styling Guidelines

## 9.1 Use TailwindCSS

Preferred:

```tsx
<div className="flex gap-4">
```

Avoid unnecessary CSS files.

---

## 9.2 Use Design Tokens

Do not hardcode colors.

Avoid:

```css
color: #000000;
```

Prefer:

```css
text-foreground
```

---

## 9.3 Responsive Design

Every component should consider:

* Desktop.
* Tablet.
* Mobile.

---

# 10. File Organization Rules

## Components

```
ComponentName.tsx
```

---

## Hooks

```
useFeatureName.ts
```

---

## API Files

```
feature.api.ts
```

---

## Types

```
types.ts
```

---

## Utilities

```
feature.utils.ts
```

---

# 11. Naming Conventions

## Variables

camelCase:

```typescript
productList
queueItems
```

---

## Constants

UPPER_CASE:

```typescript
MAX_PRODUCTS
DEFAULT_PAGE_SIZE
```

---

## Types

PascalCase:

```typescript
Product
QueueItem
Channel
```

---

# 12. Error Handling Rules

Every async operation must handle:

## Loading

Example:

```
Loading...
```

---

## Success

Provide feedback.

Example:

```
Product added successfully
```

---

## Failure

Provide:

* Clear message.
* Retry option when possible.

---

# 13. Forms Guidelines

Forms should use:

```
React Hook Form

+

Zod
```

---

Every form should include:

* Validation.
* Loading state.
* Error display.
* Success feedback.

---

# 14. Performance Guidelines

Avoid:

* Unnecessary re-renders.
* Large client components.
* Loading everything at startup.

Prefer:

* Server Components.
* Lazy loading.
* Query caching.
* Component splitting.

---

# 15. Accessibility Guidelines

All components should support:

* Keyboard navigation.
* Proper labels.
* Focus states.
* Screen readers.

---

Examples:

Buttons:

```html
<button aria-label="">
```

Images:

```html
<img alt="">
```

---

# 16. Git Workflow Guidelines

## Branch Naming

Examples:

```
feature/products-page

feature/authentication

fix/table-loading
```

---

## Commit Messages

Use clear messages.

Examples:

Good:

```
feat: add product table component

fix: handle API error state
```

Avoid:

```
update stuff
changes
```

---

# 17. Code Review Checklist

Before considering a feature complete:

## Architecture

* Is the correct folder used?
* Does it follow existing patterns?

---

## Components

* Are components reusable?
* Are responsibilities clear?

---

## Types

* No unnecessary any.
* Types are defined.

---

## UX

* Loading handled.
* Errors handled.
* Empty states handled.

---

## Design

* Matches design system.
* Supports dark mode.
* Supports RTL.

---

# 18. Testing Guidelines

Current automated coverage includes backend pytest contract/endpoint tests and frontend
Vitest tests for local UI primitives. The Playwright smoke test exists for local/manual
execution but is not part of CI. Expand hook, feature-view, and critical-flow coverage as
the implementation matures.

Priority:

## Unit Testing

For:

* Utilities.
* Hooks.
* Complex logic.

---

## Component Testing

For:

* Important reusable components.

---

## End-to-End Testing

For:

* Critical user flows.

Examples:

```
Login

Import Product

Generate Content

Publish Product
```

Run with `npm run test:e2e` in a prepared environment. Do not describe Playwright as a CI
gate until the workflow actually runs it.

---

# 19. Documentation Rules

Every major feature should include:

* Purpose.
* Architecture decisions.
* API requirements.
* Known limitations.

Documentation location:

```
/docs
```

Use `docs/06-api-integration.md` as the frontend/backend contract and
`docs/10-production-readiness.md` as the release and operational gate. Update both when a
contract or deployment assumption changes.

Prettier is installed as a development dependency, but there is currently no
`format`/`prettier` npm script. Do not document formatting as an automated gate until a
script and workflow step exist.

---

# 20. Development Philosophy Summary

The frontend follows:

```
Clean Architecture

+

Feature-Based Organization

+

Type Safety

+

Reusable Components

+

API Separation

+

AI-Assisted Development

+

Continuous Improvement
```

The goal is to build a frontend that remains understandable and maintainable as the platform evolves from a personal automation tool into a scalable SaaS product.
