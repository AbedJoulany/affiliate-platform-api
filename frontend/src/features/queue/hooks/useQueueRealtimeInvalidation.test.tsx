import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { WORKSPACE_A } from "@/test/workspace";
import { queueKey } from "./useQueue";
import { useQueueRealtimeInvalidation } from "./useQueueRealtimeInvalidation";
import { QUEUE_EVENT_NAMES } from "../types/events";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

beforeEach(() => {
  setActiveWorkspaceId(WORKSPACE_A);
});

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  session.clear();
});

describe("useQueueRealtimeInvalidation", () => {
  it("opens one SSE connection and invalidates queue queries on events", async () => {
    session.setAccessToken("realtime-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      options.onMessage?.({
        event: QUEUE_EVENT_NAMES.STATUS_CHANGED,
        version: 1,
        id: "evt-1",
        occurred_at: "2026-08-08T10:00:00.000Z",
        workspace_id: null,
        queue_id: "q-1",
        data: {
          queue_id: "q-1",
          status: "published",
          previous_status: "queued",
          scheduled_at: null,
          published_at: "2026-08-08T10:00:00.000Z",
        },
      });
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), {
          once: true,
        });
      });
    });

    const { result, unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.status).toBe("connected"));
    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey(WORKSPACE_A) }),
    );

    unmount();
    await waitFor(() =>
      expect(createStreamMock.mock.calls[0][0].signal.aborted).toBe(true),
    );
  });

  it("ignores unknown events without invalidating", async () => {
    session.setAccessToken("realtime-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      options.onMessage?.({
        event: "queue.not_real",
        version: 1,
        id: "evt-x",
        occurred_at: "2026-08-08T10:00:00.000Z",
        workspace_id: null,
        queue_id: "q-1",
        data: {},
      });
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), {
          once: true,
        });
      });
    });

    const { unmount } = renderHook(
      () => useQueueRealtimeInvalidation({ debounceMs: 0 }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(invalidateQueries).not.toHaveBeenCalled());
    // Allow a macrotask for debounceMs: 0
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(invalidateQueries).not.toHaveBeenCalled();
    unmount();
  });
});
