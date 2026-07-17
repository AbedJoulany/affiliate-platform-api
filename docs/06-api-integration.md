# API Integration Guide v1.0

**Backend contract source:** current FastAPI routers and Pydantic schemas  
**Default development origin:** `http://localhost:8000`  
**API base URL:** `http://localhost:8000/api/v1`

The frontend should configure the origin through an environment variable such as
`NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`. Do not append `/api/v1` again in
individual feature clients.

Interactive contract references are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check (outside the versioned API): `GET /health` → `{"status":"ok"}`
- Readiness check (outside the versioned API): `GET /ready` verifies PostgreSQL and Redis,
  returns `200` when both are up and `503` otherwise

## 1. Authentication

### Login

`POST /auth/login` uses `application/x-www-form-urlencoded`, not JSON.

| Form field | Value |
| --- | --- |
| `username` | The user's email address |
| `password` | The user's password |

Example:

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=user%40example.com&password=correct-horse-battery-staple
```

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Send the token on protected requests:

```http
Authorization: Bearer <jwt>
```

Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes by default). The
backend currently has no refresh-token endpoint and does not issue a refresh token.
On an authentication `401`, clear local authentication state and send the user to login.
Logging out is a frontend operation that discards the access token.

### Current user

`GET /auth/me` requires bearer authentication and returns:

```json
{
  "id": "<uuid>",
  "email": "user@example.com",
  "full_name": "Example User",
  "role": "affiliate",
  "is_active": true,
  "created_at": "<ISO-8601 datetime>",
  "updated_at": "<ISO-8601 datetime>"
}
```

### Public registration

`POST /auth/register` is public and accepts JSON containing only:

- `email`: valid email
- `password`: 8–128 characters
- `full_name`: 1–255 characters

All public registrations create an `affiliate` user. `role` is not accepted; privileged
users must be provisioned through trusted administration or database operations, not this
endpoint. Success is `201` with the current-user shape above.

## 2. Errors and validation

Application errors use:

```json
{
  "detail": "Human-readable message"
}
```

Typical statuses:

- `400`: invalid business input
- `401`: missing, invalid, expired, or inactive-user token
- `403`: authenticated but insufficient role or ownership
- `404`: resource not found
- `409`: duplicate or conflicting state
- `422`: request/form/query validation failure; FastAPI returns `detail` as a list of
  validation error objects
- `501`: AliExpress image search is not enabled/supported
- `502`: upstream AliExpress failure

Do not depend on message text for control flow. Branch on HTTP status and keep the returned
detail for user feedback or diagnostics.

## 3. Pagination

Two pagination contracts currently exist.

Standard paginated resources (`products`, `channels`, and `queues`) accept zero-based
`skip` and `limit` and return:

```json
{
  "items": [],
  "total": 0,
  "skip": 0,
  "limit": 20
}
```

- Default `limit`: 20
- Maximum `limit`: 200

Affiliate, campaign, and conversion list endpoints also accept `skip` and `limit`, but
currently return a bare JSON array with no total.

Discovery endpoints accept one-based `page` and `page_size` (default 1 and 20, maximum 50)
and return `items`, `total`, `skip`, `limit`, `page`, `total_pages`, `mode`, `sort`, and
`persisted_count`.

## 4. MVP endpoint contract

Access labels below are: **Public**, **Bearer**, **Admin**, or the named role.

### Authentication

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/auth/register` | Public | JSON `email`, `password`, `full_name`; `201 UserRead` |
| POST | `/auth/login` | Public | Form `username`, `password`; returns bearer token |
| GET | `/auth/me` | Bearer | Returns `UserRead` |

### Products

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| GET | `/products` | Public | Filters `title`, `status`, `skip=0`, `limit=20`; paginated `ProductRead` |
| GET | `/products/{product_id}` | Public | Returns `ProductRead` |
| POST | `/products` | Admin | `ProductCreate`; `201 ProductRead` |
| PATCH | `/products/{product_id}` | Admin | Partial `ProductUpdate`; returns `ProductRead` |
| DELETE | `/products/{product_id}` | Admin | Returns `{"message":"Product deleted successfully"}` |

`ProductCreate` requires `title`, non-negative `price`, `image_url`, and `product_url`.
Optional/defaulted fields are `discount` (0–100), `rating` (0–5), `sales`, `reviews`,
`score`, and `status`. Updates accept the same fields as optional values. `ProductRead`
also exposes AliExpress enrichment fields: `aliexpress_product_id`, `description`,
`original_price`, `gallery_images`, `affiliate_url`, `category`, `store_name`, `currency`,
`commission_rate`, `shipping_info`, and `last_synced_at`.

### Dashboard

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| GET | `/dashboard` | Bearer | Product, queue, and channel counts; recent product/queue activity; DB status |

Counts include `total` plus `by_status` maps using the canonical product and queue enums.
Channel counts include `total`, `active`, and `inactive`. Recent activity items identify
the resource type/ID, title, status, and occurrence time.

### Product discovery and import

Discovery list filters are `category_id`, `min_rating`, `min_orders`, `min_price`,
`max_price`, `min_discount`, `shipping_country` (two characters), `currency` (three
characters), `choice_only`, `free_shipping`, `keywords`, `sort`, `page`, `page_size`,
`persist`, and `promotion_name`.

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| GET | `/products/discover` | Public | General discovery filters; `ProductDiscoveryResponse` |
| GET | `/products/discover/hot` | Public | Hot products; same response |
| GET | `/products/discover/deals` | Public | Deals; same response |
| GET | `/products/discover/trending` | Public | Trending products; same response |
| GET | `/products/discover/category/{category_id}` | Public | Category discovery; same response |
| GET | `/products/search` | Public | Requires `q`; supports discovery filters except `keywords`/`promotion_name` |
| POST | `/products/search/image` | Public | Exactly one of `image_url` or `image_base64`; optional `page`, `page_size`, `persist` |
| POST | `/products/import-url` | Admin | JSON `{"url":"..."}`; `201` if created, otherwise `200` |
| POST | `/products/import` | Admin | Exactly one of `url` or numeric `product_id`; `201` or `200` |
| POST | `/products/import/batch` | Admin | `product_ids`: 1–50 numeric strings; returns counts and products |
| POST | `/aliexpress/import` | Admin | Exactly one of `url` or numeric `product_id`; `201` or `200` |
| GET | `/aliexpress/categories` | Bearer | Cached AliExpress categories, total, and latest sync time |

Setting `persist=true` writes discovered products to the product store; leave it false for
browsing. Import responses contain `product`, `aliexpress_product_id`, `imported`, and
`image_count`. Batch responses contain `imported`, `updated`, `failed`, and `products`.
Category items contain numeric `category_id`, `category_name`, `parent_category_id`, and
`synced_at`.

### AI content

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/ai-content/generate` | Bearer | Exactly one of `product_id` or `url`; optional `provider` |

The response contains nullable `product_id`, nullable `source_url`, `provider`, and Arabic
marketing `content`. Providers are `openai` and `gemini`.

### Publishing queue

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/queues` | Bearer | `QueueCreate`; `201 QueueRead` |
| GET | `/queues` | Bearer | `status`, `skip=0`, `limit=20`; paginated |
| GET | `/queues/{queue_id}` | Bearer | Returns `QueueRead` |
| PATCH | `/queues/{queue_id}` | Bearer | Partial `QueueUpdate` |
| POST | `/queues/{queue_id}/publish` | Bearer | Returns publish receipt |
| DELETE | `/queues/{queue_id}` | Bearer | Returns a message |

Queue input supports `title`, required `content`, `status`, `scheduled_at`, `channel_id`,
`product_id`, `image_url`, `button_text`, and `button_url`. A scheduled item requires
`scheduled_at`. Button text and URL must be supplied together. A publish receipt contains
`queue_id`, `telegram_message_id`, `chat_id`, `message_type`, and `published_at`.

### Telegram channels

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/channels` | Bearer | `telegram_channel_id`, optional `title`, `is_active`; `201` |
| GET | `/channels` | Bearer | `skip=0`, `limit=20`; paginated |
| PUT | `/channels/{channel_id}` | Bearer | Partial channel fields |
| DELETE | `/channels/{channel_id}` | Bearer | Returns a message |

Channel responses include normalized Telegram ID, title/username, permission status,
post/edit/delete permission flags, permission check time/detail, and active state.

## 5. Supporting backend endpoints

These routes exist in the current backend even though campaigns and conversions are beyond
the frontend MVP described in the roadmap.

### Affiliates

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/affiliates` | Affiliate bearer | Create own profile; `201` |
| GET | `/affiliates/me` | Bearer | Return own affiliate profile |
| PATCH | `/affiliates/{affiliate_id}` | Owner or admin | Partial profile update |
| POST | `/affiliates/join-campaign` | Bearer | JSON `campaign_id`; `201` tracking link |
| GET | `/affiliates` | Admin | `skip=0`, `limit=100`; bare array |

An affiliate owner may update `company_name`, `website`, and `payout_details`. Only an admin
may update `status` or `commission_rate`; an affiliate request containing either field
returns `403`.

### Campaigns

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/campaigns` | Admin or advertiser | Create campaign; `201` |
| GET | `/campaigns/active` | Public | `skip=0`, `limit=100`; bare array |
| GET | `/campaigns/{campaign_id}` | Public | Return campaign |
| GET | `/campaigns` | Admin | `skip=0`, `limit=100`; bare array |
| PATCH | `/campaigns/{campaign_id}` | Bearer; service enforces ownership/role | Partial update |

Create requires `name`, positive `payout_amount`, and `landing_url`; it accepts optional
`description`, three-character `currency` (default USD), `starts_at`, and `ends_at`.

### Conversions

| Method | Path | Access | Contract |
| --- | --- | --- | --- |
| POST | `/conversions` | Public | Record conversion; `201` |
| GET | `/conversions/me` | Bearer | Affiliate conversions; bare array |
| GET | `/conversions` | Admin | All conversions; bare array |
| PATCH | `/conversions/{conversion_id}` | Admin | JSON `status`; returns conversion |

Conversion creation requires `affiliate_id`, `campaign_id`, `external_order_id`, and a
positive `amount`; `currency` defaults to USD and `click_id` is optional.

## 6. Current enums

- User role: `admin`, `affiliate`, `advertiser`
- Affiliate status: `pending`, `active`, `suspended`, `rejected`
- Campaign status: `draft`, `active`, `paused`, `completed`
- Conversion status: `pending`, `approved`, `rejected`, `paid`
- Product status: `draft`, `active`, `inactive`, `archived`
- Queue status: `draft`, `queued`, `scheduled`, `published`
- Telegram bot permission: `unknown`, `pending`, `granted`, `partial`, `denied`
- AI provider: `openai`, `gemini`
- Discovery mode: `general`, `hot`, `deals`, `big_discount`, `choice`, `category`,
  `keyword`, `commission`, `trending`
- Product sort: `orders_desc`, `rating_desc`, `discount_desc`, `price_asc`, `price_desc`,
  `newest`, `commission_desc`

## 7. Frontend integration pattern

Keep transport concerns in the shared Axios client and feature contracts in feature-owned
API modules, matching the documented feature-based frontend architecture.

```ts
import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { Accept: "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401) {
    clearAccessToken();
    redirectToLogin();
  }
  return Promise.reject(error);
});
```

Submit login as form data:

```ts
const body = new URLSearchParams({ username: email, password });
const { data } = await api.post<TokenResponse>("/auth/login", body, {
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
});
```

TanStack Query keys should include every server-side filter:

```ts
useQuery({
  queryKey: ["products", { title, status, skip, limit }],
  queryFn: () => productsApi.list({ title, status, skip, limit }),
});
```

After mutations, invalidate the smallest relevant resource keys (for example
`["products"]`, `["queues"]`, or `["channels"]`). Use the server's `total`, `skip`, and
`limit` for standard list controls, and `page`/`total_pages` for discovery. Keep enum
strings in shared TypeScript unions or generated OpenAPI types so invalid UI states cannot
be submitted.

Because channel and queue routes are currently authenticated but not scoped by user in the
HTTP contract, the frontend must not imply tenant isolation that the backend does not
enforce. Treat backend authorization as authoritative and still hide role-ineligible
actions for usability.
