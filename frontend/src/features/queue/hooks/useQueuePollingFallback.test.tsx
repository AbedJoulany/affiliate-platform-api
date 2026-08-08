import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { QueueRealtimePollingContext } from "../hooks/QueueRealtimePollingContext";
import { queueKey, useQueue } from "../hooks/useQueue";
import { useQueueRealtimeInvalidation } from "../hooks/useQueueRealtimeInvalidation";
import type { CreateQueueEventStreamOptions } from "../lib/sse-client";
import {
  QUEUE_POLL_FALLBACK_MIN_MS,
  createQueuePollIntervalSelector,
} from "../lib/queue-polling";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

vi.mock("../api/queue.api", () => ({
  getQueue: vi.fn(async () => ({ items: [], total: 0, skip: 0, limit: 200 })),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

function wrapper(client: QueryClient, pollingEnabled = false) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client },
      createElement(
        QueueRealtimePollingContext.Provider,
        { value: pollingEnabled },
        children,
      ),
    );
  };
}

function realtimeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  session.clear();
});

describe("SSE → polling fallback", () => {
  it("Test A — connected disables polling", async () => {
    session.setAccessToken("poll-token");
    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: realtimeWrapper(new QueryClient()) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(result.current.pollingEnabled).toBe(false);
    unmount();
  });

  it("Test B — disconnected enables polling at the 5s floor", async () => {
    session.setAccessToken("poll-token");
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
      { wrapper: realtimeWrapper(new QueryClient()) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    captured!.onError?.({
      kind: "network",
      message: "stream closed",
      fatal: false,
    });
    await waitFor(() => expect(result.current.status).toBe("disconnected"));
    expect(result.current.pollingEnabled).toBe(true);
    expect(createQueuePollIntervalSelector()({
      state: {
        data: undefined,
        dataUpdateCount: 0,
        fetchStatus: "idle",
      },
    } as never)).toBe(QUEUE_POLL_FALLBACK_MIN_MS);
    unmount();
  });

  it("Test C — reconnect disables polling and refreshes once", async () => {
    session.setAccessToken("poll-token");
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
      { wrapper: realtimeWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(result.current.pollingEnabled).toBe(false);
    expect(invalidateQueries).not.toHaveBeenCalledWith({ queryKey: queueKey });

    captured!.onError?.({
      kind: "network",
      message: "stream closed",
      fatal: false,
    });
    await waitFor(() => expect(result.current.status).toBe("disconnected"));
    expect(result.current.pollingEnabled).toBe(true);

    captured!.onReconnect?.(1, 10);
    await waitFor(() => expect(result.current.status).toBe("connecting"));
    expect(result.current.pollingEnabled).toBe(true);

    invalidateQueries.mockClear();
    captured!.onOpen?.();
    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(result.current.pollingEnabled).toBe(false);
    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey }),
    );
    expect(invalidateQueries).toHaveBeenCalledTimes(1);
    unmount();
  });

  it("Test D — initial connection does not trigger reconnect refresh", async () => {
    session.setAccessToken("poll-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: realtimeWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(result.current.pollingEnabled).toBe(false);
    expect(invalidateQueries).not.toHaveBeenCalledWith({ queryKey: queueKey });
    unmount();
  });

  it("Test E — unmount cleans up stream and disables polling", async () => {
    session.setAccessToken("poll-token");
    const signals: AbortSignal[] = [];
    createStreamMock.mockImplementation(async (options) => {
      signals.push(options.signal);
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: realtimeWrapper(new QueryClient()) },
    );

    await waitFor(() => expect(result.current.status).toBe("connected"));
    unmount();
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
  });

  it("Test F — useQueue enables a single refetchInterval only while polling is on", async () => {
    const clientOff = new QueryClient();
    const off = renderHook(() => useQueue(undefined, 200), {
      wrapper: wrapper(clientOff, false),
    });
    await waitFor(() => expect(off.result.current.isSuccess).toBe(true));
    const offObserver = clientOff
      .getQueryCache()
      .find({ queryKey: [...queueKey, undefined, 200, 0] })
      ?.observers[0];
    expect(offObserver?.options.refetchInterval).toBe(false);
    off.unmount();

    const clientOn = new QueryClient();
    const on = renderHook(() => useQueue(undefined, 200), {
      wrapper: wrapper(clientOn, true),
    });
    await waitFor(() => expect(on.result.current.isSuccess).toBe(true));
    const onQuery = clientOn
      .getQueryCache()
      .find({ queryKey: [...queueKey, undefined, 200, 0] });
    const onObserver = onQuery?.observers[0];
    expect(typeof onObserver?.options.refetchInterval).toBe("function");
    expect(
      (onObserver?.options.refetchInterval as (q: never) => number | false)({
        state: { data: undefined, dataUpdateCount: 0, fetchStatus: "idle" },
      } as never),
    ).toBe(QUEUE_POLL_FALLBACK_MIN_MS);

    // One observer / one interval selector for the queue query — no storm.
    expect(onQuery?.getObserversCount()).toBe(1);
    on.unmount();
  });

  it("does not enable polling during the initial connecting phase", async () => {
    session.setAccessToken("poll-token");
    createStreamMock.mockImplementation(async (options) => {
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: realtimeWrapper(new QueryClient()) },
    );

    await waitFor(() => expect(result.current.status).toBe("connecting"));
    expect(result.current.pollingEnabled).toBe(false);
    unmount();
  });
});
