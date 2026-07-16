# Frontend Architecture v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-14

---

# 1. Purpose

The frontend of the AI Affiliate Automation Platform is designed to provide a modern, scalable, and productive workspace for managing affiliate marketing automation workflows.

The application is not intended to be a traditional administration dashboard. Instead, it should provide a SaaS-like experience where users can:

* Discover affiliate products.
* Review and manage imported products.
* Generate AI-powered marketing content.
* Manage publishing workflows.
* Schedule and monitor content distribution.
* Configure automation settings.

The frontend acts as a client application responsible for user interaction, presentation, and communication with backend services.

Business logic remains exclusively in the backend.

---

# 2. Architecture Goals

The frontend architecture should achieve the following goals:

* Build a modern SaaS-quality user experience.
* Maintain clean separation between UI, state management, and backend communication.
* Support future scalability into a multi-user SaaS platform.
* Enable fast development using AI-assisted tools such as Cursor.
* Maximize component reuse.
* Maintain predictable project organization.
* Ensure long-term maintainability.

---

# 3. Architecture Principles

## 3.1 API First

The frontend consumes backend APIs and does not contain business logic.

The frontend is responsible for:

* Rendering data.
* Handling user interactions.
* Managing UI state.
* Validating user input.
* Providing user feedback.

The backend is responsible for:

* Product discovery.
* Product scoring.
* AI generation logic.
* Scheduling.
* Publishing automation.
* Affiliate processing.

---

## 3.2 Feature-Based Architecture

The project is organized around business features rather than technical layers.

Each feature should contain its own:

* Components.
* API functions.
* Hooks.
* Types.
* Validation schemas.
* Utilities.

Example:

```
features/

products/
    components/
    api/
    hooks/
    types/

queue/
    components/
    api/
    hooks/
    types/
```

This approach improves scalability and makes features easier to understand and maintain.

---

## 3.3 Reusable Components

Generic UI components must exist only once.

Examples:

* Buttons.
* Inputs.
* Cards.
* Tables.
* Dialogs.
* Dropdowns.
* Pagination.
* Loading states.
* Empty states.

Reusable components belong to:

```
components/ui
```

Feature-specific components belong inside their feature folder.

---

## 3.4 Separation of Responsibilities

Each layer has a clear responsibility.

### Components

Responsible for:

* Rendering UI.
* User interaction.

Should not:

* Call APIs directly.
* Contain complex business rules.

---

### Hooks

Responsible for:

* Managing reusable logic.
* Connecting UI with application state.

Examples:

```
useProducts()
useChannels()
useQueue()
```

---

### Services

Responsible for:

* API communication.
* HTTP configuration.
* External integrations.

---

### Backend

Responsible for:

* Business rules.
* Automation.
* Data processing.

---

# 4. Technology Stack

## Framework

```
Next.js 15
```

Using:

* App Router.
* Server Components where applicable.
* Client Components only when required.

---

## Language

```
TypeScript
```

Reasons:

* Type safety.
* Better developer experience.
* Easier AI-assisted development.

---

## Styling

```
TailwindCSS
```

Used for:

* Layout.
* Responsive design.
* Utility styling.

---

## UI Library

```
shadcn/ui
```

Used for:

* Base components.
* Accessible primitives.
* Consistent design system.

---

## Data Fetching

```
TanStack Query
```

Responsible for:

* Server state.
* API caching.
* Background updates.
* Loading/error states.

---

## HTTP Client

```
Axios
```

Used through a centralized API client.

Components should never call Axios directly.

---

## Forms

```
React Hook Form
+
Zod
```

Used for:

* Form management.
* Validation.
* Type-safe schemas.

---

## Icons

```
Lucide React
```

Used as the single icon system.

---

## Theme

```
next-themes
```

Supports:

* Light mode.
* Dark mode.
* System preference.

---

# 5. Project Structure

Recommended structure:

```
src/

app/
    (auth)/
    (dashboard)/
    layout.tsx
    providers.tsx

components/

    ui/
    layout/
    common/

features/

    auth/

    dashboard/

    products/

    discovery/

    ai/

    queue/

    channels/

    settings/


services/

hooks/

lib/

types/

utils/
```

---

# 6. Routing Strategy

Application routes:

```
/login

/dashboard

/products

/products/[id]

/discovery

/ai

/queue

/channels

/settings

/profile
```

Routes should represent business features.

---

# 7. State Management

The application separates state into two categories.

## Server State

Managed by:

```
TanStack Query
```

Examples:

* Products.
* Channels.
* Queue items.
* Dashboard statistics.

---

## Client State

Used only for UI state.

Examples:

* Sidebar collapsed state.
* Modal visibility.
* Theme.
* Temporary filters.

Possible tools:

* React Context.
* Zustand if complexity increases.

---

# 8. API Architecture

All backend communication must go through an API layer.

Example:

```
features/products/api/products.api.ts
```

Example usage:

```
useProducts()
```

instead of:

```
axios.get("/products")
```

inside components.

---

# 9. Authentication Architecture

Authentication will support future SaaS requirements.

Current version:

* JWT authentication.
* Protected routes.
* User session handling.

Future support:

* Workspaces.
* Roles.
* Permissions.
* Team members.

---

# 10. UI Architecture

The application follows a workspace design approach.

Main layout:

```
Application Shell

├── Sidebar
├── Header
└── Content Area
```

The design inspiration:

* Linear.
* Vercel.
* Stripe.
* Notion.

The interface should prioritize:

* Simplicity.
* Clear hierarchy.
* Fast navigation.
* Minimal visual noise.

---

# 11. Error Handling

Every page must support:

## Loading State

Example:

* Skeleton components.
* Loading indicators.

---

## Empty State

Example:

* No products found.
* Empty queue.

---

## Error State

Example:

* API unavailable.
* Permission errors.

The application should never show broken screens.

---

# 12. Performance Guidelines

The application should follow performance best practices:

* Avoid unnecessary client components.
* Use server components when possible.
* Lazy load heavy features.
* Optimize images.
* Cache API requests.
* Avoid unnecessary re-renders.

---

# 13. RTL and Internationalization

The platform must support Arabic-first content.

Requirements:

* Full RTL support.
* Layout mirroring.
* Arabic-friendly typography.
* Future language expansion.

Supported direction:

```
RTL
```

Future:

```
LTR
```

---

# 14. AI-Friendly Development Principles

Because development uses AI coding assistants, the project must maintain:

* Small components.
* Clear naming.
* Predictable structure.
* Minimal hidden dependencies.
* Strong documentation.

Every feature should be understandable independently.

---

# 15. Coding Standards

## Naming

Components:

```
PascalCase
```

Example:

```
ProductCard.tsx
```

Hooks:

```
camelCase with use prefix
```

Example:

```
useProducts.ts
```

Files:

```
kebab-case where applicable
```

---

## Components

Components should:

* Have one responsibility.
* Avoid excessive complexity.
* Prefer composition.

---

## Types

Shared types:

```
types/
```

Feature-specific types:

```
features/[feature]/types
```

---

# 16. Future Scalability

The architecture should allow future expansion:

## Multi Workspace

Support:

* Multiple users.
* Multiple organizations.
* Team collaboration.

---

## Multiple Affiliate Networks

Future integrations:

* AliExpress.
* Amazon.
* Other affiliate platforms.

---

## Multiple Publishing Channels

Future support:

* Telegram.
* Facebook.
* Instagram.
* WhatsApp.

---

# 17. Architecture Decision Summary

The project follows:

```
Next.js 15
+
TypeScript
+
Feature-Based Architecture
+
TanStack Query
+
shadcn/ui
+
TailwindCSS
+
API First Design
+
SaaS Ready Structure
```

The goal is to build a maintainable, scalable, AI-assisted frontend that can evolve from a personal automation tool into a commercial SaaS platform.
