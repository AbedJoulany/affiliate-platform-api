# Routing and Navigation v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-16

---

# 1. Purpose

This document defines the routing architecture and navigation structure of the AI Affiliate Automation Platform frontend.

The purpose of this architecture is to provide:

* A predictable URL structure.
* Clear separation between application areas.
* Scalable routing for future SaaS expansion.
* Consistent navigation patterns.
* Support for authentication and authorization.

The routing system should reflect the product structure and business modules.

---

# 2. Routing Principles

## 2.1 Feature-Based Routes

Routes should represent product features.

Example:

```text
/products
/discovery
/queue
/channels
```

Each route maps to a business module.

---

## 2.2 Clean URLs

URLs should be:

* Short.
* Predictable.
* Human-readable.

Preferred:

```
/products/123
```

Avoid:

```
/dashboard/products/details?id=123
```

---

## 2.3 SaaS Ready Structure

Although version one supports a single user, the routing design should allow future support for:

* Multiple workspaces.
* Organizations.
* Teams.
* Permissions.

Future example:

```
/workspace/{workspaceId}/products
```

The current implementation should avoid decisions that prevent this evolution.

---

# 3. Next.js Routing Strategy

The application uses:

```
Next.js 15 App Router
```

The routing structure follows:

```
src/app/
```

---

# 4. Application Route Groups

The application is divided into route groups.

Structure:

```text
app/

├── (auth)/
│
└── (dashboard)/
```

---

# 5. Authentication Routes

Location:

```text
app/(auth)/
```

These routes are accessible without authentication.

---

## Login

Route:

```
/login
```

Purpose:

Allows users to authenticate.

Contains:

* Email input.
* Password input.
* Login action.
* Error handling.

---

## Future Authentication Routes

Potential additions:

```
/register

/forgot-password

/reset-password

/verify-email
```

---

# 6. Application Routes

Location:

```text
app/(dashboard)/
```

These routes require authentication.

The shared layout contains:

* Sidebar.
* Header.
* Navigation.
* User menu.

---

# 7. Main Application Routes

## Dashboard

Route:

```
/dashboard
```

Purpose:

Main workspace overview.

Contains:

* Key metrics.
* Recent activity.
* Quick actions.
* System status.

---

## Products

Route:

```
/products
```

Purpose:

Manage discovered and imported products.

Features:

* Product list.
* Search.
* Filtering.
* Import.
* Product actions.

---

## Product Details

Route:

```
/products/[id]
```

Purpose:

Detailed product workspace.

Contains:

* Product information.
* Affiliate data.
* AI content.
* Publishing actions.
* History.

Example:

```
/products/12345
```

---

## Discovery

Route:

```
/discovery
```

Purpose:

Manage product discovery workflows.

Contains:

* Discovery sources.
* Filters.
* Discovery results.
* Import actions.

Future:

* Automated discovery monitoring.
* Trend detection.

---

## AI Studio

Route:

```
/ai
```

Purpose:

AI content generation workspace.

Contains:

* Content generation.
* Prompt profiles.
* Editing.
* Generation history.

---

## Queue

Route:

```
/queue
```

Purpose:

Manage publishing lifecycle.

Contains:

* `draft` items.
* `queued` items.
* `scheduled` items.
* `published` items.
* Retry actions.

These four lowercase values are the canonical backend `QueueStatus` enum. Publishing failures are operation errors that may expose retry actions; they are not a `failed` queue status.

---

## Channels

Route:

```
/channels
```

Purpose:

Manage publishing destinations.

Current:

```
Telegram
```

Future:

```
Facebook

Instagram

WhatsApp
```

---

## Future Analytics

Route:

```
/analytics
```

Purpose:

Monitor performance.

Analytics is deferred until after the MVP. The route is reserved for future implementation and is not included in the MVP route map or sidebar.

Future features:

* Click tracking.
* Engagement.
* Conversion.
* Revenue.

---

## Settings

Route:

```
/settings
```

Purpose:

Manage application configuration.

Sections:

```
/settings/general

/settings/aliexpress

/settings/ai

/settings/telegram

/settings/discovery

/settings/scheduling
```

`/settings` is the parent route and should redirect to or render `/settings/general` as its default section. All settings sections use nested routes consistently.

---

## Profile

Route:

```
/profile
```

Purpose:

Manage user settings.

Profile is opened from the header user menu and is not a sidebar item.

Contains:

* Account information.
* Preferences.
* Security settings.

---

# 8. Complete Route Map

Current MVP:

```text
/
│
├── login
│
├── dashboard
│
├── products
│   └── [id]
│
├── discovery
│
├── ai
│
├── queue
│
├── channels
│
├── settings
│   ├── general
│   ├── aliexpress
│   ├── ai
│   ├── telegram
│   ├── discovery
│   └── scheduling
│
└── profile
```

---

# 9. Sidebar Navigation

The sidebar represents the main product modules.

Structure:

```text
Workspace

├── Dashboard
│
├── Products
│
├── Discovery
│
├── AI Studio
│
├── Queue
│
├── Channels
│
└── Settings
```

Profile is available through the header user menu. Analytics is deferred and omitted from the MVP sidebar. A workspace selector must remain hidden until multi-workspace support is implemented.

---

# 10. Navigation Item Structure

Each navigation item contains:

```typescript
{
    label: string,
    href: string,
    icon: Icon,
    permissions?: Permission[]
}
```

Example:

```typescript
{
    label: "Products",
    href: "/products",
    icon: Package
}
```

---

# 11. Sidebar States

The sidebar supports:

## Expanded Mode

Desktop default.

Displays:

* Icon.
* Label.
* Optional badge.

---

## Collapsed Mode

Displays:

* Icons only.
* Tooltip labels.

---

## Mobile Mode

Uses:

* Drawer navigation.
* Overlay interaction.

---

# 12. Breadcrumb Navigation

Complex pages should display breadcrumbs.

Example:

```
Products
    >
Product Details
    >
AI Content
```

Used for:

* Deep navigation.
* Better context.

---

# 13. Route Protection

Protected routes use:

* Authentication provider.
* Middleware checks.
* Session validation.

Unauthenticated users:

```
Any protected route
        ↓
Redirect
        ↓
/login
```

---

# 14. Authorization Strategy

Future SaaS support requires permissions.

Example:

```text
User

Workspace Owner

Admin

Editor

Viewer
```

Routes may define required permissions.

Example:

```
/settings
requires:
ADMIN
```

---

# 15. Dynamic Navigation

Navigation should support future dynamic modules.

Example:

Future workspace configuration:

```text
Enabled Features:

✓ Products

✓ Telegram

✓ Analytics

✗ Facebook
```

The sidebar should render based on enabled modules.

---

# 16. Page Layout Rules

Every application page follows:

```text
Page Layout

├── Page Header
│
│   ├── Title
│   ├── Description
│   └── Actions
│
└── Page Content
```

---

# 17. Loading Navigation

Navigation should provide feedback for:

* Route changes.
* Data loading.
* Permission checks.

Preferred:

* Skeleton states.
* Optimistic transitions.

---

# 18. Error Routes

The application should provide:

## Global Error

```
/error
```

Handles unexpected errors.

---

## Not Found

```
/not-found
```

Handles invalid routes.

---

## Unauthorized

Handles:

* Missing permissions.
* Restricted pages.

---

# 19. Future Routing Expansion

Potential future routes:

## Analytics

```
/analytics
```

---

## Workspaces

```
/workspaces

/workspaces/[id]
```

---

## Automation

```
/automation

/automation/workflows/[id]
```

---

## Competitor Analysis

```
/competitors
```

---

## Integrations

```
/integrations
```

---

# 20. Routing Summary

The routing architecture follows:

```
Next.js App Router

+

Feature-Based Routes

+

Protected Application Shell

+

Clean URLs

+

SaaS Expansion Ready

+

Permission-Aware Navigation
```

The goal is to create a navigation system that remains simple for the MVP while supporting the evolution into a full SaaS platform.
