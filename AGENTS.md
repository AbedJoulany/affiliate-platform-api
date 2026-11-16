# AGENTS.md — Product A MVP / Codex Instructions

## Mission and authority

Build **Product A: Affiliate Marketing Assistant MVP**. This is a practical end-to-end product, **not a SaaS or affiliate-network marketplace**. Read `docs/product-a-mvp-roadmap.md` for scope, milestones, and acceptance criteria. Inspect the code before making technical claims: the roadmap is a **plan**, not evidence of implemented behavior.

Desired manual flow: `Discover → Filter → Evaluate → Recommend → Select → Generate → Review/Edit → Queue → Schedule → Publish → Measure`.

Later automation reuses existing services: `Discovery → Recommendation → AIContentService → QueueService → existing Scheduler → existing Publisher`. It must not create a parallel publishing pipeline.

## Current baseline and status

- PRs #5, #7, #8, #9, #10, #11, #12, #13, #14, and #15 are merged into `main`; PR #15 is the current baseline (`b0593f8a72c8ec2866793e8df2d70d04070272bc`).
- **Phase 0 is partially verified:** manual Telegram publishing, image/affiliate-link delivery, and scheduling were operator-verified; controlled live failure/retry verification remains pending.
- Phase 3A Page connection, Phase 3B Facebook publishing backend, Phase 3C.1 frontend destination selection, Phase 3C.2 Queue Display & Safe Ambiguous Retry, and Phase 3C.3 publishing safety/live validation are implemented and merged. **Phase 4 — Operational Dashboard is next.**
- Facebook uses manual Page ID + Page Access Token connection for this MVP. OAuth and Facebook Login are deferred.
- Controlled live Facebook text, image, and scheduled publishing were operator-verified before PR #15; do not treat mocked tests or CI as live provider evidence. Strict exactly-once delivery is not claimed.
- Current Alembic head is `019`; historical migrations `001–019` are protected unless a later migration is explicitly approved.
- Before beginning work, check the actual branch, HEAD, working tree, migrations, and tests. Do not assume this status note is forever current.

## Non-negotiable scope

- Preserve Product A and existing Discovery/AliExpress, Products, AI Studio, Queue, scheduling, Telegram Channels, Dashboard, Workspace, auth/refresh, Redis/Celery, and SSE functionality.
- Preserve `Product.affiliate_url` and `Product.commission_rate` and their Product A semantics.
- **Never silently substitute `product_url` for `affiliate_url`** as a marketing CTA. A manual post may omit a CTA when no affiliate URL is available; unattended automation should skip products lacking a valid affiliate URL unless explicitly approved otherwise.
- **Do not reintroduce Product B**: affiliate network marketplace, campaigns/conversions/click tracking, Product B analytics, or `AFFILIATE`/`ADVERTISER` roles.
- Do not add SaaS subscriptions, billing, plans, advanced analytics, ML recommendation, AI agents, additional social networks, or unrelated features without explicit approval.
- Keep workspace authorization and tenant isolation intact.

## Architecture and database safety

- Prefer existing FastAPI API/service/repository/schema layers and Next.js feature structure. Reuse established patterns rather than broad refactors.
- Preserve the existing queue, scheduler, publish-attempt history, retry/idempotency behavior, and provider-specific publisher integration.
- **Never modify historical Alembic migrations `001–019`**. Add a later migration only when a real schema change requires one; include upgrade/downgrade and verify compatibility.
- Do not alter existing catalog product score semantics accidentally. For Recommendation Engine, prefer a separate deterministic and explainable recommendation score, with defined normalization, missing-data policy, stable tie-breakers, and tests.
- Treat credentials and tokens as secrets: never print, commit, or put them in frontend storage unless existing approved flows require it. Facebook page tokens (when implemented) must be handled server-side.
- Provider-aware Queue, existing SSE/polling fallback, Celery scheduling, and publish-attempt history must remain compatible.
- An ambiguous Facebook attempt requires operator inspection and explicit confirmation before retry; it must never be retried automatically.
- Automation must reuse Discovery, Recommendation, AIContentService, QueueService, the existing Scheduler, and the existing Publisher. Unattended automation must fail closed when a valid affiliate URL is missing.

## Workflow for every task

1. **Inspect**: read relevant code, `AGENTS.md`, roadmap, docs, and tests; check Git status and current branch.
2. **Plan**: state scope, affected files, API/DB impacts, edge cases, and test plan. Flag ambiguities and deviations from the roadmap.
3. **Wait for approval** before implementation when the user requests an inspection/plan or has not authorized code changes.
4. **Implement narrowly**: avoid unrelated changes and new dependencies unless justified.
5. **Verify**: run focused tests and broader relevant suites where environment permits. Report exact commands and results; explicitly identify tests that could not run.
6. **Report**: summarize behavior, changed files, regressions, limitations, migrations, and remaining live checks.
7. **Git safety**: do **not** commit, push, open PRs, merge, rebase, reset, force-push, or alter `main` without explicit authorization for that action. Prefer a fresh feature branch from updated `main` after approval. Never overwrite user changes.

## Phase 0: live Telegram verification gate

Verify with real, authorized credentials and a test channel: login/workspace → default active Telegram channel → AliExpress product with `affiliate_url` → AI generation/edit → queue with image/affiliate CTA → publish now and scheduled publish → actual Telegram delivery → queue status and attempt record → controlled failure → failed state → retry creates a new attempt. Never expose credentials in logs or reports. If live verification cannot run, report it as **pending**, not passed.

## Roadmap Phase 1: Recommendation Engine requirements

- Inspect existing discovery/filter/scoring code before choosing endpoint or component design.
- Filters: keywords, price range, minimum rating/orders/discount, and minimum/maximum commission as supported by actual data.
- Deterministic weighted ranking; suggested **initial** weights: rating 30%, orders 20%, discount 15%, price 10%, commission 25%. Validate normalization and the meaning of price desirability before adopting them.
- Explainable output: score and criterion contributions; explicit missing-value handling and stable tie-breaking.
- Preserve old catalog score behavior and the existing Discovery → AI → Queue handoff.
- Prefer no database migration for initial stateless recommendations; add persistence only when needed and approved.
- Test filters/boundaries, weights, missing values, tie-breaking, Top N, request mapping, UI explanation, and regressions.

## Quality and completion

- Backend: run available lint/type checks and pytest; frontend: typecheck, unit tests, lint/build as relevant; E2E for changed critical flows where supported.
- Mock third-party providers in CI, but keep **live provider verification** as a separate acceptance gate.
- Do not mark a roadmap phase complete without acceptance criteria and evidence. Update `docs/product-a-mvp-roadmap.md` only after verified changes are accepted.
- If environment dependencies are unavailable, do not report tests as passed. Describe the blocker and provide reproducible commands or CI evidence.

## Communication

Respond with concise, concrete implementation plans and results. Distinguish **confirmed facts**, **assumptions**, **proposals**, and **unverified live behavior**. Ask before expanding scope. Default to minimal MVP solutions.
