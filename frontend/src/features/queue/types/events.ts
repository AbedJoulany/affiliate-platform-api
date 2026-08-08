import type { QueueStatus } from "./api";

/** Canonical Phase A.2 queue realtime event names (match backend). */
export const QUEUE_EVENT_NAMES = {
  STATUS_CHANGED: "queue.status_changed",
  DELETED: "queue.deleted",
  ATTEMPT_STARTED: "queue.attempt_started",
  ATTEMPT_SUCCEEDED: "queue.attempt_succeeded",
  ATTEMPT_FAILED: "queue.attempt_failed",
} as const;

export type QueueEventName =
  (typeof QUEUE_EVENT_NAMES)[keyof typeof QUEUE_EVENT_NAMES];

export const QUEUE_EVENT_ENVELOPE_VERSION = 1;

/** Shared versioned envelope fields for every queue realtime event. */
export interface QueueEventEnvelopeBase {
  event: string;
  version: number;
  /** Stream cursor (ULID) — also sent as SSE `id:`. */
  id: string;
  occurred_at: string;
  /** Reserved for future multi-tenancy; always null today. */
  workspace_id: string | null;
  queue_id: string;
  data: Record<string, unknown>;
}

export interface QueueStatusChangedData {
  queue_id: string;
  status: QueueStatus;
  previous_status: QueueStatus;
  scheduled_at: string | null;
  published_at: string | null;
}

export interface QueueDeletedData {
  queue_id: string;
}

export interface QueueAttemptStartedData {
  queue_id: string;
  attempt_number: number;
  provider: string;
}

export interface QueueAttemptSucceededData {
  queue_id: string;
  attempt_number: number;
  provider_message_id: number;
}

export interface QueueAttemptFailedData {
  queue_id: string;
  attempt_number: number;
  error_code: string;
  is_terminal: boolean;
}

export interface QueueStatusChangedEvent extends Omit<
  QueueEventEnvelopeBase,
  "event" | "data"
> {
  event: typeof QUEUE_EVENT_NAMES.STATUS_CHANGED;
  data: QueueStatusChangedData;
}

export interface QueueDeletedEvent extends Omit<
  QueueEventEnvelopeBase,
  "event" | "data"
> {
  event: typeof QUEUE_EVENT_NAMES.DELETED;
  data: QueueDeletedData;
}

export interface QueueAttemptStartedEvent extends Omit<
  QueueEventEnvelopeBase,
  "event" | "data"
> {
  event: typeof QUEUE_EVENT_NAMES.ATTEMPT_STARTED;
  data: QueueAttemptStartedData;
}

export interface QueueAttemptSucceededEvent extends Omit<
  QueueEventEnvelopeBase,
  "event" | "data"
> {
  event: typeof QUEUE_EVENT_NAMES.ATTEMPT_SUCCEEDED;
  data: QueueAttemptSucceededData;
}

export interface QueueAttemptFailedEvent extends Omit<
  QueueEventEnvelopeBase,
  "event" | "data"
> {
  event: typeof QUEUE_EVENT_NAMES.ATTEMPT_FAILED;
  data: QueueAttemptFailedData;
}

export type QueueTypedRealtimeEvent =
  | QueueStatusChangedEvent
  | QueueDeletedEvent
  | QueueAttemptStartedEvent
  | QueueAttemptSucceededEvent
  | QueueAttemptFailedEvent;

/**
 * Wire-level envelope. Prefer narrowing via `event` when handling known types;
 * unknown future event names remain valid as the base shape.
 */
export type QueueEventEnvelope = QueueTypedRealtimeEvent | QueueEventEnvelopeBase;

export function isQueueEventName(value: string): value is QueueEventName {
  return (Object.values(QUEUE_EVENT_NAMES) as string[]).includes(value);
}
