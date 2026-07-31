# QueuePublishAttempt Design

**Scope:** Phase A.1, Backend Task 1 only  
**Provider:** Telegram only  
**Authority:** `docs/08-implementation-roadmap.md` §3

## Purpose and boundaries

`QueuePublishAttempt` is the durable record of a guard-authorized Telegram send try for an existing queue item. A row is created before the try can contact Telegram and is then finalized with its outcome. A retry that reaches the provider is a new attempt and receives a new attempt number; an invocation rejected by the idempotency or concurrency guard does not create a fictitious attempt.

The entity is additive. It does not change `queue_items`, existing queue endpoints, or existing response schemas. It follows the repository's `UUIDPrimaryKeyMixin` and `TimestampMixin` conventions.

The current `QueueStatus` remains exactly `draft`, `queued`, `scheduled`, and `published`. Attempt `status` is a separate, attempt-scoped value; `failed` describes one send try and is never a queue item status because a queue item may remain queued or scheduled and later succeed.

## Current publishing facts that shape the design

- `TelegramPublishingService.publish_queue_item` currently validates the queue item and channel, resolves the effective Telegram payload, calls `TelegramPublisher.publish`, and only then stores the queue item's published state and Telegram message ID.
- `_publish_items` currently discards `ValidationError`, `ForbiddenError`, and `ConflictError` with `continue`, leaving no structured fact for those failures.
- `TelegramPublisher` chooses `sendPhoto` when an image is resolved and `sendMessage` otherwise. A successful result contains `chat_id`, `message_id`, and `message_type`.
- `TelegramPublishError` currently contains only a message and HTTP-like service status. Telegram error codes and `retry_after` are not preserved.
- The API dependency commits at the end of a request, while each Celery publishing entry point commits only after its service work finishes. That is insufficient for a durable pre-call `started` record and must be addressed by later instrumentation.
- The scheduled worker selects eligible items without a claim or row lock, so a scheduled run, another worker, and a manual publish can currently race.

## Entity definition

The persistence name should be `queue_publish_attempts`.

### `id`

- Type: UUID.
- Nullability: non-null.
- Default: application-generated UUID v4.
- Purpose: primary key, supplied by `UUIDPrimaryKeyMixin`.

### `queue_id`

- Type: UUID.
- Nullability: non-null.
- Default: none.
- Purpose: identifies the owning `QueueItem`.
- Constraint: foreign key to `queue_items.id` with `ON DELETE CASCADE`.

Cascade deletion preserves the existing hard-delete behavior of `DELETE /queues/{id}` and prevents orphan attempts. The audit history is therefore durable for the lifetime of its queue item, not after that item is deliberately deleted.

### `attempt_number`

- Type: integer.
- Nullability: non-null.
- Default: none; allocated atomically while the queue item is locked.
- Purpose: one-based, monotonically increasing sequence for all Telegram send tries belonging to a queue item.
- Constraints: greater than zero and unique with `queue_id`.

Numbering is per queue item rather than per Celery task or HTTP request. Provider-level retries and Celery retries that actually start another send try consume the next number.

### `provider`

- Type: variable-length string, maximum 32 characters.
- Nullability: non-null.
- Default: `telegram`.
- Purpose: identifies the publishing provider without creating generic provider infrastructure.
- Constraint: only `telegram` is valid in this milestone.

### `status`

- Type: variable-length string, maximum 16 characters, constrained independently from `QueueStatus`.
- Nullability: non-null.
- Default: `started`.
- Allowed values: `started`, `succeeded`, `failed`.
- Purpose: records the lifecycle and outcome of this attempt only.

The only valid transition is from `started` to one terminal value. Terminal attempts are immutable except for corrections performed through an explicit administrative data-repair process outside Phase A.1.

### `content_hash`

- Type: fixed-length 64-character lowercase hexadecimal string.
- Nullability: non-null.
- Default: none; calculated before the claim is inserted.
- Purpose: stores the SHA-256 fingerprint used with `queue_id` for idempotency decisions.

The hash input is a canonical UTF-8 representation of the effective outbound payload: provider, Telegram method/message type, resolved Telegram chat ID, text, resolved image URL or null, resolved button text and URL or null, and parse mode or null. Keys are sorted, strings are not trimmed or case-folded, and absent optional values are represented consistently as null. Queue title, queue status, scheduling timestamps, and database timestamps are excluded because Telegram does not receive them.

Hashing resolved values is important because image and button values may fall back to the related product, and the destination comes from the related channel. A change to any provider-visible value therefore creates a different fingerprint even when `QueueItem.content` itself is unchanged.

### `idempotency_expires_at`

- Type: timezone-aware timestamp.
- Nullability: non-null.
- Default: none; set from the same clock as `occurred_at` to exactly 24 hours after attempt start.
- Purpose: makes the bounded guard lifetime explicit and stable even if a later configuration changes.

This timestamp does not expire or delete the audit row. It only bounds how long a `started` or `succeeded` attempt can suppress another send of the same key.

### `error_code`

- Type: variable-length string, maximum 128 characters.
- Nullability: nullable.
- Default: null.
- Purpose: stable, machine-queryable failure category. It should preserve a Telegram API error code when one exists and otherwise use a backend category such as `validation_error`, `transport_error`, `ambiguous_outcome`, or `unexpected_error`.

The value is required when status is `failed` and absent for `started` and `succeeded`.

### `error_message`

- Type: text.
- Nullability: nullable.
- Default: null.
- Purpose: human-readable diagnostic detail suitable for operators. Secrets, bot tokens, and full request payloads must not be stored.

The value is required when status is `failed` and absent for `started` and `succeeded`.

### `provider_chat_id`

- Type: variable-length string, maximum 64 characters.
- Nullability: nullable.
- Default: null.
- Purpose: records the Telegram `chat_id` returned for this specific successful attempt. It is stored as a string to match the current `TelegramPublishResult` contract and avoid imposing a numeric representation on provider identity.

The value is required when status is `succeeded` and absent otherwise.

### `provider_message_id`

- Type: big integer.
- Nullability: nullable.
- Default: null.
- Purpose: records the Telegram `message_id` returned for this specific successful attempt.

The value is required when status is `succeeded` and absent otherwise. Telegram message IDs are scoped to a chat, so `(provider_chat_id, provider_message_id)` is the provider identity of the published message; `provider_message_id` alone is not globally identifying. Both values belong on the attempt because `QueueItem.telegram_message_id` represents only current queue state and can be cleared or overwritten, while the related channel can change or be deleted.

### `occurred_at`

- Type: timezone-aware timestamp.
- Nullability: non-null.
- Default: database current time.
- Purpose: immutable time at which the attempt entered `started`; this is the event time used for ordering, daily KPI queries, and the future Phase A.2 event contract.

### `created_at`

- Type: timezone-aware timestamp.
- Nullability: non-null.
- Default: database current time.
- Purpose: records persistence time and follows `TimestampMixin`. It will normally be equal or very close to `occurred_at`, but it has a distinct persistence-audit meaning.

### `updated_at`

- Type: timezone-aware timestamp.
- Nullability: non-null.
- Default: database current time, updated when the row changes.
- Purpose: follows `TimestampMixin` and records when `started` was finalized as `succeeded` or `failed`.

## Constraints and indexes

The future database change should enforce these invariants:

- Primary key on `id`.
- Foreign key from `queue_id` to `queue_items.id` with cascade deletion.
- Unique constraint on `(queue_id, attempt_number)`.
- Positive check on `attempt_number`.
- Provider check allowing only `telegram`.
- Attempt-status check allowing only `started`, `succeeded`, and `failed`.
- Outcome consistency: a failed row has both error fields; a succeeded row has both provider identity fields; started rows have no outcome fields; successful rows have no error fields.
- No unique constraint on `(queue_id, content_hash)`: multiple failed tries and a later success intentionally share that logical key. Blocking is determined from status and `idempotency_expires_at` while the queue row is locked, not from permanent database uniqueness.

Query support should include:

- A unique B-tree index on `(queue_id, attempt_number)`. Its queue prefix supports listing attempts, and scanning the highest attempt number supports “latest attempt for a queue item.”
- A B-tree index on `(queue_id, content_hash, status, idempotency_expires_at)` for guard lookups over attempts sharing an idempotency key and testing whether a blocking state is still active.
- A B-tree index on `(provider, status, occurred_at)` for backend-owned failure counts such as “failed today.”

Attempt lists should use `attempt_number` descending with `id` as a deterministic tie-breaker. The unique constraint makes ties impossible under normal operation.

## Relationship to QueueItem

`QueueItem` has a one-to-many relationship with `QueuePublishAttempt`; each attempt belongs to exactly one queue item. The relationship is historical and must not drive `QueueItem.status`. A failed terminal attempt leaves the queue status unchanged, while a successful attempt may accompany the existing queue transition to `published` in later service instrumentation.

Cascade deletion is chosen because queue deletion is an existing supported operation and this task must not make it fail. If audit retention after queue deletion becomes a product or compliance requirement, hard deletion itself will need a separate retention design; nullable ownership or silent orphaning is not introduced here.

This makes the table an operational audit history, durable across retries, processes, and browser sessions but retained only for the owning queue item's lifetime. `ON DELETE RESTRICT` would silently change the existing delete endpoint into a failure after the first attempt, while `ON DELETE SET NULL` would require a nullable `queue_id` and break the required ownership and per-queue query contract. Under Phase A.1's additive and backward-compatibility constraints, cascade is therefore the deliberate policy rather than an accidental default.

## Idempotency decisions

### 1. Key definition

**Decision:** use `(queue_id, content_hash)`, where `content_hash` fingerprints the effective Telegram payload described above.

**Rationale:** `queue_id` alone would suppress a legitimate publish after any provider-visible edit. Including the effective payload keeps unchanged retries deduplicated while allowing edits, channel changes, and resolved product fallback changes to produce a fresh key.

This is a logical lookup key, not a uniqueness constraint. The guard queries attempts matching both values and applies status and expiry rules: an unexpired `started` or `succeeded` row blocks, a `failed` row does not, and an expired row does not. The migration therefore needs the `content_hash` and `idempotency_expires_at` columns plus the guard lookup index, but must allow repeated rows with the same key.

### 2. Ambiguous-failure handling

**Decision:** commit a `started` attempt before the Telegram call. An unexpired `started` row for the same key suppresses automatic and manual resend because the prior call may have succeeded. When its 24-hour guard window expires, later recovery may finalize it as `failed` with `ambiguous_outcome` before allowing a new attempt.

**Rationale:** Telegram provides neither a client idempotency key nor a reliable lookup that proves whether a timed-out send was accepted. The durable pre-call marker closes the crash gap and favors avoiding duplicate channel posts during the bounded ambiguity window. A retry after expiration still carries a documented residual duplicate risk if Telegram accepted the original call; the provider API cannot eliminate that risk.

### 3. Concurrency guard

**Decision:** use a database row lock on the owning `queue_items` row for a short claim transaction. While holding the lock, re-read the effective payload, calculate its hash, inspect blocking attempts, allocate the next attempt number, insert `started`, and commit. Release the lock before network I/O.

**Rationale:** every publishing path already has a `queue_id`, and row locking serializes manual, scheduled, and Celery retry claim decisions without holding a database lock across a 30-second network timeout. The unique attempt-number constraint is a final integrity backstop. A separate in-memory or Redis-only claim would not be authoritative across processes and could diverge from attempt history.

### 4. Key lifetime

**Decision:** a `started` or `succeeded` attempt blocks the same key for 24 hours from `occurred_at`; a definitively `failed` attempt does not block the next retry. Attempt rows themselves are retained until their queue item is deleted.

**Rationale:** 24 hours covers immediate provider and Celery retry storms and manual double-submission while remaining bounded for controlled replay and testing. Treating failed attempts as blockers would defeat the required retry policy, while indefinite successful keys would prevent intentional replay of unchanged content forever.

The behavior is identical for every trigger:

- Automatic provider or Celery retry after a definitive `failed` attempt may claim the next attempt immediately.
- Manual retry after a definitive `failed` attempt may also claim the next attempt immediately.
- Automatic retry and manual retry are both suppressed by an unexpired `started` attempt with the same key.
- Automatic retry and manual retry are both suppressed by an unexpired `succeeded` attempt with the same key.
- Manual invocation has no force-bypass. To publish changed content, the changed effective payload produces a new hash; to replay identical content, the caller must wait until expiry.

### 5. Manual versus automatic retry

**Decision:** manual publish, scheduled publishing, provider retry, and automatic Celery retry must all enter through the same database-backed claim guard and use the same key and lifetime rules. No trigger may bypass it.

**Rationale:** the current manual endpoint and worker paths converge on `TelegramPublishingService`; preserving one claim boundary is the only way to prevent a user action racing a scheduled or retried task.

### 6. Content changed during retries

**Decision:** re-resolve the outbound payload and recompute the hash inside the locked claim transaction for every retry. A changed hash is a fresh key and may start immediately, even when the old key has an unexpired attempt.

**Rationale:** operators must be able to correct content or destination data and publish the correction. Computing from the latest resolved payload under the same lock prevents a retry from claiming one version and sending another. The attempt retains its original hash so history remains attributable to the payload identity that was actually claimed.

## Expected later service lifecycle

This section defines the entity contract only; it does not prescribe repository or task implementation details.

1. A publish trigger identifies an existing queue item and enters the shared claim boundary.
2. The claim transaction locks the queue item, resolves a stable outbound snapshot, computes the hash, applies the guard, allocates `attempt_number`, inserts `started`, and commits before any Telegram request.
3. The send try uses exactly the snapshot that was hashed. It must not re-read mutable queue, product, or channel values after the claim.
4. A Telegram result finalizes the attempt as `succeeded` with `provider_chat_id` and `provider_message_id`; the queue item's existing published fields are updated consistently with that success.
5. A validation, permission, transport, Telegram API, or unexpected error finalizes the attempt as `failed` with structured error detail before the error is returned or made eligible for retry.
6. A process loss after the pre-call commit leaves `started`, which is intentionally detectable by the next guarded invocation.
7. Each subsequent send try repeats the process and creates a new numbered row. Suppressed invocations return or raise an idempotency/concurrency outcome without claiming that Telegram was contacted.

Local failures for an existing queue item should be recorded once a send try has been claimed, including the validation and permission failures currently discarded by `_publish_items`. A request for a nonexistent queue ID cannot produce an attempt because there is no valid foreign-key owner; it remains a normal not-found request failure.

## Assumptions

- PostgreSQL remains the database, so UUIDs, timezone-aware timestamps, row-level locks, and B-tree indexes follow existing conventions.
- A 24-hour guard window is acceptable operationally; no different duration is specified in the authoritative roadmap.
- Queue hard deletion is intentional existing behavior, so preserving endpoint compatibility takes priority over retaining attempts after deletion.
- The effective outbound snapshot can be resolved before the network call and reused unchanged for that call.
- `provider_chat_id` and `provider_message_id` are always present in a successful `TelegramPublishResult`, as the current publisher contract requires.
- Timestamps use UTC throughout, matching current publishing service behavior.

## Open questions for later tasks

These do not change the entity or the six decisions above:

- Later implementation must choose how to expose a guard-suppressed invocation through the existing publish response without changing contracts prematurely.
- Later retry work must preserve one attempt row per actual send try even if retry control is placed inside `TelegramPublisher`; otherwise provider-level retries would be invisible.
- A future product requirement may call for audit retention after queue deletion. That would require reconsidering hard-delete semantics as a separate change.

## Risks for downstream implementation

- Current request and Celery transaction boundaries cannot make `started` durable before the provider call. Reusing the existing single transaction would allow a crash or rollback to erase the marker.
- The batch worker commits scheduled and queued processing together. One uncaught Telegram or unexpected error can abort the batch and roll back other pending changes.
- `_publish_items` catches only three service-error types. Telegram transport/API errors and unexpected errors can abort iteration, while the caught validation, permission, and conflict errors are silently discarded.
- `TelegramPublishError` does not retain Telegram numeric error codes, HTTP status, `retry_after`, or a retryable/non-retryable classification. Stable `error_code` population and the required 429 policy will need richer error propagation.
- `TelegramPublisher._post` assumes a JSON response and catches only `httpx.HTTPError`; malformed responses can escape as unclassified exceptions.
- Telegram has no native idempotency key or reliable sent-message lookup. The 24-hour ambiguous marker reduces duplicates but cannot prove the outcome of a timed-out accepted request.
- Resolved payload data can come from mutable channel and product relations. The later claim flow must lock or otherwise validate the resolved snapshot so the hash and sent payload cannot diverge.
- Cascade deletion means operational history is removed with a queue item. This is compatible with current deletion behavior but limits long-term audit retention.
