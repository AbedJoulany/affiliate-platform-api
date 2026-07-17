# Cursor Development Prompts v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-16

---

# 1. Purpose

This document defines the standard prompts and workflow used with Cursor AI during frontend development.

The goal is to ensure that AI-assisted development follows:

* Frontend architecture rules.
* Design system standards.
* Component library patterns.
* TypeScript practices.
* Feature-based organization.

Cursor should act as a development assistant, not as an architect.

The architecture decisions are already defined in:

```text
/docs
```

---

# 2. Cursor Working Rules

Before generating code, Cursor should:

1. Read relevant documentation.
2. Understand existing folder structure.
3. Reuse existing components.
4. Avoid unnecessary dependencies.
5. Avoid changing architecture without approval.
6. Generate small incremental changes.

---

# 3. General Feature Development Prompt Template

Use this template when creating any feature.

```
You are working on the AI Affiliate Automation Platform frontend.

Before writing code:
- Read the frontend documentation in /docs.
- Follow the architecture defined in:
  - 02-Frontend-Architecture.md
  - 03-design-system.md
  - 04-component-library.md
  - 07-development-guidelines.md

Task:
[DESCRIBE FEATURE]

Requirements:
- Use Next.js 15 App Router.
- Use TypeScript.
- Follow feature-based architecture.
- Use existing UI components when possible.
- Do not create duplicate components.
- Support loading, error, and empty states.
- Support dark mode.
- Support RTL.
- Keep components reusable.

Before implementation:
Explain:
1. Files you will create.
2. Files you will modify.
3. Components needed.
4. Data flow.

Then implement the feature.
```

---

# 4. Project Initialization Prompt

Use when creating the Next.js project.

```
Create the frontend foundation for the
AI Affiliate Automation Platform.

Technology requirements:

- Next.js 15
- TypeScript
- TailwindCSS
- shadcn/ui
- TanStack Query
- Axios
- React Hook Form
- Zod

Create this structure:

src/

app/

components/
    ui/
    layout/
    common/

features/

services/

hooks/

lib/

types/

utils/

Requirements:

- Configure TypeScript.
- Configure ESLint.
- Configure Tailwind.
- Add path aliases.
- Add theme support.
- Prepare RTL support.
- Create clean production-ready structure.

Do not create business features yet.
Only create the foundation.
```

---

# 5. Design System Implementation Prompt

```
Implement the Design System defined in:

/docs/03-design-system.md

Create reusable UI foundations.

Implement:

UI Components:
- Button
- Input
- Select
- Card
- Badge
- Dialog
- Dropdown
- Toast

Requirements:

- Use shadcn/ui where appropriate.
- Follow existing design tokens.
- Support dark mode.
- Support RTL.
- Use TypeScript.
- Do not add custom styles unless necessary.

After implementation:
Provide a list of created components.
```

---

# 6. Application Shell Prompt

```
Build the main application shell.

Follow:

/docs/04-component-library.md
/docs/05-routing-and-navigation.md

Create:

components/layout/

- AppShell
- Sidebar
- Header
- PageContainer
- PageHeader


Requirements:

Sidebar:

- Responsive.
- Collapsible.
- Mobile drawer support.
- Active route highlighting.

Navigation items:

- Dashboard
- Products
- Discovery
- AI Studio
- Queue
- Channels
- Settings

Profile must be accessed from the header user menu, not the sidebar.
Do not render a workspace selector until multi-workspace support is implemented.
Analytics is deferred and must not appear in the MVP sidebar.

Do not add business logic.
Only implement layout.
```

---

# 7. Authentication Prompt

```
Implement frontend authentication.

Follow:

/docs/06-api-integration.md

Requirements:

Create:

features/auth/

api/
hooks/
types/
components/


Implement:

- Login page.
- Authentication provider.
- Protected routes.
- Logout.
- JWT handling.

Use:

- Axios API client.
- TanStack Query.
- TypeScript.

Do not store authentication logic inside UI components.
```

---

# 8. API Client Prompt

```
Create the frontend API integration layer.

Follow:

/docs/06-api-integration.md


Create:

services/

api-client.ts


Requirements:

Implement:

- Axios instance.
- Base URL configuration.
- Authentication headers.
- Error normalization.
- Request interceptors.
- Response interceptors.


Do not create feature-specific API calls here.
```

---

# 9. Feature API Prompt

Use for each backend module.

Example:

Products.

```
Create the API layer for the Products feature.

Location:

features/products/api/


Implement:

- products.api.ts


Functions:

- getProducts()
- getProduct()
- createProduct()
- updateProduct()
- deleteProduct()


Requirements:

- Use centralized api-client.
- Add TypeScript types.
- Do not add UI logic.
```

---

# 10. TanStack Query Hook Prompt

```
Create TanStack Query hooks for this feature.

Feature:

[FEATURE NAME]


Location:

features/[feature]/hooks/


Requirements:

Create:

- Query hooks.
- Mutation hooks.
- Proper query keys.
- Cache invalidation.
- Loading states.
- Error handling.


Follow API integration rules.
```

---

# 11. Dashboard Prompt

```
Build the Dashboard feature.

Follow:

/docs/04-component-library.md
/docs/05-routing-and-navigation.md


Create:

features/dashboard/


Components:

- StatCard
- ActivityFeed
- QuickActionCard
- SystemStatus


Page:

/dashboard


Requirements:

Display:

- Products count.
- Queue status.
- Published posts.
- AI usage.
- Recent activity.


Use mock data first if API is unavailable.

Keep components reusable.
```

---

# 12. Products Module Prompt

```
Build the Products feature.

Follow:

/docs/08-implementation-roadmap.md


Create:

features/products/


Components:

- ProductTable
- ProductCard
- ProductFilters
- ProductPreview


Pages:

/products

/products/[id]


Features:

- Search.
- Filtering.
- Pagination.
- Product details.
- Actions.


Use:

- DataTable component.
- TanStack Query.
- TypeScript.


Support:

- Loading.
- Empty state.
- Errors.
```

---

# 13. AI Studio Prompt

```
Build the AI Studio feature.

Create:

features/ai/


Components:

- AIContentEditor
- PromptProfileSelector
- GenerationStatus


Page:

/ai


Features:

- Generate content.
- Edit content.
- Regenerate.
- Save.


Requirements:

Follow AI architecture.
Keep AI provider logic in backend.
Frontend only manages user interaction.
```

---

# 14. Queue Module Prompt

```
Build the Publishing Queue feature.


Create:

features/queue/


Components:

- QueueTable
- SchedulePicker


Page:

/queue


Features:

- `draft` items.
- `queued` items.
- `scheduled` items.
- `published` items.
- Retry publishing failures.
- Publish now.


Use existing DataTable component.
Use the canonical backend QueueStatus values exactly.
Do not add a `failed` queue status; failures are operation errors.
```

---

# 15. Channels Module Prompt

```
Build Channels management.

Create:

features/channels/


Components:

- ChannelCard
- ConnectionStatus


Page:

/channels


Features:

- List channels.
- Add channel.
- Test connection.
- Display status.


Initial platform:

Telegram
```

---

# 16. Settings Module Prompt

```
Build Settings pages.


Create:

- /settings
- /settings/general
- /settings/aliexpress
- /settings/ai
- /settings/telegram
- /settings/discovery
- /settings/scheduling


Sections:

- General
- AliExpress
- AI Providers
- Telegram
- Discovery
- Scheduling


Requirements:

- Treat /settings as the parent route and use /settings/general as the default section.
- Use reusable form components.
- Use React Hook Form.
- Use Zod validation.
```

---

# 17. Refactoring Prompt

Use when improving existing code.

```
Review this implementation.

Check against:

- 02-Frontend-Architecture.md
- 03-design-system.md
- 07-development-guidelines.md


Identify:

- Duplicate components.
- Bad folder placement.
- Missing types.
- Poor abstractions.
- Performance issues.


Suggest improvements first.

Do not modify until approved.
```

---

# 18. Code Review Prompt

```
Review this code as a senior frontend engineer.

Check:

Architecture:
- Correct location?
- Feature separation?

TypeScript:
- Any unsafe types?
- Missing interfaces?

UX:
- Loading states?
- Error states?
- Empty states?

Design:
- Matches design system?
- Dark mode?
- RTL?

Performance:
- Unnecessary renders?
- Bad data fetching?


Return:
1. Issues found.
2. Suggested fixes.
3. Priority level.
```

---

# 19. Debugging Prompt

```
Debug this issue.

Context:

[ERROR DESCRIPTION]


Before changing code:

Explain:
- Root cause.
- Files involved.
- Possible solutions.


Then implement the safest solution.

Do not introduce unrelated changes.
```

---

# 20. Feature Completion Prompt

Use after finishing any feature.

```
Review the completed feature.

Verify:

Architecture:
✓ Correct folders
✓ Reusable components

UI:
✓ Design system compliance
✓ Responsive
✓ Dark mode
✓ RTL

Data:
✓ API separation
✓ Query handling

Quality:
✓ TypeScript safety
✓ Error handling
✓ Loading states


Provide:
- Completed items.
- Remaining issues.
- Suggested improvements.
```

---

# 21. Cursor Development Philosophy

Cursor should help implement decisions.

It should not decide:

* Architecture.
* Folder structure.
* Libraries.
* Design direction.

The workflow is:

```
Human defines architecture

↓

Cursor implements

↓

Human reviews

↓

Improve

↓

Commit
```

---

# Final Goal

Use Cursor as a professional engineering assistant to accelerate development while maintaining:

```
Clean Architecture

+

Consistent Design

+

High Code Quality

+

Scalable SaaS Foundation
```

The objective is not only to finish the frontend, but to build a maintainable product foundation.
