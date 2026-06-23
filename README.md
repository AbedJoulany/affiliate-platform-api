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

## Environment Variables

See `.env.example` for all configuration options. Change `JWT_SECRET_KEY` before deploying to production.

Set `TELEGRAM_BOT_TOKEN` to enable live bot permission checks against the Telegram Bot API. Without it, channels are stored with `bot_permission_status: unknown`.

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
