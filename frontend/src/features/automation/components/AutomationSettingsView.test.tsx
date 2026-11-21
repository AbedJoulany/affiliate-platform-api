import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";
import { AutomationSettingsView } from "./AutomationSettingsView";
import type { AutomationPolicy } from "../types/api";

const mutate = vi.fn();
const policy: AutomationPolicy = {
  id: null,
  workspace_id: WORKSPACE_A,
  revision: 0,
  enabled: false,
  configuration_ready: false,
  execution_available: false,
  execution_state: "disabled",
  destination: null,
  discovery: {
    keywords: null,
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

vi.mock("../hooks/useAutomationPolicy", () => ({
  useAutomationPolicy: () => ({ data: policy, isPending: false, isError: false, refetch: vi.fn() }),
  usePatchAutomationPolicy: () => ({ isPending: false, mutate }),
}));
vi.mock("@/features/settings/hooks/useWorkspaceSettings", () => ({
  useWorkspaceSettings: () => ({ data: { can_edit: true }, isPending: false }),
}));
vi.mock("@/features/channels/hooks/useChannels", () => ({
  useChannels: () => ({ data: { items: [] }, isError: false }),
  useFacebookPages: () => ({ data: { items: [] }, isError: false }),
}));

function renderView() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(createElement(AutomationSettingsView), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  session.clear();
  mutate.mockReset();
});

describe("AutomationSettingsView", () => {
  it("shows saved intent separately from unavailable execution", () => {
    setActiveWorkspaceId(WORKSPACE_A);
    renderView();
    expect(screen.getByText("التشغيل التلقائي غير متاح بعد")).toBeInTheDocument();
    expect(screen.getByText("غير متاح")).toBeInTheDocument();
    expect(screen.getByText("لا توجد وجهة محفوظة حالياً.")).toBeInTheDocument();
  });

  it("submits only configuration changes and never an execution action", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    renderView();
    fireEvent.change(screen.getByLabelText("الكلمات المفتاحية"), { target: { value: "سماعات" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ التغييرات" }));
    await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1));
    expect(mutate.mock.calls[0][0]).toMatchObject({
      expected_revision: 0,
      discovery: { keywords: "سماعات" },
    });
    expect(screen.queryByRole("button", { name: /تشغيل|نشر/ })).not.toBeInTheDocument();
  });

  it("does not silently retry a stale revision", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    mutate.mockImplementation((_payload: unknown, options: { onError: (error: unknown) => void }) => {
      options.onError({ status: 409, message: "conflict" });
    });
    renderView();
    fireEvent.change(screen.getByLabelText("الكلمات المفتاحية"), { target: { value: "تغيير محلي" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ التغييرات" }));
    await waitFor(() => expect(screen.getByText(/تغيّرت الإعدادات/)).toBeInTheDocument());
    expect(screen.getByDisplayValue("تغيير محلي")).toBeInTheDocument();
    expect(mutate).toHaveBeenCalledTimes(1);
  });
});
