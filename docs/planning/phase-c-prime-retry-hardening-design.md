# Phase C' — Non-Telegram Retry Hardening Design

**Status:** COMPLETE — Phase C' Tasks 0–5 shipped (2026-08-09). Historical Task 0 ADR retained; implementation and session task numbering follow the decisions below (see §1 closeout note for the executed task sequence).
**Author context:** Backend architecture session, analysis-only originally; closeout documents shipped reality.
**Scope owner:** Phase C' — Non-Telegram retry hardening (AliExpress, OpenAI, Gemini). Telegram publishing retry/idempotency is Phase A.1 (complete) and explicitly out of scope here.
**Roadmap authority:** `docs/08-implementation-roadmap.md` §3 "Phase C' — Non-Telegram retry hardening"

This document began as a Task 0 architecture decision record grounded in the repository state at analysis time. **Phase C' Tasks 1–5 have since shipped**; treat the repository implementation as the runtime source of truth. Where early §2 "current state" snapshots describe pre-implementation gaps (especially AI "zero retry" and the categories service-layer re-wrap), the **shipped** behavior in §1 Closeout and `docs/08-implementation-roadmap.md` / `docs/10-production-readiness.md` §9.3 is authoritative.

---

## 1. Status / Executive Summary

**COMPLETE (Tasks 0–5).** Task 0 decisions below remain the architectural rationale. Do not re-introduce Celery HTTP `autoretry_for` for AliExpress failures already owned by `_execute_with_retries`. Do not move AI generation onto Celery. A.1 and A.2 remain stable and must not be modified by Phase C' follow-ups.

Phase C' is asymmetric, not a "treat AliExpress and AI the same way" task. **AliExpress already had a complete client-level retry system** — exponential backoff with jitter, a rate-limit gate, and explicit retryable/non-retryable error classification, all inside `app/aliexpress/api_client.py`. Phase C' **preserved** that policy, added regression tests, and fixed discovery exception hygiene so all three discovery refresh paths propagate `app.aliexpress.exceptions.AliExpressAPIError`. **OpenAI and Gemini** received a shared provider-layer retry helper (`app/ai/retry.py`) with a **2-attempt** budget — Celery is not in the AI path.

Because the AliExpress client already retries internally before any exception reaches Celery, nesting `autoretry_for=(AliExpressAPIError,)` on discovery tasks would multiply outbound AliExpress calls (up to ~16×) with no correctness benefit (§5). That nesting remains **forbidden**.

**Executed session sequence (mapped to this document's decisions):**

| Session task | Outcome |
| --- | --- |
| Task 0 | This ADR — ownership locked |
| Task 1 | AliExpress retry tests + discovery exception hygiene (§6/§7) |
| Task 2 | AI shared retry helper + OpenAI/Gemini wiring (§8–§11) |
| Task 3 | No-nested-Celery-HTTP-retry regression (§5/§19.5) |
| Task 4 | API/integration regression validation |
| Task 5 | Documentation closeout |

(Design §21's finer AI split into separate abstraction/OpenAI/Gemini tasks was implemented as a single provider-hardening task; decisions are unchanged.)

**Shipped ownership diagram:**

```text
AliExpress HTTP failures → api_client._execute_with_retries → discovery/API
AI provider failures → OpenAI/Gemini + app/ai/retry.py → AIProviderError → existing API

Celery HTTP retry for AliExpress: NOT USED
Celery retry for AI generation: NOT USED
```

**Explicit non-goals verified:** no DB migration; no queue/SSE events; no frontend changes; no Telegram/A.1/A.2 changes; no new API endpoints; no Prometheus.

This document locks seven decisions (§23), defines per-provider failure classification (§10, §11), and records that no database migration, no new events, and no frontend work were required (§13–§16).

---

## 2. Current State (Task 0 baseline — historical)

> **Closeout note:** §2 describes the repository **at Task 0 analysis time**. After Phase C' completion: AI providers **do** retry via `app/ai/retry.py`; `refresh_categories` **no longer** re-wraps to `app.services.exceptions.AliExpressAPIError` (all three discovery refresh paths propagate the domain exception). Keep §2 for ADR context; do not treat its "zero AI retry" / categories re-wrap statements as current runtime truth.

### 2.1 AliExpress

Verified in `app/aliexpress/api_client.py` (`AliExpressAPIClient`, the shared base client) and `app/aliexpress/client.py` (`AliExpressAffiliateClient`, the facade used by discovery):

- `_execute_with_retries()` (lines 160–187) loops `aliexpress_max_retries + 1` times per `call_method()` invocation.
- `_is_retryable()` classifies failures: `AliExpressRateLimitError` always retries; other `AliExpressAPIError`s retry only if `code` is in `RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}` or the message contains `"timeout"`/`"temporarily"`; `AliExpressCredentialsError` is caught separately and **re-raised immediately without consuming a retry** (`except AliExpressCredentialsError: raise`).
- `_backoff_seconds()` computes `aliexpress_retry_backoff_seconds * (2 ** attempt) + random.uniform(0, 0.25)` — exponential backoff with jitter.
- `_apply_rate_limit()` enforces a minimum inter-request interval (`aliexpress_rate_limit_interval_seconds`, default 0.2s) via an `asyncio.Lock`, independent of the retry loop — this runs before every attempt, not just retries.
- `app/core/config.py` defines `aliexpress_max_retries: int = 3`, `aliexpress_retry_backoff_seconds: float = 0.5`, `aliexpress_rate_limit_interval_seconds: float = 0.2` — all already read directly inside the retry/backoff/rate-limit code, not merely declared and unused.

**`ALIEXPRESS_MAX_RETRIES` is already enforced, not merely configured.** It is the literal loop bound in `_execute_with_retries`'s `for attempt in range(max_retries + 1)`. The roadmap's phrasing ("add `ALIEXPRESS_MAX_RETRIES` enforcement review") is misleading if read as "enforcement doesn't exist yet" — it does. What is genuinely missing is test coverage (§7) and an explicit decision that Celery must not duplicate this (§5).

### 2.2 OpenAI

Verified in `app/ai/openai_provider.py`. `OpenAIProvider.generate_content()`:

- Makes exactly one `httpx.AsyncClient(timeout=60.0).post(...)` call to `{base_url}/chat/completions`.
- `except httpx.HTTPStatusError as exc:` → immediately raises `AIProviderError(f"OpenAI request failed: {detail}")` where `detail = exc.response.text` (the raw response body, included verbatim in the error message — see §18 for the associated, pre-existing detail-leak note).
- `except httpx.HTTPError as exc:` → immediately raises `AIProviderError(f"OpenAI request failed: {exc}")` for any network-level failure (timeout, connection error, etc.).
- No status-code inspection occurs before raising — `exc.response.status_code` and any `retry-after`-style header are read nowhere in this file.
- No retry loop, no backoff, no jitter, no classification. First failure is the final failure.

### 2.3 Gemini

Verified in `app/ai/gemini_provider.py`. `GeminiProvider.generate_content()` is structurally identical to OpenAI's: single `httpx.AsyncClient(timeout=60.0).post(...)` to `{base_url}/models/{model}:generateContent`, same two-branch `except httpx.HTTPStatusError` / `except httpx.HTTPError` → immediate `AIProviderError`, same absence of status-code inspection, retry, backoff, or jitter.

The two providers share no code (no shared HTTP helper, no shared retry wrapper) — each independently implements the same "no retry" shape. Any future retry policy must be added to both files individually unless a shared helper is introduced (this document does not mandate one; see §8).

### 2.4 Celery Discovery Tasks

Verified in `app/worker/tasks/discovery.py` and `app/services/product_discovery_persistence.py`:

- `refresh_hot_products`, `refresh_trending_products`, `refresh_categories` are declared as plain `@celery_app.task(name=...)` with **no** `autoretry_for`, `max_retries`, `retry_backoff`, or `retry_kwargs` of any kind. This is confirmed by direct inspection of `app/worker/tasks/discovery.py` (compare with `app/worker/tasks/publishing.py`, which does set these for the two Telegram tasks).
- `refresh_hot_products` / `refresh_trending_products` both funnel through `ProductDiscoveryPersistenceService._refresh_discovery_mode()`, which calls `ProductDiscoveryService.discover()` with **no try/except anywhere in the call chain** — whatever `app.aliexpress.exceptions.AliExpressAPIError` (or its subclasses `AliExpressRateLimitError`, `AliExpressCredentialsError`) the client raises after exhausting its own retry budget propagates unmodified straight to Celery.
- `refresh_categories` is different: `ProductDiscoveryPersistenceService.refresh_categories()` explicitly wraps its call — `except AliExpressAPIError as exc: raise ServiceAliExpressAPIError(exc.message, code=exc.code) from exc` — where `ServiceAliExpressAPIError` is `app.services.exceptions.AliExpressAPIError`, imported under an alias specifically because it is a **different class** from `app.aliexpress.exceptions.AliExpressAPIError` despite sharing the exact same name. See §6.
- No task in this file catches its own exceptions to retry-in-place or to swallow-and-continue (contrast with `TelegramPublishingService._publish_items`, which deliberately swallows per-item failures in a batch — the discovery tasks have no equivalent per-item batching, so this pattern does not apply here).

### 2.5 Existing Error Propagation

```text
AliExpress path (hot/trending):
  api_client._execute_with_retries (up to 4 attempts, self-contained)
    → raises app.aliexpress.exceptions.AliExpressAPIError (or subclass)
    → ProductDiscoveryService.discover() [no catch]
    → ProductDiscoveryPersistenceService._refresh_discovery_mode() [no catch]
    → Celery task body [no catch, no autoretry_for]
    → Celery marks task FAILURE (visible in Flower, Phase B)

AliExpress path (categories):
  api_client._execute_with_retries (up to 4 attempts, self-contained)
    → raises app.aliexpress.exceptions.AliExpressAPIError
    → ProductDiscoveryPersistenceService.refresh_categories() [catches and
      RE-RAISES app.services.exceptions.AliExpressAPIError — a different class]
    → Celery task body [no catch, no autoretry_for]
    → Celery marks task FAILURE

AI path (both providers):
  httpx.AsyncClient.post() [single attempt, no retry]
    → raises AIProviderError immediately on any HTTPStatusError/HTTPError
    → AIContentService.generate_marketing_content() [no catch]
    → app/api/v1/ai_content.py route [catches ServiceError generically]
    → HTTPException(status_code=502, detail=message)
    → frontend renders the message (already wired — see §15)
```

---

## 3. Retry Ownership Decision

| Integration | Current Retry Layer | Phase C' Retry Layer | Celery Retry? | Decision |
| --- | --- | --- | --- | --- |
| AliExpress HTTP/API calls (all methods via `api_client.py`) | Client (`_execute_with_retries`) — **already implemented** | Client (unchanged — no new layer) | **No** | Keep as-is. Existing behavior, not missing behavior. |
| AliExpress Celery discovery tasks (`refresh_hot_products`, `refresh_trending_products`, `refresh_categories`) | None | None (no new Celery-level retry for HTTP-class errors) | **No, explicitly** | Missing behavior only in the sense of "no retry for non-HTTP failures" (e.g. a DB commit error) — not a gap Phase C' commits to filling now; see §5 and §20 |
| OpenAI provider requests | None — **missing behavior** | Provider/client layer (inside `OpenAIProvider.generate_content`) | **No — not architecturally possible** (§8, §2.5) | Planned behavior — implement per §9/§10 |
| Gemini provider requests | None — **missing behavior** | Provider/client layer (inside `GeminiProvider.generate_content`) | **No — not architecturally possible** | Planned behavior — implement per §9/§11 |
| `AIContentService` (orchestration layer) | None, and none needed | None — must not independently retry | N/A (not a Celery task) | Existing behavior stays; no service-layer retry added |
| `POST /ai-content/generate` (API route) | None, and none needed | None | N/A | Existing error contract (`ServiceError` → `HTTPException`) unchanged |

---

## 4. AliExpress Retry Architecture

Current, unmodified, already-shipped behavior (`app/aliexpress/api_client.py`):

| Property | Value |
| --- | --- |
| Retry loop | `_execute_with_retries`, iterates `for attempt in range(max_retries + 1)` |
| Max attempts | `aliexpress_max_retries + 1` = **4** (1 initial + 3 retries), from `Settings.aliexpress_max_retries = 3` |
| Backoff | `aliexpress_retry_backoff_seconds * (2 ** attempt)` = `0.5 * 2^attempt` seconds (0.5s, 1s, 2s for attempts 0/1/2) |
| Jitter | `+ random.uniform(0, 0.25)` seconds, added on every backoff sleep |
| Rate limiting | Separate mechanism (`_apply_rate_limit`), not part of the retry loop — enforces `aliexpress_rate_limit_interval_seconds` (default 0.2s) minimum spacing between **all** requests, retries included |
| Retryable exceptions | `AliExpressRateLimitError` (always, within budget); `AliExpressAPIError` when `code` ∈ `{408, 429, 500, 502, 503, 504}` or message contains `"timeout"`/`"temporarily"` |
| Non-retryable exceptions | `AliExpressCredentialsError` (invalid app key/secret) — re-raised on first occurrence, consumes no retry budget; any `AliExpressAPIError` not matching the retryable set above (conservative default: unclassified errors are treated as permanent) |
| Exception propagation | Fully self-contained — the loop either returns a successful payload or raises the final `AliExpressAPIError`/subclass after the budget is exhausted. Nothing above this method (service layer, Celery task) can observe how many attempts occurred; it only ever sees success or one final exception. |

This is a complete, correctly-shaped retry implementation. **Phase C' does not need to add anything at this layer.**

---

## 5. AliExpress Celery Boundary

**This is the most important decision in this document.**

Confirmed: none of `refresh_hot_products`, `refresh_trending_products`, `refresh_categories` currently use `autoretry_for`, `max_retries`, `retry_backoff`, `retry_kwargs`, or any other Celery retry mechanism (`app/worker/tasks/discovery.py`, full file inspected — bare `@celery_app.task(name=...)` decorators only).

If a future implementer added, by analogy to Phase A.1's Telegram tasks:

```python
@celery_app.task(
    name="app.worker.tasks.discovery.refresh_hot_products",
    autoretry_for=(AliExpressAPIError,),
    max_retries=3,
    retry_backoff=True,
)
def refresh_hot_products() -> dict:
    return run_async(_refresh_hot_products())
```

the resulting behavior would be:

```text
Client layer:  up to (aliexpress_max_retries + 1) = 4 attempts, already exhausted
               before the exception ever reaches Celery.

Celery layer:  up to (max_retries + 1) = 4 task executions, EACH of which
               re-enters the client and performs its own up-to-4-attempt loop
               from scratch.

Worst case:    4 (Celery executions) × 4 (client attempts per execution)
               = 16 outbound AliExpress HTTP calls for a single transient
               failure condition that the client alone was already designed
               to fully absorb in 4 calls.
```

This is a **4x amplification with zero correctness benefit** — unlike Telegram (A.1), where layering Celery retry on top of client retry is safe *because* the idempotency guard (`queue_id` + content hash, 24h window) makes repeated executions a no-op rather than a duplicate side effect. AliExpress discovery calls have no equivalent duplicate-send risk (they are read-only catalog queries), so there is no safety mechanism that would make the nested retry "free" the way it is for Telegram — it is pure amplification against a rate-limited external API.

> **DO NOT add Celery-level retry for the same AliExpress HTTP exceptions already handled by the client** (`AliExpressAPIError` and its subclasses `AliExpressRateLimitError`, `AliExpressCredentialsError`, `AliExpressImageSearchNotSupportedError`, and the aliased `app.services.exceptions.AliExpressAPIError` used by `refresh_categories` — see §6).

If a future need is demonstrated for Celery-level retry in this area, it may **only** cover failures that occur *outside* the HTTP client's ownership — for example, a transient database error during `ProductImporter.upsert_many`'s commit, or a `session_maker`/connection-pool failure. Those are a structurally different exception family (SQLAlchemy/database exceptions, not `AliExpressAPIError`), require their own classification analysis, and are explicitly **not implemented, scoped, or designed by this document**. This document only rules out the wrong approach; it does not commit Phase C' to building the narrow alternative either, absent evidence that database/infrastructure failures during discovery are an actual observed problem.

---

## 6. AliExpress Exception Consistency

Two distinct exception classes share the identical name `AliExpressAPIError`:

1. `app.aliexpress.exceptions.AliExpressAPIError` — the client-layer exception, raised by `api_client.py`. Subclasses: `AliExpressRateLimitError`, `AliExpressCredentialsError`, `AliExpressImageSearchNotSupportedError`.
2. `app.services.exceptions.AliExpressAPIError` — a `ServiceError` subclass (HTTP 502), used for API-facing error responses across the service layer generally.

`app/services/product_discovery_persistence.py` imports both in the same file, disambiguating with an alias:

```python
from app.aliexpress.exceptions import AliExpressAPIError
from app.services.exceptions import AliExpressAPIError as ServiceAliExpressAPIError
```

`refresh_categories()` explicitly catches the first and re-raises the second. `refresh_hot_products()` / `refresh_trending_products()` (via `_refresh_discovery_mode()`) do neither — they let the first class propagate unmodified.

**Why this matters:** any future Celery-level `autoretry_for=(...)` tuple (even one scoped correctly per §5, for non-HTTP failures only, or one written later by someone who has not read this document) must name the *correct* exception class for each task. A tuple written against `app.aliexpress.exceptions.AliExpressAPIError` would silently fail to catch what `refresh_categories` actually raises, and vice versa. This is a concrete, verified correctness trap, not a hypothetical one.

**This document does not fix it.** It is recorded here as a **prerequisite hygiene item** for whichever implementation task first needs to reason precisely about exception types across all three discovery tasks (see Task 1, §21). Any future work in this area — even work limited to tests — **must use one canonical exception type per propagation path**, and must not assume the three discovery tasks are exception-consistent with each other until this is resolved.

---

## 7. AliExpress Test Coverage Gap

Inspected: `tests/test_aliexpress_api_client.py`, `tests/test_product_discovery_service.py`, `tests/test_aliexpress_scoring.py`, `tests/test_aliexpress_endpoints.py`, `tests/test_product_importer.py`. No test file exists for `app/worker/tasks/discovery.py` itself.

| Behavior | Covered? | Evidence |
| --- | --- | --- |
| Retryable HTTP status classification | **No** | `test_aliexpress_api_client.py` contains exactly 4 tests: request building, `call_method` → IOP SDK execution, and response-parsing/meta-extraction (`test_extract_products_and_meta_*`). None exercise `_is_retryable`. |
| Non-retryable HTTP status classification | **No** | Same as above |
| Network failure handling | **No** | No test simulates a raised network exception from `asyncio.to_thread(client.execute, request)` |
| Rate-limit handling (`AliExpressRateLimitError`, `_apply_rate_limit`) | **No** | Not referenced anywhere in the test file |
| Max retry enforcement (`aliexpress_max_retries` loop bound) | **No** | No test asserts the number of attempts made before final failure |
| Backoff calculation (`_backoff_seconds`) | **No** | Not tested |
| Jitter | **No** | Not tested |
| Retry exhaustion (final exception raised after budget) | **No** | Not tested |
| No-nested-retry behavior (discovery task does not multiply client retries) | **No** | No test exists for `app/worker/tasks/discovery.py` at all |
| Discovery service dedupe/filter/sort/mode-dispatch | **Yes** | `test_product_discovery_service.py` covers `test_dedupe_products`, `test_apply_filters`, `test_apply_sort_orders_desc`, `test_discover_hot_delegates_to_client` — none touch retry, all pre-date and are orthogonal to this analysis |
| Product upsert idempotency | **Yes** | `test_product_importer.py`: `test_importer_creates_new_product`, `test_importer_updates_existing_product_by_aliexpress_id`, `test_importer_upsert_many_counts_created_and_updated` — confirms the upsert path itself is already tested (relevant to §17) |

**Summary:** the entire retry/backoff/rate-limit/classification surface of `_execute_with_retries` has **zero** direct test coverage today, despite being fully implemented and load-bearing. This is a pre-existing gap, not something Phase C' introduces — closing it (Task 1, §21) is valuable independent of any new retry work, since it protects already-shipped behavior that currently has no regression protection.

---

## 8. AI Provider Retry Architecture

**AI retry belongs at the provider/client layer, not Celery.**

Verified via full-repository grep across `app/worker/`: no match for `AIContentService`, `get_ai_provider`, `generate_content`, or `generate_marketing_content` anywhere in the Celery worker package. `POST /ai-content/generate` (`app/api/v1/ai_content.py`) calls `AIContentService(db).generate_marketing_content(...)` directly and `await`s it inline within the request handler; the response is returned in the same HTTP request/response cycle. No queue, no task dispatch, no deferred execution exists in this path today.

This means:

- Celery is **architecturally unavailable** as a retry layer for AI generation — there is no task boundary to attach `autoretry_for` to.
- **Introducing one is out of scope for Phase C'.** Making AI generation asynchronous (dispatch to Celery, poll or push a result) would be a materially larger architectural change than "retry hardening" — it would touch the API contract (`POST /ai-content/generate` would need to become a job-submission endpoint), the frontend (which currently awaits a synchronous response — see `docs/06-api-integration.md` §4.5, "Connected" status, and `ContentWorkspaceView.tsx`'s direct `generation.isError`/`generation.error` usage), and session-persistence assumptions. Nothing in the roadmap or this analysis justifies that scope expansion.
- Retry must therefore complete **within the existing synchronous request**, which bounds how aggressive it can be (§9, §18) — a retry policy appropriate for a background Celery task (minutes of backoff, many attempts) is not appropriate here.
- Retry logic should live inside `OpenAIProvider.generate_content()` and `GeminiProvider.generate_content()` respectively (or a small shared helper both call), because each provider is the only layer with visibility into its own HTTP status codes and error-body shape (§10, §11). Neither `AIContentService` nor the API route should attempt classification themselves — they would have to either duplicate provider-specific logic or treat all providers identically, which §7 of the originating analysis and this document's §11 both reject as too coarse.

Also confirmed: both providers already convert every `httpx.HTTPStatusError`/`httpx.HTTPError` into `AIProviderError` uniformly, with no status-code inspection — this is the exact place any retry/classification logic must be inserted (not implemented here).

---

## 9. AI Retry Policy

**Decision: maximum 2 total attempts (1 initial + 1 retry).**

The prompt's suggested baseline (max 2 attempts, transient-only retry, bounded exponential backoff, jitter if appropriate, honor `Retry-After` when available) is **validated, not blindly copied**, against the actual implementation:

- Both providers use `httpx.AsyncClient(timeout=60.0)` **per attempt**. A policy with more than 2 attempts risks a worst-case latency of `N × 60s + backoff`, which is unacceptable for a synchronous, user-waiting API call (§8, §18) — 3 attempts (AliExpress/Telegram's number) would allow up to ~180s of worst-case wait, nearly triple what a user of a "generate content" button should ever be asked to tolerate. 2 attempts caps worst case near ~120s + a few seconds of backoff, still long but a meaningfully smaller multiplier.
- AliExpress's and Telegram's "3 retries" figures were each independently tuned for fast, cheap, high-volume calls (catalog queries, bot messages) — not for a slow, expensive, per-request-billed LLM call. Reusing their number here would not be "consistency," it would be applying a constant derived from a different cost/latency profile.

| Parameter | Decision |
| --- | --- |
| Maximum attempts | **2** (1 initial + 1 retry) |
| Base backoff | **1.0s** — deliberately higher than AliExpress's 0.5s base, because AI calls already run in the 1–10s+ range under normal conditions; a sub-second base would be proportionally negligible |
| Exponential backoff? | Yes, same shape as the existing AliExpress/Telegram implementations: `base * (2 ** attempt)` |
| Jitter? | Yes — small jitter (e.g., `uniform(0, 0.5)`), consistent with the existing pattern, to avoid synchronized retry storms if multiple requests fail at once |
| Retryable errors | Network-level failures with no response (`httpx.ConnectError`, `httpx.ConnectTimeout`, `httpx.ReadTimeout`); HTTP `429`; HTTP `500`/`502`/`503`/`504` |
| Non-retryable errors | HTTP `400` (malformed request — retrying reproduces the identical error); HTTP `401`/`403` (invalid/revoked API key — permanent until an operator intervenes, exactly analogous to AliExpress's `AliExpressCredentialsError` treatment); HTTP `404` (bad model/endpoint — configuration error); a successfully-received response that fails to parse into the expected shape (`KeyError`/`IndexError`/`TypeError`, already caught by both providers today) — retrying an identical request against a response-shape bug produces the identical malformed response |
| Honor `Retry-After`? | **Yes, when the provider supplies it** — OpenAI is documented to return a `retry-after`-bearing header/body on 429 responses; if present, it should override the calculated backoff (mirroring Telegram's existing `_rate_limit_delay` pattern). Verified gap: neither provider file currently inspects response headers at all before converting to `AIProviderError`, so this information is available in `httpx.HTTPStatusError.response` but is currently discarded — implementing retry necessarily means capturing it before the conversion happens, not after. |
| Behavior on exhaustion | Identical external shape to today: raise `AIProviderError` with the same message format, which the existing route/frontend wiring already handles end-to-end (§15). Exhaustion must not change the error contract — only the number of attempts made before it is reached. |

This policy intentionally **does not match AliExpress's or Telegram's numbers**. It is derived from AI's own latency/cost/synchronicity constraints, per the safety rule against blind copying.

---

## 10. OpenAI Error Classification

Analyzed independently, based on `app/ai/openai_provider.py`'s actual call shape (`POST {base_url}/chat/completions`) and OpenAI's documented API error conventions:

| Condition | Retryable? | Reasoning |
| --- | --- | --- |
| Network failure (no response received) | Yes | Transient; the request may not have reached OpenAI at all |
| HTTP `429` (rate limit / quota) | Yes | OpenAI documents a `retry-after`-bearing response on rate limiting; honor it per §9 |
| HTTP `500`/`502`/`503` | Yes | Standard transient server-side failure |
| HTTP `400` (invalid request, e.g. bad `model` parameter or malformed messages array) | No | Deterministic — retrying sends the identical invalid payload |
| HTTP `401` (invalid API key) | No | Permanent until `settings.openai_api_key` is corrected |
| HTTP `403` (insufficient permissions for the requested model) | No | Permanent configuration issue |
| HTTP `404` (unknown model) | No | Configuration error (`settings.openai_model`) |
| Successful HTTP response, but `response.json()`'s `choices[0].message.content` path is missing/malformed (already caught today via `except (KeyError, IndexError, TypeError)`) | No | Not a transport failure — identical request would reproduce the identical malformed response |

**Provider-specific error body consideration:** OpenAI's error responses are typically a JSON body of the shape `{"error": {"message": ..., "type": ..., "code": ...}}`. The current code (`openai_provider.py`) discards this entirely, using only `exc.response.text` as a raw string inside the `AIProviderError` message. Any classification logic added later should parse the status code from `exc.response.status_code` (already accessible on `httpx.HTTPStatusError`, simply unused today) rather than string-matching the error body, since the body's `type`/`code` fields are not currently verified against real OpenAI responses in this repository (no test captures one) and should not be trusted without validation during implementation (§19).

---

## 11. Gemini Error Classification

Analyzed independently — **not forced into OpenAI's classification**, per the explicit instruction not to treat providers identically where their semantics differ:

| Condition | Retryable? | Reasoning |
| --- | --- | --- |
| Network failure (no response received) | Yes | Same transient reasoning as OpenAI |
| HTTP `429` (Gemini quota/rate limit) | Yes | Transient by nature, though Gemini's `retry-after` header presence is **not verified in this codebase** (no test or captured response exists) — this must be confirmed during implementation (§19), not assumed identical to OpenAI's behavior |
| HTTP `500`/`503` (Gemini documents these for internal/overload errors) | Yes | Standard transient failure |
| HTTP `400` (invalid request — e.g. malformed `contents`/`generationConfig`) | No | Deterministic, same reasoning as OpenAI's 400 |
| HTTP `403` (API key invalid or Gemini API not enabled for the project) | No | Permanent configuration issue — Gemini's auth failure surfaces as 403 via the `key` query parameter, structurally different from OpenAI's header-based 401, but the retry decision (never retry) is the same |
| HTTP `404` (unknown model in `{model}:generateContent` path) | No | Configuration error (`settings.gemini_model`) |
| Successful HTTP response, but `candidates[0].content.parts[0].text` path is missing/malformed (already caught via `except (KeyError, IndexError, TypeError)`) | No | Same reasoning as OpenAI's equivalent case |

**Provider-specific error body consideration:** Gemini's error responses use a different JSON shape than OpenAI's (`{"error": {"code": ..., "message": ..., "status": ...}}`, with a Google-API-standard `status` string rather than OpenAI's `type`). Gemini also authenticates via a `key` query parameter rather than an `Authorization` header — meaning any future log line must be careful not to include the request URL verbatim if it still contains `?key=...` (a distinct, Gemini-specific secret-leak vector that does not apply to OpenAI's header-based auth; see §18).

**Where OpenAI and Gemini classification intentionally differ:** the *auth failure status code* (401 vs. 403) and the *secret exposure vector* (header vs. query parameter) are provider-specific and must remain provider-specific in implementation — a shared "retry these status codes" constant is reasonable (both treat 429/500/502/503/504 as retryable), but the auth-error and secret-handling logic must not be collapsed into one shared code path without accounting for this difference.

---

## 12. Retry Layering Rules

Explicit, regression-preventing architectural rule for Phase C' and beyond:

```text
HTTP/client layer:
  - Owns transport-level retries (network errors, HTTP status classification).
  - Owns provider-specific error classification (AliExpress's numeric/string
    codes; OpenAI's and Gemini's distinct HTTP status + JSON error shapes).
  - Owns backoff and jitter calculation.
  - Owns rate-limit / Retry-After handling where a provider supplies it.
  - Exhausts its own retry budget completely before ever raising to its caller.

Celery:
  - Does NOT retry the same HTTP/provider exceptions already retried by the
    client (AliExpress's AliExpressAPIError family). This applies regardless
    of which of the two AliExpressAPIError classes (§6) is in play.
  - Has NO retry role for AI generation at all — no Celery task exists in
    that path, and none should be introduced by Phase C' (§8).
  - If a future Celery-level retry is ever justified for AliExpress, it is
    strictly limited to failures OUTSIDE the HTTP client's ownership (e.g.
    database/session-maker failures during ProductImporter.upsert_many) — a
    different exception family, requiring its own future analysis, not
    designed or implemented here.

API/service layer (AIContentService, TelegramPublishingService-equivalent
  for AI if one existed, the ai-content API route):
  - Must NOT independently retry the same provider operation the client/
    provider layer already owns. AIContentService.generate_marketing_content
    calls provider.generate_content() exactly once per invocation; any retry
    happens inside that call, invisibly to AIContentService.
  - The API route's existing generic ServiceError → HTTPException mapping is
    unchanged — it must not gain integration-specific retry-awareness.
```

This rule is the direct generalization of §5's AliExpress-specific finding, extended to cover AI's zero-Celery-availability case, and is the single rule every future Phase C' implementation task must be checked against before merging.

---

## 13. Database Impact

**NO MIGRATION FOR PHASE C'.**

Verified: `app/models/queue.py`'s `QueuePublishAttempt` table carries `CheckConstraint("provider = 'telegram'", name="ck_queue_publish_attempts_provider_telegram")` and a `NOT NULL` foreign key to a specific `queue_id` (`queue_item` relationship, `cascade="all, delete-orphan"`). This table is:

1. **Schema-locked to Telegram** — inserting a row with `provider='aliexpress'` or `provider='openai'` would violate the check constraint at the database level, not merely be discouraged by convention.
2. **Structurally tied to a `QueueItem`** — AliExpress catalog refresh has no `queue_id` at all (it is not a queue-domain operation); most AI generations occur *before* any queue item exists (a user generates content, reviews it, and only then creates a queue draft from it).

Neither AliExpress nor AI retry work has a demonstrated requirement for a durable, queryable attempt-history record (no UI surface analogous to `QueueDetailsDrawer`'s attempt history is requested by the roadmap for these integrations). Application-level structured logging (§18) is sufficient for operator visibility. **No new table, no new column, no schema change of any kind is part of Phase C'.**

---

## 14. API Impact

**NO NEW API.**

`POST /ai-content/generate` must retain its current external error contract exactly:

- Success: `200` with `GenerateContentResponse` — unchanged.
- Failure: `ServiceError` subclasses (including `AIProviderError`) are caught generically in `app/api/v1/ai_content.py` and converted to `HTTPException(status_code=exc.status_code, detail=exc.message)` — this mapping is unchanged. `AIProviderError` continues to map to `502` with a message string.
- The only externally observable difference after Phase C' implementation should be **timing** (a transient failure may now succeed after a bounded retry instead of failing immediately) and, for exhausted-retry cases, no difference at all versus today.
- No new endpoints, no new request/response fields, no new query parameters. AliExpress-facing endpoints (`GET /products/discover*`, `GET /aliexpress/categories`, `POST /products/import*`) are entirely unaffected — their contracts do not change because their underlying client's retry behavior does not change (§4).

---

## 15. Frontend Impact

**NO NEW FRONTEND WORK.**

Verified: `app/api/v1/ai_content.py` already propagates `AIProviderError` (and any other `ServiceError`) as an `HTTPException` with the same `status_code`/`message` shape used across the rest of the API. `frontend/src/features/ai/components/ContentWorkspaceView.tsx` (line 144) already renders `generation.isError ? generation.error.message : null` — the error path from a failed AI generation to a visible message in the UI is **already fully wired and functioning today**, independent of anything Phase C' does.

Discovery's error handling is likewise already complete: `frontend/src/features/discovery/components/DiscoveryView.tsx` already renders an `ErrorState` component with an `onRetry` handler wired to `discovery.isError` (lines 70–77, 243, 324–326).

Because retry (at the provider/client layer, per §8) happens entirely before an HTTP response is ever sent to the frontend, it is **completely transparent** to both of these already-working UI paths — the frontend cannot distinguish "succeeded on attempt 1" from "succeeded on attempt 2," and only ever sees the final outcome. **This record classifies this roadmap sub-item ("surface AIProviderError to UI") as COMPLETE today, not as a Phase C' deliverable.**

---

## 16. Events / Realtime Impact

**NO QUEUE EVENTS / SSE CHANGES.**

AliExpress discovery refresh and AI content generation are not queue-domain operations — neither touches `QueueItem`, neither should ever publish to the A.2 `queue-events` Redis Pub/Sub channel, and neither should produce a new `QueueEventEnvelope` event type. No new SSE endpoint, no new event schema, no new frontend subscription. Retry hardening in Phase C' is backend/provider reliability work and must remain entirely transparent to the existing, already-complete A.2 realtime architecture (`EventPublisher` → Redis → `EventConsumer` → `EventBroadcaster` → SSE). If retry-attempt visibility is ever needed beyond Flower/logging (§18), it must be solved with additional application logging, not a new event bus surface.

---

## 17. Idempotency

**AliExpress product import/upsert:** verified safe to retry, and already tested. `ProductImporter.upsert_product()` (`app/services/product_importer.py`) looks up an existing row by `aliexpress_product_id`, then canonical `product_url`, then `affiliate_url`, before deciding create-vs-update (`_find_existing`, lines 53–74) — this is a genuine upsert with a well-defined dedup key, not an append-only insert. `tests/test_product_importer.py` already covers create, update-by-id, and `upsert_many` counting. Repeating a fetch (whether due to a client-level retry or a future beat tick) does not create duplicate `Product` rows. `refresh_categories`'s `AliExpressCategoryRepository.replace_all()` is a full replace, which is idempotent by construction (running it twice with the same fetched data produces the same end state).

**AI generation:** verified to have no persistence side effect to protect. `AIContentService.generate_marketing_content()` performs read-only product/URL lookups and returns generated text directly to the API caller — no repository write occurs anywhere in this call path. The frontend holds generated content in `sessionStorage` until the user explicitly creates a queue item from it (per `docs/06-api-integration.md` §4.5). A retry of a failed or even a successful generation call produces, at most, a second (possibly textually different, due to LLM sampling non-determinism) piece of generated text returned to the same request — never a duplicate database row, never a duplicate external side effect. Non-determinism across retries is an accepted, inherent property of LLM calls, not a defect to engineer around.

**Conclusion: neither integration requires a new idempotency mechanism.** This is a direct contrast with Telegram (A.1), where an idempotency guard was essential specifically because publishing produces an irreversible, user-visible external side effect (a sent message) with no natural dedup key. Nothing in either AliExpress or AI's retry surface has that property. No idempotency work is added by Phase C'.

---

## 18. Security / Cost / Latency Considerations

**AI retry latency:** with the §9 policy (max 2 attempts, 60s timeout per attempt, ~1–1.5s backoff), worst-case latency for a fully-exhausted retry is approximately `60s + ~1.5s + 60s ≈ 121.5s` — still a long wait for a synchronous request, which is precisely why 2 attempts (not 3) was chosen (§9) and why this document does not recommend raising it without also reconsidering whether AI generation should remain synchronous at all (explicitly out of scope, §8, §20).

**AI API cost multiplication:** every retry is a full billable provider call. At the chosen policy (≤2 attempts), worst-case cost multiplication is 2x per request, only in the (expected to be uncommon) case where the first attempt hits a transient failure. This is a deliberate, bounded trade-off — accepting occasional 2x cost on rare transient failures in exchange for fewer user-visible failures — and is a materially smaller multiplier than AliExpress's or Telegram's 4x (3-retry) budgets, chosen specifically because AI cost-per-call is higher.

**Provider rate limits:** retrying into an active rate limit without honoring `Retry-After` (§9, §10) risks worsening the very condition being retried against. Implementation must capture and honor the header/body-provided delay where available, particularly for OpenAI's documented 429 behavior, rather than always using calculated backoff.

**Request timeout implications:** both providers already set `httpx.AsyncClient(timeout=60.0)` per call — this is unchanged by retry work. The retry loop must apply this timeout **per attempt**, not as a shared budget across attempts, consistent with how AliExpress's and Telegram's existing retry loops already behave (each attempt gets its own full timeout).

**Avoiding unbounded retry loops:** the 2-attempt cap (§9) is a hard, non-configurable-by-accident ceiling for this phase — no environment variable should default to an unbounded or excessively high retry count for AI given the latency/cost analysis above. (AliExpress's `aliexpress_max_retries` env var precedent is fine to follow for AI's *own* new setting, since it is explicit and defaults conservatively — the point is the default and reasoning must be justified per-integration, not inherited from AliExpress's tuning.)

**Secret exposure, pre-existing and newly relevant:**
- `openai_provider.py`'s current `AIProviderError(f"OpenAI request failed: {detail}")` includes `exc.response.text` verbatim — a pre-existing risk that a verbose OpenAI error body could leak into a user-facing 502 message. Not introduced by this document, but directly relevant because implementation will already be editing this exact line for retry work — worth fixing in the same change as a low-cost bundled improvement (not mandated here; a recommendation, see §21 Task 4).
- Gemini's `key` query-parameter auth (§11) means any future retry-attempt log line must log the request **path**, not the full **URL**, or it will leak the API key into logs — a Gemini-specific risk with no OpenAI equivalent (OpenAI's key lives in a header, which is not logged by default `httpx` request-URL logging).
- Retry-attempt logging (recommended, not implemented, per this document) must log only: integration name, attempt number, status code / error classification, and backoff delay — never the request payload, response body, or full request URL.

**Flower exposure (Phase B, reused passively):** any Celery-level retry activity (should any ever be added per §5's narrow non-HTTP carve-out) would become visible in Flower the same way Telegram publishing tasks already are — already covered by Phase B's existing basic-auth + localhost-only binding; no new mitigation required since discovery tasks take no arguments and AI has no Celery task at all.

---

## 19. Test Strategy

Future tests only — **none implemented in this task.**

1. **AliExpress retry classification tests** — verify `_is_retryable()` correctly classifies each status code in `RETRYABLE_STATUS_CODES` as retryable and correctly rejects `AliExpressCredentialsError` and unclassified errors.
2. **AliExpress max retry enforcement** — verify `_execute_with_retries` makes exactly `aliexpress_max_retries + 1` attempts before raising, using a mock that always fails.
3. **AliExpress backoff tests** — verify `_backoff_seconds()` produces the expected exponential curve and that jitter falls within the documented `[0, 0.25)` range.
4. **AliExpress retry exhaustion** — verify the final raised exception, after budget exhaustion, is the correct type and carries the original error detail.
5. **AliExpress no-nested-retry regression test** — exercise a discovery task (e.g. `refresh_hot_products`) end-to-end with a mocked always-failing client and assert the total number of client-level attempts equals the client's own budget (4), not a multiple of it — this is the direct regression guard for §5's core finding and should be the first test written once any retry-related change touches this area, even before any Celery-level change is (deliberately not) made.
6. **OpenAI retryable error tests** — verify network failures, 429, and 5xx responses trigger the (to-be-implemented) retry loop.
7. **OpenAI non-retryable error tests** — verify 400/401/403/404 and malformed-response-shape errors raise immediately without retrying.
8. **Gemini retryable error tests** — same shape as #6, using Gemini's actual response format (verify against real or captured Gemini error bodies during implementation — not assumed identical to OpenAI's, per §11).
9. **Gemini non-retryable error tests** — same shape as #7, for Gemini's 400/403/404 cases specifically (403, not 401, for auth — see §11).
10. **AI retry exhaustion** — verify that after the chosen max-attempts budget (2) is exhausted, `AIProviderError` is raised with the same message shape as today.
11. **`POST /ai-content/generate` error-contract regression test** — verify the route's external error shape (`status_code`, `detail`) is unchanged after retry logic is added, using the existing `mock_ai_provider` fixture pattern in `tests/conftest.py` as a base, extended to simulate a transient-then-success or transient-exhausted scenario.
12. **Product importer idempotency verification** — largely already covered by `tests/test_product_importer.py`; verify (not necessarily add new tests) that this coverage remains valid and sufficient once any AliExpress-side changes land, since no new idempotency mechanism is planned (§17).

---

## 20. Phase C' Scope

### In scope

- AliExpress: exception-consistency hygiene (§6) and closing the pre-existing zero test coverage on already-implemented retry/backoff/classification logic (§7).
- AliExpress: an explicit, documented, and test-guarded rule that Celery must not duplicate client-level retry (§5).
- OpenAI: provider-layer retry implementation per the classification in §10 and the policy in §9.
- Gemini: provider-layer retry implementation per the classification in §11 and the policy in §9.
- Structured logging for retry attempts at the provider/client layer, since Flower cannot observe client-internal retries (§18).
- Documentation closeout updating `docs/08`/`docs/10`'s Phase C' rows once implementation lands (a later task, not this one).

### Out of scope

- **Telegram** — Phase A.1 is complete; nothing here touches `app/telegram/`, `TelegramPublishingService`, or Celery's publishing tasks.
- **Queue domain changes** — no `QueueItem`, `QueuePublishAttempt`, or queue API changes.
- **Celery retry for AliExpress HTTP errors already owned by the client** — explicitly ruled out (§5).
- **AI → Celery migration** — AI generation remains synchronous and request-bound (§8); no job queue, no polling endpoint, no async task dispatch.
- **Database retry tracking** — no new table, column, or migration (§13).
- **Dead-letter implementation** — no dead-letter concept exists or is proposed for AliExpress/AI; neither integration has Telegram's irreversible-external-action property that motivated it in A.1.
- **Realtime events** — no new `queue-events` payloads, no new SSE event types (§16).
- **Frontend changes** — the existing error-surfacing paths for both AliExpress (Discovery) and AI (AI Studio) already work end-to-end (§15).
- **A non-HTTP Celery retry layer for AliExpress persistence/infrastructure failures** — acknowledged as a theoretical future carve-out in §5, but **not designed, scoped, or committed to by this document** absent evidence it is actually needed.

---

## 21. Task Breakdown

```text
Task 0 — Architecture Decision
Status: COMPLETE (this document)

Task 1 — AliExpress Retry Test Coverage + Exception Hygiene
Status: COMPLETE
  - Discovery paths propagate app.aliexpress.exceptions.AliExpressAPIError
  - Client retry/backoff/classification covered by tests

Task 2 — AI Provider Retry Hardening (design Tasks 3–5 combined in execution)
Status: COMPLETE
  - Shared app/ai/retry.py + OpenAI/Gemini wiring
  - Max 2 attempts; Retry-After; malformed outside retry loop

Task 3 — AliExpress No-Nested-Retry Regression Protection (design Task 2)
Status: COMPLETE
  - Discovery Celery tasks have no AliExpress HTTP autoretry
  - Attempt counts equal client budget only

Task 4 — Integration/API Regression Validation (design Task 6 subset)
Status: COMPLETE
  - POST /ai-content/generate + discovery API contracts unchanged
  - No Celery in AI path

Task 5 — Documentation Closeout (design Task 7)
Status: COMPLETE
```

The original design preferred AliExpress hygiene/tests ahead of AI implementation; execution ultimately completed both tracks plus API regression and documentation closeout. Decisions C1–C7 remain binding.

---

## 22. Acceptance Criteria

Phase C' is complete when:

- [x] AliExpress client-level retry behavior remains bounded at `aliexpress_max_retries + 1` attempts — verified by test (§19.2), not merely by code inspection.
- [x] No nested retry amplification exists for AliExpress — no Celery-level `autoretry_for` was added for `AliExpressAPIError`/subclasses, verified by the regression test in §19.5.
- [x] AliExpress retryable/non-retryable classification (`_is_retryable`) is covered by tests (§19.1).
- [x] `ALIEXPRESS_MAX_RETRIES` (`aliexpress_max_retries`) enforcement is verified by test, not assumed from code reading alone.
- [x] The `AliExpressAPIError` naming/import inconsistency (§6) is resolved so all three discovery tasks propagate one canonical exception type.
- [x] OpenAI transient failures (network, 429, 5xx) retry within the chosen 2-attempt budget — verified by test (§19.6).
- [x] Gemini transient failures retry within the same 2-attempt budget — verified by test (§19.8).
- [x] Permanent errors (400/401/403/404, malformed response shape) never retry for either AliExpress or AI providers — verified by tests (§19.7, §19.9).
- [x] `Retry-After` behavior is implemented and tested (numeric header honored; capped at 60s; malformed/missing falls back to backoff).
- [x] Exhausted retries preserve the existing `AIProviderError` / `POST /ai-content/generate` error contract — verified by API regression tests.
- [x] No database migration was introduced (§13).
- [x] No new queue events or SSE changes were introduced (§16).
- [x] No frontend changes were made (§15).
- [x] No Telegram publishing reliability behavior was reimplemented (§20).
- [x] No Celery task was introduced for AI generation (§8).

---

## 23. Architecture Decisions

**Decision C1:** AliExpress HTTP retry remains owned by the AliExpress client (`app/aliexpress/api_client.py`). It is already fully implemented and correctly enforced; Phase C' adds no new retry mechanism at this layer.

**Decision C2:** Do NOT add Celery `autoretry_for` (or equivalent) for AliExpress HTTP exceptions already handled by the client (`AliExpressAPIError` and all its subclasses, under either import path — see Decision C2a). Doing so would nest a Celery-level retry loop on top of an already-exhausting client-level loop, producing up to a 4x outbound-call amplification (§5) with no correctness benefit, since AliExpress discovery has no duplicate-send risk analogous to Telegram's that would make such nesting safe.

**Decision C2a:** Any future exception-matching logic for AliExpress discovery tasks (Celery-level or otherwise) must use one canonical, resolved exception type per task — the `app.aliexpress.exceptions.AliExpressAPIError` / `app.services.exceptions.AliExpressAPIError` naming collision (§6) must be resolved as a prerequisite hygiene step (Task 1) before any such logic is written.

**Decision C3:** AI retry is owned by the provider/client implementations (`OpenAIProvider.generate_content`, `GeminiProvider.generate_content`), not Celery. No Celery task exists in the AI generation path today, and none is introduced by Phase C' — AI generation remains synchronous and request-bound inside `POST /ai-content/generate`.

**Decision C4:** AI retry budget is bounded and conservative: maximum 2 total attempts, exponential backoff from a 1.0s base with jitter, honoring provider-supplied `Retry-After` when available. This is deliberately smaller than AliExpress's or Telegram's 3-retry (4-attempt) budgets, chosen for AI's own latency (60s timeout per attempt) and cost (billable per call) profile — not copied from either existing implementation.

**Decision C5:** No database retry tracking. `QueuePublishAttempt` is schema-locked to Telegram (`CheckConstraint("provider = 'telegram'")`) and FK'd to a specific `queue_id`; it is not reusable for AliExpress or AI, and no new table is justified by any requirement identified in this analysis.

**Decision C6:** No new queue/SSE events. AliExpress and AI retry activity is backend/provider reliability work, entirely transparent to the existing, complete A.2 realtime architecture. Retry visibility is served by Phase B's Flower (for the narrow future case of a Celery-level non-HTTP retry) plus new application-level structured logging (for client-level retries, which Flower cannot see) — never a new event type.

**Decision C7:** No frontend work is required. `AIProviderError` already reaches `POST /ai-content/generate`'s caller with a stable error contract, and the frontend (`ContentWorkspaceView.tsx`) already renders it; Discovery's `ErrorState`/retry UI is likewise already complete. Both paths are backend-retry-transparent by construction (§8's synchronous design), so nothing in the frontend needs to change for Phase C' to ship.

---

## 24. Related Documents

- [08-implementation-roadmap.md](../08-implementation-roadmap.md) — Phase C' roadmap entry (current status: next milestone after Phase B)
- [10-production-readiness.md](../10-production-readiness.md) §9.3 — Error handling & retries table (AliExpress/AI rows currently ⬜; see §23 documentation-consistency notes carried over from the pre-Task-0 analysis)
- [planning/phase-b-worker-observability-design.md](./phase-b-worker-observability-design.md) — Phase B design + closeout (Flower/heartbeat infrastructure reused passively by this design, §18)
- [planning/phase-a2-realtime-operations-design.md](./phase-a2-realtime-operations-design.md) — Phase A.2 design (queue-events architecture explicitly NOT extended by this design, §16)
