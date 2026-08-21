import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardView } from "./DashboardView";
import { getDashboardOverview } from "../api/dashboard.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) =>
    createElement("a", { href }, children),
}));

vi.mock("../api/dashboard.api", () => ({
  getDashboardOverview: vi.fn(),
}));

const getDashboardMock = vi.mocked(getDashboardOverview);

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(createElement(DashboardView), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  cleanup();
  session.clear();
  vi.clearAllMocks();
});

describe("DashboardView workspace gating", () => {
  it("shows no-workspace state and does not fetch without a workspace id", () => {
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(screen.queryByLabelText("جار التحميل")).not.toBeInTheDocument();
    expect(getDashboardMock).not.toHaveBeenCalled();
  });

  it("fetches GET /dashboard when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getDashboardMock.mockResolvedValue({
      products: { total: 24, by_status: { draft: 0, active: 24, inactive: 0, archived: 0 } },
      queue: { total: 0, by_status: { draft: 0, queued: 0, scheduled: 0, published: 0 } },
      channels: { total: 0, active: 0, inactive: 0 },
      recent_activity: [],
      system_status: {
        status: "operational",
        database: "up",
        generated_at: "2026-07-16T00:00:00Z",
      },
    });

    renderView();
    await waitFor(() => expect(getDashboardMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("24")).toBeInTheDocument();
  });
});
