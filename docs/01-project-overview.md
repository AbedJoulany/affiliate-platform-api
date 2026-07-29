# Project Overview

**Document Version:** 2.0  
**Last Updated:** 2026-07-29

---

## 1. Introduction

The **AI Affiliate Automation Platform** is an intelligent SaaS-ready system that automates affiliate marketing from product discovery through AI content generation to Telegram publishing.

The repository contains:

- A **layered async FastAPI backend** (PostgreSQL, Celery, Redis)
- A **Next.js 15 App Router frontend** with Arabic-first workspace UX
- Integration clients for **AliExpress**, **OpenAI**, **Gemini**, and **Telegram**

Primary workflow:

```text
AliExpress Discovery → Product Scoring → Inventory Review
        ↓
AI Content Studio → Publishing Queue → Telegram Dispatch
        ↓
Performance Analytics (planned)
```

---

## 2. Vision & Problem

Affiliate marketers spend excessive time on repetitive research, copywriting, scheduling, and channel management. This platform reduces manual work by combining data-driven product scoring, AI-generated Arabic marketing copy, and automated publishing pipelines.

Long-term vision: an **affiliate automation operating system** supporting multi-workspace SaaS, additional affiliate networks, and multi-channel publishing.

---

## 3. Target Users

| User | Needs |
| --- | --- |
| **Primary — Affiliate marketers** | Discover products, evaluate scores, generate content, publish to Telegram |
| **Admin operators** | Import products, manage catalog lifecycle, configure channels |
| **Future — Teams & businesses** | Shared workspaces, roles, analytics, automation rules |

Public registration creates `affiliate` users only. Admin accounts must be provisioned operationally before catalog import is available.

---

## 4. System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Next.js Frontend (workspaces: discovery, products, queue) │
└────────────────────────────┬────────────────────────────────┘
                             │ REST /api/v1 + JWT
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI API Layer (app/api/v1/*, app/auth/router.py)       │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Service Layer   │  │ Repositories │  │ Integration      │
│ app/services/*  │  │ app/repos/*  │  │ ai, telegram,    │
└────────┬────────┘  └──────┬───────┘  │ aliexpress       │
         │                  │          └──────────────────┘
         └──────────┬───────┘
                    ▼
           ┌────────────────┐
           │ PostgreSQL 16  │
           └────────────────┘

        ┌──── Celery Worker ────┐
        │  Redis broker/beat    │
        │  Scheduled publishing │
        └───────────────────────┘
```

### Backend layers

| Layer | Location | Responsibility |
| --- | --- | --- |
| API | `app/api/v1/` | Routes, Pydantic validation, auth guards |
| Services | `app/services/` | Business rules, orchestration |
| Repositories | `app/repositories/` | Database access only |
| Models | `app/models/`, `app/auth/` | SQLAlchemy 2.0 ORM |
| Schemas | `app/schemas/` | Pydantic v2 DTOs |
| Workers | `app/worker/` | Celery tasks (publish, discovery refresh) |
| Integrations | `app/ai/`, `app/telegram/`, `app/aliexpress/` | External API clients |

### Request lifecycle

1. HTTP request → FastAPI router
2. Dependencies inject DB session, `CurrentUser`, role guards
3. Service executes business logic
4. Repository persists/queries PostgreSQL
5. Pydantic response returned; session auto-commits on success

### Background processing

Celery Beat triggers `process_publish_queue` on a configurable interval (default 60s). Workers publish due **scheduled** and ready **queued** items via `TelegramPublishingService`.

---

## 5. Technology Stack

### Frontend

| Technology | Role |
| --- | --- |
| Next.js 15.5 / React 19 | App Router, client feature views |
| TypeScript | Type safety |
| Tailwind CSS 3.4 | Styling, density/layout tokens |
| TanStack Query 5 | Server state, caching |
| Axios | HTTP via shared `apiClient` |
| React Hook Form + Zod | Form validation |
| Lucide React | Icons |
| next-themes | Light/dark mode |

UI primitives live in `frontend/src/components/ui/primitives.tsx` (Button, Input, Select, Card, Badge, Skeleton, **Drawer**, **Popover**). shadcn/ui is not installed.

### Backend

Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy 2.0 async · Alembic · Celery · Redis · Docker

### External services

AliExpress Affiliate API (IOP SDK) · OpenAI · Gemini · Telegram Bot API

---

## 6. Core Workflows (Current)

### Discovery workspace (`/discovery`)

Browse AliExpress products by intent (hot, deals, trending, category, general). Filter, sort, bulk-select, inspect in a slide-over drawer, import (admin), and hand off to AI Studio or queue.

### Products inventory (`/products`)

Server-paginated catalog grid with density controls, column visibility, bulk selection, row-click **ProductDetailsDrawer**, admin delete, status updates, and queue/AI shortcuts.

### AI Content Studio (`/ai`)

Multi-variant content workspace with tone/type/language controls, local session persistence, performance scoring (client-side), and queue/distribution actions.

### Publishing queue (`/queue`)

KPI summary cards, filterable table, **QueueDetailsDrawer**, inline scheduling dialog, bulk publish/schedule/delete, channel routing indicators, and publish-failure tracking (client-side).

### Channels & settings

Telegram channel management; read-only settings/capability screens backed by `/ready`.

---

## 7. MVP Scope & Boundaries

**In scope today:** Login, dashboard, discovery, products inventory, AI studio, queue operations, channels, read-only settings.

**Partial / roadmap:** Real-time queue streaming, tenant isolation, refresh tokens, analytics route, editable settings, image search UI, full discovery filter surface, server-side AI variant persistence.

---

## 8. Documentation Suite

| Doc | Topic |
| --- | --- |
| [01-project-overview.md](./01-project-overview.md) | This document |
| [02-frontend-architecture.md](./02-frontend-architecture.md) | Frontend structure & state |
| [03-design-system.md](./03-design-system.md) | Visual tokens & patterns |
| [04-component-library.md](./04-component-library.md) | Shared & feature components |
| [05-routing-and-navigation.md](./05-routing-and-navigation.md) | Routes & navigation |
| [06-api-integration.md](./06-api-integration.md) | API contracts & integration matrix |
| [07-development-guidelines.md](./07-development-guidelines.md) | Coding standards |
| [08-implementation-roadmap.md](./08-implementation-roadmap.md) | Feature checklist & phases |
| [09-cursor-prompts.md](./09-cursor-prompts.md) | AI-assisted development prompts |
| [10-production-readiness.md](./10-production-readiness.md) | Release & security runbook |

Legacy root documents `ARCHITECTURE.md` and `HANDOFF.md` were consolidated into this suite on 2026-07-29.

---

## 9. Success Criteria

A provisioned user can:

1. Discover and inspect products with AI score breakdowns
2. Import products (admin) and manage inventory from `/products`
3. Generate and refine Arabic marketing content in AI Studio
4. Create, schedule, and publish queue items to Telegram
5. Monitor queue KPIs and resolve publish failures

Scheduling, real-time status, and analytics remain incremental goals documented in [08-implementation-roadmap.md](./08-implementation-roadmap.md).
