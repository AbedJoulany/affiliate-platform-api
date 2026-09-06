import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceSettingsView } from "./WorkspaceSettingsView";
import { getWorkspaceSettings } from "../api/settings.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";
import type { WorkspaceSettings } from "../types/api";

vi.mock("../api/settings.api", () => ({
  getWorkspaceSettings: vi.fn(),
  patchWorkspaceSettings: vi.fn(),
}));

vi.mock("@/features/channels/hooks/useChannels", () => ({
  useChannels: () => ({ data: { items: [] }, isPending: false, isError: false }),
}));

vi.mock("@/features/categories/hooks/useCategories", () => ({
  usePlatformReadiness: () => ({
    data: { status: "ready" },
    isPending: false,
    isError: false,
  }),
}));

const getSettingsMock = vi.mocked(getWorkspaceSettings);

const sample: WorkspaceSettings = {
  workspace_id: WORKSPACE_A,
  can_edit: true,
  timezone: "UTC",
  ui_language: "ar",
  aliexpress_target_currency: "USD",
  aliexpress_ship_to_country: "IL",
  aliexpress_target_language: "EN",
  default_ai_provider: "openai",
  default_content_type: "telegram",
  default_tone: "persuasive",
  default_content_language: "ar",
  default_content_length: "medium",
  discovery_default_mode: "general",
  discovery_page_size: 20,
  default_telegram_channel_id: null,
  connections: {
    aliexpress: false,
    telegram_bot: true,
    openai: false,
    gemini: false,
    image_search: false,
  },
  created_at: null,
  updated_at: null,
};

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(createElement(WorkspaceSettingsView, { section: "general" }), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  cleanup();
  session.clear();
  vi.clearAllMocks();
});

describe("WorkspaceSettingsView workspace gating", () => {
  it("shows no-workspace state and does not fetch without a workspace id", () => {
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(getSettingsMock).not.toHaveBeenCalled();
  });

  it("fetches workspace settings when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getSettingsMock.mockResolvedValue(sample);
    renderView();
    expect(await screen.findByRole("button", { name: "حفظ" })).toBeInTheDocument();
    expect(getSettingsMock).toHaveBeenCalledTimes(1);
  });

  it("disables save for members who cannot edit", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getSettingsMock.mockResolvedValue({ ...sample, can_edit: false });
    renderView();
    const save = await screen.findByRole("button", { name: "حفظ" });
    expect(save).toBeDisabled();
    expect(
      screen.getByText("التعديل متاح لمالك مساحة العمل أو حساب المسؤول فقط."),
    ).toBeInTheDocument();
  });
});
