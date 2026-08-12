# Phase D — Authentication & Public-Endpoint Security Design

**Status:** Task 0 — Architecture decision. Design only. No implementation performed.
**Precedes:** [phase-d-analysis-and-roadmap.md](./phase-d-analysis-and-roadmap.md) (Phase D selection/charter — read first for *why* Phase D exists).
**This document answers:** *how* Phase D's four charter gaps should be closed, in a form Tasks 1–6 can implement directly without further architectural discovery.

---

## 1. Executive Summary

The repository was inspected directly (not assumed from prior documentation) to resolve the ten architectural decisions Phase D's implementation tasks depend on. The headline findings:

- **No token/session persistence of any kind exists today.** There is no `refresh_token`, `session`, or `api_key` table anywhere in `app/models/`. Refresh tokens must be designed from zero, not extended from an existing partial implementation.
- **The exact authorization primitive Task 4 needs already exists and is already proven in this codebase** — `AffiliateRepository.get_by_user_id(user.id)`, used today by `ConversionService.list_for_affiliate` to resolve "the calling user's own affiliate record." `record_conversion` (the vulnerable path) simply never calls it. This is a reuse, not an invention.
- **Redis, in this repository, is used exclusively for ephemeral/operational state** — Celery broker/backend, the `queue-events` Pub/Sub channel, and a 90-second-TTL heartbeat key. It has never been used as a durable source of truth for anything security- or business-critical; that role is consistently PostgreSQL's (`QueuePublishAttempt`, `Conversion`, etc.). This project-established convention directly drives Decision 1 (§5).
- **The project already has a proven pattern for avoiding Redis-outage cascading failures**: `WorkerHealthService` degrades to `"unknown"` rather than raising; the SSE `EventPublisher`'s Redis failures are logged, not fatal. Decision 6 (§10) follows this existing precedent rather than inventing a new failure philosophy.
- **`app/main.py` deliberately avoids `BaseHTTPMiddleware`** for `SecurityHeadersMiddleware`, specifically because it would buffer and break the SSE response (A.2). This is a hard architectural constraint that rules out global rate-limiting middleware and drives Decision 4 (§8) toward a route-scoped dependency instead.
- **`app/services/exceptions.py`'s `ServiceError` hierarchy already auto-maps to HTTP responses** via `app.main`'s global exception handler. A new `TooManyRequestsError(status_code=429)` slots into this existing mechanism with zero new wiring.
- **Zero backend tests exist today for authentication or conversions** (`tests/test_auth*.py` and `tests/test_conversion*.py` both return no matches). Every future task in this phase starts from a true zero baseline on these two subjects — there is no existing test suite to accidentally break, only one to build for the first time.

All ten decisions below are resolved to a single recommendation each, with alternatives explicitly rejected and evidenced.

---

## 2. Repository Security Baseline

Verified directly (2026-08-12, branch `cursor/phase-c-prime-retry-hardening`):

| Area | Current state | Evidence |
| --- | --- | --- |
| Auth mechanism | Access-token-only JWT, HS256, `python-jose` | `app/auth/security.py` |
| Access token TTL | 30 minutes (`access_token_expire_minutes`) | `app/core/config.py:36` |
| Refresh token | Config field exists (`refresh_token_expire_days: int = 7`), **read nowhere else in `app/`** | `app/core/config.py:37`; repo-wide grep confirms no other reference |
| JWT secret | Hardcoded default `"change-me-to-a-long-random-secret-in-production"`, **zero startup or runtime validation anywhere** | `app/core/config.py:34` |
| Password hashing | `bcrypt`, 12 rounds, correct for passwords | `app/auth/security.py:hash_password` |
| Token type discriminator | Already present and enforced: `{"sub", "exp", "type": "access"}`; `decode_access_token` raises if `type != "access"` | `app/auth/security.py:25-63` |
| `CurrentUser` dependency | Decodes, checks `type == "access"` (via `decode_access_token`), loads user, checks `is_active` | `app/auth/dependencies.py:33-51` |
| Role-based authorization | `require_roles(*roles)` factory, already used for admin-gated routes (products delete, conversions admin routes) | `app/auth/dependencies.py:58-66` |
| Rate limiting | **None found anywhere in `app/`.** Only rate limiting in the repo is AliExpress's own *outbound* client gate (`app/aliexpress/api_client.py`), which protects AliExpress from this app, not this app's routes from callers | Repo-wide grep for `rate.?limit`, `slowapi`, `limiter` |
| `POST /conversions` auth | **No `Depends` on any auth dependency at all** — fully anonymous | `app/api/v1/conversions.py:18-26` |
| `POST /conversions` amount trust | `amount: Decimal = Field(gt=0)` accepted verbatim from the request body and used directly to compute `commission` | `app/schemas/conversion.py:14`; `app/services/conversion.py:44-46` |
| User↔Affiliate relationship | One-to-one, enforced by a `unique=True` FK (`affiliates.user_id`) | `app/models/affiliate.py:21-25` |
| Existing ownership-resolution pattern | `AffiliateRepository.get_by_user_id(user.id)`, already used in `ConversionService.list_for_affiliate` | `app/services/conversion.py:76-91` |
| Session/token persistence | **No table exists** — `app/models/` has 11 files, none named `session`, `token`, or `api_key` | `Glob app/models/*.py` |
| Redis client pattern | No shared dependency/pool; every consumer calls `redis.asyncio.from_url(settings.broker_url, ...)` independently | `app/main.py:59`, `app/services/worker_health.py:67`, `app/worker/tasks/publishing.py` |
| Redis key/channel naming | Two conventions in use: colon-namespaced point keys (`celery:health:heartbeat`), hyphenated Pub/Sub channels (`queue-events`) | `app/worker/tasks/health.py`, `app/events/publisher.py:13` |
| Redis failure philosophy (existing) | **Degrade gracefully, never hard-fail a dependent feature** — `WorkerHealthService` returns `"unknown"` on Redis read failure; `EventPublisher` logs Redis publish failures without rolling back the domain mutation | `app/services/worker_health.py:32-36`; `docs/10-production-readiness.md` §9.1 |
| Global middleware constraint | `SecurityHeadersMiddleware` is deliberately pure ASGI (not `BaseHTTPMiddleware`) specifically to avoid buffering the SSE response body | `app/main.py:25-52` (docstring explains why) |
| Error-to-HTTP mapping | `ServiceError` subclasses auto-map via one global handler; `NotFoundError`(404), `ConflictError`(409), `UnauthorizedError`(401), `ForbiddenError`(403), `ValidationError`(422) already exist | `app/services/exceptions.py`; `app/main.py:94-96` |
| Migration numbering | Sequential, zero-padded 3-digit (`001`…`008`); next would be `009` | `alembic/versions/*.py` |
| Model conventions | `Base` + `UUIDPrimaryKeyMixin` + `TimestampMixin`; `Enum(..., native_enum=False)`; indexed FKs; `uq_*`-named unique constraints | `app/core/model_mixins.py`; `app/models/affiliate.py` |
| Frontend session storage | Access token in `sessionStorage` only; non-`httpOnly` presence-marker cookie for middleware redirect only | `frontend/src/services/session.ts` |
| Frontend 401 handling | Axios response interceptor clears session and redirects to `/login` on any 401 except from `/auth/login` itself | `frontend/src/services/api-client.ts:26-46` |
| Frontend refresh assumptions | **None** — no refresh logic, no token-expiry pre-emption, no retry-after-401 logic exists today | Same file, full read |
| Backend auth/conversion tests | **Zero files** — `tests/test_auth*.py` and `tests/test_conversion*.py` both match nothing | `Glob` results, this session |
| New dependency needed? | **No** — `redis>=5.2.0` (async client), `python-jose[cryptography]`, `bcrypt` already in `requirements.txt`; a hand-rolled `INCR`/`EXPIRE` counter and a `hashlib.sha256` hash need nothing new | `requirements.txt` |

---

## 3. Current Authentication Architecture

```text
POST /auth/login (form: username=email, password)
    → AuthService.login
        → verify_password (bcrypt)
        → create_access_token(user.id)
            → {"sub": str(user_id), "exp": now+30min, "type": "access"}
            → jwt.encode(HS256, settings.jwt_secret_key)
    ← TokenResponse{access_token, token_type="bearer"}

Authenticated request (Authorization: Bearer <access_token>)
    → get_current_user
        → decode_access_token
            → jwt.decode(HS256, settings.jwt_secret_key)
            → reject if payload["type"] != "access"
        → UserRepository.get_by_id(sub)
        → reject if missing or not is_active
    ← User
```

There is no branch of this diagram for a refresh token, a rate limit, or a `/conversions`-specific authorization check — all three are genuinely absent, not disabled or partially built.

---

## 4. Identified Security Gaps

Restated from the Phase D charter, now with the exact repository evidence line-referenced (§2) rather than summarized:

1. **JWT secret** — default value has zero enforcement (`app/core/config.py:34`, no validator).
2. **Refresh token** — config field present, zero implementation (`app/core/config.py:37`).
3. **Rate limiting** — absent everywhere (§2 grep).
4. **`/conversions` authorization** — anonymous endpoint that drives a monetary commission calculation from a fully client-supplied amount (`app/api/v1/conversions.py:18`, `app/services/conversion.py:44`).

No fifth gap was discovered during this inspection that rises to the same level of concreteness; anything else noticed (e.g., no `task_time_limit` on Celery tasks) was already classified as out-of-charter technical debt in the preceding Phase D analysis and is not re-opened here.

---

## 5. Decision 1 — Refresh Token Storage

**Decision: Option B — opaque, high-entropy random refresh tokens, stored server-side in PostgreSQL as a salted hash (never the raw token).**

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the decision? | New `refresh_tokens` table (PostgreSQL); the token issued to the client is a random opaque string; only its hash is persisted. |
| 2 | Why is it needed? | Revocation, rotation, and reuse-detection (Decisions 2–3) all require a server-side lookup by definition — no stateless design can support them. |
| 3 | Evidence | (a) No session/token table exists today — nothing to extend, a clean design is possible. (b) `refresh_token_expire_days` already exists in `Settings`, sized for a *stored, expiring* credential, not a stateless-forever JWT. (c) Every other durable, security/business-relevant record in this repository lives in PostgreSQL (`QueuePublishAttempt`, `Conversion`), never Redis — Redis here is exclusively ephemeral/operational (§2). A refresh token is a multi-day credential controlling account access, which is business-critical, not ephemeral — it belongs in Postgres by this project's own established pattern. |
| 4 | Alternatives considered | Option A (fully stateless JWT refresh); Option C (JWT refresh token wrapping a server-side session record); Redis-as-store variant of Option B. |
| 5 | Why rejected | **Option A** cannot be revoked — a stolen refresh token remains valid for its full 7-day life with no way to cut it off, which fails the phase's own stated goal of closing integrity/security gaps, not just adding a convenience feature. **Option C** requires the exact same server-side lookup as Option B (to check revocation) while additionally paying JWT encode/decode overhead and a second signing-key surface — it is strictly more complex for zero additional capability, since the opaque token carries no claims that need decoding (the DB lookup already yields `user_id`). **Redis-as-store** is rejected because Redis has no configured persistence/eviction guarantee anywhere in this repo's Docker Compose, and using it as the authoritative store for a security-critical credential would be a new, undocumented risk class inconsistent with how this project already treats Redis (ephemeral only). |
| 6 | Which future task depends on it? | Task 2 (implementation), Task 5 (frontend integration consumes the resulting `/auth/refresh` contract). |

**Minimal schema (design only, not implemented in Task 0):**

```text
refresh_tokens
  id            UUID PK   (UUIDPrimaryKeyMixin)
  user_id       UUID FK -> users.id, ON DELETE CASCADE, indexed
  token_hash    VARCHAR   unique, indexed   -- sha256 of the raw opaque token
  created_at    timestamptz  (TimestampMixin)
  updated_at    timestamptz  (TimestampMixin)
  expires_at    timestamptz  not null
  revoked_at    timestamptz  nullable
  replaced_by_id UUID FK -> refresh_tokens.id, nullable, self-referential
```

This follows existing conventions exactly: `UUIDPrimaryKeyMixin` + `TimestampMixin`, `ON DELETE CASCADE` FK to `users.id` (mirrors `affiliates.user_id`), a single new migration (`009_add_refresh_tokens.py`, additive-only — consistent with every migration this project has shipped, e.g. `008_add_queue_publish_attempts.py`).

---

## 6. Decision 2 — Refresh Token Lifecycle

| Question | Decision | Rationale |
| --- | --- | --- |
| Refresh token TTL | **7 days** — reuse `settings.refresh_token_expire_days` as-is | Already configured; zero config change needed; this is the single strongest piece of evidence that a stored, expiring refresh token was the originally intended design |
| Access token TTL compatibility | Unchanged — 30 minutes, untouched | Explicitly out of scope (§4 non-goals); refresh only *adds* a renewal path |
| Rotation behavior | **Rotate on every use** — each successful `/auth/refresh` call issues a brand-new refresh token and marks the presented one as replaced (`replaced_by_id` set) | Standard practice; enables reuse detection (below) at no extra schema cost, since the chain is already needed for auditability |
| Every refresh invalidates the previous token? | **Yes** — the presented token is marked used/replaced in the same transaction that issues the new one | Prevents a single leaked token from being valid indefinitely across multiple refresh calls |
| Reuse detection required? | **Yes** — if a token whose `replaced_by_id` is already set (or whose `revoked_at` is set) is presented again, this is treated as a theft signal | Cheap to implement (already have `replaced_by_id`/`revoked_at`); meaningfully raises the security bar over "just expire after 7 days" |
| Logout behavior | **`POST /auth/logout` revokes the presented refresh token** (`revoked_at = now`) | A server-side-revocable design without any way to trigger revocation is incomplete — this is a small, necessary addition to Task 2's scope, not scope creep (see §16 Task 2) |
| Server-side revocation on reuse detection | **Revoke all of that user's currently-active (non-revoked, non-expired) refresh tokens**, not just the one row | A detected-reuse event means *a* token from this user was stolen; the specific device that leaked it is unknown, so the safe response is to force full re-login everywhere, not just on the flagged token |
| Behavior after password/account invalidation | **N/A for Phase D** — no password-change endpoint exists anywhere in this repository today; this is explicitly not a gap Phase D needs to close, since there is nothing to invalidate against yet | Confirmed absent from `app/auth/router.py` |
| Single-use? | **Yes**, by construction of "rotate on every use" above | — |
| Multiple active sessions/devices supported? | **Yes, by default, with no extra work** — each login creates an independent `refresh_tokens` row; nothing in this design artificially restricts a user to one active session | No evidence in the repository requires restricting to a single session; adding such a restriction would be unjustified scope |
| Device/session metadata (IP, user agent) | **Not included in Phase D.** Explicitly deferred (§20) | No product requirement evidenced for a "manage your devices" UI; adding these columns now would be speculative per the task's own "no speculative architecture" instruction — they can be added additively later without a breaking migration |

---

## 7. Decision 3 — Refresh Token Security

| Question | Decision |
| --- | --- |
| Should raw refresh tokens ever be stored? | **No.** Only `sha256(raw_token)` is persisted. |
| Why hash, and why not bcrypt? | The refresh token itself is a high-entropy random secret (recommend `secrets.token_urlsafe(32)`-equivalent, ≥256 bits), not a low-entropy human password. `bcrypt`'s deliberate slowness exists to defend against offline brute-forcing of *guessable* secrets — it has no purpose here and would add unnecessary CPU cost to every refresh call. A single fast cryptographic hash (`sha256`) is the correct, standard tool for hashing an already-high-entropy token for lookup purposes; this mirrors the project's existing discipline in Phase C' of "no token leakage" in logs, extended one step further to storage. |
| How does lookup/revocation work? | `SELECT ... WHERE token_hash = sha256(presented_token)`. The unique index on `token_hash` makes this an O(1) lookup. Revocation = `UPDATE refresh_tokens SET revoked_at = now() WHERE id = ...`. |
| How does rotation prevent replay? | Single-use + `replaced_by_id` chain (§6) — a token can be exchanged for a new one exactly once; any second presentation is either already-expired or already-replaced, both of which are rejected, and the latter triggers reuse detection. |
| Are refresh token "families" necessary? | Only in the lightweight sense already captured by `replaced_by_id` — a self-referential chain reconstructs the family without a dedicated `family_id` column. A separate family table/column is unnecessary; the chain is sufficient for the one behavior that needs it (revoke-all-on-reuse, which just means "revoke all non-revoked tokens for this `user_id`," not "walk the chain"). |
| How should token theft/reuse be handled? | Per §6: revoke all active tokens for the user; the next `/auth/refresh` or authenticated request proceeds normally (access tokens already in flight remain valid until their own 30-minute expiry — this is an accepted, bounded window, not a gap, since access tokens were never designed to be instantly revocable and Phase D's charter does not ask for that). |
| Redis or PostgreSQL as source of truth? | **PostgreSQL** — see Decision 1 (§5) for full reasoning; not repeated here. |

No new cryptographic mechanism beyond `hashlib.sha256` (standard library) and `secrets.token_urlsafe` (standard library) is introduced — both are already implicitly available via Python's standard library with no new dependency.

---

## 8. Decision 4 — Rate Limiting Architecture

**Decision: Redis-backed fixed-window counter, implemented as a FastAPI route-level dependency — not global ASGI/`BaseHTTPMiddleware`.**

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the decision? | A small `app/core/rate_limit.py` module exposing a dependency factory, e.g. `rate_limit(key: str, limit: int, window_seconds: int)`, applied via `Depends(...)` only on the three named routes (§9). Implementation: Redis `INCR` on a namespaced key, `EXPIRE` set only on first increment (`window_seconds`), reject when the counter exceeds `limit`. |
| 2 | Why is it needed? | Closes charter gap 3 with the smallest mechanism that is provably correct across multiple API worker processes (a plain in-memory counter is not, since Uvicorn/Gunicorn workers do not share memory). |
| 3 | Evidence | (a) Redis is already a hard dependency of this stack (`docker-compose.yml` `redis` service, required by Celery/A.2/Phase B) — no new infrastructure. (b) `redis>=5.2.0` (async client) is already in `requirements.txt`. (c) `SecurityHeadersMiddleware`'s docstring explicitly explains why `BaseHTTPMiddleware` was rejected for this app (it buffers/breaks SSE) — the same reasoning rules out a global rate-limit middleware, since it would sit in front of `GET /queues/stream` too and risk the exact problem that middleware was written to avoid, for a route Phase D does not even intend to rate-limit. A dependency, by contrast, is opt-in per-route and cannot touch the SSE endpoint unless explicitly added to it (which Phase D does not do). |
| 4 | Alternatives considered | In-memory/process-local counter; global ASGI/`BaseHTTPMiddleware`-based limiter; sliding-window or token-bucket algorithms; a third-party library (`slowapi`, etc.). |
| 5 | Why rejected | **In-memory**: incorrect the moment more than one API process/replica exists (already true in `docker-compose.yml`'s implicit support for scaling `api`); rejected on correctness, not preference. **Global middleware**: would need to explicitly exempt the SSE route and any future streaming route, inverting the safer default (opt-in per sensitive route) into an error-prone default (opt-out per exempted route); also touches every request whether or not it's one of the three charter-named endpoints, expanding blast radius beyond what Phase D asks for. **Sliding window / token bucket**: no repository evidence (traffic patterns, abuse history) justifies this complexity; fixed-window is the simplest approach that correctly closes the identified gaps (brute-force login, refresh abuse, conversion-spam), and "prefer the smallest architecture" is an explicit instruction for this task. **Third-party library**: would be a new dependency; the required behavior (`INCR`+`EXPIRE`) is roughly 15 lines against a client already in `requirements.txt` — adding a library for this is not justified by repository evidence of need for more advanced features (per-route configuration DSLs, distributed leaky-bucket, etc.) that such libraries provide but this phase does not require. |
| 6 | Which future task depends on it? | Task 3 (implementation); Task 1 and Task 4 do not depend on this decision directly, but Task 3 must land before or alongside Task 1/Task 4's routes go live with limits attached. |

---

## 9. Decision 5 — Rate-Limit Targets and Limits

Exactly three endpoints, matching the charter and no more (explicitly **not** extending to discovery, product-list, or any other public read endpoint — out of scope per the Phase D charter and the preceding analysis document).

| Endpoint | Identity/key | Limit (recommended default) | Window | Failure status | `Retry-After`? | Identity override rule |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /auth/login` | Client IP (`request.client.host`, or the first `X-Forwarded-For` hop if a reverse proxy is confirmed to set it — **open question**, §22) | **10 attempts / 5 minutes** *(recommended default — not derived from repository traffic data, which does not exist; label as a design recommendation for product-owner confirmation)* | 5 min fixed window | `429` | Yes — seconds until the Redis key's TTL expires | N/A (no identity exists pre-login) |
| `POST /auth/refresh` | Client IP | **20 attempts / 5 minutes** *(recommended default, deliberately looser than login since legitimate silent-refresh traffic from multiple open tabs of the same user is expected)* | 5 min fixed window | `429` | Yes | N/A (the refresh token itself is the credential; IP is the only pre-lookup key available without doing a DB read first, which the limiter should avoid paying for on every request) |
| `POST /conversions` | **Authenticated user ID** once Task 4 lands (preferred key); IP as a secondary/fallback layer | **30 requests / minute** *(recommended default)* | 1 min fixed window | `429` | Yes | **Yes** — once Task 4 requires authentication, the resolved `user.id` should be the primary key, not IP, so that one legitimate integration behind a shared corporate/NAT IP is not penalized for other traffic on the same IP. Until Task 4 ships, IP is the only available key — this row's identity model has a short-lived intermediate state (IP-only) between Task 3 and Task 4, which is acceptable since it only *adds* protection incrementally, never removes it. |

"Multiple users behind one IP" risk is explicitly why `/conversions` prefers a per-user key once available; for `/auth/login` and `/auth/refresh`, IP is unavoidable (no identity exists yet) and is an accepted, standard trade-off (shared-IP users legitimately share a login-attempt budget, matching typical industry practice for unauthenticated brute-force protection).

All three limits are explicitly labeled **recommended defaults requiring confirmation**, not values derived from this repository's evidence (no production traffic data exists to derive them from) — this is called out per the task's own instruction to label unjustified numeric limits as such.

---

## 10. Decision 6 — Redis Failure Semantics

**Decision: Fail open, uniformly, across all three rate-limited routes.**

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the decision? | If the rate-limiter's Redis call raises (connection error, timeout), the request is **allowed through** and a warning is logged — the same shape of behavior already used by `WorkerHealthService` (§2) and `EventPublisher`. |
| 2 | Why is it needed? | Without an explicit decision, an implementer could default to fail-closed, which would make Redis availability a new, undocumented hard dependency for login — a significant, unadvertised availability regression, since login has never depended on Redis in this project's history. |
| 3 | Evidence | This repository has a consistent, established philosophy for Redis-adjacent operational failures: degrade the *feature* the Redis call supports, never the *core* request path it's attached to. `WorkerHealthService.check()` returns `"unknown"` rather than raising when Redis is unreadable (`app/services/worker_health.py:32-36`). `EventPublisher`'s publish failures are "logged only," explicitly not rolled back against the domain mutation (`docs/10-production-readiness.md` §9.1). Rate limiting is architecturally the same shape of concern: an operational safeguard *around* a core feature (auth, conversion recording), not the core feature itself. |
| 4 | Alternatives considered | Fail-closed uniformly; fail-closed for login/refresh only (treating auth as more security-sensitive) with fail-open for conversions. |
| 5 | Why rejected | **Uniform fail-closed** directly contradicts the project's own established Redis-failure philosophy (above) and would mean a transient Redis blip locks every user out of the entire application (no login = no access to anything), which is a categorically worse outcome than a brief window of reduced brute-force protection. **Mixed fail-closed-for-auth**: superficially appealing ("auth is more sensitive") but inconsistent with this project's own precedent and adds implementation complexity (two different failure branches to test and maintain) for a benefit that is speculative — no repository evidence of an active brute-force threat exists today; the risk being guarded against is prospective, while the availability cost of fail-closed is immediate and certain. |
| 6 | Which future task depends on it? | Task 3 (must implement this exact fail-open branch and log a warning, not silently swallow the error). |

This explicitly answers the instruction not to leave this ambiguous: **fail-open, same behavior on all three routes, no exceptions.**

---

## 11. Decision 7 — Conversion Authorization

Inspected: `app/api/v1/conversions.py`, `app/services/conversion.py`, `app/schemas/conversion.py`, `app/models/conversion.py`, `app/models/affiliate.py`.

| # | Question | Answer |
| --- | --- | --- |
| 1 | Should the endpoint require authentication? | **Yes.** |
| 2 | Which authenticated principal is allowed to create a conversion? | Either (a) a user whose own `Affiliate` record (`AffiliateRepository.get_by_user_id(current_user.id)`) matches the request's `affiliate_id`, or (b) an `ADMIN`-role user, acting on behalf of any affiliate — mirroring the exact bypass pattern already used by `update_status`/`list_all` in the same service. |
| 3 | Is ownership user-based or workspace-based? | **User-based**, via the existing 1:1 `Affiliate.user_id` FK. The project is confirmed single-tenant (`docs/10-production-readiness.md` §6: "Queue/channel data **not user-scoped** — not multi-tenant safe"); this analysis does **not** introduce workspace-based authorization, since no workspace/tenant concept exists anywhere in the repository. Explicitly not inventing multi-tenancy, per the task's own instruction. |
| 4 | Is there an existing authorization dependency that should be reused? | **Yes, two, both already present and proven**: `CurrentUser` (`app/auth/dependencies.py`) for authentication, and the `get_by_user_id` → compare-to-request-`affiliate_id` pattern already exercised by `list_for_affiliate` (`app/services/conversion.py:76-91`) for ownership. Task 4 should call the same repository method, not write a new one. |
| 5 | What happens if the client submits another user's/affiliate's identifier? | **Rejected with `403 Forbidden`** (reuse `ForbiddenError`, already used by `update_status` for the equivalent admin-only violation) — unless the caller is `ADMIN`. |
| 6 | Should the authenticated principal be taken exclusively from the access token? | **Yes** — `current_user` from `CurrentUser`, never from a request-body field. This is the actual fix: today, nothing about the caller's identity is checked at all; after this change, identity comes exclusively from the verified JWT, and the request body's `affiliate_id` is *validated against* that identity rather than trusted outright. |
| 7 | Should the endpoint remain callable anonymously for any reason supported by the repository? | **No evidence supports this.** `docs/06-api-integration.md` §4.8 lists `conversions` as "Backend only — No MVP screens," meaning **nothing in this repository — frontend or otherwise — currently calls `POST /conversions` at all.** There is no in-repo caller whose access would break by requiring authentication. |

**Important open question this decision surfaces, not resolved here (see §22):** the shape of `ConversionCreate` (`affiliate_id` + `campaign_id` + `external_order_id`, no user-facing fields like "note" or "screenshot") strongly resembles a **server-to-server conversion-postback** pattern (a merchant or ad network reporting "this affiliate's link converted"), not a form a logged-in affiliate would fill in themselves through a browser session. If such an external caller exists today outside this repository's visibility, requiring a *user* JWT (as recommended above) would break it, and a separate service-credential path would be needed instead of, or in addition to, user-JWT auth. This analysis found **no evidence** of such an external caller in the repository (no webhook signature verification code, no partner/API-key model anywhere in `app/`), so the recommendation above (user-JWT + ownership, with an admin bypass available as an interim path for any trusted internal/ops tool) is the correct **smallest, evidence-grounded default**. This is flagged as an explicit open question requiring the product owner's confirmation before Task 4 ships (§22), not silently assumed away.

---

## 12. Decision 8 — Conversion Value/Amount Integrity

| # | Question | Answer |
| --- | --- | --- |
| 1 | Does `POST /conversions` currently accept an amount/value from the client? | **Yes** — `amount: Decimal = Field(gt=0)` (`app/schemas/conversion.py:14`), used directly and unmodified in the commission calculation (`app/services/conversion.py:44-46`). |
| 2 | Is the client-supplied amount authoritative today? | **Yes, entirely** — there is no other data source in this system for "what was the sale total." |
| 3 | Can the amount be manipulated? | **Yes** — today, by anyone (no auth at all). After Decision 7's fix, only by an authorized caller (an affiliate's own identity, or an admin) — which narrows *who* can submit a number, but does not verify the number itself against any external ground truth, because none exists in this repository. |
| 4 | Should the amount instead be derived server-side? | **No — there is no server-side source of truth to derive it from.** This repository has no order/price/webhook-verification table for AliExpress (or any other network) that would let the server compute `amount` independently. Recommending server-side derivation would be inventing infrastructure not evidenced by the repository, which the task instructions explicitly prohibit. |
| 5 | Does the server already have the required source data? | **No.** See above. |
| 6 | Should Phase D remove `amount` from the request? | **No.** Removing it without a replacement source of truth would make the endpoint unable to do its job (recording how much a conversion was worth) at all. |
| 7 | Is changing the API contract justified? | **Partially — additively, not by removing fields.** The commission-rate lookup (`affiliate.commission_rate`) is already correctly server-side and untouched by the client (good — this part of the integrity story is already sound). The only contract-relevant change from this phase is *authorization*, not the request schema's fields. |
| 8 | What is the minimum change required to close the integrity issue *this phase* is chartered to close? | **Require authentication + ownership (Decision 7).** This converts the vulnerability from "anyone can fabricate a conversion for any affiliate, unlimited, forever" to "only an affiliate (or an admin) can submit a conversion, and only for their own affiliate record, and only up to the Decision 5 rate limit." The residual risk — a legitimate, authenticated affiliate self-reporting an inflated `amount` for their own conversions — is a **business-process trust question** (does the payout team verify conversions before paying out? `ConversionStatus` already defaults new conversions to `PENDING`, and only an admin can move them via `update_status` — this existing admin-review gate is the correct, already-built control for that residual risk, not something Phase D needs to add). |

**Conclusion:** Phase D closes the *access-control* integrity gap (who can write) using purely existing repository primitives. It explicitly does **not** attempt to close a *data-provenance* integrity gap (whether the number itself is true), because no evidence-grounded mechanism for that exists in this repository, and the existing `PENDING`-status admin-review workflow is already the designed control for that residual risk. This distinction is deliberate and should be preserved in Task 4's scope — do not let Task 4 grow into a "verify conversions against AliExpress" feature, which would be new, unevidenced, out-of-charter scope.

---

## 13. Decision 9 — Public vs Authenticated Endpoint Boundary

| Endpoint | Current auth | Phase D auth | Reason |
| --- | --- | --- | --- |
| `GET /health` | None | **Unchanged — None** | Process liveness; no Phase D evidence justifies changing this cross-phase operational contract |
| `GET /ready` | None | **Unchanged — None** | Database + Redis dependency check only (A.2/B established); no secrets exposed; explicitly preserved per this task's own instruction |
| `GET /worker/health` | None | **Unchanged — None** | Phase B explicitly designed this as unauthenticated operational infrastructure (`docs/06-api-integration.md` §7: "It is **not** part of the authenticated `/api/v1` application API surface"); no Phase D reason to revisit |
| `POST /auth/login` | None (that's inherent to login) | **None + rate limit (Decision 4/5)** | Cannot require auth to obtain auth; the only applicable control is abuse-rate limiting |
| `GET /auth/me` | Access token | **Unchanged — Access token** | Already correctly authenticated; not part of the charter |
| `POST /auth/refresh` (planned, Task 2) | N/A (doesn't exist yet) | **Refresh token (not access token) as the presented credential + rate limit** | The refresh token itself is the bearer credential for this one route; `CurrentUser`/access-token validation must **not** be reused here — this route needs its own, separate credential-validation path so that an access token can never be presented in place of a refresh token (regression boundary, §18) |
| `POST /conversions` | **None (current gap)** | **Access token + ownership-or-admin (Decision 7) + rate limit** | The one endpoint this phase's charter directly names as needing authorization |
| `GET /conversions/me` | Access token | **Unchanged — Access token** | Already correct; not part of the charter |
| `GET /conversions` (admin list) | Access token + `ADMIN` role | **Unchanged** | Already correct |
| `PATCH /conversions/{id}` | Access token + `ADMIN` role | **Unchanged** | Already correct |
| `GET /products`, `GET /products/discover*` | None (public reads) | **Unchanged — None** | Explicitly out of scope (§4 non-goals; also §9's "do not automatically rate-limit every endpoint"); no evidence of abuse; changing this would be unjustified scope expansion |
| `GET /queues`, `POST /queues`, etc. | Access token | **Unchanged** | Already correctly authenticated (A.1/A.2); not part of the charter |
| `GET /queues/stream` (SSE) | Access token | **Unchanged** | A.2-established; explicitly protected as a regression boundary (§18) — Phase D must not touch this route at all |
| `GET /channels`, `POST /channels`, etc. | Access token | **Unchanged** | Not part of the charter |

---

## 14. Decision 10 — JWT Secret Validation

(Design guidance for Task 1's later implementation — **not implemented in Task 0**.)

| Question | Decision |
| --- | --- |
| What constitutes an unsafe/default secret? | Primary check: **exact string match** against the literal current default, `"change-me-to-a-long-random-secret-in-production"`. This has zero false-positive risk (it is a fixed, known literal) and needs no entropy heuristics. Secondary, defense-in-depth check: **minimum length** (recommend ≥32 characters) to also catch an operator who changed the value but chose something still weak (e.g., `"secret123"`) — this second check is a recommended default, not derived from repository evidence, and should be explicitly labeled as such in Task 1. |
| May development/test environments retain the default? | **Yes, exactly when `settings.is_development` is `True`** (`app_env == "development"`, the existing property in `app/core/config.py:107-109` — already fit for purpose, zero new config needed). Test runs (`tests/conftest.py`) do not override `app_env`, so they inherit the `"development"` default and are unaffected by this validation as long as no `.env`/CI configuration sets `APP_ENV` to a non-development value without also setting a real secret — this must be explicitly verified as part of Task 1's rollout (flagged in §22), not assumed. |
| What should production behavior be? | **Fail fast at process/settings-construction time** (raise before the app can serve any request), not a runtime warning that could be missed in logs. This matches the "critical, impossible-to-miss" framing already used to classify this issue in `docs/10-production-readiness.md` §10. |
| Startup validation or configuration validation? | **Configuration validation**, specifically a Pydantic `model_validator(mode="after")` on the `Settings` class itself — not a separate FastAPI startup-event hook. Rationale: the decision depends on **two fields together** (`jwt_secret_key` and `app_env`), which is exactly what a model-level (not field-level) validator is for; this is consistent with the existing `field_validator` already used for `database_url` (`app/core/config.py:95-105`), just one level up. Because `get_settings()` is called at **import time** in many modules (`app.main`, `app.auth.security`, etc. — every one of them via `from app.core.config import get_settings; settings = get_settings()`), a `Settings`-level validator fires at the earliest possible point, before Uvicorn can bind or serve a single request — stronger than a startup-event hook, which only fires after the app object is already constructed. |
| Minimum length/entropy requirements? | Length yes (≥32 chars, recommended default). Entropy scoring (e.g., character-class diversity checks) is **not recommended** — no repository evidence justifies this complexity, and simple length + exact-default-match closes the actual, evidenced gap (§4, item 1) completely. |
| How does this fit existing settings/configuration patterns? | Directly — extends the exact validator style already present in the same file for `database_url`, using the exact `is_development` property already present for exactly this kind of environment-conditional check. No new configuration pattern is introduced. |

---

## 15. Rejected Alternatives

Consolidated (also inline per-decision above, repeated here for a single reference point):

| Area | Rejected alternative | Why |
| --- | --- | --- |
| Refresh token storage | Stateless JWT refresh | No revocation possible; fails the phase's own security goal |
| Refresh token storage | JWT-wrapped server-side session | Same DB lookup cost as opaque token, plus unnecessary JWT encode/decode overhead |
| Refresh token storage | Redis as source of truth | No persistence/eviction guarantee configured; inconsistent with project's Redis-is-ephemeral-only convention |
| Refresh token hashing | `bcrypt` | Wrong tool for an already-high-entropy random secret; unnecessary CPU cost per refresh |
| Rate limiting | In-process/in-memory counter | Incorrect across multiple worker processes |
| Rate limiting | Global `BaseHTTPMiddleware` | Same class of SSE-buffering risk `SecurityHeadersMiddleware`'s own docstring already rejects; also over-broad blast radius |
| Rate limiting | Sliding window / token bucket | No repository evidence justifies the added complexity over fixed-window |
| Rate limiting | Third-party library (`slowapi`, etc.) | New dependency for ~15 lines of logic against an already-available client |
| Redis failure semantics | Fail-closed (uniform or auth-only) | Contradicts this project's own established Redis-degrades-gracefully precedent; makes Redis an undocumented hard dependency for login |
| Conversion authorization | Workspace-scoped authorization | No workspace/tenant concept exists anywhere in the repository; would be invented, not evidenced |
| Conversion amount integrity | Server-derived amount | No source-of-truth data exists in this repository to derive it from |
| Conversion amount integrity | Remove `amount` from the request entirely | Would make the endpoint unable to perform its function |
| JWT secret validation | Entropy-scoring heuristics | Unjustified complexity; exact-match + length covers the evidenced gap completely |
| JWT secret validation | FastAPI startup-event hook | Fires later than a `Settings`-level validator, which triggers at the earliest possible import-time point |

---

## 16. Phase D Task Breakdown

Task 0 (this document) is complete. Tasks 1–6 are defined precisely below; **none are implemented in this task.**

### Task 1 — JWT Secret Validation

- **Objective:** the API refuses to construct a valid, servable `Settings` instance when `jwt_secret_key` is unsafe (Decision 10) and `app_env != "development"`.
- **Exact scope:** a `model_validator(mode="after")` on `app.core.config.Settings`; raise `ValueError` (or a dedicated `ImproperlyConfigured` exception, implementer's choice, but must be a hard failure, not a log line) when unsafe.
- **Expected files/modules:** `app/core/config.py` only.
- **Expected tests:** new `tests/test_config_security.py` — construct `Settings(jwt_secret_key=<default>, app_env="production")` → expect failure; construct with `app_env="development"` and the default → expect success; construct with a non-default, ≥32-char secret and any `app_env` → expect success; construct with a non-default but short (<32-char) secret and `app_env="production"` → expect failure (secondary check).
- **Dependencies:** none — can start immediately, independent of Task 0's other decisions (this is the only task that does not depend on Decisions 1–9).
- **Explicit non-goals:** does not touch refresh tokens, rate limiting, or `/conversions`; does not add an entropy-scoring check (Decision 10).
- **Acceptance criteria:** all four test cases above pass; existing `tests/conftest.py`-driven suite (35 files) still passes unmodified, confirming the default `app_env="development"` test path is unaffected.
- **Security invariants:** must not weaken `decode_access_token`'s existing `"type": "access"` check; must not change `jwt_algorithm` or `access_token_expire_minutes` semantics.

### Task 2 — Refresh Token Implementation

- **Objective:** implement the Decision 1–3 design — `refresh_tokens` table + migration, `POST /auth/refresh`, `POST /auth/logout`, rotation, reuse detection.
- **Exact scope:** new migration `009_add_refresh_tokens.py` (additive-only); new `app/models/refresh_token.py`; `create_refresh_token`/`hash_refresh_token`/`verify_and_rotate_refresh_token` helpers (naming illustrative) in `app/auth/security.py` alongside the existing access-token functions; `app/auth/repository.py` gains a `RefreshTokenRepository` or equivalent; `app/auth/schemas.py`'s `TokenResponse` gains `refresh_token: str` (additive field, `access_token`/`token_type` unchanged); `app/auth/router.py` gains `POST /auth/refresh` and `POST /auth/logout`; `app/auth/service.py::login` issues both tokens.
- **Expected tests:** new `tests/test_auth_refresh.py` — successful login issues both tokens; successful refresh issues a new access+refresh pair and invalidates the old refresh token; expired refresh token rejected (401); already-rotated ("replaced") refresh token presented again triggers reuse detection and revokes all of that user's active refresh tokens (verify a *second* previously-valid refresh token for the same user now also fails); an access token presented to `/auth/refresh` is rejected (proves the two credential types are not interchangeable); `/auth/logout` revokes the presented token and a subsequent refresh with it fails.
- **Dependencies:** Task 0 (this document) — specifically Decisions 1, 2, 3. Independent of Tasks 1, 3, 4.
- **Explicit non-goals:** no device/session metadata (Decision 2); no password-change/account-invalidation handling (N/A, Decision 2); no change to `access_token_expire_minutes` or `decode_access_token`'s existing behavior for access tokens.
- **Acceptance criteria:** all `tests/test_auth_refresh.py` cases pass; full existing 35-file backend suite still passes unmodified (in particular, `GET /auth/me` and every other `CurrentUser`-gated route must behave identically for existing access tokens).
- **Security invariants:** `get_current_user`/`CurrentUser` must continue to reject any token whose `type != "access"` — this must be verified by a test that a refresh token cannot be used as a Bearer token on any existing authenticated route (e.g., `GET /auth/me`).

### Task 3 — Rate Limiting

- **Objective:** implement the Decision 4–6 design — Redis-backed fixed-window dependency, applied to the three Decision 5 routes, fail-open on Redis errors.
- **Exact scope:** new `app/core/rate_limit.py` (dependency factory + a new `TooManyRequestsError(ServiceError)` with `status_code=429` in `app/services/exceptions.py`); apply via `Depends(...)` to `POST /auth/login`, `POST /auth/refresh` (once Task 2 exists), and `POST /conversions`.
- **Expected tests:** new `tests/test_rate_limit.py` — under-limit requests succeed; the (N+1)th request within the window returns 429 with a `Retry-After` header; after the window elapses, requests succeed again; simulate a Redis connection failure (e.g., via monkeypatching the client) and confirm the request still succeeds (fail-open, Decision 6) and a warning is logged.
- **Dependencies:** Task 0 (Decisions 4, 5, 6). Should land at or before Task 2 and Task 4 so their new routes ship with limits already attached, but is not a hard blocker for either — a route can exist briefly unlimited between tasks if sequencing requires it, since this only means *temporarily* not yet having the *additional* protection, never a regression from a previously-limited state.
- **Explicit non-goals:** does not rate-limit any endpoint beyond the three named (§9); does not introduce a third-party rate-limiting library; does not change `SecurityHeadersMiddleware` or add any global middleware.
- **Acceptance criteria:** all `tests/test_rate_limit.py` cases pass; `GET /queues/stream` (SSE) is verified, by an explicit test or code-review note, to have **no** rate-limit dependency attached (regression boundary, §18).
- **Security invariants:** the limiter must never be implemented as `BaseHTTPMiddleware` or any mechanism that buffers a streaming response body.

### Task 4 — Conversion Authorization

- **Objective:** implement Decision 7 — require authentication and ownership-or-admin on `POST /conversions`.
- **Exact scope:** add `current_user: CurrentUser` (or `Annotated[User, Depends(get_current_user)]`, matching existing router style) to `record_conversion`'s signature in `app/api/v1/conversions.py`; pass `current_user` into `ConversionService.record_conversion`; inside the service, resolve the caller's own `Affiliate` via the existing `AffiliateRepository.get_by_user_id` (already used in `list_for_affiliate`), compare to `payload.affiliate_id`, and raise `ForbiddenError` on mismatch unless `current_user.role == UserRole.ADMIN`.
- **Expected files/modules:** `app/api/v1/conversions.py`, `app/services/conversion.py` only.
- **Expected tests:** new `tests/test_conversions_authorization.py` — an authenticated affiliate recording a conversion for their own `affiliate_id` succeeds (existing enrollment-check behavior from `record_conversion` must still apply unchanged); an authenticated affiliate attempting to record a conversion for a *different* `affiliate_id` is rejected with 403 (new — no equivalent test exists today); an `ADMIN` user recording a conversion for any `affiliate_id` succeeds; an unauthenticated request is rejected with 401 (new — today it would succeed, so this test explicitly documents the intended breaking change).
- **Dependencies:** Task 0 (Decisions 7, 8). Independent of Tasks 1, 2, 3 (can be implemented in parallel), though should ideally land alongside Task 3's rate limit for the same route.
- **Explicit non-goals:** does not change `ConversionUpdate`, `list_all`, or `list_for_affiliate` (already correct); does not attempt to verify the *amount* against any external source (Decision 8); does not add a service-to-service credential path (deferred, §20/§22, pending the open question about real external callers).
- **Acceptance criteria:** all four `tests/test_conversions_authorization.py` cases pass; existing conversion-recording success path (enrollment check) behaves identically for an authorized caller.
- **Security invariants:** the authenticated principal must be taken exclusively from `CurrentUser`, never from any request-body field; `payload.affiliate_id` is validated against, never trusted as, the caller's identity.

### Task 5 — Frontend Session Refresh Integration

- **Objective:** the frontend transparently uses `POST /auth/refresh` (Task 2) instead of forcing full re-login on access-token expiry, without introducing any new UI.
- **Exact scope:** `frontend/src/services/session.ts` gains refresh-token storage (same `sessionStorage` mechanism already used for the access token — no new storage pattern); `frontend/src/services/api-client.ts`'s response interceptor attempts exactly one silent refresh-and-retry on a 401 (excluding `/auth/login` and `/auth/refresh` itself, to avoid a refresh-loop) before falling back to today's existing clear-session-and-redirect behavior.
- **Expected files/modules:** `frontend/src/services/session.ts`, `frontend/src/services/api-client.ts` only. No new routes, pages, drawers, or dialogs (per `docs/07-development-guidelines.md`'s AI-agent guardrails and this phase's own non-goals).
- **Expected tests:** new `frontend/src/services/api-client.test.ts` — a 401 followed by a successful refresh retries the original request once and succeeds; a 401 followed by a failed refresh (e.g., refresh token also expired/revoked) falls back to clearing the session and redirecting, exactly as today's unmodified behavior for the case with no refresh token at all; a request to `/auth/login` itself returning 401 does **not** trigger a refresh attempt (existing exclusion, preserved).
- **Dependencies:** **Hard dependency on Task 2** — cannot be implemented or meaningfully tested before `POST /auth/refresh` exists and is stable, since this task's entire surface is "consume that endpoint correctly."
- **Explicit non-goals:** no "remember me" feature; no session/device management UI; no change to the existing cookie-as-presence-marker middleware pattern (`docs/02-frontend-architecture.md` §6).
- **Acceptance criteria:** all three new test cases pass; none of the 16 existing frontend test files (in particular the 11 Queue-realtime files) regress — the SSE client's own, separately-documented 401 handling (A.2 design doc §18) must be explicitly checked for interaction with this new interceptor logic and confirmed not to double-handle a 401 on the stream connection.
- **Security invariants:** the refresh token must be stored via the same `sessionStorage`-only mechanism as the access token (§18) — never a cookie, never `localStorage`.

### Task 6 — Documentation Closeout

- **Objective:** update the authoritative docs to reflect Tasks 1–5's shipped behavior, following this project's own established closeout convention (every prior phase — A.1, A.2, B, C' — closed with a documentation update in the same milestone).
- **Exact scope:** `docs/10-production-readiness.md` §6 (security boundaries table gains refresh-token/rate-limit rows) and §10 (the "Default JWT secret — Critical" and "No refresh token — Medium" rows updated to reflect resolution); `docs/06-api-integration.md` §1 (new `/auth/refresh`/`/auth/logout` entries) and the `/conversions` row in §4.8 (status changes from "Backend only — No MVP screens" to reflect the new auth requirement); `docs/02-frontend-architecture.md` §6 ("Refresh tokens are **not implemented**" sentence updated); `docs/08-implementation-roadmap.md` (mark Phase D complete, name the next recommended milestone per `docs/planning/phase-d-analysis-and-roadmap.md` §5).
- **Expected files/modules:** documentation only.
- **Expected tests:** none.
- **Dependencies:** Tasks 1–5 complete and their tests passing.
- **Explicit non-goals:** does not implement Candidate 2/3/4/5 from the prior Phase D analysis document — only names the recommended next one.
- **Acceptance criteria:** every doc file listed above is updated; no other existing documentation file is touched.
- **Security invariants:** none (documentation task).

---

## 17. Dependency Graph

```text
Task 0 (this document — Decisions 1-10 finalized)
 │
 ├── Task 1 — JWT Secret Validation                     (independent; no dependency on Decisions 1-9)
 │
 ├── Task 2 — Refresh Token Implementation               (consumes Decisions 1, 2, 3)
 │    └── Task 5 — Frontend Session Refresh Integration  (hard dependency: Task 2 must be complete+stable first)
 │
 ├── Task 3 — Rate Limiting                              (consumes Decisions 4, 5, 6; should land at/before Task 2 & Task 4's routes ship, but is not a hard blocker for either)
 │
 └── Task 4 — Conversion Authorization                   (consumes Decisions 7, 8; independent of Tasks 1, 2, 3)
                    │
                    ▼
              Task 6 — Documentation Closeout            (requires Tasks 1-5 complete)
```

**Parallelizable after Task 0:** Task 1, Task 3, and Task 4 have no dependency on each other or on Task 2 — they can be implemented in any order or simultaneously. **Sequential:** Task 5 strictly requires Task 2. **Last:** Task 6 requires everything else.

This matches the structure the charter expected (`Task 0 → {1, 2→5, 3, 4} → 6`) exactly — repository analysis did not surface any reason to reorder it, only to make each edge's *reason* explicit (above), which the charter asked for.

---

## 18. Regression Boundaries

1. `POST /auth/login`'s existing response fields (`access_token`, `token_type`) are unchanged in meaning; `refresh_token` is *additive* only (Task 2).
2. `GET /auth/me` continues to work identically for any currently-valid access token, before and after every task in this phase.
3. `get_current_user`/`CurrentUser` continues to accept **only** tokens with `"type": "access"` — a refresh token must be rejected if presented as a Bearer access token on any existing route. This is the single highest-priority regression boundary in this phase, since a failure here would silently weaken every authenticated route in the system at once.
4. `QueueStatus` (`app/models/queue.py`, `app/schemas/queue.py`) — untouched; no task in §16 modifies either file.
5. `queue_publish_attempts` — untouched; no task in §16 reads or writes this table.
6. A.1 Telegram retry architecture (`app/telegram/`) — untouched.
7. A.2 SSE / `queue-events` architecture (`app/events/`, `app/api/v1/queue_stream.py`) — untouched; `GET /queues/stream` receives **no** new rate-limit dependency and **no** change to its existing access-token authentication.
8. Phase B heartbeat and `/worker/health` (`app/worker/tasks/health.py`, `app/services/worker_health.py`) — untouched.
9. Phase C' retry ownership (`app/aliexpress/`, `app/ai/retry.py`, Celery `autoretry_for` configuration) — untouched.
10. No new dependency is introduced anywhere in Tasks 1–6 — every mechanism above (hashing, random token generation, Redis counters, Pydantic model validators) uses libraries already present in `requirements.txt` or the Python standard library.
11. Existing API error contracts remain stable except where a Phase D task *intentionally* changes them — the only intentional change is `POST /conversions` moving from anonymous-always-succeeds to authenticated-and-owned (Task 4), which is a deliberate, documented breaking change, not an accidental one.
12. Existing frontend behavior (login, session storage, 401-redirect-to-login) remains fully compatible through Tasks 1–4; Task 5 is the only task permitted to change frontend session behavior, and even then only by *adding* a refresh attempt before the existing fallback — the existing fallback path itself must remain reachable and correct.

---

## 19. Security Invariants

- The refresh token type discriminator (`"type": "refresh"`, mirroring the existing `"type": "access"`) must never be accepted by `get_current_user`.
- Raw refresh tokens are never persisted — only `sha256` hashes (Decision 3).
- Raw refresh tokens are never logged — matching this project's existing "no token leakage" discipline (Phase C' design doc).
- A refresh token, once rotated (replaced) or revoked, must never again yield a successful refresh (Decision 2/3, enforced via `replaced_by_id`/`revoked_at`).
- Rate-limit keys must never be constructed from unsanitized user input in a way that could allow key-injection into the Redis namespace (e.g., always prefix with a fixed, code-controlled string such as `ratelimit:login:` before appending the IP/user-id).
- `POST /conversions`'s authorization check must resolve identity exclusively from `CurrentUser`, never from any client-supplied field.
- The JWT secret validator (Task 1) must run before the application can bind to a port and accept traffic in any non-development environment.
- No task in this phase may weaken `decode_access_token`'s existing `"type": "access"` enforcement, `access_token_expire_minutes`, or `jwt_algorithm`.

---

## 20. Out of Scope / Deferred Work

- Device/session metadata on `refresh_tokens` (IP, user agent, "manage your devices" UI) — no product requirement evidenced; additive, non-breaking to add later.
- Rate limiting for any endpoint beyond the three named in Decision 5 (discovery, product list, etc.) — explicitly out of the Phase D charter.
- A service-to-service/API-key credential path for `POST /conversions` — deferred pending the open question in §22 about whether a real external caller exists; the current design's admin-role bypass is an adequate interim path if one is confirmed to exist before that dedicated mechanism is built.
- Verifying the *truth* of a submitted conversion `amount` against an external source (e.g., AliExpress) — no source-of-truth data exists in this repository (Decision 8); this would be new, unevidenced scope.
- Password-change / account-invalidation-triggered refresh-token revocation — no password-change feature exists yet (Decision 2); revisit when one is built.
- Any change to `access_token_expire_minutes`, `jwt_algorithm`, or the access-token payload shape.
- Analytics/affiliate-performance frontend workspace, frontend test-coverage expansion for Discovery/Products/AI Studio/Channels, and form/schema validation standardization — all remain the separately-scoped Phase D+1 candidates identified in `docs/planning/phase-d-analysis-and-roadmap.md` §5, untouched by this document.

---

## 21. Implementation Readiness Checklist

- [x] Current authentication architecture verified from source, not assumed from documentation.
- [x] Current Redis usage and failure-handling precedent verified from source.
- [x] Current rate-limiting state (absence) verified via repository-wide search.
- [x] `/conversions` implementation, schema, and service layer fully read and traced end-to-end.
- [x] Existing ownership-resolution primitive (`get_by_user_id`) confirmed to already exist and already be proven in this exact domain.
- [x] Existing test baseline for auth/conversions confirmed to be zero files (not partially covered).
- [x] Frontend session/auth architecture read in full; no refresh assumptions found.
- [x] All ten decisions (A–J / Decisions 1–10) resolved with an explicit recommendation, evidence, and rejected alternatives.
- [x] Task 0 → Task 1–6 dependency graph produced and matches the charter's expected shape.
- [x] Regression boundaries for A.1, A.2, B, and C' explicitly enumerated.
- [x] Security invariants explicitly enumerated.
- [x] Open questions explicitly listed, not silently resolved by assumption (§22).
- [x] No production code, test, migration, configuration, or frontend file modified during this task (verified, §0 below).

---

## 22. Final Recommendation

**Proceed to Task 1 and Task 3 first** (both fully independent of every other decision and of each other — the lowest-risk, highest-confidence starting points), **then Task 2**, **then Task 5** (hard dependency on Task 2), **with Task 4 implementable at any point after Task 0** (recommend pairing it with Task 3 so `/conversions` gains authorization and its rate limit together), **and Task 6 last.**

Two items should be confirmed by the product owner before Task 4 specifically (not before Task 0/1/2/3, which have no such dependency):

```text
Open questions:
1. Does any real external system (merchant/network webhook, ops tool, etc.)
   currently call POST /conversions outside this repository's visibility?
   If yes, Task 4 needs an additional service-credential path, designed as a
   follow-up to this document, not assumed here. If no (as this analysis's
   repository-only evidence suggests), Task 4 as designed (user-JWT +
   ownership + admin bypass) is sufficient and should proceed unchanged.

2. Confirm whether any reverse proxy in front of the API sets
   X-Forwarded-For, to determine whether Task 3's IP-based rate-limit key
   should read request.client.host directly or a forwarded header. Not
   resolved here — infrastructure-topology-dependent, outside this
   repository's own evidence.
```

Neither open question blocks Task 0's completion or Tasks 1/2/3's start — both are scoped narrowly to refinements Task 4 (and, for question 2, Task 3's exact key derivation) should confirm before shipping, not before beginning implementation.

---

## Related Documents

- [phase-d-analysis-and-roadmap.md](./phase-d-analysis-and-roadmap.md) — Phase D charter/selection (read first)
- [phase-c-prime-retry-hardening-design.md](./phase-c-prime-retry-hardening-design.md) — precedent for this project's Task-0-first pattern
- [phase-b-worker-observability-design.md](./phase-b-worker-observability-design.md) — precedent for this project's Redis-degrades-gracefully failure philosophy
- [../10-production-readiness.md](../10-production-readiness.md) §6, §10 — source of the Critical/Medium severity markers this design closes
- [../06-api-integration.md](../06-api-integration.md) §1, §4.8, §7 — current API contracts this design extends without breaking
- [../02-frontend-architecture.md](../02-frontend-architecture.md) §6 — current frontend auth flow Task 5 extends
