import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalyticsView } from "./AnalyticsView";
import { getAnalyticsOverview } from "../api/analytics.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) =>
    createElement("a", { href }, children),
}));

vi.mock("../api/analytics.api", () => ({
  getAnalyticsOverview: vi.fn(),
  getCampaignFunnel: vi.fn(),
  getActiveCampaigns: vi.fn(async () => []),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) =>
    createElement("div", { "data-testid": "chart" }, children),
  LineChart: ({ children }: { children: ReactNode }) => createElement("div", null, children),
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

const getOverviewMock = vi.mocked(getAnalyticsOverview);

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(createElement(AnalyticsView), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  cleanup();
  session.clear();
  vi.clearAllMocks();
});

describe("AnalyticsView workspace gating", () => {
  it("shows no-workspace state and does not fetch without a workspace id", () => {
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(getOverviewMock).not.toHaveBeenCalled();
  });

  it("fetches GET /analytics/overview when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getOverviewMock.mockResolvedValue({
      from: "2026-08-05T00:00:00.000Z",
      to: "2026-09-04T23:59:59.999Z",
      total_clicks: 12,
      total_conversions: 3,
      conversion_rate: 0.25,
      total_revenue: "90.00",
      by_day: [{ date: "2026-08-10", clicks: 12, conversions: 3 }],
    });

    renderView();
    await waitFor(() => expect(getOverviewMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(getOverviewMock.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({ from: expect.stringContaining("T"), to: expect.stringContaining("T") }),
    );
  });
});
