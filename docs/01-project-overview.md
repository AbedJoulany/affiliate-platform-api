# Project Overview v1.0

## AI Affiliate Automation Platform

**Document Version:** 1.0
**Last Updated:** 2026-07-17

---

# 1. Introduction

The AI Affiliate Automation Platform is an intelligent SaaS-ready platform designed to automate the affiliate marketing workflow from product discovery to content publishing.

The platform combines:

* Product discovery automation.
* AI-powered marketing content generation.
* Publishing automation.
* Scheduling.
* Analytics.

The main goal is to reduce manual affiliate marketing work and create a system capable of continuously discovering, evaluating, and promoting high-potential products.

---

# 2. Vision

The long-term vision is to build an intelligent affiliate automation operating system.

Instead of manually:

* Searching for products.
* Checking product quality.
* Writing marketing content.
* Creating posts.
* Scheduling publications.
* Tracking performance.

The platform should automatically manage the complete workflow:

```text
Product Discovery

↓

Product Evaluation

↓

AI Content Generation

↓

Publishing Queue

↓

Scheduled Publishing

↓

Analytics & Optimization
```

---

# 3. Problem Statement

Affiliate marketers currently spend significant time on repetitive tasks:

## Product Research

Finding profitable products requires:

* Searching multiple sources.
* Comparing products.
* Checking reviews.
* Evaluating demand.

---

## Content Creation

Creating attractive marketing posts requires:

* Writing descriptions.
* Translating content.
* Adding persuasive copy.
* Adapting content for different platforms.

---

## Publishing Management

Managing multiple channels requires:

* Scheduling posts.
* Tracking publishing status.
* Repeating manual actions.

---

## Optimization

Understanding what works requires:

* Analytics.
* Performance tracking.
* Continuous adjustments.

---

The platform solves these challenges by automating the entire workflow.

---

# 4. Product Goal

The primary goal is:

> Build an AI-powered automation platform that discovers valuable products, creates marketing content, and publishes them automatically with minimal human intervention.

---

# 5. Target Users

## Primary User

Affiliate marketers who:

* Promote products online.
* Manage Telegram channels.
* Need continuous product discovery.
* Want to automate publishing.

---

## Future Users

Small businesses and creators who need:

* Product promotion automation.
* Social media publishing.
* AI marketing assistance.

---

# 6. Core Workflow

The main product workflow:

```text
AliExpress Product Sources

↓

Discovery Engine

↓

Filtering System

↓

Product Scoring

↓

AI Content Generation

↓

Publishing Queue

↓

Telegram Publishing

↓

Performance Analytics
```

---

# 7. Core Features

---

## Current implementation boundary (2026-07-17)

The repository currently contains a FastAPI backend and an Arabic-first Next.js frontend.
The frontend implements login, dashboard, products, product detail, discovery, AI generation,
queue, Telegram channels, profile, and read-only settings/status routes. Pages are thin App
Router entries that render client-side feature views. Advanced analytics, editable settings,
AI prompt profiles/history, queue scheduling controls, and multi-workspace behavior remain
target capabilities.

Product imports require an `admin` account. Public registration intentionally creates only
`affiliate` users, so operational admin provisioning is required before imports can be used.


# 7.1 Product Discovery

The platform automatically discovers products from AliExpress.

Supported sources:

* Hot Products.
* Trending Products.
* Promotional Products.
* Categories.
* Keyword Search.

Future:

* Multiple affiliate networks.
* Competitor monitoring.
* Trend detection.

---

# 7.2 Product Filtering

Products can be filtered based on configurable rules.

Examples:

* Price.
* Rating.
* Sales volume.
* Review count.
* Commission rate.
* Categories.
* Keywords.

---

# 7.3 Product Scoring Engine

Each product receives a quality score.

Example:

```text
Product Score =

Discount Weight

+

Rating Weight

+

Sales Weight

+

Reviews Weight

+

Commission Weight

+

Trend Weight
```

The scoring system is configurable.

Future:

* Machine learning ranking.
* Performance-based optimization.

---

# 7.4 AI Content Generation

The platform generates marketing content using AI providers.

Supported providers:

* OpenAI.
* Gemini.

Generated content includes:

* Product title.
* Marketing description.
* Call-to-action.
* Hashtags.
* Arabic promotional text.

---

# 7.5 Publishing Queue

The publishing system manages content lifecycle.

Statuses:

```text
draft

↓

queued

↓

scheduled

↓

published
```

These values match the backend `QueueStatus` enum. Publishing failures are operation errors and do not introduce a `failed` queue status.

---

# 7.6 Telegram Publishing

Initial publishing platform:

```text
Telegram
```

Capabilities:

* Channel management.
* Automatic publishing.
* Scheduled posts.
* Publishing status tracking.

---

# 7.7 Future Analytics

Analytics is deferred until after the MVP. The planned frontend route is `/analytics`; it is not included in the MVP route map or sidebar.

Planned metrics:

* Products discovered.
* Products imported.
* Queue size.
* Published posts.
* AI usage.

AI usage is a future analytics metric; it is not part of the current dashboard API or UI.

Future:

* Click tracking.
* Conversion tracking.
* Revenue analytics.

---

# 8. Future SaaS Vision

The platform is designed to evolve into a multi-tenant SaaS product.

Future capabilities:

---

## Multi Workspace

Support multiple users and organizations.

Features:

* Workspaces.
* Teams.
* Permissions.
* Collaboration.

---

## Multiple Affiliate Networks

Future integrations:

* Amazon.
* Other affiliate networks.

---

## Multi Platform Publishing

Future support:

```text
Facebook

Instagram

WhatsApp

Other social platforms
```

---

## Automation Engine

Advanced workflows:

Example:

```text
IF Product Score > 85

AND

Commission > 10%

THEN

Generate Content

AND

Schedule Post
```

---

## Competitor Intelligence

Future features:

* Competitor monitoring.
* Trending product discovery.
* Market analysis.

---

# 9. Technical Architecture Overview

The system consists of:

```text
Frontend

↓

Backend API

↓

Database

↓

Background Workers

↓

External Services
```

---

# 10. Technology Stack

## Frontend

```text
Next.js 15.5.x and React 19

TypeScript

Tailwind CSS 3.4 with local primitives

TanStack Query 5

Axios

React Hook Form

Zod

Lucide React

next-themes
```

The current UI layer is the Tailwind-based local component set in
`frontend/src/components/ui/primitives.tsx`; shadcn/ui is not installed. Adopting shadcn/ui
or a richer accessible component library is a future option, not a description of the
current implementation. CI uses Node 22.

---

## Backend

```text
Python

FastAPI

PostgreSQL

SQLAlchemy

Alembic

Celery

Redis

Docker
```

---

## External Services

Current:

```text
AliExpress API

OpenAI API

Gemini API

Telegram API
```

---

# 11. Project Architecture Philosophy

The project follows:

## Feature-Based Architecture

Each feature owns:

* Components.
* API calls.
* Hooks.
* Types.

---

## Separation of Concerns

Frontend:

* User interface.
* User interactions.

Backend:

* Business logic.
* Automation.
* Data processing.

---

## Scalable Design

The system is designed to support:

* More users.
* More platforms.
* More integrations.

---

# 12. MVP Scope

The first production-ready version includes:

## Authentication

* Login.
* Protected routes.
* Access-JWT session validation.

---

## Dashboard

* Basic metrics.
* Activity overview.

---

## Products

* Product list.
* Product details.
* Import products.
* Search.
* Filters.

---

## AI Studio

* Generate marketing content.
* Edit content.

---

## Queue

* Manage posts.
* Filter and publish existing queue items.

Creating scheduled items is supported by the API, but a scheduling editor is not currently
implemented in the UI.

---

## Channels

* Telegram management.

---

## Settings

* Read-only capability and readiness/status screens.

There are no editable settings APIs or settings forms in the current implementation.

---

# 13. Development Principles

The project prioritizes:

```text
Maintainability

+

Scalability

+

Clean Architecture

+

Reusable Components

+

AI-Assisted Development
```

---

# 14. Current Development Strategy

Development is divided into two major stages.

---

# Stage 1 — Frontend Productization

Focus:

* Build professional SaaS interface.
* Connect existing backend.
* Validate workflows.
* Improve usability.

---

# Stage 2 — Platform Expansion

Focus:

* Automation engine.
* Multi-user support.
* Analytics.
* Additional platforms.

---

# 15. Success Criteria

Current frontend productization is successful when a provisioned user can:

1. Discover and review products.
2. Import products with an admin account.
3. Generate and edit marketing content.
4. Add generated content to the publishing queue.
5. Publish queue content to a configured Telegram channel.

The complete product vision additionally includes scheduling controls and performance
monitoring with minimal manual effort. Those capabilities remain roadmap targets rather
than claims about the current frontend.

---

# 16. Project Summary

The AI Affiliate Automation Platform is not simply a product posting tool.

It is an intelligent automation system designed to transform affiliate marketing from a manual process into an automated workflow powered by:

```text
Data

+

Automation

+

Artificial Intelligence

+

Scalable Software Architecture
```

The ultimate goal is to create a commercial SaaS platform capable of helping affiliate marketers discover, promote, and optimize products automatically.
