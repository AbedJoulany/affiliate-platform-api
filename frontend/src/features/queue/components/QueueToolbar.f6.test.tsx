import { cleanup, render, screen } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueueRealtimePollingContext } from "../hooks/QueueRealtimePollingContext";
import { QueueRealtimeStatusBadge } from "./QueueRealtimeStatusBadge";
import { QueueToolbar } from "./QueueToolbar";

vi.mock("@/components/common/WorkspaceResultsToolbar", () => ({
  WorkspaceResultsToolbar: ({
    actions,
    refreshing,
    onRefresh,
    countLabel,
  }: {
    actions?: ReactNode;
    refreshing: boolean;
    onRefresh: () => void;
    countLabel: ReactNode;
  }) =>
    createElement(
      "div",
      { "data-testid": "toolbar-shell" },
      createElement("span", null, countLabel),
      createElement(
        "button",
        {
          type: "button",
          "aria-label": "تحديث النتائج",
          "aria-busy": refreshing || undefined,
          onClick: onRefresh,
        },
        "refresh",
      ),
      actions,
    ),
}));

function renderToolbar({
  realtimeStatus,
  pollingEnabled = false,
  withF4Badge = false,
}: {
  realtimeStatus?: "connecting" | "connected" | "disconnected" | "error";
  pollingEnabled?: boolean;
  withF4Badge?: boolean;
} = {}) {
  return render(
    createElement(
      QueueRealtimePollingContext.Provider,
      { value: pollingEnabled },
      createElement(QueueToolbar, {
        search: "",
        status: "",
        channel: "",
        sort: "newest",
        density: "comfortable",
        pageSize: 25,
        resultCount: 3,
        channels: [],
        refreshing: false,
        onSearchChange: () => undefined,
        onStatusChange: () => undefined,
        onChannelChange: () => undefined,
        onSortChange: () => undefined,
        onDensityChange: () => undefined,
        onPageSizeChange: () => undefined,
        onRefresh: () => undefined,
        realtimeStatus,
        actions:
          withF4Badge && realtimeStatus
            ? createElement(QueueRealtimeStatusBadge, { status: realtimeStatus })
            : undefined,
      }),
    ),
  );
}

afterEach(() => {
  cleanup();
});

describe("F6 — QueueToolbar realtime status", () => {
  it("preserves default toolbar behavior when realtimeStatus is omitted", () => {
    renderToolbar();
    expect(screen.getByTestId("toolbar-shell")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تحديث النتائج" })).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps F4 live indicator when connected and does not add polling chrome", () => {
    renderToolbar({
      realtimeStatus: "connected",
      pollingEnabled: false,
      withF4Badge: true,
    });
    const badge = screen.getByRole("status", { name: "البث الحي متصل" });
    expect(badge).toHaveTextContent("مباشر");
    expect(screen.queryByText("تحديث دوري")).not.toBeInTheDocument();
  });

  it("shows the polling indicator when SSE is down and polling is active", () => {
    renderToolbar({
      realtimeStatus: "disconnected",
      pollingEnabled: true,
      withF4Badge: true,
    });
    expect(
      screen.getByRole("status", {
        name: "البث الحي غير متصل — يتم تحديث قائمة النشر تلقائياً بشكل دوري",
      }),
    ).toHaveTextContent("تحديث دوري");
    // F4 connection badge remains authoritative alongside F6 polling chrome.
    expect(
      screen.getByRole("status", {
        name: "البث الحي غير متصل — قائمة النشر تبقى قابلة للاستخدام",
      }),
    ).toHaveTextContent("غير متصل");
  });

  it("shows polling chrome while reconnecting with polling enabled", () => {
    renderToolbar({
      realtimeStatus: "connecting",
      pollingEnabled: true,
    });
    expect(
      screen.getByRole("status", {
        name: "البث الحي غير متصل — يتم تحديث قائمة النشر تلقائياً بشكل دوري",
      }),
    ).toHaveTextContent("تحديث دوري");
  });

  it("does not claim live or polling while connecting without polling", () => {
    renderToolbar({
      realtimeStatus: "connecting",
      pollingEnabled: false,
      withF4Badge: true,
    });
    const badge = screen.getByRole("status", {
      name: "جارٍ الاتصال بالبث الحي",
    });
    expect(badge).toHaveTextContent("جاري الاتصال…");
    expect(badge).not.toHaveTextContent("مباشر");
    expect(screen.queryByText("تحديث دوري")).not.toBeInTheDocument();
  });

  it("preserves F4 error semantics without showing live or polling chrome", () => {
    renderToolbar({
      realtimeStatus: "error",
      pollingEnabled: false,
      withF4Badge: true,
    });
    const badge = screen.getByRole("status", {
      name: "تعذر استمرار البث الحي — قائمة النشر تبقى قابلة للاستخدام",
    });
    expect(badge).toHaveTextContent("البث متوقف");
    expect(screen.queryByText("تحديث دوري")).not.toBeInTheDocument();
  });
});
