# Affiliate Platform API — Project Handoff Document

**Project:** `affiliate-platform-api`  
**Version:** 0.1.0  
**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy 2.0 · Alembic · Celery · Redis  
**Last updated:** June 2026

---

## 1. Project Purpose

This backend powers an **affiliate marketing platform** focused on:

- Managing affiliates, campaigns, and conversion tracking
- Building a **product catalog** (manual entry or AliExpress import)
- Generating **Arabic marketing content** via AI (OpenAI / Gemini)
- Connecting **Telegram channels** and publishing promotional posts
- Scheduling and automating content delivery through a **publish queue**

The platform is designed as a production-oriented API service with Docker-based deployment, async database access, and background workers for scheduled Telegram publishing.

---

## 2. Current Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────▶│  FastAPI API │────▶│   PostgreSQL    │
│  (future)   │     │  (uvicorn)   │     │   (asyncpg)     │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │  OpenAI  │ │  Gemini  │ │  Telegram    │
        │  API     │ │  API     │ │  Bot API     │
        └──────────┘ └──────────┘ └──────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌──────────┐            ┌──────────────┐
        │  Redis   │◀───────────│ Celery Beat  │
        │ (broker) │            │ + Worker     │
        └──────────┘            └──────────────┘
              │
              ▼
        ┌──────────────────┐
        │ AliExpress         │
        │ Affiliate API      │
        └──────────────────┘
```

### Layered design

| Layer | Responsibility |
|-------|----------------|
| **API** (`app/api/`) | HTTP routes, request validation, auth guards |
| **Services** (`app/services/`) | Business logic, orchestration |
| **Repositories** (`app/repositories/`) | Database queries (Repository pattern) |
| **Models** (`app/models/`, `app/auth/models.py`) | SQLAlchemy 2.0 ORM entities |
| **Schemas** (`app/schemas/`) | Pydantic v2 request/response DTOs |
| **Integrations** (`app/ai/`, `app/telegram/`, `app/aliexpress/`) | External API clients |
| **Workers** (`app/worker/`) | Celery tasks for background jobs |

### Key patterns

- **Async SQLAlchemy 2.0** with `asyncpg`
- **JWT Bearer authentication** (access tokens only)
- **Role-based access control** (`admin`, `affiliate`, `advertiser`)
- **Dependency injection** via FastAPI `Depends`
- **Alembic** for schema migrations

---

## 3. Folder Structure

```
affiliate-platform-api/
├── alembic/                    # Database migrations
│   └── versions/               # 001–005 migration files
├── app/
│   ├── ai/                     # AI provider abstraction (OpenAI, Gemini)
│   ├── aliexpress/             # AliExpress Affiliate API client & mapper
│   ├── api/
│   │   ├── deps.py             # Shared auth dependencies
│   │   ├── deps_aliexpress.py  # AliExpress DI
│   │   └── v1/                 # Versioned REST routes
│   ├── auth/                   # Authentication module (User, JWT, login)
│   ├── core/                   # Config, database, security re-exports
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # Data access layer
│   ├── schemas/                # Pydantic DTOs
│   ├── services/               # Business logic
│   ├── telegram/               # Telegram bot client & publisher
│   └── worker/                 # Celery app & tasks
├── tests/                      # pytest suite (minimal)
├── .env.example                # Environment variable template
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── HANDOFF.md                  # This document
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 4. Implemented Modules

### 4.1 Authentication (`app/auth/`)

| Feature | Status |
|---------|--------|
| User model (UUID, email, bcrypt password, roles) | ✅ |
| Register / Login / Me endpoints | ✅ |
| JWT access tokens | ✅ |
| FastAPI dependency injection (`CurrentUser`, `AuthServiceDep`) | ✅ |
| Refresh tokens | ❌ Not implemented (config field exists but unused) |

### 4.2 Affiliates (`app/services/affiliate.py`)

| Feature | Status |
|---------|--------|
| Affiliate profile with referral code | ✅ |
| Join campaign + tracking link generation | ✅ |
| Admin list affiliates | ✅ |

### 4.3 Campaigns (`app/services/campaign.py`)

| Feature | Status |
|---------|--------|
| CRUD (create, list, get, update) | ✅ |
| Public active campaigns listing | ✅ |
| Role-based create/update permissions | ✅ |

### 4.4 Conversions (`app/services/conversion.py`)

| Feature | Status |
|---------|--------|
| Record conversion with commission calculation | ✅ |
| Affiliate self-list / admin list | ✅ |
| Admin status updates (pending → approved → paid) | ✅ |

### 4.5 Products (`app/services/product.py`)

| Feature | Status |
|---------|--------|
| Full CRUD with pagination & title search | ✅ |
| Product status lifecycle (draft/active/inactive/archived) | ✅ |
| Score field on product | ✅ |

### 4.6 Telegram Channels (`app/services/channel.py`)

| Feature | Status |
|---------|--------|
| Channel CRUD | ✅ |
| Telegram channel ID validation (`@username` or `-100…`) | ✅ |
| Bot permission check via Telegram Bot API | ✅ |

### 4.7 AI Content (`app/services/ai_content.py`)

| Feature | Status |
|---------|--------|
| Provider abstraction (OpenAI, Gemini) | ✅ |
| Generate Arabic marketing content | ✅ |
| Input by `product_id` or product `url` | ✅ |
| URL metadata fetch for non-DB products | ✅ (HTML meta tags, not AliExpress API) |

### 4.8 Queue (`app/services/queue.py`)

| Feature | Status |
|---------|--------|
| Queue item CRUD | ✅ |
| Statuses: draft, queued, scheduled, published | ✅ |
| Scheduling with `scheduled_at` | ✅ |
| Manual publish endpoint | ✅ |
| Publishing fields (image, button, telegram_message_id) | ✅ |

### 4.9 Telegram Publishing (`app/telegram/publisher.py`)

| Feature | Status |
|---------|--------|
| Send text messages | ✅ |
| Send photo with caption | ✅ |
| Inline URL button | ✅ |
| Queue integration | ✅ |

### 4.10 Celery Workers (`app/worker/`)

| Feature | Status |
|---------|--------|
| Redis broker | ✅ |
| Periodic publish task (`process_publish_queue`) | ✅ |
| Auto-publish scheduled + queued items | ✅ |
| Single-item publish task | ✅ |

### 4.11 AliExpress Import (`app/services/aliexpress_import.py`)

| Feature | Status |
|---------|--------|
| Official Affiliate API client (MD5 signed) | ✅ |
| URL / product ID extraction | ✅ |
| Map to Product model + save to PostgreSQL | ✅ |
| Initial score calculation | ✅ |
| Update existing product on re-import | ✅ |

---

## 5. Pending Modules

These were discussed or are logical next steps but **are not implemented**:

| Module | Description |
|--------|-------------|
| **JWT refresh tokens** | `REFRESH_TOKEN_EXPIRE_DAYS` in config; no `/auth/refresh` endpoint |
| **Click tracking** | Track affiliate link clicks before conversions |
| **Payout / billing** | Pay affiliates for approved conversions |
| **Analytics dashboard API** | Aggregated stats, revenue, conversion rates |
| **Admin seed script** | Bootstrap first admin user |
| **Product image gallery** | AliExpress returns multiple images; only main image stored |
| **AliExpress bulk import** | Import by keyword/search via `product.query` API |
| **Affiliate auto-provisioning** | Auto-create affiliate profile on register (removed from current auth service) |
| **Channel GET by ID** | No single-channel fetch endpoint |
| **Rate limiting** | No API throttling middleware |
| **Email notifications** | Publish failures, conversion approvals |
| **CI/CD pipeline** | GitHub Actions or similar |
| **Frontend application** | No UI included |
| **Celery monitoring** | Flower or similar observability |
| **Webhook receivers** | AliExpress/Telegram inbound webhooks |
| **Production hardening** | HTTPS termination, secret rotation, structured logging |

---

## 6. Database Schema

**Engine:** PostgreSQL 16  
**Migrations:** `001` → `005` (run `alembic upgrade head`)

### Entity relationship overview

```
users ──┬── affiliates ──┬── affiliate_campaigns ── campaigns
        │                └── conversions ────────── campaigns
        └── campaigns (advertiser_id)

products ◀── queue_items ──▶ telegram_channels
```

### Tables

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| email | VARCHAR(255) | Unique |
| hashed_password | VARCHAR(255) | bcrypt |
| full_name | VARCHAR(255) | |
| role | ENUM | admin, affiliate, advertiser |
| is_active | BOOLEAN | |
| created_at, updated_at | TIMESTAMPTZ | |

#### `affiliates`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users, unique |
| company_name | VARCHAR(255) | Nullable |
| website | VARCHAR(512) | Nullable |
| referral_code | VARCHAR(32) | Unique |
| status | ENUM | pending, active, suspended, rejected |
| commission_rate | NUMERIC(5,2) | Default 10% |
| payout_details | TEXT | Nullable |

#### `campaigns`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | VARCHAR(255) | |
| description | TEXT | Nullable |
| advertiser_id | UUID | FK → users, nullable |
| status | ENUM | draft, active, paused, completed |
| payout_amount | NUMERIC(12,2) | |
| currency | VARCHAR(3) | Default USD |
| landing_url | VARCHAR(512) | |
| starts_at, ends_at | TIMESTAMPTZ | Nullable |

#### `affiliate_campaigns`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| affiliate_id | UUID | FK → affiliates |
| campaign_id | UUID | FK → campaigns |
| tracking_link | VARCHAR(512) | Unique pair (affiliate_id, campaign_id) |

#### `conversions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| affiliate_id | UUID | FK → affiliates |
| campaign_id | UUID | FK → campaigns |
| external_order_id | VARCHAR(128) | Unique |
| amount | NUMERIC(12,2) | |
| commission | NUMERIC(12,2) | Auto-calculated |
| currency | VARCHAR(3) | |
| status | ENUM | pending, approved, rejected, paid |
| click_id | VARCHAR(64) | Nullable |

#### `products`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| title | VARCHAR(255) | |
| price | NUMERIC(12,2) | |
| discount | NUMERIC(5,2) | Percentage 0–100 |
| rating | NUMERIC(3,2) | 0–5 scale |
| sales | INTEGER | |
| reviews | INTEGER | |
| image_url | VARCHAR(512) | |
| product_url | VARCHAR(512) | |
| score | NUMERIC(10,4) | Ranking score |
| status | ENUM | draft, active, inactive, archived |

#### `telegram_channels`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| telegram_channel_id | VARCHAR(64) | Unique (@username or -100…) |
| title | VARCHAR(255) | Nullable |
| username | VARCHAR(64) | Nullable |
| bot_permission_status | ENUM | unknown, pending, granted, partial, denied |
| can_post_messages | BOOLEAN | |
| can_edit_messages | BOOLEAN | |
| can_delete_messages | BOOLEAN | |
| permissions_checked_at | TIMESTAMPTZ | Nullable |
| permission_detail | VARCHAR(512) | Nullable |
| is_active | BOOLEAN | |

#### `queue_items`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| title | TEXT | Nullable |
| content | TEXT | Post body |
| status | ENUM | draft, queued, scheduled, published |
| scheduled_at | TIMESTAMPTZ | Required when scheduled |
| published_at | TIMESTAMPTZ | Nullable |
| channel_id | UUID | FK → telegram_channels, nullable |
| product_id | UUID | FK → products, nullable |
| image_url | VARCHAR(512) | Nullable |
| button_text | VARCHAR(128) | Nullable |
| button_url | VARCHAR(512) | Nullable |
| telegram_message_id | BIGINT | Nullable, set after publish |

---

## 7. API Endpoints

**Base URL:** `http://localhost:8000`  
**API prefix:** `/api/v1`  
**Docs:** `/docs` · **Health:** `/health`

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | Public | Register user |
| POST | `/api/v1/auth/login` | Public | OAuth2 form login → JWT |
| GET | `/api/v1/auth/me` | Bearer | Current user profile |

### Affiliates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/affiliates/me` | Bearer | My affiliate profile |
| POST | `/api/v1/affiliates` | Bearer | Create affiliate profile |
| PATCH | `/api/v1/affiliates/{id}` | Bearer | Update profile |
| POST | `/api/v1/affiliates/join-campaign` | Bearer | Join campaign |
| GET | `/api/v1/affiliates` | Admin | List affiliates |

### Campaigns

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/campaigns` | Admin/Advertiser | Create campaign |
| GET | `/api/v1/campaigns/active` | Public | List active campaigns |
| GET | `/api/v1/campaigns/{id}` | Public | Get campaign |
| GET | `/api/v1/campaigns` | Admin | List all campaigns |
| PATCH | `/api/v1/campaigns/{id}` | Bearer | Update campaign |

### Conversions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/conversions` | Public | Record conversion |
| GET | `/api/v1/conversions/me` | Bearer | My conversions |
| GET | `/api/v1/conversions` | Admin | List all conversions |
| PATCH | `/api/v1/conversions/{id}` | Admin | Update status |

### Products

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/products` | Admin | Create product |
| GET | `/api/v1/products` | Public | List (pagination, title, status) |
| GET | `/api/v1/products/{id}` | Public | Get product |
| PATCH | `/api/v1/products/{id}` | Admin | Update product |
| DELETE | `/api/v1/products/{id}` | Admin | Delete product |

### Telegram Channels

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/channels` | Bearer | Register channel |
| GET | `/api/v1/channels` | Bearer | List channels |
| PUT | `/api/v1/channels/{id}` | Bearer | Update channel |
| DELETE | `/api/v1/channels/{id}` | Bearer | Delete channel |

### AI Content

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/ai-content/generate` | Bearer | Generate Arabic content (`product_id` or `url`) |

### Queue

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/queues` | Bearer | Create queue item |
| GET | `/api/v1/queues` | Bearer | List queue items |
| GET | `/api/v1/queues/{id}` | Bearer | Get queue item |
| PATCH | `/api/v1/queues/{id}` | Bearer | Update queue item |
| POST | `/api/v1/queues/{id}/publish` | Bearer | Publish to Telegram now |
| DELETE | `/api/v1/queues/{id}` | Bearer | Delete queue item |

### AliExpress

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/aliexpress/import` | Admin | Import product via Affiliate API |

### Product Discovery & Import

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/products/discover` | Public | General discovery (filters, sort, optional `persist`) |
| GET | `/api/v1/products/discover/hot` | Public | Hot selling products |
| GET | `/api/v1/products/discover/deals` | Public | Featured promo / deals |
| GET | `/api/v1/products/discover/trending` | Public | Trending (smart match) |
| GET | `/api/v1/products/discover/category/{category_id}` | Public | Category browse |
| GET | `/api/v1/products/search` | Public | Keyword search |
| POST | `/api/v1/products/search/image` | Public | Image search interface (DS API) |
| POST | `/api/v1/products/import-url` | Admin | Import from URL |
| POST | `/api/v1/products/import` | Admin | Import by URL or product ID |
| POST | `/api/v1/products/import/batch` | Admin | Batch import |

---

## 8. Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_NAME` | No | Affiliate Platform API | Application name |
| `APP_ENV` | No | development | Environment |
| `DEBUG` | No | false | SQLAlchemy echo |
| `API_V1_PREFIX` | No | /api/v1 | Route prefix |
| `HOST` | No | 0.0.0.0 | Server bind |
| `PORT` | No | 8000 | Server port |
| `POSTGRES_USER` | Yes* | affiliate | DB user |
| `POSTGRES_PASSWORD` | Yes* | affiliate_secret | DB password |
| `POSTGRES_DB` | Yes* | affiliate_db | DB name |
| `POSTGRES_HOST` | Yes* | localhost | DB host |
| `POSTGRES_PORT` | No | 5432 | DB port |
| `DATABASE_URL` | Yes* | (assembled) | Async PostgreSQL URL |
| `JWT_SECRET_KEY` | **Yes (prod)** | change-me… | JWT signing secret |
| `JWT_ALGORITHM` | No | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | 30 | Token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | 7 | Unused (no refresh endpoint) |
| `CORS_ORIGINS` | No | ["http://localhost:3000"] | Allowed origins |
| `TELEGRAM_BOT_TOKEN` | For Telegram | — | Bot token from @BotFather |
| `TELEGRAM_API_BASE_URL` | No | api.telegram.org | Telegram API base |
| `AI_DEFAULT_PROVIDER` | No | openai | openai or gemini |
| `OPENAI_API_KEY` | For AI | — | OpenAI API key |
| `OPENAI_MODEL` | No | gpt-4o-mini | OpenAI model |
| `GEMINI_API_KEY` | For AI | — | Google Gemini key |
| `GEMINI_MODEL` | No | gemini-2.0-flash | Gemini model |
| `REDIS_HOST` | For Celery | localhost | Redis hostname |
| `REDIS_PORT` | No | 6379 | Redis port |
| `CELERY_BROKER_URL` | For Celery | redis://… | Celery broker |
| `CELERY_RESULT_BACKEND` | No | redis://… | Celery results |
| `CELERY_PUBLISH_INTERVAL_SECONDS` | No | 60 | Beat schedule interval |
| `CELERY_PUBLISH_BATCH_SIZE` | No | 50 | Max items per publish run |
| `ALIEXPRESS_APP_KEY` | For import | — | AliExpress Open Platform |
| `ALIEXPRESS_APP_SECRET` | For import | — | AliExpress app secret |
| `ALIEXPRESS_TRACKING_ID` | Recommended | — | Affiliate tracking ID |
| `ALIEXPRESS_API_URL` | No | https://api-sg.aliexpress.com/sync | Official IOP SDK gateway |
| `ALIEXPRESS_TARGET_CURRENCY` | No | USD | Price currency |
| `ALIEXPRESS_TARGET_LANGUAGE` | No | EN | API language |
| `ALIEXPRESS_COUNTRY` | No | US | Target country |
| `ALIEXPRESS_REQUEST_TIMEOUT` | No | 30.0 | HTTP timeout (seconds) |
| `ALIEXPRESS_MAX_RETRIES` | No | 3 | API retry attempts |
| `ALIEXPRESS_RATE_LIMIT_INTERVAL_SECONDS` | No | 0.2 | Min delay between API calls |
| `ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH` | No | false | Enable DS image search API |
| `CELERY_DISCOVERY_HOT_INTERVAL_SECONDS` | No | 21600 | Hot products refresh (6h) |
| `CELERY_DISCOVERY_TRENDING_INTERVAL_SECONDS` | No | 21600 | Trending refresh (6h) |
| `CELERY_DISCOVERY_CATEGORIES_INTERVAL_SECONDS` | No | 86400 | Category cache refresh (24h) |

\*Required for database connectivity.

---

## 9. Docker Services

```bash
docker compose up --build
```

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **api** | affiliate-api | 8000 | FastAPI + Alembic migrate on start |
| **db** | affiliate-db | 5432 | PostgreSQL 16 |
| **redis** | affiliate-redis | 6379 | Celery broker/backend |
| **celery-worker** | affiliate-celery-worker | — | Executes background tasks |
| **celery-beat** | affiliate-celery-beat | — | Schedules periodic publishing |

### Startup sequence

1. PostgreSQL and Redis become healthy
2. API runs `alembic upgrade head`, then Uvicorn with hot reload
3. Celery worker connects to Redis and processes tasks
4. Celery beat triggers `process_publish_queue` every 60 seconds

### Local (without Docker)

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Separate terminals:
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

---

## 10. Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Async SQLAlchemy 2.0** | Non-blocking I/O for FastAPI; scales with concurrent requests |
| **Repository + Service layers** | Separates HTTP, business logic, and data access for testability |
| **JWT access-only (no refresh yet)** | Simpler initial auth; refresh config reserved for future |
| **Pydantic v2** | Fast validation, OpenAPI schema generation |
| **Alembic migrations** | Version-controlled schema changes across environments |
| **Celery + Redis** | Reliable scheduled publishing without blocking API requests |
| **Official IOP SDK for AliExpress** | Uses vendored `iop.IopClient` / `iop.IopRequest` against `https://api-sg.aliexpress.com/sync`; signing and timestamps are handled by the SDK |
| **Single `image_url` on Product** | Simplifies model; AliExpress multi-image stored only as primary |
| **Score formula (rating/sales/discount/reviews)** | Weighted heuristic for product ranking in catalog |
| **GMT+8 timestamps for AliExpress** | API requirement (Asia/Shanghai timezone) |
| **Enum as VARCHAR (native_enum=False)** | Avoids PostgreSQL enum migration pain |
| **Lazy DB engine init** | Prevents circular imports in `database.py` |
| **OAuth2 password form for login** | FastAPI/Swagger compatible token flow |

---

## 11. Known Issues

| Issue | Severity | Details |
|-------|----------|---------|
| **Debug prints in auth service** | High | `app/auth/service.py` logs password length/value on register — **remove before production** |
| **No JWT refresh endpoint** | Medium | `REFRESH_TOKEN_EXPIRE_DAYS` configured but unused |
| **AliExpress API gateway** | Low | Default is `https://api-sg.aliexpress.com/sync` via official IOP SDK; override with `ALIEXPRESS_API_URL` if your app uses a different region |
| **Silent Celery publish failures** | Medium | Failed queue items are skipped without retry logging in `publish_due_scheduled` |
| **Single product image** | Low | AliExpress import discards secondary images |
| **No `aliexpress_product_id` column** | Low | Dedup relies on `product_url` matching only |
| **Limited test coverage** | Low | Only health check + OpenAPI smoke test (`tests/`) |
| **AI URL fetch is HTML meta parsing** | Info | `/ai-content/generate` with `url` uses page meta tags, not AliExpress API |
| **No admin bootstrap** | Info | First admin must be registered manually with `role=admin` |
| **Celery beat single instance** | Info | Running multiple beat processes will duplicate schedules |
| **Default JWT secret** | Critical (prod) | Default `change-me…` must be replaced in production |
| **Conversion endpoint is public** | Info | `POST /conversions` has no auth — intentional for tracking pixels but abusable |

---

## 12. Quick Reference Commands

```bash
# Run all services
docker compose up --build

# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run tests
pip install -e ".[dev]"
pytest

# Manual Celery publish
python -c "from app.worker.tasks.publishing import process_publish_queue; process_publish_queue.delay()"
```

---

## 13. Handoff Checklist

- [ ] Copy `.env.example` → `.env` and fill all secrets
- [ ] Remove debug print statements from `app/auth/service.py`
- [ ] Change `JWT_SECRET_KEY` for non-dev environments
- [ ] Register AliExpress Open Platform app and set API credentials
- [ ] Create Telegram bot via @BotFather and add as channel admin
- [ ] Run `alembic upgrade head` on target database
- [ ] Verify `docker compose up` — all 5 services healthy
- [ ] Test `/health` and `/docs`
- [ ] Register admin user and test import → AI content → queue → publish flow

---

*End of handoff document.*
