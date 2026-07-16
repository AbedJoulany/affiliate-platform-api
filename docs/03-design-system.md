# Design System v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-14

---

# 1. Purpose

The Design System defines the visual language, interaction patterns, and reusable UI principles of the AI Affiliate Automation Platform.

Its purpose is to create a consistent, scalable, and professional user experience across all application modules.

The design system should ensure that every page feels like part of the same product while allowing individual features to evolve independently.

---

# 2. Design Philosophy

The platform should feel like a modern SaaS workspace rather than a traditional administration dashboard.

The main design inspiration comes from:

* Linear
* Vercel Dashboard
* Stripe Dashboard
* Notion
* GitHub

The interface should prioritize:

* Clarity over decoration.
* Productivity over complexity.
* Information hierarchy.
* Fast navigation.
* Minimal cognitive load.
* Consistent interactions.

---

# 3. Core Design Principles

## 3.1 Minimalism

The interface should avoid unnecessary visual elements.

Avoid:

* Excessive borders.
* Heavy shadows.
* Too many colors.
* Decorative elements without purpose.

Prefer:

* Clean spacing.
* Clear typography.
* Subtle visual hierarchy.

---

## 3.2 Consistency

The same interaction should always look and behave the same way.

Examples:

* All primary actions use the same button style.
* All statuses use consistent badges.
* All tables follow the same structure.
* All pages follow the same layout pattern.

---

## 3.3 Information Hierarchy

Important information should be visually dominant.

Priority order:

1. Page purpose.
2. Primary actions.
3. Important metrics.
4. Main content.
5. Secondary information.

---

## 3.4 User Efficiency

The design should minimize the number of actions required to complete tasks.

Examples:

* Quick actions from dashboard.
* Bulk operations.
* Keyboard-friendly interactions.
* Smart defaults.

---

# 4. Visual Identity

## Brand Personality

The product should feel:

* Intelligent.
* Professional.
* Reliable.
* Modern.
* Efficient.

Avoid feeling:

* Generic admin template.
* Overly corporate.
* Consumer shopping application.

---

# 5. Color System

Colors should be implemented using CSS variables to support:

* Light mode.
* Dark mode.
* Future customization.

---

# 5.1 Semantic Colors

## Background

Used for:

* Application background.
* Page surfaces.

Variables:

```
--background
--foreground
```

---

## Surface

Used for:

* Cards.
* Panels.
* Dropdowns.
* Modals.

Variables:

```
--surface
--surface-foreground
```

---

## Primary

Used for:

* Main actions.
* Active states.
* Important interactions.

Examples:

* Create Product.
* Generate AI Content.
* Publish.

Variables:

```
--primary
--primary-foreground
```

---

## Secondary

Used for:

* Secondary actions.
* Supporting elements.

Variables:

```
--secondary
--secondary-foreground
```

---

## Muted

Used for:

* Secondary text.
* Hints.
* Disabled information.

Variables:

```
--muted
--muted-foreground
```

---

## Border

Used for:

* Dividers.
* Input borders.
* Table separators.

Variable:

```
--border
```

---

# 5.2 Status Colors

## Success

Used for:

* Published.
* Completed.
* Connected.

---

## Warning

Used for:

* Pending.
* Attention required.

---

## Error

Used for:

* Failed operations.
* Validation errors.

---

## Info

Used for:

* Informational messages.

---

# 6. Typography

Typography should provide clear hierarchy and readability.

Recommended font:

Primary:

```
Inter
```

Arabic support:

```
IBM Plex Sans Arabic
or
Noto Sans Arabic
```

---

# Typography Scale

## Display

Used for:

* Landing pages.
* Major metrics.

---

## Heading 1

Used for:

* Page titles.

Example:

```
Products
```

---

## Heading 2

Used for:

* Section titles.

---

## Heading 3

Used for:

* Card titles.

---

## Body

Used for:

* General content.

---

## Small

Used for:

* Metadata.
* Labels.

---

## Caption

Used for:

* Supporting information.

---

# 7. Spacing System

Use a consistent spacing scale.

Base unit:

```
4px
```

Scale:

```
4
8
12
16
20
24
32
40
48
64
```

Usage:

```
4px
Small gaps

16px
Component spacing

24px
Section spacing

32px+
Page-level spacing
```

---

# 8. Border Radius

Rounded corners should be subtle and modern.

Values:

```
sm: 6px

md: 8px

lg: 12px

xl: 16px
```

Usage:

Buttons:

```
md
```

Cards:

```
lg
```

Modals:

```
xl
```

---

# 9. Shadows

Shadows should be minimal.

Usage:

## Small

Dropdowns.

## Medium

Cards requiring elevation.

## Large

Dialogs and overlays.

Avoid heavy shadows.

---

# 10. Layout System

The application uses a workspace layout.

```
Application

├── Sidebar
│
├── Header
│
└── Main Content
```

---

# Page Layout Pattern

Every page should follow:

```
Page Container

    Page Header

        Title

        Description

        Actions


    Main Content

        Sections

        Cards

        Tables
```

---

# 11. Components Principles

All components should:

* Be reusable.
* Support loading states.
* Support disabled states.
* Support accessibility.
* Have predictable APIs.

---

# 12. Component Categories

## UI Components

Location:

```
components/ui
```

Examples:

* Button.
* Input.
* Select.
* Card.
* Badge.
* Dialog.

---

## Layout Components

Location:

```
components/layout
```

Examples:

* Sidebar.
* Header.
* PageContainer.
* Navigation.

---

## Feature Components

Location:

```
features/[feature]/components
```

Examples:

```
ProductCard

QueueItem

ChannelCard
```

---

# 13. Buttons

Buttons represent actions.

## Primary

Used for:

* Main action.

Examples:

* Create.
* Generate.
* Publish.

---

## Secondary

Used for:

* Supporting actions.

---

## Ghost

Used for:

* Low emphasis actions.

---

## Danger

Used for:

* Destructive actions.

Examples:

* Delete.

---

# 14. Cards

Cards are used to group related information.

Types:

## Stat Card

Used for:

* Dashboard metrics.

Example:

```
Products Imported

245
```

---

## Content Card

Used for:

* Product information.
* AI content.

---

## Action Card

Used for:

* Quick actions.

---

# 15. Tables

Tables are a core component of the platform.

All tables should support:

* Search.
* Filtering.
* Sorting.
* Pagination.
* Loading.
* Empty state.
* Row actions.
* Bulk actions.

---

# 16. Status System

Statuses should always use badges.

Examples:

Product:

```
Imported
Reviewed
Queued
Published
Failed
```

Queue:

```
Draft
Scheduled
Publishing
Published
Failed
```

---

# 17. Forms

Forms should follow:

* Clear labels.
* Helpful descriptions.
* Inline validation.
* Consistent spacing.

Required:

* Loading state.
* Error handling.
* Success feedback.

---

# 18. Feedback Patterns

## Toast

Used for:

* Short notifications.

Examples:

"Product imported successfully"

---

## Dialog

Used for:

* Confirmation.
* Important decisions.

---

## Empty State

Every empty page needs:

* Explanation.
* Helpful action.

---

# 19. Loading Patterns

Preferred:

* Skeleton loading.

Avoid:

* Full-page spinners whenever possible.

Examples:

* Table skeleton.
* Card skeleton.
* Content skeleton.

---

# 20. Dark Mode

Dark mode is a first-class feature.

Requirements:

* All components support dark mode.
* No hardcoded colors.
* Use semantic variables.

---

# 21. Responsive Design

The application should support:

Desktop:

Primary experience.

Tablet:

Supported.

Mobile:

Basic usability.

---

# 22. RTL Support

Arabic is a primary content language.

Requirements:

* Layout mirroring.
* Correct text alignment.
* RTL-aware components.
* Icon positioning awareness.

---

# 23. Accessibility

All components should follow accessibility best practices:

* Keyboard navigation.
* Proper labels.
* Focus states.
* Screen reader compatibility.
* Sufficient contrast.

---

# 24. Animation Guidelines

Animations should be subtle.

Use for:

* Page transitions.
* Hover states.
* Loading feedback.

Avoid:

* Excessive motion.
* Distracting animations.

---

# 25. Future Expansion

The design system should support future:

* Multiple themes.
* White labeling.
* Workspace customization.
* Additional platforms.
* Additional languages.

---

# Design System Summary

The AI Affiliate Automation Platform design system follows these principles:

```
Modern SaaS Experience

+

Minimal Interface

+

Reusable Components

+

Consistent Patterns

+

RTL Ready

+

Dark Mode Ready

+

AI Development Friendly
```

The goal is to create an interface that feels like a professional automation platform, not a traditional admin panel.
