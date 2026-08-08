import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { queueKey } from "../hooks/useQueue";
import { useQueueRealtimeInvalidation } from "../hooks/useQueueRealtimeInvalidation";
import type { CreateQueueEventStreamOptions } from "../lib/sse-client";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

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

describe("F4 — reconnect recovery refresh", () => {
  it("invalidates queue queries after reconnect, not on first connect", async () => {
    session.setAccessToken("f4-token");
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const captured: { options: CreateQueueEventStreamOptions | null } = {
      options: null,
    };

    createStreamMock.mockImplementation(async (options) => {
      captured.options = options;
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
    expect(invalidateQueries).not.toHaveBeenCalledWith({ queryKey: queueKey });

    captured.options?.onReconnect?.(1, 10);
    await waitFor(() => expect(result.current.status).toBe("connecting"));
    captured.options?.onOpen?.();
    await waitFor(() => expect(result.current.status).toBe("connected"));

    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queueKey }),
    );

    unmount();
  });

  it("keeps status usable and does not fatal on transient network errors", async () => {
    session.setAccessToken("f4-token");
    const queryClient = new QueryClient();
    const captured: { options: CreateQueueEventStreamOptions | null } = {
      options: null,
    };

    createStreamMock.mockImplementation(async (options) => {
      captured.options = options;
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
    captured.options?.onError?.({
      kind: "network",
      message: "stream closed",
      fatal: false,
    });
    await waitFor(() => expect(result.current.status).toBe("disconnected"));
    expect(result.current.status).not.toBe("error");
    unmount();
  });
});
