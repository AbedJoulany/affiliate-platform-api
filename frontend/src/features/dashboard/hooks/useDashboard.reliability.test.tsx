import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";
import { getDashboardOverview } from "../api/dashboard.api";
import { useDashboard } from "./useDashboard";

vi.mock("../api/dashboard.api", () => ({
  getDashboardOverview: vi.fn(),
}));

const getDashboardMock = vi.mocked(getDashboardOverview);

function dashboardResponse(dayEndUtc: string) {
  return {
    products: {
      total: 0,
      by_status: { draft: 0, active: 0, inactive: 0, archived: 0 },
    },
    queue: {
      total: 0,
      by_status: { draft: 0, queued: 0, scheduled: 0, published: 0, failed: 0 },
    },
    channels: { total: 0, active: 0, inactive: 0 },
    recent_activity: [],
    system_status: {
      status: "operational" as const,
      database: "up" as const,
      generated_at: "2026-11-19T10:00:00Z",
    },
    reporting: {
      timezone: "America/New_York",
      day_start_utc: "2026-11-19T05:00:00Z",
      day_end_utc: dayEndUtc,
      generated_at: "2026-11-19T10:00:00Z",
    },
    publishing: {
      published_today: 0,
      failed_today: 0,
      ambiguous_unresolved: 0,
      by_provider: {
        telegram: { published: 0, failed: 0 },
        facebook: { published: 0, failed: 0 },
      },
    },
    attention_items: [],
    destination_readiness: {
      telegram: { total: 0, active: 0, permission_granted: 0 },
      facebook: {
        total: 0,
        active: 0,
        validated: 0,
        publishing_permission_verified: false,
      },
    },
    automation: { status: "not_configured" as const, last_run_at: null },
  };
}

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

beforeEach(() => {
  setActiveWorkspaceId(WORKSPACE_A);
  session.setAccessToken("dashboard-token");
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  session.clear();
  vi.clearAllMocks();
});

describe("Dashboard reporting rollover", () => {
  it("refetches at the server-provided UTC reporting boundary", async () => {
    vi.setSystemTime(new Date("2026-11-19T04:59:00Z"));
    const dayEnd = "2026-11-19T05:00:00Z";
    getDashboardMock.mockResolvedValue(dashboardResponse(dayEnd));

    const { result, unmount } = renderHook(() => useDashboard(), {
      wrapper: wrapper(new QueryClient()),
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isSuccess).toBe(true);
    expect(getDashboardMock).toHaveBeenCalledTimes(1);

    vi.setSystemTime(new Date(dayEnd));
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    expect(getDashboardMock).toHaveBeenCalledTimes(2);
    unmount();
  });

  it("revalidates after a hidden tab returns past the boundary", async () => {
    const dayEnd = "2026-11-19T05:00:00Z";
    getDashboardMock.mockResolvedValue(dashboardResponse(dayEnd));
    vi.setSystemTime(new Date("2026-11-19T04:59:00Z"));

    const { result, unmount } = renderHook(() => useDashboard(), {
      wrapper: wrapper(new QueryClient()),
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isSuccess).toBe(true);

    vi.setSystemTime(new Date("2026-11-19T06:00:00Z"));
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(getDashboardMock).toHaveBeenCalledTimes(2);
    unmount();
  });
});
