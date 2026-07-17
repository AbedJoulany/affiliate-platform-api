# Implementation Roadmap v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-17

---

# 1. Purpose

This document defines the implementation roadmap for building the frontend application.

The roadmap translates the architecture documents into actionable development phases.

The goal is to build the frontend incrementally while maintaining:

* Clean architecture.
* Consistent design.
* High code quality.
* Fast iteration.
* AI-assisted development efficiency.

---

# 2. Development Strategy

The frontend will be developed in incremental phases.

Each phase should produce a usable improvement to the product.

The implementation order follows:

```text
Foundation

↓

Design System

↓

Application Shell

↓

Authentication

↓

Core Features

↓

Automation Features

↓

Advanced Features
```

---

# 3. MVP Scope

The first version focuses on creating a usable affiliate automation workspace.

MVP includes:

```text
Authentication

Application Layout

Dashboard

Products Management

Product Discovery

AI Content Generation

Publishing Queue

Telegram Channels

Read-only Settings Status
```

## Current implementation status — 2026-07-17

The frontend foundation, application shell, login/session protection, dashboard, products,
discovery, AI generation, queue, channels, profile, settings route set, and shared
loading/empty/error states are implemented at MVP depth.

Still partial or future: a shared `DataTable` and richer UI primitives, registration UI,
admin provisioning tooling, full discovery controls, AI prompt profiles/history, queue
scheduling/editing, explicit channel connection testing/deletion, editable settings APIs,
broader tests/accessibility polish, and analytics. Settings currently display read-only
capability/status information; they do not configure the system.

---

# 4. Deferred Features

The following features are intentionally postponed.

## Advanced Analytics

Includes:

* Future route: `/analytics`.
* Revenue tracking.
* Conversion analytics.
* Click attribution.
* Performance reports.

---

## Multi Workspace

Includes:

* Organizations.
* Teams.
* Workspace switching.
* Roles.

---

## Additional Publishing Platforms

Future:

* Facebook.
* Instagram.
* WhatsApp.

---

## Advanced Automation

Includes:

* Workflow builder.
* Conditional rules.
* Automation templates.

---

## Competitor Analysis

Includes:

* Product monitoring.
* Market intelligence.
* Trend tracking.

---

# 5. Phase 0 — Project Foundation

**Status: Done for the MVP foundation; tooling partial.** The app, environment pattern,
aliases, theme provider, RTL root, and feature structure exist. Prettier script/CI
integration remains future.

## Goal

Create a clean and scalable Next.js project foundation.

---

## Tasks

Initialize:

```text
Next.js 15

TypeScript

TailwindCSS

Local Tailwind UI primitives (shadcn/ui is a future option)

ESLint

Prettier dependency (script/CI integration future)
```

Current result: Next.js 15.5.x, React 19, Tailwind 3.4, TypeScript, ESLint, TanStack Query 5,
Axios, React Hook Form/Zod, Lucide, and next-themes are installed. The UI uses local
Tailwind primitives; shadcn/ui is not installed. Prettier is installed but has no npm
format script or CI step.

---

Configure:

* Project structure.
* Environment variables.
* Path aliases.
* Theme provider.
* RTL support.

---

Create:

```text
src/

app/

components/

features/

services/

lib/
```

Current hooks and API types live inside feature folders; utilities live in `lib/utils.ts`.

---

## Deliverables

Completed:

* Running Next.js application.
* Clean folder structure.
* Development environment ready.

---

# 6. Phase 1 — Design System Foundation

**Status: Partial.** Button, Input, Select, Textarea, Card, Badge, Skeleton, and shared
loading/empty/error states exist. Dialog, dropdown, toast, shared DataTable/SearchBar/
FilterPanel, and richer accessible primitives remain planned.

## Goal

Create reusable UI foundations before building pages.

---

## Tasks

Implement:

## UI Components

```text
Button

Input

Select

Card

Badge

Dialog

Dropdown

Toast
```

---

## Layout Components

```text
AppShell

Sidebar

Header

PageContainer

PageHeader
```

---

## Common Components

```text
DataTable (planned extraction)

SearchBar

FilterPanel

EmptyState

LoadingState

ErrorState
```

---

## Deliverables

A reusable component library matching:

* Design System.
* Dark mode.
* RTL.
* Accessibility rules.

---

# 7. Phase 2 — Application Shell

**Status: Done at MVP depth.** `AppShell.tsx` combines the sidebar, header, responsive
drawer, navigation, theme toggle, user menu, and content frame.

## Goal

Create the main application workspace.

---

## Tasks

Build:

```text
Sidebar

Header

Navigation

User Menu

Theme Toggle

Main Content Layout
```

---

Implement:

* Responsive behavior.
* Desktop layout.
* Mobile navigation drawer.
* Profile access through the header user menu.
* Keep the workspace selector hidden until multi-workspace support is implemented.

---

## Deliverables

A complete application frame where all pages can be displayed.

---

# 8. Phase 3 — Authentication

**Status: Done at MVP depth.** Login, logout, middleware redirect, access-JWT
`sessionStorage`, presence-only cookie, `/auth/me` validation, and `401` clearing are
implemented. There is no auth provider/context and no refresh token. Registration UI and
operational admin-provisioning tooling remain future.

## Goal

Connect frontend authentication with backend.

---

## Tasks

Implement:

```text
Login Page

Protected Routes

Session Handling

Logout
```

---

Integrate:

* JWT authentication.
* API client.
* Error handling.

---

## Deliverables

Users can:

* Login.
* Access protected pages.
* Logout.

---

# 9. Phase 4 — Dashboard

**Status: Done at MVP depth.** The real `GET /dashboard` contract powers product/queue/
published/active-channel counts, recent product/queue activity, and database status.

## Goal

Create the main workspace overview.

---

## Components

Implement:

```text
StatCard

ActivityFeed

QuickActionCard

SystemStatus
```

---

## Dashboard Sections

```text
Products Overview

Queue Status

Publishing Status

Recent Activity

Quick Actions
```

---

## Deliverables

A functional dashboard connected to backend data.

---

# 10. Phase 5 — Products Module

**Status: Done at MVP depth.** List, title/status filters, pagination, and details are
implemented using a feature-local table. A shared DataTable and frontend admin CRUD
controls remain future.

## Goal

Build the main product management workspace.

---

## Pages

```text
/products

/products/[id]
```

---

## Features

Implement:

```text
Feature-local product table (shared DataTable is future)

Search

Filters

Pagination

Product Details

Open product in AI Studio
```

Admin-only import is implemented in the Discovery phase. Frontend product CRUD actions
remain future work.

---

## Components

```text
ProductCard

ProductTable

ProductFilters

ProductPreview
```

---

## Deliverables

Users can:

* View products.
* Search.
* Filter.
* Open product details.
* Open a product in AI Studio.

---

# 11. Phase 6 — Discovery Module

**Status: Partial.** General/hot/deals/trending/category modes, selected filters,
categories, results, and admin import are implemented. The complete backend filter set,
image search, persistence/paging controls, and automation monitoring remain future.

## Goal

Create product discovery workspace.

---

## Features

Implement:

```text
Discovery Sources

Search

Filters

Discovery Results

Import Actions
```

---

Future-ready for:

* Automatic discovery.
* Trend detection.
* Scoring engine.

---

## Deliverables

Users can discover and import products.

---

# 12. Phase 7 — AI Studio

**Status: Partial.** Provider selection, generation by product ID or URL, local editing,
copy, and draft creation are implemented. Prompt profiles, saved history, persistence, and
dedicated regenerate/save workflows remain future.

## Goal

Create AI content generation workspace.

---

## Features

Implement:

```text
Content Generator

Prompt Profiles

Content Editor

Regenerate

Save

Queue
```

---

## Components

```text
AIContentEditor

PromptProfileSelector (future)

GenerationStatus
```

---

## Deliverables

Users can:

* Generate marketing content.
* Edit content.
* Prepare content for publishing.

---

# 13. Phase 8 — Publishing Queue

**Status: Partial.** List, status filter, and publish-now are implemented. AI Studio can
create drafts. Editing, deleting, retry orchestration, and scheduling controls remain
future even though the API accepts scheduled records.

## Goal

Manage content lifecycle.

---

## Pages

```text
/queue
```

---

## Features

Implement:

```text
draft

queued

scheduled

published

Publish Now
```

The lowercase status values must match the backend `QueueStatus` enum exactly. Publishing
failures are operation errors, not a `failed` queue status. Dedicated retry controls and
retry orchestration remain future work.

---

## Deliverables

Users can manage publishing workflow.

---

# 14. Phase 9 — Channels Management

**Status: Partial.** List, add, permission display, and active-state toggle are implemented.
Delete, a richer connection-test action, and additional platforms remain future.

## Goal

Manage publishing destinations.

---

## Features

Implement:

```text
Channel List

Add Channel

Connection Test (future)

Channel Settings (future)
```

---

Initial support:

```text
Telegram
```

Future:

```text
Facebook

Instagram

WhatsApp
```

---

# 15. Phase 10 — Settings

**Status: Partial/read-only.** All routes exist and render capability/status screens.
There are no editable settings APIs, forms, or persistence.

## Goal

Provide application configuration.

---

## Sections

```text
/settings/general

/settings/aliexpress

/settings/ai

/settings/telegram

/settings/discovery

/settings/scheduling
```

`/settings` is the parent route and should redirect to or render `/settings/general` by default.

---

## Deliverables

Users can inspect documented capability details and database/Redis readiness. Editable
configuration is a future deliverable.

---

# 16. Phase 11 — Polish & Optimization

**Status: Ongoing.**

## Goal

Improve quality before release.

---

## Tasks

Improve:

* Loading states.
* Empty states.
* Error handling.
* Animations.
* Responsive behavior.
* Accessibility.

---

Review:

* Component reuse.
* Code quality.
* Performance.

---

# 17. Cursor Development Workflow

Every implementation task follows:

```text
Documentation

↓

Task Definition

↓

Cursor Prompt

↓

Generated Code

↓

Manual Review

↓

Refactor

↓

Commit
```

---

# 18. Cursor Prompt Rules

Prompts should:

Include:

* Feature name.
* File location.
* Required components.
* Design requirements.
* Architecture rules.

Example:

Good:

```text
Create ProductTable component inside
features/products/components.

Inspect the current feature-local table first. Extract or extend a shared DataTable only
when the task explicitly includes that planned refactor.
Follow Design System.
Support loading and empty states.
Use TypeScript.
```

---

Avoid:

```text
Build products page.
```

---

# 19. Definition of Done

A feature is complete only when:

## Architecture

✓ Correct folder structure
✓ Reusable components
✓ No duplicated logic

---

## UX

✓ Loading state
✓ Empty state
✓ Error handling
✓ Responsive design

---

## Quality

✓ TypeScript errors resolved
✓ Code reviewed
✓ Design system followed

---

# 20. Future Version Roadmap

## V2 — SaaS Platform

Potential additions:

```text
Multi Workspace

Team Collaboration

Roles & Permissions

Multiple Affiliate Networks

Advanced Analytics

Workflow Automation

Competitor Intelligence

Subscription System
```

---

# Implementation Philosophy

The frontend will be built as a product, not a collection of pages.

The priorities are:

```text
Quality

+

Consistency

+

Scalability

+

Maintainability

+

Fast Iteration
```

The final goal is a professional SaaS-ready application that can evolve from a personal affiliate automation tool into a commercial platform.
