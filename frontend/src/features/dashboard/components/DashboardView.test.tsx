import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardView } from "./DashboardView";
import { getDashboardOverview } from "../api/dashboard.api";
import type { DashboardOverview } from "../types/api";
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

function dashboardData(
  overrides: Partial<DashboardOverview> = {},
): DashboardOverview {
  return {
    products: {
      total: 24,
      by_status: { draft: 0, active: 24, inactive: 0, archived: 0 },
    },
    queue: {
      total: 8,
      by_status: { draft: 1, queued: 2, scheduled: 3, published: 1, failed: 1 },
    },
    channels: { total: 3, active: 2, inactive: 1 },
    recent_activity: [
      {
        resource_type: "queue",
        resource_id: "queue-1",
        title: "منشور Facebook",
        status: "failed",
        occurred_at: "2026-11-18T10:00:00Z",
      },
      {
        resource_type: "product",
        resource_id: "product-1",
        title: "منتج تجريبي",
        status: "active",
        occurred_at: "2026-11-18T09:00:00Z",
      },
    ],
    system_status: {
      status: "operational",
      database: "up",
      generated_at: "2026-11-18T10:30:00Z",
    },
    reporting: {
      timezone: "Asia/Hebron",
      day_start_utc: "2026-11-17T22:00:00Z",
      day_end_utc: "2026-11-18T22:00:00Z",
      generated_at: "2026-11-18T10:30:00Z",
    },
    publishing: {
      published_today: 4,
      failed_today: 2,
      ambiguous_unresolved: 1,
      by_provider: {
        telegram: { published: 1, failed: 1 },
        facebook: { published: 2, failed: 0 },
      },
    },
    attention_items: [
      {
        queue_id: "queue-1",
        title: "منشور Facebook",
        provider: "facebook",
        issue: "failed",
        error_code: "meta_error",
        message: null,
        occurred_at: "2026-11-18T10:00:00Z",
      },
      {
        queue_id: "queue-2",
        title: "نتيجة غير مؤكدة",
        provider: "facebook",
        issue: "ambiguous",
        error_code: "ambiguous_delivery",
        message: null,
        occurred_at: "2026-11-18T08:00:00Z",
      },
    ],
    destination_readiness: {
      telegram: { total: 2, active: 2, permission_granted: 1 },
      facebook: {
        total: 2,
        active: 1,
        validated: 1,
        publishing_permission_verified: false,
      },
    },
    automation: { status: "not_configured", last_run_at: null },
    ...overrides,
  };
}

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

describe("DashboardView", () => {
  it("shows no-workspace state and does not fetch without a workspace id", () => {
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(screen.queryByLabelText("جار التحميل")).not.toBeInTheDocument();
    expect(getDashboardMock).not.toHaveBeenCalled();
  });

  it("renders backend KPIs, attention items, readiness, activity, and navigation", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getDashboardMock.mockResolvedValue(dashboardData());

    renderView();
    await screen.findByTestId("dashboard-kpi-queued");
    expect(getDashboardMock).toHaveBeenCalledTimes(1);

    expect(screen.getByTestId("dashboard-kpi-queued")).toHaveTextContent("2");
    expect(screen.getByTestId("dashboard-kpi-scheduled")).toHaveTextContent("3");
    expect(screen.getByTestId("dashboard-kpi-published-today")).toHaveTextContent("4");
    expect(screen.getByTestId("dashboard-kpi-failed-today")).toHaveTextContent("2");
    expect(screen.getByTestId("dashboard-timezone")).toHaveTextContent("Asia/Hebron");

    expect(screen.getByText("فشل النشر")).toBeInTheDocument();
    expect(screen.getAllByText("نتيجة غير مؤكدة").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("التحقق من الصفحة لا يثبت صلاحية النشر الفعلية عبر Meta.")).toBeInTheDocument();
    expect(screen.getByText("غير مهيأة")).toBeInTheDocument();
    expect(screen.getByText("منتج تجريبي")).toBeInTheDocument();

    const queueLinks = screen.getAllByRole("link", { name: /فتح في قائمة النشر/ });
    expect(queueLinks[0]).toHaveAttribute("href", "/queue?item=queue-1");
    expect(queueLinks[1]).toHaveAttribute("href", "/queue?item=queue-2");
    expect(screen.getByRole("link", { name: /منتج تجريبي/ })).toHaveAttribute(
      "href",
      "/products/product-1",
    );
  });

  it("keeps current queue state separate from daily publishing metrics", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getDashboardMock.mockResolvedValue(dashboardData());

    renderView();
    await screen.findByTestId("dashboard-kpi-published-today");

    const providerSection = screen.getByText("الحالة حسب المزوّد").parentElement?.parentElement;
    expect(providerSection).toBeTruthy();
    expect(within(providerSection as HTMLElement).getByText("هذه الأرقام تعكس الحالة الحالية للعناصر، وليست نشاط اليوم.")).toBeInTheDocument();
  });

  it("shows a calm empty state when there are no attention items", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getDashboardMock.mockResolvedValue(
      dashboardData({ attention_items: [], publishing: { ...dashboardData().publishing, ambiguous_unresolved: 0 } }),
    );

    renderView();
    expect(await screen.findByText("لا توجد عناصر تحتاج إلى متابعة")).toBeInTheDocument();
    expect(screen.queryByText("فتح في قائمة النشر")).not.toBeInTheDocument();
  });

  it("renders loading and retryable error states", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    let resolveRequest: ((value: DashboardOverview) => void) | undefined;
    getDashboardMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    renderView();
    expect(screen.getByLabelText("جار التحميل")).toBeInTheDocument();
    resolveRequest?.(dashboardData());
    await screen.findByTestId("dashboard-kpi-queued");

    cleanup();
    session.clear();
    setActiveWorkspaceId(WORKSPACE_A);
    getDashboardMock.mockRejectedValueOnce(new Error("dashboard unavailable"));
    renderView();
    expect(await screen.findByRole("alert")).toHaveTextContent("dashboard unavailable");
    expect(screen.getByRole("button", { name: "إعادة المحاولة" })).toBeInTheDocument();
  });
});
