# Production Readiness and Release Runbook

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
- The Playwright smoke flow in an environment with a browser installed.

Do not release from a working tree or commit with a failing or skipped required check.

## 3. Staging deployment

1. Build immutable backend and frontend images.
2. Apply Alembic migrations.
3. Start PostgreSQL, Redis, API, Celery worker, and Celery beat.
4. Confirm `GET /health` returns `200`.
5. Confirm `GET /ready` returns `200` with database and Redis both `up`.
6. Start the frontend and confirm login redirects to the protected dashboard.
7. Confirm API and frontend security headers are present.
8. Confirm application logs contain no passwords, tokens, provider payloads, or secrets.

## 4. MVP acceptance flow

Execute this flow with a staging admin account:

1. Authenticate and load the dashboard.
2. Browse hot, trending, deals, keyword, and category discovery modes.
3. Verify rating, order, price, discount, free-shipping, and sort controls affect results.
4. Import one product and verify its details and images.
5. Generate Arabic content and review/edit the result.
6. Register a staging Telegram channel and verify bot permissions.
7. Create a draft queue item, schedule it, and publish it.
8. Confirm the Telegram message, image, affiliate button, and published queue state.
9. Simulate an upstream AI/AliExpress error and confirm safe user feedback.
10. Simulate an unavailable Redis worker and confirm readiness/queue behavior is observable.

## 5. Non-functional checks

- Arabic RTL and English LTR layout at mobile, tablet, and desktop widths.
- Keyboard-only navigation, visible focus, labels, dialogs, and error announcements.
- Light and dark themes without hardcoded unreadable colors.
- Expired JWT clears the session and returns the user to login.
- Slow and failed requests show loading, retry, empty, and error states.
- Product and queue lists remain usable at expected production volumes.
- Database backup, restore, retention, and rollback procedures have been exercised.

## 6. Release and rollback

- Record image digests, migration revision, environment version, and acceptance owner.
- Promote the exact staging images; do not rebuild between staging and production.
- Monitor API error rate, worker failures, queue age, provider errors, and publish success.
- Roll back application images if health degrades. Roll back database changes only through a
  reviewed Alembic downgrade or forward-fix procedure.

## 7. Current verification boundary

Local frontend typecheck, lint, unit/component tests, and production build have passed.
Provider-backed staging acceptance requires valid staging credentials and reachable
PostgreSQL/Redis/Celery services; it cannot be certified by mocked tests alone.
