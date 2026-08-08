import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { useQueueEventStream } from "./useQueueEventStream";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  session.clear();
});

describe("useQueueEventStream", () => {
  it("connects on mount when a token is present", async () => {
    session.setAccessToken("hook-token");
    createStreamMock.mockImplementation(async (options) => {
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result } = renderHook(() => useQueueEventStream());

    await waitFor(() => {
      expect(createStreamMock).toHaveBeenCalledTimes(1);
    });

    expect(createStreamMock.mock.calls[0][0].token).toBe("hook-token");

    await waitFor(() => {
      expect(result.current.status).toBe("connected");
    });
  });

  it("exposes error when no token is available", () => {
    const { result } = renderHook(() => useQueueEventStream());
    expect(result.current.status).toBe("error");
    expect(createStreamMock).not.toHaveBeenCalled();
  });

  it("disconnects on unmount by aborting the stream", async () => {
    session.setAccessToken("hook-token");
    const observed = { signal: null as AbortSignal | null };

    createStreamMock.mockImplementation(async (options) => {
      observed.signal = options.signal;
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { unmount, result } = renderHook(() => useQueueEventStream());

    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(observed.signal?.aborted).toBe(false);

    unmount();

    await waitFor(() => expect(observed.signal?.aborted).toBe(true));
  });

  it("stays disconnected when disabled", () => {
    session.setAccessToken("hook-token");
    const { result } = renderHook(() =>
      useQueueEventStream({ enabled: false }),
    );
    expect(result.current.status).toBe("disconnected");
    expect(createStreamMock).not.toHaveBeenCalled();
  });
});
