# Production Readiness and Release Runbook

**Last Updated:** 2026-07-17

This runbook is the release gate for the MVP. It supplements, and does not change, the
architecture defined in documents 01–09.

## 1. Required environment

- PostgreSQL 16 and Redis 7 are reachable from the API and workers.
- `JWT_SECRET_KEY` is a generated production secret.
- `CORS_ORIGINS` contains only deployed frontend origins.
- Telegram, AliExpress, and the selected AI provider use non-development credentials.
- `NEXT_PUBLIC_API_URL` is set at frontend image build time.
- Database migrations run once before the API and workers are promoted.

Never copy credentials from examples. Rotate a credential immediately if it is committed,
logged, pasted into an issue, or otherwise exposed.

## 2. Automated gate

The CI workflow must pass:

- Ruff checks for production-readiness additions and the full backend pytest suite. Existing
  repository-wide lint debt should be removed incrementally before expanding the lint gate.
- Frontend typecheck, ESLint, unit/component tests, and production build.

The current GitHub Actions workflow uses Python 3.12 and Node 22. It runs the full backend
pytest suite, Ruff only on the explicitly listed production-readiness files, and frontend
typecheck, lint, Vitest, and build. Playwright exists as `npm run test:e2e` for local/manual
verification; it is not currently a CI job or required automated check.

Do not release from a working tree or commit with a failing or skipped required check.

## 3. Staging deployment

1. Build immutable backend and frontend images.
2. Apply Alembic migrations.
3. Provision a staging admin through the trusted operational/database process. Public
   registration only creates affiliates, while product import requires admin access.
4. Start PostgreSQL, Redis, API, Celery worker, and Celery beat.
5. Confirm `GET /health` returns `200`.
6. Confirm `GET /ready` returns `200` with database and Redis both `up`.
7. Verify Celery worker/beat health separately; Redis readiness proves connectivity, not
   that a worker is alive or consuming tasks.
8. Start the frontend and confirm login redirects to the protected dashboard.
9. Confirm API and frontend security headers are present.
10. Confirm application logs contain no passwords, tokens, provider payloads, or secrets.

## 4. MVP acceptance flow

Execute this flow with a staging admin account:

1. Authenticate and load the dashboard.
2. Browse general/keyword, hot, trending, deals, and category discovery through the current
   UI.
3. Verify keyword, rating, discount, and category controls affect results. Verify additional
   order, price, shipping, sort, paging, and persistence contract options separately at the
   API level until corresponding UI controls exist.
4. Import one product and verify its details and images.
5. Generate Arabic content and review/edit the result.
6. Register a staging Telegram channel and verify bot permissions.
7. Create a draft queue item in AI Studio and publish it from the queue. Verify scheduled
   creation separately through the API until the scheduling UI is implemented.
8. Confirm the Telegram message, image, affiliate button, and published queue state.
9. Simulate an upstream AI/AliExpress error and confirm safe user feedback.
10. Simulate Redis unavailability and confirm `/ready` returns `503` with a stable
    `not_ready` body; separately stop a Celery worker and confirm worker monitoring detects
    it without assuming `/ready` will.

## 5. Non-functional checks

- Arabic RTL layout at mobile, tablet, and desktop widths. English/LTR is a future
  internationalization gate, not a current UI mode.
- Keyboard-only navigation, visible focus, labels, and error announcements on implemented
  controls. Add dialog-specific checks when shared dialogs are introduced.
- Light and dark themes without hardcoded unreadable colors.
- Expired JWT clears the session and returns the user to login.
- Slow and failed requests show loading, retry, empty, and error states.
- Product and queue lists remain usable at expected production volumes.
- Database backup, restore, retention, and rollback procedures have been exercised.
- Repeat time-sensitive checks relative to the execution time (for example, "published
  during this verification window"), not hard-coded calendar dates or "today" fixtures.

## 6. Release and rollback

- Record image digests, migration revision, environment version, and acceptance owner.
- Promote the exact staging images; do not rebuild between staging and production.
- Monitor API error rate, worker failures, queue age, provider errors, and publish success.
- Roll back application images if health degrades. Roll back database changes only through a
  reviewed Alembic downgrade or forward-fix procedure.

## 7. Current verification boundary

The repository defines frontend typecheck, lint, unit/component tests, and production build
checks. Record fresh command output and CI run IDs for each release; do not treat a
time-sensitive statement that they once passed as permanent evidence.
Provider-backed staging acceptance requires valid staging credentials and reachable
PostgreSQL/Redis/Celery services; it cannot be certified by mocked tests alone.

## 8. Security and tenancy boundaries

- The browser stores the access JWT in `sessionStorage`; the middleware cookie is a
  presence-only marker and is not proof of authentication. `AuthGuard` confirms `/auth/me`.
- A `401` clears local session state. There is no refresh-token flow.
- Product import endpoints require admin access. Public registration cannot create admins.
- Queue and channel HTTP routes require authentication but their data access is not
  tenant/user scoped in the current backend. Do not represent them as isolated per user or
  deploy this boundary as multi-tenant SaaS without backend ownership enforcement.
- `/ready` exposes dependency state only; keep secrets and provider payloads out of status
  responses and logs.
