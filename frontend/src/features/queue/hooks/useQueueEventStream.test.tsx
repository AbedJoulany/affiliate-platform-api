import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { WORKSPACE_A, WORKSPACE_B } from "@/test/workspace";
import { useQueueEventStream } from "./useQueueEventStream";

vi.mock("../lib/sse-client", () => ({
  createQueueEventStream: vi.fn(),
}));

import { createQueueEventStream } from "../lib/sse-client";

const createStreamMock = vi.mocked(createQueueEventStream);

beforeEach(() => {
  setActiveWorkspaceId(WORKSPACE_A);
});

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
    expect(createStreamMock.mock.calls[0][0].workspaceId).toBe(WORKSPACE_A);

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

  it("aborts workspace A and opens workspace B when the active workspace changes", async () => {
    session.setAccessToken("hook-token");
    const signals: AbortSignal[] = [];
    createStreamMock.mockImplementation(async (options) => {
      signals.push(options.signal);
      options.onOpen?.();
      await new Promise<void>((resolve) => {
        options.signal.addEventListener("abort", () => resolve(), { once: true });
      });
    });

    const { result } = renderHook(() => useQueueEventStream());
    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(createStreamMock.mock.calls[0][0].workspaceId).toBe(WORKSPACE_A);

    setActiveWorkspaceId(WORKSPACE_B);

    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
    await waitFor(() => expect(createStreamMock).toHaveBeenCalledTimes(2));
    expect(createStreamMock.mock.calls[1][0].workspaceId).toBe(WORKSPACE_B);
    await waitFor(() => expect(result.current.status).toBe("connected"));
    expect(signals[1]?.aborted).toBe(false);
    expect(signals.filter((signal) => !signal.aborted)).toHaveLength(1);
  });
});
