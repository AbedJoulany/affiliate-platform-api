import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { queueAttemptsKey, queueKey } from "../hooks/useQueue";
import {
  QUEUE_EVENT_NAMES,
  isQueueEventName,
  type QueueEventEnvelope,
} from "../types/events";

/** Coalesce burst publish events into one refetch per affected key. */
export const QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS = 300;

/**
 * Map a realtime queue event to TanStack Query keys that must refetch.
 * Unknown event names return an empty list (no invalidation).
 */
export function getQueryKeysForQueueEvent(
  event: QueueEventEnvelope,
): QueryKey[] {
  if (!event || typeof event.event !== "string") return [];
  if (!isQueueEventName(event.event)) return [];

  const keys: QueryKey[] = [queueKey];

  switch (event.event) {
    case QUEUE_EVENT_NAMES.ATTEMPT_STARTED:
    case QUEUE_EVENT_NAMES.ATTEMPT_SUCCEEDED:
    case QUEUE_EVENT_NAMES.ATTEMPT_FAILED: {
      const queueId = normalizeQueueId(event.queue_id);
      if (queueId) keys.push(queueAttemptsKey(queueId));
      break;
    }
    case QUEUE_EVENT_NAMES.STATUS_CHANGED:
    case QUEUE_EVENT_NAMES.DELETED:
      break;
  }

  return keys;
}

export type QueueEventInvalidator = {
  handle: (event: QueueEventEnvelope) => void;
  flush: () => void;
  dispose: () => void;
};

/**
 * Debounced invalidation against the shared QueryClient.
 * Never mutates cache entries — server state remains authoritative.
 */
export function createDebouncedQueueEventInvalidator(
  queryClient: QueryClient,
  debounceMs: number = QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS,
): QueueEventInvalidator {
  const pending = new Map<string, QueryKey>();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  const flush = () => {
    if (disposed) return;
    timer = null;
    const keys = Array.from(pending.values());
    pending.clear();
    for (const key of keys) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  };

  return {
    handle(event: QueueEventEnvelope) {
      if (disposed) return;
      try {
        const keys = getQueryKeysForQueueEvent(event);
        if (keys.length === 0) return;
        for (const key of keys) {
          pending.set(JSON.stringify(key), key);
        }
        if (debounceMs <= 0) {
          flush();
          return;
        }
        if (timer) clearTimeout(timer);
        timer = setTimeout(flush, debounceMs);
      } catch {
        // Malformed envelopes must not crash the SSE consumer.
      }
    },
    flush,
    dispose() {
      disposed = true;
      if (timer) clearTimeout(timer);
      timer = null;
      pending.clear();
    },
  };
}

function normalizeQueueId(value: unknown): string | null {
  if (typeof value === "string" && value.length > 0) return value;
  if (value == null) return null;
  const asString = String(value);
  return asString.length > 0 ? asString : null;
}
