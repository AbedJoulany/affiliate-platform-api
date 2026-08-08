import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { queueAttemptsKey, queueKey } from "../hooks/useQueue";
import { QUEUE_EVENT_NAMES, type QueueEventEnvelope } from "../types/events";
import {
  QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS,
  createDebouncedQueueEventInvalidator,
  getQueryKeysForQueueEvent,
} from "./queue-event-invalidation";

const QUEUE_ID = "11111111-1111-1111-1111-111111111111";

function envelope(
  event: string,
  overrides: Partial<QueueEventEnvelope> = {},
): QueueEventEnvelope {
  return {
    event,
    version: 1,
    id: `evt-${event}`,
    occurred_at: "2026-08-08T10:00:00.000Z",
    workspace_id: null,
    queue_id: QUEUE_ID,
    data: { queue_id: QUEUE_ID },
    ...overrides,
  } as QueueEventEnvelope;
}

describe("getQueryKeysForQueueEvent", () => {
  it("invalidates the queue list for status_changed", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED)),
    ).toEqual([queueKey]);
  });

  it("invalidates the queue list for deleted", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.DELETED)),
    ).toEqual([queueKey]);
  });

  it("invalidates queue list + attempts for attempt_started", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.ATTEMPT_STARTED)),
    ).toEqual([queueKey, queueAttemptsKey(QUEUE_ID)]);
  });

  it("invalidates queue list + attempts for attempt_succeeded", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.ATTEMPT_SUCCEEDED)),
    ).toEqual([queueKey, queueAttemptsKey(QUEUE_ID)]);
  });

  it("invalidates queue list + attempts for attempt_failed", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.ATTEMPT_FAILED)),
    ).toEqual([queueKey, queueAttemptsKey(QUEUE_ID)]);
  });

  it("returns no keys for unknown events", () => {
    expect(getQueryKeysForQueueEvent(envelope("queue.unknown_event"))).toEqual(
      [],
    );
  });

  it("returns no keys for malformed envelopes", () => {
    expect(
      getQueryKeysForQueueEvent({} as QueueEventEnvelope),
    ).toEqual([]);
  });
});

describe("createDebouncedQueueEventInvalidator", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces invalidateQueries for known events", async () => {
    vi.useFakeTimers();
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 300);

    invalidator.handle(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));
    invalidator.handle(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));
    expect(invalidateQueries).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS);

    expect(invalidateQueries).toHaveBeenCalledTimes(1);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey });
    invalidator.dispose();
  });

  it("invalidates attempts key for attempt events after debounce", async () => {
    vi.useFakeTimers();
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 300);

    invalidator.handle(envelope(QUEUE_EVENT_NAMES.ATTEMPT_FAILED));
    await vi.advanceTimersByTimeAsync(300);

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: queueAttemptsKey(QUEUE_ID),
    });
    invalidator.dispose();
  });

  it("does not invalidate for unknown events", async () => {
    vi.useFakeTimers();
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 300);

    invalidator.handle(envelope("not.a.queue.event"));
    await vi.advanceTimersByTimeAsync(300);

    expect(invalidateQueries).not.toHaveBeenCalled();
    invalidator.dispose();
  });

  it("swallows handler errors without throwing", () => {
    const queryClient = new QueryClient();
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 0);
    expect(() =>
      invalidator.handle(null as unknown as QueueEventEnvelope),
    ).not.toThrow();
    invalidator.dispose();
  });
});
