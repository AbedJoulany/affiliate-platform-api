# Affiliate Platform API

AI affiliate marketing automation platform with a FastAPI backend and Next.js frontend.

## Product scope

The product is intentionally focused on one loop:

**Discover → Evaluate → Select → Create with AI → Review → Queue → Schedule → Publish → Measure**

This repository does **not** implement an affiliate network, advertiser portal, campaign enrollment system, conversion settlement, or commission/payout management.

## Stack

- Python 3.12 / FastAPI
- PostgreSQL 16 / SQLAlchemy 2.0 async / Alembic
- JWT access tokens + rotating opaque refresh tokens
- Pydantic v2
- Redis / Celery
- Next.js 15 / TypeScript / TanStack Query / TailwindCSS
- Docker / Docker Compose

## Core modules

- Authentication and user accounts
- Product discovery and AliExpress import
- Product catalog / product intelligence
- AI marketing content generation
- Publishing queue and scheduling
- Telegram channels and publishing
- Dashboard and operational analytics

## Documentation

| Doc | Topic |
| --- | --- |
| `docs/01-project-overview.md` | Vision and architecture |
| `docs/06-api-integration.md` | API contracts and frontend integration |
| `docs/08-implementation-roadmap.md` | Roadmap |
| `docs/10-production-readiness.md` | Release and security runbook |
| `docs/11-product-blueprint.md` | Current product boundaries and domain model |

## Architecture

```text
app/
├── auth/          # Authentication and sessions
├── api/           # HTTP routes
├── ai/            # AI providers and prompts
├── aliexpress/    # AliExpress integration
├── core/          # Config, database, enums
├── models/        # SQLAlchemy models
├── repositories/  # Data access
├── schemas/       # Pydantic contracts
├── services/      # Business logic
└── worker/        # Celery tasks
```

## Domain models

| Entity | Purpose |
| --- | --- |
| User | Platform account |
| Product | Product/opportunity being evaluated and promoted |
| TelegramChannel | Publishing destination |
| QueueItem | Marketing content waiting to be published |
| QueuePublishAttempt | Publishing attempt and operational history |
| RefreshToken | Rotating session credential |

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`  
Frontend: `http://localhost:3000`

## Authentication

Public registration creates a normal `USER` account. `ADMIN` is an operator role and is not an affiliate-network role.

The current session contract uses a short-lived JWT access token plus a single-use rotating opaque refresh token. Refresh tokens are stored hashed in PostgreSQL.

## API surface

Main routes are mounted below `/api/v1`:

- `/auth`
- `/products`
- `/channels`
- `/ai-content`
- `/queues`
- `/aliexpress`
- `/dashboard`

Operational root endpoints are `/health`, `/ready`, and `/worker/health`.

## Environment

See `.env.example`. Configure PostgreSQL, Redis/Celery, Telegram, AliExpress, and exactly one AI provider as required by the deployment environment.

## Tests

```bash
pytest
cd frontend
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```
