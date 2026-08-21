import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { channelKey } from "@/features/channels/hooks/useChannels";
import { dashboardKey } from "@/features/dashboard/hooks/useDashboard";
import { queueKey, useQueue } from "@/features/queue/hooks/useQueue";
import { productKeys } from "@/features/products/hooks/useProducts";
import {
  setActiveWorkspaceId,
  workspaceScopedQueryKey,
} from "@/lib/workspace";
import { WorkspaceQuerySync } from "@/lib/workspace-query-sync";
import { session } from "@/services/session";
import { WORKSPACE_A, WORKSPACE_B } from "@/test/workspace";

vi.mock("@/features/queue/api/queue.api", () => ({
  getQueue: vi.fn(async () => ({
    items: [{ id: "q-current" }],
    total: 1,
    skip: 0,
    limit: 20,
  })),
}));

vi.mock("@/features/channels/api/channels.api", () => ({
  getChannels: vi.fn(async () => ({ items: [], total: 0 })),
}));

vi.mock("@/features/dashboard/api/dashboard.api", () => ({
  getDashboardOverview: vi.fn(async () => ({
    products: { total: 1, by_status: {} },
    queue: { total: 0, by_status: {} },
    channels: { total: 0, active: 0, inactive: 0 },
    recent_activity: [],
    system_status: { status: "operational", database: "up", generated_at: "" },
  })),
}));

import { getQueue } from "@/features/queue/api/queue.api";
import type { QueueListResponse } from "@/features/queue/types/api";

const getQueueMock = vi.mocked(getQueue);

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client },
      createElement(WorkspaceQuerySync),
      children,
    );
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  session.clear();
});

describe("workspace-aware TanStack Query keys", () => {
  it("does not share queue, channel, or dashboard cache identity across workspaces", () => {
    expect(queueKey(WORKSPACE_A)).not.toEqual(queueKey(WORKSPACE_B));
    expect(channelKey(WORKSPACE_A)).not.toEqual(channelKey(WORKSPACE_B));
    expect(dashboardKey(WORKSPACE_A)).not.toEqual(dashboardKey(WORKSPACE_B));
    expect(productKeys.all).toEqual(["products"]);
    expect(productKeys.list({})).toEqual(["products", "list", {}]);
  });

  it("refetches workspace B after a switch and does not keep A as B", async () => {
    getQueueMock.mockImplementation(async () => ({
      items: [{ id: `q-${session.getActiveWorkspaceId()}` }],
      total: 1,
      skip: 0,
      limit: 20,
    } as QueueListResponse));

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    client.setQueryData(productKeys.all, { items: ["global-product"] });
    setActiveWorkspaceId(WORKSPACE_A);

    const { result, rerender } = renderHook(() => useQueue(undefined, 200), {
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0]).toEqual({ id: `q-${WORKSPACE_A}` });
    expect(client.getQueryData([...queueKey(WORKSPACE_A), undefined, 200, 0])).toEqual(
      expect.objectContaining({ items: [{ id: `q-${WORKSPACE_A}` }] }),
    );

    setActiveWorkspaceId(WORKSPACE_B);
    rerender();

    await waitFor(() => {
      expect(result.current.data?.items[0]).toEqual({ id: `q-${WORKSPACE_B}` });
    });
    expect(
      client.getQueryData([...queueKey(WORKSPACE_A), undefined, 200, 0]),
    ).toBeUndefined();
    expect(client.getQueryData(productKeys.all)).toEqual({ items: ["global-product"] });
    expect(workspaceScopedQueryKey("queue", WORKSPACE_A)).not.toEqual(
      workspaceScopedQueryKey("queue", WORKSPACE_B),
    );
  });

  it("does not fetch GET /queues when no workspace is active", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { result } = renderHook(() => useQueue(undefined, 200), {
      wrapper: wrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(getQueueMock).not.toHaveBeenCalled();
  });
});
