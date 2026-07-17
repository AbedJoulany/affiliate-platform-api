# Component Library v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-16

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

Link
```

## Supports

* Loading state.
* Disabled state.
* Icon.
* Size variations.

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
Published

Draft

Failed

Connected
```

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

Does not:

* Fetch data.
* Handle business logic.

---

# 5.2 Sidebar

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

Contains:

* Search.
* Notifications.
* Theme toggle.
* User menu.

---

# 5.4 PageContainer

Standard page wrapper.

Responsible for:

* Width.
* Padding.
* Responsive spacing.

---

# 5.5 PageHeader

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

[Import Product]
```

---

# 6. Common Components

Location:

```
components/common
```

These are reusable application patterns.

---

# 6.1 DataTable

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

Feature tables should compose `DataTable` rather than duplicate its behavior. For example, `ProductTable` is the products-specific wrapper around `DataTable`.

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

Reusable loading patterns:

```
Skeleton Card

Skeleton Table

Spinner

Progress Indicator
```

---

# 6.6 ErrorState

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

---

# 7.1 StatCard

Used for metrics.

Examples:

```
Products Found

Queue Size

Published Today

AI Usage
```

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

AI content generated

Post published
```

---

# 7.3 QuickActionCard

Used for common actions.

Examples:

```
Import Product

Run Discovery

Generate Content
```

---

# 7.4 SystemStatus

Summarizes the health and availability of backend services used by the dashboard.

Shows:

* API availability.
* Worker availability.
* External service connection status where exposed by the backend.

---

# 8. Product Components

Location:

```
features/products/components
```

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

Main AI workspace.

Contains:

* Generated content.
* Editing.
* Regenerate.
* Copy.
* Save.

---

# 9.2 PromptProfileSelector

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

Displays queue items using the canonical backend statuses:

```text
draft
queued
scheduled
published
```

Publishing failures are displayed as operation feedback and retry actions, not as a `failed` queue status.

Columns:

```
Product

Channel

Schedule

Status

Actions
```

---

# 10.2 SchedulePicker

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

Displays:

* Channel name.
* Platform.
* Status.
* Connection state.

---

# 11.2 ConnectionStatus

Shows:

```
Connected

Disconnected

Error
```

---

# 12. Component Development Checklist

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
