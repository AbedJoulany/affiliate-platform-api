# Affiliate Platform API

Product A is a single-operator Affiliate Marketing Assistant MVP with a FastAPI backend and Next.js frontend. It supports AliExpress discovery, deterministic recommendations, AI content, a provider-aware Queue, Telegram, and Facebook Pages. It is not a SaaS marketplace.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.0 (async)
- Alembic
- JWT authentication with short-lived access tokens and rotating opaque refresh tokens
- Pydantic v2
- Docker & Docker Compose
- Next.js 15, TypeScript, TanStack Query, and TailwindCSS

## Documentation

Full project documentation lives in [`docs/`](./docs/):

| Doc | Topic |
| --- | --- |
| [01-project-overview.md](./docs/01-project-overview.md) | Vision, architecture, tech stack |
| [02-Frontend-Architecture.md](./docs/02-Frontend-Architecture.md) | Frontend structure & workspaces |
| [03-design-system.md](./docs/03-design-system.md) | Visual tokens & patterns |
| [04-component-library.md](./docs/04-component-library.md) | Component registry |
| [05-routing-and-navigation.md](./docs/05-routing-and-navigation.md) | Routes & navigation |
| [06-api-integration.md](./docs/06-api-integration.md) | API contracts & integration status |
| [07-development-guidelines.md](./docs/07-development-guidelines.md) | Coding standards |
| [08-implementation-roadmap.md](./docs/08-implementation-roadmap.md) | Feature checklist & roadmap |
| [09-cursor-prompts.md](./docs/09-cursor-prompts.md) | AI development prompts |
| [10-production-readiness.md](./docs/10-production-readiness.md) | Release & security runbook |
| [product-a-mvp-roadmap.md](./docs/product-a-mvp-roadmap.md) | Canonical Product A roadmap and acceptance gates |

## Architecture

```
app/
├── auth/          # Authentication module (User, JWT, login/register/me)
├── api/           # HTTP routes and dependencies
├── core/          # Config, database
├── models/        # SQLAlchemy ORM models
├── repositories/  # Data access layer
├── schemas/       # Pydantic request/response models
└── services/      # Business logic layer
```

## Domain Models

| Entity | Description |
|--------|-------------|
| **User** | Platform users (`admin` or `user`) |
| **Product** | Shared product catalog with pricing, AliExpress `affiliate_url`, and `commission_rate` |
| **TelegramChannel** | Connected Telegram channels with bot permission status |
| **FacebookPage** | Workspace-scoped manually connected Page with encrypted server-side token |
| **QueueItem** | Provider-aware scheduled or published Telegram/Facebook post |
| **QueuePublishAttempt** | Provider-specific attempt history, including failed and ambiguous outcomes |

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Frontend: http://localhost:3000

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Start PostgreSQL (or use docker compose up db)
alembic upgrade head
uvicorn app.main:app --reload
```

## Authentication Module

Located at `app/auth/`:

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy `User` model |
| `security.py` | bcrypt password hashing, JWT access tokens |
| `repository.py` | User data access (SQLAlchemy 2.0 async) |
| `service.py` | Register and login business logic |
| `dependencies.py` | `get_auth_service`, `get_current_user`, `CurrentUser` |
| `router.py` | `/register`, `/login`, `/me` endpoints |
| `schemas.py` | Pydantic v2 request/response models |

Protected routes inject the current user via FastAPI dependencies:

```python
from app.auth.dependencies import CurrentUser

@router.get("/example")
async def example(current_user: CurrentUser):
    return current_user.email
```

The backend issues short-lived access tokens and rotating opaque refresh tokens. Refresh
tokens are stored as hashes server-side, are single-use, and are never sent as Bearer
tokens. Public registration exists at the API level, but the single-operator MVP does
not provide public onboarding UI.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login (OAuth2 form) |
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/auth/refresh` | Rotate an opaque refresh token |
| POST | `/api/v1/auth/logout` | Revoke a refresh token |
| GET | `/api/v1/products` | List products (pagination, title search, status filter) |
| GET | `/api/v1/products/{id}` | Get product by ID |
| POST | `/api/v1/products` | Create product (admin) |
| PATCH | `/api/v1/products/{id}` | Update product (admin) |
| DELETE | `/api/v1/products/{id}` | Delete product (admin) |
| POST | `/api/v1/channels` | Register Telegram channel (auth required) |
| GET | `/api/v1/channels` | List channels with pagination |
| PUT | `/api/v1/channels/{id}` | Update channel |
| DELETE | `/api/v1/channels/{id}` | Delete channel |
| POST | `/api/v1/channels/{id}/refresh-permissions` | Refresh Telegram bot permissions |
| GET/POST | `/api/v1/facebook/pages` | List or connect Facebook Pages |
| POST | `/api/v1/facebook/pages/{id}/validate` | Revalidate a Page token |
| PATCH/DELETE | `/api/v1/facebook/pages/{id}` | Replace, disable, or remove a Page connection |
| POST | `/api/v1/ai-content/generate` | Manual AI Studio generation by `product_id` or `url` |
| POST | `/api/v1/automation/content/preview` | Explicit, paid, stateless generation preview for up to two server-selected products |
| POST | `/api/v1/automation/queue/prepare` | Explicit, cost-confirmed preparation of up to two validated products as scheduled Queue items; `execution_available` remains false |
| GET | `/api/v1/products/recommendations` | Authenticated deterministic recommendations |
| POST | `/api/v1/queues` | Create queue item |
| GET | `/api/v1/queues` | List queue items (filter by status, paginated) |
| GET | `/api/v1/queues/{id}` | Get queue item |
| PATCH | `/api/v1/queues/{id}` | Update queue item |
| POST | `/api/v1/queues/{id}/publish` | Publish queue item to its configured Telegram or Facebook destination |
| GET | `/api/v1/queues/{id}/attempts` | Provider-specific publish-attempt history |
| DELETE | `/api/v1/queues/{id}` | Delete queue item |
| POST | `/api/v1/aliexpress/import` | Import product from AliExpress Affiliate API |

## Environment Variables

See `.env.example` for the baseline configuration options. The Facebook encryption
key is documented below and remains a local/server-only addition because the
pre-existing `.env.example` is intentionally preserved unchanged. Change
`JWT_SECRET_KEY` before deploying to production.

Set `TELEGRAM_BOT_TOKEN` to enable live bot permission checks against the Telegram Bot API. Without it, channels are stored with `bot_permission_status: unknown`.

Facebook Page tokens are entered through the authenticated Pages UI and remain encrypted
server-side. `FACEBOOK_TOKEN_ENCRYPTION_KEY` must be configured for Page credentials;
generate a 32-byte URL-safe Base64 key and keep it outside Git. The key is not recoverable
from the database.

Configure `OPENAI_API_KEY` or `GEMINI_API_KEY` and set `AI_DEFAULT_PROVIDER` (`openai` or `gemini`) for AI content generation.

Set `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, and optionally `ALIEXPRESS_TRACKING_ID` to import products via the official AliExpress Affiliate API.

AliExpress requests use the **official IOP SDK** (`iop.IopClient`, `iop.IopRequest`) against `https://api-sg.aliexpress.com/sync`. The SDK owns signing, timestamps, and HTTP transport — the application does not use `httpx` or manual MD5 signing for AliExpress calls.

## Celery & Scheduled Publishing

Background workers use **Redis** as the Celery broker and automatically publish queue items:

| Task | Schedule | Action |
|------|----------|--------|
| `process_publish_queue` | Every 60s (configurable) | Publishes due **scheduled** posts and ready **queued** posts |
| `refresh_hot_products` | Every 6 hours | Syncs hot AliExpress products into the catalog |
| `refresh_trending_products` | Every 6 hours | Syncs trending AliExpress products into the catalog |
| `refresh_categories` | Every 24 hours | Refreshes cached AliExpress category tree |

### Docker (recommended)

```bash
docker compose up --build
```

This starts:
- `redis` — Celery broker
- `celery-worker` — executes publish tasks
- `celery-beat` — schedules periodic publishing

### Local development

```bash
# Terminal 1 — Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2 — Worker
celery -A app.worker.celery_app worker --loglevel=info

# Terminal 3 — Beat scheduler
celery -A app.worker.celery_app beat --loglevel=info
```

### Environment

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_PUBLISH_INTERVAL_SECONDS=60
CELERY_PUBLISH_BATCH_SIZE=50
```

### Manual task trigger

```python
from app.worker.tasks.publishing import process_publish_queue, publish_queue_item_task

process_publish_queue.delay()
publish_queue_item_task.delay("queue-item-uuid")
```

## Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

The current migration head is `022` (Phase 9B.4 AI usage reservations). Historical
migrations `001–022` must not be edited; new schema changes require a later additive
migration and verified downgrade path.

## Tests

```bash
pip install -e ".[dev]"
pytest

cd frontend
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

## AliExpress Product Discovery

Official AliExpress Affiliate/Open Platform APIs only (no scraping). Discovery routes are mounted under `/api/v1/products` **before** the `/{product_id}` CRUD route.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/products/discover` | Public | General discovery with filters/sort |
| GET | `/products/discover/hot` | Public | Hot selling products |
| GET | `/products/discover/deals` | Public | Featured promo / best deals |
| GET | `/products/discover/trending` | Public | Smart-match trending products |
| GET | `/products/discover/category/{category_id}` | Public | Products by category |
| GET | `/products/search` | Public | Keyword search |
| POST | `/products/search/image` | Public | Image search (DS API; disabled by default) |
| POST | `/products/import-url` | Admin | Import product from AliExpress URL |
| POST | `/products/import` | Admin | Import by URL or product ID |
| POST | `/products/import/batch` | Admin | Batch import by product IDs |

Use `persist=true` on discovery/search endpoints to upsert results into PostgreSQL. Product score uses **40% rating · 30% orders · 20% discount · 10% reviews**.

Configure AliExpress credentials and optional discovery tuning in `.env` (see `.env.example`).

### IOP SDK layout

| Path | Purpose |
|------|---------|
| `iop/` | Official AliExpress Open Platform IOP SDK (vendored) |
| `app/aliexpress/api_client.py` | Async adapter: builds `IopRequest`, executes via SDK, retries/rate-limits |
| `app/aliexpress/client.py` | Affiliate-specific API methods (import, discovery) |
