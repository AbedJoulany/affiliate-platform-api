# Component Library v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-17

---

# 1. Purpose

The Component Library defines the reusable UI components used throughout the AI Affiliate Automation Platform.

The purpose of this library is to:

* Maintain visual consistency.
* Reduce duplicated code.
* Improve development speed.
* Provide predictable UI patterns.
* Support AI-assisted development with Cursor.
* Enable future scalability.

All components should follow the Design System rules defined in:

```
docs/03-design-system.md
```

---

# 2. Component Architecture

## Status labels

* **Implemented MVP** — exists in the repository and is used by current screens.
* **Planned extraction** — behavior exists inside a feature or combined component but has
  not been extracted into the documented shared component.
* **Future** — target capability with no current implementation.

The current UI is a local Tailwind primitive module, not installed shadcn/ui.

The application separates components into three categories:

```
components/

├── ui/
│
├── layout/
│
└── common/
```

Feature-specific components are stored inside their feature folders:

```
features/

products/
    components/

queue/
    components/

ai/
    components/
```

---

# 3. Component Rules

All components should follow these principles:

## Single Responsibility

A component should have one clear purpose.

Bad:

```
ProductPage
- Fetch data
- Manage filters
- Generate AI
- Render table
- Handle dialogs
```

Good:

```
ProductPage

├── ProductTable
├── ProductFilters
├── ProductActions
└── ProductDetails
```

---

## Reusability

Before creating a new component, check:

* Does this already exist?
* Can an existing component be extended?
* Is this specific to one feature?

---

## Composition

Prefer combining small components.

Example:

```
PageHeader

+
Button

+
Dropdown

+
Search
```

Instead of creating:

```
ProductPageHeaderWithActionsAndSearch
```

---

# 4. UI Components

Location:

```
components/ui
```

These components are application-independent.

They should not contain business logic.

**Implemented MVP:** `Button`, `Input`, `Select`, `Textarea`, `Card`, `Badge`, and `Skeleton`
are exported together from `components/ui/primitives.tsx`.

**Future:** Checkbox, Switch, Avatar, Dialog, Drawer, Dropdown Menu, Tooltip, and Toast are
design targets below; they do not currently exist as shared components.

---

# 4.1 Button

## Purpose

Primary interaction element.

## Variants

```
Primary

Secondary

Outline

Ghost

Danger
```

## Supports

* Loading state.
* Disabled state.
* Size variations.

Icons are composed as children. There is no dedicated link variant; use Next.js `Link`
with an appropriate button/action style.

Example:

```
Generate Content
```

```
Publish Product
```

---

# 4.2 Input

## Purpose

Standard text input.

Supports:

* Label.
* Description.
* Error message.
* Icon.
* Disabled state.

Used in:

* Search.
* Forms.
* Settings.

---

# 4.3 Select

## Purpose

Selection from predefined options.

Examples:

```
Category

Language

Status

AI Provider
```

---

# 4.4 Textarea

Used for:

* AI generated content.
* Descriptions.
* Prompts.

Supports:

* Character count.
* Resize.
* Validation.

---

# 4.5 Checkbox

Used for:

* Filters.
* Bulk selection.
* Settings.

---

# 4.6 Switch

Used for:

Boolean settings:

Examples:

```
Enable Auto Publish

Enable AI Generation
```

---

# 4.7 Badge

## Purpose

Display small status indicators.

Examples:

```
Draft

Active

Scheduled

Connected
```

Use exact backend product/queue enum values for status badges. `Failed` may describe an
operation alert, but it is not a queue status.

Variants:

```
Success

Warning

Error

Neutral

Info
```

---

# 4.8 Avatar

Used for:

* User profile.
* Workspace members.

Supports:

* Image.
* Initials.
* Fallback.

---

# 4.9 Card

Base container component.

Used by:

* Dashboard.
* Product information.
* Settings sections.

Variants:

```
Default

Interactive

Highlighted
```

---

# 4.10 Dialog

Used for:

* Confirmations.
* Important actions.

Examples:

```
Delete Product?

Publish Now?
```

Should support:

* Title.
* Description.
* Actions.

---

# 4.11 Drawer

Used for:

Side panels.

Examples:

```
Product Preview

Filters

Details
```

---

# 4.12 Dropdown Menu

Used for:

* Row actions.
* User menu.
* Context actions.

---

# 4.13 Tooltip

Used for:

* Icon explanations.
* Additional information.

---

# 4.14 Toast

Used for:

Temporary notifications.

Examples:

Success:

```
Product added to queue
```

Error:

```
Publishing failed
```

---

# 5. Layout Components

Location:

```
components/layout
```

---

# 5.1 AppShell

**Implemented MVP (combined component).**

## Purpose

Main application container.

Structure:

```
AppShell

├── Sidebar

├── Header

└── Main Content
```

Responsibilities:

* Global layout.
* Responsive behavior.
* Theme integration.
* Current sidebar, header, mobile drawer, navigation, theme toggle, and user menu.

Does not:

* Fetch data.
* Handle business logic.

---

# 5.2 Sidebar

**Planned extraction:** currently implemented inside `AppShell.tsx`.

## Purpose

Main navigation.

Contains:

* Logo.
* Navigation items.
* Collapse button.

Navigation:

```
Dashboard

Products

Discovery

AI Studio

Queue

Channels

Settings
```

Analytics is deferred and is not shown in the MVP sidebar. Profile is accessed from the header user menu rather than the sidebar. The workspace selector remains hidden until multi-workspace support is implemented.

Supports:

* Expanded mode.
* Collapsed mode.
* Mobile drawer.

---

# 5.3 Header

**Planned extraction:** currently implemented inside `AppShell.tsx`.

Current header contains:

* Mobile navigation trigger.
* Page context.
* Theme toggle.
* User menu.

Global search and notifications are future header capabilities.

---

# 5.4 PageContainer

**Implemented MVP** in `components/layout/page.tsx`.

Standard page wrapper.

Responsible for:

* Width.
* Padding.
* Responsive spacing.

---

# 5.5 PageHeader

**Implemented MVP** in `components/layout/page.tsx`.

Used on every page.

Contains:

```
Title

Description

Actions
```

Example:

```
Products

Manage discovered affiliate products

[Status Filter]
```

The current Products page uses the action slot for filtering. Product import is an
admin-only action on the Discovery page.

---

# 6. Common Components

Location:

```
components/common
```

These are reusable application patterns.

---

# 6.1 DataTable

**Planned extraction / future shared component.**

One of the most important components.

Used for:

* Products.
* Queue.
* Channels.
* Logs.

Supports:

* Columns.
* Sorting.
* Filtering.
* Pagination.
* Selection.
* Row actions.
* Loading.
* Empty state.

Current product and queue screens use feature-local HTML tables. A future extraction should
consolidate repeated table behavior into `DataTable`; do not claim that current feature
tables already compose it.

Example `ProductTable` columns:

```
Product Table

Name

Price

Score

Status

Actions
```

---

# 6.2 SearchBar

Reusable search component.

Supports:

* Debounce.
* Clear action.
* Keyboard shortcuts.

---

# 6.3 FilterPanel

Used for advanced filtering.

Examples:

Products:

```
Category

Price

Rating

Sales

Score
```

---

# 6.4 EmptyState

**Implemented MVP** in `components/common/states.tsx`.

Every list page requires an empty state.

Contains:

* Icon.
* Title.
* Description.
* Action button.

Example:

```
No products discovered yet

Start discovery
```

---

# 6.5 LoadingState

**Implemented MVP** in `components/common/states.tsx` using `Skeleton`.

Reusable loading patterns:

```
Skeleton Card

Skeleton Table

Spinner

Progress Indicator
```

---

# 6.6 ErrorState

**Implemented MVP** in `components/common/states.tsx`.

Used when:

* API fails.
* Permission denied.
* Unexpected error.

Contains:

* Error message.
* Retry action.

---

# 6.7 ConfirmAction

Reusable confirmation pattern.

Examples:

```
Delete channel?

Remove product?
```

---

# 7. Dashboard Components

Location:

```
features/dashboard/components
```

**Implemented MVP:** `DashboardView` contains the current stat cards, quick-action cards,
recent activity, and database status. The named components below describe useful future
extractions rather than separate files.

---

# 7.1 StatCard

Used for metrics.

Examples:

```
Products Found

Queue Size

Published Queue Items

AI Usage
```

The first three examples map to current concepts; AI Usage is a future analytics card. The
current dashboard shows products total, queue total, published count, and active channels.
AI usage is not returned by the dashboard API.

Contains:

* Title.
* Value.
* Trend.
* Icon.

---

# 7.2 ActivityFeed

Displays recent activity.

Examples:

```
Product imported

Queue draft created

Post published
```

---

# 7.3 QuickActionCard

Used for common actions.

Examples:

```
Explore Products

Generate Content

Review Queue
```

---

# 7.4 SystemStatus

Summarizes the status data currently exposed to the dashboard.

Current behavior:

* `/dashboard` reports a database-up snapshot.
* `/ready` reports database and Redis readiness and is used by read-only settings views.

Celery worker health and external-provider status are not exposed by the current dashboard
contract; they remain operational monitoring targets.

---

# 8. Product Components

Location:

```
features/products/components
```

**Implemented MVP:** `ProductsView` and `ProductDetailView`. `ProductCard`,
`ProductFilters`, and `ProductPreview` below are possible future extractions.

---

# 8.1 ProductCard

Displays product summary.

Contains:

* Image.
* Title.
* Price.
* Rating.
* Score.
* Status.

Actions:

```
Generate AI

Queue

Publish
```

---

# 8.2 ProductPreview

Detailed product view.

Contains:

* Product information.
* Affiliate information.
* Generated content.
* Actions.

---

# 8.3 ProductFilters

Product-specific filtering.

---

# 9. AI Components

Location:

```
features/ai/components
```

---

# 9.1 AIContentEditor

**Implemented MVP within `AIStudioView`**, not as a separate component.

Main AI workspace.

Contains:

* Generated content.
* Editing.
* Copy.
* Add as a queue draft.

A user can submit the generation form again, but there is no dedicated Regenerate action.
Server-side Save and generation history are future workflows.

---

# 9.2 PromptProfileSelector

**Future.** Prompt profiles and generation history are not implemented by the current API
or frontend.

Selects AI writing style.

Examples:

```
Standard

Technology

Luxury

Urgency

Short

Long
```

---

# 9.3 GenerationStatus

**Planned extraction.** Current pending/error feedback is rendered inside `AIStudioView`.

Shows:

```
Generating...

Completed

Failed
```

---

# 10. Queue Components

Location:

```
features/queue/components
```

---

# 10.1 QueueTable

**Implemented MVP within `QueueView`**, not as a shared component.

Displays queue items using the canonical backend statuses:

```text
draft
queued
scheduled
published
```

Publishing failures are displayed as operation feedback, not as a `failed` queue status.
Users may invoke Publish Now again; a dedicated retry action and retry orchestration are future.

Current feature-local table columns:

```
Content

Schedule

Status

Action
```

Product and channel columns are planned for the extracted `QueueTable`.

---

# 10.2 SchedulePicker

**Future.** The API accepts `scheduled_at`, but the current queue UI does not create or edit
scheduled items.

Used for:

* Date.
* Time.
* Timezone.

---

# 11. Channel Components

Location:

```
features/channels/components
```

---

# 11.1 ChannelCard

**Implemented MVP within `ChannelsView`**, not as a separate component.

Displays:

* Channel name.
* Platform.
* Status.
* Connection state.

---

# 11.2 ConnectionStatus

**Implemented MVP as channel permission badges.** A richer explicit connection-test action
is future work.

Shows:

```
Connected

Disconnected

Error
```

---

# 12. Component Development Checklist

## Current settings component

`features/settings/components/CapabilityView.tsx` is **Implemented MVP**. It presents
read-only configuration/capability details and the `/ready` database/Redis result. It does
not edit settings and must not imply that provider credentials or Celery worker health were
checked.

Before creating a component:

Check:

* Is it reusable?
* Does it belong in ui/common/feature?
* Does it follow the Design System?
* Does it support loading?
* Does it support errors?
* Does it work in RTL?
* Does it support dark mode?

---

# 13. Future Components

Potential future additions:

```
WorkspaceSwitcher

CommandPalette

NotificationCenter

AnalyticsChart

WorkflowBuilder

AutomationNode

AIChatAssistant

CompetitorCard
```

`WorkspaceSwitcher` must remain unrendered until multi-workspace support is available.

---

# Component Library Summary

The component architecture follows:

```
Reusable UI Components

+

Application Layout Components

+

Feature Components

+

Composition Pattern

+

AI-Friendly Structure
```

The goal is to create a consistent and scalable component ecosystem that allows the platform to grow from a personal automation tool into a full SaaS product.
