# Affiliate Platform API

Production-ready FastAPI backend for an affiliate marketing platform.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.0 (async)
- Alembic
- JWT authentication (access + refresh tokens)
- Pydantic v2
- Docker & Docker Compose

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
| **User** | Platform users (admin, affiliate, advertiser) |
| **Affiliate** | Affiliate profile with referral code and commission rate |
| **Campaign** | Advertiser offers with payout and landing URL |
| **AffiliateCampaign** | Enrollment linking affiliates to campaigns with tracking links |
| **Conversion** | Recorded sales/leads with commission calculation |
| **Product** | Affiliate product catalog with pricing, ratings, and status |
| **TelegramChannel** | Connected Telegram channels with bot permission status |

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login (OAuth2 form) |
| GET | `/api/v1/auth/me` | Current user profile |
| GET | `/api/v1/affiliates/me` | My affiliate profile |
| POST | `/api/v1/affiliates/join-campaign` | Join a campaign |
| GET | `/api/v1/campaigns/active` | List active campaigns |
| POST | `/api/v1/campaigns` | Create campaign (admin/advertiser) |
| POST | `/api/v1/conversions` | Record a conversion |
| GET | `/api/v1/conversions/me` | My conversions |
| GET | `/api/v1/products` | List products (pagination, title search, status filter) |
| GET | `/api/v1/products/{id}` | Get product by ID |
| POST | `/api/v1/products` | Create product (admin) |
| PATCH | `/api/v1/products/{id}` | Update product (admin) |
| DELETE | `/api/v1/products/{id}` | Delete product (admin) |
| POST | `/api/v1/channels` | Register Telegram channel (auth required) |
| GET | `/api/v1/channels` | List channels with pagination |
| PUT | `/api/v1/channels/{id}` | Update channel |
| DELETE | `/api/v1/channels/{id}` | Delete channel |
| POST | `/api/v1/ai-content/generate` | Generate Arabic marketing content by `product_id` or `url` |
| POST | `/api/v1/queues` | Create queue item |
| GET | `/api/v1/queues` | List queue items (filter by status, paginated) |
| GET | `/api/v1/queues/{id}` | Get queue item |
| PATCH | `/api/v1/queues/{id}` | Update queue item |
| POST | `/api/v1/queues/{id}/publish` | Publish queue item to Telegram |
| DELETE | `/api/v1/queues/{id}` | Delete queue item |
| POST | `/api/v1/aliexpress/import` | Import product from AliExpress Affiliate API |

## Environment Variables

See `.env.example` for all configuration options. Change `JWT_SECRET_KEY` before deploying to production.

Set `TELEGRAM_BOT_TOKEN` to enable live bot permission checks against the Telegram Bot API. Without it, channels are stored with `bot_permission_status: unknown`.

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

## Tests

```bash
pip install -e ".[dev]"
pytest
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
