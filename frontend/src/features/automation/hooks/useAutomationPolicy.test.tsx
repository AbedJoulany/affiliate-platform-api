import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A, WORKSPACE_B } from "@/test/workspace";
import { getAutomationPolicy, patchAutomationPolicy } from "../api/automation.api";
import type { AutomationPolicy } from "../types/api";
import { automationPolicyKey, useAutomationPolicy, usePatchAutomationPolicy } from "./useAutomationPolicy";

vi.mock("../api/automation.api", () => ({
  getAutomationPolicy: vi.fn(),
  patchAutomationPolicy: vi.fn(),
}));

const getMock = vi.mocked(getAutomationPolicy);
const patchMock = vi.mocked(patchAutomationPolicy);

function policyFor(workspaceId: string, keywords: string): AutomationPolicy {
  return {
    id: null,
    workspace_id: workspaceId,
    revision: 0,
    enabled: false,
    configuration_ready: false,
    execution_available: false,
    execution_state: "disabled",
    destination: null,
    discovery: {
      keywords,
      min_price: null,
      max_price: null,
      min_rating: null,
      min_orders: null,
      min_discount: null,
      min_commission: null,
      max_commission: null,
      products_per_run: 5,
    },
    schedule: { frequency: "daily", preferred_time_local: "09:00", timezone: "UTC", posts_per_day: 1 },
    content: { ai_provider: null, language: null, tone: null, content_type: null, length: null },
    warnings: [],
    created_at: null,
    updated_at: null,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

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

describe("useAutomationPolicy workspace safety", () => {
  it("keeps a late workspace A response out of workspace B state", async () => {
    const pendingA = deferred<AutomationPolicy>();
    getMock.mockImplementation((workspaceId) =>
      workspaceId === WORKSPACE_A
        ? pendingA.promise
        : Promise.resolve(policyFor(WORKSPACE_B, "إعداد B")),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    setActiveWorkspaceId(WORKSPACE_A);

    const { result } = renderHook(() => useAutomationPolicy(), { wrapper: wrapper(client) });
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(WORKSPACE_A));

    act(() => setActiveWorkspaceId(WORKSPACE_B));
    await waitFor(() => expect(getMock).toHaveBeenCalledWith(WORKSPACE_B));
    await waitFor(() => expect(result.current.data?.workspace_id).toBe(WORKSPACE_B));

    act(() => pendingA.resolve(policyFor(WORKSPACE_A, "إعداد A")));
    await waitFor(() => expect(result.current.data?.workspace_id).toBe(WORKSPACE_B));
    expect(client.getQueryData(automationPolicyKey(WORKSPACE_B))).toMatchObject({
      workspace_id: WORKSPACE_B,
    });
  });

  it("updates only the cache for the workspace captured by a pending PATCH", async () => {
    const pendingPatch = deferred<AutomationPolicy>();
    patchMock.mockImplementation((workspaceId) => {
      expect(workspaceId).toBe(WORKSPACE_A);
      return pendingPatch.promise;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    setActiveWorkspaceId(WORKSPACE_A);
    const { result } = renderHook(() => usePatchAutomationPolicy(), { wrapper: wrapper(client) });

    act(() => {
      result.current.mutate({ workspaceId: WORKSPACE_A, patch: { expected_revision: 0 } });
      setActiveWorkspaceId(WORKSPACE_B);
    });
    act(() => pendingPatch.resolve(policyFor(WORKSPACE_A, "نتيجة A")));

    await waitFor(() =>
      expect(client.getQueryData(automationPolicyKey(WORKSPACE_A))).toMatchObject({
        workspace_id: WORKSPACE_A,
        discovery: { keywords: "نتيجة A" },
      }),
    );
    expect(client.getQueryData(automationPolicyKey(WORKSPACE_B))).toBeUndefined();
  });
});
