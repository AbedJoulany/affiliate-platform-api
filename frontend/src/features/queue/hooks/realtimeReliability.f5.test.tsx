import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  renderHook,
  waitFor,
} from "@testing-library/react";
import { StrictMode, createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { WORKSPACE_A } from "@/test/workspace";
import { queueAttemptsKey, queueKey } from "../hooks/useQueue";
import { useQueueEventStream } from "../hooks/useQueueEventStream";
import { useQueueRealtimeInvalidation } from "../hooks/useQueueRealtimeInvalidation";
import {
  createDebouncedQueueEventInvalidator,
  getQueryKeysForQueueEvent,
} from "../lib/queue-event-invalidation";
import type { CreateQueueEventStreamOptions } from "../lib/sse-client";
import { QUEUE_EVENT_NAMES } from "../types/events";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

beforeEach(() => {
  setActiveWorkspaceId(WORKSPACE_A);
});

function wrapper(client: QueryClient, strict = false) {
  return function Wrapper({ children }: { children: ReactNode }) {
    const tree = createElement(QueryClientProvider, { client }, children);
    return strict ? createElement(StrictMode, null, tree) : tree;
  };
}

function envelope(
  event: string,
  queueId = "q-1",
): Parameters<NonNullable<CreateQueueEventStreamOptions["onMessage"]>>[0] {
  return {
    event,
    version: 1,
    id: `evt-${event}-${queueId}`,
    occurred_at: "2026-08-08T12:00:00.000Z",
    workspace_id: null,
    queue_id: queueId,
    data: { queue_id: queueId },
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  session.clear();
});

describe("F5 — single active stream lifecycle", () => {
  it("opens exactly one stream on mount and aborts it on unmount", async () => {
    session.setAccessToken("f5-token");
    const signals: AbortSignal[] = [];

    createStreamMock.mockImplementation(async (options) => {
      signals.push(options.signal);
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(() => useQueueEventStream(), {
      wrapper: wrapper(new QueryClient()),
    });

    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(1));
    expect(signals[0]?.aborted).toBe(false);

    unmount();
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
  });

  it("remount creates a clean stream and previous signal stays aborted", async () => {
    session.setAccessToken("f5-token");
    const signals: AbortSignal[] = [];

    createStreamMock.mockImplementation(async (options) => {
      signals.push(options.signal);
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(() => useQueueEventStream(), {
      wrapper: wrapper(new QueryClient()),
    });
    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(1));
    unmount();
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));

    const second = renderHook(() => useQueueEventStream(), {
      wrapper: wrapper(new QueryClient()),
    });
    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(2));
    expect(signals[0]?.aborted).toBe(true);
    expect(signals[1]?.aborted).toBe(false);
    second.unmount();
  });

  it("StrictMode mount/unmount/remount does not leave overlapping live streams", async () => {
    session.setAccessToken("f5-token");
    const live = new Set<AbortSignal>();

    createStreamMock.mockImplementation(async (options) => {
      live.add(options.signal);
      options.signal.addEventListener(
        "abort",
        () => {
          live.delete(options.signal);
        },
        { once: true },
      );
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(() => useQueueEventStream(), {
      wrapper: wrapper(new QueryClient(), true),
    });

    await waitFor(() => expect(live.size).toBe(1));
    // StrictMode may open more than once sequentially; never more than one live.
    expect(createStreamMock.mock.calls.length).toBeGreaterThanOrEqual(1);
    for (const call of createStreamMock.mock.calls) {
      const signal = call[0].signal;
      if (!live.has(signal)) {
        expect(signal.aborted).toBe(true);
      }
    }

    unmount();
    await waitFor(() => expect(live.size).toBe(0));
  });
});

describe("F5 — no stale event handling after unmount", () => {
  it("does not deliver events to onEvent after unmount", async () => {
    session.setAccessToken("f5-token");
    const onEvent = vi.fn();
    let captured: CreateQueueEventStreamOptions | null = null;

    createStreamMock.mockImplementation(async (options) => {
      captured = options;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(
      () => useQueueEventStream({ onEvent }),
      { wrapper: wrapper(new QueryClient()) },
    );

    await waitFor(() => expect(captured).not.toBeNull());
    unmount();
    await waitFor(() => expect(captured!.signal.aborted).toBe(true));

    captured!.onMessage?.(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("disposed invalidator ignores late handle calls", () => {
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 0);

    invalidator.dispose();
    invalidator.handle(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));
    invalidator.flush();

    expect(invalidateQueries).not.toHaveBeenCalled();
  });

  it("unmounted realtime hook does not invalidate on late SSE frames", async () => {
    session.setAccessToken("f5-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    let captured: CreateQueueEventStreamOptions | null = null;

    createStreamMock.mockImplementation(async (options) => {
      captured = options;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(captured).not.toBeNull());
    unmount();
    await waitFor(() => expect(captured!.signal.aborted).toBe(true));

    invalidateQueries.mockClear();
    captured!.onMessage?.(envelope(QUEUE_EVENT_NAMES.ATTEMPT_STARTED));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(invalidateQueries).not.toHaveBeenCalled();
  });
});

describe("F5 — invalidation deduplication", () => {
  it("debounces a burst of events into one invalidate per key", async () => {
    vi.useFakeTimers();
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const invalidator = createDebouncedQueueEventInvalidator(queryClient, 300);

    invalidator.handle(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));
    invalidator.handle(envelope(QUEUE_EVENT_NAMES.ATTEMPT_STARTED));
    invalidator.handle(envelope(QUEUE_EVENT_NAMES.ATTEMPT_SUCCEEDED));
    invalidator.handle(envelope(QUEUE_EVENT_NAMES.STATUS_CHANGED));

    expect(invalidateQueries).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300);

    expect(invalidateQueries).toHaveBeenCalledTimes(2);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey(WORKSPACE_A) });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: queueAttemptsKey(WORKSPACE_A, "q-1"),
    });

    invalidator.dispose();
    vi.useRealTimers();
  });

  it("maps attempt events to queue + attempts keys and ignores unknown events", () => {
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.ATTEMPT_FAILED)),
    ).toEqual([queueKey(WORKSPACE_A), queueAttemptsKey(WORKSPACE_A, "q-1")]);
    expect(
      getQueryKeysForQueueEvent(envelope(QUEUE_EVENT_NAMES.DELETED)),
    ).toEqual([queueKey(WORKSPACE_A)]);
    expect(
      getQueryKeysForQueueEvent(envelope("queue.unknown_event")),
    ).toEqual([]);
  });
});

describe("F5 — reconnect invalidation", () => {
  it("does not invalidate on first connect; invalidates after a real reconnect", async () => {
    session.setAccessToken("f5-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    let captured: CreateQueueEventStreamOptions | null = null;

    createStreamMock.mockImplementation(async (options) => {
      captured = options;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(invalidateQueries).not.toHaveBeenCalledWith({ queryKey: queueKey(WORKSPACE_A) });

    captured!.onReconnect?.(1, 5);
    await waitFor(() => expect(result.current.status).toBe("connecting"));
    captured!.onOpen?.();
    await waitFor(() => expect(result.current.status).toBe("connected"));
    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey(WORKSPACE_A) }),
    );

    unmount();
  });

  it("does not invalidate on repeated connection failures without reconnect success", async () => {
    session.setAccessToken("f5-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    let captured: CreateQueueEventStreamOptions | null = null;

    createStreamMock.mockImplementation(async (options) => {
      captured = options;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    invalidateQueries.mockClear();

    captured!.onError?.({
      kind: "network",
      message: "temporary",
      fatal: false,
    });
    await waitFor(() => expect(result.current.status).toBe("disconnected"));
    captured!.onReconnect?.(1, 5);
    await waitFor(() => expect(result.current.status).toBe("connecting"));
    captured!.onError?.({
      kind: "server",
      message: "503",
      status: 503,
      fatal: false,
    });
    await waitFor(() => expect(result.current.status).toBe("disconnected"));

    expect(invalidateQueries).not.toHaveBeenCalled();
    unmount();
  });

  it("StrictMode remount does not treat the first open as a reconnect refresh", async () => {
    session.setAccessToken("f5-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient, true) },
    );

    await waitFor(() =>
      expect(createStreamMock.mock.calls.length).toBeGreaterThanOrEqual(1),
    );
    // Allow status effects from StrictMode double-invoke to settle.
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(invalidateQueries).not.toHaveBeenCalledWith({ queryKey: queueKey(WORKSPACE_A) });
    unmount();
  });
});

describe("F5 — auth failure stops retrying", () => {
  it("marks fatal auth errors as error status without further reconnect UI loops", async () => {
    session.setAccessToken("f5-token");
    let captured: CreateQueueEventStreamOptions | null = null;

    createStreamMock.mockImplementation(async (options) => {
      captured = options;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(() => useQueueEventStream(), {
      wrapper: wrapper(new QueryClient()),
    });

    await waitFor(() => expect(result.current.status).toBe("connected"));
    captured!.onError?.({
      kind: "auth",
      message: "unauthorized",
      status: 401,
      fatal: true,
    });
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.status).not.toBe("connecting");
    unmount();
  });
});
